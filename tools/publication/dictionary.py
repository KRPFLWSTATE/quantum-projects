from __future__ import annotations

from . import ANALYSIS_VERSION

DATA_DICTIONARY = {
    "analysis_version": ANALYSIS_VERSION,
    "tables": {
        "job_level.csv": {
            "unit": "one SamplerV2 block",
            "client_dispatch_utc": "Client created_utc in the raw archive; not IBM metrics.timestamps.created.",
            "charged_usage_seconds": "Reconciled IBM QPU charge for the job.",
            "missing": "null if a provider timestamp was absent.",
        },
        "pub_level.csv": {
            "unit": "one PUB = one fixture × depth inside one block",
            "feasible_shot_fraction": "Feasible shots / 1024. Denominator is all shots, including infeasible.",
            "optimal_hit_fraction": "Shots equal to an exact optimum bitstring / 1024.",
            "absolute_optimality_gap": "exact_optimum - best_feasible_utility; null if no feasible shot (not observed).",
        },
        "policy_level.csv": {
            "strict_improvement_field": "Value returned by frozen apply_policy. P0 does not populate this field; do not treat missing as measured zero.",
            "independent_strict_improvement": "Recomputed from business utility versus greedy incumbent.",
        },
        "ghz_jobs.csv": {
            "hellinger_vs_sampled_aer_baseline": "Hellinger agreement of computational-basis bitstring distributions versus each run's sampled Aer baseline; not quantum-state fidelity or entanglement certification.",
            "hellinger_vs_exact_ghz_baseline": "Separate exact 000/111 split; not a substitute for Aer.",
        },
        "classical_fair_pools.csv": {
            "unit": "fixture × QAOA-panel × prefix × Monte Carlo summary",
            "denominator": "32 replications; seed 20260909 + 1000 × fixture_index in code order. Same classical pools reused for p=1 and p=2 panels. Prefixes are nested prefixes of already acquired pools.",
            "synthetic_elapsed_seconds": "Plan value 10 s, not a measured classical runtime.",
        },
        "replay_adapter_compact.json / replay_adapter_drill.json": {
            "unit": "derived policy record = one pool/scenario combination × one policy",
            "denominators": "Six scenarios use all 72 pools; four substantive-change scenarios use only the first block's 12 pools. 480 pool/scenario combinations × 4 policies = 1,920 derived records. Not six-block specification-change replication.",
            "missing": "null selected when status is abstain/fallback without a candidate.",
        },
        "simulation_fixture_replay.json": {
            "unit": "synthetic fixture policy row",
            "n": "24 fixtures × policies; 672 policy rows. Shared seed 4245 because S01–S24 IDs have equal length. Not hardware.",
        },
    },
    "evidence_classes": {
        "decision_hardware": "Observed IBM SamplerV2 archives under decision-study/data/raw/.",
        "legacy_ghz_hardware": "Observed 3-qubit GHZ probes under dba-qpu-run/results/runs/.",
        "post_collection_policy_replay": "New analysis of already-collected shots; not a new QPU job.",
        "sampled_simulation": "Local random sampling, not hardware.",
    },
}
