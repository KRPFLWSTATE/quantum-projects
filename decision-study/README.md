# Decision study

Frozen six-variable QAOA decision campaign, **separate** from `dba-qpu-run/results/runs/`.

**Campaign status (archive):** COMPLETE — six physical `ibm_fez` SamplerV2 jobs, 30.0 s reconciled charge. **Submission status:** blocked (`JOB_CAP_REACHED`). Do not reset the ledger or start a seventh job.

Public interpretation: [`docs/results.md`](../docs/results.md). Offline rebuild: [`docs/reproduce.md`](../docs/reproduce.md).

Active implementation: `study.py` and `src/` (frozen hashes in `config/protocol.json`). New publication analysis is under [`tools/`](../tools/), not inside frozen modules.

Do not use `study.py prepare` / live `status` as the newcomer path. After dependency install:

```bash
python tools/reproduce.py --output build/reproduction
```

Hardware submission still requires the author’s exact phrases (`do a run` / `do a decision run`) and is not part of public reproduction. Development installers live under [`archive/development/`](../archive/development/).
