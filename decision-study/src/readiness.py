"""Shared engineering-readiness function for CLI, report, and dispatch."""

from __future__ import annotations

import json
from pathlib import Path

from .budget import campaign_allowance, inspect_open_plan_usage
from .ledger import can_submit, load_ledger
from .legacy_audit import verify_hashes
from .paths import DERIVED_DIR, HASHES_PATH, PROTOCOL_PATH, SRC_DIR, STUDY_ROOT
from .hashing import sha256_file, sha256_json


REQUIRED_ISA = [f"D{i}_p{p}_isa.qpy" for i in range(1, 7) for p in (1, 2)]


def _equivalence_record() -> dict:
    path = DERIVED_DIR / "circuit_equivalence.json"
    if not path.is_file():
        return {"present": False, "all_pass": False}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "present": True,
        "all_pass": bool(data.get("all_pass")),
        "n_circuits": data.get("n_circuits"),
        "maximum_error": data.get("maximum_error"),
        "tolerance": data.get("tolerance"),
    }


def engineering_status(*, live_usage: dict | None = None) -> dict:
    blockers = []
    tests = {}
    tests_path = DERIVED_DIR / "validate_unittests.json"
    if not tests_path.is_file():
        blockers.append("UNIT_TESTS_RECORD_MISSING")
    else:
        tests = json.loads(tests_path.read_text())
        if tests.get("ok") is not True:
            blockers.append("UNIT_TESTS_FAILING")
    compile_path = DERIVED_DIR / "compile" / "isa_summary.json"
    compile_ok = False
    if compile_path.is_file():
        compile_summary = json.loads(compile_path.read_text())
        compile_ok = bool(compile_summary.get("structural_ok") and compile_summary.get("compact_ok"))
        if not compile_ok:
            blockers.append("COMPILE_STRUCTURAL_FAILED")
        qpy_dir = DERIVED_DIR / "compile" / "qpy"
        missing = [name for name in REQUIRED_ISA if not (qpy_dir / name).is_file()]
        if missing:
            blockers.append("ISA_QPY_MISSING")
        rows = {(row["instance_id"], int(row["p"])): row for row in compile_summary.get("rows", [])}
        for name in REQUIRED_ISA:
            inst, rest = name.split("_", 1)
            depth = int(rest[1])
            row = rows.get((inst, depth))
            if not row:
                blockers.append("ISA_SUMMARY_ROW_MISSING")
                break
            path = STUDY_ROOT / row["isa_qpy"]
            if path.is_file() and row.get("isa_qpy_sha256") and sha256_file(path) != row["isa_qpy_sha256"]:
                blockers.append("ISA_HASH_MISMATCH")
                break
    else:
        blockers.append("COMPILE_SUMMARY_MISSING")
    equiv = _equivalence_record()
    if not equiv["present"]:
        blockers.append("CIRCUIT_EQUIVALENCE_MISSING")
    elif equiv["all_pass"] is not True or equiv.get("n_circuits") != 12:
        blockers.append("CIRCUIT_EQUIVALENCE_FAILED")
    hashes = json.loads(HASHES_PATH.read_text()) if HASHES_PATH.is_file() else {}
    if hashes:
        check = verify_hashes(hashes)
        if not check.get("ok"):
            blockers.append("LEGACY_HASH_MISMATCH")
    else:
        blockers.append("LEGACY_HASH_BASELINE_MISSING")
    if not PROTOCOL_PATH.is_file():
        blockers.append("PROTOCOL_MISSING")
    else:
        protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
        body = {k: v for k, v in protocol.items() if k != "protocol_hash"}
        if protocol.get("protocol_hash") != sha256_json(body):
            blockers.append("PROTOCOL_HASH_MISMATCH")
        if not protocol.get("freeze_complete"):
            blockers.append("PROTOCOL_NOT_FROZEN")
        recorded_code = protocol.get("code_sha256") or {}
        for rel, expected in recorded_code.items():
            path = STUDY_ROOT / rel
            if not path.is_file() or sha256_file(path) != expected:
                blockers.append("CODE_HASH_MISMATCH")
                break
        recorded_params = protocol.get("qaoa_parameters_sha256")
        param_path = DERIVED_DIR / "qaoa_parameters.json"
        if recorded_params and (not param_path.is_file() or sha256_file(param_path) != recorded_params):
            blockers.append("PARAMETER_HASH_MISMATCH")
        recorded_eq = protocol.get("circuit_equivalence_sha256")
        eq_path = DERIVED_DIR / "circuit_equivalence.json"
        if recorded_eq and (not eq_path.is_file() or sha256_file(eq_path) != recorded_eq):
            blockers.append("EQUIVALENCE_HASH_MISMATCH")
        recorded_isa = protocol.get("isa_qpy_sha256") or {}
        for name, expected in recorded_isa.items():
            path = DERIVED_DIR / "compile" / "qpy" / name
            if not path.is_file() or sha256_file(path) != expected:
                blockers.append("FROZEN_ISA_HASH_MISMATCH")
                break
        tests_hash = protocol.get("validate_unittests_sha256")
        if tests_hash and tests_path.is_file() and sha256_file(tests_path) != tests_hash:
            blockers.append("TEST_RECORD_HASH_MISMATCH")
    usage = live_usage if live_usage is not None else inspect_open_plan_usage()
    remaining = usage.get("remaining_seconds")
    if remaining is None:
        blockers.append("BALANCE_UNRESOLVED")
    allowance = campaign_allowance(remaining)
    if allowance.get("blocked"):
        blockers.append(str(allowance.get("reason") or "BUDGET"))
    ledger = load_ledger()
    submit_ok, submit_reason = can_submit(ledger, remaining)
    if not submit_ok:
        blockers.append(submit_reason)
    estimate_path = DERIVED_DIR / "usage_estimate.json"
    if not estimate_path.is_file():
        blockers.append("DURATION_ESTIMATE_MISSING")
        estimate = {}
    else:
        estimate = json.loads(estimate_path.read_text())
    if estimate.get("exceeds_45s_cap") or (estimate.get("block_estimate_seconds") is not None and float(estimate["block_estimate_seconds"]) > 45):
        blockers.append("DURATION_ESTIMATE_EXCEEDS_45S")
    if estimate.get("error"):
        blockers.append("DURATION_ESTIMATE_ERROR")
    runner_src = (SRC_DIR / "hardware.py").read_text(encoding="utf-8")
    runner_ok = "SamplerV2(mode=backend, options=options)" in runner_src.replace(" ", "") or "SamplerV2(mode=backend, options=options)" in runner_src
    if "run_physical_block" not in runner_src:
        blockers.append("PHYSICAL_RUNNER_MISSING")
    research = {"novelty": "unresolved", "publication_ready": False}
    if blockers:
        label = "BLOCKED"
    else:
        label = "READY_FOR_FIRST_HARDWARE"
    code_hash = sha256_file(SRC_DIR / "runner.py")
    protocol = json.loads(PROTOCOL_PATH.read_text()) if PROTOCOL_PATH.is_file() else {}
    return {
        "engineering_status": label,
        "ready_for_first_hardware": label == "READY_FOR_FIRST_HARDWARE",
        "blockers": blockers,
        "tests": {"ok": tests.get("ok"), "tests_run": tests.get("tests_run")},
        "allowance": allowance,
        "submit_gate": {"ok": submit_ok, "reason": submit_reason},
        "equivalence": equiv,
        "estimate_seconds": estimate.get("block_estimate_seconds"),
        "pinned_backend": None if not compile_path.is_file() else json.loads(compile_path.read_text()).get("pinned_backend"),
        "protocol_hash": protocol.get("protocol_hash"),
        "runner_hash": code_hash,
        "runner_implemented": runner_ok,
        "usage": {k: v for k, v in usage.items() if k != "service"},
        "research": research,
        "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0,
    }
