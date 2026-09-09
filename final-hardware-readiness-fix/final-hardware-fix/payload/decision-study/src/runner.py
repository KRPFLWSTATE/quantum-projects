"""Single dispatch/resume path. Physical IBM run is CLI opt-in only; tests inject an adapter and temp store."""

from __future__ import annotations

import concurrent.futures
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from qiskit import qpy

from .hashing import write_json_atomic
from .ledger import can_submit
from .paths import DERIVED_DIR, STUDY_ROOT
from .readiness import engineering_status
from .runtime_adapter import (
    FakeSamplerV2,
    FakeService,
    decode_primitive_result,
    interpret_usage,
    job_id_of,
    sampler_options_object,
    shots_are_valid,
)
from .store import DEFAULT_STORE, CampaignStore


AUTHORISED_HARDWARE = False
LIVE_DEADLINE_SECONDS = 30.0


def physical_submit_allowed() -> bool:
    return bool(AUTHORISED_HARDWARE)


def authorise_hardware_cli() -> None:
    global AUTHORISED_HARDWARE
    AUTHORISED_HARDWARE = True


def build_pub_manifest(seed: int = 20260908) -> list[dict[str, Any]]:
    items = [{"instance_id": f"D{i}", "p": p} for i in range(1, 7) for p in (1, 2)]
    rng = __import__("random").Random(seed)
    order = list(range(len(items)))
    rng.shuffle(order)
    return [{**items[i], "pub_index": pos} for pos, i in enumerate(order)]


def load_isa_pubs(manifest: list[dict[str, Any]]) -> tuple[list[Any], list[dict[str, Any]]]:
    summary_path = DERIVED_DIR / "compile" / "isa_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    by_key = {(row["instance_id"], int(row["p"])): row for row in summary["rows"]}
    pubs = []
    meta = []
    for item in sorted(manifest, key=lambda row: int(row["pub_index"])):
        row = by_key[(item["instance_id"], int(item["p"]))]
        path = STUDY_ROOT / row["isa_qpy"]
        with path.open("rb") as handle:
            circuit = qpy.load(handle)[0]
        pubs.append(circuit)
        meta.append({**item, "isa_qpy": row["isa_qpy"], "isa_qpy_sha256": row["isa_qpy_sha256"]})
    return pubs, meta


class InjectedAdapter:
    def __init__(self, sampler: FakeSamplerV2, service: FakeService, backend_name: str = "fake_backend") -> None:
        self.sampler = sampler
        self.service = service
        self.backend_name = backend_name
        self.physical = False

    def submit(self, pubs, shots: int = 1024, tags: list[str] | None = None):
        self.sampler.options = sampler_options_object(job_tags=tags)
        job = self.sampler.run(pubs, shots=shots)
        if tags:
            job.tags = list(tags)
        self.service.jobs[job_id_of(job)] = job
        self.sampler.jobs[job_id_of(job)] = job
        return job

    def retrieve(self, job_id: str):
        return self.service.job(job_id)

    def retrieve_by_tags(self, tags: list[str]):
        if hasattr(self.service, "jobs_by_tags"):
            return self.service.jobs_by_tags(tags)
        return []


class PhysicalAdapter:
    def __init__(self, backend, service) -> None:
        self.backend = backend
        self.service = service
        self.backend_name = backend.name
        self.physical = True
        self.run_calls = 0

    def submit(self, pubs, shots: int = 1024, tags: list[str] | None = None):
        from .hardware import run_physical_block

        self.run_calls += 1
        return run_physical_block(self.backend, pubs, shots=shots, job_tags=tags)

    def retrieve(self, job_id: str):
        return self.service.job(job_id)

    def retrieve_by_tags(self, tags: list[str]):
        if hasattr(self.service, "jobs"):
            try:
                return list(self.service.jobs(job_tags=tags) or [])
            except TypeError:
                # Never recover an unrelated job from an unfiltered provider listing.
                wanted = set(tags)
                return [job for job in self.service.jobs(limit=50) or []
                        if wanted.issubset(set(getattr(job, "tags", []) or []))]
        return []


def _persist_job_index(store: CampaignStore, job_id: str, payload: dict[str, Any]) -> None:
    index = {}
    if store.jobs_index_path.is_file():
        index = json.loads(store.jobs_index_path.read_text(encoding="utf-8"))
    index[job_id] = payload
    write_json_atomic(store.jobs_index_path, index)


def _job_usage_report(job: Any, usage_seconds: float | None) -> dict[str, Any]:
    if usage_seconds is not None:
        # Only caller-supplied test values or a previously resolved archived charge use this path.
        return interpret_usage(usage_seconds, metrics={"usage": {
            "status": "completed", "qpu_charge_time_seconds": usage_seconds}})
    raw = None
    metrics = None
    status = getattr(job, "status", None)
    try:
        raw = job.usage() if hasattr(job, "usage") else None
    except Exception:
        return {"state": "error", "seconds": None, "final_zero": False, "raw": None}
    try:
        metrics = job.metrics() if hasattr(job, "metrics") else None
    except Exception:
        metrics = None
    return interpret_usage(raw, metrics=metrics, status=status)


def _already_finalised(ledger: dict[str, Any], job_id: str) -> bool:
    return any(item.get("job_id") == job_id and item.get("finalised") for item in ledger.get("history", []))


def _evaluate_policies(decoded: dict[str, Any], pubs_meta: list[dict[str, Any]], intent: str, elapsed: float) -> list[dict[str, Any]]:
    from .classical import greedy_then_swaps
    from .fixtures import hardware_instances
    from .policies import apply_policy
    from .spec import spec_from_instance

    instances = {inst.instance_id: inst for inst in hardware_instances()}
    rows = []
    pubs = decoded.get("pubs") or []
    for pub, meta in zip(pubs, pubs_meta or []):
        inst = instances.get(meta.get("instance_id"))
        if inst is None:
            continue
        spec = spec_from_instance(inst, request_id=f"{intent}-{meta.get('instance_id')}-p{meta.get('p')}")
        greedy = greedy_then_swaps(inst)
        incumbent = {"bitstring": greedy["bitstring"], "utility": greedy["utility"]} if greedy.get("status") == "ok" else None
        circuit_hash = meta.get("isa_qpy_sha256") or "missing"
        linkage = {
            "request_id": spec["request_id"],
            "source_hash": spec["source_hash"],
            "circuit_hash": circuit_hash,
            "expected_circuit_hash": circuit_hash,
            "expected_request_id": spec["request_id"],
            "expected_source_hash": spec["source_hash"],
        }
        shots = list(pub.get("shots") or [])
        for policy in ("P0", "P1", "P2", "P3"):
            rows.append(
                {**apply_policy(
                    policy,
                    spec,
                    shots,
                    incumbent,
                    now_elapsed=elapsed,
                    linkage=linkage,
                    trusted_source=spec,
                ), "instance_id": inst.instance_id, "p": meta["p"],
                 "pub_index": meta["pub_index"], "request_id": spec["request_id"],
                 "elapsed_seconds": elapsed}
            )
    return rows


def finalise_attempt(
    *,
    store: CampaignStore,
    adapter: Any,
    job: Any,
    job_id: str,
    intent: str,
    pubs_meta: list[dict[str, Any]] | None,
    tags: list[str],
    decoded: dict[str, Any],
    usage_seconds: float | None,
    physical: bool,
    dispatched_utc: str,
    received_utc: str,
    elapsed_s: float | None,
    metrics: Any = None,
) -> dict[str, Any]:
    # Durable decoded receipt comes before any billing or status query.
    usage = {"state": "unknown", "seconds": None, "final_zero": False}
    n_ok = shots_are_valid(decoded)
    archive = {
        "evidence_type": "decision_hardware" if physical else "sampled_simulation",
        "mock": not physical,
        "job_id": job_id,
        "intent": intent,
        "pubs": decoded.get("pubs"),
        "n_pubs_observed": decoded.get("n_pubs"),
        "pub_mapping": pubs_meta,
        "created_utc": dispatched_utc,
        "result_received_utc": received_utc,
        "client_elapsed_seconds": elapsed_s,
        "charged_usage_seconds": usage.get("seconds"),
        "usage_state": usage.get("state"),
        "usage_final_zero": usage.get("final_zero"),
        "status": None,
        "result_error": decoded.get("result_error"),
        "metrics": metrics,
        "tags": tags,
        "shots_valid": n_ok,
        "label": store.label if not physical else None,
    }
    write_json_atomic(store.raw_dir / f"{job_id}.json", archive)
    usage = _job_usage_report(job, usage_seconds)
    archive.update(charged_usage_seconds=usage.get("seconds"), usage_state=usage.get("state"),
                   usage_final_zero=usage.get("final_zero"), status=_safe_status(job))
    write_json_atomic(store.raw_dir / f"{job_id}.json", archive)
    elapsed_for_policy = elapsed_s if elapsed_s is not None else float("inf")
    policy_rows = _evaluate_policies(decoded, pubs_meta or [], intent, elapsed_for_policy) if n_ok else []
    if elapsed_s is None:
        for row in policy_rows:
            row["elapsed_seconds"] = None
    write_json_atomic(store.derived_dir / f"policies_{job_id}.json", {
        "intent": intent, "job_id": job_id, "rows": policy_rows,
        "analysis_type": "archived_shot_policy_evaluation", "timing_known": elapsed_s is not None})
    _persist_policy_rows(store, policy_rows, event="result.received", job_id=job_id)

    ledger = store.load_ledger()
    if _already_finalised(ledger, job_id):
        outstanding = ledger.get("outstanding_job") or {}
        if outstanding.get("intent") == intent or outstanding.get("job_id") == job_id:
            ledger["outstanding_job"] = None
        for item in ledger.get("reservations", []):
            if item.get("intent") == intent or item.get("job_id") == job_id:
                item["open"] = False
                item["job_id"] = job_id
        store.save_ledger(ledger)
        return {"ok": n_ok, "already_finalised": True, "job_id": job_id, "shots_valid": n_ok, "n_pubs": decoded.get("n_pubs"), "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0}

    if usage.get("state") != "resolved":
        ledger["outstanding_job"] = {"intent": intent, "job_id": job_id, "tags": tags, "physical": physical, "usage_state": usage.get("state")}
        for item in ledger.get("reservations", []):
            if item.get("intent") == intent:
                item["open"] = True
                item["job_id"] = job_id
        store.save_ledger(ledger)
        write_json_atomic(
            store.derived_dir / "last_dispatch.json",
            {
                "intent": intent,
                "job_id": job_id,
                "n_pubs": decoded.get("n_pubs"),
                "shots_valid": n_ok,
                "usage_state": usage.get("state"),
                "ok": False,
                "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 1 if physical else 0,
            },
        )
        return {
            "ok": False,
            "unresolved": True,
            "reason": "USAGE_UNRESOLVED",
            "job_id": job_id,
            "intent": intent,
            "shots_valid": n_ok,
            "n_pubs": decoded.get("n_pubs"),
            "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 1 if physical else 0,
        }

    charged = float(usage["seconds"])
    ledger["jobs_submitted"] = int(ledger.get("jobs_submitted", 0)) + 1
    ledger["outstanding_job"] = None
    for item in ledger.get("reservations", []):
        if item.get("intent") == intent or item.get("job_id") == job_id:
            item["open"] = False
            item["job_id"] = job_id
    ledger["usage_reconciled_seconds"] = float(ledger.get("usage_reconciled_seconds", 0.0)) + charged
    remaining = float(ledger.get("campaign_remaining_seconds", 0.0)) - max(charged, 0.0)
    ledger["campaign_remaining_seconds"] = max(0.0, remaining)
    ledger.setdefault("history", []).append(
        {
            "intent": intent,
            "job_id": job_id,
            "mock": not physical,
            "physical": physical,
            "shots_valid": n_ok,
            "charged_usage_seconds": charged,
            "finalised": True,
        }
    )
    store.save_ledger(ledger)
    write_json_atomic(
        store.derived_dir / "last_dispatch.json",
        {
            "intent": intent,
            "job_id": job_id,
            "n_pubs": decoded.get("n_pubs"),
            "shots": [row.get("n_shots") for row in (decoded.get("pubs") or [])],
            "shots_valid": n_ok,
            "evidence_type": archive["evidence_type"],
            "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 1 if physical else 0,
        },
    )
    return {
        "ok": n_ok,
        "blocked": False,
        "mock": not physical,
        "job_id": job_id,
        "intent": intent,
        "n_pubs": decoded.get("n_pubs"),
        "shots_valid": n_ok,
        "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 1 if physical else 0,
    }


def dispatch_block(
    *,
    physical: bool,
    adapter: InjectedAdapter | PhysicalAdapter | None = None,
    store: CampaignStore | None = None,
    live_remaining: float | None = None,
    skip_readiness: bool = False,
    usage_seconds: float | None = None,
) -> dict[str, Any]:
    store = store or DEFAULT_STORE
    store.ensure()
    if physical and adapter is None and not physical_submit_allowed():
        return {
            "blocked": True,
            "ok": False,
            "reason": "AWAITING_USER_RUN_COMMAND",
            "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0,
        }
    if physical and adapter is None:
        from .budget import bind_open_plan

        if not skip_readiness:
            status = engineering_status()
            if status["engineering_status"] != "READY_FOR_FIRST_HARDWARE" and status.get("blockers"):
                return {
                    "blocked": True,
                    "ok": False,
                    "reason": "READINESS_BLOCKED",
                    "blockers": status.get("blockers"),
                    "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0,
                }
        bound = bind_open_plan()
        if not bound.get("bound") or bound.get("remaining_seconds") is None:
            return {
                "blocked": True,
                "ok": False,
                "reason": bound.get("error") or "INSTANCE_OR_BALANCE_UNRESOLVED",
                "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0,
            }
        live_remaining = float(bound["remaining_seconds"])
        pin = json.loads((DERIVED_DIR / "backend_pin.json").read_text())
        service = bound["service"]
        backend = service.backend(pin["backend"])
        adapter = PhysicalAdapter(backend, service)
    if live_remaining is None:
        return {
            "blocked": True,
            "ok": False,
            "reason": "BALANCE_UNRESOLVED",
            "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0,
        }
    if getattr(adapter, "physical", False):
        estimate_path = DERIVED_DIR / "usage_estimate.json"
        if not estimate_path.is_file():
            return {"blocked": True, "ok": False, "reason": "DURATION_ESTIMATE_MISSING", "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0}
        estimate = json.loads(estimate_path.read_text(encoding="utf-8"))
        if estimate.get("exceeds_45s_cap") or float(estimate.get("block_estimate_seconds") or 99) > 45:
            return {
                "blocked": True,
                "ok": False,
                "reason": "DURATION_ESTIMATE_EXCEEDS_45S",
                "estimate": estimate.get("block_estimate_seconds"),
                "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0,
            }
    with store.lock():
        ledger = store.load_ledger()
        if ledger.get("frozen_allowance_seconds") is None and live_remaining is not None:
            from .budget import campaign_allowance

            frozen = campaign_allowance(live_remaining)
            ledger["frozen_allowance_seconds"] = frozen.get("allowance_seconds")
            if frozen.get("allowance_seconds") is not None:
                ledger["campaign_remaining_seconds"] = float(frozen["allowance_seconds"])
        ok, reason = can_submit(ledger, live_remaining)
        if not ok:
            return {"blocked": True, "ok": False, "reason": reason, "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0}
        intent = str(uuid.uuid4())
        pubs_meta_plan = build_pub_manifest()
        reservation = {"intent": intent, "seconds": 45, "open": True}
        ledger.setdefault("reservations", []).append(reservation)
        tags = [f"decision-{intent[:8]}", "decision-study"]
        ledger["outstanding_job"] = {
            "intent": intent,
            "job_id": None,
            "tags": tags,
            "physical": bool(getattr(adapter, "physical", False)),
        }
        store.save_ledger(ledger)
        try:
            circuits, pubs_meta = load_isa_pubs(pubs_meta_plan)
        except Exception as exc:
            ledger["outstanding_job"]["error"] = f"{type(exc).__name__}:{exc}"
            store.save_ledger(ledger)
            return {
                "blocked": True,
                "ok": False,
                "reason": "ISA_LOAD_FAILED",
                "error": f"{type(exc).__name__}:{exc}",
                "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0,
            }
        dispatched_utc = datetime.now(timezone.utc).isoformat()
        started = time.monotonic()
        protocol = json.loads((STUDY_ROOT / "config" / "protocol.json").read_text())
        write_json_atomic(store.attempts_dir / f"{intent}.json", {
            "intent": intent, "pubs": pubs_meta, "tags": tags, "dispatched_utc": dispatched_utc,
            "deadline_seconds": LIVE_DEADLINE_SECONDS, "protocol_hash": protocol.get("protocol_hash"),
            "backend": adapter.backend_name, "physical": bool(getattr(adapter, "physical", False))})
        try:
            job = adapter.submit(circuits, shots=1024, tags=tags)
            jid = job_id_of(job)
        except Exception as exc:
            ledger["outstanding_job"]["error"] = f"{type(exc).__name__}:{exc}"
            store.save_ledger(ledger)
            return {
                "ok": False,
                "unresolved": True,
                "reason": "TRANSPORT_FAILURE",
                "intent": intent,
                "did_call_run": True,
                "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 1 if getattr(adapter, "physical", False) else 0,
            }
        ledger["outstanding_job"]["job_id"] = jid
        store.save_ledger(ledger)
        _persist_job_index(store, jid, {"intent": intent, "tags": tags, "physical": getattr(adapter, "physical", False)})

    collected = _collect_result(job, store, pubs_meta, intent, jid, dispatched_utc, started)
    if collected.get("unresolved"):
        return {**collected, "job_id": jid, "intent": intent,
                "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 1 if getattr(adapter, "physical", False) else 0}
    with store.lock():
        out = finalise_attempt(
            store=store, adapter=adapter, job=job, job_id=jid, intent=intent,
            pubs_meta=pubs_meta, tags=tags, decoded=collected["decoded"],
            usage_seconds=usage_seconds, physical=bool(getattr(adapter, "physical", False)),
            dispatched_utc=dispatched_utc, received_utc=collected["received_utc"],
            elapsed_s=collected["elapsed_s"], metrics=collected["metrics"])
    out["run_calls"] = getattr(getattr(adapter, "sampler", adapter), "run_calls", getattr(adapter, "run_calls", 1))
    return out


def _safe_status(job):
    try:
        return job.status() if callable(getattr(job, "status", None)) else getattr(job, "status", None)
    except Exception:
        return None


def _safe_metrics(job):
    try:
        return job.metrics() if hasattr(job, "metrics") else None
    except Exception:
        return None


def _persist_policy_rows(store, rows, *, event, job_id):
    # Caller holds the store lock. Per-policy final decisions are immutable.
    from .agents import Bus, Coordinator, Message
    coordinator = Coordinator(persist_path=store.decisions_path)
    bus = Bus()
    bus.register(coordinator)
    for row in rows:
        request = f"{row['request_id']}:{row['policy']}"
        decision = {**row, "request_id": request, "event": event, "job_id": job_id, "final": True}
        coordinator.handle(Message("decision.final", decision, "validator"), bus)


def _deadline_fallback(store, pubs_meta, intent, job_id, elapsed):
    decoded = {"pubs": [{"shots": []} for _ in pubs_meta]}
    rows = _evaluate_policies(decoded, pubs_meta, intent, elapsed)
    # P0 is the unguarded ablation. It waits for a result; P1-P3 finalise at the deadline.
    with store.lock():
        _persist_policy_rows(store, [r for r in rows if r["policy"] != "P0"],
                             event="timeout", job_id=job_id)


def _collect_result(job, store, pubs_meta, intent, job_id, dispatched_utc, started=None):
    """Wait without the ledger lock; persist actual deadline fallback while the worker waits."""
    def elapsed():
        if started is not None:
            return time.monotonic() - started
        if dispatched_utc:
            return max(0.0, (datetime.now(timezone.utc) - datetime.fromisoformat(dispatched_utc)).total_seconds())
        return None

    def receive():
        try:
            result = job.result()
            error = None
        except Exception as exc:
            result, error = None, f"{type(exc).__name__}:{exc}"
        return result, error, datetime.now(timezone.utc).isoformat(), elapsed()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(receive)
        spent = elapsed()
        remaining = max(0.0, LIVE_DEADLINE_SECONDS - spent) if spent is not None else 0.0
        try:
            result, error, received, duration = future.result(timeout=remaining)
        except concurrent.futures.TimeoutError:
            _deadline_fallback(store, pubs_meta, intent, job_id, elapsed() or LIVE_DEADLINE_SECONDS)
            result, error, received, duration = future.result()
    metrics = _safe_metrics(job)
    if error:
        if _safe_status(job) not in {"ERROR", "CANCELLED"}:
            return {"ok": False, "unresolved": True, "reason": "RESULT_RETRIEVAL_FAILED", "error": error}
        decoded = {"pubs": [], "n_pubs": 0, "result_error": error}
    else:
        try:
            decoded = decode_primitive_result(result)
        except Exception as exc:
            # Preserve an uninterpretable terminal payload without inventing shots.
            from qiskit_ibm_runtime.utils import RuntimeEncoder
            try:
                serialised = json.loads(json.dumps(result, cls=RuntimeEncoder))
            except Exception:
                serialised = {"type": type(result).__name__, "repr": repr(result)}
            write_json_atomic(store.raw_dir / f"{job_id}_undecoded.json", {
                "evidence_type": "undecoded_provider_payload", "job_id": job_id,
                "payload": serialised, "received_utc": received})
            decoded = {"pubs": [], "n_pubs": 0, "result_error": f"{type(exc).__name__}:{exc}"}
    return {"decoded": decoded, "received_utc": received, "elapsed_s": duration, "metrics": metrics}


class ArchivedJob:
    """Receipt-only recovery. Supplies no usage estimate, synthetic status, or provider data."""
    def __init__(self, archive):
        self.archive = archive

    def usage(self):
        return None

    def status(self):
        return self.archive.get("status")

    def metrics(self):
        return self.archive.get("metrics")


def resume_block(*, adapter=None, store=None):
    store = store or DEFAULT_STORE
    store.ensure()
    with store.lock():
        ledger = store.load_ledger()
        outstanding = ledger.get("outstanding_job")
        if not outstanding:
            return {"blocked": True, "ok": False, "reason": "NO_OUTSTANDING_JOB",
                    "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0, "did_call_run": False}
        outstanding = dict(outstanding)
    job_id, intent = outstanding.get("job_id"), outstanding.get("intent")
    tags = list(outstanding.get("tags") or [])
    raw_path = store.raw_dir / f"{job_id}.json" if job_id else None
    existing = json.loads(raw_path.read_text()) if raw_path and raw_path.is_file() else None
    need_provider = not existing or existing.get("usage_state") != "resolved"
    if adapter is None and need_provider:
        from .budget import bind_open_plan
        bound = bind_open_plan()
        if not bound.get("bound") or not bound.get("service"):
            return {"blocked": True, "ok": False, "reason": "RESUME_SERVICE_UNAVAILABLE",
                    "job_id": job_id, "did_call_run": False, "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0}
        service = bound["service"]
        adapter = PhysicalAdapter(service.backend(json.loads((DERIVED_DIR / "backend_pin.json").read_text())["backend"]), service)
    try:
        if job_id is None:
            recovered = adapter.retrieve_by_tags(tags) if adapter is not None and tags else []
            if len(recovered) != 1:
                return {"blocked": True, "ok": False, "reason": "AMBIGUOUS_SUBMISSION_NO_JOB_ID",
                        "intent": intent, "did_call_run": False, "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0}
            job_id = job_id_of(recovered[0])
            with store.lock():
                ledger = store.load_ledger()
                if not ledger.get("outstanding_job") or ledger["outstanding_job"].get("intent") != intent:
                    return {"ok": False, "reason": "ATTEMPT_CHANGED", "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0}
                ledger["outstanding_job"]["job_id"] = job_id
                store.save_ledger(ledger)
                _persist_job_index(store, job_id, {"intent": intent, "tags": tags, "recovered": True})
            raw_path = store.raw_dir / f"{job_id}.json"
            existing = json.loads(raw_path.read_text()) if raw_path.is_file() else None
        job = adapter.retrieve(job_id) if adapter is not None else ArchivedJob(existing)
    except Exception as exc:
        if existing and existing.get("usage_state") == "resolved":
            job = ArchivedJob(existing)
        else:
            return {"ok": False, "unresolved": True, "reason": "RESUME_RETRIEVAL_FAILED",
                    "error": f"{type(exc).__name__}:{exc}", "job_id": job_id,
                    "did_call_run": False, "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0}
    attempt_path = store.attempts_dir / f"{intent}.json"
    attempt = json.loads(attempt_path.read_text()) if attempt_path.is_file() else {}
    pubs_meta = (existing or {}).get("pub_mapping") or attempt.get("pubs") or []
    if existing:
        decoded = {"pubs": existing.get("pubs"), "n_pubs": existing.get("n_pubs_observed"),
                   "result_error": existing.get("result_error")}
        dispatched = existing.get("created_utc") or attempt.get("dispatched_utc")
        received = existing.get("result_received_utc")
        elapsed = existing.get("client_elapsed_seconds")
        metrics = _safe_metrics(job) or existing.get("metrics")
        charge = existing.get("charged_usage_seconds") if existing.get("usage_state") == "resolved" else None
    else:
        dispatched = attempt.get("dispatched_utc")
        collected = _collect_result(job, store, pubs_meta, intent, job_id, dispatched)
        if collected.get("unresolved"):
            return {**collected, "job_id": job_id, "did_call_run": False, "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0}
        decoded, received, elapsed = collected["decoded"], collected["received_utc"], collected["elapsed_s"]
        metrics, charge = collected["metrics"], None
    with store.lock():
        out = finalise_attempt(store=store, adapter=adapter, job=job, job_id=job_id, intent=intent,
            pubs_meta=pubs_meta, tags=tags, decoded=decoded, usage_seconds=charge,
            physical=bool(outstanding.get("physical")), dispatched_utc=dispatched,
            received_utc=received, elapsed_s=elapsed, metrics=metrics)
    out.update(resumed=True, did_call_run=False, NEW_PHYSICAL_QPU_JOBS_SUBMITTED=0)
    return out


def interrupted_dispatch_then_resume(store: CampaignStore | None = None) -> dict[str, Any]:
    """Crash after run and ID persist, then resume with a fresh adapter object."""
    if store is None:
        import tempfile
        from pathlib import Path

        store = CampaignStore(Path(tempfile.mkdtemp(prefix="decision-mock-")), label="mock_interrupt")
    sampler = FakeSamplerV2()
    service = FakeService()
    adapter = InjectedAdapter(sampler, service)
    first = dispatch_block(physical=False, adapter=adapter, store=store, live_remaining=1000.0, usage_seconds=2.0)
    first_calls = sampler.run_calls
    ledger = store.load_ledger()
    if ledger.get("outstanding_job"):
        ledger["outstanding_job"]["job_id"] = first["job_id"]
        store.save_ledger(ledger)
    raw = store.raw_dir / f"{first['job_id']}.json"
    if raw.is_file():
        raw.unlink()
        ledger = store.load_ledger()
        ledger["outstanding_job"] = {
            "intent": first["intent"],
            "job_id": first["job_id"],
            "tags": [f"decision-{first['intent'][:8]}", "decision-study"],
            "physical": False,
        }
        ledger["jobs_submitted"] = max(0, int(ledger.get("jobs_submitted", 1)) - 1)
        ledger["history"] = [item for item in ledger.get("history", []) if item.get("job_id") != first["job_id"]]
        ledger["usage_reconciled_seconds"] = 0.0
        if ledger.get("frozen_allowance_seconds") is not None:
            ledger["campaign_remaining_seconds"] = float(ledger["frozen_allowance_seconds"])
        for item in ledger.get("reservations", []):
            if item.get("intent") == first["intent"]:
                item["open"] = True
        store.save_ledger(ledger)
    fresh_sampler = FakeSamplerV2()
    fresh_sampler.jobs = sampler.jobs
    fresh_service = FakeService()
    fresh_service.jobs = dict(sampler.jobs)
    fresh = InjectedAdapter(fresh_sampler, fresh_service)
    resumed = resume_block(adapter=fresh, store=store)
    return {
        "first_run_calls": first_calls,
        "resume_run_calls": fresh_sampler.run_calls,
        "duplicate": fresh_sampler.run_calls > 0,
        "job_id": first["job_id"],
        "n_pubs": 12,
        "shots": 1024,
        "max_execution_time": 45,
        "evidence_type": "sampled_simulation",
        "resumed": resumed,
    }
