"""Single dispatch/resume path. Physical IBM run is CLI opt-in only; tests inject an adapter and temp store."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from qiskit import qpy

from .hashing import sha256_file, write_json_atomic
from .ledger import can_submit
from .paths import DERIVED_DIR, STUDY_ROOT
from .readiness import engineering_status
from .runtime_adapter import FakeSamplerV2, FakeService, decode_primitive_result, job_id_of
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

    def submit(self, pubs, shots: int = 1024):
        job = self.sampler.run(pubs, shots=shots)
        self.service.jobs[job_id_of(job)] = job
        self.sampler.jobs[job_id_of(job)] = job
        return job

    def retrieve(self, job_id: str):
        return self.service.job(job_id)


class PhysicalAdapter:
    def __init__(self, backend, service) -> None:
        self.backend = backend
        self.service = service
        self.backend_name = backend.name
        self.physical = True
        self.run_calls = 0

    def submit(self, pubs, shots: int = 1024):
        from .hardware import run_physical_block

        self.run_calls += 1
        return run_physical_block(self.backend, pubs, shots=shots)

    def retrieve(self, job_id: str):
        return self.service.job(job_id)


def _persist_job_index(store: CampaignStore, job_id: str, payload: dict[str, Any]) -> None:
    index = {}
    if store.jobs_index_path.is_file():
        index = json.loads(store.jobs_index_path.read_text(encoding="utf-8"))
    index[job_id] = payload
    write_json_atomic(store.jobs_index_path, index)


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
        from qiskit_ibm_runtime import QiskitRuntimeService

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
        if estimate_path.is_file():
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
        ledger["outstanding_job"] = {"intent": intent, "job_id": None, "tags": tags, "physical": bool(physical and adapter and getattr(adapter, "physical", False))}
        store.save_ledger(ledger)
        try:
            circuits, pubs_meta = load_isa_pubs(pubs_meta_plan)
        except Exception as exc:
            reservation["open"] = True
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
        try:
            job = adapter.submit(circuits, shots=1024)
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
        try:
            decoded = decode_primitive_result(job.result())
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
        charged = usage_seconds
        if charged is None:
            usage = job.usage() if hasattr(job, "usage") else {}
            charged = float((usage or {}).get("quantum_seconds") or (usage or {}).get("qpu_usage") or 0.0)
        archive = {
            "evidence_type": "decision_hardware" if getattr(adapter, "physical", False) else "sampled_simulation",
            "mock": not getattr(adapter, "physical", False),
            "job_id": jid,
            "intent": intent,
            "pubs": decoded["pubs"],
            "pub_mapping": pubs_meta,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "charged_usage_seconds": charged,
            "status": job.status() if callable(getattr(job, "status", None)) else getattr(job, "status", None),
        }
        if archive["evidence_type"] != "decision_hardware":
            archive["label"] = store.label
        write_json_atomic(store.raw_dir / f"{jid}.json", archive)
        n_ok = len(decoded["pubs"]) == 12 and all(int(row["n_shots"]) == 1024 for row in decoded["pubs"])
        ledger["jobs_submitted"] = int(ledger.get("jobs_submitted", 0)) + 1
        ledger["outstanding_job"] = None
        reservation["open"] = False
        reservation["job_id"] = jid
        ledger["usage_reconciled_seconds"] = float(ledger.get("usage_reconciled_seconds", 0.0)) + float(charged or 0.0)
        remaining = float(ledger.get("campaign_remaining_seconds", 0.0)) - max(float(charged or 0.0), 0.0)
        ledger["campaign_remaining_seconds"] = max(0.0, remaining)
        ledger.setdefault("history", []).append(
            {
                "intent": intent,
                "job_id": jid,
                "mock": not getattr(adapter, "physical", False),
                "physical": getattr(adapter, "physical", False),
                "shots_valid": n_ok,
            }
        )
        store.save_ledger(ledger)
        write_json_atomic(
            store.derived_dir / "last_dispatch.json",
            {
                "intent": intent,
                "job_id": jid,
                "n_pubs": decoded["n_pubs"],
                "shots": [row["n_shots"] for row in decoded["pubs"]],
                "shots_valid": n_ok,
                "evidence_type": archive["evidence_type"],
                "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 1 if getattr(adapter, "physical", False) else 0,
            },
        )
        physical_count = 1 if getattr(adapter, "physical", False) else 0
        return {
            "ok": True,
            "blocked": False,
            "mock": not getattr(adapter, "physical", False),
            "job_id": jid,
            "intent": intent,
            "n_pubs": 12,
            "shots_valid": n_ok,
            "run_calls": getattr(getattr(adapter, "sampler", adapter), "run_calls", getattr(adapter, "run_calls", 1)),
            "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": physical_count,
        }


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
        if job_id is None:
            return {
                "blocked": True,
                "ok": False,
                "reason": "AMBIGUOUS_SUBMISSION_NO_JOB_ID",
                "intent": outstanding.get("intent"),
                "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0,
                "did_call_run": False,
            }
        raw = store.raw_dir / f"{job_id}.json"
        if raw.is_file():
            return {"ok": True, "resumed": True, "job_id": job_id, "did_call_run": False, "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0}
        if adapter is None:
            from .budget import bind_open_plan

            bound = bind_open_plan()
            if not bound.get("bound"):
                return {"blocked": True, "ok": False, "reason": "RESUME_SERVICE_UNAVAILABLE", "job_id": job_id, "did_call_run": False}
            adapter = PhysicalAdapter(bound["service"].backend(json.loads((DERIVED_DIR / "backend_pin.json").read_text())["backend"]), bound["service"])
        job = adapter.retrieve(job_id)
        decoded = decode_primitive_result(job.result())
        write_json_atomic(
            store.raw_dir / f"{job_id}.json",
            {
                "evidence_type": "sampled_simulation" if not getattr(adapter, "physical", False) else "decision_hardware",
                "mock": not getattr(adapter, "physical", False),
                "job_id": job_id,
                "intent": outstanding.get("intent"),
                "pubs": decoded["pubs"],
                "resumed": True,
            },
        )
        for item in ledger.get("reservations", []):
            if item.get("intent") == outstanding.get("intent"):
                item["open"] = False
                item["job_id"] = job_id
        ledger["jobs_submitted"] = int(ledger.get("jobs_submitted", 0)) + 1
        ledger["outstanding_job"] = None
        store.save_ledger(ledger)
        return {"ok": True, "resumed": True, "job_id": job_id, "did_call_run": False, "NEW_PHYSICAL_QPU_JOBS_SUBMITTED": 0}


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
            "tags": [f"decision-{first['intent'][:8]}"],
            "physical": False,
        }
        ledger["jobs_submitted"] = max(0, int(ledger.get("jobs_submitted", 1)) - 1)
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
