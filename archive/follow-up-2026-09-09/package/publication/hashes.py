from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from .paths import LEGACY_HASHES, PRE_MANIFEST, PROTOCOL, REPO_ROOT, SRC_DIR, STUDY_ROOT

sys.path.insert(0, str(STUDY_ROOT))
from src.hashing import sha256_file, sha256_json  # type: ignore  # noqa: E402


def protocol_self_hash(protocol: dict[str, Any]) -> str:
    body = {k: v for k, v in protocol.items() if k != "protocol_hash"}
    return sha256_json(body)


def load_protocol() -> dict[str, Any]:
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def verify_protocol() -> dict[str, Any]:
    protocol = load_protocol()
    expected = protocol.get("protocol_hash")
    recomputed = protocol_self_hash(protocol)
    code_ok = True
    mismatches = []
    for rel, digest in (protocol.get("code_sha256") or {}).items():
        path = STUDY_ROOT / rel
        current = sha256_file(path) if path.is_file() else None
        if current != digest:
            code_ok = False
            mismatches.append({"path": rel, "expected": digest, "current": current})
    isa_ok = True
    for name, digest in (protocol.get("isa_qpy_sha256") or {}).items():
        path = STUDY_ROOT / "data" / "derived" / "compile" / "qpy" / name
        current = sha256_file(path) if path.is_file() else None
        if current != digest:
            isa_ok = False
            mismatches.append({"path": str(path.relative_to(REPO_ROOT)), "expected": digest, "current": current})
    param_path = STUDY_ROOT / "data" / "derived" / "qaoa_parameters.json"
    param_ok = sha256_file(param_path) == protocol.get("qaoa_parameters_sha256")
    eq_path = STUDY_ROOT / "data" / "derived" / "circuit_equivalence.json"
    eq_ok = sha256_file(eq_path) == protocol.get("circuit_equivalence_sha256")
    return {
        "protocol_hash_recorded": expected,
        "protocol_hash_recomputed": recomputed,
        "protocol_hash_ok": expected == recomputed,
        "code_ok": code_ok,
        "isa_ok": isa_ok,
        "parameters_ok": param_ok,
        "equivalence_ok": eq_ok,
        "mismatches": mismatches,
        "ok": expected == recomputed and code_ok and isa_ok and param_ok and eq_ok,
    }


def verify_legacy_hashes() -> dict[str, Any]:
    expected = json.loads(LEGACY_HASHES.read_text(encoding="utf-8"))
    changed = {}
    missing = []
    for rel, digest in expected.items():
        path = REPO_ROOT / rel
        if not path.is_file():
            missing.append(rel)
            continue
        current = sha256_file(path)
        if current != digest:
            changed[rel] = {"expected": digest, "current": current}
    return {
        "n_expected": len(expected),
        "ok": not changed and not missing,
        "changed": changed,
        "missing": missing,
    }


PROTECTED_PREFIXES = (
    "dba-qpu-run/results/",
    "decision-study/config/protocol.json",
    "decision-study/config/hardware_fixtures.json",
    "decision-study/config/simulation_fixtures.json",
    "decision-study/src/",
    "decision-study/study.py",
    "decision-study/data/raw/",
    "decision-study/data/attempts/",
    "decision-study/data/campaign_ledger.json",
    "decision-study/data/decisions.json",
    "decision-study/data/provider_jobs.json",
    "decision-study/data/preservation/legacy_sha256.json",
    "decision-study/data/derived/protocol_freeze.json",
    "decision-study/data/derived/qaoa_parameters.json",
    "decision-study/data/derived/circuit_equivalence.json",
    "decision-study/data/derived/compile/",
    "decision-study/data/derived/greedy_baselines.json",
    "decision-study/data/derived/backend_pin.json",
    "decision-study/data/derived/validate_unittests.json",
    "decision-study/data/derived/policies_",
    "decision-study/data/derived/last_dispatch.json",
    "decision-study/data/derived/hardware_archive_analysis.json",
)


def verify_pre_manifest() -> dict[str, Any]:
    if not PRE_MANIFEST.is_file():
        return {"ok": False, "error": "pre_housekeeping_manifest missing"}
    manifest = json.loads(PRE_MANIFEST.read_text(encoding="utf-8"))
    changed = []
    missing = []
    checked = 0
    for entry in manifest.get("files") or []:
        rel = entry["path"]
        if not any(rel.startswith(prefix) or rel == prefix.rstrip("/") for prefix in PROTECTED_PREFIXES):
            continue
        checked += 1
        path = REPO_ROOT / rel
        if not path.is_file():
            missing.append(rel)
            continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != entry["sha256"] or len(data) != int(entry["bytes"]):
            changed.append({"path": rel, "expected": entry["sha256"], "current": digest})
    return {
        "ok": not changed and not missing,
        "n_manifest_files": len(manifest.get("files") or []),
        "n_protected_checked": checked,
        "changed": changed,
        "missing": missing,
        "manifest_excluded_from_self_hash": True,
        "note": "Public README/CITATION copies were snapshotted then updated; protected experiment bytes are the check.",
    }


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
