## Learned User Preferences
- Never run `git add`, `git commit`, or `git push` until the user says the exact phrase "push all to github" (or an unambiguous equivalent).
- Never invent or fabricate experimental QPU results; report only observed jobs, counts, and metrics.
- "Do a run" means submit a real IBM hardware job via `dba-qpu-run/run_circuit.py`, then run `analyze_results.py` and paste the full terminal output; do not generate figures or rewrite README for a single run.
- Do not submit extra IBM jobs except when the user says to do a run.
- Do not modify the manuscript; do not create extra markdown files when the answer can go in chat.
- Do not overwrite Run 1 or Run 2 archives; do not commit `save_credentials.py`, `.env`, `venv/`, `__pycache__/`, or `*_backup.json`.

## Learned Workspace Facts
- This repo supports a paper under double-blind review at International Journal of Computers and Applications (Taylor & Francis); the manuscript is not linked here and data availability is upon reasonable request.
- Authoritative hardware archives live in `dba-qpu-run/results/runs/`; root/`dba-qpu-run` `qpu_run_telemetry.json` is a last-run convenience copy.
- Hardware backend is chosen by `service.least_busy(simulator=False, operational=True, min_num_qubits=3)`, not a hardcoded machine.
- Probe circuit is 3-qubit GHZ-style (`H(0)`, `CX(0,1)`, `CX(1,2)`, `measure_all()`), 1000 shots, Hellinger fidelity over the union of all bitstrings without renormalizing leakage away.
- Python env is repo-root `venv/` with canonical deps in root `requirements.txt`; IBM credentials are local and gitignored.
- Run IBM scripts with unbuffered Python (`PYTHONUNBUFFERED=1` / `python -u`); `QiskitRuntimeService()` / `least_busy()` can hang with empty buffered stdout.
