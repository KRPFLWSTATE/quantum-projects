"""Local sampling-prefix and classical comparison tables. No hardware counts."""

from __future__ import annotations

import json
import random
from itertools import combinations

from .classical import cardinality_k_then_conflict_check, uniform_bitstring_samples, _bits_from_set
from .fixtures import hardware_instances
from .hashing import write_json_atomic
from .model import is_feasible, bits_from_little_endian_bitstring, little_endian_bitstring, utility
from .oracle import exact_summary
from .paths import DERIVED_DIR, TABLES_DIR
from .qaoa import independent_statevector_amplitudes, probability_dict

PREFIXES = [1, 4, 16, 64, 256, 1024]


def _prefix_stats(instance, shots: list[str], optimum: float) -> list[dict]:
    rows = []
    for n in PREFIXES:
        pool = shots[: min(n, len(shots))]
        distinct = list(dict.fromkeys(pool))
        feasible = []
        for bitstring in pool:
            bits = bits_from_little_endian_bitstring(bitstring, instance.n)
            if is_feasible(instance, bits):
                feasible.append(utility(instance, bits))
        best = max(feasible) if feasible else None
        opt_hits = sum(1 for u in feasible if abs(u - optimum) < 1e-9)
        denom = len(pool) or None
        rows.append(
            {
                "instance_id": instance.instance_id,
                "prefix": n,
                "shots_available": len(shots),
                "shots_inspected": len(pool),
                "distinct": len(distinct),
                "feasible_count": len(feasible),
                "feasible_fraction": (len(feasible) / len(pool)) if pool else None,
                "best_feasible_utility": best,
                "optimal_hit_count": opt_hits,
                "optimal_hit_rate": (opt_hits / len(pool)) if pool else None,
                "evidence_type": "sampled_simulation",
                "note": "Prefixes from one shared stream are dependent analyses, not independent experiments. Full-shot cost still applies.",
            }
        )
    return rows


def write_analysis_tables(qaoa_params: dict) -> dict:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    instances = {inst.instance_id: inst for inst in hardware_instances()}
    ideal_rows = []
    prefix_rows = []
    card_rows = []
    for fx in qaoa_params["fixtures"]:
        inst = instances[fx["instance_id"]]
        summary = exact_summary(inst)
        opt_u = float(summary["optimum_utility"])
        n_feas = int(summary["feasible_count"])
        n_opt = len(summary["optimum_bitstrings"])
        uniform_feas = n_feas / 64.0
        uniform_opt = n_opt / 64.0
        for depth, key in ((1, "p1"), (2, "p2")):
            best = fx[key]["best"]
            amps = independent_statevector_amplitudes(inst, best["gammas"], best["betas"])
            probs = probability_dict(amps, inst.n)
            rng_seed = 20260908 + (ord(inst.instance_id[-1]) * 10) + depth
            keys = list(probs.keys())
            weights = [probs[k] for k in keys]
            shots = random.Random(rng_seed).choices(keys, weights=weights, k=1024)
            prefix_rows.extend(
                {**row, "p": depth, "solver": "ideal_qaoa_finite_shot_sim"}
                for row in _prefix_stats(inst, shots, opt_u)
            )
            uniform_shots = uniform_bitstring_samples(1024, seed=rng_seed + 99)
            prefix_rows.extend(
                {**row, "p": None, "solver": "uniform_bitstring"}
                for row in _prefix_stats(inst, uniform_shots, opt_u)
            )
            ideal_rows.append(
                {
                    "instance_id": inst.instance_id,
                    "p": depth,
                    "expectation_e_over_a": best.get("expectation_e_over_a"),
                    "ideal_feasibility_probability": best.get("ideal_feasibility_probability"),
                    "ideal_optimal_hit_probability": best.get("ideal_optimal_hit_probability"),
                    "uniform_feasibility_probability": uniform_feas,
                    "uniform_optimal_hit_probability": uniform_opt,
                    "worse_than_uniform_feasibility": float(best.get("ideal_feasibility_probability") or 0) < uniform_feas - 1e-12,
                    "worse_than_uniform_optimal_hit": float(best.get("ideal_optimal_hit_probability") or 0) < uniform_opt - 1e-12,
                    "evidence_type": "ideal_simulation",
                }
            )
        card = cardinality_k_then_conflict_check(inst, 1024, seed=4242 + ord(inst.instance_id[-1]))
        card_rows.append(
            {
                "instance_id": inst.instance_id,
                "proposals": card["proposals"],
                "rejected_conflicts": card["rejected_conflicts"],
                "accepted": len(card["accepted"]),
                "subset_space": card["subset_space"],
                "work": card["work"],
                "evidence_type": "sampled_simulation",
            }
        )
        subsets = list(combinations(range(inst.n), inst.k))
        rng = random.Random(4242 + ord(inst.instance_id[-1]))
        stream = []
        for _ in range(1024):
            chosen = subsets[rng.randrange(len(subsets))]
            bits = _bits_from_set(set(chosen), inst.n)
            stream.append(little_endian_bitstring(bits, inst.n))
        prefix_rows.extend(
            {**row, "p": None, "solver": "cardinality_k_proposals"}
            for row in _prefix_stats(inst, stream, opt_u)
        )

    write_json_atomic(DERIVED_DIR / "ideal_qaoa_vs_uniform.json", ideal_rows)
    write_json_atomic(DERIVED_DIR / "prefix_analysis.json", prefix_rows)
    write_json_atomic(DERIVED_DIR / "cardinality_k_baseline.json", card_rows)
    _write_csv(TABLES_DIR / "ideal_qaoa_vs_uniform.csv", ideal_rows)
    _write_csv(TABLES_DIR / "prefix_analysis.csv", prefix_rows)
    _write_csv(TABLES_DIR / "cardinality_k_baseline.csv", card_rows)
    return {
        "ideal_rows": len(ideal_rows),
        "prefix_rows": len(prefix_rows),
        "cardinality_rows": len(card_rows),
    }


def analyse_hardware_archives() -> dict:
    from .paths import RAW_DIR

    rows = []
    if RAW_DIR.is_dir():
        for path in sorted(RAW_DIR.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("evidence_type") != "decision_hardware":
                continue
            pubs = data.get("pubs") or []
            rows.append(
                {
                    "job_id": data.get("job_id"),
                    "intent": data.get("intent"),
                    "n_pubs": data.get("n_pubs_observed") or len(pubs),
                    "shots_valid": data.get("shots_valid"),
                    "charged_usage_seconds": data.get("charged_usage_seconds"),
                    "created_utc": data.get("created_utc"),
                    "result_received_utc": data.get("result_received_utc"),
                    "evidence_type": "decision_hardware",
                }
            )
    write_json_atomic(DERIVED_DIR / "hardware_archive_analysis.json", {"rows": rows, "n_jobs": len(rows)})
    return {"n_jobs": len(rows)}


def _write_csv(path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    lines = [",".join(keys)]
    for row in rows:
        cells = []
        for key in keys:
            value = row.get(key)
            if value is None:
                cells.append("")
            elif isinstance(value, (int, float, str, bool)):
                cells.append(str(value).replace(",", ";"))
            else:
                cells.append(json.dumps(value).replace(",", ";"))
        lines.append(",".join(cells))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
