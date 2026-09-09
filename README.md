# Decision-QAOA hardware archive and GHZ probe records

Software artifact for a **bounded, synthetic six-variable QAOA decision study** on IBM Quantum (`ibm_fez`, six SamplerV2 blocks) together with a **separate 20-run 3-qubit GHZ telemetry probe**. This software title is not the manuscript’s working title.

This is **not** a quantum-advantage, organisational-effectiveness, or publication-readiness claim. Visual polish does not create novelty.

## Evidence (generated)

| Item | Observation | Details |
|---|---|---|
| Decision campaign | **COMPLETE** (archive label) | Six physical jobs, cap six, 30.0 s reconciled charge. Submission gate remains `JOB_CAP_REACHED`. |
| Decision jobs | `ibm_fez` SamplerV2 | 12 PUBs × 1,024 shots per block; 72 PUB evaluations; 73,728 shots as six clustered repeats, not 72 independent firms. |
| GHZ probes | 20 hardware jobs | Kingston 3, Fez 9, Marrakesh 8. Hellinger vs each run’s sampled Aer baseline. |
| Reproduction | Offline after `pip install` | [`python tools/reproduce.py --output build/reproduction`](docs/reproduce.md) |
| License | MIT | [`LICENSE`](LICENSE) |
| Tested env | Python 3.14.6 + [`requirements-repro.txt`](requirements-repro.txt) | Hosted CI is configured locally; a green badge is shown only after a real run. |

Figures: [architecture](results/publication/figures/architecture_and_provenance.svg) · [sampling fractions](results/publication/figures/feasibility_and_optimal_hit.svg) · [policies](results/publication/figures/policy_selection.svg) · [GHZ](results/publication/figures/legacy_ghz.svg)

## Navigation

[Results](docs/results.md) · [Reproduce](docs/reproduce.md) · [Methods](docs/methods.md) · [Data](docs/data-and-provenance.md) · [Architecture](docs/architecture-and-policies.md) · [Limitations](docs/limitations-and-contributions.md) · [Citation](CITATION.cff)

## What the results mean (short)

Guarded policies P1–P3 selected feasible optima on all 72 unchanged-specification PUBs and beat the greedy incumbent only on D3 and D5 (24/72). P0 is an unguarded modal ablation (feasible in 40/72). D4 p=2 optimal-hit frequency is **below** uniform 1/64. Extra p=2 layers on D3 and D6 are identity. The six blocks were taken in about 18 minutes on 9 September 2026. Specification-change behaviour is studied by **post-collection replay** of the same shots, not by a second IBM campaign.

The GHZ archive is a comparative probe, including Run 20’s long queue wait. Details: [`docs/results.md`](docs/results.md) and [`dba-qpu-run/results/runs/README.md`](dba-qpu-run/results/runs/README.md).

## Offline quick start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-repro.txt
python -m unittest discover -s decision-study/tests -v
python tools/reproduce.py --output build/reproduction
```

Expect exit code 0 and `COMPLETE`. These commands must not submit IBM jobs. There is **no** one-command hardware replication runner.

## Repository map

```
decision-study/     Frozen QAOA decision experiment (do not mix into GHZ runs)
dba-qpu-run/        20-run GHZ probe archive
tools/              Post-collection analysis and offline reproduce.py
results/publication/ Generated tables/figures (checked in)
docs/               Reader documentation
archive/            Historical READMEs and development installers
```

## Citation, author, AI

Cite the software via [`CITATION.cff`](CITATION.cff). There is no GitHub Release/DOI as of this writing. Author: Kawin Rehan Perera. AI assistance was used for implementation, debugging, and analysis, not merely grammar. The author is responsible for the archived jobs.
