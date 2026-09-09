# Quantum Projects

This repository documents a **20-run comparative pilot** of a 3-qubit telemetry-probe circuit executed on IBM Quantum Heron r2 hardware. Observed backends were `ibm_kingston` (3 runs), `ibm_fez` (9 runs), and `ibm_marrakesh` (8 runs). Public code and reproducibility artefacts live under [`dba-qpu-run/`](dba-qpu-run/).

These are **comparative pilot observations**, not claims of quantum advantage or a general backend-performance ranking. Sample mean and sample standard deviation in [`comparative_summary.json`](dba-qpu-run/results/comparative_summary.json) are descriptive of this 20-run set only.

## Compact results

Values below are copied from the archived run records. Each Hellinger fidelity compares hardware counts with that run’s corresponding AerSimulator baseline over the full three-qubit outcome space, without renormalizing away leakage.

| Run | Backend | Job ID | Hellinger fidelity | Queue wait (s) | Client-side wall-clock (s) |
|-----|---------|--------|--------------------|----------------|----------------------------|
| Run 1 | `ibm_kingston` | `da6c1u60ukec7381slv0` | 0.6981714217786029 | 1.191856 | 6.97963285446167 |
| Run 2 | `ibm_fez` | `da715qe0ukec7382m480` | 0.9310600068882383 | 1.046131 | 10.588152885437012 |
| Run 3 | `ibm_fez` | `dabb4gpl216s739pap00` | 0.9249946426251118 | 1.196978 | 216.5911831855774 |
| Run 4 | `ibm_marrakesh` | `dabjia809bds739s745g` | 0.9672727143671567 | 1.714729 | 68.98611497879028 |
| Run 5 | `ibm_marrakesh` | `dac1dm0c4p7c738kmq6g` | 0.9799583366060217 | 1.84353 | 15.635506868362427 |
| Run 6 | `ibm_kingston` | `dac7fr5nj4cs73ac93vg` | 0.6835891578876895 | 35.123728 | 49.69556474685669 |
| Run 7 | `ibm_fez` | `dacku7tnj4cs73acpgn0` | 0.9189940519525712 | 1.20247 | 23.017614126205444 |
| Run 8 | `ibm_kingston` | `dacqshe42tqs73asiaa0` | 0.5853527915556171 | 0.953737 | 8.056244134902954 |
| Run 9 | `ibm_marrakesh` | `dadbm2d1ierc738klg2g` | 0.9785668452751094 | 1.143676 | 7.85809588432312 |
| Run 10 | `ibm_fez` | `dae9knm42tqs73audj90` | 0.9464689386776945 | 0.846913 | 7.298269987106323 |
| Run 11 | `ibm_fez` | `daej6ht1ierc738m806g` | 0.9346480786998017 | 8.819207 | 33.621010065078735 |
| Run 12 | `ibm_marrakesh` | `daekkq5nj4cs73af9tq0` | 0.9555557695336403 | 1.222141 | 14.700201272964478 |
| Run 13 | `ibm_marrakesh` | `daetchd1ierc738mk190` | 0.9331689783800481 | 1.07479 | 17.839301824569702 |
| Run 14 | `ibm_fez` | `daf6dhm42tqs73avhlc0` | 0.9397460321838972 | 1.408739 | 8.042850971221924 |
| Run 15 | `ibm_fez` | `dafjq4m42tqs73b01qhg` | 0.8854012537326047 | 1.56452 | 7.7089011669158936 |
| Run 16 | `ibm_marrakesh` | `dafqipe42tqs73b0bfsg` | 0.9599915981197692 | 1.443633 | 16.115031003952026 |
| Run 17 | `ibm_fez` | `dag140omhr3c73e4h5hg` | 0.9652427584038366 | 1.146283 | 8.167666912078857 |
| Run 18 | `ibm_marrakesh` | `dag1u40mhr3c73e4i5ag` | 0.98393469220306 | 1.054296 | 8.083191871643066 |
| Run 19 | `ibm_marrakesh` | `dag30qj9k43c73acqeu0` | 0.9624023920073217 | 1.412515 | 11.746185064315796 |
| Run 20 | `ibm_fez` | `dag3hpb9k43c73acr12g` | 0.9528646087411794 | 1660.303566 | 1692.7952399253845 |

Observed Hellinger fidelity across these 20 jobs: sample mean 0.9043692534809487, sample stdev 0.11148758083997115, min 0.5853527915556171, max 0.98393469220306.

## Reproducibility archive

- [Immutable run records](dba-qpu-run/results/runs/)
- [IBM Runtime exports](dba-qpu-run/results/ibm-runtime-exports/)
- [Measurement-distribution figures](dba-qpu-run/results/figures/) (Run 1 and Run 2 only; later runs were not given IBM UI figure copies)
- [Comparative summary](dba-qpu-run/results/comparative_summary.json)

Legacy Run 1 convenience exports (do not treat as the multi-run archive):

- [QPU run telemetry](dba-qpu-run/results/qpu_run_telemetry.json)
- [Simulation counts](dba-qpu-run/results/simulation_counts.json)
- [Hardware counts](dba-qpu-run/results/hardware_counts.json)
- [Environment versions](dba-qpu-run/results/environment_versions.md)

`dba-qpu-run/qpu_run_telemetry.json` is a last-run convenience copy (currently Run 20). Authoritative records are `dba-qpu-run/results/runs/run_NN_*.json`.

## How to reproduce

IBM Quantum credentials must be configured locally (for example via `QiskitRuntimeService.save_account()`). Do not commit tokens or `.env` files.

```bash
cd dba-qpu-run
PYTHONUNBUFFERED=1 python -u run_circuit.py
PYTHONUNBUFFERED=1 python -u analyze_results.py
```

Backend selection is `service.least_busy(simulator=False, operational=True, min_num_qubits=3)`, not a hardcoded machine. New jobs append the next `run_NN_*.json` archive and must **not** overwrite existing files under `dba-qpu-run/results/runs/`.

## Anti-fabrication rule

**Never invent experimental results.** Bitstring counts, fidelity values, job IDs, queue times, backend names, and plots must come only from real Qiskit / IBM Quantum runs.

## Layout

```
dba-qpu-run/                 # Pilot circuit, analysis, and verified results
├── results/runs/            # Authoritative immutable 20-run archive
├── results/ibm-runtime-exports/
├── results/figures/         # Run 1 and Run 2 measurement plots only
└── results/comparative_summary.json
```

## Setup

Python 3.10+ recommended.

```bash
cd "/path/to/Quantum Projects"
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### IBM Quantum credentials

Create a `.env` file at the project root (never commit it; it is listed in `.gitignore`), or save an account with Qiskit Runtime as noted above. Example `.env` keys:

```
IBM_QUANTUM_TOKEN=your_token_here
```

Load credentials in code with `python-dotenv` or your runner’s documented method. Do not paste tokens into the repository or chat logs.

## Citation

See [`CITATION.cff`](CITATION.cff). Licensed under the [MIT License](LICENSE).
