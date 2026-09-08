"""Open-plan instance binding and usage extraction. No job submission."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


SECOND_KEYS = ("usage_remaining_seconds", "remaining_seconds")
MINUTE_UNITS = {"m", "min", "minute", "minutes"}
SECOND_UNITS = {"s", "sec", "second", "seconds"}


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _convert_duration(value: Any, unit: Any, *, seconds_implied: bool) -> float | None:
    number = _finite_number(value)
    if number is None:
        return None
    unit_s = str(unit or "").strip().lower()
    if unit_s in SECOND_UNITS or (seconds_implied and not unit_s):
        return number
    if unit_s in MINUTE_UNITS:
        return number * 60.0
    return None


def _extract_remaining_seconds(usage: Any) -> float | None:
    if not isinstance(usage, dict):
        return None
    if "remaining" in usage:
        converted = _convert_duration(
            usage.get("remaining"),
            usage.get("unit"),
            seconds_implied=False,
        )
        if converted is not None:
            return converted
        unit_s = str(usage.get("unit") or "").strip().lower()
        if unit_s and unit_s not in SECOND_UNITS and unit_s not in MINUTE_UNITS:
            return None
        if not unit_s:
            pass
    for key in SECOND_KEYS:
        if key in usage:
            converted = _convert_duration(usage[key], usage.get("unit"), seconds_implied=True)
            if converted is not None:
                return converted
            return None
    if "timeRemaining" in usage:
        converted = _convert_duration(usage.get("timeRemaining"), usage.get("unit"), seconds_implied=True)
        if converted is not None:
            return converted
    for nested_key in ("period", "byInstance", "by_instance"):
        nested = usage.get(nested_key)
        if isinstance(nested, dict):
            found = _extract_remaining_seconds(nested)
            if found is not None:
                return found
    return None


def redact_instance_fields(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = {}
    for key, value in payload.items():
        if any(token in key.lower() for token in ("instance", "crn", "token", "email", "account", "plan_id")):
            redacted[key] = "<redacted>"
        elif isinstance(value, dict):
            redacted[key] = redact_instance_fields(value)
        else:
            redacted[key] = value
    return redacted


def bind_open_plan(*, service_factory=None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "queried": False,
        "plan": None,
        "instance_name": None,
        "remaining_seconds": None,
        "error": None,
        "instance_redacted": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "bound": False,
    }
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
    except Exception as exc:  # pragma: no cover
        report["error"] = f"import_failed:{type(exc).__name__}"
        return report
    factory = service_factory or QiskitRuntimeService
    try:
        unbound = factory()
        report["queried"] = True
        raw_instances = unbound.instances() if hasattr(unbound, "instances") else []
        open_rows = []
        for item in raw_instances or []:
            if not isinstance(item, dict):
                continue
            plan = str(item.get("plan") or item.get("plan_name") or "").lower()
            pricing = str(item.get("pricing_type") or "").lower()
            if plan == "open" or pricing == "free":
                open_rows.append({"plan": plan or "open", "name": item.get("name"), "pricing_type": pricing})
        report["open_instance_count"] = len(open_rows)
        if not open_rows:
            report["error"] = "NO_OPEN_PLAN_INSTANCE"
            return report
        chosen = open_rows[0]
        if not chosen.get("name"):
            report["error"] = "OPEN_INSTANCE_NAME_MISSING"
            return report
        if any(str(row.get("plan") or "") not in {"open", ""} for row in open_rows if row is not chosen):
            pass
        bound = factory(instance=chosen["name"])
        report["instance_name"] = chosen["name"]
        report["plan"] = chosen["plan"] or "open"
        report["bound"] = True
        report["service"] = bound
        if hasattr(bound, "usage"):
            usage = bound.usage()
            report["raw_usage_keys"] = sorted(usage.keys()) if isinstance(usage, dict) else []
            report["usage"] = redact_instance_fields(usage) if isinstance(usage, dict) else {"usage_type": type(usage).__name__}
            report["remaining_seconds"] = _extract_remaining_seconds(usage)
            if report["remaining_seconds"] is None:
                report["error"] = "BALANCE_UNRESOLVED"
        else:
            report["error"] = "service.usage_missing"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}:{exc}"
    return report


def inspect_open_plan_usage() -> dict[str, Any]:
    bound = bind_open_plan()
    out = {k: v for k, v in bound.items() if k != "service"}
    return out


def campaign_allowance(verified_remaining: float | None, user_bound: float = 540.0, cap: float = 300.0, preserve: float = 90.0) -> dict:
    if verified_remaining is None or not math.isfinite(float(verified_remaining)):
        return {
            "verified_remaining_seconds": None,
            "user_planning_bound_seconds": user_bound,
            "campaign_cap_seconds": cap,
            "preserve_seconds": preserve,
            "allowance_seconds": None,
            "formula": "min(300, 540, max(0, verified_remaining-90))",
            "blocked": True,
            "reason": "BALANCE_UNRESOLVED",
        }
    allowance = min(cap, user_bound, max(0.0, float(verified_remaining) - preserve))
    return {
        "verified_remaining_seconds": float(verified_remaining),
        "user_planning_bound_seconds": user_bound,
        "campaign_cap_seconds": cap,
        "preserve_seconds": preserve,
        "allowance_seconds": allowance,
        "per_job_reserve_seconds": 45,
        "jobs_reservable_at_45s": int(allowance // 45),
        "formula": "min(300, 540, max(0, verified_remaining-90))",
        "blocked": allowance < 45,
        "reason": None if allowance >= 45 else "CAMPAIGN_ALLOWANCE_BELOW_PER_JOB_RESERVE",
    }
