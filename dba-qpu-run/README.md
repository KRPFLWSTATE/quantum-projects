# DBA QPU run package

Bounded pilot implementation of a multi-agent-to-QPU telemetry-probe workflow for the DBA research artefact.

## Authoritative vs convenience telemetry

- **`results/runs/`** is the authoritative immutable archive of all observed hardware executions (Run 1 on `ibm_kingston`, Run 2 on `ibm_fez`).
- **`qpu_run_telemetry.json`** at this package root is a backward-compatible convenience copy of **Run 1** only. Do not treat it as the full multi-run archive, and do not overwrite it with Run 2 data.

Supporting artefacts (IBM Runtime exports, figures, comparative index) live under [`results/`](results/).

## Reproduce locally

IBM Quantum credentials must be configured locally (for example via `QiskitRuntimeService.save_account()`). Do not commit tokens or `.env` files.

```bash
cd dba-qpu-run
python run_circuit.py
python analyze_results.py
```

Future executions must **not** overwrite the immutable records under `results/runs/`.
