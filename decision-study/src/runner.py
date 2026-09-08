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
                return list(self.service.jobs(limit=50) or [])
        return []


def _persist_job_index(store: CampaignStore, job_id: str, payload: dict[str, Any]) -> None:
    index = {}
    if store.jobs_index_path.is_file():
        index = json.loads(store.jobs_index_path.read_text(encoding="utf-8"))
    index[job_id] = payload
    write_json_atomic(store.jobs_index_path, index)


def _job_usage_report(job: Any, usage_seconds: float | None) -> dict[str, Any]:
    if usage_seconds is not None:
        return {"state": "resolved", "seconds": float(usage_seconds), "final_zero": float(usage_seconds) == 0.0, "raw": usage_seconds}
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
                apply_policy(
                    policy,
                    spec,
                    shots,
                    incumbent,
                    now_elapsed=elapsed,
                    linkage=linkage,
                    trusted_source=spec,
                )
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
    elapsed_s: float,
    metrics: Any = None,
) -> dict[str, Any]:
    usage = _job_usage_report(job, usage_seconds)
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
        "status": job.status() if callable(getattr(job, "status", None)) else getattr(job, "status", None),
        "metrics": metrics,
        "tags": tags,
        "shots_valid": n_ok,
        "label": store.label if not physical else None,
    }
    write_json_atomic(store.raw_dir / f"{job_id}.json", archive)
    policy_rows = _evaluate_policies(decoded, pubs_meta or [], intent, elapsed_s)
    write_json_atomic(store.derived_dir / f"policies_{job_id}.json", {"intent": intent, "job_id": job_id, "rows": policy_rows})
    decisions = {}
    if store.decisions_path.is_file():
        decisions = json.loads(store.decisions_path.read_text(encoding="utf-8"))
    if intent not in decisions:
        decisions[intent] = {"job_id": job_id, "policy_rows": policy_rows, "final": True}
        write_json_atomic(store.decisions_path, decisions)
    ledger = store.load_ledger()
    if _already_finalised(ledger, job_id):
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
        write_json_atomic(store.attempts_dir / f"{intent}.json", {"intent": intent, "pubs": pubs_meta, "tags": tags})
        dispatched_utc = datetime.now(timezone.utc).isoformat()
        started = time.monotonic()
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

    from .agents import Bus, Coordinator, Encoder, Message, SolverAdapter, Validator

    bus = Bus()
    coordinator = Coordinator(persist_path=store.decisions_path)
    bus.register(coordinator)

    def encode_fn(payload):
        return payload

    def solve_fn(payload):
        return payload

    def validate_fn(payload):
        return {"request_id": payload.get("request_id") or intent, "event": payload.get("event"), "ok": True}

    bus.register(Encoder(encode_fn))
    bus.register(SolverAdapter(solve_fn, hold=True))
    bus.register(Validator(validate_fn))
    bus.post("dispatch", "spec.ready", {"request_id": intent}, "coordinator")
    bus.drain()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(job.result)
        bus.post("dispatch", "timeout", {"request_id": intent}, "coordinator")
        bus.drain()
        result_obj = future.result()
    received_utc = datetime.now(timezone.utc).isoformat()
    elapsed = time.monotonic() - started
    try:
        decoded = decode_primitive_result(result_obj)
    except Exception as exc:
        return {
            "ok": False,
            "unresolved": True,
            "reason": "RESULT_DECODE_FAILED",
            "job_id": jid,
            "intent": intent,
            "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 1 if getattr(adapter, "physical", False) else 0,
            "error": f"{type(exc).__name__}:{exc}",
        }
    metrics = None
    try:
        metrics = job.metrics() if hasattr(job, "metrics") else None
    except Exception:
        metrics = None
    with store.lock():
        out = finalise_attempt(
            store=store,
            adapter=adapter,
            job=job,
            job_id=jid,
            intent=intent,
            pubs_meta=pubs_meta,
            tags=tags,
            decoded=decoded,
            usage_seconds=usage_seconds,
            physical=bool(getattr(adapter, "physical", False)),
            dispatched_utc=dispatched_utc,
            received_utc=received_utc,
            elapsed_s=elapsed,
            metrics=metrics,
        )
    out["run_calls"] = getattr(getattr(adapter, "sampler", adapter), "run_calls", getattr(adapter, "run_calls", 1))
    return out


def resume_block(
    *,
    adapter: InjectedAdapter | PhysicalAdapter | None = None,
    store: CampaignStore | None = None,
) -> dict[str, Any]:
    store = store or DEFAULT_STORE
    store.ensure()
    with store.lock():
        ledger = store.load_ledger()
        outstanding = ledger.get("outstanding_job")
        if not outstanding:
            return {"blocked": True, "ok": False, "reason": "NO_OUTSTANDING_JOB", "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0}
        job_id = outstanding.get("job_id")
        tags = list(outstanding.get("tags") or [])
        intent = outstanding.get("intent")
        if job_id is None:
            if adapter is None:
                return {
                    "blocked": True,
                    "ok": False,
                    "reason": "AMBIGUOUS_SUBMISSION_NO_JOB_ID",
                    "intent": intent,
                    "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0,
                    "did_call_run": False,
                }
            recovered = adapter.retrieve_by_tags(tags) if tags else []
            if len(recovered) != 1:
                return {
                    "blocked": True,
                    "ok": False,
                    "reason": "AMBIGUOUS_SUBMISSION_NO_JOB_ID",
                    "intent": intent,
                    "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0,
                    "did_call_run": False,
                }
            job_id = job_id_of(recovered[0])
            outstanding["job_id"] = job_id
            store.save_ledger(ledger)
        raw_path = store.raw_dir / f"{job_id}.json"
        attempt_path = store.attempts_dir / f"{intent}.json" if intent else None
        pubs_meta = None
        if attempt_path and attempt_path.is_file():
            pubs_meta = json.loads(attempt_path.read_text(encoding="utf-8")).get("pubs")
        if adapter is None and not raw_path.is_file():
            from .budget import bind_open_plan

            bound = bind_open_plan()
            if not bound.get("bound"):
                return {"blocked": True, "ok": False, "reason": "RESUME_SERVICE_UNAVAILABLE", "job_id": job_id, "did_call_run": False}
            adapter = PhysicalAdapter(
                bound["service"].backend(json.loads((DERIVED_DIR / "backend_pin.json").read_text())["backend"]),
                bound["service"],
            )
        if raw_path.is_file():
            existing = json.loads(raw_path.read_text(encoding="utf-8"))
            decoded = {"pubs": existing.get("pubs"), "n_pubs": existing.get("n_pubs_observed") or len(existing.get("pubs") or [])}
            pubs_meta = existing.get("pub_mapping") or pubs_meta
            job = None
            if adapter is not None:
                try:
                    job = adapter.retrieve(job_id)
                except Exception:
                    job = None
            if job is None:
                from .runtime_adapter import FakePrimitiveResult, FakePubResult, FakeRuntimeJob

                pubs = [FakePubResult(row.get("shots") or []) for row in (existing.get("pubs") or [])]
                job = FakeRuntimeJob(job_id, FakePrimitiveResult(pubs), tags=tags)
            now = datetime.now(timezone.utc).isoformat()
            out = finalise_attempt(
                store=store,
                adapter=adapter,
                job=job,
                job_id=job_id,
                intent=intent,
                pubs_meta=pubs_meta,
                tags=tags,
                decoded=decoded,
                usage_seconds=existing.get("charged_usage_seconds") if existing.get("usage_state") == "resolved" else None,
                physical=bool(outstanding.get("physical")),
                dispatched_utc=existing.get("created_utc") or now,
                received_utc=existing.get("result_received_utc") or now,
                elapsed_s=float(existing.get("client_elapsed_seconds") or 0.0),
                metrics=existing.get("metrics"),
            )
            out["resumed"] = True
            out["did_call_run"] = False
            return out
        job = adapter.retrieve(job_id)
        decoded = decode_primitive_result(job.result())
        now = datetime.now(timezone.utc).isoformat()
        out = finalise_attempt(
            store=store,
            adapter=adapter,
            job=job,
            job_id=job_id,
            intent=intent,
            pubs_meta=pubs_meta,
            tags=tags,
            decoded=decoded,
            usage_seconds=None,
            physical=bool(outstanding.get("physical") or getattr(adapter, "physical", False)),
            dispatched_utc=now,
            received_utc=now,
            elapsed_s=0.0,
        )
        out["resumed"] = True
        out["did_call_run"] = False
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
