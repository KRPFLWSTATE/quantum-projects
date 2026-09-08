"""Classical solvers that never silently invoke the exact oracle."""

from __future__ import annotations

from itertools import combinations
from typing import Iterable

from .model import DecisionInstance, is_feasible, little_endian_bitstring, utility


def _bits_from_set(selected: set[int], n: int) -> tuple[int, ...]:
    return tuple(1 if i in selected else 0 for i in range(n))


def greedy_then_swaps(instance: DecisionInstance) -> dict[str, object]:
    """Deterministic greedy construction plus improving feasible swaps."""
    n = instance.n
    selected: set[int] = set()
    evals = 0
    abstain_reason = None
    while len(selected) < instance.k:
        best_item = None
        best_u = None
        for i in range(n):
            if i in selected:
                continue
            trial = selected | {i}
            bits = _bits_from_set(trial, n)
            evals += 1
            if conflict_only_infeasible(instance, bits) and len(trial) <= instance.k:
                continue
            if not _partial_conflict_ok(instance, trial):
                continue
            u = utility(instance, bits)
            if best_u is None or u > best_u + 1e-12 or (
                abs(u - best_u) <= 1e-12 and (best_item is None or i < best_item)
            ):
                best_u = u
                best_item = i
        if best_item is None:
            abstain_reason = "NO_VALID_INCUMBENT"
            break
        selected.add(best_item)
    bits = _bits_from_set(selected, n)
    if abstain_reason or not is_feasible(instance, bits):
        return {
            "status": "abstain",
            "reason": abstain_reason or "NO_VALID_INCUMBENT",
            "evaluations": evals,
            "bits": None,
            "bitstring": None,
            "utility": None,
            "feasible": False,
        }
    improved = True
    while improved:
        improved = False
        current_u = utility(instance, bits)
        best_move = None
        best_u = current_u
        for out_i in sorted(selected):
            for in_j in range(n):
                if in_j in selected:
                    continue
                trial = (selected - {out_i}) | {in_j}
                trial_bits = _bits_from_set(trial, n)
                evals += 1
                if not is_feasible(instance, trial_bits):
                    continue
                u = utility(instance, trial_bits)
                if u > best_u + 1e-12 or (
                    abs(u - best_u) <= 1e-12 and best_move is not None and (in_j, out_i) < best_move
                ):
                    if u > current_u + 1e-12:
                        best_u = u
                        best_move = (in_j, out_i)
                        improved = True
        if improved and best_move is not None:
            in_j, out_i = best_move
            selected = (selected - {out_i}) | {in_j}
            bits = _bits_from_set(selected, n)
    return {
        "status": "ok",
        "reason": None,
        "evaluations": evals,
        "bits": list(bits),
        "bitstring": little_endian_bitstring(bits, n),
        "utility": utility(instance, bits),
        "feasible": True,
        "stopping_rule": "no_improving_feasible_swap",
    }


def _partial_conflict_ok(instance: DecisionInstance, selected: set[int]) -> bool:
    for i, j in instance.conflict_set():
        if i in selected and j in selected:
            return False
    return True


def conflict_only_infeasible(instance: DecisionInstance, bits: Iterable[int]) -> bool:
    return not _partial_conflict_ok(instance, {i for i, v in enumerate(bits) if v})


def uniform_bitstring_samples(n_samples: int, seed: int, n: int = 6) -> list[str]:
    rng = __import__("random").Random(seed)
    out = []
    for _ in range(n_samples):
        bits = [rng.randint(0, 1) for _ in range(n)]
        out.append(little_endian_bitstring(bits, n))
    return out


def cardinality_k_then_conflict_check(
    instance: DecisionInstance, n_proposals: int, seed: int
) -> dict[str, object]:
    rng = __import__("random").Random(seed)
    subsets = list(combinations(range(instance.n), instance.k))
    rejected = 0
    accepted_bits: list[str] = []
    work = 0
    for _ in range(n_proposals):
        work += 1
        chosen = subsets[rng.randrange(len(subsets))]
        bits = _bits_from_set(set(chosen), instance.n)
        if is_feasible(instance, bits):
            accepted_bits.append(little_endian_bitstring(bits, instance.n))
        else:
            rejected += 1
    return {
        "proposals": n_proposals,
        "rejected_conflicts": rejected,
        "accepted": accepted_bits,
        "work": work,
        "subset_space": len(subsets),
    }
