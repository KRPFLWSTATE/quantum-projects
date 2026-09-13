# ZIP archive navigation

A GitHub clone and an extracted research ZIP are different trees.

- **Clone:** figures and tables currently published after a validated refresh live under `results/publication/`. Default offline reproduction writes `build/reproduction` and does not replace publication output.
- **ZIP:** generated artefacts are under `reproduction_outputs/`. Start at `ARCHIVE_LANDING.md`. Do not treat `docs/` image links that point at `results/publication/` as ZIP-relative; those paths describe the clone.
- `archive/development/PATH_MAP.json` records where historical installer bundles were moved inside the full repository. It is not a map of ZIP members.

Do not execute `dba-qpu-run/run_circuit.py` from the archive; IBM submission is not part of offline reproduction.
