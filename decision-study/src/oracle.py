"""Exact enumeration oracle. Must not be imported by candidate selectors."""

from __future__ import annotations

from .model import (
    DecisionInstance,
    bits_from_int,
    energy_from_definition,
    is_feasible,
    little_endian_bitstring,
    utility,
)


def enumerate_all(instance: DecisionInstance) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for value in range(2 ** instance.n):
        bits = bits_from_int(value, instance.n)
        feasible = is_feasible(instance, bits)
        rows.append(
            {
                "int": value,
                "bits": bits,
                "bitstring": little_endian_bitstring(bits, instance.n),
                "feasible": feasible,
                "utility": utility(instance, bits),
                "energy": energy_from_definition(instance, bits),
            }
        )
    return rows


def feasible_rows(instance: DecisionInstance) -> list[dict[str, object]]:
    return [row for row in enumerate_all(instance) if row["feasible"]]


def exact_summary(instance: DecisionInstance) -> dict[str, object]:
    feasible = feasible_rows(instance)
    if not feasible:
        return {
            "instance_id": instance.instance_id,
            "satisfiable": False,
            "feasible_count": 0,
            "optimum_utility": None,
            "optimum_bitstrings": [],
            "optimum_bits": [],
        }
    best = max(float(row["utility"]) for row in feasible)
    optima = [row for row in feasible if abs(float(row["utility"]) - best) < 1e-12]
    return {
        "instance_id": instance.instance_id,
        "satisfiable": True,
        "feasible_count": len(feasible),
        "optimum_utility": best,
        "optimum_bitstrings": [row["bitstring"] for row in optima],
        "optimum_bits": [list(row["bits"]) for row in optima],
    }
