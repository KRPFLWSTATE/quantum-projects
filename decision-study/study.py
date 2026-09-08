"""Command-line entry for the decision study. Hardware submit is opt-in only."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parent
if str(STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(STUDY_DIR))

from src.paths import (
    CONFIG_DIR,
    DERIVED_DIR,
    FIGURES_DIR,
    MANUSCRIPT_DIR,
    PROTOCOL_PATH,
    REPORTS_DIR,
    TABLES_DIR,
    COMMAND_LOG_PATH,
    ensure_directories,
)
from src.hashing import sha256_file, sha256_json, write_json_atomic
from src.fixtures import (
    EXPECTED_FEASIBLE_COUNTS,
    EXPECTED_OPTIMA,
    generate_simulation_fixtures,
    hardware_instances,
)
from src.model import penalty_scale, verify_encodings
from src.oracle import exact_summary
from src.classical import greedy_then_swaps, cardinality_k_then_conflict_check
from src.optimiser import optimize_all_hardware_fixtures
from src.legacy_audit import audit_legacy, snapshot_hashes, verify_hashes
from src.replay import replay_all
from src.budget import campaign_allowance, inspect_open_plan_usage
from src.ledger import load_ledger, save_ledger, default_ledger
from src.qaoa import independent_statevector_amplitudes, qiskit_statevector, qaoa_circuit
import numpy as np


def cmd_audit_legacy() -> dict:
    ensure_directories()
    result = audit_legacy()
    write_json_atomic(DERIVED_DIR / "legacy_audit.json", result)
    return result


def cmd_prepare() -> dict:
    ensure_directories()
    hashes = snapshot_hashes()
    instances = hardware_instances()
    fixture_checks = []
    for instance, expected_n, expected_u in zip(instances, EXPECTED_FEASIBLE_COUNTS, EXPECTED_OPTIMA):
        encodings = verify_encodings(instance)
        summary = exact_summary(instance)
        recomputed_n = summary["feasible_count"]
        recomputed_u = summary["optimum_utility"]
        fixture_checks.append(
            {
                "instance_id": instance.instance_id,
                "A": penalty_scale(instance),
                "encoding_ok": encodings["ok"],
                "feasible_count_recomputed": recomputed_n,
                "feasible_count_expected_check": expected_n,
                "feasible_match": recomputed_n == expected_n,
                "optimum_recomputed": recomputed_u,
                "optimum_expected_check": expected_u,
                "optimum_match": abs(float(recomputed_u) - expected_u) < 1e-9,
                "satisfiable": summary["satisfiable"],
            }
        )
    sim_fixtures = generate_simulation_fixtures()
    write_json_atomic(CONFIG_DIR / "simulation_fixtures.json", sim_fixtures)
    greedy_rows = []
    for instance in instances:
        greedy_rows.append({"instance_id": instance.instance_id, **greedy_then_swaps(instance)})
    write_json_atomic(DERIVED_DIR / "greedy_baselines.json", greedy_rows)
    qaoa_path = DERIVED_DIR / "qaoa_parameters.json"
    if qaoa_path.is_file():
        opt = json.loads(qaoa_path.read_text(encoding="utf-8"))
        print("Keeping frozen pre-repair QAOA parameters (no retune).", flush=True)
    else:
        print("Optimising QAOA parameters locally (statevector only)...", flush=True)
        opt = optimize_all_hardware_fixtures()
        write_json_atomic(DERIVED_DIR / "qaoa_parameters.json", opt)
    # Independent gate vs numpy check on D1 p=1 first start-ish point.
    d1 = instances[0]
    amps_np = independent_statevector_amplitudes(d1, [0.3], [0.4])
    amps_qk = qiskit_statevector(d1, [0.3], [0.4])
    overlap = abs(np.vdot(amps_np, amps_qk))
    write_json_atomic(
        DERIVED_DIR / "statevector_crosscheck.json",
        {"overlap_abs": float(overlap), "pass": float(overlap) > 1 - 1e-8},
    )
    ledger = load_ledger()
    if PROTOCOL_PATH.is_file():
        existing = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
        if existing.get("freeze_complete") and (
            ledger.get("jobs_submitted") or ledger.get("outstanding_job") or any(item.get("open") for item in ledger.get("reservations", []))
        ):
            protocol = existing
        else:
            from src.freeze import freeze_protocol

            protocol = freeze_protocol()
    else:
        from src.freeze import freeze_protocol

        protocol = freeze_protocol()
    write_json_atomic(CONFIG_DIR / "hardware_fixtures.json", {"fixtures": [inst.instance_id for inst in instances]})
    if not (
        ledger.get("jobs_submitted")
        or ledger.get("outstanding_job")
        or any(item.get("open") for item in ledger.get("reservations", []))
    ):
        protocol_id = protocol["protocol_id"]
        ledger = default_ledger()
        ledger["protocol_id"] = protocol_id
        save_ledger(ledger)
    else:
        ledger["protocol_id"] = ledger.get("protocol_id") or protocol["protocol_id"]
        save_ledger(ledger)
    return {
        "fixture_checks": fixture_checks,
        "all_fixtures_match_expected": all(row["feasible_match"] and row["optimum_match"] for row in fixture_checks),
        "simulation_fixtures_kept": len(sim_fixtures["kept"]),
        "simulation_fixtures_rejected": len(sim_fixtures["rejected"]),
        "statevector_overlap": float(overlap),
        "protocol_hash": protocol["protocol_hash"],
        "legacy_hash_count": len(hashes),
        "greedy": greedy_rows,
    }


def cmd_validate() -> dict:
    ensure_directories()
    import unittest

    loader = unittest.TestLoader()
    suite = loader.discover(str(Path(__file__).resolve().parent / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    out = {
        "tests_run": result.testsRun,
        "failures": [(str(t), str(e)) for t, e in result.failures],
        "errors": [(str(t), str(e)) for t, e in result.errors],
        "ok": result.wasSuccessful(),
    }
    write_json_atomic(DERIVED_DIR / "validate_unittests.json", out)
    replay = replay_all()
    write_json_atomic(DERIVED_DIR / "policy_replay.json", replay)
    hashes = json.loads((Path(__file__).resolve().parent / "data/preservation/legacy_sha256.json").read_text())
    hash_check = verify_hashes(hashes)
    out["hash_check"] = hash_check
    from src.sampler_api import inspect_sampler_options
    from src.analysis import write_analysis_tables
    from src.compile import compile_all_fixtures
    from src.usage_estimate import estimate_block_usage
    from src.provenance import retrieve_legacy_jobs

    out["sampler_options"] = inspect_sampler_options()
    qaoa_path = DERIVED_DIR / "qaoa_parameters.json"
    if qaoa_path.is_file():
        qaoa = json.loads(qaoa_path.read_text())
        out["analysis"] = write_analysis_tables(qaoa)
        print("Compiling ISA circuits on pinned backend (no Sampler.run)...", flush=True)
        try:
            compile_summary = compile_all_fixtures(qaoa)
            out["compile"] = {
                "pinned_backend": compile_summary.get("pinned_backend"),
                "structural_ok": compile_summary.get("structural_ok"),
                "compact_ok": compile_summary.get("compact_ok"),
                "n_circuits": len(compile_summary.get("rows", [])),
            }
            from qiskit_ibm_runtime import QiskitRuntimeService

            backend = QiskitRuntimeService().backend(compile_summary["pinned_backend"])
            out["usage_estimate"] = estimate_block_usage(backend, compile_summary["rows"])
        except Exception as exc:
            out["compile"] = {"error": f"{type(exc).__name__}:{exc}", "blocked": True}
        print("Retrieving supplementary provenance for existing GHZ jobs (no new jobs)...", flush=True)
        out["legacy_supplementary"] = retrieve_legacy_jobs()
    from src.freeze import freeze_protocol

    out["protocol_freeze"] = {"protocol_hash": freeze_protocol().get("protocol_hash")}
    write_json_atomic(DERIVED_DIR / "validate.json", out)
    return out


def cmd_status() -> dict:
    ensure_directories()
    from src.readiness import engineering_status

    usage = inspect_open_plan_usage()
    write_json_atomic(DERIVED_DIR / "usage_probe.json", usage)
    status = engineering_status(live_usage=usage)
    protocol = json.loads(PROTOCOL_PATH.read_text()) if PROTOCOL_PATH.is_file() else None
    ledger = load_ledger()
    return {
        "status": status["engineering_status"],
        "blockers": status["blockers"],
        "protocol": protocol,
        "ledger_jobs_submitted": ledger.get("jobs_submitted"),
        "outstanding_job": ledger.get("outstanding_job"),
        "usage_probe": usage,
        "campaign_allowance": status["allowance"],
        "compile_ok": "COMPILE_STRUCTURAL_FAILED" not in status["blockers"] and "COMPILE_SUMMARY_MISSING" not in status["blockers"],
        "pinned_backend": status.get("pinned_backend"),
        "ready_for_first_hardware": status.get("ready_for_first_hardware"),
        "new_qpu_jobs_this_session": 0,
        "NEW_QPU_JOBS_SUBMITTED": 0,
        "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0,
        "hardware_submit_enabled": False,
    }


def cmd_run_next(hardware: bool) -> dict:
    if not hardware:
        return {"blocked": True, "ok": False, "reason": "run-next without --hardware is a no-op", "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0}
    from src.runner import authorise_hardware_cli, dispatch_block, physical_submit_allowed

    authorise_hardware_cli()
    if not physical_submit_allowed():
        return {
            "blocked": True,
            "ok": False,
            "reason": "AWAITING_USER_RUN_COMMAND",
            "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0,
        }
    result = dispatch_block(physical=True)
    if result.get("ok") and result.get("NEW_PHYSICAL_QPU_JOBS_SUBMITTED"):
        try:
            cmd_report()
            cmd_export()
        except Exception as exc:
            result["post_complete_error"] = f"{type(exc).__name__}:{exc}"
            result["resubmit"] = False
    return result


def cmd_resume() -> dict:
    from src.runner import resume_block

    return resume_block()


def cmd_report() -> dict:
    from src.report import write_reports

    return write_reports()


def cmd_export() -> dict:
    from src.packet import export_packet

    return export_packet()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Policy-controlled quantum decision study")
    parser.add_argument(
        "command",
        choices=["audit-legacy", "prepare", "validate", "status", "run-next", "resume", "report", "export-return-packet"],
    )
    parser.add_argument("--hardware", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "run-next" and args.hardware:
        result = cmd_run_next(True)
        print(json.dumps(result, indent=2, default=str)[:20000])
        if result.get("blocked"):
            return 2
        return 0 if result.get("ok") else 1
    commands = {
        "audit-legacy": cmd_audit_legacy,
        "prepare": cmd_prepare,
        "validate": cmd_validate,
        "status": cmd_status,
        "run-next": lambda: cmd_run_next(False),
        "resume": cmd_resume,
        "report": cmd_report,
        "export-return-packet": cmd_export,
    }
    try:
        result = commands[args.command]()
        line = json.dumps({"command": args.command, "ok": True, "keys": list(result) if isinstance(result, dict) else type(result).__name__}, default=str)
        COMMAND_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with COMMAND_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        print(json.dumps(result, indent=2, default=str)[:20000])
        return 0 if not (isinstance(result, dict) and result.get("ok") is False) else 1
    except Exception:
        COMMAND_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with COMMAND_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"command": args.command, "ok": False, "traceback": traceback.format_exc()[-4000:]}) + "\n")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
