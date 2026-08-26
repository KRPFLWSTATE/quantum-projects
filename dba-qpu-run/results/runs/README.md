# Observed QPU run records

This directory is the authoritative immutable archive of the two observed IBM Quantum hardware executions reported in the research artefact.

- **Run 1** on `ibm_kingston`, job `da6c1u60ukec7381slv0`.
- **Run 2** on `ibm_fez`, job `da715qe0ukec7382m480`.
- Both used a 3-qubit telemetry-probe circuit and 1,000 shots.
- Each Hellinger fidelity compared against that run's own local AerSimulator baseline.
- Leakage outcomes retained; no outcome renormalized away.
- Two-run comparative pilot, not statistically powered backend benchmark.
- Do not overwrite these records during future circuit execution.

| File | Backend | Job ID | Hellinger fidelity |
|------|---------|--------|-------------------|
| `run_01_ibm_kingston.json` | `ibm_kingston` | `da6c1u60ukec7381slv0` | 0.6981714217786029 |
| `run_02_ibm_fez.json` | `ibm_fez` | `da715qe0ukec7382m480` | 0.9310600068882383 |
