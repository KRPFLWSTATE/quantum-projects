from __future__ import annotations

from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_DIR.parent
STUDY_ROOT = REPO_ROOT / "decision-study"
SRC_DIR = STUDY_ROOT / "src"
CONFIG = STUDY_ROOT / "config"
DATA = STUDY_ROOT / "data"
RAW = DATA / "raw"
ATTEMPTS = DATA / "attempts"
DERIVED = DATA / "derived"
PRESERVATION = DATA / "preservation"
PROTOCOL = CONFIG / "protocol.json"
LEDGER = DATA / "campaign_ledger.json"
LEGACY_HASHES = PRESERVATION / "legacy_sha256.json"
PRE_MANIFEST = PRESERVATION / "pre_housekeeping_manifest.json"
LEGACY_RUNS = REPO_ROOT / "dba-qpu-run" / "results" / "runs"
PUBLICATION = REPO_ROOT / "results" / "publication"
PUBLICATION_TABLES = PUBLICATION / "tables"
PUBLICATION_FIGURES = PUBLICATION / "figures"
PUBLICATION_REPORTS = PUBLICATION / "reports"
FROZEN_OUTPUTS = {DATA / "raw", DATA / "attempts", DERIVED / "compile" / "qpy", CONFIG / "protocol.json"}


def ensure_publication_dirs() -> None:
    for path in (PUBLICATION, PUBLICATION_TABLES, PUBLICATION_FIGURES, PUBLICATION_REPORTS):
        path.mkdir(parents=True, exist_ok=True)


def assert_safe_output(path: Path) -> None:
    resolved = path.resolve()
    protected_roots = [
        (DATA / "raw").resolve(),
        ATTEMPTS.resolve(),
        (DERIVED / "compile").resolve(),
        LEGACY_RUNS.resolve(),
    ]
    protected_files = {
        LEDGER.resolve(),
        (DATA / "decisions.json").resolve(),
        PROTOCOL.resolve(),
    }
    if resolved in protected_files:
        raise ValueError(f"refusing to overwrite protected file {resolved}")
    for root in protected_roots:
        if resolved == root or root in resolved.parents:
            raise ValueError(f"refusing to write into protected path {resolved}")
