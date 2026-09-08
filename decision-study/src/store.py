"""Temporary or campaign filesystem roots for ledger/archives. Tests never use the physical campaign ledger."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .hashing import write_json_atomic
from .ledger import LedgerLock, default_ledger
from .paths import (
    ATTEMPTS_DIR,
    DATA_DIR,
    DERIVED_DIR,
    LEDGER_LOCK_PATH,
    LEDGER_PATH,
    RAW_DIR,
    STUDY_ROOT,
)


@dataclass
class CampaignStore:
    root: Path
    label: str = "campaign"

    @property
    def data_dir(self) -> Path:
        return self.root / "data" if self.root != STUDY_ROOT else DATA_DIR

    @property
    def ledger_path(self) -> Path:
        return self.root / "data" / "campaign_ledger.json" if self.root != STUDY_ROOT else LEDGER_PATH

    @property
    def lock_path(self) -> Path:
        return self.root / "data" / "campaign_ledger.lock" if self.root != STUDY_ROOT else LEDGER_LOCK_PATH

    @property
    def attempts_dir(self) -> Path:
        return self.root / "data" / "attempts" if self.root != STUDY_ROOT else ATTEMPTS_DIR

    @property
    def raw_dir(self) -> Path:
        return self.root / "data" / "raw" if self.root != STUDY_ROOT else RAW_DIR

    @property
    def derived_dir(self) -> Path:
        return self.root / "data" / "derived" if self.root != STUDY_ROOT else DERIVED_DIR

    @property
    def decisions_path(self) -> Path:
        return self.data_dir / "decisions.json"

    @property
    def jobs_index_path(self) -> Path:
        return self.data_dir / "provider_jobs.json"

    def ensure(self) -> None:
        self.attempts_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.derived_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def lock(self) -> LedgerLock:
        return LedgerLock(self.lock_path)

    def load_ledger(self) -> dict[str, Any]:
        if not self.ledger_path.is_file():
            return default_ledger()
        return json.loads(self.ledger_path.read_text(encoding="utf-8"))

    def save_ledger(self, ledger: dict[str, Any]) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(self.ledger_path, ledger)


DEFAULT_STORE = CampaignStore(STUDY_ROOT, label="campaign")
