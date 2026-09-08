# Observed QPU run records

This directory is the authoritative immutable archive of the 20 observed IBM Quantum hardware executions in this repository.

- Circuit: 3-qubit GHZ-style telemetry-probe (`H(0)`, `CX(0,1)`, `CX(1,2)`, `measure_all()`), 1,000 shots.
- Each Hellinger fidelity compared against that run's own local AerSimulator baseline.
- Leakage outcomes retained; no outcome renormalized away.
- Backend chosen at submit time by `least_busy` (not hardcoded). Observed machines: `ibm_kingston` (3), `ibm_fez` (9), `ibm_marrakesh` (8).
- 20-run comparative pilot, not a statistically powered backend benchmark.
- Do not overwrite these records during future circuit execution.

| File | Backend | Job ID | Hellinger fidelity |
|------|---------|--------|-------------------|
| `run_01_ibm_kingston.json` | `ibm_kingston` | `da6c1u60ukec7381slv0` | 0.6981714217786029 |
| `run_02_ibm_fez.json` | `ibm_fez` | `da715qe0ukec7382m480` | 0.9310600068882383 |
| `run_03_ibm_fez.json` | `ibm_fez` | `dabb4gpl216s739pap00` | 0.9249946426251118 |
| `run_04_ibm_marrakesh.json` | `ibm_marrakesh` | `dabjia809bds739s745g` | 0.9672727143671567 |
| `run_05_ibm_marrakesh.json` | `ibm_marrakesh` | `dac1dm0c4p7c738kmq6g` | 0.9799583366060217 |
| `run_06_ibm_kingston.json` | `ibm_kingston` | `dac7fr5nj4cs73ac93vg` | 0.6835891578876895 |
| `run_07_ibm_fez.json` | `ibm_fez` | `dacku7tnj4cs73acpgn0` | 0.9189940519525712 |
| `run_08_ibm_kingston.json` | `ibm_kingston` | `dacqshe42tqs73asiaa0` | 0.5853527915556171 |
| `run_09_ibm_marrakesh.json` | `ibm_marrakesh` | `dadbm2d1ierc738klg2g` | 0.9785668452751094 |
| `run_10_ibm_fez.json` | `ibm_fez` | `dae9knm42tqs73audj90` | 0.9464689386776945 |
| `run_11_ibm_fez.json` | `ibm_fez` | `daej6ht1ierc738m806g` | 0.9346480786998017 |
| `run_12_ibm_marrakesh.json` | `ibm_marrakesh` | `daekkq5nj4cs73af9tq0` | 0.9555557695336403 |
| `run_13_ibm_marrakesh.json` | `ibm_marrakesh` | `daetchd1ierc738mk190` | 0.9331689783800481 |
| `run_14_ibm_fez.json` | `ibm_fez` | `daf6dhm42tqs73avhlc0` | 0.9397460321838972 |
| `run_15_ibm_fez.json` | `ibm_fez` | `dafjq4m42tqs73b01qhg` | 0.8854012537326047 |
| `run_16_ibm_marrakesh.json` | `ibm_marrakesh` | `dafqipe42tqs73b0bfsg` | 0.9599915981197692 |
| `run_17_ibm_fez.json` | `ibm_fez` | `dag140omhr3c73e4h5hg` | 0.9652427584038366 |
| `run_18_ibm_marrakesh.json` | `ibm_marrakesh` | `dag1u40mhr3c73e4i5ag` | 0.98393469220306 |
| `run_19_ibm_marrakesh.json` | `ibm_marrakesh` | `dag30qj9k43c73acqeu0` | 0.9624023920073217 |
| `run_20_ibm_fez.json` | `ibm_fez` | `dag3hpb9k43c73acr12g` | 0.9528646087411794 |
