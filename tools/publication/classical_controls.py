"""Post-collection classical candidate pools. Not hardware and not preregistered."""
from __future__ import annotations

import json
import statistics
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

from . import ANALYSIS_VERSION
from .paths import STUDY_ROOT, TOOLS_DIR
from .campaign import list_raw_jobs
from .metrics import instance_catalog

import sys

sys.path.insert(0, str(STUDY_ROOT))
from src.classical import greedy_then_swaps  # type: ignore  # noqa: E402
from src.model import bits_from_int, bits_from_little_endian_bitstring, is_feasible, little_endian_bitstring, utility  # type: ignore  # noqa: E402
from src.policies import apply_policy  # type: ignore  # noqa: E402
from src.spec import spec_from_instance  # type: ignore  # noqa: E402

PLAN_PATH = TOOLS_DIR / "publication" / "plans" / "classical_comparison_plan.json"


def load_plan() -> dict[str, Any]:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def _all_strings() -> list[str]:
    return [little_endian_bitstring(bits_from_int(i), 6) for i in range(64)]


def _k3_strings() -> list[str]:
    out = []
    for combo in combinations(range(6), 3):
        bits = [0] * 6
        for i in combo:
            bits[i] = 1
        out.append(little_endian_bitstring(tuple(bits), 6))
    return out


def _annotate(policy_id: str, result: dict[str, Any], inst, catalog_row, greedy_u) -> dict[str, Any]:
    selected = result.get("selected")
    selected_feasible = False
    selected_u = None
    meaning_ok = True
    if result.get("reason") == "VARIABLE_MEANING_CHANGED":
        meaning_ok = False
    if selected and meaning_ok:
        bits = bits_from_little_endian_bitstring(str(selected), inst.n)
        selected_feasible = is_feasible(inst, bits)
        selected_u = utility(inst, bits)
    opt_u = catalog_row["optimum"]
    gap = None if selected_u is None else abs(opt_u - selected_u)
    improve = selected_feasible and greedy_u is not None and selected_u is not None and selected_u > greedy_u + 1e-9
    return {
        "policy": policy_id,
        "status": result.get("status"),
        "reason": result.get("reason"),
        "selected": selected,
        "selected_feasible": selected_feasible if meaning_ok else None,
        "selected_utility": selected_u if meaning_ok else None,
        "gap_to_exact_optimum": gap if meaning_ok else None,
        "independent_strict_improvement": improve if meaning_ok else None,
        "comparison_undefined": not meaning_ok,
        "is_optimum": bool(selected in catalog_row["opt_set"]) if selected and meaning_ok else False,
    }


def _eval_pool(inst, catalog_row, shots: list[str], prefix: int) -> dict[str, Any]:
    spec = spec_from_instance(inst, request_id=f"post-classical-{inst.instance_id}")
    greedy = catalog_row["greedy"]
    greedy_u = float(greedy["utility"]) if greedy.get("status") == "ok" else None
    incumbent = {"bitstring": greedy["bitstring"], "utility": greedy["utility"]} if greedy.get("status") == "ok" else None
    linkage = {
        "request_id": spec["request_id"],
        "source_hash": spec["source_hash"],
        "circuit_hash": "classical-control-pool",
        "expected_circuit_hash": "classical-control-pool",
        "expected_request_id": spec["request_id"],
        "expected_source_hash": spec["source_hash"],
    }
    subset = shots[:prefix]
    feas = 0
    opt = 0
    for bitstring in subset:
        bits = bits_from_little_endian_bitstring(bitstring, inst.n)
        if is_feasible(inst, bits):
            feas += 1
        if bitstring in catalog_row["opt_set"]:
            opt += 1
    policies = {}
    for policy in ("P0", "P1", "P2", "P3"):
        result = apply_policy(policy, spec, subset, incumbent, 10.0, linkage, trusted_source=spec)
        policies[policy] = _annotate(policy, result, inst, catalog_row, greedy_u)
    return {
        "n": prefix,
        "feasible_shot_fraction": feas / prefix if prefix else None,
        "optimal_hit_fraction": opt / prefix if prefix else None,
        "pool_contains_optimum": opt > 0,
        "policies": policies,
    }


def run_classical_controls() -> dict[str, Any]:
    plan = load_plan()
    catalog = instance_catalog()
    universe = _all_strings()
    k3 = _k3_strings()
    assert len(universe) == 64
    assert len(k3) == 20
    prefixes = list(plan["prefixes"])
    n_rep = int(plan["n_monte_carlo_replications"])
    seed_root = int(plan["seed_root"])
    hardware_by_fx: dict[str, dict[int, list[list[str]]]] = {f"D{i}": {1: [], 2: []} for i in range(1, 7)}
    for item in list_raw_jobs():
        data = item["data"]
        mapping = {int(m["pub_index"]): m for m in data["pub_mapping"]}
        for pub in data["pubs"]:
            meta = mapping[int(pub["pub_index"])]
            hardware_by_fx[meta["instance_id"]][int(meta["p"])].append([str(s) for s in pub["shots"]])

    fixture_rows = []
    policy_rows = []
    for fx_index, fx in enumerate(plan["fixtures"], start=1):
        inst = catalog[fx]["instance"]
        cat = catalog[fx]
        rng = np.random.RandomState(seed_root + 1000 * fx_index)
        uniform_pools = [[universe[i] for i in rng.randint(0, 64, size=1024)] for _ in range(n_rep)]
        k3_pools = [[k3[i] for i in rng.randint(0, 20, size=1024)] for _ in range(n_rep)]
        p_opt = cat["uniform_opt"]
        analytical = {
            "p_opt_uniform": p_opt,
            "p_at_least_one_opt_m": {str(m): 1.0 - (1.0 - p_opt) ** m for m in prefixes},
            "p_opt_k3": len([s for s in k3 if s in cat["opt_set"]]) / 20.0,
        }
        for prefix in prefixes:
            uniform_eval = [_eval_pool(inst, cat, pool, prefix) for pool in uniform_pools]
            k3_eval = [_eval_pool(inst, cat, pool, prefix) for pool in k3_pools]
            enum_eval = _eval_pool(inst, cat, universe, 64)
            greedy_eval = _eval_pool(inst, cat, [cat["greedy"]["bitstring"]], 1) if cat["greedy"].get("bitstring") else None

            def _stats(vals: list[float]) -> dict[str, float]:
                return {
                    "mean": statistics.fmean(vals),
                    "stdev": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
                    "n": len(vals),
                }

            for depth in (1, 2):
                hw_pools = hardware_by_fx[fx][depth]
                hw_eval = [_eval_pool(inst, cat, pool, prefix) for pool in hw_pools]
                fixture_rows.append(
                    {
                        "fixture": fx,
                        "p_panel": depth,
                        "classical_pools_shared_across_p": True,
                        "prefix": prefix,
                        "analytical_p_at_least_one_opt_uniform": analytical["p_at_least_one_opt_m"][str(prefix)],
                        "p_opt_uniform_single_draw": analytical["p_opt_uniform"],
                        "uniform_opt_hit": _stats([row["optimal_hit_fraction"] for row in uniform_eval]),
                        "uniform_contains_opt": _stats([float(row["pool_contains_optimum"]) for row in uniform_eval]),
                        "k3_opt_hit": _stats([row["optimal_hit_fraction"] for row in k3_eval]),
                        "hardware_opt_hit": _stats([row["optimal_hit_fraction"] for row in hw_eval]),
                        "hardware_n_blocks": len(hw_eval),
                        "exact_enumeration_opt_hit": enum_eval["optimal_hit_fraction"],
                        "greedy_selected_utility": cat["greedy"].get("utility"),
                        "exact_optimum": cat["optimum"],
                        "sample_origin": "post_collection_classical_controls",
                        "analysis_type": "post_collection_classical_controls",
                    }
                )
                for policy in ("P0", "P1", "P2", "P3"):
                    def _pstats(evals, field, policy_id=policy):
                        vals = [row["policies"][policy_id][field] for row in evals if row["policies"][policy_id][field] is not None]
                        if not vals:
                            return None
                        if isinstance(vals[0], bool):
                            return {"mean": statistics.fmean(float(v) for v in vals), "n": len(vals)}
                        return {"mean": statistics.fmean(vals), "n": len(vals)}

                    policy_rows.append(
                        {
                            "fixture": fx,
                            "p_panel": depth,
                            "prefix": prefix,
                            "policy": policy,
                            "hardware_improve_mean": _pstats(hw_eval, "independent_strict_improvement"),
                            "uniform_improve_mean": _pstats(uniform_eval, "independent_strict_improvement"),
                            "k3_improve_mean": _pstats(k3_eval, "independent_strict_improvement"),
                            "enumeration_improve": enum_eval["policies"][policy]["independent_strict_improvement"],
                            "greedy_improve": greedy_eval["policies"][policy]["independent_strict_improvement"] if greedy_eval else None,
                            "hardware_selected_feasible_mean": _pstats(hw_eval, "selected_feasible"),
                            "uniform_selected_feasible_mean": _pstats(uniform_eval, "selected_feasible"),
                            "classical_pools_shared_across_p": True,
                        }
                    )
    return {
        "plan": plan,
        "k3_universe_size": len(k3),
        "n_64": 64,
        "fixture_prefix_rows": fixture_rows,
        "policy_prefix_rows": policy_rows,
        "note": "Monte Carlo estimates are labelled separately from analytical 1-(1-p_opt)^m. Hardware six blocks remain clustered observations, not organisations.",
    }
