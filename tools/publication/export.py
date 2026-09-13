from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from . import ANALYSIS_VERSION
from .paths import LEGACY_HASHES, REPO_ROOT, STUDY_ROOT, assert_safe_output
from .provenance import git_state

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
EXTRA_ARCHIVE_PATHS = [
    REPO_ROOT / "dba-qpu-run" / "README.md",
    REPO_ROOT / "dba-qpu-run" / "run_circuit.py",
    REPO_ROOT / "dba-qpu-run" / "analyze_results.py",
    REPO_ROOT / "archive" / "README.md",
    REPO_ROOT / "archive" / "development" / "PATH_MAP.json",
    REPO_ROOT / "docs" / "archive-zip-navigation.md",
    REPO_ROOT / "docs" / "contribution-note.md",
    REPO_ROOT / "archive" / "historical-public-docs" / "related-work-handoff.md",
    REPO_ROOT / "archive" / "historical-exports" / "CHECKSUMS.md",
]


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
    for extra in EXTRA_ARCHIVE_PATHS:
        if extra.is_file() and _allow_source(extra):
            files.add(extra.resolve())
    return sorted(files, key=lambda p: _rel(p))


def missing_inventory() -> list[str]:
    expected = json.loads(LEGACY_HASHES.read_text(encoding="utf-8"))
    missing = []
    rels = {_rel(p) for p in source_inventory()}
    if "decision-study/tools/verify_isa.py" not in rels:
        missing.append("decision-study/tools/verify_isa.py")
    if "dba-qpu-run/README.md" not in rels:
        missing.append("dba-qpu-run/README.md")
    if "archive/development/PATH_MAP.json" not in rels:
        missing.append("archive/development/PATH_MAP.json")
    for rel in expected:
        if rel not in rels:
            missing.append(rel)
    return missing


def _safe_member_name(rel: str) -> str:
    if not rel or rel.startswith("/") or rel.startswith("\\") or ".." in Path(rel).parts:
        raise ValueError(f"unsafe zip member name {rel!r}")
    if rel.replace("\\", "/") != rel:
        raise ValueError(f"unsafe zip member name {rel!r}")
    return rel


def _landing_markdown() -> bytes:
    text = """# Research archive landing (ZIP)

This ZIP is a self-contained offline snapshot. It is **not** a GitHub checkout.

- Generated tables/figures/reports: [`reproduction_outputs/`](reproduction_outputs/)
- Reader docs: [`docs/`](docs/) — GitHub-relative `results/publication/` figure links apply to a clone, not this ZIP. Use `reproduction_outputs/figures/` here.
- ZIP navigation notes: [`docs/archive-zip-navigation.md`](docs/archive-zip-navigation.md)
- Legacy GHZ README: [`dba-qpu-run/README.md`](dba-qpu-run/README.md) (do not execute hardware scripts from this archive)
- Historical path map: [`archive/development/PATH_MAP.json`](archive/development/PATH_MAP.json) maps old bundle locations in the full repository; omitted historical installer directories are not required for reproduction
- Snapshot provenance: [`EXPORTED_SNAPSHOT_PROVENANCE.json`](EXPORTED_SNAPSHOT_PROVENANCE.json)

Run from this extracted root:

```bash
python -m unittest discover -s decision-study/tests -v
python -m unittest discover -s tools/tests -v
python tools/reproduce.py --output reproduction_outputs_extracted
```

Do not pass `--refresh-publication` unless `results/publication` exists as a separate tree.
"""
    return text.encode("utf-8")


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
    seen: set[str] = set()
    manifest_entries = []

    def _add(rel: str, data: bytes) -> None:
        name = _safe_member_name(rel)
        if name in seen:
            raise ValueError(f"duplicate zip member {name}")
        seen.add(name)
        archive_bytes.append((name, data))
        manifest_entries.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})

    for path in files:
        _add(_rel(path), path.read_bytes())
    if generated_root is not None and generated_root.is_dir():
        for path in sorted(generated_root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() == ".zip" or path.name.endswith(".sha256") or path.name == "export_receipt.json":
                continue
            rel_parts = path.relative_to(generated_root).parts
            if "dist" in rel_parts:
                continue
            rel = "reproduction_outputs/" + str(path.relative_to(generated_root)).replace("\\", "/")
            _add(rel, path.read_bytes())
    git = git_state()
    snapshot = {
        "git_present": git.get("git_present"),
        "head": git.get("head"),
        "dirty": git.get("dirty"),
        "status_porcelain": git.get("status_porcelain"),
        "exported_snapshot_identifier": git.get("head") or git.get("exported_snapshot_identifier"),
        "analysis_version": ANALYSIS_VERSION,
        "generation_command": "python tools/reproduce.py --output <isolated-dir>",
        "packaging_uncommitted_changes": bool(git.get("dirty")),
        "paper_cited_commit": "0abf41f2e9b256c94cd056e55ec8f9fc8766faec",
        "note": "HEAD alone does not describe uncommitted edits. If dirty is true, this ZIP includes working-tree files.",
    }
    if members is None:
        _add("ARCHIVE_LANDING.md", _landing_markdown())
        _add("EXPORTED_SNAPSHOT_PROVENANCE.json", (json.dumps(snapshot, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    manifest_entries.sort(key=lambda e: e["path"])
    archive_bytes.sort(key=lambda item: item[0])
    tmp_manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "analysis_version": ANALYSIS_VERSION,
        "packaging_provenance": snapshot,
        "n_files": len(manifest_entries),
        "files": manifest_entries,
        "scientific_content_hashes": {e["path"]: e["sha256"] for e in manifest_entries},
        "note": "Member SHA-256 hashes are the stable scientific-content hashes. The whole-ZIP digest is stored only in the external sidecar. Manifest excludes itself, the ZIP, and the external sidecar.",
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
        crc_fail = zf.testzip()
        if crc_fail:
            raise RuntimeError(f"zip CRC failure {crc_fail}")
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
        if any(n.lower().endswith(".zip") for n in names):
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
        "packaging_uncommitted_changes": bool(git.get("dirty")),
    }
