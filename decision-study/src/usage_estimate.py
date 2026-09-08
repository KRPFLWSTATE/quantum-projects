"""ISA duration estimate from backend target. Conservative; not charged usage."""

from __future__ import annotations

from typing import Any

from qiskit import qpy

from .hashing import write_json_atomic
from .paths import DERIVED_DIR, STUDY_ROOT

IBM_EXECUTION_OVERHEAD_S = 2.0
UNCERTAINTY_MARGIN = 0.35


def _instruction_duration_s(backend, name: str, qubits: tuple[int, ...]) -> float | None:
    target = getattr(backend, "target", None)
    if target is None:
        return None
    try:
        props = target[name][qubits]
        duration = getattr(props, "duration", None)
        if duration is None and isinstance(props, dict):
            duration = props.get("duration")
        if duration is None:
            return None
        return float(duration)
    except Exception:
        try:
            for qargs, props in (target[name] or {}).items():
                duration = getattr(props, "duration", None)
                if duration is not None:
                    return float(duration)
        except Exception:
            return None
    return None


def _circuit_shot_duration_s(backend, circuit) -> tuple[float, dict[str, Any]]:
    total = 0.0
    missing = 0
    counted = 0
    for instruction in circuit.data:
        name = instruction.operation.name
        if name in {"barrier", "delay"}:
            continue
        qubits = tuple(circuit.find_bit(q).index for q in instruction.qubits)
        duration = _instruction_duration_s(backend, name, qubits)
        if duration is None:
            missing += 1
            nq = len(qubits)
            duration = 5e-7 if nq >= 2 else 5e-8
        else:
            counted += 1
        total += duration
    measure_extra = _instruction_duration_s(backend, "measure", (0,)) or 8e-7
    reset_extra = _instruction_duration_s(backend, "reset", (0,)) or 0.0
    total += measure_extra + reset_extra
    return total, {"instructions_with_target_duration": counted, "instructions_fallback": missing}


def estimate_block_usage(backend, compile_rows: list[dict[str, Any]], shots: int = 1024) -> dict[str, Any]:
    report: dict[str, Any] = {
        "method": "isa_target_durations_times_shots_plus_rep_delay_plus_one_execution_overhead",
        "shots_per_pub": shots,
        "n_pubs": 12,
        "uncertain": True,
        "partition_assumption": (
            "One SamplerV2.run of 12 PUBs is treated as one execution/sub-job, "
            "so IBM's approximate 2 s classical overhead is applied once, not per PUB."
        ),
        "ibm_execution_overhead_s": IBM_EXECUTION_OVERHEAD_S,
        "uncertainty_margin": UNCERTAINTY_MARGIN,
        "do_not_confuse_with_queue_or_client_wait": True,
        "error": None,
    }
    try:
        report["backend"] = getattr(backend, "name", None)
        dt = getattr(backend, "dt", None)
        report["dt"] = dt
        rep_delay = getattr(backend, "default_rep_delay", None)
        if rep_delay is None:
            conf = getattr(backend, "configuration", None)
            cfg = conf() if callable(conf) else None
            rep_delay = getattr(cfg, "rep_delay", None) if cfg is not None else None
        if not isinstance(rep_delay, (int, float)):
            rep_delay = 2.5e-4
        report["default_rep_delay"] = float(rep_delay)
        per_pub = []
        for row in compile_rows:
            rel = row.get("isa_qpy")
            path = STUDY_ROOT / rel if rel else None
            if path is None or not path.is_file():
                raise FileNotFoundError(f"ISA_QPY_MISSING:{row.get('instance_id')}_p{row.get('p')}")
            with path.open("rb") as handle:
                circuit = qpy.load(handle)[0]
            per_shot, meta = _circuit_shot_duration_s(backend, circuit)
            per_shot_with_delay = per_shot + float(rep_delay)
            per_pub.append(
                {
                    "instance_id": row["instance_id"],
                    "p": row["p"],
                    "approx_circuit_s": per_shot,
                    "approx_per_shot_s": per_shot_with_delay,
                    "approx_pub_s": per_shot_with_delay * shots,
                    **meta,
                }
            )
        pubs_sum = sum(item["approx_pub_s"] for item in per_pub)
        point = pubs_sum + IBM_EXECUTION_OVERHEAD_S
        with_margin = point * (1.0 + UNCERTAINTY_MARGIN)
        report["per_pub_approx"] = per_pub
        report["sum_pub_seconds_approx"] = pubs_sum
        report["point_estimate_seconds"] = point
        report["block_estimate_seconds"] = with_margin
        report["exceeds_45s_cap"] = with_margin > 45
        report["note"] = (
            "Target durations used when present; missing gates use conservative 500 ns two-qubit / 50 ns one-qubit fallbacks. "
            "Not measured charged usage."
        )
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}:{exc}"
        report["exceeds_45s_cap"] = True
    write_json_atomic(DERIVED_DIR / "usage_estimate.json", report)
    return report
