from __future__ import annotations

import json
import sys
from typing import Any

from . import ANALYSIS_TYPE_REPLAY
from .campaign import list_raw_jobs
from .paths import CONFIG, SRC_DIR, STUDY_ROOT

sys.path.insert(0, str(STUDY_ROOT))
from src.classical import greedy_then_swaps  # type: ignore  # noqa: E402
from src.fixtures import generate_simulation_fixtures, instance_from_spec as fixture_instance  # type: ignore  # noqa: E402
from src.fixtures import hardware_instances  # type: ignore  # noqa: E402
from src.policies import apply_policy  # type: ignore  # noqa: E402
from src.qaoa import independent_statevector_amplitudes, probability_dict  # type: ignore  # noqa: E402
from src.replay import PREFIXES, replay_fixture  # type: ignore  # noqa: E402
from src.spec import spec_from_instance  # type: ignore  # noqa: E402


def hardware_pool_map() -> dict[tuple[str, str, int], list[str]]:
    pools = {}
    for item in list_raw_jobs():
        data = item["data"]
        mapping = {int(m["pub_index"]): m for m in data.get("pub_mapping") or []}
        for pub in data.get("pubs") or []:
            meta = mapping[int(pub["pub_index"])]
            key = (data["job_id"], meta["instance_id"], int(meta["p"]))
            pools[key] = [str(s) for s in pub.get("shots") or []]
    return pools


def replay_hardware_pools() -> dict[str, Any]:
    pools = hardware_pool_map()
    instances = {inst.instance_id: inst for inst in hardware_instances()}
    rows = []
    compact = []
    for (job_id, fixture, depth), shots in sorted(pools.items()):
        inst = instances[fixture]
        replayed = replay_fixture(inst, shots)
        for key, result in replayed["results"].items():
            rows.append(
                {
                    "job_id": job_id,
                    "fixture": fixture,
                    "p": depth,
                    "scenario": key,
                    "policy": result.get("policy"),
                    "status": result.get("status"),
                    "reason": result.get("reason"),
                    "selected": result.get("selected"),
                    "strict_improvement": result.get("strict_improvement"),
                    "sample_origin": "decision_hardware",
                    "analysis_type": ANALYSIS_TYPE_REPLAY,
                    "timing_origin": "injected_schedule" if "late" in key else "fixture_default_elapsed",
                }
            )
        compact.append(
            {
                "job_id": job_id,
                "fixture": fixture,
                "p": depth,
                "n_results": len(replayed["results"]),
                "greedy_utility": replayed.get("greedy", {}).get("utility"),
                "analysis_type": ANALYSIS_TYPE_REPLAY,
                "sample_origin": "decision_hardware",
            }
        )
    elapsed_by_job = {item["data"]["job_id"]: float(item["data"].get("client_elapsed_seconds") or 0) for item in list_raw_jobs()}
    deadline_rows = []
    for (job_id, fixture, depth), shots in sorted(pools.items()):
        inst = instances[fixture]
        greedy = greedy_then_swaps(inst)
        incumbent = {"bitstring": greedy["bitstring"], "utility": greedy["utility"]} if greedy.get("status") == "ok" else None
        spec = spec_from_instance(inst, request_id=f"post-replay-{job_id}-{fixture}-p{depth}")
        linkage = {
            "request_id": spec["request_id"],
            "source_hash": spec["source_hash"],
            "circuit_hash": "frozen-hardware-pool",
            "expected_circuit_hash": "frozen-hardware-pool",
            "expected_request_id": spec["request_id"],
            "expected_source_hash": spec["source_hash"],
        }
        observed = elapsed_by_job[job_id]
        for prefix in PREFIXES:
            for deadline in (5, 30, 300):
                spec["deadline_seconds"] = deadline
                for policy in ("P0", "P1", "P2", "P3"):
                    observed_out = apply_policy(policy, spec, shots[:prefix], incumbent, observed, linkage, trusted_source=spec)
                    deadline_rows.append(
                        {
                            "job_id": job_id,
                            "fixture": fixture,
                            "p": depth,
                            "prefix": prefix,
                            "deadline": deadline,
                            "policy": policy,
                            "status": observed_out.get("status"),
                            "reason": observed_out.get("reason"),
                            "timing_origin": "observed_receipt",
                            "now_elapsed": observed,
                            "analysis_type": ANALYSIS_TYPE_REPLAY,
                            "sample_origin": "decision_hardware",
                            "note": "Counterfactual deadline applied to the observed full-job client receipt time. Prefixes remain dependent on the already-paid full shot budget.",
                        }
                    )
                    for schedule, elapsed in (("on_time", max(0.0, deadline - 1.0)), ("late", deadline + 1.0)):
                        inj = apply_policy(policy, spec, shots[:prefix], incumbent, elapsed, linkage, trusted_source=spec)
                        deadline_rows.append(
                            {
                                "job_id": job_id,
                                "fixture": fixture,
                                "p": depth,
                                "prefix": prefix,
                                "deadline": deadline,
                                "policy": policy,
                                "status": inj.get("status"),
                                "reason": inj.get("reason"),
                                "timing_origin": "injected_schedule",
                                "schedule": schedule,
                                "now_elapsed": elapsed,
                                "analysis_type": ANALYSIS_TYPE_REPLAY,
                                "sample_origin": "decision_hardware",
                            }
                        )
    return {
        "analysis_type": ANALYSIS_TYPE_REPLAY,
        "scenario_rows": rows,
        "compact": compact,
        "deadline_rows": deadline_rows,
        "n_scenario_rows": len(rows),
        "n_deadline_rows": len(deadline_rows),
    }


def replay_simulation_fixtures() -> dict[str, Any]:
    sim_file = CONFIG / "simulation_fixtures.json"
    if sim_file.is_file():
        payload = json.loads(sim_file.read_text(encoding="utf-8"))
        kept = payload.get("kept") or []
    else:
        kept = generate_simulation_fixtures()["kept"]
    rows = []
    full = []
    for spec_row in kept:
        inst = fixture_instance(spec_row)
        amps = independent_statevector_amplitudes(inst, [0.3], [0.4])
        probs = probability_dict(amps, inst.n)
        keys = list(probs)
        weights = [probs[k] for k in keys]
        seed = 4242 + len(str(spec_row.get("instance_id", "")))
        rng = __import__("random").Random(seed)
        shots = rng.choices(keys, weights=weights, k=1024)
        replayed = replay_fixture(inst, shots)
        compact_results = {
            name: {
                "policy": val.get("policy"),
                "status": val.get("status"),
                "reason": val.get("reason"),
                "selected": val.get("selected"),
            }
            for name, val in replayed["results"].items()
        }
        full.append(
            {
                "instance_id": inst.instance_id,
                "seed": seed,
                "seed_convention": "4242 + len(instance_id)",
                "shared_seed_note": "S01–S24 IDs have equal length, so they share seed 4245.",
                "angles": [0.3, 0.4],
                "angle_note": "Arbitrary unit-test/replay angles, not simulator-optimised QAOA parameters.",
                "results": compact_results,
                "greedy": replayed["greedy"],
                "evidence_type": "sampled_simulation",
                "analysis_type": ANALYSIS_TYPE_REPLAY,
            }
        )
        rows.append(
            {
                "instance_id": inst.instance_id,
                "n_results": len(replayed["results"]),
                "greedy_utility": replayed["greedy"].get("utility"),
                "greedy_status": replayed["greedy"].get("status"),
                "seed": seed,
            }
        )
    return {
        "n_fixtures": len(full),
        "summaries": rows,
        "fixtures": full,
        "parameter_source_correction": "Historical replay.py labels p=2 prefix rows as parameter_source=frozen_p1 even when the sampled pool used p=2 amplitudes. Corrected labels appear only in this post-collection artifact.",
    }
