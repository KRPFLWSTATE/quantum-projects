"""Helpers for immutable per-run archives of observed QPU executions."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "results"
RUNS_DIR = RESULTS_DIR / "runs"
EXPORTS_DIR = RESULTS_DIR / "ibm-runtime-exports"

RUN_FILENAME_RE = re.compile(r"^run_(\d+)_.+\.json$")

ANALYSIS_NOTE = (
    "Fidelity was computed over the union of all ideal and hardware "
    "measurement states. Leakage outcomes were retained and were not "
    "renormalized away."
)
RESULT_STATUS = "observed_hardware_execution"
SCHEMA_VERSION = "1.0"


def discover_run_files(runs_dir: Path | None = None) -> list[tuple[int, Path]]:
    """Return (run_number, path) pairs for archived run JSON files, sorted."""
    directory = runs_dir or RUNS_DIR
    found: list[tuple[int, Path]] = []
    if not directory.is_dir():
        return found
    for path in directory.iterdir():
        if not path.is_file():
            continue
        match = RUN_FILENAME_RE.match(path.name)
        if match is None:
            continue
        found.append((int(match.group(1)), path))
    found.sort(key=lambda item: (item[0], item[1].name))
    return found


def next_run_number(runs_dir: Path | None = None) -> int:
    """Return the next unused run number (currently 03 after runs 01 and 02)."""
    existing = discover_run_files(runs_dir)
    if not existing:
        return 1
    return existing[-1][0] + 1


def sanitize_backend_name(backend_name: str) -> str:
    """Make a backend name safe for a filename."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", backend_name.strip())
    return cleaned or "unknown_backend"


def allocate_run_slot(
    backend_name: str,
    runs_dir: Path | None = None,
) -> tuple[int, Path]:
    """Choose the next run number and a non-colliding archive path."""
    directory = runs_dir or RUNS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    run_number = next_run_number(directory)
    backend_slug = sanitize_backend_name(backend_name)
    while True:
        path = directory / f"run_{run_number:02d}_{backend_slug}.json"
        if not path.exists():
            return run_number, path
        run_number += 1


def build_run_record(
    *,
    run_number: int,
    backend_name: str,
    processor_family: str,
    num_qubits_on_backend: int,
    circuit_qubits: int,
    shots: int,
    job_id: str,
    submission_timestamp_utc: str,
    queue_wait_seconds: float | None,
    client_side_wall_clock_seconds: float | None,
    ideal_counts: dict[str, int],
    hardware_counts: dict[str, int],
    hellinger_fidelity: float,
) -> dict[str, Any]:
    """Build an archive record matching the Run 1 / Run 2 schema."""
    return {
        "schema_version": SCHEMA_VERSION,
        "run_label": f"Run {run_number}",
        "result_status": RESULT_STATUS,
        "analysis_note": ANALYSIS_NOTE,
        "backend_name": backend_name,
        "processor_family": processor_family,
        "num_qubits_on_backend": num_qubits_on_backend,
        "circuit_qubits": circuit_qubits,
        "shots": shots,
        "job_id": job_id,
        "submission_timestamp_utc": submission_timestamp_utc,
        "queue_wait_seconds": queue_wait_seconds,
        "client_side_wall_clock_seconds": client_side_wall_clock_seconds,
        "ideal_counts": dict(ideal_counts),
        "hardware_counts": dict(hardware_counts),
        "hellinger_fidelity": hellinger_fidelity,
    }


def write_json(path: Path, payload: Any) -> None:
    """Write JSON with trailing newline; never overwrite if caller already checked."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _json_safe(value: Any) -> Any:
    """Convert objects to JSON-serializable forms without inventing fields."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    name = getattr(value, "name", None)
    if isinstance(name, str) and not callable(name):
        return name
    try:
        return str(value)
    except Exception:
        return repr(value)


def collect_job_info(job: Any) -> dict[str, Any]:
    """Collect available job metadata; omit fields that cannot be retrieved."""
    info: dict[str, Any] = {}

    def try_set(key: str, getter) -> None:
        try:
            info[key] = _json_safe(getter())
        except Exception:
            return

    try_set("id", job.job_id)
    try_set("backend", lambda: job.backend().name)
    try_set("status", lambda: str(job.status()))
    try_set("primitive_id", lambda: getattr(job, "primitive_id", None))
    try_set("metrics", job.metrics)
    try_set("metadata", lambda: getattr(job, "metadata", None))
    try_set("usage", job.usage)
    try_set("creation_date", lambda: getattr(job, "creation_date", None))
    return info


def collect_job_result(job: Any, hardware_counts: dict[str, int] | None) -> dict[str, Any]:
    """Collect a serializable result dump plus observed counts."""
    payload: dict[str, Any] = {}
    try:
        payload["id"] = job.job_id()
    except Exception:
        pass
    if hardware_counts is not None:
        payload["hardware_counts"] = dict(hardware_counts)
    try:
        result = job.result()
        payload["result_type"] = type(result).__name__
        try:
            payload["result_repr"] = repr(result)
        except Exception:
            pass
    except Exception as exc:
        payload["result_error"] = str(exc)
    return payload


def write_runtime_exports(
    *,
    run_number: int,
    backend_name: str,
    job: Any,
    hardware_counts: dict[str, int] | None,
    exports_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Write job_info and job_result JSON for a newly archived run."""
    directory = exports_dir or EXPORTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    slug = sanitize_backend_name(backend_name)
    prefix = f"run_{run_number:02d}_{slug}"
    info_path = directory / f"{prefix}_job_info.json"
    result_path = directory / f"{prefix}_job_result.json"
    if info_path.exists() or result_path.exists():
        raise FileExistsError(
            f"Runtime export already exists for {prefix}; refusing to overwrite."
        )
    write_json(info_path, collect_job_info(job))
    write_json(result_path, collect_job_result(job, hardware_counts))
    return info_path, result_path


def archive_successful_run(
    *,
    backend_name: str,
    processor_family: str,
    num_qubits_on_backend: int,
    circuit_qubits: int,
    shots: int,
    job_id: str,
    submission_timestamp_utc: str,
    queue_wait_seconds: float | None,
    client_side_wall_clock_seconds: float | None,
    ideal_counts: dict[str, int],
    hardware_counts: dict[str, int],
    hellinger_fidelity: float,
    job: Any,
) -> Path:
    """Write immutable run JSON and runtime exports; return the run path."""
    run_number, run_path = allocate_run_slot(backend_name)
    record = build_run_record(
        run_number=run_number,
        backend_name=backend_name,
        processor_family=processor_family,
        num_qubits_on_backend=num_qubits_on_backend,
        circuit_qubits=circuit_qubits,
        shots=shots,
        job_id=job_id,
        submission_timestamp_utc=submission_timestamp_utc,
        queue_wait_seconds=queue_wait_seconds,
        client_side_wall_clock_seconds=client_side_wall_clock_seconds,
        ideal_counts=ideal_counts,
        hardware_counts=hardware_counts,
        hellinger_fidelity=hellinger_fidelity,
    )
    write_json(run_path, record)
    write_runtime_exports(
        run_number=run_number,
        backend_name=backend_name,
        job=job,
        hardware_counts=hardware_counts,
    )
    return run_path
