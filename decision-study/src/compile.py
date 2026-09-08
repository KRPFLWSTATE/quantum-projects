"""ISA transpilation, compact remap, QPY, and layout maps. Does not submit Sampler jobs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qiskit import qpy
from qiskit.converters import circuit_to_dag, dag_to_circuit
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

from .fixtures import hardware_instances
from .hashing import sha256_file, write_json_atomic
from .paths import DERIVED_DIR, STUDY_ROOT
from .qaoa import bind_measure, qaoa_circuit

BACKEND_RULE = (
    "lexicographic_name_among_operational_nonsimulator_backends_with_num_qubits_ge_6; "
    "do_not_use_historical_GHZ_fidelity"
)
TRANSPILER_SEED = 20260908
OPT_LEVEL = 1
CEILING_2Q = 250
CEILING_DEPTH = 600
CEILING_ACTIVE = 12


def _active_qubit_indices(circuit) -> list[int]:
    dag = circuit_to_dag(circuit)
    idle = set(dag.idle_wires())
    idle_idx = set()
    for wire in idle:
        if wire._register is circuit.qregs[0] or getattr(wire, "register", None) is not None:
            try:
                idle_idx.add(circuit.find_bit(wire).index)
            except Exception:
                continue
    used = [i for i in range(circuit.num_qubits) if i not in idle_idx]
    if not used:
        used = list(range(min(circuit.num_qubits, 6)))
    return used


def compact_remap(circuit):
    """Drop idle backend qubits. Never statevector-simulate a 156-qubit pad."""
    used = []
    seen: set[int] = set()
    for inst in circuit.data:
        if inst.operation.name == "barrier":
            continue
        for qubit in inst.qubits:
            idx = circuit.find_bit(qubit).index
            if idx not in seen:
                seen.add(idx)
                used.append(idx)
    used = sorted(seen)
    if not used:
        used = list(range(min(6, circuit.num_qubits)))
    if len(used) == circuit.num_qubits:
        circuit.metadata = {**(circuit.metadata or {}), "physical_indices": used, "compacted": False}
        return circuit
    from qiskit import QuantumCircuit as QC

    index_map = {old: i for i, old in enumerate(used)}
    compact = QC(len(used), circuit.num_clbits)
    for inst in circuit.data:
        if inst.operation.name == "barrier":
            continue
        qidx = [circuit.find_bit(q).index for q in inst.qubits]
        if any(i not in index_map for i in qidx):
            continue
        compact.append(
            inst.operation,
            [compact.qubits[index_map[i]] for i in qidx],
            [compact.clbits[circuit.find_bit(c).index] for c in inst.clbits],
        )
    compact.metadata = {"physical_indices": used, "compacted": True, "source_num_qubits": circuit.num_qubits}
    return compact


def two_qubit_count(circuit) -> int:
    ops = circuit.count_ops()
    return int(sum(ops.get(name, 0) for name in ("cx", "cz", "ecr", "rzz", "swap")))


def pin_backend(service):
    backends = [
        b
        for b in service.backends(simulator=False, operational=True)
        if getattr(b, "num_qubits", 0) >= 6
    ]
    names = sorted(b.name for b in backends)
    if not names:
        raise RuntimeError("NO_ELIGIBLE_BACKEND")
    name = names[0]
    return service.backend(name), names, BACKEND_RULE


def compile_all_fixtures(params: dict[str, Any], timeout_note: str | None = None) -> dict[str, Any]:
    from qiskit_ibm_runtime import QiskitRuntimeService

    out_dir = DERIVED_DIR / "compile"
    qpy_dir = out_dir / "qpy"
    out_dir.mkdir(parents=True, exist_ok=True)
    qpy_dir.mkdir(parents=True, exist_ok=True)
    service = QiskitRuntimeService()
    pin_path = DERIVED_DIR / "backend_pin.json"
    ledger_jobs = False
    from .ledger import load_ledger

    try:
        ledger_jobs = bool(load_ledger().get("jobs_submitted") or load_ledger().get("outstanding_job"))
    except Exception:
        ledger_jobs = False
    if pin_path.is_file() and ledger_jobs:
        pin = json.loads(pin_path.read_text(encoding="utf-8"))
        backend = service.backend(pin["backend"])
        eligible = pin.get("eligible") or [backend.name]
        rule = pin.get("rule") or BACKEND_RULE
    else:
        backend, eligible, rule = pin_backend(service)
    pm = generate_preset_pass_manager(
        optimization_level=OPT_LEVEL,
        backend=backend,
        seed_transpiler=TRANSPILER_SEED,
    )
    instances = {inst.instance_id: inst for inst in hardware_instances()}
    rows = []
    structural_ok = True
    compact_ok = True
    for fx in params["fixtures"]:
        inst = instances[fx["instance_id"]]
        for depth, key in ((1, "p1"), (2, "p2")):
            best = fx[key]["best"]
            logical = bind_measure(qaoa_circuit(inst, best["gammas"], best["betas"]))
            isa = pm.run(logical)
            compact = compact_remap(isa)
            n2q = two_qubit_count(isa)
            depth_v = int(isa.depth())
            active = int(compact.num_qubits)
            layout = None
            if getattr(isa, "layout", None) is not None:
                try:
                    layout = {
                        "initial": str(isa.layout.initial_layout),
                        "final_index_layout": list(isa.layout.final_index_layout()),
                    }
                except Exception as exc:
                    layout = {"error": f"{type(exc).__name__}:{exc}"}
            qpy_path = qpy_dir / f"{inst.instance_id}_p{depth}_compact.qpy"
            with qpy_path.open("wb") as handle:
                qpy.dump(compact, handle)
            logical_qpy = qpy_dir / f"{inst.instance_id}_p{depth}_logical.qpy"
            with logical_qpy.open("wb") as handle:
                qpy.dump(logical, handle)
            isa_qpy = qpy_dir / f"{inst.instance_id}_p{depth}_isa.qpy"
            with isa_qpy.open("wb") as handle:
                qpy.dump(isa, handle)
            row = {
                "instance_id": inst.instance_id,
                "p": depth,
                "ops": {k: int(v) for k, v in isa.count_ops().items()},
                "isa_num_qubits_padded": int(isa.num_qubits),
                "compact_num_qubits": active,
                "depth": depth_v,
                "two_qubit": n2q,
                "exceeds_250_2q": n2q > CEILING_2Q,
                "exceeds_depth_600": depth_v > CEILING_DEPTH,
                "exceeds_12_active": active > CEILING_ACTIVE,
                "layout": layout,
                "compact_qpy": str(qpy_path.relative_to(STUDY_ROOT)),
                "logical_qpy": str(logical_qpy.relative_to(STUDY_ROOT)),
                "isa_qpy": str(isa_qpy.relative_to(STUDY_ROOT)),
                "compact_qpy_sha256": sha256_file(qpy_path),
                "logical_qpy_sha256": sha256_file(logical_qpy),
                "isa_qpy_sha256": sha256_file(isa_qpy),
            }
            if row["exceeds_250_2q"] or row["exceeds_depth_600"]:
                structural_ok = False
            if row["exceeds_12_active"]:
                compact_ok = False
            rows.append(row)
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "pinned_backend": backend.name,
        "backend_num_qubits": backend.num_qubits,
        "eligible_operational_names": eligible,
        "selection_rule": rule,
        "transpiler": {"optimization_level": OPT_LEVEL, "seed": TRANSPILER_SEED},
        "timeout_note": timeout_note,
        "rows": rows,
        "structural_ok": structural_ok,
        "compact_ok": compact_ok,
        "new_qpu_jobs_submitted": 0,
    }
    write_json_atomic(out_dir / "isa_summary.json", summary)
    pin = {
        "backend": backend.name,
        "rule": rule,
        "eligible": eligible,
        "frozen_for_campaign": True,
    }
    write_json_atomic(DERIVED_DIR / "backend_pin.json", pin)
    return summary
