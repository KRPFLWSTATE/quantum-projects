"""Allowlisted return packet ZIP."""

from __future__ import annotations

import zipfile
from pathlib import Path

from .hashing import sha256_file
from .paths import REPORTS_DIR, STUDY_ROOT

ALLOW_PREFIXES = (
    "src/",
    "tests/",
    "config/",
    "data/",
    "reports/",
    "manuscript_support/",
    "tools/",
)
ALLOW_ROOT_FILES = {"study.py", "README.md"}
EXCLUDE_NAMES = {".env", "save_credentials.py", "venv", "chatgpt_return_packet.zip"}
EXCLUDE_SUFFIX = {".pyc"}


def export_packet() -> dict:
    zip_path = REPORTS_DIR / "chatgpt_return_packet.zip"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    included = []
    hashes = []
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in STUDY_ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(STUDY_ROOT)
            rel_s = str(rel).replace("\\", "/")
            if any(part in EXCLUDE_NAMES or part.endswith(".tmp") for part in rel.parts):
                continue
            if path.suffix in EXCLUDE_SUFFIX or "__pycache__" in rel.parts:
                continue
            if path.name.endswith("_backup.json"):
                continue
            if zip_path.name == path.name:
                continue
            allowed = rel_s in ALLOW_ROOT_FILES or rel_s.startswith(ALLOW_PREFIXES)
            if not allowed:
                continue
            zf.write(path, arcname=str(Path("decision-study") / rel))
            included.append(rel_s)
            hashes.append(f"{sha256_file(path)}  {rel_s}  {path.stat().st_size}")
        manifest = "self_reference=excluded_from_hashed_entries\n" + "\n".join(sorted(hashes)) + "\n"
        zf.writestr("decision-study/PACKET_MANIFEST.txt", manifest)
    return {"zip": str(zip_path), "files": len(included), "sha256": sha256_file(zip_path)}
