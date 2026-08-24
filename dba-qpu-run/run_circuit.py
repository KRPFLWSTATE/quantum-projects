"""Run a 3-qubit entanglement circuit on IBM Quantum hardware and compare to Aer simulation."""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

from qiskit import QuantumCircuit
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime import SamplerV2 as Sampler

SHOTS = 1000
CIRCUIT_QUBITS = 3
SCRIPT_DIR = Path(__file__).resolve().parent
TELEMETRY_PATH = SCRIPT_DIR / "qpu_run_telemetry.json"


def build_circuit() -> QuantumCircuit:
    """Build a 3-qubit GHZ-style entanglement circuit."""
    circuit = QuantumCircuit(CIRCUIT_QUBITS)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.cx(1, 2)
    circuit.measure_all()
    return circuit


def processor_family_from_backend(backend) -> str:
    """Map backend configuration to a processor family string."""
    processor_type = getattr(backend, "processor_type", None)
    if processor_type is None:
        config = backend.configuration()
        processor_type = getattr(config, "processor_type", None)

    if isinstance(processor_type, dict):
        family = processor_type.get("family")
        revision = processor_type.get("revision")
        if family and revision is not None:
            return f"{family} r{revision}"
        if family:
            return str(family)

    if processor_type is not None:
        return str(processor_type)

    return "N/A"


def run_ideal_simulation(circuit: QuantumCircuit) -> dict[str, int]:
    """Run the circuit locally with AerSimulator."""
    simulator = AerSimulator()
    job = simulator.run(circuit, shots=SHOTS)
    result = job.result()
    return dict(result.get_counts())


def extract_sampler_counts(primitive_result) -> dict[str, int]:
    """Extract measurement counts from a SamplerV2 PrimitiveResult."""
    pub_result = primitive_result[0]
    return dict(pub_result.data.meas.get_counts())


def compute_hellinger_fidelity(
    ideal_counts: dict[str, int],
    hardware_counts: dict[str, int],
    total_shots: int,
) -> float:
    """Compute Hellinger fidelity between two count distributions."""
    all_states = set(ideal_counts) | set(hardware_counts)
    overlap = 0.0

    for state in all_states:
        p_ideal = ideal_counts.get(state, 0) / total_shots
        p_hardware = hardware_counts.get(state, 0) / total_shots
        overlap += math.sqrt(p_ideal * p_hardware)

    return overlap**2


def parse_utc_timestamp(value: datetime | str | None) -> datetime | None:
    """Parse a job.metrics() timestamp into a timezone-aware datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    timestamp = str(value)
    if timestamp.endswith("Z"):
        timestamp = timestamp[:-1] + "+00:00"
    parsed = datetime.fromisoformat(timestamp)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def queue_wait_seconds_from_metrics(metrics: dict) -> float | None:
    """Derive queue wait time from job.metrics() timestamps."""
    timestamps = metrics.get("timestamps", {})
    created = parse_utc_timestamp(timestamps.get("created"))
    running = parse_utc_timestamp(timestamps.get("running"))

    if created is None or running is None:
        return None

    return (running - created).total_seconds()


def main() -> None:
    service = QiskitRuntimeService()
    backend = service.least_busy(simulator=False, operational=True, min_num_qubits=3)

    processor_type = getattr(backend, "processor_type", None)
    if processor_type is None:
        processor_type = getattr(backend.configuration(), "processor_type", "N/A")

    processor_family = processor_family_from_backend(backend)

    print("Selected backend:")
    print(f"  name: {backend.name}")
    print(f"  num_qubits: {backend.num_qubits}")
    print(f"  processor_type: {processor_type if processor_type is not None else 'N/A'}")

    circuit = build_circuit()

    print(f"\nRunning local Aer simulation ({SHOTS} shots)...")
    ideal_counts = run_ideal_simulation(circuit)
    print(f"  ideal_counts: {ideal_counts}")

    pass_manager = generate_preset_pass_manager(optimization_level=1, backend=backend)
    transpiled_circuit = pass_manager.run(circuit)

    job_id = None
    submission_timestamp_utc = None
    queue_wait_seconds = None
    execution_wall_time_seconds = None
    hardware_counts: dict[str, int] | None = None
    hellinger_fidelity = None
    hardware_error: str | None = None

    print(f"\nSubmitting to hardware backend '{backend.name}' ({SHOTS} shots)...")
    try:
        sampler = Sampler(mode=backend)
        submission_timestamp_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        job = sampler.run([transpiled_circuit], shots=SHOTS)
        job_id = job.job_id()
        print(f"  job_id: {job_id}")
        print(f"  submission_timestamp_utc: {submission_timestamp_utc}")

        execution_start = time.time()
        result = job.result()
        execution_wall_time_seconds = time.time() - execution_start

        metrics = job.metrics()
        queue_wait_seconds = queue_wait_seconds_from_metrics(metrics)

        hardware_counts = extract_sampler_counts(result)
        hellinger_fidelity = compute_hellinger_fidelity(
            ideal_counts,
            hardware_counts,
            SHOTS,
        )

        print(f"  queue_wait_seconds: {queue_wait_seconds}")
        print(f"  execution_wall_time_seconds: {execution_wall_time_seconds:.3f}")
        print(f"  hardware_counts: {hardware_counts}")
        print(f"  hellinger_fidelity: {hellinger_fidelity:.6f}")

    except Exception as exc:
        hardware_error = str(exc)
        print(f"\nHardware submission failed: {hardware_error}")

    telemetry = {
        "backend_name": backend.name,
        "processor_family": processor_family,
        "num_qubits_on_backend": backend.num_qubits,
        "circuit_qubits": CIRCUIT_QUBITS,
        "shots": SHOTS,
        "job_id": job_id,
        "submission_timestamp_utc": submission_timestamp_utc,
        "queue_wait_seconds": queue_wait_seconds,
        "execution_wall_time_seconds": execution_wall_time_seconds,
        "ideal_counts": ideal_counts,
        "hardware_counts": hardware_counts,
        "hellinger_fidelity": hellinger_fidelity,
    }

    if hardware_error is not None:
        telemetry["hardware_error"] = hardware_error

    with TELEMETRY_PATH.open("w", encoding="utf-8") as telemetry_file:
        json.dump(telemetry, telemetry_file, indent=2)
        telemetry_file.write("\n")

    print(f"\nTelemetry saved to: {TELEMETRY_PATH}")
    print("\nSummary:")
    print(f"  backend_name: {telemetry['backend_name']}")
    print(f"  processor_family: {telemetry['processor_family']}")
    print(f"  num_qubits_on_backend: {telemetry['num_qubits_on_backend']}")
    print(f"  circuit_qubits: {telemetry['circuit_qubits']}")
    print(f"  shots: {telemetry['shots']}")
    print(f"  job_id: {telemetry['job_id']}")
    print(f"  submission_timestamp_utc: {telemetry['submission_timestamp_utc']}")
    print(f"  queue_wait_seconds: {telemetry['queue_wait_seconds']}")
    print(f"  execution_wall_time_seconds: {telemetry['execution_wall_time_seconds']}")
    print(f"  ideal_counts: {telemetry['ideal_counts']}")
    print(f"  hardware_counts: {telemetry['hardware_counts']}")
    print(f"  hellinger_fidelity: {telemetry['hellinger_fidelity']}")
    if hardware_error is not None:
        print(f"  hardware_error: {hardware_error}")


if __name__ == "__main__":
    main()
