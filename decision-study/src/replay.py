"""Deterministic specification-change and injected-fault replay envelopes."""

from __future__ import annotations

import copy
from itertools import combinations
from typing import Any

from .classical import greedy_then_swaps
from .model import DecisionInstance, is_feasible, bits_from_little_endian_bitstring
from .oracle import exact_summary
from .policies import apply_policy
from .spec import instance_from_spec, spec_from_instance
from .fixtures import hardware_instances


PREFIXES = [1, 4, 16, 64, 256, 1024]
DEADLINES = [5, 30, 300]


def rotate_benefits(spec: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(spec)
    b = list(out["benefits"])
    out["benefits"] = b[1:] + b[:1]
    out["source_version"] = spec.get("source_version", "v1")
    out["current_version"] = "v2_objective_drift"
    return out


def add_first_new_conflict(spec: dict[str, Any]) -> dict[str, Any]:
    instance = instance_from_spec(spec)
    existing = instance.conflict_set()
    out = copy.deepcopy(spec)
    for i, j in combinations(range(instance.n), 2):
        if (i, j) in existing:
            continue
        trial_conflicts = list(instance.conflicts) + [(i, j)]
        trial = DecisionInstance(
            instance_id=instance.instance_id,
            benefits=instance.benefits,
            conflicts=tuple(trial_conflicts),
            interactions=instance.interactions,
            k=instance.k,
        )
        if exact_summary(trial)["satisfiable"]:
            out["conflicts"] = [list(pair) for pair in trial_conflicts]
            out["source_version"] = spec.get("source_version", "v1")
            out["current_version"] = "v2_constraint_drift"
            out["added_conflict"] = [i, j]
            return out
    out["constraint_drift"] = "noop_no_safe_conflict"
    return out


def capacity_k2(spec: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(spec)
    out["k"] = 2
    out["source_version"] = spec.get("source_version", "v1")
    out["current_version"] = "v2_capacity_k2"
    return out


def meaning_change(spec: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(spec)
    meanings = list(out["variable_meanings"])
    meanings[0] = "CHANGED MEANING: now a different organisational object."
    out["variable_meanings"] = meanings
    out["variable_meanings_changed"] = True
    out["current_version"] = "v2_meaning_change"
    return out


def replay_fixture(instance: DecisionInstance, simulated_shots: list[str]) -> dict[str, Any]:
    base_spec = spec_from_instance(instance, request_id=f"replay-{instance.instance_id}")
    greedy = greedy_then_swaps(instance)
    incumbent = None
    if greedy["status"] == "ok":
        incumbent = {"bitstring": greedy["bitstring"], "utility": greedy["utility"]}
    scenarios = {
        "unchanged": base_spec,
        "objective_drift": rotate_benefits(base_spec),
        "constraint_drift": add_first_new_conflict(base_spec),
        "capacity_k2": capacity_k2(base_spec),
        "meaning_change": meaning_change(base_spec),
    }
    linkage_ok = {
        "request_id": base_spec["request_id"],
        "source_hash": base_spec["source_hash"],
        "circuit_hash": "replay-circuit",
        "expected_circuit_hash": "replay-circuit",
        "expected_request_id": base_spec["request_id"],
        "expected_source_hash": base_spec["source_hash"],
        "require_request_id": True,
    }
    linkage_bad = {
        "request_id": "other-request",
        "source_hash": base_spec["source_hash"],
        "circuit_hash": "aaa",
        "expected_circuit_hash": "bbb",
        "expected_request_id": base_spec["request_id"],
        "expected_source_hash": base_spec["source_hash"],
        "require_request_id": True,
    }
    results = {}
    for name, spec in scenarios.items():
        spec["request_id"] = base_spec["request_id"] if name != "meaning_change" else base_spec["request_id"]
        current_instance = instance_from_spec(spec)
        current_incumbent = None
        greedy_now = greedy_then_swaps(current_instance)
        if greedy_now["status"] == "ok":
            current_incumbent = {"bitstring": greedy_now["bitstring"], "utility": greedy_now["utility"]}
        for policy in ("P0", "P1", "P2", "P3"):
            results[f"{name}:{policy}"] = apply_policy(
                policy,
                spec,
                simulated_shots,
                current_incumbent if policy != "P0" else incumbent,
                now_elapsed=10.0,
                linkage=linkage_ok,
            )
        results[f"{name}:lateP2"] = apply_policy("P2", spec, simulated_shots, current_incumbent, 301.0, linkage_ok)
    results["bad_linkage:P2"] = apply_policy("P2", base_spec, simulated_shots, incumbent, 10.0, linkage_bad)
    results["bad_linkage:P3"] = apply_policy("P3", base_spec, simulated_shots, incumbent, 10.0, linkage_bad)
    results["empty:P1"] = apply_policy("P1", base_spec, [], incumbent, 10.0, linkage_ok)
    return {"instance_id": instance.instance_id, "greedy": greedy, "results": results}


def replay_all() -> dict[str, Any]:
    from pathlib import Path

    from .paths import DERIVED_DIR
    from .qaoa import independent_statevector_amplitudes, probability_dict

    params = {}
    qaoa_path = DERIVED_DIR / "qaoa_parameters.json"
    if qaoa_path.is_file():
        import json

        params = json.loads(qaoa_path.read_text(encoding="utf-8"))
    by_id = {fx["instance_id"]: fx for fx in params.get("fixtures", [])}
    payload = []
    prefix_deadline_rows = []
    for instance in hardware_instances():
        fx = by_id.get(instance.instance_id)
        if fx:
            p1 = fx["p1"]["best"]
            amps = independent_statevector_amplitudes(instance, p1["gammas"], p1["betas"])
            pool_label = "frozen_p1"
            p2 = fx["p2"]["best"]
            amps2 = independent_statevector_amplitudes(instance, p2["gammas"], p2["betas"])
        else:
            amps = independent_statevector_amplitudes(instance, [0.3], [0.4])
            amps2 = amps
            pool_label = "unit_test_arbitrary_angles"
        probs = probability_dict(amps, instance.n)
        keys = list(probs)
        weights = [probs[k] for k in keys]
        rng = __import__("random").Random(20260908 + ord(instance.instance_id[-1]))
        shots = rng.choices(keys, weights=weights, k=1024)
        probs2 = probability_dict(amps2, instance.n)
        keys2 = list(probs2)
        weights2 = [probs2[k] for k in keys2]
        shots2 = rng.choices(keys2, weights=weights2, k=1024)
        payload.append({"depth": 1, **replay_fixture(instance, shots)})
        payload.append({"depth": 2, **replay_fixture(instance, shots2)})
        greedy = greedy_then_swaps(instance)
        incumbent = {"bitstring": greedy["bitstring"], "utility": greedy["utility"]} if greedy["status"] == "ok" else None
        spec = spec_from_instance(instance, request_id=f"replay-prefix-{instance.instance_id}")
        linkage = {
            "request_id": spec["request_id"],
            "source_hash": spec["source_hash"],
            "circuit_hash": "frozen-p1p2",
            "expected_circuit_hash": "frozen-p1p2",
            "expected_request_id": spec["request_id"],
            "expected_source_hash": spec["source_hash"],
        }
        for pool_name, pool in (("p1", shots), ("p2", shots2)):
            for prefix in PREFIXES:
                for deadline in DEADLINES:
                    spec["deadline_seconds"] = deadline
                    for policy in ("P0", "P1", "P2", "P3"):
                        for schedule, elapsed in (("on_time", max(0.0, deadline - 1.0)), ("late", deadline + 1.0)):
                            out = apply_policy(
                                policy,
                                spec,
                                pool[:prefix],
                                incumbent,
                                now_elapsed=elapsed,
                                linkage=linkage,
                                trusted_source=spec,
                            )
                            prefix_deadline_rows.append(
                                {
                                    "instance_id": instance.instance_id,
                                    "pool": pool_name,
                                    "prefix": prefix,
                                    "deadline": deadline,
                                    "schedule": schedule,
                                    "now_elapsed": elapsed,
                                    "policy": policy,
                                    "status": out["status"],
                                    "reason": out.get("reason"),
                                    "evidence_type": "sampled_simulation",
                                    "parameter_source": pool_label,
                                    "timing_kind": "injected_schedule",
                                }
                            )
    sim_rows = []
    from .paths import CONFIG_DIR
    from .fixtures import instance_from_spec as fixture_instance
    import json as _json

    sim_file = CONFIG_DIR / "simulation_fixtures.json"
    if sim_file.is_file():
        sim_payload = _json.loads(sim_file.read_text(encoding="utf-8"))
        for spec_row in sim_payload.get("kept") or []:
            inst = fixture_instance(spec_row)
            amps_s = independent_statevector_amplitudes(inst, [0.3], [0.4])
            probs_s = probability_dict(amps_s, inst.n)
            keys_s = list(probs_s)
            weights_s = [probs_s[k] for k in keys_s]
            rng_s = __import__("random").Random(4242 + len(spec_row.get("instance_id", "")))
            shots_s = rng_s.choices(keys_s, weights=weights_s, k=1024)
            replayed = replay_fixture(inst, shots_s)
            sim_rows.append(
                {
                    "instance_id": inst.instance_id,
                    "evidence_type": "sampled_simulation",
                    "greedy": replayed["greedy"],
                    "n_results": len(replayed["results"]),
                }
            )
    return {
        "evidence_type": "policy_replay",
        "fixtures": payload,
        "prefixes": PREFIXES,
        "deadlines": DEADLINES,
        "prefix_deadline_executed": True,
        "prefix_deadline_rows": prefix_deadline_rows,
        "n_prefix_deadline_evaluations": len(prefix_deadline_rows),
        "simulation_fixture_evaluations": sim_rows,
        "n_simulation_fixture_evaluations": len(sim_rows),
    }
