from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .paths import REPO_ROOT, assert_safe_output

SKIP_NAMES = {".env", "save_credentials.py", "campaign_ledger.lock"}
SKIP_SUFFIX = {".pyc"}
SKIP_DIRS = {"venv", "__pycache__", ".git", ".cursor", "build"}


def _allow(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT)
    parts = set(rel.parts)
    if parts & SKIP_DIRS:
        return False
    if path.name in SKIP_NAMES or path.suffix in SKIP_SUFFIX:
        return False
    if path.name.endswith("_backup.json"):
        return False
    if path.suffix.lower() in {".zip"}:
        return False
    return True


def default_members() -> list[Path]:
    roots = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "CITATION.cff",
        REPO_ROOT / "LICENSE",
        REPO_ROOT / "requirements.txt",
        REPO_ROOT / "requirements-repro.txt",
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "docs",
        REPO_ROOT / "tools",
        REPO_ROOT / "results" / "publication",
        REPO_ROOT / "decision-study" / "README.md",
        REPO_ROOT / "decision-study" / "config",
        REPO_ROOT / "decision-study" / "src",
        REPO_ROOT / "decision-study" / "study.py",
        REPO_ROOT / "decision-study" / "tests",
        REPO_ROOT / "decision-study" / "data",
        REPO_ROOT / "dba-qpu-run" / "results" / "runs",
        REPO_ROOT / "dba-qpu-run" / "results" / "comparative_summary.json",
        REPO_ROOT / "archive" / "development" / "PATH_MAP.json",
        REPO_ROOT / "archive" / "development" / "README.md",
        REPO_ROOT / "archive" / "historical-public-docs",
    ]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            for path in root.rglob("*"):
                if path.is_file() and _allow(path):
                    files.append(path)
    unique = sorted({p.resolve() for p in files}, key=lambda p: str(p.relative_to(REPO_ROOT)))
    return unique


def write_research_archive(output_dir: Path, members: Iterable[Path] | None = None) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / "decision-qaoa-and-ghz-research-archive.zip"
    sidecar = output_dir / "decision-qaoa-and-ghz-research-archive.sha256"
    assert_safe_output(zip_path)
    files = list(members) if members is not None else default_members()
    manifest_entries = []
    for path in files:
        rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        data = path.read_bytes()
        manifest_entries.append({"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    manifest_entries.sort(key=lambda e: e["path"])
    # ZIP first without embedding sidecar. Manifest is added after hashing files but is not hashed as an included scientific input.
    tmp_manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "n_files": len(manifest_entries),
        "files": manifest_entries,
        "note": "Manifest hashes member files only. It excludes itself, the ZIP, and the external sidecar.",
    }
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            info = zipfile.ZipInfo(rel)
            info.date_time = (2026, 9, 9, 0, 0, 0)
            zf.writestr(info, path.read_bytes())
        info = zipfile.ZipInfo("ARCHIVE_MANIFEST.json")
        info.date_time = (2026, 9, 9, 0, 0, 0)
        zf.writestr(info, json.dumps(tmp_manifest, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    sidecar.write_text(digest + "\n", encoding="utf-8")
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        if "ARCHIVE_MANIFEST.json" not in names:
            raise RuntimeError("manifest missing from zip")
        inner = json.loads(zf.read("ARCHIVE_MANIFEST.json"))
        for entry in inner["files"]:
            if entry["path"] not in names:
                raise RuntimeError(f"missing zip member {entry['path']}")
    return {"zip": str(zip_path), "sidecar": str(sidecar), "sha256": digest, "n_files": len(manifest_entries)}
