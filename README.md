# Quantum Projects

This repository supports the DBA paper **"Hybrid Multi-Agent AI and Quantum Cloud Infrastructure: An Exploratory Organisational Framework for Complex Decision Processing"**. It contains a bounded pilot implementation of a multi-agent-to-QPU workflow, plus manuscript materials under [`quantum-paper-project/`](quantum-paper-project/).

Public code and named-hardware telemetry for the pilot run live primarily under [`dba-qpu-run/`](dba-qpu-run/).

## Reproducibility package

Evidence from the pilot run (telemetry, counts, and environment versions):

- [QPU run telemetry](dba-qpu-run/results/qpu_run_telemetry.json)
- [Simulation counts](dba-qpu-run/results/simulation_counts.json)
- [Hardware counts](dba-qpu-run/results/hardware_counts.json)
- [Environment versions](dba-qpu-run/results/environment_versions.md)

Prefer these artifacts over restating numeric results in secondary documentation.

## How to reproduce the pilot run

IBM Quantum credentials must be configured locally (for example via `QiskitRuntimeService.save_account()`). Do not commit tokens or `.env` files.

```bash
cd dba-qpu-run
python run_circuit.py
python analyze_results.py
```

## Anti-fabrication rule

**Never invent experimental results.** Bitstring counts, fidelity values, job IDs, queue times, backend names, and plots must come only from real Qiskit / IBM Quantum runs. Until data exists, keep placeholders (`null`, empty objects, or explicit pending markers) in `results/` and documentation. See [`.cursor/rules/no-invent-results.mdc`](.cursor/rules/no-invent-results.mdc) and [`quantum-paper-project/README.md`](quantum-paper-project/README.md).

## Layout

```
dba-qpu-run/              # Pilot circuit, analysis, and verified results
quantum-paper-project/
├── circuits/             # Circuit definitions and exports
├── src/                  # Runners, analysis, utilities
├── results/              # JSON from verified runs only
├── logs/                 # Execution and job logs
├── manuscript/           # Paper draft
└── figures/              # Diagrams from real artifacts
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

## Running experiments

- **Pilot package:** see [How to reproduce the pilot run](#how-to-reproduce-the-pilot-run) and [`dba-qpu-run/`](dba-qpu-run/).
- **Paper project scaffolding:** scripts under `quantum-paper-project/src/` should write outputs under `quantum-paper-project/results/` and `quantum-paper-project/logs/` only after real executions complete.

For manuscript-specific notes and result templates, see [`quantum-paper-project/README.md`](quantum-paper-project/README.md) and [`quantum-paper-project/results_summary.md`](quantum-paper-project/results_summary.md).

## Citation

See [`CITATION.cff`](CITATION.cff). Licensed under the [MIT License](LICENSE).
