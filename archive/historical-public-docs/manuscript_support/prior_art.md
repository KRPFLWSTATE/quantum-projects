# Prior-art comparison (honest; novelty unresolved)

Access date: 2026-09-08. Full texts were not uniformly available. Cells use
"not established from inspected text" when the available abstract/record did not
establish the cell. Do not treat this table as a claim of absence.

Working question: How can a reproducible orchestration workflow validate and,
when appropriate, revalidate sampled quantum optimisation candidates against a
current organisational decision specification, while respecting deadlines and
retaining a classical fallback?

Candidate contribution (unverified as first-of-kind): a precisely specified
policy for accepting, rejecting, or revalidating candidate pools when the
decision specification changes during an asynchronous quantum request.

## Sources inspected at record/abstract level

| Source | Link | What was actually read |
| --- | --- | --- |
| Farhi, Goldstone, Gutmann, A Quantum Approximate Optimization Algorithm | https://arxiv.org/abs/1411.4028 | arXiv abstract/record (HTML fetch timed out in this session) |
| Hadfield et al., From QAOA to Quantum Alternating Operator Ansatz | https://arxiv.org/abs/1709.03489 | citation record; full PDF not loaded here |
| Weder et al., QProv | https://doi.org/10.1049/qtc2.12012 | Wiley/IET abstract: provenance attributes, automatic collection, hardware selection / compiler comparison / error analysis use cases. Published IET Quant. Commun. 2 (2021) 171-181 |
| Weder et al., Provenance-Preserving Analysis and Rewrite of Quantum Workflows | https://doi.org/10.1007/s42979-022-01625-9 | DOI only in this session; workflow rewrite + provenance is the title-level topic |
| Gerlach et al., Hybrid Quantum-Classical Multi-Agent Pathfinding | https://proceedings.mlr.press/v267/gerlach25a.html | PMLR proceedings landing; MAPF hybrid, not organisational spec-change revalidation |
| Shi et al., hierarchical Bayesian hybrid multi-agent decision making | https://cpb.iphy.ac.cn/article/doi/10.1088/1674-1056/adefd7 | DOI landing not fully loaded here |
| Hevner et al., Design Science in IS Research | https://aisel.aisnet.org/misq/vol28/iss1/6/ | canonical DSR method paper; not a quantum workflow |
| Descazeaux, Mapping the Narratives of Quantum Computing in IS | https://aisel.aisnet.org/icis2025/quantum/quantum/5/ | AIS landing; full text not established from inspected text |
| Classical analogue (stale results) | e.g. cache invalidation / MVCC / optimistic concurrency | conceptual analogue only; not a substitute for a systematic IS literature review |

## Comparison matrix

Columns: problem; actual agents; problem-dependent encoding; hardware vs sim; constraint verification; decision-version handling; deadlines; fallback; provenance; evaluation.

| Work | problem | actual agents | problem-dependent encoding | hardware vs sim | constraint verification | decision-version handling | deadlines | fallback | provenance | evaluation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Farhi et al. QAOA | combinatorial optimisation via alternating cost/mixer unitaries | not established from inspected text (algorithm paper, not an actor system) | problem Hamiltonian / cost operator | theory/simulation in original paper; later hardware uses exist outside this paper | feasibility of application constraints not established from inspected text as an organisational verifier | not established from inspected text | not established from inspected text | not established from inspected text | not established from inspected text | optimisation quality of QAOA |
| Hadfield et al. QAOA ansatz | constrained QAOA mixers | not established from inspected text as organisational agents | mixing operators that preserve feasible subspaces | not established from inspected text for IBM Open Plan | constraint-preserving mixers are the paper topic at the encoding level | not established from inspected text | not established from inspected text | not established from inspected text | not established from inspected text | ansatz design |
| Weder et al. QProv | collect/store quantum provenance attributes | software provenance system, not organisational decision agents | circuit/hardware metadata | hardware-oriented collection (IBM in project docs) | not established from inspected text as business-constraint verification | not established from inspected text | not established from inspected text | not established from inspected text | yes: QProv model and collector | case study of provenance uses |
| Weder et al. workflow rewrite | quantum workflow analysis/rewrite while preserving provenance | workflow system; “agents” not established from inspected text | workflow/circuit artefacts | hybrid quantum algorithms in title | not established from inspected text as incumbent-threshold policies | specification-change-during-async-request not established from inspected text | not established from inspected text | not established from inspected text | provenance-preserving rewrite is the stated topic | workflow methods |
| Gerlach HQMAP | multi-agent pathfinding | yes: MAPF agents | hybrid quantum-classical MAPF encoding | not fully established from inspected text in this session | path constraints of MAPF | organisational decision-version drift not established from inspected text | not established from inspected text | not established from inspected text | not established from inspected text | MAPF metrics |
| Shi et al. | hierarchical Bayesian hybrid multi-agent decisions | multi-agent in title | not established from inspected text | not established from inspected text | not established from inspected text | not established from inspected text | not established from inspected text | not established from inspected text | not established from inspected text | not established from inspected text |
| Hevner DSR | IS design-science method | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | design evaluation guidelines |
| Descazeaux ICIS 2025 | narratives of QC in IS | not established from inspected text | not established from inspected text | not established from inspected text | not established from inspected text | not established from inspected text | not established from inspected text | not established from inspected text | not established from inspected text | narrative mapping |
| This study (local, unpublished) | six-item selection with interactions/conflicts; synthetic | deterministic mailbox components + monolithic controller; no runtime LLM | QUBO/Ising QAOA p=1/p=2 | GHZ historical hardware separate; decision hardware not yet run | independent business verifier + policies P1–P3 | P2 reject mismatch; P3 compatible revalidation (replay only so far) | modelled 5/30/300 s, not measured org requirements | greedy incumbent / abstain | local hashes + IBM job linkage planned; hashes ≠ cryptographic IBM proof | local sim + policy replay; decision hardware 0 |

## Novelty assessment

Overlap is substantial: QAOA, quantum provenance, hybrid workflows, multi-agent optimisation, and design-science evaluation already exist.

Remaining candidate contribution is the evaluated *policy contract* for stale/async sampled solver pools under specification change, with classical fallback and explicit deadlines.

Because closest workflow/provenance papers were not fully read as PDFs in this session, **novelty is unresolved**. Local engineering may continue. This does not authorise extra quantum consumption to chase an unsupported first-of-kind claim. The study is not marked publication-ready on novelty grounds.
