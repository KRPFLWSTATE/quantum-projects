"""Analyze QPU run telemetry and print a formatted results summary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TELEMETRY_PATH = SCRIPT_DIR / "qpu_run_telemetry.json"

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


def print_summary_table(telemetry: dict) -> None:
    """Print the run metadata summary table."""
    rows = [
        ("Backend name", format_scalar(telemetry.get("backend_name"))),
        ("Processor family", format_scalar(telemetry.get("processor_family"))),
        ("Qubits on backend", format_scalar(telemetry.get("num_qubits_on_backend"))),
        ("Circuit qubits used", format_scalar(telemetry.get("circuit_qubits"))),
        ("Shots", format_scalar(telemetry.get("shots"))),
        ("Job ID", format_scalar(telemetry.get("job_id"))),
        ("Submission timestamp UTC", format_scalar(telemetry.get("submission_timestamp_utc"))),
        ("Queue wait", format_queue_wait(telemetry.get("queue_wait_seconds"))),
        (
            "Execution wall time (seconds)",
            format_seconds(telemetry.get("execution_wall_time_seconds")),
        ),
        ("Hellinger fidelity", format_fidelity(telemetry.get("hellinger_fidelity"))),
    ]

    label_width = max(len(label) for label, _ in rows)
    print_section_header("QPU RUN SUMMARY")
    print(f"{'Field':<{label_width}}  Value")
    print("-" * SECTION_WIDTH)
    for label, value in rows:
        print(f"{label:<{label_width}}  {value}")


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


def load_telemetry() -> dict:
    """Load telemetry JSON from the script directory."""
    if not TELEMETRY_PATH.is_file():
        raise FileNotFoundError(
            f"Telemetry file not found: {TELEMETRY_PATH}\n"
            "Run run_circuit.py first to generate qpu_run_telemetry.json."
        )

    with TELEMETRY_PATH.open(encoding="utf-8") as telemetry_file:
        data = json.load(telemetry_file)

    if not isinstance(data, dict):
        raise ValueError(
            f"Telemetry file must contain a JSON object, got {type(data).__name__}."
        )

    return data


def main() -> int:
    """Load telemetry and print the formatted analysis report."""
    try:
        telemetry = load_telemetry()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(
            f"ERROR: Failed to parse telemetry JSON at {TELEMETRY_PATH}: {exc}",
            file=sys.stderr,
        )
        return 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    ideal_counts = normalize_counts(telemetry.get("ideal_counts"))
    hardware_counts_raw = telemetry.get("hardware_counts")
    hardware_counts = normalize_counts(hardware_counts_raw)

    print_summary_table(telemetry)

    print_counts_table("IDEAL SIMULATION COUNTS", ideal_counts, unavailable_note=None)

    hardware_note = None
    if hardware_counts_raw is None:
        hardware_note = "(hardware counts unavailable — run may have failed or is incomplete)"
    print_counts_table(
        "HARDWARE EXECUTION COUNTS",
        hardware_counts,
        unavailable_note=hardware_note,
    )

    print_comparison_table(ideal_counts, hardware_counts)

    print_section_header("CONCLUSION")
    print(fidelity_conclusion(telemetry.get("hellinger_fidelity")))

    hardware_error = telemetry.get("hardware_error")
    if hardware_error:
        print(f"Hardware error recorded: {hardware_error}")

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
