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


def protected_roots() -> list[Path]:
    return [
        (DATA).resolve(),
        (DATA / "raw").resolve(),
        ATTEMPTS.resolve(),
        (DERIVED / "compile").resolve(),
        LEGACY_RUNS.resolve(),
        SRC_DIR.resolve(),
        CONFIG.resolve(),
    ]


def protected_files() -> set[Path]:
    return {
        LEDGER.resolve(),
        (DATA / "decisions.json").resolve(),
        PROTOCOL.resolve(),
        (STUDY_ROOT / "study.py").resolve(),
        (DATA / "preservation" / "legacy_sha256.json").resolve(),
    }


def validate_output_root(output: Path) -> None:
    resolved = output.resolve()
    if resolved == REPO_ROOT.resolve():
        raise ValueError("refusing to use the repository root as an output directory")
    if resolved in protected_files() or resolved in protected_roots():
        raise ValueError(f"refusing protected output root {resolved}")
    for root in protected_roots():
        if root in resolved.parents:
            raise ValueError(f"refusing to create output inside protected path {root}")


def ensure_publication_dirs() -> None:
    for path in (PUBLICATION, PUBLICATION_TABLES, PUBLICATION_FIGURES, PUBLICATION_REPORTS):
        path.mkdir(parents=True, exist_ok=True)


def assert_safe_output(path: Path) -> None:
    resolved = path.resolve()
    if resolved in protected_files():
        raise ValueError(f"refusing to overwrite protected file {resolved}")
    for root in protected_roots():
        if resolved == root or root in resolved.parents:
            raise ValueError(f"refusing to write into protected path {resolved}")
