# Changelog 2026-09-13 (publication-analysis-v3)

Repository correction pass. No new QPU jobs. Frozen protocol, `decision-study/src`, `study.py`, raw jobs, ledger, QPY, and preservation manifests were not rewritten.

- Isolated generation cannot target `results/publication`; refresh copies from a separate successful tree, stages replacement, and timestamp-backups the previous publication tree without touching `archive/follow-up-2026-09-09/results-publication-before-refresh`.
- ISA/hash validation completes before promoting tables/figures; failures write diagnostics only.
- Expected ISA digest is resolved from the frozen protocol QPY table and file bytes, not copied from the job archive field.
- Six physical job archives are validated for linkage, 12 unique D1–D6×p=1,2 mappings, and 1024 six-bit shots matching counts.
- Research ZIP includes PATH_MAP, legacy GHZ README/code (not executed), landing page, and exported-snapshot provenance; whole-ZIP checksum remains external.
- Superseded 2026-09-09 replay tables moved to `archive/superseded-analysis/2026-09-09-post-collection-replay/`.
- Historical `chatgpt_return_packet` sidecar mismatch documented; zip not overwritten.
- Docs/figures aligned to the supplied manuscript contract (greedy heuristic, replay denominators, signed interactions, squared cardinality penalty, Hellinger as bitstring-distribution agreement).
