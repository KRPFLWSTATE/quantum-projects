from __future__ import annotations

from pathlib import Path

STUDY_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = STUDY_ROOT.parent
SRC_DIR = STUDY_ROOT / "src"
CONFIG_DIR = STUDY_ROOT / "config"
DATA_DIR = STUDY_ROOT / "data"
REQUESTS_DIR = DATA_DIR / "requests"
ATTEMPTS_DIR = DATA_DIR / "attempts"
RAW_DIR = DATA_DIR / "raw"
DERIVED_DIR = DATA_DIR / "derived"
PRESERVATION_DIR = DATA_DIR / "preservation"
REPORTS_DIR = STUDY_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
TABLES_DIR = REPORTS_DIR / "tables"
MANUSCRIPT_DIR = STUDY_ROOT / "manuscript_support"
TESTS_DIR = STUDY_ROOT / "tests"
LEGACY_RUNS_DIR = REPO_ROOT / "dba-qpu-run" / "results" / "runs"
LEGACY_EXPORTS_DIR = REPO_ROOT / "dba-qpu-run" / "results" / "ibm-runtime-exports"
LEGACY_RESULTS_DIR = REPO_ROOT / "dba-qpu-run" / "results"
PROTOCOL_PATH = CONFIG_DIR / "protocol.json"
FIXTURES_PATH = CONFIG_DIR / "hardware_fixtures.json"
LEDGER_PATH = DATA_DIR / "campaign_ledger.json"
LEDGER_LOCK_PATH = DATA_DIR / "campaign_ledger.lock"
HASHES_PATH = PRESERVATION_DIR / "legacy_sha256.json"
COMMAND_LOG_PATH = REPORTS_DIR / "command_test_log.txt"


def ensure_directories() -> None:
    for path in (
        CONFIG_DIR,
        REQUESTS_DIR,
        ATTEMPTS_DIR,
        RAW_DIR,
        DERIVED_DIR,
        PRESERVATION_DIR,
        REPORTS_DIR,
        FIGURES_DIR,
        TABLES_DIR,
        MANUSCRIPT_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
