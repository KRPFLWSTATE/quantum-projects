# Generated results (archived-data reproduction)

Campaign status: **COMPLETE**. Submission gate remains **JOB_CAP_REACHED**.

## Decision study (six ibm_fez blocks)

- 72 PUB evaluations, 73,728 shots. These are six repeated 12-PUB blocks on six synthetic fixtures, not 72 independent organisations.
- Exact optima D1–D6: {'D1': 23.0, 'D2': 23.0, 'D3': 23.0, 'D4': 24.0, 'D5': 23.0, 'D6': 22.0}.
- Greedy incumbents: {'D1': 23.0, 'D2': 23.0, 'D3': 21.0, 'D4': 24.0, 'D5': 22.0, 'D6': 22.0}.
- Every full 1,024-shot pool contained at least one optimum. That is expected for 1,024 draws from 64 states and is not a quantum-advantage claim.
- P0 modal string was feasible in 40/72 PUBs. An `accept` label on P0 is unguarded.
- P1, P2 and P3 each selected a feasible optimum on all 72 unchanged-specification PUBs and improved on the greedy incumbent in 24/72 cases (D3 and D5). The other 48 already had an optimal incumbent. The three policies share samples.
- D4 p=2 mean optimal-hit fraction is 0.008789, below uniform 1/64 = 0.015625.
- Identity second QAOA layer on fixtures ['D3', 'D6']. These are not demonstrations that extra layers help.
- Client receipt elapsed times ranged from 13.10s to 22.99s; all six returned within 30s. No deadline-timeout or specification-change event is established by these jobs.

## Legacy GHZ (20 jobs)

Sample mean Hellinger versus sampled Aer baselines: 0.9043692534809485. Run 20 is the long queue outlier (1660.303566 s). Exact-GHZ baselines are tabulated separately.

## Bitstring convention

The displayed six-character string is little-endian over task_0..task_5: left character is task_5, right character is task_0. Worked D1 example `011001` maps to {'task_0': 1, 'task_1': 0, 'task_2': 0, 'task_3': 1, 'task_4': 1, 'task_5': 0} with utility 23.0.

## Replay

Post-collection replay of the same hardware pools is labelled `analysis_type=post_collection_policy_replay`. It is not a new IBM job. P2 compares objective/constraint/variable payloads; a metadata-only `current_version` change is overwritten in `verifier.py` and does not by itself cause VERSION_MISMATCH.
