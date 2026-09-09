# Results

Generated tables and figures live in [`results/publication/`](../results/publication/) after `python tools/reproduce.py`. Interpretation text is produced by that command in `results/publication/reports/RESULTS.md`.

Favourable and unfavourable observations that must remain visible:

- Guarded policies P1–P3 selected feasible optima on all 72 unchanged-specification PUBs, and improved over greedy only on D3 and D5 (24/72). The remaining 48 PUBs already had an optimal incumbent.
- P0 is an unguarded modal ablation. Its `accept` label is not a valid business decision. Feasible modals occurred in 40/72 PUBs.
- D4 p=2 mean optimal-hit frequency is below uniform 1/64 even though every 1,024-shot pool contained an optimum.
- Six blocks were collected on 9 September 2026 in about 18 minutes. They are clustered repeats, not a longitudinal stability study.
- 73,728 shots are not 73,728 independent experiments. The highest-level repeated acquisition unit is the block.

Legacy GHZ results remain 20 comparative probes. Hellinger fidelity versus each run’s sampled Aer baseline is the archived comparison. Exact-GHZ (000/111) fidelity is tabulated separately. Run 20 is the long queue-wait outlier (log axis on the queue figure).

Post-collection replay of archived hardware pools is labelled separately from the raw jobs. It does not create IBM events.
