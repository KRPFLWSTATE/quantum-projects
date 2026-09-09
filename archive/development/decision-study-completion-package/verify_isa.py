"""Offline verification of this study's saved circuits; never uses an IBM service.

Usage: python verify_isa.py /absolute/path/to/decision-study --output checks.json
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import qiskit
from qiskit import QuantumCircuit, qpy
from qiskit.quantum_info import Statevector


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measured_distribution(circuit):
    """Simulate only active wires, then map probabilities into classical-bit order."""
    active = sorted({circuit.find_bit(q).index for op in circuit.data
                     if op.operation.name != 'barrier' for q in op.qubits})
    if not 0 < len(active) <= 12:
        raise ValueError('Active wire count outside safe offline limit')
    if circuit.num_clbits != 6:
        raise ValueError('Expected six measured classical bits')
    remap = {physical: compact for compact, physical in enumerate(active)}
    unitary = QuantumCircuit(len(active))
    unitary.global_phase = circuit.global_phase
    measurements = {}
    measured_wires = set()
    for op in circuit.data:
        name = op.operation.name
        if name == 'barrier':
            continue
        qs = [circuit.find_bit(q).index for q in op.qubits]
        if name == 'measure':
            c = circuit.find_bit(op.clbits[0]).index
            if c in measurements or qs[0] in measured_wires:
                raise ValueError('Repeated measurement unsupported')
            measurements[c] = remap[qs[0]]
            measured_wires.add(qs[0])
        else:
            if op.clbits or measured_wires.intersection(qs):
                raise ValueError('Conditional or post-measurement gate unsupported')
            if name in {'reset', 'if_else', 'while_loop', 'for_loop', 'switch_case'}:
                raise ValueError('Nonunitary/control-flow operation unsupported')
            unitary.append(op.operation, [remap[q] for q in qs])
    if set(measurements) != set(range(6)):
        raise ValueError('Incomplete classical measurement mapping')
    raw = Statevector.from_instruction(unitary).probabilities()
    result = np.zeros(64)
    for basis, probability in enumerate(raw):
        classical = sum(((basis >> compact) & 1) << c
                        for c, compact in measurements.items())
        result[classical] += probability
    if abs(float(result.sum()) - 1.0) > 1e-10:
        raise ValueError('Probability normalisation failure')
    return result, active, measurements


def permutation_regression():
    logical = QuantumCircuit(6, 6)
    for i in range(6):
        logical.ry(0.12 + 0.22 * i, i)
    logical.cx(0, 3)
    logical.measure(range(6), range(6))
    physical = QuantumCircuit(11, 6)
    placement = [9, 2, 7, 4, 10, 1]
    for op in logical.data:
        physical.append(op.operation,
                        [placement[logical.find_bit(q).index] for q in op.qubits],
                        [logical.find_bit(c).index for c in op.clbits])
    expected, _, _ = measured_distribution(logical)
    actual, _, _ = measured_distribution(physical)
    wrong = QuantumCircuit(11, 6)
    for op in physical.data:
        cs = [physical.find_bit(c).index for c in op.clbits]
        if op.operation.name == 'measure':
            cs = [{0: 5, 5: 0}.get(c, c) for c in cs]
        wrong.append(op.operation, [physical.find_bit(q).index for q in op.qubits], cs)
    incorrect, _, _ = measured_distribution(wrong)
    correct_error = float(np.max(np.abs(expected - actual)))
    incorrect_error = float(np.max(np.abs(expected - incorrect)))
    return {'correct_max_error': correct_error,
            'deliberately_wrong_map_max_error': incorrect_error,
            'pass': correct_error < 1e-10 and incorrect_error > 1e-3}


def verify(root):
    sys.path.insert(0, str(root))
    from src.fixtures import hardware_instances
    from src.qaoa import independent_statevector_amplitudes
    manifest = json.loads((root / 'data/derived/compile/isa_summary.json').read_text())
    params = json.loads((root / 'data/derived/qaoa_parameters.json').read_text())
    fixtures = {f.instance_id: f for f in hardware_instances()}
    parameters = {f['instance_id']: f for f in params['fixtures']}
    rows = []
    expected = {(f'D{i}', p) for i in range(1, 7) for p in (1, 2)}
    seen = set()
    for row in manifest['rows']:
        key = (row['instance_id'], row['p'])
        if key not in expected or key in seen:
            raise ValueError('Duplicate/unexpected fixture/depth')
        seen.add(key)
        distributions = {}
        hashes = {}
        for kind in ('logical', 'isa', 'compact'):
            path = (root / row[kind + '_qpy']).resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError('Circuit path outside study')
            hashes[kind] = sha(path)
            if hashes[kind] != row[kind + '_qpy_sha256']:
                raise ValueError(f'{key}: {kind} hash mismatch')
            with path.open('rb') as handle:
                circuits = qpy.load(handle)
            if len(circuits) != 1:
                raise ValueError('Expected one circuit per QPY file')
            circuit = circuits[0]
            distributions[kind], active, mapping = measured_distribution(circuit)
            if kind == 'isa':
                physical_map = {str(c): active[q] for c, q in mapping.items()}
                active_physical = active
        best = parameters[key[0]]['p' + str(key[1])]['best']
        amps = independent_statevector_amplitudes(fixtures[key[0]], best['gammas'], best['betas'])
        ideal = np.abs(amps) ** 2
        errors = {kind: float(np.max(np.abs(dist - ideal)))
                  for kind, dist in distributions.items()}
        rows.append({'instance_id': key[0], 'p': key[1], 'sha256': hashes,
                     'max_errors_vs_independent_numpy': errors,
                     'active_physical_qubits': active_physical,
                     'classical_bit_to_physical_qubit': physical_map,
                     'pass': max(errors.values()) <= 1e-10})
    if seen != expected:
        raise ValueError('Not all twelve fixture/depth pairs present')
    permutation = permutation_regression()
    return {'evidence_type': 'ideal_simulation', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'qiskit_version': qiskit.__version__, 'tolerance': 1e-10,
            'n_circuits': len(rows), 'all_pass': all(r['pass'] for r in rows) and permutation['pass'],
            'maximum_error': max(v for r in rows for v in r['max_errors_vs_independent_numpy'].values()),
            'permutation_regression': permutation, 'rows': rows,
            'physical_jobs_submitted': 0,
            'scope': 'Saved-circuit numerical equivalence only; no live backend eligibility, noise, duration, runner or research-novelty certification.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('study_root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.study_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}, indent=2))
    return 0 if report['all_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
