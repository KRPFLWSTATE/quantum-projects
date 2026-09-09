from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .paths import LEGACY_HASHES, REPO_ROOT, STUDY_ROOT, assert_safe_output

SKIP_NAMES = {
    ".env",
    "save_credentials.py",
    "campaign_ledger.lock",
    "export_receipt.json",
    "chatgpt_return_packet.zip",
    "chatgpt_return_packet.sha256",
}
SKIP_SUFFIX = {".pyc", ".zip"}
SKIP_DIR_NAMES = {"venv", "__pycache__", ".git", ".cursor", "build", "dist"}


def _rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _allow_source(path: Path) -> bool:
    if not path.is_file():
        return False
    rel = Path(_rel(path))
    if any(part in SKIP_DIR_NAMES for part in rel.parts):
        return False
    if path.name in SKIP_NAMES or path.suffix.lower() in SKIP_SUFFIX:
        return False
    if path.name.endswith("_backup.json"):
        return False
    if path.name.endswith(".sha256") and "research-archive" in path.name:
        return False
    return True


def source_inventory() -> list[Path]:
    """Every source file required by the documented offline command and integrity checks."""
    files: set[Path] = set()
    roots = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "CITATION.cff",
        REPO_ROOT / "LICENSE",
        REPO_ROOT / "requirements.txt",
        REPO_ROOT / "requirements-repro.txt",
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "docs",
        REPO_ROOT / "tools",
        STUDY_ROOT / "README.md",
        STUDY_ROOT / "config",
        STUDY_ROOT / "src",
        STUDY_ROOT / "study.py",
        STUDY_ROOT / "tests",
        STUDY_ROOT / "tools",
        STUDY_ROOT / "data",
    ]
    for root in roots:
        if root.is_file() and _allow_source(root):
            files.add(root.resolve())
        elif root.is_dir():
            for path in root.rglob("*"):
                if _allow_source(path):
                    files.add(path.resolve())
    expected = json.loads(LEGACY_HASHES.read_text(encoding="utf-8"))
    for rel in expected:
        path = REPO_ROOT / rel
        if path.is_file():
            files.add(path.resolve())
    return sorted(files, key=lambda p: _rel(p))


def missing_inventory() -> list[str]:
    expected = json.loads(LEGACY_HASHES.read_text(encoding="utf-8"))
    missing = []
    rels = {_rel(p) for p in source_inventory()}
    if "decision-study/tools/verify_isa.py" not in rels:
        missing.append("decision-study/tools/verify_isa.py")
    for rel in expected:
        if rel not in rels:
            missing.append(rel)
    return missing


def write_research_archive(
    output_dir: Path,
    members: Iterable[Path] | None = None,
    generated_root: Path | None = None,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / "decision-qaoa-and-ghz-research-archive.zip"
    sidecar = output_dir / "decision-qaoa-and-ghz-research-archive.sha256"
    assert_safe_output(zip_path)
    if members is None:
        files = source_inventory()
    else:
        files = [Path(p).resolve() for p in members]
    archive_bytes: list[tuple[str, bytes]] = []
    manifest_entries = []
    for path in files:
        rel = _rel(path)
        data = path.read_bytes()
        archive_bytes.append((rel, data))
        manifest_entries.append({"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    if generated_root is not None and generated_root.is_dir():
        for path in sorted(generated_root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() == ".zip" or path.name.endswith(".sha256") or path.name == "export_receipt.json":
                continue
            if "dist" in path.relative_to(generated_root).parts:
                continue
            rel = "reproduction_outputs/" + str(path.relative_to(generated_root)).replace("\\", "/")
            data = path.read_bytes()
            archive_bytes.append((rel, data))
            manifest_entries.append({"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    manifest_entries.sort(key=lambda e: e["path"])
    archive_bytes.sort(key=lambda item: item[0])
    tmp_manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "n_files": len(manifest_entries),
        "files": manifest_entries,
        "scientific_content_hashes": {e["path"]: e["sha256"] for e in manifest_entries},
        "note": "Member SHA-256 hashes are the stable scientific-content hashes. The whole-ZIP digest varies if compressor metadata changes. Manifest excludes itself, the ZIP, and the external sidecar.",
    }
    manifest_bytes = (json.dumps(tmp_manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with zipfile.ZipFile(zip_path, "w") as zf:
        for rel, data in archive_bytes:
            info = zipfile.ZipInfo(rel)
            info.date_time = (2026, 9, 9, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
        info = zipfile.ZipInfo("ARCHIVE_MANIFEST.json")
        info.date_time = (2026, 9, 9, 0, 0, 0)
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, manifest_bytes)
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        if "ARCHIVE_MANIFEST.json" not in names:
            raise RuntimeError("manifest missing from zip")
        inner = json.loads(zf.read("ARCHIVE_MANIFEST.json"))
        for entry in inner["files"]:
            if entry["path"] not in names:
                raise RuntimeError(f"missing zip member {entry['path']}")
            payload = zf.read(entry["path"])
            if len(payload) != int(entry["bytes"]):
                raise RuntimeError(f"size mismatch {entry['path']}")
            if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
                raise RuntimeError(f"hash mismatch {entry['path']}")
        if any(n.endswith(".zip") and n != "ARCHIVE_MANIFEST.json" for n in names if n.lower().endswith(".zip")):
            raise RuntimeError("nested zip not allowed")
        if any("dist/" in n and n.endswith(".sha256") for n in names):
            raise RuntimeError("internal export sidecar not allowed")
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    sidecar.write_text(digest + "\n", encoding="utf-8")
    return {
        "zip": str(zip_path),
        "sidecar": str(sidecar),
        "sha256": digest,
        "n_files": len(manifest_entries),
        "missing_required": missing_inventory() if members is None else [],
    }
