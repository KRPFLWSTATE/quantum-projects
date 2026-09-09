# Decision study (separate from the 20-job GHZ archive)

Policy-controlled six-variable QAOA decision workflow. This namespace is **not** part of `dba-qpu-run/results/runs/`.

## Commands

```bash
cd "/Users/kawinperera/Downloads/Quantum Projects"
PYTHONUNBUFFERED=1 venv/bin/python -u decision-study/study.py audit-legacy
PYTHONUNBUFFERED=1 venv/bin/python -u decision-study/study.py prepare
PYTHONUNBUFFERED=1 venv/bin/python -u decision-study/study.py validate
PYTHONUNBUFFERED=1 venv/bin/python -u decision-study/study.py status
PYTHONUNBUFFERED=1 venv/bin/python -u decision-study/study.py report
PYTHONUNBUFFERED=1 venv/bin/python -u decision-study/study.py export-return-packet
```

Hardware:

- Legacy GHZ: user says `do a legacy GHZ run`.
- This study: `do a run` or `do a decision run` (exactly one 12-PUB block after live budget checks).
- Resume an in-flight decision job: `resume the run` (never submits a replacement).

`run-next --hardware` is wired but still refuses unless that later authorisation is used.

## Evidence status

Decision QPU jobs submitted: **0** (setup). Historical GHZ jobs remain the 20 archived probe executions.
