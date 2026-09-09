# Reproduce

## Environment

Tested locally: Python 3.14.6 in the repository `venv/`, packages pinned in [`requirements-repro.txt`](../requirements-repro.txt). Archived IBM jobs report Runtime 0.49.0, Qiskit 2.5.2 and Aer 0.17.2 inside job metrics; that is historical job metadata, not a complete per-job lock of every transitive library.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-repro.txt
```

Do not commit `.env` or IBM tokens. They are not required for archived-data reproduction.

## Archived-data reproduction (default, offline)

```bash
python tools/reproduce.py --output build/reproduction
```

Expected: exit code 0, `campaign_status: COMPLETE`, tables and figures **only** under the `--output` directory (default `build/reproduction`). Ordinary reproduction does **not** copy into `results/publication`. Use `--refresh-publication` only after a successful isolated rebuild if you intend to replace derived publication outputs (prior `results/publication` is copied to `archive/follow-up-2026-09-09/results-publication-before-refresh` on first refresh).

Also run:

```bash
python -m unittest discover -s decision-study/tests -v
python -m unittest discover -s tools/tests -v
```

The 46 frozen decision-study tests remain authoritative for the executed implementation.

## Ideal-circuit validation

`decision-study/tools/verify_isa.py` compares frozen logical/compact/ISA probabilities using the compact active-wire mapping. It must not statevector-simulate the padded 156-qubit ISA as a 156-qubit register. Reproduction writes its JSON into the rebuild directory.

## Fresh hardware replication (not implemented as one command)

There is **no tested isolated replication runner**. The published ledger must not be erased or reopened. A new campaign would require IBM access, a **separate directory**, a new protocol freeze, and would produce different stochastic outcomes and possibly different calibration/layout. This repository will not submit QPU jobs from documentation commands.

## Troubleshooting

- `JOB_CAP_REACHED` on `study.py status` after a completed campaign is the submission gate, not an archive failure.
- Do not run `study.py prepare` / live `status` as the public quick start; they are not all pure offline operations.
- If protocol or legacy hashes fail, stop. Do not rewrite `legacy_sha256.json` to hide a mismatch.
