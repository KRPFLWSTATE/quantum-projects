"""Transverse-field QAOA p=1/p=2 and independent statevector verification."""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from .model import (
    DecisionInstance,
    bits_from_int,
    energy_from_definition,
    ising_coefficients,
    little_endian_bitstring,
    penalty_scale,
)


def cost_circuit(instance: DecisionInstance, gamma: float) -> QuantumCircuit:
    n = instance.n
    a = penalty_scale(instance)
    _offset, h, j_map = ising_coefficients(instance)
    qc = QuantumCircuit(n)
    scale = 2.0 * gamma / a
    for i in range(n):
        qc.rz(scale * h[i], i)
    for (i, j), coeff in sorted(j_map.items()):
        qc.rzz(scale * coeff, i, j)
    return qc


def mixer_circuit(n: int, beta: float) -> QuantumCircuit:
    qc = QuantumCircuit(n)
    for i in range(n):
        qc.rx(2.0 * beta, i)
    return qc


def qaoa_circuit(instance: DecisionInstance, gammas: Sequence[float], betas: Sequence[float]) -> QuantumCircuit:
    if len(gammas) != len(betas):
        raise ValueError("gamma/beta depth mismatch")
    n = instance.n
    qc = QuantumCircuit(n)
    for i in range(n):
        qc.h(i)
    for gamma, beta in zip(gammas, betas):
        qc.compose(cost_circuit(instance, float(gamma)), inplace=True)
        qc.compose(mixer_circuit(n, float(beta)), inplace=True)
    return qc


def bind_measure(circuit: QuantumCircuit) -> QuantumCircuit:
    measured = circuit.copy()
    measured.measure_all()
    return measured


def independent_statevector_amplitudes(
    instance: DecisionInstance,
    gammas: Sequence[float],
    betas: Sequence[float],
) -> np.ndarray:
    """64-amplitude simulation using numpy, independent of Qiskit gates."""
    n = instance.n
    dim = 2 ** n
    a = penalty_scale(instance)
    energies = np.array(
        [energy_from_definition(instance, bits_from_int(k, n)) / a for k in range(dim)],
        dtype=np.complex128,
    )
    state = np.ones(dim, dtype=np.complex128) / math.sqrt(dim)
    x_masks = [1 << i for i in range(n)]
    for gamma, beta in zip(gammas, betas):
        phase = np.exp(-1j * float(gamma) * energies)
        state = phase * state
        # Mixer product of RX(2 beta) = exp(-i beta X) on each qubit.
        c = math.cos(float(beta))
        s = -1j * math.sin(float(beta))
        for mask in x_masks:
            new = np.empty_like(state)
            for basis in range(dim):
                partner = basis ^ mask
                if basis < partner:
                    a0 = state[basis]
                    a1 = state[partner]
                    new[basis] = c * a0 + s * a1
                    new[partner] = s * a0 + c * a1
            state = new
    return state


def qiskit_statevector(instance: DecisionInstance, gammas: Sequence[float], betas: Sequence[float]) -> np.ndarray:
    sv = Statevector.from_instruction(qaoa_circuit(instance, gammas, betas))
    return np.array(sv.data, dtype=np.complex128)


def probability_dict(amplitudes: np.ndarray, n: int = 6) -> dict[str, float]:
    probs = np.abs(amplitudes) ** 2
    out: dict[str, float] = {}
    for k, p in enumerate(probs):
        out[little_endian_bitstring(bits_from_int(k, n), n)] = float(p)
    return out


def expectation_e_over_a(instance: DecisionInstance, amplitudes: np.ndarray) -> float:
    a = penalty_scale(instance)
    n = instance.n
    probs = np.abs(amplitudes) ** 2
    value = 0.0
    for k, p in enumerate(probs):
        value += p * energy_from_definition(instance, bits_from_int(k, n)) / a
    return float(value)
