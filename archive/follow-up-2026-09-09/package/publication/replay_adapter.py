"""Post-collection replay adapter. Does not rewrite frozen src/replay.py."""
from __future__ import annotations

import copy
import json
import sys
from typing import Any

from . import ANALYSIS_TYPE_REPLAY
from .campaign import JOB_ORDER, list_raw_jobs
from .paths import DATA, PROTOCOL, STUDY_ROOT

sys.path.insert(0, str(STUDY_ROOT))
from src.classical import greedy_then_swaps  # type: ignore  # noqa: E402
from src.fixtures import generate_simulation_fixtures, hardware_instances  # type: ignore  # noqa: E402
from src.model import bits_from_little_endian_bitstring, is_feasible, utility  # type: ignore  # noqa: E402
from src.oracle import exact_summary  # type: ignore  # noqa: E402
from src.policies import apply_policy  # type: ignore  # noqa: E402
from src.replay import PREFIXES, add_first_new_conflict, capacity_k2, meaning_change, replay_fixture, rotate_benefits  # type: ignore  # noqa: E402
from src.spec import instance_from_spec, spec_from_instance  # type: ignore  # noqa: E402


SCENARIO_MATRIX = [
    "unchanged",
    "objective_drift",
    "constraint_drift",
    "capacity_k2",
    "meaning_change",
    "metadata_only_version",
    "malformed_linkage",
    "missing_linkage",
    "empty_candidates",
    "late_arrival",
]


def _independent(result: dict[str, Any], spec: dict[str, Any], greedy_now: dict[str, Any], original_opt: set[str]) -> dict[str, Any]:
    selected = result.get("selected")
    reasons = result.get("reason")
    if reasons == "VARIABLE_MEANING_CHANGED" or spec.get("variable_meanings_changed"):
        if result.get("status") in {"abstain", "fallback_incumbent"} or "VARIABLE_MEANING_CHANGED" in str(reasons):
            return {
                "selected": selected,
                "status": result.get("status"),
                "reason": reasons,
                "feasibility_current": None,
                "utility_current": None,
                "incumbent_utility_current": greedy_now.get("utility") if greedy_now.get("status") == "ok" else None,
                "exact_optimum_current": None,
                "regret": None,
                "strict_improvement_independent": None,
                "originally_sampled_optimum_still_valid": None,
                "comparison": "undefined_incompatible_meanings",
            }
    inst = instance_from_spec(spec)
    summary = exact_summary(inst)
    greedy_u = greedy_now.get("utility") if greedy_now.get("status") == "ok" else None
    feas = None
    selected_u = None
    if selected:
        bits = bits_from_little_endian_bitstring(str(selected), inst.n)
        feas = is_feasible(inst, bits)
        selected_u = utility(inst, bits)
    opt_u = float(summary["optimum_utility"]) if summary.get("satisfiable") else None
    regret = None if selected_u is None or opt_u is None else opt_u - selected_u
    improve = feas is True and greedy_u is not None and selected_u is not None and selected_u > greedy_u + 1e-9
    still = None
    if original_opt:
        still = any(s in summary.get("optimum_bitstrings") or [] for s in original_opt)
        # whether originally sampled strings that were optima remain feasible optima under current spec
        still = any(
            is_feasible(inst, bits_from_little_endian_bitstring(s, inst.n))
            and utility(inst, bits_from_little_endian_bitstring(s, inst.n)) == opt_u
            for s in original_opt
        ) if opt_u is not None else False
    return {
        "selected": selected,
        "status": result.get("status"),
        "reason": reasons,
        "feasibility_current": feas,
        "utility_current": selected_u,
        "incumbent_utility_current": greedy_u,
        "exact_optimum_current": opt_u,
        "regret": regret,
        "strict_improvement_independent": improve,
        "originally_sampled_optimum_still_valid": still,
        "comparison": "current_specification",
        "p0_unguarded": result.get("policy") == "P0",
    }


def run_replay_adapter() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    isa_expected = protocol.get("isa_qpy_sha256") or {}
    instances = {inst.instance_id: inst for inst in hardware_instances()}
    original_opt = {iid: set(exact_summary(inst)["optimum_bitstrings"]) for iid, inst in instances.items()}
    archived = json.loads((DATA / "decisions.json").read_text(encoding="utf-8"))
    drill = []
    compact_counts: dict[str, int] = {}
    reconcile = []
    first_job = JOB_ORDER[0]
    for item in list_raw_jobs():
        data = item["data"]
        job_id = data["job_id"]
        elapsed = float(data["client_elapsed_seconds"])
        mapping = {int(m["pub_index"]): m for m in data["pub_mapping"]}
        for pub in data["pubs"]:
            meta = mapping[int(pub["pub_index"])]
            fx = meta["instance_id"]
            depth = int(meta["p"])
            shots = [str(s) for s in pub["shots"]]
            inst = instances[fx]
            qpy_name = f"{fx}_p{depth}_isa.qpy"
            archived_isa = meta.get("isa_qpy_sha256")
            protocol_isa = isa_expected.get(qpy_name)
            request_id = f"{data['intent']}-{fx}-p{depth}"
            base_spec = spec_from_instance(inst, request_id=request_id)
            archived_source_hash = base_spec["source_hash"]
            observed_linkage = {
                "request_id": request_id,
                "source_hash": archived_source_hash,
                "circuit_hash": archived_isa,
                "expected_circuit_hash": protocol_isa,
                "expected_request_id": request_id,
                "expected_source_hash": archived_source_hash,
                "require_request_id": True,
                "identity_origin": "archived_pub",
                "job_id": job_id,
                "pub_index": int(meta["pub_index"]),
                "injected_envelope": False,
            }
            scenarios = {
                "unchanged": (base_spec, observed_linkage, shots, elapsed, False),
                "objective_drift": (rotate_benefits(copy.deepcopy(base_spec)), observed_linkage, shots, elapsed, False),
                "constraint_drift": (add_first_new_conflict(copy.deepcopy(base_spec)), observed_linkage, shots, elapsed, False),
                "capacity_k2": (capacity_k2(copy.deepcopy(base_spec)), observed_linkage, shots, elapsed, False),
                "meaning_change": (meaning_change(copy.deepcopy(base_spec)), observed_linkage, shots, elapsed, False),
            }
            meta_ver = copy.deepcopy(base_spec)
            meta_ver["current_version"] = "v-label-only"
            scenarios["metadata_only_version"] = (meta_ver, observed_linkage, shots, elapsed, False)
            bad = dict(observed_linkage)
            bad.update({"circuit_hash": "injected-wrong-circuit", "injected_envelope": True, "identity_origin": "synthetic_replay_envelope"})
            scenarios["malformed_linkage"] = (base_spec, bad, shots, elapsed, True)
            missing = {k: observed_linkage[k] for k in ("expected_circuit_hash", "expected_request_id", "expected_source_hash")}
            missing.update({"request_id": None, "source_hash": None, "circuit_hash": None, "injected_envelope": True, "identity_origin": "synthetic_replay_envelope"})
            scenarios["missing_linkage"] = (base_spec, missing, shots, elapsed, True)
            scenarios["empty_candidates"] = (base_spec, observed_linkage, [], elapsed, False)
            scenarios["late_arrival"] = (base_spec, observed_linkage, shots, 31.0, True)

            bounded = job_id == first_job or True
            # Unchanged + faults on all 72; drift only on first block to bound size.
            names = SCENARIO_MATRIX if job_id == first_job else ["unchanged", "metadata_only_version", "malformed_linkage", "missing_linkage", "empty_candidates", "late_arrival"]
            for name in names:
                spec, linkage, pool, now_elapsed, injected = scenarios[name]
                current = instance_from_spec(spec)
                greedy_now = greedy_then_swaps(current)
                incumbent = {"bitstring": greedy_now["bitstring"], "utility": greedy_now["utility"]} if greedy_now.get("status") == "ok" else None
                trusted = base_spec
                for policy in ("P0", "P1", "P2", "P3"):
                    result = apply_policy(policy, spec, pool, incumbent, now_elapsed, linkage, trusted_source=trusted)
                    result["policy"] = policy
                    indep = _independent(result, spec, greedy_now, original_opt[fx])
                    key = f"{name}:{policy}"
                    compact_counts[key] = compact_counts.get(key, 0) + 1
                    row = {
                        "job_id": job_id,
                        "pub_index": int(meta["pub_index"]),
                        "fixture": fx,
                        "p": depth,
                        "isa_qpy_sha256_archived": archived_isa,
                        "isa_qpy_sha256_protocol": protocol_isa,
                        "isa_match": archived_isa == protocol_isa,
                        "archived_request_id": request_id,
                        "scenario": name,
                        "policy": policy,
                        "timing_origin": "injected_schedule" if name == "late_arrival" else "observed_receipt",
                        "injected_envelope": injected,
                        "sample_origin": "decision_hardware",
                        "analysis_type": ANALYSIS_TYPE_REPLAY,
                        **indep,
                    }
                    drill.append(row)
                    if name == "unchanged" and policy in {"P0", "P1", "P2", "P3"}:
                        arch_key = f"{request_id}:{policy}"
                        hist = archived.get(arch_key)
                        if hist:
                            reconcile.append(
                                {
                                    "key": arch_key,
                                    "job_id": job_id,
                                    "pub_index": int(meta["pub_index"]),
                                    "policy": policy,
                                    "archived_status": hist.get("status"),
                                    "recomputed_status": result.get("status"),
                                    "archived_selected": hist.get("selected"),
                                    "recomputed_selected": result.get("selected"),
                                    "status_match": hist.get("status") == result.get("status"),
                                    "selected_match": hist.get("selected") == result.get("selected"),
                                }
                            )

    n_diff = sum(1 for row in reconcile if not (row["status_match"] and row["selected_match"]))
    generated = generate_simulation_fixtures()
    sim = []
    for spec in generated.get("kept") or []:
        iid = spec.get("instance_id")
        sim.append(
            {
                "instance_id": iid,
                "historical_seed_rule": f"4242 + len(instance_id) = {4242 + len(str(iid))}",
                "parameter_note": "arbitrary [0.3]/[0.4] angles are not simulator-optimised",
                "shared_seed_coupling": "equally long S01–S24 IDs share a seed",
            }
        )

    # Retain frozen 24-fixture replay on one empty/full placeholder is expensive; call replay_fixture with empty then skip.
    # Instead load historical file length.
    hist_replay = json.loads((DATA / "derived" / "policy_replay.json").read_text(encoding="utf-8")) if (DATA / "derived" / "policy_replay.json").is_file() else {}

    p2_meta = [row for row in drill if row["scenario"] == "metadata_only_version" and row["policy"] == "P2"]
    p2_accept = sum(1 for row in p2_meta if row["status"] == "accept")

    return {
        "scenario_matrix": SCENARIO_MATRIX,
        "n_drill_rows": len(drill),
        "compact_counts": compact_counts,
        "p2_metadata_only_accept_count": p2_accept,
        "p2_contract": "Frozen verifier overwrites a metadata-only current_version mismatch with payload equality. P2 is not a strict version-label gate.",
        "n_reconcile": len(reconcile),
        "n_reconcile_differences": n_diff,
        "reconcile_differences": [row for row in reconcile if not (row["status_match"] and row["selected_match"])][:50],
        "historical_simulation_replay_keys": list(hist_replay)[:8] if isinstance(hist_replay, dict) else {"type": type(hist_replay).__name__},
        "simulation_fixture_provenance": sim[:24],
        "drill_rows": drill,
        "analysis_type": ANALYSIS_TYPE_REPLAY,
    }
