# Results

Default offline reproduction writes **`build/reproduction`**:

```bash
python tools/reproduce.py --output build/reproduction
```

That command does **not** replace [`results/publication/`](../results/publication/). Publication replacement requires `--refresh-publication` after a **separate**, successful isolated generation. Refresh copies from that generation, stages the replacement, and backups the previous publication tree under `archive/publication-backups/` without overwriting the historical `archive/follow-up-2026-09-09/results-publication-before-refresh` snapshot. `results/publication` is rejected as a generation `--output`.

Favourable and unfavourable observations that must remain visible:

- Guarded policies P1–P3 selected feasible optima on all 72 unchanged-specification PUBs, and improved over greedy only on D3 and D5 (24/72). The remaining 48 PUBs already had an optimal incumbent.
- P0 is an unguarded modal ablation. Its `accept` label is not a valid business decision. Feasible modals occurred in 40/72 PUBs.
- D4 p=2 optimal-hit total is 54/6144 = 0.0087890625, below uniform 1/64, even though every 1,024-shot pool contained an optimum.
- Six blocks were collected on 9 September 2026 in about 18 minutes (reconciled charge 30 s). They are clustered repeats, not a longitudinal stability study or 72 firms.
- 73,728 shots are not 73,728 independent experiments. The highest-level repeated acquisition unit is the block.
- Current replay: 1,920 derived policy records as defined in [`claim-evidence-limitation.md`](claim-evidence-limitation.md). Not six-block spec-change replication.

Legacy GHZ results remain 20 comparative probes (not 20 plus 18). Hellinger versus each run’s sampled Aer baseline is computational-basis distribution agreement, not quantum-state fidelity or entanglement certification. Exact-GHZ (000/111) fidelity is tabulated separately. Run 20 is the long queue-wait outlier.

Post-collection replay of archived hardware pools is labelled separately from the raw jobs. It does not create IBM events. Superseded 2026-09-09 replay tables (different path; fixture-default/synthetic linkage) are preserved under `archive/superseded-analysis/2026-09-09-post-collection-replay/` and are not current adapter evidence.
