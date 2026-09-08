"""Local noiseless statevector parameter optimisation. Frozen before hardware."""

from __future__ import annotations

import math
import time
from typing import Sequence

import numpy as np
from scipy.optimize import minimize

from .fixtures import hardware_instances
from .model import DecisionInstance, is_feasible, bits_from_int, little_endian_bitstring
from .qaoa import expectation_e_over_a, independent_statevector_amplitudes, probability_dict

GAMMA_BOUNDS = (0.0, 2.0 * math.pi)
BETA_BOUNDS = (0.0, math.pi)
P1_GRID = 17
P1_STARTS = 4
MAX_EVALS_PER_START = 500
P2_RANDOM_STARTS = 7
PROTOCOL_SEED_BASE = 20260908


def _pack(gammas: Sequence[float], betas: Sequence[float]) -> np.ndarray:
    return np.array(list(gammas) + list(betas), dtype=float)


def _unpack(x: np.ndarray, p: int) -> tuple[list[float], list[float]]:
    return list(x[:p]), list(x[p:])


def evaluate_point(instance: DecisionInstance, gammas: Sequence[float], betas: Sequence[float]) -> dict[str, object]:
    amps = independent_statevector_amplitudes(instance, gammas, betas)
    probs = probability_dict(amps, instance.n)
    energy = expectation_e_over_a(instance, amps)
    feasible_p = 0.0
    optimal_p = 0.0
    from .oracle import exact_summary

    summary = exact_summary(instance)
    optima = set(summary.get("optimum_bitstrings") or [])
    for bits_int in range(2 ** instance.n):
        bits = bits_from_int(bits_int, instance.n)
        key = little_endian_bitstring(bits, instance.n)
        p = probs[key]
        if is_feasible(instance, bits):
            feasible_p += p
            if key in optima:
                optimal_p += p
    return {
        "gammas": [float(g) for g in gammas],
        "betas": [float(b) for b in betas],
        "expectation_e_over_a": float(energy),
        "ideal_feasibility_probability": float(feasible_p),
        "ideal_optimal_hit_probability": float(optimal_p),
        "uniform_feasibility_probability": summary["feasible_count"] / (2 ** instance.n)
        if summary["satisfiable"]
        else 0.0,
    }


def _bounds(p: int) -> list[tuple[float, float]]:
    return [GAMMA_BOUNDS] * p + [BETA_BOUNDS] * p


def _refine(instance: DecisionInstance, x0: np.ndarray, p: int) -> dict[str, object]:
    evals = {"count": 0}
    best_seen: dict[str, object] = {"fun": None, "x": None}

    def objective(x: np.ndarray) -> float:
        evals["count"] += 1
        gammas, betas = _unpack(x, p)
        amps = independent_statevector_amplitudes(instance, gammas, betas)
        value = expectation_e_over_a(instance, amps)
        if math.isfinite(value) and (best_seen["fun"] is None or value < best_seen["fun"]):
            best_seen["fun"] = float(value)
            best_seen["x"] = [float(v) for v in x]
        return value

    objective(np.array(x0, dtype=float))
    result = minimize(
        objective,
        x0,
        method="Powell",
        bounds=_bounds(p),
        options={"maxfev": MAX_EVALS_PER_START, "xtol": 1e-6, "ftol": 1e-8},
    )
    chosen = np.array(best_seen["x"] if best_seen["x"] is not None else result.x, dtype=float)
    gammas, betas = _unpack(chosen, p)
    return {
        "x": [float(v) for v in chosen],
        "scipy_x": [float(v) for v in result.x],
        "success": bool(result.success),
        "message": str(result.message),
        "nfev": int(getattr(result, "nfev", evals["count"])),
        "objective_evals": evals["count"],
        "fun": float(best_seen["fun"] if best_seen["fun"] is not None else result.fun),
        "scipy_fun": float(result.fun),
        "gammas": gammas,
        "betas": betas,
        "retained_best_callback_point": True,
    }


def optimize_p1(instance: DecisionInstance) -> dict[str, object]:
    started = time.perf_counter()
    gammas = np.linspace(GAMMA_BOUNDS[0], GAMMA_BOUNDS[1], P1_GRID)
    betas = np.linspace(BETA_BOUNDS[0], BETA_BOUNDS[1], P1_GRID)
    grid: list[tuple[float, list[float], list[float]]] = []
    for g in gammas:
        for b in betas:
            amps = independent_statevector_amplitudes(instance, [float(g)], [float(b)])
            energy = expectation_e_over_a(instance, amps)
            grid.append((float(energy), [float(g)], [float(b)]))
    grid.sort(key=lambda item: (item[0], item[1], item[2]))
    starts = []
    seen: set[tuple[float, float]] = set()
    for energy, gs, bs in grid:
        key = (round(gs[0], 12), round(bs[0], 12))
        if key in seen:
            continue
        seen.add(key)
        starts.append((energy, gs, bs))
        if len(starts) >= P1_STARTS:
            break
    refined = []
    best = None
    for energy, gs, bs in starts:
        packed = _pack(gs, bs)
        start_eval = evaluate_point(instance, gs, bs)
        candidate = {
            "kind": "grid_start",
            **start_eval,
            "nfev": 1,
            "success": True,
            "message": "grid_point",
        }
        ref = _refine(instance, packed, 1)
        refined_eval = evaluate_point(instance, ref["gammas"], ref["betas"])
        refined_candidate = {
            "kind": "powell",
            **refined_eval,
            "nfev": ref["nfev"],
            "objective_evals": ref["objective_evals"],
            "success": ref["success"],
            "message": ref["message"],
        }
        refined.append({"start": candidate, "refined": refined_candidate})
        for item in (candidate, refined_candidate):
            if best is None or item["expectation_e_over_a"] < best["expectation_e_over_a"]:
                best = item
    elapsed = time.perf_counter() - started
    return {
        "p": 1,
        "instance_id": instance.instance_id,
        "starts": refined,
        "best": best,
        "grid_points": P1_GRID * P1_GRID,
        "wall_seconds": elapsed,
        "bounds": {"gamma": list(GAMMA_BOUNDS), "beta": list(BETA_BOUNDS)},
    }


def optimize_p2(instance: DecisionInstance, p1_best: dict[str, object]) -> dict[str, object]:
    started = time.perf_counter()
    seed = PROTOCOL_SEED_BASE + sum(ord(ch) for ch in instance.instance_id)
    rng = np.random.default_rng(seed)
    identity_start = {
        "gammas": list(p1_best["gammas"]) + [0.0],
        "betas": list(p1_best["betas"]) + [0.0],
        "note": "p1_embedded_identity_second_layer",
    }
    random_starts = []
    for _ in range(P2_RANDOM_STARTS):
        random_starts.append(
            {
                "gammas": [float(rng.uniform(*GAMMA_BOUNDS)), float(rng.uniform(*GAMMA_BOUNDS))],
                "betas": [float(rng.uniform(*BETA_BOUNDS)), float(rng.uniform(*BETA_BOUNDS))],
                "note": "seeded_random",
            }
        )
    all_starts = [identity_start] + random_starts
    records = []
    best = None
    for start in all_starts:
        start_eval = evaluate_point(instance, start["gammas"], start["betas"])
        start_candidate = {"kind": "start", "note": start["note"], **start_eval, "nfev": 1, "success": True}
        ref = _refine(instance, _pack(start["gammas"], start["betas"]), 2)
        refined_eval = evaluate_point(instance, ref["gammas"], ref["betas"])
        refined_candidate = {
            "kind": "powell",
            "note": start["note"],
            **refined_eval,
            "nfev": ref["nfev"],
            "objective_evals": ref["objective_evals"],
            "success": ref["success"],
            "message": ref["message"],
        }
        records.append({"start": start_candidate, "refined": refined_candidate})
        for item in (start_candidate, refined_candidate):
            if best is None or item["expectation_e_over_a"] < best["expectation_e_over_a"]:
                best = item
    return {
        "p": 2,
        "instance_id": instance.instance_id,
        "seed": seed,
        "starts": records,
        "best": best,
        "wall_seconds": time.perf_counter() - started,
        "bounds": {"gamma": list(GAMMA_BOUNDS), "beta": list(BETA_BOUNDS)},
    }


def optimize_all_hardware_fixtures() -> dict[str, object]:
    results = []
    for instance in hardware_instances():
        p1 = optimize_p1(instance)
        p2 = optimize_p2(instance, p1["best"])
        results.append({"instance_id": instance.instance_id, "p1": p1, "p2": p2})
    return {"fixtures": results}
