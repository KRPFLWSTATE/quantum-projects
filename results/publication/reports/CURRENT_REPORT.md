# CURRENT report (dated 2026-09-09)

This is the current generated report. `decision-study/reports/CHATGPT_RETURN_REPORT.md` is historical.

# Generated results (archived-data reproduction)

Campaign status: **COMPLETE**. Submission gate remains **JOB_CAP_REACHED**.

## Decision study (six ibm_fez blocks)

- 72 PUB evaluations, 73,728 shots as six clustered repeats, not 72 organisations.
- Exact optima D1–D6: {'D1': 23.0, 'D2': 23.0, 'D3': 23.0, 'D4': 24.0, 'D5': 23.0, 'D6': 22.0}.
- Greedy incumbents: {'D1': 23.0, 'D2': 23.0, 'D3': 21.0, 'D4': 24.0, 'D5': 22.0, 'D6': 22.0}.
- Every full 1,024-shot hardware pool contained at least one optimum. For independent draws from a fixed distribution the probability is 1-(1-p_opt)^m, not a consequence of the 64-state support size alone. Uniform analytical values are in `checkpoints.json` under `uniform_opt_containment_1024`.
- P0 modal string was feasible in 40/72 PUBs. An `accept` label on P0 is unguarded and is not a safety result.
- P1, P2 and P3 each selected a feasible optimum on all 72 unchanged-specification PUBs and improved on the greedy incumbent in 24/72 cases (D3 and D5).
- D4 p=2 mean optimal-hit fraction is 0.008789, below uniform 1/64 = 0.015625.
- Identity second QAOA layer on fixtures ['D3', 'D6'].
- Client receipt elapsed times ranged from 13.10s to 22.99s.

## Fair classical controls (post-collection)

Plan `tools/publication/plans/classical_comparison_plan.json` is dated after hardware collection and is not preregistered. Classical pools are reused across p=1/p=2 panels. Monte Carlo n=32.

## Replay

Adapter rows: 1920. Unchanged-spec reconcile differences: 0. P2 metadata-only accepts: 72. Frozen verifier overwrites a metadata-only current_version mismatch with payload equality. P2 is not a strict version-label gate.

## Legacy GHZ (20 jobs)

Sample mean Hellinger versus sampled Aer baselines: 0.9043692534809485. Run 20 is the long queue outlier (1660.303566 s).

## Bitstring convention

The displayed six-character string is little-endian over task_0..task_5: left character is task_5, right character is task_0. Worked D1 example `011001` maps to {'task_0': 1, 'task_1': 0, 'task_2': 0, 'task_3': 1, 'task_4': 1, 'task_5': 0} with utility 23.0.
