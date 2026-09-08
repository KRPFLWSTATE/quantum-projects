"""Supplementary retrieval of existing GHZ jobs. Does not rewrite historical exports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .hashing import write_json_atomic
from .paths import DERIVED_DIR, LEGACY_RUNS_DIR


def retrieve_legacy_jobs(timeout_s: float = 20.0) -> dict[str, Any]:
    out_dir = DERIVED_DIR / "legacy_supplementary_provenance"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "label": "supplementary_retrieval_not_historical_export",
        "rewrote_historical_exports": False,
        "new_qpu_jobs_submitted": 0,
        "jobs": [],
        "error": None,
    }
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService

        service = QiskitRuntimeService()
    except Exception as exc:
        summary["error"] = f"service:{type(exc).__name__}:{exc}"
        write_json_atomic(out_dir / "summary.json", summary)
        return summary
    for path in sorted(LEGACY_RUNS_DIR.glob("run_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        job_id = data.get("job_id")
        row: dict[str, Any] = {
            "archive_file": path.name,
            "job_id": job_id,
            "retrieved": False,
        }
        try:
            job = service.job(job_id)
            row["retrieved"] = True
            row["status"] = str(job.status())
            row["backend"] = getattr(job, "backend", lambda: None)()
            if callable(row["backend"]):
                row["backend"] = str(row["backend"])
            else:
                b = row["backend"]
                row["backend"] = getattr(b, "name", str(b))
            usage = None
            if hasattr(job, "usage"):
                try:
                    usage = job.usage()
                except Exception as exc:
                    usage = f"usage_error:{type(exc).__name__}"
            metrics = None
            if hasattr(job, "metrics"):
                try:
                    metrics = job.metrics()
                except Exception as exc:
                    metrics = f"metrics_error:{type(exc).__name__}"
            payload = {
                "job_id": job_id,
                "archive_file": path.name,
                "status": row["status"],
                "backend": row["backend"],
                "usage": usage if not isinstance(usage, dict) else {k: usage[k] for k in list(usage)[:40]},
                "metrics_keys": list(metrics.keys()) if isinstance(metrics, dict) else metrics,
                "note": "Supplementary. Does not replace dba-qpu-run exports. Missing fields remain unknown.",
            }
            dest = out_dir / f"{path.stem}_supplementary.json"
            write_json_atomic(dest, payload)
            row["file"] = dest.name
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}:{exc}"
            dest = out_dir / f"{path.stem}_supplementary.json"
            write_json_atomic(dest, {"job_id": job_id, "error": row["error"], "retrieved": False})
        summary["jobs"].append(row)
    write_json_atomic(out_dir / "summary.json", summary)
    return summary
