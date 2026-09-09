# Methods

The decision study is a **synthetic six-task maintenance selection** problem: choose exactly `k=3` of six tasks (`task_0` … `task_5`) subject to pairwise conflicts and pairwise interaction bonuses. It is not an operational maintenance system.

Utility is the business objective:

`U(x) = Σ_i b_i x_i + Σ_{i<j} s_{ij} x_i x_j`

Feasibility requires `Σ x_i = k` and `x_i x_j = 0` for each conflict pair. QUBO energy is `E = -U + A V`, where `V` counts cardinality and conflict violations and `A = 1 + Σ|b| + Σ|s|`. Feasibility is **not** inferred from low energy.

QAOA uses the independent numpy mixer/phase convention in `decision-study/src/qaoa.py`. Frozen parameters are the saved pre-repair Powell `result.x` values in `qaoa_parameters.json`. A later callback-best optimiser exists in source but **did not** generate this frozen set. Re-running the current optimiser will not reconstruct the stored parameters.

Circuits were transpiled at optimization level 1, seed 20260908, onto pinned `ibm_fez`. Each SamplerV2 block submitted 12 PUBs (D1–D6 × p=1 and p=2) with 1,024 shots. Twirling and dynamical decoupling were disabled if the API exposed those switches.

Displayed IBM bitstrings are little-endian over the six tasks: the leftmost character is `task_5`. See `results/publication/tables/worked_example.json`.

Simulation fixtures S01–S24 were generated with seed 20260908. Policy replay of those fixtures samples with seed `4242 + len(instance_id)`. Because S01–S24 IDs have equal length, they share seed 4245. Their [0.3]/[0.4] angles are arbitrary, not simulator-optimised parameters.

D3 and D6 p=2 saved parameters have a second-layer identity (`γ₂ = β₂ = 0`, `kind=start`). They are not evidence that extra QAOA layers help.
