"""Freeze protocol artefacts without retuning QAOA after the pre-repair parameter file."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .hashing import sha256_file, sha256_json, write_json_atomic
from .paths import DERIVED_DIR, PROTOCOL_PATH, SRC_DIR, STUDY_ROOT


PRE_REPAIR_NOTE = (
    "Frozen QAOA parameters are the saved pre-repair Powell selections (scipy result.x). "
    "Callback-best retention is implemented in the optimiser but was not used to replace this frozen set."
)


def freeze_protocol() -> dict:
    from .ledger import load_ledger

    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8")) if PROTOCOL_PATH.is_file() else {}
    ledger = load_ledger()
    if protocol.get("freeze_complete") and (ledger.get("jobs_submitted") or ledger.get("outstanding_job")):
        return protocol
    notes = list(protocol.get("notes") or [])
    if PRE_REPAIR_NOTE not in notes:
        notes.append(PRE_REPAIR_NOTE)
    qpy_dir = DERIVED_DIR / "compile" / "qpy"
    isa_files = sorted(qpy_dir.glob("*_isa.qpy")) if qpy_dir.is_dir() else []
    code_files = sorted(SRC_DIR.glob("*.py")) + [STUDY_ROOT / "study.py"]
    freeze = {
        **protocol,
        "notes": notes,
        "parameter_selection": "pre_repair_powell_result_x",
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "isa_qpy_sha256": {path.name: sha256_file(path) for path in isa_files},
        "code_sha256": {str(path.relative_to(STUDY_ROOT)): sha256_file(path) for path in code_files if path.is_file()},
        "qaoa_parameters_sha256": sha256_file(DERIVED_DIR / "qaoa_parameters.json") if (DERIVED_DIR / "qaoa_parameters.json").is_file() else None,
        "circuit_equivalence_sha256": sha256_file(DERIVED_DIR / "circuit_equivalence.json") if (DERIVED_DIR / "circuit_equivalence.json").is_file() else None,
        "freeze_complete": True,
    }
    freeze.pop("protocol_hash", None)
    freeze["protocol_hash"] = sha256_json({k: v for k, v in freeze.items() if k != "protocol_hash"})
    write_json_atomic(PROTOCOL_PATH, freeze)
    write_json_atomic(DERIVED_DIR / "protocol_freeze.json", freeze)
    return freeze
