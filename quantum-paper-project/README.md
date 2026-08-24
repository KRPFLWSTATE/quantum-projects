# Quantum Paper Project (DSL Submission)

Repository for the DSL submission quantum paper: manuscript, experiment code, and **verified** results only.

## THE HARD RULE: Never invent results

**This project absolutely prohibits inventing, fabricating, or hallucinating experimental results under any circumstance.**

- Do not add fake bitstring counts, fidelity values, job IDs, timings, or backend telemetry.
- JSON files under `results/` are **schema templates** until filled from real Qiskit / IBM Quantum runs.
- Do not commit synthetic plots or diagrams presented as experimental output.
- Cursor enforces this via [`.cursor/rules/no-invent-results.mdc`](../.cursor/rules/no-invent-results.mdc) (`alwaysApply: true`).

If an experiment has not been run, leave placeholders as `null` or empty objects and mark documentation as pending.

## Folder structure

```
quantum-paper-project/
├── manuscript/          # Paper draft (Word)
├── src/                 # Circuits, runners, analysis (to be added)
├── results/             # JSON outputs from real runs only (templates until then)
├── logs/                # Job logs from real executions
├── figures/             # Diagrams/plots from real artifacts (e.g. circuit_diagram.png later)
├── results_summary.md   # Human-readable summary (template until real data)
└── requirements.txt     # Python dependencies
```

## What will contain real data (after experiments)

| File | Purpose |
|------|---------|
| `results/simulation_counts.json` | AerSimulator bitstring histogram |
| `results/hardware_counts.json` | QPU measurement histogram |
| `results/qpu_run_telemetry.json` | Job metadata and timing |
| `results/fidelity_calculation.json` | Hellinger fidelity from real inputs |
| `results_summary.md` | Narrative summary with actual numbers |
| `figures/circuit_diagram.png` | Circuit diagram from implemented circuit |
| `logs/` | Raw execution logs |

## Setup

Requires **Python 3.10+**.

```bash
cd quantum-paper-project
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

IBM Quantum access (for hardware runs): configure credentials per [Qiskit IBM Runtime](https://docs.quantum.ibm.com/) documentation. Do not commit secrets; use `.env` (gitignored).

## Manuscript

Draft: `manuscript/DSL-Submission-Manuscript-15.docx`

## Pending artifacts

The following are **intentionally not included** until backed by real work:

- `figures/circuit_diagram.png` — add after the circuit is implemented and diagram is exported from Qiskit/matplotlib.
- Numeric content in `results_summary.md` and all `results/*.json` fields currently marked template-only.

## License / attribution

See repository root for collaboration and publication context.
