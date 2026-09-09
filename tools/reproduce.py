#!/usr/bin/env python3
"""Offline archived-data reproduction. No IBM credentials or QPU submission."""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO / "decision-study"))

from publication import ANALYSIS_VERSION  # noqa: E402
from publication.campaign import campaign_status  # noqa: E402
from publication.dictionary import DATA_DICTIONARY  # noqa: E402
from publication.export import write_research_archive  # noqa: E402
from publication.figures import architecture_diagram, feasibility_opt_hit, ghz_panel, policy_panel, timing_panel, utility_panel  # noqa: E402
from publication.ghz import collect_ghz_jobs  # noqa: E402
from publication.hashes import sha256_path, verify_legacy_hashes, verify_pre_manifest, verify_protocol  # noqa: E402
from publication.metrics import checkpoints, flatten_policy_rows, grouped_rows, instance_catalog, job_rows, p2_layer_note, pub_rows, worked_example  # noqa: E402
from publication.paths import PUBLICATION, PUBLICATION_FIGURES, PUBLICATION_REPORTS, PUBLICATION_TABLES, REPO_ROOT, assert_safe_output, ensure_publication_dirs  # noqa: E402
from publication.replay_analysis import replay_hardware_pools, replay_simulation_fixtures  # noqa: E402
from publication.tables import write_csv, write_json  # noqa: E402


def _forbid_ibm() -> None:
    if os.environ.get("QISKIT_IBM_TOKEN") and os.environ.get("PUBLICATION_ALLOW_IBM") == "1":
        raise RuntimeError("offline reproduction must not enable IBM submission")


def _write_pair(output: Path, name: str, obj) -> None:
    dest = output / name
    assert_safe_output(dest)
    if name.endswith(".csv") and isinstance(obj, list):
        write_csv(dest, obj)
    else:
        write_json(dest, obj)


def run(output: Path) -> int:
    _forbid_ibm()
    output = output.resolve()
    tables = output / "tables"
    figures = output / "figures"
    reports = output / "reports"
    for path in (tables, figures, reports):
        path.mkdir(parents=True, exist_ok=True)
        assert_safe_output(path / ".keep")

    errors = []
    protocol = verify_protocol()
    if not protocol["ok"]:
        errors.append({"protocol": protocol})
    legacy = verify_legacy_hashes()
    if not legacy["ok"]:
        errors.append({"legacy": legacy})
    preserved = verify_pre_manifest()
    if not preserved["ok"]:
        errors.append({"preservation": preserved})

    ghz = collect_ghz_jobs()
    if ghz["n_jobs"] != 20:
        errors.append({"ghz_count": ghz["n_jobs"]})
    if any(not row["aer_matches_archive"] for row in ghz["rows"]):
        errors.append("ghz_aer_mismatch")

    campaign = campaign_status()
    if not campaign["complete"]:
        errors.append({"campaign": campaign})

    catalog = instance_catalog()
    jobs = job_rows()
    pubs = pub_rows()
    if len(jobs) != 6 or len(pubs) != 72:
        errors.append({"jobs": len(jobs), "pubs": len(pubs)})
    if sum(r["n_shots"] for r in pubs) != 73728:
        errors.append("shot_total")
    checks = checkpoints(pubs, catalog)
    expected_opt = {"D1": 23, "D2": 23, "D3": 23, "D4": 24, "D5": 23, "D6": 22}
    if {k: int(v) for k, v in checks["exact_optima"].items()} != expected_opt:
        errors.append({"optima": checks["exact_optima"]})
    expected_g = {"D1": 23, "D2": 23, "D3": 21, "D4": 24, "D5": 22, "D6": 22}
    if {k: int(v) for k, v in checks["greedy_incumbent_utilities"].items()} != expected_g:
        errors.append({"greedy": checks["greedy_incumbent_utilities"]})
    if checks["n_pools_with_optimum"] != 72:
        errors.append({"opt_pools": checks["n_pools_with_optimum"]})
    if checks["d4_p2_optimal_hit_mean"] is None or float(checks["d4_p2_optimal_hit_mean"]) >= (1.0 / 64.0):
        errors.append({"d4_p2": checks["d4_p2_optimal_hit_mean"]})
    if not checks["all_within_30s"]:
        errors.append({"elapsed": [checks["client_elapsed_min"], checks["client_elapsed_max"]]})
    if checks["p0_feasible_modal"] != 40:
        errors.append({"p0_feas": checks["p0_feasible_modal"]})
    for policy in ("P1", "P2", "P3"):
        if checks["guarded"][policy]["feasible_optima"] != 72:
            errors.append({policy: checks["guarded"][policy]})
        if checks["guarded"][policy]["improve_over_greedy"] != 24:
            errors.append({f"{policy}_improve": checks["guarded"][policy]})

    replay = replay_hardware_pools()
    sim_replay = replay_simulation_fixtures()
    grouped = grouped_rows(pubs)
    policies = flatten_policy_rows(pubs)
    example = worked_example(catalog)
    layers = p2_layer_note()

    compact_decisions = {
        "note": "Index only. Full records remain in decision-study/data/decisions.json.",
        "n_jobs": 6,
        "n_pubs": 72,
        "policies": ["P0", "P1", "P2", "P3"],
    }
    compact_policy_replay = {
        "note": "Index only. Full historical simulation replay remains in decision-study/data/derived/policy_replay.json.",
        "historical_parameter_source_defect": "p=2 prefix rows were labelled frozen_p1.",
        "n_simulation_fixtures": sim_replay["n_fixtures"],
    }

    write_json(tables / "job_level.json", jobs)
    write_csv(tables / "job_level.csv", jobs)
    write_json(tables / "pub_level.json", pubs)
    write_csv(tables / "pub_level.csv", [{k: v for k, v in r.items() if k != "policies"} for r in pubs])
    write_json(tables / "policy_level.json", policies)
    write_csv(tables / "policy_level.csv", policies)
    write_json(tables / "fixture_depth_summary.json", grouped)
    write_csv(tables / "fixture_depth_summary.csv", grouped)
    write_json(tables / "ghz_jobs.json", ghz)
    write_csv(tables / "ghz_jobs.csv", ghz["rows"])
    write_json(tables / "checkpoints.json", checks)
    write_json(tables / "worked_example.json", example)
    write_json(tables / "p2_layer_identity.json", layers)
    write_json(tables / "campaign_status.json", campaign)
    write_json(tables / "data_dictionary.json", DATA_DICTIONARY)
    write_json(tables / "decisions_index.json", compact_decisions)
    write_json(tables / "policy_replay_index.json", compact_policy_replay)
    write_json(tables / "post_collection_replay.json", {"compact": replay["compact"], "n_scenario_rows": replay["n_scenario_rows"], "n_deadline_rows": replay["n_deadline_rows"]})
    write_json(tables / "post_collection_replay_scenarios.json", replay["scenario_rows"])
    write_csv(tables / "post_collection_replay_deadlines.csv", replay["deadline_rows"])
    write_json(tables / "simulation_fixture_replay.json", sim_replay)

    feasibility_opt_hit(pubs, figures / "feasibility_and_optimal_hit")
    utility_panel(pubs, figures / "utility_vs_greedy_optimum")
    policy_panel(pubs, figures / "policy_selection")
    timing_panel(jobs, figures / "timing_and_usage")
    ghz_panel(ghz, figures / "legacy_ghz")
    architecture_diagram(figures / "architecture_and_provenance")

    isa_out = output / "isa_compact_checks.json"
    isa_script = REPO / "decision-study" / "tools" / "verify_isa.py"
    isa = subprocess.run(
        [sys.executable, str(isa_script), str(REPO / "decision-study"), "--output", str(isa_out)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    if isa.returncode != 0:
        errors.append({"verify_isa": isa.stderr[-2000:]})

    env = {
        "python": sys.version,
        "platform": platform.platform(),
        "executable": sys.executable,
    }
    try:
        import matplotlib
        import numpy
        import qiskit
        import qiskit_aer
        import qiskit_ibm_runtime
        import scipy

        env["packages"] = {
            "numpy": numpy.__version__,
            "qiskit": qiskit.__version__,
            "qiskit_ibm_runtime": qiskit_ibm_runtime.__version__,
            "qiskit_aer": qiskit_aer.__version__,
            "scipy": scipy.__version__,
            "matplotlib": matplotlib.__version__,
        }
    except Exception as exc:
        errors.append({"environment": str(exc)})

    manifest = {
        "analysis_version": ANALYSIS_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "command": "python tools/reproduce.py --output " + str(output),
        "protocol": protocol,
        "legacy_hashes": {"ok": legacy["ok"], "n_expected": legacy["n_expected"]},
        "preservation": preserved,
        "campaign": campaign,
        "environment": env,
        "errors": errors,
        "ok": not errors,
        "new_physical_qpu_jobs_submitted": 0,
        "historical_account_balance_note": "524 seconds remaining was observed at 2026-09-09T11:17:44.252800+00:00 and is not live availability.",
    }
    write_json(output / "analysis_manifest.json", manifest)

    report = _results_markdown(campaign, checks, ghz, layers, example)
    (reports / "RESULTS.md").write_text(report, encoding="utf-8")
    paper = PUBLICATION / "paper-support-notes.md"
    paper.parent.mkdir(parents=True, exist_ok=True)
    paper.write_text(
        "# Paper-support notes (generated from archived observations)\n\n"
        "These notes index generated tables and figures. They are not a manuscript rewrite.\n\n"
        f"- Campaign: {campaign['campaign_status']}; submission gate: {campaign['submission_gate']}.\n"
        f"- Exact optima: {checks['exact_optima']}.\n"
        f"- Greedy incumbents: {checks['greedy_incumbent_utilities']}.\n"
        f"- P0 feasible modal: {checks['p0_feasible_modal']}/72.\n"
        f"- P1–P3 feasible optima / greedy improve: {checks['guarded']}.\n"
        f"- D4 p=2 mean optimal-hit: {checks['d4_p2_optimal_hit_mean']}.\n"
        "- Tables: `results/publication/tables/`.\n"
        "- Figures: `results/publication/figures/`.\n"
        "- Replay is labelled `post_collection_policy_replay`, not a new IBM job.\n",
        encoding="utf-8",
    )

    if output != PUBLICATION:
        ensure_publication_dirs()
        _mirror(output, PUBLICATION)

    archive = write_research_archive(output / "dist")
    write_json(output / "dist" / "export_receipt.json", archive)
    if output != PUBLICATION:
        from shutil import copytree, copy2
        dest = PUBLICATION / "dist"
        if dest.exists():
            import shutil
            shutil.rmtree(dest)
        copytree(output / "dist", dest)

    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"ok": True, "output": str(output), "campaign_status": campaign["campaign_status"]}, indent=2))
    return 0


def _mirror(src: Path, dest: Path) -> None:
    import shutil

    for sub in ("tables", "figures", "reports"):
        target = dest / sub
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src / sub, target)
    shutil.copy2(src / "analysis_manifest.json", dest / "analysis_manifest.json")
    isa = src / "isa_compact_checks.json"
    if isa.is_file():
        shutil.copy2(isa, dest / "isa_compact_checks.json")


def _results_markdown(campaign, checks, ghz, layers, example) -> str:
    d4 = checks["d4_p2_optimal_hit_mean"]
    identity = [row["fixture"] for row in layers if row["second_layer_identity"]]
    return f"""# Generated results (archived-data reproduction)

Campaign status: **{campaign['campaign_status']}**. Submission gate remains **{campaign['submission_gate']}**.

## Decision study (six ibm_fez blocks)

- 72 PUB evaluations, 73,728 shots. These are six repeated 12-PUB blocks on six synthetic fixtures, not 72 independent organisations.
- Exact optima D1–D6: {checks['exact_optima']}.
- Greedy incumbents: {checks['greedy_incumbent_utilities']}.
- Every full 1,024-shot pool contained at least one optimum. That is expected for 1,024 draws from 64 states and is not a quantum-advantage claim.
- P0 modal string was feasible in {checks['p0_feasible_modal']}/72 PUBs. An `accept` label on P0 is unguarded.
- P1, P2 and P3 each selected a feasible optimum on all 72 unchanged-specification PUBs and improved on the greedy incumbent in 24/72 cases (D3 and D5). The other 48 already had an optimal incumbent. The three policies share samples.
- D4 p=2 mean optimal-hit fraction is {d4:.6f}, below uniform 1/64 = 0.015625.
- Identity second QAOA layer on fixtures {identity}. These are not demonstrations that extra layers help.
- Client receipt elapsed times ranged from {checks['client_elapsed_min']:.2f}s to {checks['client_elapsed_max']:.2f}s; all six returned within 30s. No deadline-timeout or specification-change event is established by these jobs.

## Legacy GHZ (20 jobs)

Sample mean Hellinger versus sampled Aer baselines: {ghz['fidelity_mean']}. Run 20 is the long queue outlier ({ghz['queue_max_seconds']} s). Exact-GHZ baselines are tabulated separately.

## Bitstring convention

{example['convention']} Worked D1 example `{example['displayed_ibm_style_little_endian_string']}` maps to {example['task_bits']} with utility {example['utility']}.

## Replay

Post-collection replay of the same hardware pools is labelled `analysis_type=post_collection_policy_replay`. It is not a new IBM job. P2 compares objective/constraint/variable payloads; a metadata-only `current_version` change is overwritten in `verifier.py` and does not by itself cause VERSION_MISMATCH.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline reproduction from archived observations.")
    parser.add_argument("--output", default=str(REPO / "build" / "reproduction"))
    args = parser.parse_args(argv)
    return run(Path(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
