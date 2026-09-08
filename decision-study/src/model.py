"""Independent business utility, QUBO energy, and Ising mapping."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable


N_VARS = 6


def bits_from_int(value: int, n: int = N_VARS) -> tuple[int, ...]:
    return tuple((value >> i) & 1 for i in range(n))


def int_from_bits(bits: Iterable[int]) -> int:
    value = 0
    for i, bit in enumerate(bits):
        if bit:
            value |= 1 << i
    return value


def little_endian_bitstring(bits: Iterable[int], n: int = N_VARS) -> str:
    vals = list(bits)
    if len(vals) != n:
        raise ValueError("bit length mismatch")
    return "".join(str(vals[i]) for i in range(n - 1, -1, -1))


def bits_from_little_endian_bitstring(text: str, n: int = N_VARS) -> tuple[int, ...]:
    if len(text) != n or any(ch not in "01" for ch in text):
        raise ValueError(f"invalid bitstring {text!r}")
    return tuple(int(text[n - 1 - i]) for i in range(n))


@dataclass(frozen=True)
class DecisionInstance:
    instance_id: str
    benefits: tuple[float, ...]
    conflicts: tuple[tuple[int, int], ...]
    interactions: dict[tuple[int, int], float]
    k: int = 3
    n: int = N_VARS

    def pair_key(self, i: int, j: int) -> tuple[int, int]:
        return (i, j) if i < j else (j, i)

    def s(self, i: int, j: int) -> float:
        if i == j:
            return 0.0
        return float(self.interactions.get(self.pair_key(i, j), 0.0))

    def conflict_set(self) -> set[tuple[int, int]]:
        return {self.pair_key(i, j) for i, j in self.conflicts}


def penalty_scale(instance: DecisionInstance) -> float:
    d = sum(abs(b) for b in instance.benefits)
    d += sum(abs(s) for s in instance.interactions.values())
    return 1.0 + d


def utility(instance: DecisionInstance, bits: Iterable[int]) -> float:
    x = tuple(int(v) for v in bits)
    u = sum(instance.benefits[i] * x[i] for i in range(instance.n))
    for i, j in combinations(range(instance.n), 2):
        u += instance.s(i, j) * x[i] * x[j]
    return float(u)


def cardinality(bits: Iterable[int]) -> int:
    return int(sum(int(v) for v in bits))


def conflict_violations(instance: DecisionInstance, bits: Iterable[int]) -> int:
    x = tuple(int(v) for v in bits)
    count = 0
    for i, j in instance.conflict_set():
        count += x[i] * x[j]
    return int(count)


def is_feasible(instance: DecisionInstance, bits: Iterable[int]) -> bool:
    return cardinality(bits) == instance.k and conflict_violations(instance, bits) == 0


def violation_measure(instance: DecisionInstance, bits: Iterable[int]) -> int:
    bits_t = tuple(int(v) for v in bits)
    card = cardinality(bits_t)
    return (card - instance.k) ** 2 + conflict_violations(instance, bits_t)


def energy_from_definition(instance: DecisionInstance, bits: Iterable[int]) -> float:
    a = penalty_scale(instance)
    return float(-utility(instance, bits) + a * violation_measure(instance, bits))


def qubo_coefficients(instance: DecisionInstance) -> tuple[float, tuple[float, ...], dict[tuple[int, int], float]]:
    a = penalty_scale(instance)
    k = instance.k
    constant = a * (k ** 2)
    linear = tuple(-instance.benefits[i] + a * (1 - 2 * k) for i in range(instance.n))
    quadratic: dict[tuple[int, int], float] = {}
    conflicts = instance.conflict_set()
    for i, j in combinations(range(instance.n), 2):
        quadratic[(i, j)] = -instance.s(i, j) + 2 * a + (a if (i, j) in conflicts else 0.0)
    return float(constant), linear, quadratic


def energy_from_qubo(instance: DecisionInstance, bits: Iterable[int]) -> float:
    constant, linear, quadratic = qubo_coefficients(instance)
    x = tuple(int(v) for v in bits)
    value = constant + sum(linear[i] * x[i] for i in range(instance.n))
    for (i, j), coeff in quadratic.items():
        value += coeff * x[i] * x[j]
    return float(value)


def ising_coefficients(instance: DecisionInstance) -> tuple[float, tuple[float, ...], dict[tuple[int, int], float]]:
    constant, linear, quadratic = qubo_coefficients(instance)
    n = instance.n
    h = [0.0] * n
    j_map: dict[tuple[int, int], float] = {}
    for i, j in combinations(range(n), 2):
        j_map[(i, j)] = quadratic[(i, j)] / 4.0
    for i in range(n):
        pair_sum = 0.0
        for j in range(n):
            if i == j:
                continue
            key = (min(i, j), max(i, j))
            pair_sum += quadratic[key]
        h[i] = -linear[i] / 2.0 - pair_sum / 4.0
    offset = constant + sum(linear[i] / 2.0 for i in range(n)) + sum(j_map.values())
    return float(offset), tuple(h), j_map


def energy_from_ising(instance: DecisionInstance, bits: Iterable[int]) -> float:
    offset, h, j_map = ising_coefficients(instance)
    z = tuple(1 - 2 * int(v) for v in bits)
    value = offset + sum(h[i] * z[i] for i in range(instance.n))
    for (i, j), coeff in j_map.items():
        value += coeff * z[i] * z[j]
    return float(value)


def verify_encodings(instance: DecisionInstance, atol: float = 1e-9) -> dict[str, object]:
    mismatches: list[str] = []
    feasible_count = 0
    for value in range(2 ** instance.n):
        bits = bits_from_int(value, instance.n)
        u = utility(instance, bits)
        e_def = energy_from_definition(instance, bits)
        e_qubo = energy_from_qubo(instance, bits)
        e_ising = energy_from_ising(instance, bits)
        if abs(e_def - e_qubo) > atol:
            mismatches.append(f"qubo {value}: {e_def} vs {e_qubo}")
        if abs(e_def - e_ising) > atol:
            mismatches.append(f"ising {value}: {e_def} vs {e_ising}")
        if is_feasible(instance, bits):
            feasible_count += 1
            if abs(e_def + u) > atol:
                mismatches.append(f"feasible energy/utility {value}")
    return {
        "ok": not mismatches,
        "mismatches": mismatches[:20],
        "mismatch_count": len(mismatches),
        "feasible_count": feasible_count,
        "penalty_A": penalty_scale(instance),
    }
