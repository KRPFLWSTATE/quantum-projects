# Results layout

This directory holds reproducibility artefacts for the two-run comparative IBM Quantum hardware pilot.

## Contents

- **`runs/`** — authoritative immutable run records for Run 1 (`ibm_kingston`) and Run 2 (`ibm_fez`). Do not overwrite these during future executions.
- **`ibm-runtime-exports/`** — unmodified IBM Runtime job-info and job-result exports for both jobs.
- **`figures/`** — one observed measurement-distribution visualisation per run (copied from the IBM result UI; not regenerated).
- **`comparative_summary.json`** — descriptive cross-run index of backends, job IDs, timings, and fidelities. It is **not** an aggregate benchmark (no mean/median/ranking of fidelity).

## Timing notes

Client-side wall-clock recorded in the immutable run archives includes local completion and result-retrieval overhead; it is **not** hardware-only duration. IBM Runtime server-side timing fields in the raw exports may use a different definition.

## Legacy Run 1 convenience exports

The following files are legacy Run 1 convenience exports retained for backward compatibility. Their empirical values must not be changed:

- `qpu_run_telemetry.json`
- `simulation_counts.json`
- `hardware_counts.json`

Authoritative multi-run evidence lives under `runs/`.
