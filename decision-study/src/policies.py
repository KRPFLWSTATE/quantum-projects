"""Acceptance policies P0–P3 applied to identical candidate pools."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .model import bits_from_little_endian_bitstring
from .spec import recompute_current
from .verifier import validate_incumbent, verify_candidate

INCUMBENT_TOL = 1e-9


def ordered_unique(bitstrings: list[str]) -> tuple[list[str], list[str]]:
    seen: set[str] = set()
    unique: list[str] = []
    invalid: list[str] = []
    valid: list[str] = []
    for item in bitstrings:
        if item not in seen:
            seen.add(item)
            unique.append(item)
        try:
            bits_from_little_endian_bitstring(str(item), 6)
            valid.append(item)
        except (ValueError, TypeError):
            invalid.append(str(item))
    return bitstrings, unique, invalid


def p0_modal(bitstrings: list[str]) -> dict[str, Any]:
    valid = []
    for item in bitstrings:
        try:
            bits_from_little_endian_bitstring(str(item), 6)
            valid.append(item)
        except (ValueError, TypeError):
            continue
    if not valid:
        return {"policy": "P0", "status": "abstain", "reason": "EMPTY_CANDIDATES", "selected": None}
    counts = Counter(valid)
    best_count = max(counts.values())
    tied = sorted([key for key, val in counts.items() if val == best_count])
    selected = tied[0]
    return {
        "policy": "P0",
        "status": "accept",
        "reason": "UNGUARDED_MODAL",
        "selected": selected,
        "safeguards": False,
        "note": "Ablation only; omits feasibility, incumbent, deadline, and provenance checks.",
        "tie_break": "lexicographic_little_endian_bitstring_among_valid",
    }


def _select_best_eligible(eligible: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not eligible:
        return None
    # Maximise current utility; ties in stable variable-ID order (task_0 ... task_5 bit tuple).
    eligible_sorted = sorted(
        eligible,
        key=lambda row: (-float(row["utility"]), tuple(row["bits"])),
    )
    return eligible_sorted[0]


def apply_policy(
    policy_id: str,
    spec: dict[str, Any],
    bitstrings: list[str],
    incumbent: dict[str, Any] | None,
    now_elapsed: float,
    linkage: dict[str, Any],
    trusted_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    original, unique, invalid = ordered_unique(list(bitstrings or []))
    if policy_id in {"P2", "P3"}:
        expected_circuit = (linkage or {}).get("expected_circuit_hash")
        if not expected_circuit:
            spec_pre = spec
            checked_incumbent = validate_incumbent(spec_pre, incumbent)
            return {
                "policy": policy_id,
                "status": "fallback_incumbent" if checked_incumbent else "abstain",
                "reason": "MISSING_EXPECTED_CIRCUIT_HASH",
                "selected": None if not checked_incumbent else checked_incumbent["bitstring"],
                "proposed_count": len(original),
                "distinct_count": len(unique),
                "invalid_candidates": invalid,
            }
        supplied_source = (linkage or {}).get("source_hash")
        trusted_hash = (trusted_source or spec.get("source_spec") or {}).get("source_hash")
        if supplied_source and trusted_hash and supplied_source != trusted_hash:
            spec_pre = spec
            checked_incumbent = validate_incumbent(spec_pre, incumbent)
            return {
                "policy": policy_id,
                "status": "fallback_incumbent" if checked_incumbent else "abstain",
                "reason": "SOURCE_HASH_MISMATCH",
                "selected": None if not checked_incumbent else checked_incumbent["bitstring"],
                "proposed_count": len(original),
                "distinct_count": len(unique),
                "invalid_candidates": invalid,
            }
    spec = recompute_current(spec, trusted_source)
    if policy_id == "P0":
        return {
            **p0_modal(original),
            "proposed_count": len(original),
            "distinct_count": len(unique),
            "invalid_candidates": invalid,
        }

    require_version = policy_id == "P2"
    allow_reval = policy_id == "P3"
    source = trusted_source or spec.get("source_spec")
    checked_incumbent = validate_incumbent(spec, incumbent)
    if policy_id in {"P1", "P2", "P3"} and checked_incumbent is None:
        return {
            "policy": policy_id,
            "status": "abstain",
            "reason": "NO_VALID_INCUMBENT",
            "selected": None,
            "proposed_count": len(original),
            "distinct_count": len(unique),
            "invalid_candidates": invalid,
        }

    if policy_id in {"P2", "P3"}:
        missing = [key for key in ("request_id", "source_hash", "circuit_hash") if not (linkage or {}).get(key)]
        if missing:
            return {
                "policy": policy_id,
                "status": "fallback_incumbent",
                "reason": "MISSING_LINKAGE",
                "selected": checked_incumbent["bitstring"],
                "utility": checked_incumbent["utility"],
                "strict_improvement": False,
                "proposed_count": len(original),
                "distinct_count": len(unique),
                "invalid_candidates": invalid,
                "eligible_count": 0,
            }

    checks = []
    for bitstring in unique:
        try:
            bits = bits_from_little_endian_bitstring(bitstring, 6)
        except (ValueError, TypeError):
            checks.append(
                {
                    "bitstring": str(bitstring),
                    "eligible": False,
                    "reasons": ["INVALID_CANDIDATE"],
                    "feasible": False,
                    "utility": None,
                }
            )
            continue
        link = dict(linkage or {})
        if policy_id == "P1":
            link = {"require_request_id": False}
        checks.append(
            verify_candidate(
                spec,
                bits,
                now_elapsed=now_elapsed,
                incumbent_utility=checked_incumbent["utility"],
                linkage=link,
                require_version_match=require_version,
                allow_revalidation=allow_reval,
                trusted_source=source if policy_id in {"P2", "P3"} else None,
            )
        )
    eligible = [row for row in checks if row.get("eligible")]
    best = _select_best_eligible(eligible)
    if best is not None:
        return {
            "policy": policy_id,
            "status": "accept",
            "reason": "ELIGIBLE_CANDIDATE",
            "selected": best["bitstring"],
            "utility": best["utility"],
            "strict_improvement": best["strict_improvement"],
            "proposed_count": len(original),
            "distinct_count": len(unique),
            "eligible_count": len(eligible),
            "invalid_candidates": invalid,
            "checks": checks,
            "tie_break": "neg_utility_then_variable_id_bit_tuple",
        }
    return {
        "policy": policy_id,
        "status": "fallback_incumbent",
        "reason": "NO_ELIGIBLE_CANDIDATE",
        "selected": checked_incumbent["bitstring"],
        "utility": checked_incumbent["utility"],
        "strict_improvement": False,
        "proposed_count": len(original),
        "distinct_count": len(unique),
        "eligible_count": 0,
        "invalid_candidates": invalid,
        "checks": checks,
    }
