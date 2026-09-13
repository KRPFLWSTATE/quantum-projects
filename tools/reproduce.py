#!/usr/bin/env python3
"""Offline archived-data reproduction. No IBM credentials or QPU submission."""
from __future__ import annotations

import argparse
import json
import shutil
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
from publication.classical_controls import run_classical_controls  # noqa: E402
from publication.dictionary import DATA_DICTIONARY  # noqa: E402
from publication.export import missing_inventory, write_research_archive  # noqa: E402
from publication.figures import (  # noqa: E402
    architecture_diagram,
    fair_pool_panel,
    feasibility_opt_hit,
    ghz_panel,
    policy_panel,
    timing_panel,
    utility_panel,
)
from publication.ghz import collect_ghz_jobs  # noqa: E402
from publication.hashes import verify_legacy_hashes, verify_pre_manifest, verify_protocol  # noqa: E402
from publication.ibm_guard import install_tripwires  # noqa: E402
from publication.metrics import checkpoints, flatten_policy_rows, grouped_rows, instance_catalog, job_rows, p2_layer_note, pub_rows, worked_example  # noqa: E402
from publication.paths import PUBLICATION, REPO_ROOT, assert_safe_output, is_publication_output, validate_output_root  # noqa: E402
from publication.provenance import analysis_provenance, hash_path_list  # noqa: E402
from publication.replay_adapter import run_replay_adapter  # noqa: E402
from publication.replay_analysis import replay_simulation_fixtures  # noqa: E402
from publication.tables import write_json, write_csv  # noqa: E402


HISTORICAL_PUBLICATION_BACKUP = REPO / "archive" / "follow-up-2026-09-09" / "results-publication-before-refresh"
PUBLICATION_BACKUP_ROOT = REPO / "archive" / "publication-backups"
REQUIRED_GENERATION = (
    "tables",
    "figures",
    "reports",
    "analysis_manifest.json",
    "isa_compact_checks.json",
)
PROTECTED_HASH_TARGETS = [
    REPO / "decision-study" / "config" / "protocol.json",
    REPO / "decision-study" / "study.py",
    REPO / "decision-study" / "data" / "campaign_ledger.json",
    REPO / "decision-study" / "data" / "decisions.json",
]


def _write_diagnostics(output: Path, payload: dict) -> None:
    diag = output / "diagnostics"
    diag.mkdir(parents=True, exist_ok=True)
    assert_safe_output(diag / "errors.json")
    write_json(diag / "errors.json", payload)


def _validate(errors: list) -> dict:
    protocol = verify_protocol()
    if not protocol["ok"]:
        errors.append({"protocol": protocol})
    legacy = verify_legacy_hashes()
    if not legacy["ok"]:
        errors.append({"legacy": legacy})
    preserved = verify_pre_manifest()
    if not preserved["ok"]:
        errors.append({"preservation": preserved})
    missing = missing_inventory()
    if missing:
        errors.append({"export_inventory_missing": missing})
    return {"protocol": protocol, "legacy": legacy, "preserved": preserved}


def run(output: Path, *, refresh_publication: bool = False) -> int:
    install_tripwires()
    output = output.resolve()
    try:
        validate_output_root(output)
    except ValueError as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 1

    hashes_before = hash_path_list(PROTECTED_HASH_TARGETS)
    errors: list = []
    checks_pack = _validate(errors)
    if errors:
        _write_diagnostics(output, {"ok": False, "errors": errors, "hashes_before": hashes_before})
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1

    ghz = collect_ghz_jobs()
    if ghz["n_jobs"] != 20:
        errors.append({"ghz_count": ghz["n_jobs"]})
    if any(not row["aer_matches_archive"] for row in ghz["rows"]):
        errors.append("ghz_aer_mismatch")

    campaign = campaign_status()
    if not campaign["complete"]:
        errors.append({"campaign": campaign})
    for row in job_rows():
        if not row.get("backend"):
            errors.append({"missing_backend": row.get("job_id")})
        if row.get("client_elapsed_seconds") is None:
            errors.append({"missing_elapsed": row.get("job_id")})

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

    if errors:
        _write_diagnostics(output, {"ok": False, "errors": errors})
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1

    classical = run_classical_controls()
    replay = run_replay_adapter()
    sim_replay = replay_simulation_fixtures()
    grouped = grouped_rows(pubs)
    policies = flatten_policy_rows(pubs)
    example = worked_example(catalog)
    layers = p2_layer_note()

    stage = output / ".generation-stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    try:
        isa_out = stage / "isa_compact_checks.json"
        isa_script = REPO / "decision-study" / "tools" / "verify_isa.py"
        isa = subprocess.run(
            [sys.executable, str(isa_script), str(REPO / "decision-study"), "--output", str(isa_out)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
        )
        if isa.returncode != 0:
            errors.append({"verify_isa": (isa.stderr or isa.stdout)[-2000:]})
            _write_diagnostics(output, {"ok": False, "errors": errors})
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1

        hashes_after = hash_path_list(PROTECTED_HASH_TARGETS)
        if hashes_after != hashes_before:
            errors.append({"protected_hash_drift": {"before": hashes_before, "after": hashes_after}})
            _write_diagnostics(output, {"ok": False, "errors": errors})
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1

        tables = stage / "tables"
        figures = stage / "figures"
        reports = stage / "reports"
        for path in (tables, figures, reports):
            path.mkdir(parents=True, exist_ok=True)
            assert_safe_output(path / ".keep")

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
        write_json(tables / "classical_fair_pools.json", classical)
        write_csv(tables / "classical_fair_pools.csv", classical["fixture_prefix_rows"])
        write_json(tables / "classical_policy_prefix.json", classical["policy_prefix_rows"])
        write_json(tables / "replay_adapter_compact.json", {k: replay[k] for k in replay if k != "drill_rows"})
        write_json(tables / "replay_adapter_drill.json", replay["drill_rows"])
        write_json(tables / "simulation_fixture_replay.json", sim_replay)

        feasibility_opt_hit(pubs, figures / "feasibility_and_optimal_hit")
        utility_panel(pubs, figures / "utility_vs_greedy_optimum")
        policy_panel(pubs, figures / "policy_selection")
        timing_panel(jobs, figures / "timing_and_usage")
        ghz_panel(ghz, figures / "legacy_ghz")
        architecture_diagram(figures / "architecture_and_provenance")
        fair_pool_panel(classical["fixture_prefix_rows"], figures / "fair_classical_pools")

        generated_utc = datetime.now(timezone.utc).isoformat()
        manifest = analysis_provenance(
            command="python tools/reproduce.py --output " + str(output),
            extra={
                "protocol": checks_pack["protocol"],
                "legacy_hashes": {"ok": checks_pack["legacy"]["ok"], "n_expected": checks_pack["legacy"]["n_expected"]},
                "preservation": checks_pack["preserved"],
                "campaign": campaign,
                "errors": errors,
                "ok": not errors,
                "new_physical_qpu_jobs_submitted": 0,
                "hashes_before": hashes_before,
                "hashes_after": hashes_after,
                "refresh_publication": refresh_publication,
                "hardware_collection_date": "2026-09-09",
                "analysis_generated_utc": generated_utc,
                "paper_cited_commit": "0abf41f2e9b256c94cd056e55ec8f9fc8766faec",
            },
        )
        write_json(stage / "analysis_manifest.json", manifest)

        report = _results_markdown(campaign, checks, ghz, layers, example, classical, replay, generated_utc)
        (reports / "RESULTS.md").write_text(report, encoding="utf-8")
        (reports / "CURRENT_REPORT.md").write_text(
            f"# CURRENT generated report\n\n"
            f"Analysis generated: {generated_utc} (`{ANALYSIS_VERSION}`). "
            "Hardware collection date remains 2026-09-09. "
            "`decision-study/reports/CHATGPT_RETURN_REPORT.md` is historical.\n\n"
            + report,
            encoding="utf-8",
        )
        (reports / "SOURCE_TO_OUTPUT_INDEX.json").write_text(
            json.dumps(
                {
                    "analysis_version": ANALYSIS_VERSION,
                    "generator": "tools/reproduce.py",
                    "hardware_collection_date": "2026-09-09",
                    "analysis_generated_utc": generated_utc,
                    "current_outputs": list(REQUIRED_GENERATION),
                    "current_tables_from_generator": [
                        "job_level",
                        "pub_level",
                        "policy_level",
                        "fixture_depth_summary",
                        "ghz_jobs",
                        "checkpoints",
                        "worked_example",
                        "p2_layer_identity",
                        "campaign_status",
                        "data_dictionary",
                        "classical_fair_pools",
                        "classical_policy_prefix",
                        "replay_adapter_compact",
                        "replay_adapter_drill",
                        "simulation_fixture_replay",
                    ],
                    "superseded_not_regenerated": "archive/superseded-analysis/2026-09-09-post-collection-replay/",
                    "static_supporting_identified": [
                        "archive/superseded-analysis/2026-09-09-post-collection-replay/",
                        "archive/historical-exports/CHECKSUMS.md",
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (reports / "paper-support-notes.md").write_text(
            "# Paper-support notes\n\nGenerated under the requested --output directory only.\n\n"
            f"- Analysis version: {ANALYSIS_VERSION}\n"
            f"- Analysis generated UTC: {generated_utc}\n"
            f"- Hardware collection date: 2026-09-09\n"
            f"- Paper-cited evidence snapshot: 0abf41f2e9b256c94cd056e55ec8f9fc8766faec\n"
            f"- Campaign: {campaign['campaign_status']}; gate: {campaign['submission_gate']}\n"
            f"- D4 p=2 mean optimal-hit: {checks['d4_p2_optimal_hit_mean']}\n"
            f"- Replay reconcile differences: {replay['n_reconcile_differences']}\n",
            encoding="utf-8",
        )
        _promote_stage(stage, output)
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)

    archive = write_research_archive(output / "dist", generated_root=output)
    write_json(output / "dist" / "export_receipt.json", archive)

    if refresh_publication:
        _refresh_publication(output)

    print(json.dumps({"ok": True, "output": str(output), "campaign_status": campaign["campaign_status"]}, indent=2))
    return 0


def _promote_stage(stage: Path, output: Path) -> None:
    for name in REQUIRED_GENERATION:
        src = stage / name
        dest = output / name
        if not src.exists():
            raise RuntimeError(f"incomplete staged generation missing {name}")
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        shutil.move(str(src), str(dest))


def _copy_generation(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True)
    for name in REQUIRED_GENERATION:
        item = src / name
        if not item.exists():
            raise ValueError(f"incomplete generation missing {name}")
        target = dest / name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def _refresh_publication(src: Path) -> None:
    src = src.resolve()
    if is_publication_output(src):
        raise ValueError("refresh source must be a separate isolated generation, not results/publication")
    for name in REQUIRED_GENERATION:
        if not (src / name).exists():
            raise ValueError(f"refusing refresh; source missing {name}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    PUBLICATION_BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    backup = PUBLICATION_BACKUP_ROOT / f"results-publication-before-{stamp}"
    previous = None
    if PUBLICATION.exists():
        shutil.copytree(PUBLICATION, backup)
        previous = backup
        (backup / "BACKUP_PROVENANCE.json").write_text(
            json.dumps(
                {
                    "created_utc": stamp,
                    "source_generation": str(src),
                    "historical_2026_09_09_backup_untouched": str(HISTORICAL_PUBLICATION_BACKUP),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    staged = PUBLICATION.parent / f"publication.next.{stamp}"
    if staged.exists():
        shutil.rmtree(staged)
    try:
        _copy_generation(src, staged)
        old = PUBLICATION.parent / f"publication.old.{stamp}"
        if PUBLICATION.exists():
            PUBLICATION.rename(old)
        staged.rename(PUBLICATION)
        if old.exists():
            shutil.rmtree(old)
    except Exception:
        if staged.exists():
            shutil.rmtree(staged, ignore_errors=True)
        if previous is not None and previous.exists() and not PUBLICATION.exists():
            shutil.copytree(previous, PUBLICATION)
        raise


def _results_markdown(campaign, checks, ghz, layers, example, classical, replay, generated_utc: str) -> str:
    d4 = checks["d4_p2_optimal_hit_mean"]
    identity = [row["fixture"] for row in layers if row["second_layer_identity"]]
    return f"""# Generated results (archived-data reproduction)

Analysis generated: {generated_utc} (`{ANALYSIS_VERSION}`). Hardware collection date: 2026-09-09. This generation timestamp is not the collection date.

Campaign status: **{campaign['campaign_status']}**. Submission gate remains **{campaign['submission_gate']}**.

## Decision study (six ibm_fez blocks)

- 72 PUB evaluations, 73,728 shots as six clustered repeats, not 72 organisations.
- Exact optima D1–D6: {checks['exact_optima']}.
- Greedy incumbents: {checks['greedy_incumbent_utilities']}.
- Every full 1,024-shot hardware pool contained at least one optimum. For independent draws from a fixed distribution the probability is 1-(1-p_opt)^m, not a consequence of the 64-state support size alone. Uniform analytical values are in `checkpoints.json` under `uniform_opt_containment_1024`.
- P0 modal string was feasible in {checks['p0_feasible_modal']}/72 PUBs. An `accept` label on P0 is unguarded and is not a safety result.
- P1, P2 and P3 each selected a feasible optimum on all 72 unchanged-specification PUBs and improved on the greedy incumbent in 24/72 cases (D3 and D5).
- D4 p=2 mean optimal-hit fraction is {d4:.6f}, below uniform 1/64 = 0.015625.
- Identity second QAOA layer on fixtures {identity}.
- Client receipt elapsed times ranged from {checks['client_elapsed_min']:.2f}s to {checks['client_elapsed_max']:.2f}s.

## Fair classical controls (post-collection)

Plan `tools/publication/plans/classical_comparison_plan.json` is dated after hardware collection and is not preregistered. Classical pools are reused across p=1/p=2 panels. Monte Carlo n={classical['plan']['n_monte_carlo_replications']}.

## Replay

Adapter rows: {replay['n_drill_rows']}. Unchanged-spec reconcile differences: {replay['n_reconcile_differences']}. P2 metadata-only accepts: {replay['p2_metadata_only_accept_count']}. {replay['p2_contract']}

## Legacy GHZ (20 jobs)

Sample mean Hellinger versus sampled Aer baselines: {ghz['fidelity_mean']}. Run 20 is the long queue outlier ({ghz['queue_max_seconds']} s).

## Bitstring convention

{example['convention']} Worked D1 example `{example['displayed_ibm_style_little_endian_string']}` maps to {example['task_bits']} with utility {example['utility']}.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline reproduction from archived observations.")
    parser.add_argument("--output", default=str(REPO / "build" / "reproduction"))
    parser.add_argument(
        "--refresh-publication",
        action="store_true",
        help="After a successful isolated rebuild, copy outputs into results/publication (not the default).",
    )
    args = parser.parse_args(argv)
    return run(Path(args.output), refresh_publication=args.refresh_publication)


if __name__ == "__main__":
    raise SystemExit(main())
