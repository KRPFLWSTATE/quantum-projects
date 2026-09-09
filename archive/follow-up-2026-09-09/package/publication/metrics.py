from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from datetime import datetime
from typing import Any

from . import ANALYSIS_TYPE_HARDWARE
from .campaign import JOB_ORDER, list_raw_jobs
from .paths import ATTEMPTS, DERIVED, SRC_DIR, STUDY_ROOT

sys.path.insert(0, str(STUDY_ROOT))
from src.classical import greedy_then_swaps  # type: ignore  # noqa: E402
from src.fixtures import hardware_instances  # type: ignore  # noqa: E402
from src.model import bits_from_little_endian_bitstring, is_feasible, utility  # type: ignore  # noqa: E402
from src.oracle import exact_summary  # type: ignore  # noqa: E402
from src.policies import apply_policy  # type: ignore  # noqa: E402
from src.spec import spec_from_instance  # type: ignore  # noqa: E402


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def seconds_between(a: str | None, b: str | None) -> float | None:
    left = parse_iso(a)
    right = parse_iso(b)
    if left is None or right is None:
        return None
    return (right - left).total_seconds()


def instance_catalog() -> dict[str, Any]:
    rows = {}
    for inst in hardware_instances():
        summary = exact_summary(inst)
        greedy = greedy_then_swaps(inst)
        n_opt = len(summary["optimum_bitstrings"])
        rows[inst.instance_id] = {
            "instance": inst,
            "summary": summary,
            "greedy": greedy,
            "n_feasible": int(summary["feasible_count"]),
            "n_optima": n_opt,
            "optimum": float(summary["optimum_utility"]),
            "uniform_feas": int(summary["feasible_count"]) / 64.0,
            "uniform_opt": n_opt / 64.0,
            "opt_set": set(summary["optimum_bitstrings"]),
        }
    return rows


def policy_outcome(result: dict[str, Any], greedy_u: float | None, selected_u: float | None, selected_feasible: bool) -> str:
    status = result.get("status")
    if status == "abstain":
        return "abstained"
    if status == "fallback_incumbent":
        return "fallback"
    if status == "accept" and result.get("policy") == "P0":
        if not selected_feasible:
            return "accepted_unguarded"
        if greedy_u is None or selected_u is None:
            return "accepted_unguarded"
        if selected_u > greedy_u + 1e-9:
            return "improved"
        if abs(selected_u - greedy_u) <= 1e-9:
            return "equal_incumbent"
        return "accepted_unguarded"
    if status == "accept":
        if result.get("strict_improvement"):
            return "improved"
        return "equal_incumbent"
    return str(status)


def evaluate_pub(job: dict[str, Any], pub: dict[str, Any], meta: dict[str, Any], catalog: dict[str, Any], elapsed: float) -> dict[str, Any]:
    inst_id = meta["instance_id"]
    depth = int(meta["p"])
    cat = catalog[inst_id]
    inst = cat["instance"]
    shots = [str(s) for s in pub.get("shots") or []]
    counts = {str(k): int(v) for k, v in (pub.get("counts") or {}).items()}
    hist = Counter(shots)
    if dict(hist) != counts:
        raise ValueError(f"counts/histogram mismatch {job['job_id']} pub {meta.get('pub_index')}")
    if len(shots) != 1024:
        raise ValueError("shot count != 1024")
    feas = 0
    opt = 0
    best_feas = None
    for bitstring in shots:
        bits = bits_from_little_endian_bitstring(bitstring, inst.n)
        if is_feasible(inst, bits):
            feas += 1
            u = utility(inst, bits)
            best_feas = u if best_feas is None else max(best_feas, u)
            if bitstring in cat["opt_set"]:
                opt += 1
    greedy = cat["greedy"]
    greedy_u = float(greedy["utility"]) if greedy.get("status") == "ok" else None
    spec = spec_from_instance(inst, request_id=f"{job['intent']}-{inst_id}-p{depth}")
    circuit_hash = meta.get("isa_qpy_sha256") or "missing"
    linkage = {
        "request_id": spec["request_id"],
        "source_hash": spec["source_hash"],
        "circuit_hash": circuit_hash,
        "expected_circuit_hash": circuit_hash,
        "expected_request_id": spec["request_id"],
        "expected_source_hash": spec["source_hash"],
    }
    incumbent = {"bitstring": greedy["bitstring"], "utility": greedy["utility"]} if greedy.get("status") == "ok" else None
    policies = {}
    for policy in ("P0", "P1", "P2", "P3"):
        result = apply_policy(policy, spec, shots, incumbent, elapsed, linkage, trusted_source=spec)
        selected = result.get("selected")
        selected_feasible = False
        selected_u = None
        if selected:
            bits = bits_from_little_endian_bitstring(str(selected), inst.n)
            selected_feasible = is_feasible(inst, bits)
            selected_u = utility(inst, bits)
        independent_improve = (
            selected_feasible and greedy_u is not None and selected_u is not None and selected_u > greedy_u + 1e-9
        )
        policies[policy] = {
            "status": result.get("status"),
            "reason": result.get("reason"),
            "selected": selected,
            "selected_feasible": selected_feasible,
            "selected_utility": selected_u,
            "strict_improvement_field": result.get("strict_improvement"),
            "independent_strict_improvement": independent_improve,
            "outcome": policy_outcome(result, greedy_u, selected_u, selected_feasible),
            "is_optimum": bool(selected in cat["opt_set"]) if selected else False,
        }
    opt_u = cat["optimum"]
    gap = None if best_feas is None else abs(opt_u - best_feas)
    return {
        "job_id": job["job_id"],
        "intent": job["intent"],
        "fixture": inst_id,
        "p": depth,
        "pub_index": int(meta["pub_index"]),
        "isa_qpy_sha256": circuit_hash,
        "n_shots": len(shots),
        "feasible_shot_fraction": feas / 1024.0,
        "optimal_hit_fraction": opt / 1024.0,
        "best_feasible_utility": best_feas,
        "exact_optimum": opt_u,
        "absolute_optimality_gap": gap,
        "greedy_incumbent_utility": greedy_u,
        "pool_contains_optimum": opt > 0,
        "strict_improvement_possible": greedy_u is not None and opt_u > greedy_u + 1e-9,
        "uniform_feasibility_probability": cat["uniform_feas"],
        "uniform_optimal_hit_probability": cat["uniform_opt"],
        "evidence_type": ANALYSIS_TYPE_HARDWARE,
        "policies": policies,
        "sample_origin": "decision_hardware",
    }


def job_rows() -> list[dict[str, Any]]:
    attempts = {}
    for path in ATTEMPTS.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        attempts[data.get("intent")] = data
    rows = []
    for item in list_raw_jobs():
        data = item["data"]
        metrics = data.get("metrics") or {}
        stamps = metrics.get("timestamps") or {}
        usage = metrics.get("usage") or {}
        attempt = attempts.get(data.get("intent")) or {}
        rows.append(
            {
                "block": item["block"],
                "job_id": data["job_id"],
                "backend": attempt.get("backend"),
                "client_dispatch_utc": data.get("created_utc"),
                "provider_created_utc": stamps.get("created"),
                "provider_running_utc": stamps.get("running"),
                "provider_finished_utc": stamps.get("finished"),
                "client_receipt_utc": data.get("result_received_utc"),
                "client_elapsed_seconds": data.get("client_elapsed_seconds"),
                "provider_created_to_running_s": seconds_between(stamps.get("created"), stamps.get("running")),
                "provider_running_to_finished_s": seconds_between(stamps.get("running"), stamps.get("finished")),
                "provider_created_to_finished_s": seconds_between(stamps.get("created"), stamps.get("finished")),
                "charged_usage_seconds": data.get("charged_usage_seconds"),
                "qpu_charge_time_seconds": usage.get("qpu_charge_time_seconds"),
                "billing_status": usage.get("status"),
                "shots_valid": data.get("shots_valid"),
                "n_pubs": data.get("n_pubs_observed"),
                "protocol_hash": attempt.get("protocol_hash"),
                "deadline_seconds": attempt.get("deadline_seconds"),
                "evidence_type": data.get("evidence_type"),
                "mock": data.get("mock"),
                "circuits_execution_time_ns": metrics.get("circuits_execution_time_ns"),
                "qiskit_version": metrics.get("qiskit_version"),
            }
        )
    return rows


def pub_rows() -> list[dict[str, Any]]:
    catalog = instance_catalog()
    attempts = {json.loads(p.read_text())["intent"]: json.loads(p.read_text()) for p in ATTEMPTS.glob("*.json")}
    # reload cleanly
    attempts = {}
    for path in ATTEMPTS.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        attempts[data["intent"]] = data
    rows = []
    for item in list_raw_jobs():
        data = item["data"]
        elapsed = data.get("client_elapsed_seconds")
        if elapsed is None:
            raise ValueError(f"missing client_elapsed_seconds for {data.get('job_id')}")
        elapsed = float(elapsed)
        mapping = {int(m["pub_index"]): m for m in data.get("pub_mapping") or []}
        for pub in data.get("pubs") or []:
            meta = mapping[int(pub["pub_index"])]
            row = evaluate_pub(data, pub, meta, catalog, elapsed)
            row["block"] = item["block"]
            row["backend"] = (attempts.get(data["intent"]) or {}).get("backend")
            rows.append(row)
    return rows


def flatten_policy_rows(pubs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for pub in pubs:
        for policy, payload in pub["policies"].items():
            out.append(
                {
                    "block": pub["block"],
                    "job_id": pub["job_id"],
                    "fixture": pub["fixture"],
                    "p": pub["p"],
                    "pub_index": pub["pub_index"],
                    "policy": policy,
                    **payload,
                    "evidence_type": ANALYSIS_TYPE_HARDWARE,
                    "sample_origin": "decision_hardware",
                }
            )
    return out


def grouped_rows(pubs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in pubs:
        groups.setdefault((row["fixture"], int(row["p"])), []).append(row)
    out = []
    for (fixture, depth), items in sorted(groups.items()):
        hits = [float(r["optimal_hit_fraction"]) for r in items]
        feas = [float(r["feasible_shot_fraction"]) for r in items]
        out.append(
            {
                "fixture": fixture,
                "p": depth,
                "n_blocks": len(items),
                "optimal_hit_mean": statistics.fmean(hits),
                "optimal_hit_median": statistics.median(hits),
                "optimal_hit_min": min(hits),
                "optimal_hit_max": max(hits),
                "feasible_mean": statistics.fmean(feas),
                "uniform_optimal_hit_probability": items[0]["uniform_optimal_hit_probability"],
                "all_pools_contain_optimum": all(r["pool_contains_optimum"] for r in items),
                "evidence_type": ANALYSIS_TYPE_HARDWARE,
                "sampling_unit": "six_clustered_blocks",
            }
        )
    return out


def checkpoints(pubs: list[dict[str, Any]], catalog: dict[str, Any]) -> dict[str, Any]:
    optima = {k: catalog[k]["optimum"] for k in ("D1", "D2", "D3", "D4", "D5", "D6")}
    greedy = {k: catalog[k]["greedy"]["utility"] for k in optima}
    n_opt_pools = sum(1 for r in pubs if r["pool_contains_optimum"])
    p0_feas = sum(1 for r in pubs if r["policies"]["P0"]["selected_feasible"])
    guarded = {}
    for policy in ("P1", "P2", "P3"):
        opt_sel = sum(1 for r in pubs if r["policies"][policy]["is_optimum"] and r["policies"][policy]["selected_feasible"])
        improve = sum(1 for r in pubs if r["policies"][policy]["independent_strict_improvement"])
        guarded[policy] = {"feasible_optima": opt_sel, "improve_over_greedy": improve}
    d4p2 = [r for r in pubs if r["fixture"] == "D4" and r["p"] == 2]
    d4_mean = statistics.fmean(r["optimal_hit_fraction"] for r in d4p2) if d4p2 else None
    elapsed = [r for r in job_rows()]
    client = [float(r["client_elapsed_seconds"]) for r in elapsed]
    containment = {}
    for fx in ("D1", "D2", "D3", "D4", "D5", "D6"):
        p_opt = float(catalog[fx]["uniform_opt"])
        containment[fx] = {
            "n_optima": catalog[fx]["n_optima"],
            "p_opt_uniform": p_opt,
            "p_at_least_one_optimum_in_1024_iid_uniform": 1.0 - (1.0 - p_opt) ** 1024,
        }
    return {
        "exact_optima": optima,
        "greedy_incumbent_utilities": greedy,
        "n_pubs": len(pubs),
        "n_pools_with_optimum": n_opt_pools,
        "p0_feasible_modal": p0_feas,
        "guarded": guarded,
        "d4_p2_optimal_hit_mean": d4_mean,
        "uniform_opt": 1 / 64,
        "client_elapsed_min": min(client) if client else None,
        "client_elapsed_max": max(client) if client else None,
        "all_within_30s": all(v <= 30.0 for v in client),
        "uniform_opt_containment_1024": containment,
    }


def worked_example(catalog: dict[str, Any]) -> dict[str, Any]:
    inst = catalog["D1"]["instance"]
    bitstring = "011001"
    bits = bits_from_little_endian_bitstring(bitstring, 6)
    mapping = {f"task_{i}": int(bits[i]) for i in range(6)}
    display = {f"display_char_{i}": bitstring[i] for i in range(6)}
    return {
        "fixture": "D1",
        "displayed_ibm_style_little_endian_string": bitstring,
        "convention": "The displayed six-character string is little-endian over task_0..task_5: left character is task_5, right character is task_0.",
        "task_bits": mapping,
        "display_positions": display,
        "feasible": is_feasible(inst, bits),
        "utility": utility(inst, bits),
        "benefits": list(inst.benefits),
        "conflicts": [list(p) for p in inst.conflicts],
        "note": "Feasibility is cardinality k=3 with no selected conflict pair, computed from business constraints, not from QUBO energy.",
    }


def p2_layer_note() -> list[dict[str, Any]]:
    params = json.loads((DERIVED / "qaoa_parameters.json").read_text(encoding="utf-8"))
    rows = []
    for fx in params["fixtures"]:
        best = fx["p2"]["best"]
        gammas = list(best.get("gammas") or [])
        betas = list(best.get("betas") or [])
        identity = len(gammas) >= 2 and abs(float(gammas[1])) < 1e-15 and abs(float(betas[1])) < 1e-15
        rows.append(
            {
                "fixture": fx["instance_id"],
                "p": 2,
                "kind": best.get("kind"),
                "gammas": gammas,
                "betas": betas,
                "second_layer_identity": identity,
            }
        )
    return rows
