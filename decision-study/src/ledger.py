"""Atomic campaign ledger with process lock. Never duplicates submissions."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from .hashing import write_json_atomic
from .paths import DATA_DIR, LEDGER_LOCK_PATH, LEDGER_PATH


class LedgerLock:
    def __init__(self, path: Path = LEDGER_LOCK_PATH) -> None:
        self.path = path
        self.fd: int | None = None

    def __enter__(self) -> "LedgerLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(str(self.path), os.O_CREAT | os.O_RDWR)
        if os.name != "nt":
            import fcntl

            fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.fd is not None:
            if os.name != "nt":
                import fcntl

                fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None


def default_ledger() -> dict[str, Any]:
    return {
        "campaign_id": "decision-qaoa-20260908",
        "protocol_id": None,
        "campaign_cap_seconds": 300,
        "per_job_reserve_seconds": 45,
        "preserve_free_seconds": 90,
        "jobs_submitted": 0,
        "jobs_cap": 6,
        "outstanding_job": None,
        "reservations": [],
        "history": [],
        "usage_reconciled_seconds": 0.0,
        "campaign_remaining_seconds": 300.0,
    }


def load_ledger() -> dict[str, Any]:
    if not LEDGER_PATH.is_file():
        return default_ledger()
    return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))


def save_ledger(ledger: dict[str, Any]) -> None:
    write_json_atomic(LEDGER_PATH, ledger)


def can_submit(ledger: dict[str, Any], live_free_remaining: float | None) -> tuple[bool, str]:
    if any(item.get("open") for item in ledger.get("reservations", [])):
        return False, "UNRESOLVED_INTENT"
    if ledger.get("outstanding_job"):
        return False, "OUTSTANDING_JOB"
    if int(ledger.get("jobs_submitted", 0)) >= int(ledger.get("jobs_cap", 6)):
        return False, "JOB_CAP_REACHED"
    reserve = float(ledger.get("per_job_reserve_seconds", 45))
    pending = sum(float(item.get("seconds", 0)) for item in ledger.get("reservations", []) if item.get("open"))
    remaining = float(ledger.get("campaign_remaining_seconds", 0))
    if remaining < reserve:
        return False, "CAMPAIGN_RESERVE_INSUFFICIENT"
    if live_free_remaining is None:
        return False, "BALANCE_UNRESOLVED"
    if live_free_remaining - pending < reserve + float(ledger.get("preserve_free_seconds", 90)):
        return False, "FREE_PLAN_BUFFER_INSUFFICIENT"
    return True, "OK"
