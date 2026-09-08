# Results layout

This directory holds reproducibility artefacts for the 20-run comparative IBM Quantum hardware pilot.

## Contents

- **`runs/`** — authoritative immutable run records for Runs 1–20. Do not overwrite these during future executions.
- **`ibm-runtime-exports/`** — IBM Runtime job-info and job-result exports for each archived job. Runs 1–2 are console downloads; later runs are dumps from the live job object after each execution.
- **`figures/`** — observed measurement-distribution visualisations for **Run 1 and Run 2 only** (copied from the IBM result UI; not regenerated). No figure files exist for Runs 3–20.
- **`comparative_summary.json`** — descriptive cross-run index of backends, job IDs, timings, and fidelities, plus sample mean/stdev/min/max. Those aggregates describe this 20-run set only; they are **not** a statistically powered backend ranking.

## Timing notes

Client-side wall-clock recorded in the immutable run archives includes local completion and result-retrieval overhead; it is **not** hardware-only duration. IBM Runtime server-side timing fields in the raw exports may use a different definition.

## Legacy Run 1 convenience exports

The following files are legacy Run 1 convenience exports retained for backward compatibility. Their empirical values must not be changed:

- `qpu_run_telemetry.json`
- `simulation_counts.json`
- `hardware_counts.json`

Authoritative multi-run evidence lives under `runs/`.
