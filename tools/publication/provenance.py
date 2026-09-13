from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import ANALYSIS_VERSION
from .paths import REPO_ROOT


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_state() -> dict[str, Any]:
    git_dir = REPO_ROOT / ".git"
    marker = REPO_ROOT / "EXPORTED_SNAPSHOT_PROVENANCE.json"
    if not git_dir.exists():
        if marker.is_file():
            payload = json.loads(marker.read_text(encoding="utf-8"))
            payload.setdefault("git_present", False)
            payload.setdefault("note", "Recovered exported-snapshot provenance; this tree is not a git checkout.")
            return payload
        return {
            "git_present": False,
            "exported_snapshot_identifier": "unavailable-no-git-no-export-marker",
            "dirty": None,
            "note": "No .git and no EXPORTED_SNAPSHOT_PROVENANCE.json; do not treat this as a clean checkout.",
        }
    def _run(args: list[str]) -> str:
        proc = subprocess.run(args, cwd=str(REPO_ROOT), capture_output=True, text=True)
        return proc.stdout.strip() if proc.returncode == 0 else ""
    dirty_text = _run(["git", "status", "--porcelain"])
    return {
        "git_present": True,
        "head": _run(["git", "rev-parse", "HEAD"]),
        "dirty": bool(dirty_text),
        "status_porcelain": dirty_text,
    }


def environment() -> dict[str, Any]:
    env: dict[str, Any] = {
        "python": sys.version,
        "platform": platform.platform(),
        "executable": sys.executable,
        "cwd": os.getcwd(),
    }
    packages = {}
    for name in ("numpy", "qiskit", "qiskit_ibm_runtime", "qiskit_aer", "scipy", "matplotlib"):
        try:
            mod = __import__(name)
            packages[name] = getattr(mod, "__version__", None)
        except Exception as exc:
            packages[name] = f"unavailable:{exc.__class__.__name__}"
    env["packages"] = packages
    return env


def analysis_provenance(*, command: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "analysis_version": ANALYSIS_VERSION,
        "analysis_revision_distinct_from_frozen_hardware_protocol": True,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "git": git_state(),
        "environment": environment(),
        "historical_account_balance_note": "524 seconds remaining was observed at 2026-09-09T11:17:44.252800+00:00 and is not live availability.",
    }
    if extra:
        payload.update(extra)
    return payload


def hash_path_list(paths: list[Path]) -> dict[str, str]:
    out = {}
    for path in paths:
        if path.is_file():
            rel = str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
            out[rel] = sha256_bytes(path.read_bytes())
    return out
