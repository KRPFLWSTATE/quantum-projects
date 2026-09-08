"""Frozen hardware fixtures and additional simulation-only generators."""

from __future__ import annotations

import random
from typing import Any

from .model import DecisionInstance, N_VARS

HARDWARE_FIXTURE_SPECS: list[dict[str, Any]] = [
    {
        "instance_id": "D1",
        "benefits": [9, 8, 7, 6, 5, 4],
        "conflicts": [(0, 1), (2, 3)],
        "interaction_triples": [(0, 4, 3), (1, 5, 2), (2, 4, -2)],
    },
    {
        "instance_id": "D2",
        "benefits": [8, 6, 9, 5, 7, 4],
        "conflicts": [(0, 2), (1, 4), (3, 5)],
        "interaction_triples": [(0, 3, 3), (2, 4, 2), (1, 5, -1)],
    },
    {
        "instance_id": "D3",
        "benefits": [7, 9, 5, 8, 6, 4],
        "conflicts": [(0, 1), (1, 2), (3, 4)],
        "interaction_triples": [(0, 5, 2), (2, 3, 3), (4, 5, -2)],
    },
    {
        "instance_id": "D4",
        "benefits": [6, 8, 7, 9, 4, 5],
        "conflicts": [(0, 3), (1, 2), (2, 5), (3, 4)],
        "interaction_triples": [(0, 4, 3), (1, 5, 2), (2, 4, -1)],
    },
    {
        "instance_id": "D5",
        "benefits": [9, 5, 8, 4, 7, 6],
        "conflicts": [(0, 2), (0, 4), (1, 3), (2, 5)],
        "interaction_triples": [(0, 5, 2), (1, 4, 3), (3, 5, -2)],
    },
    {
        "instance_id": "D6",
        "benefits": [5, 9, 6, 8, 4, 7],
        "conflicts": [(0, 1), (1, 3), (2, 4), (3, 5)],
        "interaction_triples": [(0, 3, 3), (1, 4, 2), (2, 5, -1)],
    },
]

EXPECTED_FEASIBLE_COUNTS = [12, 8, 9, 6, 6, 6]
EXPECTED_OPTIMA = [23, 23, 23, 24, 23, 22]
SIM_GENERATOR_SEED = 20260908
SIM_GENERATOR_PROTOCOL = {
    "seed": SIM_GENERATOR_SEED,
    "n_requested": 24,
    "benefit_range": [2, 9],
    "interaction_range": [-3, 3],
    "conflict_count_range": [2, 4],
    "k": 3,
    "reject_if_unsatisfiable": True,
}


def instance_from_spec(spec: dict[str, Any], *, k: int = 3) -> DecisionInstance:
    interactions: dict[tuple[int, int], float] = {}
    for i, j, s in spec["interaction_triples"]:
        key = (i, j) if i < j else (j, i)
        interactions[key] = float(s)
    conflicts = tuple((min(i, j), max(i, j)) for i, j in spec["conflicts"])
    return DecisionInstance(
        instance_id=str(spec["instance_id"]),
        benefits=tuple(float(v) for v in spec["benefits"]),
        conflicts=conflicts,
        interactions=interactions,
        k=int(k),
    )


def hardware_instances() -> list[DecisionInstance]:
    return [instance_from_spec(spec) for spec in HARDWARE_FIXTURE_SPECS]


def generate_simulation_fixtures(seed: int = SIM_GENERATOR_SEED, n_keep: int = 24) -> dict[str, Any]:
    rng = random.Random(seed)
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    attempt = 0
    from .oracle import exact_summary

    while len(kept) < n_keep and attempt < 5000:
        attempt += 1
        benefits = [rng.randint(2, 9) for _ in range(N_VARS)]
        n_conflicts = rng.randint(2, 4)
        pairs = [(i, j) for i in range(N_VARS) for j in range(i + 1, N_VARS)]
        rng.shuffle(pairs)
        conflicts = pairs[:n_conflicts]
        triples: list[tuple[int, int, int]] = []
        for i, j in pairs:
            if rng.random() < 0.35:
                s = rng.randint(-3, 3)
                if s != 0:
                    triples.append((i, j, s))
        spec = {
            "instance_id": f"S{len(kept) + 1:02d}",
            "benefits": benefits,
            "conflicts": conflicts,
            "interaction_triples": triples,
            "generator_attempt": attempt,
        }
        instance = instance_from_spec(spec)
        summary = exact_summary(instance)
        if not summary["satisfiable"]:
            rejected.append({"reason": "no_feasible_selection", "spec": spec})
            continue
        spec["computed_feasible_count"] = summary["feasible_count"]
        spec["computed_optimum_utility"] = summary["optimum_utility"]
        kept.append(spec)
    return {
        "protocol": SIM_GENERATOR_PROTOCOL,
        "attempts": attempt,
        "kept": kept,
        "rejected": rejected,
    }
