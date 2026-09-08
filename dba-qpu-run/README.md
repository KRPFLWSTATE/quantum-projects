# DBA QPU run package

Bounded pilot implementation of a multi-agent-to-QPU telemetry-probe workflow for the DBA research artefact.

## Authoritative vs convenience telemetry

- **`results/runs/`** is the authoritative immutable archive of all observed hardware executions (20 runs: `ibm_kingston`, `ibm_fez`, and `ibm_marrakesh`).
- **`qpu_run_telemetry.json`** at this package root is a last-run convenience copy. Do not treat it as the full multi-run archive.

Supporting artefacts (IBM Runtime exports, figures, comparative index) live under [`results/`](results/).

## Reproduce locally

IBM Quantum credentials must be configured locally (for example via `QiskitRuntimeService.save_account()`). Do not commit tokens or `.env` files.

```bash
cd dba-qpu-run
PYTHONUNBUFFERED=1 python -u run_circuit.py
PYTHONUNBUFFERED=1 python -u analyze_results.py
```

Future executions must **not** overwrite existing immutable records under `results/runs/`.
