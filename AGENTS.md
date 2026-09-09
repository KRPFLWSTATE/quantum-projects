## Learned User Preferences
- Never run `git add`, `git commit`, or `git push` until the user says the exact phrase "push all to github" (or an unambiguous equivalent).
- Never invent or fabricate experimental QPU results; report only observed jobs, counts, and metrics.
- After the decision-study completion freeze: **"do a run"** and **"do a decision run"** both execute exactly one decision-study SamplerV2 block (`decision-study/study.py run-next --hardware`) after frozen-protocol and live free-plan budget checks. The published campaign is **COMPLETE at 6/6 jobs**; further authorised runs remain blocked by the frozen job cap unless the author later freezes a new protocol in a separate directory. **"do a legacy GHZ run"** submits the old 3-qubit GHZ probe via `dba-qpu-run/run_circuit.py` then `analyze_results.py`. **"resume the run"** retrieves an existing decision-study attempt and never calls provider run again. Status, report, repair, documentation, and completion prompts are not hardware permission.
- Do not submit extra IBM jobs except when the user says to do a run, do a decision run, or do a legacy GHZ run.
- Do not modify the manuscript. Useful repository documentation may be added when the author explicitly requests a publication-repository pass.
- Do not overwrite Run 1 or Run 2 archives; do not commit `save_credentials.py`, `.env`, `venv/`, `__pycache__/`, or `*_backup.json`.

## Learned Workspace Facts
- The IJCA/Taylor & Francis submission described in prior notes was rejected (letter dated 8 September 2026) as within scope but lacking sufficient contribution and clarity; do not treat that review-status text as current manuscript–repository alignment.
- Decision-study QAOA work lives under `decision-study/` and must not be mixed into the 20-job GHZ archive under `dba-qpu-run/results/runs/`.
- Authoritative GHZ hardware archives live in `dba-qpu-run/results/runs/`; `dba-qpu-run/qpu_run_telemetry.json` is a last-run convenience copy.
- GHZ probe backend is chosen by `service.least_busy(simulator=False, operational=True, min_num_qubits=3)`, not a hardcoded machine. Decision-study campaign backend is a frozen Open Plan pin (documented deterministic rule; not GHZ fidelity and not least_busy).
- Legacy GHZ SHA-256 baseline is captured once under `decision-study/data/preservation/legacy_sha256.json`; later commands must verify it, not silently rewrite it.
- Decision-study campaign archive status is COMPLETE (six physical jobs). Engineering `study.py status` still reports a submission blocker `JOB_CAP_REACHED`. Do not weaken that gate. Offline reproduction is `python tools/reproduce.py` and must not call Sampler run.
- Probe circuit is 3-qubit GHZ-style (`H(0)`, `CX(0,1)`, `CX(1,2)`, `measure_all()`), 1000 shots, Hellinger fidelity over the union of all bitstrings without renormalizing leakage away.
- Python env is repo-root `venv/` with tested pins in `requirements-repro.txt` and historical mins in `requirements.txt`; IBM credentials are local and gitignored.
- Run IBM scripts with unbuffered Python (`PYTHONUNBUFFERED=1` / `python -u`); `QiskitRuntimeService()` / `least_busy()` can hang with empty buffered stdout.
- Frozen protocol hash: `0e8c4283c971f672853d3dfdf9167911eb834a0b3dc0aad16e1ef377f0cd046a`. Do not format or refactor frozen `decision-study/src` or `study.py` in a way that changes those hashes.
- Post-collection analysis lives under `tools/` with version `publication-analysis-v2`. Development installers live under `archive/development/`. Isolated offline reproduction is `python tools/reproduce.py --output build/reproduction` and must not copy into `results/publication` unless `--refresh-publication` is passed.
