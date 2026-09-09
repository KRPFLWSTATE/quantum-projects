DATA_DICTIONARY = {
    "analysis_version": "publication-analysis-v1",
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
            "hellinger_vs_sampled_aer_baseline": "Primary archived comparison.",
            "hellinger_vs_exact_ghz_baseline": "Separate exact 000/111 split; not a substitute for Aer.",
        },
    },
    "evidence_classes": {
        "decision_hardware": "Observed IBM SamplerV2 archives under decision-study/data/raw/.",
        "legacy_ghz_hardware": "Observed 3-qubit GHZ probes under dba-qpu-run/results/runs/.",
        "post_collection_policy_replay": "New analysis of already-collected shots; not a new QPU job.",
        "sampled_simulation": "Local random sampling, not hardware.",
    },
}
