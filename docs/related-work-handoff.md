# Related-work bibliographic handoff

Inspection class is stated per entry. No paid access. Not an exhaustive novelty search. `NOVELTY_STATUS` remains unresolved.

## Farhi, Goldstone, Gutmann — QAOA

- Farhi, E., Goldstone, J. & Gutmann, S. *A Quantum Approximate Optimization Algorithm*. arXiv:1411.4028, 14 Nov 2014. MIT-CTP/4610.
- URL inspected: https://arxiv.org/abs/1411.4028 (abstract/title page, 2026-09-09).
- Pointer: introduces p-layer QAOA for combinatorial optimisation; MaxCut analysis on regular graphs; p=1 3-regular approximation ratio ≥ 0.6924 in the abstract.
- Class: **abstract and arXiv landing page**, not a claim that the full PDF was line-audited in this pass.

## QProv

- Weder, B., Barzen, J., Leymann, F., Salm, M. & Wild, K. *QProv: A provenance system for quantum computing*. IET Quantum Communication 2(4) 171–181 (2021). DOI 10.1049/qtc2.12012.
- URL inspected: https://doi.org/10.1049/qtc2.12012 (publisher abstract, 2026-09-09).
- Pointer: automated collection of provenance attributes for circuits, environments and QPUs.
- Class: **publisher abstract**. Full-text feature comparison with this repository’s decision policies was **not** completed here. Do not infer absence of a feature from inaccessibility.

## Weder et al. — quantum workflows

- Weder, B., Barzen, J., Beisel, M. & Leymann, F. *Provenance-Preserving Analysis and Rewrite of Quantum Workflows for Hybrid Quantum Algorithms*. SN Computer Science 4:233 (2023). DOI 10.1007/s42979-022-01625-9. Received 29 Aug 2022, accepted 20 Dec 2022, published 23 Feb 2023.
- URL inspected: https://doi.org/10.1007/s42979-022-01625-9 and Springer landing metadata (2026-09-09).
- Pointer: analyse/rewrite hybrid quantum workflows for hybrid runtimes while collecting provenance and process views.
- Class: **publisher abstract / landing page**. Full-text audit of overlap with P0–P3 reuse was not completed.

## Kung and Robinson — optimistic concurrency / validation

- Kung, H. T. & Robinson, J. T. *On optimistic methods for concurrency control*. ACM Transactions on Database Systems 6(2) 213–226 (1981). DOI 10.1145/319566.319567.
- URL inspected: https://doi.org/10.1145/319566.319567 (ACM landing, 2026-09-09). PDF copies at institutional URLs were used only as corroboration of title/authors/venue.
- Pointer: non-locking concurrency control with read / validation / write; abort on failed validation.
- Class: **ACM landing + PDF title page**. Analogical, not a claim that this paper studies QPU sample reuse.

## Use in the manuscript revision

Cite these as prior art for QAOA, quantum provenance/workflows, and classical validation-before-commit. Do not assert that inaccessible full texts lack a comparable reuse protocol.
