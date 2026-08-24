# Quantum Projects

This repository runs the quantum circuit experiment and captures telemetry for the DBA paper **"Hybrid Multi-Agent AI and Quantum Cloud Infrastructure"**. Experiment code, outputs, and manuscript materials live under [`quantum-paper-project/`](quantum-paper-project/).

## Anti-fabrication rule

**Never invent experimental results.** Bitstring counts, fidelity values, job IDs, queue times, backend names, and plots must come only from real Qiskit / IBM Quantum runs. Until data exists, keep placeholders (`null`, empty objects, or explicit pending markers) in `results/` and documentation. See [`.cursor/rules/no-invent-results.mdc`](.cursor/rules/no-invent-results.mdc) and [`quantum-paper-project/README.md`](quantum-paper-project/README.md).

## Layout

```
quantum-paper-project/
├── circuits/     # Circuit definitions and exports
├── src/          # Runners, analysis, utilities
├── results/      # JSON from verified runs only
├── logs/         # Execution and job logs
├── manuscript/   # Paper draft
└── figures/      # Diagrams from real artifacts
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

Create a `.env` file at the project root (never commit it; it is listed in `.gitignore`). Add your IBM Quantum API token and any variables your scripts expect, for example:

```
IBM_QUANTUM_TOKEN=your_token_here
```

Load credentials in code with `python-dotenv` or your runner’s documented method. Do not paste tokens into the repository or chat logs.

## Running experiments

Implement or run scripts under `quantum-paper-project/src/` and store outputs under `quantum-paper-project/results/` and `quantum-paper-project/logs/` only after real executions complete.

For manuscript-specific notes and result templates, see [`quantum-paper-project/README.md`](quantum-paper-project/README.md) and [`quantum-paper-project/results_summary.md`](quantum-paper-project/results_summary.md).
