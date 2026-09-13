"""Validate the six physical decision-study job archives without rewriting them."""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from .campaign import JOB_ORDER, load_ledger
from .paths import ATTEMPTS, RAW

SHOT_RE = re.compile(r"^[01]{6}$")
EXPECTED_COMBOS = {(f"D{i}", p) for i in range(1, 7) for p in (1, 2)}


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise ValueError(message)


def validate_pub_shots_and_counts(pub: dict[str, Any], *, job_id: str) -> None:
    shots = pub.get("shots")
    counts = pub.get("counts")
    _require(isinstance(shots, list), f"{job_id}: shots must be a list")
    _require(len(shots) == 1024, f"{job_id} pub {pub.get('pub_index')}: expected 1024 shots, got {len(shots)}")
    for shot in shots:
        text = str(shot)
        _require(SHOT_RE.fullmatch(text) is not None, f"{job_id}: invalid shot {shot!r}")
    _require(isinstance(counts, dict), f"{job_id}: counts must be an object")
    coerced = {}
    for key, value in counts.items():
        _require(SHOT_RE.fullmatch(str(key)) is not None, f"{job_id}: invalid counts key {key!r}")
        _require(isinstance(value, int) and not isinstance(value, bool) and value > 0, f"{job_id}: counts must be positive ints, got {value!r}")
        coerced[str(key)] = value
    hist = Counter(str(s) for s in shots)
    _require(dict(hist) == coerced, f"{job_id} pub {pub.get('pub_index')}: counts do not match ordered shots")


def validate_physical_job_archive(data: dict[str, Any], *, job_id: str, ledger_row: dict[str, Any] | None, attempt: dict[str, Any] | None) -> None:
    _require(data.get("job_id") == job_id, f"archive job_id {data.get('job_id')} != {job_id}")
    _require(data.get("evidence_type") == "decision_hardware", f"{job_id}: evidence_type is not decision_hardware")
    _require(data.get("mock") is False, f"{job_id}: mock archive is not a physical job")
    usage_status = str(((data.get("metrics") or {}).get("usage") or {}).get("status") or "").lower()
    _require(usage_status in {"complete", "completed", "ok", "done"}, f"{job_id}: unsuccessful usage status {usage_status!r}")
    intent = data.get("intent")
    _require(bool(intent), f"{job_id}: missing intent")
    if attempt:
        _require(attempt.get("intent") == intent, f"{job_id}: attempt intent mismatch")
        if attempt.get("job_id"):
            _require(attempt.get("job_id") == job_id, f"{job_id}: attempt job linkage mismatch")
    if ledger_row:
        _require(ledger_row.get("job_id") == job_id or ledger_row.get("ibm_job_id") == job_id, f"{job_id}: ledger row job id mismatch")
        if ledger_row.get("intent"):
            _require(ledger_row.get("intent") == intent, f"{job_id}: ledger intent mismatch")
    pubs = data.get("pubs") or []
    mapping = data.get("pub_mapping") or []
    _require(len(pubs) == 12, f"{job_id}: expected 12 PUBs, got {len(pubs)}")
    _require(len(mapping) == 12, f"{job_id}: expected 12 pub_mapping rows, got {len(mapping)}")
    indexes = [int(p["pub_index"]) for p in pubs]
    map_indexes = [int(m["pub_index"]) for m in mapping]
    _require(len(set(indexes)) == 12, f"{job_id}: duplicate pub_index in pubs")
    _require(len(set(map_indexes)) == 12, f"{job_id}: duplicate pub_index in mapping")
    _require(set(indexes) == set(map_indexes), f"{job_id}: pub/mapping index set mismatch")
    combos = []
    for meta in mapping:
        combos.append((str(meta["instance_id"]), int(meta["p"])))
    _require(len(set(combos)) == 12, f"{job_id}: duplicate fixture/depth mapping")
    _require(set(combos) == EXPECTED_COMBOS, f"{job_id}: mapping is not exactly D1–D6 × p=1,2")
    by_index = {int(m["pub_index"]): m for m in mapping}
    for pub in pubs:
        meta = by_index[int(pub["pub_index"])]
        _require(int(pub.get("pub_index")) == int(meta["pub_index"]), f"{job_id}: pub/meta index mismatch")
        validate_pub_shots_and_counts(pub, job_id=job_id)


def validate_six_physical_jobs() -> dict[str, Any]:
    ledger = load_ledger()
    history = [row for row in (ledger.get("history") or []) if row.get("physical") and not row.get("mock")]
    by_job = {}
    for row in history:
        jid = row.get("job_id") or row.get("ibm_job_id")
        if jid:
            by_job[str(jid)] = row
    attempts = {}
    for path in ATTEMPTS.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        attempts[data.get("intent")] = data
        if data.get("job_id"):
            attempts[data.get("job_id")] = data
    _require(len(JOB_ORDER) == 6, "JOB_ORDER must list six physical jobs")
    for job_id in JOB_ORDER:
        path = RAW / f"{job_id}.json"
        _require(path.is_file(), f"missing raw archive {job_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        attempt = attempts.get(data.get("intent")) or attempts.get(job_id)
        validate_physical_job_archive(data, job_id=job_id, ledger_row=by_job.get(job_id), attempt=attempt)
        if data.get("client_elapsed_seconds") is None:
            raise ValueError(f"{job_id}: missing client_elapsed_seconds (will not invent)")
        if data.get("charged_usage_seconds") is None and not ((data.get("metrics") or {}).get("usage") or {}).get("qpu_charge_time_seconds"):
            raise ValueError(f"{job_id}: missing charge (will not invent)")
    missing_ledger = [jid for jid in JOB_ORDER if jid not in by_job]
    if missing_ledger:
        # ledger may store ids only on history.job_id; already checked per row when present
        pass
    return {"ok": True, "n_jobs": 6, "job_ids": list(JOB_ORDER)}
