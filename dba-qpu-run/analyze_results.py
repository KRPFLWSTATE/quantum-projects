"""Analyze comparative QPU run results and print a formatted summary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "results"
COMPARATIVE_SUMMARY_PATH = RESULTS_DIR / "comparative_summary.json"
LEGACY_TELEMETRY_PATH = SCRIPT_DIR / "qpu_run_telemetry.json"

RUN_DETAIL_PATHS = (
    RESULTS_DIR / "runs" / "run_01_ibm_kingston.json",
    RESULTS_DIR / "runs" / "run_02_ibm_fez.json",
)

SECTION_WIDTH = 72


def format_scalar(value: object, *, fallback: str = "N/A") -> str:
    """Return a display string for a telemetry scalar, using fallback when missing."""
    if value is None:
        return fallback
    return str(value)


def format_seconds(value: float | int | None) -> str:
    """Format a duration in seconds, or N/A when unavailable."""
    if value is None:
        return "N/A"
    return f"{float(value):.3f}"


def format_queue_wait(seconds: float | int | None) -> str:
    """Format queue wait as seconds plus a human-readable minutes value."""
    if seconds is None:
        return "N/A"
    wait_seconds = float(seconds)
    wait_minutes = wait_seconds / 60.0
    return f"{wait_seconds:.3f} s ({wait_minutes:.2f} min)"


def format_fidelity(value: float | None) -> str:
    """Format Hellinger fidelity to six decimal places, or N/A when unavailable."""
    if value is None:
        return "N/A"
    return f"{float(value):.6f}"


def fidelity_conclusion(fidelity: float | None) -> str:
    """Return a conclusion line based on Hellinger fidelity thresholds."""
    if fidelity is None:
        return "CONCLUSION: Fidelity unavailable (incomplete telemetry)."
    if fidelity >= 0.90:
        return "HIGH FIDELITY: Hardware closely matches ideal simulation."
    if fidelity >= 0.70:
        return "MODERATE FIDELITY: Detectable noise present but distribution preserved."
    return "LOW FIDELITY: Significant noise or decoherence observed."


def normalize_counts(raw_counts: dict[str, int] | None) -> dict[str, int]:
    """Return a counts mapping, treating null as empty."""
    if not raw_counts:
        return {}
    return dict(raw_counts)


def print_section_header(title: str) -> None:
    """Print a section title with separators."""
    print()
    print("=" * SECTION_WIDTH)
    print(title)
    print("=" * SECTION_WIDTH)


def load_json_object(path: Path, *, label: str) -> dict:
    """Load a JSON object from path, raising clear errors on failure."""
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")

    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"{label} must contain a JSON object, got {type(data).__name__}.")

    return data


def load_comparative_summary() -> dict:
    """Load the primary two-run comparative summary."""
    return load_json_object(COMPARATIVE_SUMMARY_PATH, label="Comparative summary")


def load_run_details() -> list[dict]:
    """Load per-run detail files when present (read-only)."""
    details: list[dict] = []
    for path in RUN_DETAIL_PATHS:
        if not path.is_file():
            continue
        details.append(load_json_object(path, label=f"Run detail ({path.name})"))
    return details


def load_legacy_telemetry() -> dict | None:
    """Optionally load legacy single-run telemetry if present."""
    if not LEGACY_TELEMETRY_PATH.is_file():
        return None
    return load_json_object(LEGACY_TELEMETRY_PATH, label="Legacy telemetry")


def print_study_header(summary: dict) -> None:
    """Print study-level metadata from the comparative summary."""
    print_section_header("COMPARATIVE QPU STUDY")
    rows = [
        ("Schema version", format_scalar(summary.get("schema_version"))),
        ("Study design", format_scalar(summary.get("study_design"))),
        ("Circuit", format_scalar(summary.get("circuit_description"))),
        ("Shots per run", format_scalar(summary.get("shots_per_run"))),
    ]
    label_width = max(len(label) for label, _ in rows)
    for label, value in rows:
        print(f"{label:<{label_width}}  {value}")


def print_run_summary(run: dict) -> None:
    """Print key fields for a single comparative-summary run entry."""
    label = format_scalar(run.get("run_label"), fallback="Run")
    print_section_header(label)
    rows = [
        ("Backend", format_scalar(run.get("backend_name"))),
        ("Processor family", format_scalar(run.get("processor_family"))),
        ("Job ID", format_scalar(run.get("job_id"))),
        ("Submission timestamp UTC", format_scalar(run.get("submission_timestamp_utc"))),
        ("Queue wait", format_queue_wait(run.get("queue_wait_seconds"))),
        (
            "Wall-clock (client_side_wall_clock_seconds)",
            format_seconds(run.get("client_side_wall_clock_seconds")),
        ),
        ("Hellinger fidelity", format_fidelity(run.get("hellinger_fidelity"))),
    ]
    label_width = max(len(field) for field, _ in rows)
    for field, value in rows:
        print(f"{field:<{label_width}}  {value}")
    print()
    print(fidelity_conclusion(run.get("hellinger_fidelity")))


def print_side_by_side_comparison(runs: list[dict]) -> None:
    """Print a compact side-by-side table of both runs."""
    print_section_header("SIDE-BY-SIDE COMPARISON")
    if len(runs) < 2:
        print("(fewer than two runs in comparative summary)")
        return

    run_a, run_b = runs[0], runs[1]
    headers = (
        "Metric",
        format_scalar(run_a.get("run_label"), fallback="Run 1"),
        format_scalar(run_b.get("run_label"), fallback="Run 2"),
    )
    rows = [
        (
            "Backend",
            format_scalar(run_a.get("backend_name")),
            format_scalar(run_b.get("backend_name")),
        ),
        (
            "Job ID",
            format_scalar(run_a.get("job_id")),
            format_scalar(run_b.get("job_id")),
        ),
        (
            "Queue wait",
            format_queue_wait(run_a.get("queue_wait_seconds")),
            format_queue_wait(run_b.get("queue_wait_seconds")),
        ),
        (
            "Wall-clock (s)",
            format_seconds(run_a.get("client_side_wall_clock_seconds")),
            format_seconds(run_b.get("client_side_wall_clock_seconds")),
        ),
        (
            "Hellinger fidelity",
            format_fidelity(run_a.get("hellinger_fidelity")),
            format_fidelity(run_b.get("hellinger_fidelity")),
        ),
    ]

    metric_width = max(len(headers[0]), max(len(row[0]) for row in rows))
    col_a_width = max(len(headers[1]), max(len(row[1]) for row in rows))
    col_b_width = max(len(headers[2]), max(len(row[2]) for row in rows))

    header_line = (
        f"{headers[0]:<{metric_width}} | "
        f"{headers[1]:<{col_a_width}} | "
        f"{headers[2]:<{col_b_width}}"
    )
    separator = (
        f"{'-' * metric_width}-+-"
        f"{'-' * col_a_width}-+-"
        f"{'-' * col_b_width}"
    )
    print(header_line)
    print(separator)
    for metric, value_a, value_b in rows:
        print(
            f"{metric:<{metric_width}} | "
            f"{value_a:<{col_a_width}} | "
            f"{value_b:<{col_b_width}}"
        )


def print_counts_table(title: str, counts: dict[str, int], *, unavailable_note: str | None) -> None:
    """Print a two-column counts table sorted by state name."""
    print_section_header(title)
    if unavailable_note:
        print(unavailable_note)
        return

    if not counts:
        print("(no counts recorded)")
        return

    state_width = max(len("State"), max(len(state) for state in counts))
    print(f"{'State':<{state_width}}  Count")
    print("-" * (state_width + 9))
    for state in sorted(counts):
        print(f"{state:<{state_width}}  {counts[state]}")


def print_comparison_table(ideal_counts: dict[str, int], hardware_counts: dict[str, int]) -> None:
    """Print per-state ideal vs hardware comparison for the union of all states."""
    all_states = sorted(set(ideal_counts) | set(hardware_counts))

    print_section_header("STATE COMPARISON")
    if not all_states:
        print("(no states available for comparison)")
        return

    headers = ("State", "Ideal Count", "Hardware Count", "Difference")
    rows: list[tuple[str, str, str, str]] = []
    for state in all_states:
        ideal = ideal_counts.get(state, 0)
        hardware = hardware_counts.get(state, 0)
        rows.append((state, str(ideal), str(hardware), str(hardware - ideal)))

    state_width = max(len(headers[0]), max(len(row[0]) for row in rows))
    ideal_width = max(len(headers[1]), max(len(row[1]) for row in rows))
    hardware_width = max(len(headers[2]), max(len(row[2]) for row in rows))
    diff_width = max(len(headers[3]), max(len(row[3]) for row in rows))

    header_line = (
        f"{headers[0]:<{state_width}} | "
        f"{headers[1]:>{ideal_width}} | "
        f"{headers[2]:>{hardware_width}} | "
        f"{headers[3]:>{diff_width}}"
    )
    separator = (
        f"{'-' * state_width}-+-"
        f"{'-' * ideal_width}-+-"
        f"{'-' * hardware_width}-+-"
        f"{'-' * diff_width}"
    )

    print(header_line)
    print(separator)
    for state, ideal, hardware, difference in rows:
        print(
            f"{state:<{state_width}} | "
            f"{ideal:>{ideal_width}} | "
            f"{hardware:>{hardware_width}} | "
            f"{difference:>{diff_width}}"
        )


def print_run_detail_counts(detail: dict) -> None:
    """Print ideal/hardware counts and comparison for one detailed run file."""
    label = format_scalar(detail.get("run_label"), fallback="Run")
    backend = format_scalar(detail.get("backend_name"))
    print_section_header(f"{label} COUNTS DETAIL ({backend})")

    ideal_counts = normalize_counts(detail.get("ideal_counts"))
    hardware_counts_raw = detail.get("hardware_counts")
    hardware_counts = normalize_counts(hardware_counts_raw)

    print_counts_table(
        f"{label} — IDEAL SIMULATION COUNTS",
        ideal_counts,
        unavailable_note=None,
    )

    hardware_note = None
    if hardware_counts_raw is None:
        hardware_note = "(hardware counts unavailable — run may have failed or is incomplete)"
    print_counts_table(
        f"{label} — HARDWARE EXECUTION COUNTS",
        hardware_counts,
        unavailable_note=hardware_note,
    )
    print_comparison_table(ideal_counts, hardware_counts)


def print_interpretation(summary: dict) -> None:
    """Print the study interpretation text if present."""
    interpretation = summary.get("interpretation")
    if not interpretation:
        return
    print_section_header("INTERPRETATION")
    print(interpretation)


def main() -> int:
    """Load comparative summary (and optional run details) and print the report."""
    try:
        summary = load_comparative_summary()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(
            "Expected primary input at "
            f"{COMPARATIVE_SUMMARY_PATH.relative_to(SCRIPT_DIR) if COMPARATIVE_SUMMARY_PATH.is_relative_to(SCRIPT_DIR) else COMPARATIVE_SUMMARY_PATH}.",
            file=sys.stderr,
        )
        return 1
    except json.JSONDecodeError as exc:
        print(
            f"ERROR: Failed to parse comparative summary JSON at {COMPARATIVE_SUMMARY_PATH}: {exc}",
            file=sys.stderr,
        )
        return 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    runs = summary.get("runs")
    if not isinstance(runs, list) or not runs:
        print(
            "ERROR: comparative_summary.json has no usable 'runs' list.",
            file=sys.stderr,
        )
        return 1

    print_study_header(summary)

    for run in runs:
        if isinstance(run, dict):
            print_run_summary(run)

    dict_runs = [run for run in runs if isinstance(run, dict)]
    print_side_by_side_comparison(dict_runs)

    try:
        run_details = load_run_details()
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"WARNING: Could not load run detail files: {exc}", file=sys.stderr)
        run_details = []

    for detail in run_details:
        print_run_detail_counts(detail)

    print_interpretation(summary)

    # Optional legacy single-run telemetry (informational only; not the primary source).
    try:
        legacy = load_legacy_telemetry()
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"WARNING: Legacy telemetry present but unreadable: {exc}", file=sys.stderr)
        legacy = None

    if legacy is not None:
        print_section_header("LEGACY TELEMETRY NOTE")
        print(
            f"Found optional {LEGACY_TELEMETRY_PATH.name}; "
            "primary comparison above uses comparative_summary.json."
        )
        print(
            "Legacy job_id: "
            f"{format_scalar(legacy.get('job_id'))}; "
            "legacy Hellinger fidelity: "
            f"{format_fidelity(legacy.get('hellinger_fidelity'))}"
        )

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
