from __future__ import annotations

import json
from typing import Any

from .paths import LEDGER, RAW

JOB_ORDER = [
    "dagjoc8mhr3c73e58uk0",
    "dagjstomhr3c73e5936g",
    "dagjto8mhr3c73e5942g",
    "dagjulj9k43c73adg3j0",
    "dagjvcphvn6c73cqnkt0",
    "dagk0g0mhr3c73e5971g",
]


def load_ledger() -> dict[str, Any]:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def campaign_status(ledger: dict[str, Any] | None = None) -> dict[str, Any]:
    ledger = ledger or load_ledger()
    jobs = int(ledger.get("jobs_submitted") or 0)
    cap = int(ledger.get("jobs_cap") or 6)
    outstanding = ledger.get("outstanding_job")
    history = list(ledger.get("history") or [])
    reservations = list(ledger.get("reservations") or [])
    open_res = [row for row in reservations if row.get("open")]
    finalised = [row for row in history if row.get("finalised") and row.get("physical") and not row.get("mock")]
    complete = (
        jobs == cap == 6
        and outstanding is None
        and len(finalised) == 6
        and not open_res
        and abs(float(ledger.get("usage_reconciled_seconds") or 0) - 30.0) < 1e-9
    )
    submit_blocked = jobs >= cap
    return {
        "campaign_status": "COMPLETE" if complete else "INCOMPLETE",
        "submission_gate": "JOB_CAP_REACHED" if submit_blocked else "OPEN",
        "jobs_submitted": jobs,
        "jobs_cap": cap,
        "outstanding_job": outstanding,
        "open_reservations": len(open_res),
        "finalised_physical_jobs": len(finalised),
        "usage_reconciled_seconds": ledger.get("usage_reconciled_seconds"),
        "campaign_remaining_seconds": ledger.get("campaign_remaining_seconds"),
        "complete": complete,
        "note": "COMPLETE is a public archive label. The hardware submission gate remains blocked at the job cap and is not weakened.",
    }


def list_raw_jobs() -> list[dict[str, Any]]:
    rows = []
    for index, job_id in enumerate(JOB_ORDER, start=1):
        path = RAW / f"{job_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        rows.append({"block": index, "path": str(path), "data": data})
    return rows
