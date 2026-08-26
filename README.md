# Quantum Projects

This repository documents a **two-run comparative pilot** of a 3-qubit telemetry-probe circuit executed on IBM Quantum Heron r2 hardware (`ibm_kingston` and `ibm_fez`), with named-hardware telemetry and Hellinger-fidelity analysis. Public code and reproducibility artefacts live under [`dba-qpu-run/`](dba-qpu-run/).

These are **comparative pilot observations**, not claims of quantum advantage or a general backend-performance ranking.

## Compact results

| Run | Backend | Job ID | Hellinger fidelity | Queue wait (s) | Client-side wall-clock (s) |
|-----|---------|--------|--------------------|----------------|----------------------------|
| Run 1 | `ibm_kingston` | `da6c1u60ukec7381slv0` | 0.6981714217786029 | 1.191856 | 6.97963285446167 |
| Run 2 | `ibm_fez` | `da715qe0ukec7382m480` | 0.9310600068882383 | 1.046131 | 10.588152885437012 |

Each fidelity compares hardware counts with that run’s corresponding AerSimulator baseline over the full three-qubit outcome space, without renormalizing away leakage.

## Reproducibility archive

- [Immutable run records](dba-qpu-run/results/runs/)
- [IBM Runtime exports](dba-qpu-run/results/ibm-runtime-exports/)
- [Measurement-distribution figures](dba-qpu-run/results/figures/)
- [Comparative summary](dba-qpu-run/results/comparative_summary.json)

Legacy Run 1 convenience exports (do not treat as the multi-run archive):

- [QPU run telemetry](dba-qpu-run/results/qpu_run_telemetry.json)
- [Simulation counts](dba-qpu-run/results/simulation_counts.json)
- [Hardware counts](dba-qpu-run/results/hardware_counts.json)
- [Environment versions](dba-qpu-run/results/environment_versions.md)

## How to reproduce

IBM Quantum credentials must be configured locally (for example via `QiskitRuntimeService.save_account()`). Do not commit tokens or `.env` files.

```bash
cd dba-qpu-run
python run_circuit.py
python analyze_results.py
```

Future executions must **not** overwrite the immutable records under `dba-qpu-run/results/runs/`.

## Anti-fabrication rule

**Never invent experimental results.** Bitstring counts, fidelity values, job IDs, queue times, backend names, and plots must come only from real Qiskit / IBM Quantum runs.

## Layout

```
dba-qpu-run/                 # Pilot circuit, analysis, and verified results
├── results/runs/            # Authoritative immutable two-run archive
├── results/ibm-runtime-exports/
├── results/figures/
└── results/comparative_summary.json
```

## Setup

Python 3.10+ recommended.

```bash
cd "/path/to/Quantum Projects"
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### IBM Quantum credentials

Create a `.env` file at the project root (never commit it; it is listed in `.gitignore`), or save an account with Qiskit Runtime as noted above. Example `.env` keys:

```
IBM_QUANTUM_TOKEN=your_token_here
```

Load credentials in code with `python-dotenv` or your runner’s documented method. Do not paste tokens into the repository or chat logs.

## Citation

See [`CITATION.cff`](CITATION.cff). Licensed under the [MIT License](LICENSE).
