"""Regenerate comparative_summary.json from all archived run JSON files."""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_archive import RESULTS_DIR, RUNS_DIR, discover_run_files

SUMMARY_PATH = RESULTS_DIR / "comparative_summary.json"
SCHEMA_VERSION = "1.0"
CIRCUIT_DESCRIPTION = "3-qubit GHZ-style telemetry-probe circuit"
INTERPRETATION_TWO_RUN = (
    "The two observed executions produced different fidelity values. "
    "This descriptive comparison is not a statistically powered estimate of "
    "backend performance, calibration stability, or general quantum-computing "
    "advantage."
)
INTERPRETATION_N_RUN = (
    "The observed executions produced different fidelity values. "
    "This descriptive comparison is not a statistically powered estimate of "
    "backend performance, calibration stability, or general quantum-computing "
    "advantage."
)
RUN_INDEX_FIELDS = (
    "run_label",
    "backend_name",
    "processor_family",
    "job_id",
    "submission_timestamp_utc",
    "queue_wait_seconds",
    "client_side_wall_clock_seconds",
    "hellinger_fidelity",
)
STAT_FIELDS = (
    "hellinger_fidelity",
    "queue_wait_seconds",
    "client_side_wall_clock_seconds",
)


def load_run_json(path: Path) -> dict:
    """Load one archived run object."""
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a JSON object.")
    return data


def summarize_run(record: dict) -> dict:
    """Extract the comparative-summary fields from a full run archive."""
    return {field: record.get(field) for field in RUN_INDEX_FIELDS}


def numeric_values(runs: list[dict], field: str) -> list[float]:
    """Collect numeric values for a field, skipping missing entries."""
    values: list[float] = []
    for run in runs:
        value = run.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return values


def field_statistics(values: list[float]) -> dict:
    """Mean, sample stdev, min, and max; stdev is null when n < 2."""
    if not values:
        return {"mean": None, "stdev": None, "min": None, "max": None}
    return {
        "mean": statistics.mean(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) >= 2 else None,
    }


def build_summary(runs_dir: Path | None = None) -> dict:
    """Build a comparative summary from every archived run file."""
    directory = runs_dir or RUNS_DIR
    discovered = discover_run_files(directory)
    if not discovered:
        raise FileNotFoundError(f"No run_*.json files found in {directory}")

    run_entries: list[dict] = []
    shots_values: list[int] = []
    for _number, path in discovered:
        record = load_run_json(path)
        run_entries.append(summarize_run(record))
        shots = record.get("shots")
        if isinstance(shots, int):
            shots_values.append(shots)

    n_runs = len(run_entries)
    if shots_values and all(value == shots_values[0] for value in shots_values):
        shots_per_run: int | None = shots_values[0]
    elif shots_values:
        shots_per_run = shots_values[0]
    else:
        shots_per_run = None

    aggregate = {
        field: field_statistics(numeric_values(run_entries, field))
        for field in STAT_FIELDS
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "study_design": f"{n_runs}-run comparative pilot",
        "circuit_description": CIRCUIT_DESCRIPTION,
        "shots_per_run": shots_per_run,
        "runs": run_entries,
        "aggregate_statistics": aggregate,
        "interpretation": INTERPRETATION_TWO_RUN if n_runs == 2 else INTERPRETATION_N_RUN,
    }


def write_summary(summary: dict, path: Path | None = None) -> Path:
    """Write the regenerated summary JSON."""
    target = path or SUMMARY_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")
    return target


def compare_run_entries(generated: list[dict], existing: list[dict]) -> list[str]:
    """Return mismatch strings for run-level fields."""
    mismatches: list[str] = []
    if len(generated) != len(existing):
        return [f"run count generated={len(generated)} existing={len(existing)}"]
    for index, (new_run, old_run) in enumerate(zip(generated, existing), start=1):
        for field in RUN_INDEX_FIELDS:
            if new_run.get(field) != old_run.get(field):
                mismatches.append(
                    f"Run {index} {field}: generated={new_run.get(field)!r} "
                    f"existing={old_run.get(field)!r}"
                )
    return mismatches


def main() -> int:
    """Regenerate comparative_summary.json from archived runs."""
    summary = build_summary()
    if SUMMARY_PATH.is_file():
        with SUMMARY_PATH.open(encoding="utf-8") as handle:
            existing = json.load(handle)
        existing_runs = existing.get("runs")
        if isinstance(existing_runs, list):
            mismatches = compare_run_entries(summary["runs"], existing_runs)
            if mismatches:
                print(
                    "ERROR: generated run fields do not match existing summary:",
                    file=sys.stderr,
                )
                for line in mismatches:
                    print(f"  {line}", file=sys.stderr)
                return 1
    target = write_summary(summary)
    print(f"Wrote {target}")
    print(f"study_design: {summary['study_design']}")
    print(f"runs: {len(summary['runs'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
