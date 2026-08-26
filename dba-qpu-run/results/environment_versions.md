# Execution Environment and Package Versions

This file documents the runtime environment for the pilot QPU execution reported in the DBA manuscript "Hybrid Multi-Agent AI and Quantum Cloud Infrastructure".

## Hardware Execution

- Backend: ibm_kingston
- Processor family: Heron r2
- Physical qubits on backend: 156
- Circuit qubits used: 3
- Shots: 1,000
- Job ID: da6c1u60ukec7381slv0
- Submission timestamp (UTC): 2026-08-24T22:08:55.492250Z
- Queue wait (seconds): 1.192
- Execution wall-time (seconds): 6.980
- Hellinger fidelity (vs. ideal simulation): 0.698171

## Local Software Environment

- Python version: 3.14
- qiskit: 2.5.2
- qiskit-ibm-runtime: 0.49.0
- qiskit-aer: 0.17.2
- numpy: 2.5.2
- scipy: 1.18.1

Note: These versions reflect the actual environment in which the pilot run was executed. Minor version drift relative to the minimum requirements in requirements.txt is expected due to pip resolving newer compatible releases.

## Two-run execution record

Run 1 and Run 2 used the documented local software environment above.

- **Run 1:** backend `ibm_kingston`, job `da6c1u60ukec7381slv0`
- **Run 2:** backend `ibm_fez`, job `da715qe0ukec7382m480`

Client-side wall-clock for each run is separately recorded in the immutable archive under `results/runs/` and differs conceptually from IBM Runtime server-side timing in the raw exports.
