# Methods

The decision study is a **synthetic six-task maintenance selection** problem: choose exactly `k=3` of six tasks (`task_0` … `task_5`) subject to pairwise conflicts and **signed** pairwise interactions `s_ij` (not uniformly positive bonuses). It is not an operational maintenance system.

Utility is the business objective:

`U(x) = Σ_i b_i x_i + Σ_{i,j} s_ij x_i x_j`

QUBO energy is `E(x) = -U(x) + A[(Σ_i x_i - k)^2 + Σ_{(i,j) in C} x_i x_j]`, with `A = 1 + Σ_i |b_i| + Σ_{i,j} |s_ij|`. The squared term is the **squared cardinality penalty**. Feasibility (`Σ x_i = k` and no selected conflict pair) is **not** inferred from low energy.

QAOA uses the independent numpy mixer/phase convention in `decision-study/src/qaoa.py`. Cost unitary `exp(-i γ H_E / A)`; mixer `RX(2β)`. Frozen parameters are the saved pre-repair Powell `result.x` values in `qaoa_parameters.json`. A later callback-best optimiser exists in source but **did not** generate this frozen set. Re-running the current optimiser will not reconstruct the stored parameters. This is not a new circuit family; do not reverse bit order.

Circuits were transpiled at optimization level 1, seed 20260908, onto pinned `ibm_fez` (name rule frozen before hardware; not selected for GHZ fidelity). Each SamplerV2 block submitted 12 PUBs (D1–D6 × p=1 and p=2) with 1,024 shots. Twirling and dynamical decoupling were disabled if the API exposed those switches. ISA probabilities use the six-active-wire mapping, never a 156-qubit statevector.

Displayed IBM bitstrings are little-endian over the six tasks: the leftmost character is `x5`/`task_5`, the right character is `x0`/`task_0`. D1 displayed `011001` selects tasks 0, 3 and 4 with utility 23. See `results/publication/tables/worked_example.json` on a clone, or `build/reproduction/tables/worked_example.json` after isolated reproduction.

Feasible counts D1–D6: 12, 8, 9, 6, 6, 6. Exact optima: 23, 23, 23, 24, 23, 22. Optimal-state multiplicities: 1, 2, 1, 1, 1, 2. Greedy-plus-swaps (heuristic) utilities: 23, 23, 21, 24, 22, 22. Penalty scale A: 47, 46, 47, 46, 47, 46.

Simulation fixtures S01–S24 were generated with seed 20260908. Policy replay of those fixtures samples with seed `4242 + len(instance_id)`. Because S01–S24 IDs have equal length, they share seed 4245. Their [0.3]/[0.4] angles are arbitrary, not simulator-optimised parameters. 672 policy rows; separately labelled simulation, not extra hardware.

D3 and D6 p=2 saved parameters have a second-layer identity (`γ₂ = β₂ = 0`, `kind=start`). D4 p=2 is a retained poor result (optimal-hit 54/6144 = 0.0087890625, below uniform 1/64).
