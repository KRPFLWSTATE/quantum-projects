from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from .paths import LEGACY_RUNS, REPO_ROOT, STUDY_ROOT
import sys

sys.path.insert(0, str(STUDY_ROOT))
from src.hashing import sha256_file  # type: ignore  # noqa: E402
from src.legacy_audit import exact_ghz_counts, hellinger_fidelity  # type: ignore  # noqa: E402


def collect_ghz_jobs() -> list[dict[str, Any]]:
    rows = []
    for path in sorted(LEGACY_RUNS.glob("run_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        hardware = {str(k): int(v) for k, v in (data.get("hardware_counts") or {}).items()}
        ideal = {str(k): int(v) for k, v in (data.get("ideal_counts") or {}).items()}
        shots = int(data.get("shots") or 0)
        aer = hellinger_fidelity(ideal, hardware)
        exact = hellinger_fidelity(exact_ghz_counts(shots), hardware)
        rows.append(
            {
                "file": path.name,
                "run_label": data.get("run_label"),
                "job_id": data.get("job_id"),
                "backend_name": data.get("backend_name"),
                "shots": shots,
                "queue_wait_seconds": data.get("queue_wait_seconds"),
                "client_side_wall_clock_seconds": data.get("client_side_wall_clock_seconds"),
                "hellinger_vs_sampled_aer_baseline": aer,
                "hellinger_vs_exact_ghz_baseline": exact,
                "hellinger_archived": data.get("hellinger_fidelity"),
                "aer_matches_archive": abs(aer - float(data.get("hellinger_fidelity"))) <= 1e-9,
                "evidence_type": "legacy_ghz_hardware",
                "sha256": sha256_file(path),
                "path": str(path.relative_to(REPO_ROOT)),
            }
        )
    fidelities = [row["hellinger_vs_sampled_aer_baseline"] for row in rows]
    queues = [float(row["queue_wait_seconds"]) for row in rows]
    return {
        "n_jobs": len(rows),
        "rows": rows,
        "fidelity_mean": statistics.fmean(fidelities) if fidelities else None,
        "fidelity_stdev_sample": statistics.stdev(fidelities) if len(fidelities) > 1 else None,
        "fidelity_min": min(fidelities) if fidelities else None,
        "fidelity_max": max(fidelities) if fidelities else None,
        "queue_max_seconds": max(queues) if queues else None,
        "note": "Hellinger versus sampled Aer baseline is the archived comparison. Exact-GHZ (000/111 split) is labelled separately and is not substituted for Aer.",
    }
