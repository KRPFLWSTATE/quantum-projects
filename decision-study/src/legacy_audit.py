"""Read-only audit of the 20 historical GHZ hardware jobs."""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .hashing import sha256_file, write_json_atomic
from .paths import HASHES_PATH, LEGACY_EXPORTS_DIR, LEGACY_RESULTS_DIR, LEGACY_RUNS_DIR, REPO_ROOT


def hellinger_fidelity(p_counts: dict[str, int], q_counts: dict[str, int]) -> float:
    keys = set(p_counts) | set(q_counts)
    p_total = sum(p_counts.values()) or 1
    q_total = sum(q_counts.values()) or 1
    acc = 0.0
    for key in keys:
        acc += math.sqrt((p_counts.get(key, 0) / p_total) * (q_counts.get(key, 0) / q_total))
    return acc ** 2


def exact_ghz_counts(shots: int) -> dict[str, int]:
    # Labelled separately from sampled Aer baselines.
    half = shots // 2
    return {"000": half, "111": shots - half}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_legacy_paths() -> list[Path]:
    paths = sorted(LEGACY_RUNS_DIR.glob("run_*.json"))
    paths += sorted(LEGACY_EXPORTS_DIR.glob("*.json"))
    for extra in (
        LEGACY_RESULTS_DIR / "comparative_summary.json",
        LEGACY_RESULTS_DIR / "qpu_run_telemetry.json",
        LEGACY_RESULTS_DIR / "simulation_counts.json",
        LEGACY_RESULTS_DIR / "hardware_counts.json",
        REPO_ROOT / "dba-qpu-run" / "qpu_run_telemetry.json",
    ):
        if extra.is_file():
            paths.append(extra)
    return paths


def snapshot_hashes(*, overwrite: bool = False) -> dict[str, str]:
    mapping = {}
    for path in collect_legacy_paths():
        mapping[str(path.relative_to(REPO_ROOT))] = sha256_file(path)
    if overwrite or not HASHES_PATH.is_file():
        write_json_atomic(HASHES_PATH, mapping)
    return json.loads(HASHES_PATH.read_text(encoding="utf-8"))


def verify_hashes(expected: dict[str, str]) -> dict[str, Any]:
    current = {str(path.relative_to(REPO_ROOT)): sha256_file(path) for path in collect_legacy_paths()}
    changed = {key: {"expected": expected[key], "current": current.get(key)} for key in expected if current.get(key) != expected[key]}
    missing = [key for key in expected if key not in current]
    added = [key for key in current if key not in expected]
    return {"ok": not changed and not missing, "changed": changed, "missing": missing, "added": added}


def extract_export_counts(result_obj: Any) -> dict[str, int] | None:
    if not isinstance(result_obj, dict):
        return None
    if "quasi_dists" in result_obj:
        return None
    for key in ("hardware_counts", "counts"):
        if isinstance(result_obj.get(key), dict):
            return {str(k): int(v) for k, v in result_obj[key].items()}
    # Sampler-style nested
    text = json.dumps(result_obj)
    if "get_counts" in text:
        return None
    return None


def audit_legacy() -> dict[str, Any]:
    hashes = snapshot_hashes()
    runs = []
    issues: list[str] = []
    job_ids = []
    for path in sorted(LEGACY_RUNS_DIR.glob("run_*.json")):
        data = _load(path)
        job_id = data.get("job_id")
        job_ids.append(job_id)
        ideal = {str(k): int(v) for k, v in data.get("ideal_counts", {}).items()}
        hardware = {str(k): int(v) for k, v in data.get("hardware_counts", {}).items()}
        shots = int(data.get("shots", 0))
        hw_sum = sum(hardware.values())
        ideal_sum = sum(ideal.values())
        if hw_sum != shots:
            issues.append(f"{path.name}: hardware count sum {hw_sum} != shots {shots}")
        if any(v < 0 for v in hardware.values()):
            issues.append(f"{path.name}: negative counts")
        recomputed = hellinger_fidelity(ideal, hardware)
        archived = float(data.get("hellinger_fidelity"))
        if abs(recomputed - archived) > 1e-9:
            issues.append(f"{path.name}: fidelity mismatch archived={archived} recomputed={recomputed}")
        exact = hellinger_fidelity(exact_ghz_counts(shots), hardware)
        export_result = LEGACY_EXPORTS_DIR / path.name.replace(".json", "_job_result.json")
        export_info = LEGACY_EXPORTS_DIR / path.name.replace(".json", "_job_info.json")
        export_counts = None
        provenance = "unknown"
        if export_result.is_file():
            export_obj = _load(export_result)
            if isinstance(export_obj, dict) and "hardware_counts" in export_obj:
                export_counts = {str(k): int(v) for k, v in export_obj["hardware_counts"].items()}
                provenance = "custom_count_or_result_repr_export"
            else:
                provenance = "ibm_console_or_encoded_payload"
        if export_counts is not None and export_counts != hardware:
            issues.append(f"{path.name}: export counts differ from archive")
        usage = None
        queue_rederived = None
        if export_info.is_file():
            info = _load(export_info)
            metrics = info.get("metrics") if isinstance(info, dict) else None
            if isinstance(metrics, dict):
                usage = metrics.get("usage") or metrics.get("timestamps")
                created = metrics.get("created_dt") or metrics.get("timestamps", {}).get("created")
        runs.append(
            {
                "file": path.name,
                "job_id": job_id,
                "backend_name": data.get("backend_name"),
                "shots": shots,
                "submission_timestamp_utc": data.get("submission_timestamp_utc"),
                "queue_wait_seconds": data.get("queue_wait_seconds"),
                "client_side_wall_clock_seconds": data.get("client_side_wall_clock_seconds"),
                "hellinger_fidelity_archived": archived,
                "hellinger_fidelity_recomputed": recomputed,
                "hellinger_vs_exact_ghz_baseline": exact,
                "export_provenance": provenance,
                "hardware_count_sum": hw_sum,
                "ideal_count_sum": ideal_sum,
            }
        )
    unique_ids = len(set(job_ids)) == len(job_ids) and None not in job_ids
    if not unique_ids:
        issues.append("non-unique or missing job IDs")
    fidelities = [row["hellinger_fidelity_archived"] for row in runs]
    queues = [row["queue_wait_seconds"] for row in runs]
    waits = [row["client_side_wall_clock_seconds"] for row in runs]
    backends = Counter(row["backend_name"] for row in runs)
    summary = {
        "n_jobs": len(runs),
        "unique_job_ids": unique_ids,
        "backend_counts": dict(backends),
        "fidelity_mean": statistics.fmean(fidelities) if fidelities else None,
        "fidelity_stdev_sample": statistics.stdev(fidelities) if len(fidelities) > 1 else None,
        "fidelity_min": min(fidelities) if fidelities else None,
        "fidelity_max": max(fidelities) if fidelities else None,
        "fidelity_median": statistics.median(fidelities) if fidelities else None,
        "fidelity_iqr": (statistics.quantiles(fidelities, n=4)[0], statistics.quantiles(fidelities, n=4)[2])
        if len(fidelities) >= 4
        else None,
        "queue_median": statistics.median(queues) if queues else None,
        "queue_min": min(queues) if queues else None,
        "queue_max": max(queues) if queues else None,
        "client_wait_max": max(waits) if waits else None,
        "issues": issues,
        "collection_note": "User-triggered at irregular times; not a documented random schedule.",
        "runs": runs,
        "hash_count": len(hashes),
        "exact_ghz_baseline_label": "separate_from_sampled_aer_baseline",
    }
    return summary
