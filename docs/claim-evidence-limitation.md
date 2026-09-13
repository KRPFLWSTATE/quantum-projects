# Claim–evidence–limitation (manuscript handoff)

Post-collection analysis `publication-analysis-v3`. Hardware collection date 2026-09-09. Not a novelty declaration. Alignment checked against the supplied canonical manuscript contract; full DOCX comparison not performed in this session.

| Claim to consider | Evidence in this repository | Limitation |
|---|---|---|
| Sampled six-variable QAOA pools can be re-checked under a changed specification using frozen P1–P3 | Current replay adapter: six scenarios × 72 pools and four substantive-change scenarios × first-block 12 pools; 480 pool/scenario combinations × 4 policies = 1,920 derived policy records | Hardware jobs used an unchanged specification. Replay is not a new IBM experiment and does **not** establish specification-change replication across all six blocks. Prefixes are dependent. |
| Discarding the pool and keeping a greedy incumbent is a defined alternative | Greedy-plus-swaps utilities 23,23,21,24,22,22; P1–P3 fall back when ineligible | Greedy-plus-swaps is a **heuristic**, not cheap exact local search. n=6; not a timed organisational process. |
| Recomputing by exact enumeration is practical here | 64 states; exact optima independently enumerated | Does not generalise to large n. Unique-state cost ≠ 1024 QPU shots. |
| Guarded reuse is not the same as P0 accept | P0 feasible modal 40/72; P1–P3 feasible optima 72/72 on unchanged spec; strict improve 24/72 (D3 +2, D5 +1) | P0 is an ablation. Shared samples across P1–P3. No quantum advantage from full-pool containment. |
| Specification-change contribution is not established by the six jobs alone | Replay and separately labelled simulation fixtures (672 policy rows) exist; no hardware spec-change event | Do not treat ordinary validation plus a QPU as automatically novel. P2 accepts metadata-only version-label change (72/72). P3 added-conflict 12/12 vs P2 fallback 10/12 uses an exact feasibility oracle in scenario construction. |
| GHZ archive is separate operational context | 20 jobs (ibm_fez 9, ibm_kingston 3, ibm_marrakesh 8); sampled-baseline Hellinger mean 0.9043692534809485 | Hellinger is computational-basis distribution agreement, not state fidelity or entanglement certification. Not pooled with decision jobs as n=26. |
| Implementation versus established methods | Bounded contract connecting spec, samples, checks, fallback | Distinguishes implementation from QAOA, QProv/workflows, optimistic concurrency, and MIP reoptimization without a fresh full-text overlap audit. See [`contribution-note.md`](contribution-note.md). |
