# DBA QPU run package

20-run 3-qubit GHZ telemetry-probe archive. This namespace is **not** the decision-study QAOA campaign (`decision-study/`).

Offline recompute of archived Hellinger fidelities: `python tools/reproduce.py` (repository root). That path does not submit IBM jobs.

## Authoritative vs convenience telemetry

- **`results/runs/`** is the authoritative immutable archive of all observed hardware executions (20 runs: `ibm_kingston`, `ibm_fez`, and `ibm_marrakesh`).
- **`qpu_run_telemetry.json`** at this package root is a last-run convenience copy. Do not treat it as the full multi-run archive.

Supporting artefacts (IBM Runtime exports, figures, comparative index) live under [`results/`](results/).

## Additional hardware (not the public quick start)

IBM credentials are required only to append a **new** GHZ probe. Do not overwrite `results/runs/`. Backend selection is `least_busy(..., min_num_qubits=3)`, not a hardcoded machine. The authorising phrase is `do a legacy GHZ run`.
