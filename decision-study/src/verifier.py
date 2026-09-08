"""Independent business verifier. Does not trust compiler penalties or advisory flags."""

from __future__ import annotations

from typing import Any, Iterable

from .model import is_feasible, little_endian_bitstring, utility
from .spec import SCHEMA_ID, VARIABLE_IDS, instance_from_spec, objective_payload


def meanings_equal(left: list[str] | None, right: list[str] | None) -> bool:
    return list(left or []) == list(right or [])


def validate_incumbent(spec: dict[str, Any], incumbent: dict[str, Any] | None) -> dict[str, Any] | None:
    if not incumbent or not incumbent.get("bitstring"):
        return None
    from .model import bits_from_little_endian_bitstring

    try:
        bits = bits_from_little_endian_bitstring(str(incumbent["bitstring"]), 6)
    except ValueError:
        return None
    instance = instance_from_spec(spec)
    if not is_feasible(instance, bits):
        return None
    return {
        "bitstring": little_endian_bitstring(bits, instance.n),
        "utility": utility(instance, bits),
        "bits": list(bits),
    }


def provenance_reasons(
    spec: dict[str, Any],
    *,
    trusted_source: dict[str, Any] | None,
    linkage: dict[str, Any],
    require_version_match: bool,
    allow_revalidation: bool,
) -> list[str]:
    reasons: list[str] = []
    required = ("request_id", "source_hash", "circuit_hash")
    if require_version_match or allow_revalidation:
        for key in required:
            if not linkage.get(key):
                reasons.append("MISSING_LINKAGE")
                break
        expected_request = linkage.get("expected_request_id") or (trusted_source or {}).get("request_id")
        if linkage.get("request_id") and expected_request and linkage.get("request_id") != spec.get("request_id"):
            reasons.append("REQUEST_LINKAGE_MISMATCH")
        if expected_request and spec.get("request_id") != expected_request:
            reasons.append("REQUEST_LINKAGE_MISMATCH")
        trusted_source_hash = linkage.get("expected_source_hash") or (trusted_source or {}).get("source_hash")
        if trusted_source_hash and linkage.get("source_hash") != trusted_source_hash:
            reasons.append("SOURCE_HASH_MISMATCH")
        if trusted_source_hash and spec.get("source_hash") != trusted_source_hash:
            reasons.append("SOURCE_HASH_MISMATCH")
        expected_circuit = linkage.get("expected_circuit_hash")
        if not expected_circuit:
            reasons.append("MISSING_EXPECTED_CIRCUIT_HASH")
        elif linkage.get("circuit_hash") != expected_circuit:
            reasons.append("CIRCUIT_HASH_MISMATCH")
        source_meanings = (trusted_source or {}).get("variable_meanings")
        if source_meanings is not None and not meanings_equal(spec.get("variable_meanings"), source_meanings):
            reasons.append("VARIABLE_MEANING_CHANGED")
        source_ids = (trusted_source or {}).get("variable_ids")
        if source_ids is not None and list(spec.get("variable_ids") or []) != list(source_ids):
            reasons.append("VARIABLE_IDENTITY_MISMATCH")
        if spec.get("variable_ids") != VARIABLE_IDS:
            reasons.append("VARIABLE_IDENTITY_MISMATCH")
        version_mismatch = (trusted_source is not None) and (
            objective_payload(spec) != objective_payload(trusted_source)
            or spec.get("current_version") != trusted_source.get("source_version", trusted_source.get("current_version"))
        )
        if trusted_source is not None:
            version_mismatch = objective_payload(spec) != objective_payload(trusted_source)
        if require_version_match and version_mismatch:
            reasons.append("VERSION_MISMATCH")
        if version_mismatch and allow_revalidation:
            if spec.get("schema_id") != SCHEMA_ID:
                reasons.append("SCHEMA_INCOMPATIBLE")
        elif version_mismatch and not allow_revalidation and not require_version_match:
            pass
    return reasons


def verify_candidate(
    spec: dict[str, Any],
    bits: Iterable[int],
    *,
    now_elapsed: float,
    incumbent_utility: float | None,
    linkage: dict[str, Any],
    require_version_match: bool,
    allow_revalidation: bool,
    trusted_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    instance = instance_from_spec(spec)
    bits_t = tuple(int(v) for v in bits)
    bitstring = little_endian_bitstring(bits_t, instance.n)
    reasons: list[str] = []
    if require_version_match or allow_revalidation:
        reasons.extend(
            provenance_reasons(
                spec,
                trusted_source=trusted_source,
                linkage=linkage,
                require_version_match=require_version_match,
                allow_revalidation=allow_revalidation,
            )
        )
    if now_elapsed > float(spec.get("deadline_seconds", 30.0)) + 1e-12:
        reasons.append("DEADLINE_EXCEEDED")
    feasible = is_feasible(instance, bits_t)
    u = utility(instance, bits_t)
    if not feasible:
        reasons.append("INFEASIBLE")
    incumbent_ok = True
    strict_improvement = False
    if incumbent_utility is None:
        incumbent_ok = False
        reasons.append("NO_VALID_INCUMBENT")
    else:
        incumbent_ok = u + 1e-9 >= float(incumbent_utility)
        strict_improvement = u > float(incumbent_utility) + 1e-9
        if not incumbent_ok:
            reasons.append("BELOW_INCUMBENT")
    eligible = not reasons
    return {
        "bitstring": bitstring,
        "bits": list(bits_t),
        "feasible": feasible,
        "utility": u,
        "eligible": eligible,
        "reasons": sorted(set(reasons)),
        "incumbent_ok": incumbent_ok,
        "strict_improvement": strict_improvement,
    }
