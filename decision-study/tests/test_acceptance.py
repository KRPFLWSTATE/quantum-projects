from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
import hashlib

STUDY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDY_DIR))

from src.runtime_adapter import FakeSamplerV2, FakeService
from src.runner import InjectedAdapter, dispatch_block, resume_block, interrupted_dispatch_then_resume
from src.store import CampaignStore
from src.agents import Bus, Coordinator, Encoder, Message, SolverAdapter, Validator
from src.policies import apply_policy
from src.fixtures import hardware_instances
from src.spec import spec_from_instance
from src.classical import greedy_then_swaps


def _code_hashes() -> dict[str, str]:
    files = [
        STUDY_DIR / "src" / "runner.py",
        STUDY_DIR / "src" / "hardware.py",
        STUDY_DIR / "src" / "budget.py",
        STUDY_DIR / "src" / "readiness.py",
        STUDY_DIR / "study.py",
    ]
    out = {}
    for path in files:
        out[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


class AcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="decision-acc-"))
        self.store = CampaignStore(self.tmp, label="mock_acceptance")
        self.store.ensure()
        self.sampler = FakeSamplerV2()
        self.service = FakeService()
        self.adapter = InjectedAdapter(self.sampler, self.service)

    def test_mocked_block_twelve_pubs_and_exit_zero(self) -> None:
        result = dispatch_block(
            physical=False,
            adapter=self.adapter,
            store=self.store,
            live_remaining=1000.0,
            usage_seconds=2.0,
        )
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(result["n_pubs"], 12)
        self.assertEqual(self.sampler.last_shots, 1024)
        self.assertEqual(len(self.sampler.last_pubs), 12)
        self.assertEqual(self.sampler.run_calls, 1)
        self.assertNotEqual(result.get("evidence_type"), "decision_hardware")
        raw = json.loads((self.store.raw_dir / f"{result['job_id']}.json").read_text())
        self.assertEqual(raw["evidence_type"], "sampled_simulation")
        self.assertTrue(raw.get("mock"))
        self.assertEqual(len(raw["pubs"]), 12)
        self.assertTrue(all(row["n_shots"] == 1024 for row in raw["pubs"]))
        self.assertEqual(self.adapter.sampler.options.max_execution_time, 45)
        import study as study_mod

        with patch.object(study_mod, "cmd_run_next", return_value={"ok": True, "blocked": False}):
            rc = study_mod.main(["run-next", "--hardware"])
        self.assertEqual(rc, 0)
        self.assertEqual(_code_hashes()["runner.py"], hashlib.sha256((STUDY_DIR / "src" / "runner.py").read_bytes()).hexdigest())

    def test_fresh_resume_does_not_rerun(self) -> None:
        trace = interrupted_dispatch_then_resume(store=self.store)
        self.assertEqual(trace["first_run_calls"], 1)
        self.assertEqual(trace["resume_run_calls"], 0)
        self.assertFalse(trace["duplicate"])
        self.assertTrue(trace["resumed"].get("ok"), trace)

    def test_outstanding_blocks_new_dispatch(self) -> None:
        first = dispatch_block(physical=False, adapter=self.adapter, store=self.store, live_remaining=1000.0, usage_seconds=2.0)
        ledger = self.store.load_ledger()
        ledger["outstanding_job"] = {"intent": first["intent"], "job_id": first["job_id"]}
        self.store.save_ledger(ledger)
        second = dispatch_block(physical=False, adapter=self.adapter, store=self.store, live_remaining=1000.0)
        self.assertTrue(second.get("blocked"))
        self.assertEqual(second["reason"], "OUTSTANDING_JOB")
        self.assertEqual(self.sampler.run_calls, 1)

    def test_gates_block_before_run(self) -> None:
        blocked = dispatch_block(physical=False, adapter=self.adapter, store=self.store, live_remaining=None)
        self.assertEqual(blocked["reason"], "BALANCE_UNRESOLVED")
        self.assertEqual(self.sampler.run_calls, 0)
        ledger = self.store.load_ledger()
        ledger["jobs_submitted"] = 6
        self.store.save_ledger(ledger)
        cap = dispatch_block(physical=False, adapter=self.adapter, store=self.store, live_remaining=1000.0)
        self.assertEqual(cap["reason"], "JOB_CAP_REACHED")
        self.assertEqual(self.sampler.run_calls, 0)
        ledger = self.store.load_ledger()
        ledger["jobs_submitted"] = 0
        ledger["reservations"] = [{"open": True, "seconds": 45}]
        self.store.save_ledger(ledger)
        unresolved = dispatch_block(physical=False, adapter=self.adapter, store=self.store, live_remaining=1000.0)
        self.assertEqual(unresolved["reason"], "UNRESOLVED_INTENT")
        self.assertEqual(self.sampler.run_calls, 0)

    def test_timeout_while_worker_held_and_persistent_decision(self) -> None:
        persist = self.tmp / "decisions.json"
        bus = Bus()
        coord = Coordinator(persist_path=persist)
        bus.register(coord)
        bus.register(Encoder(lambda payload: {**payload, "encoded": True}))
        solver = SolverAdapter(lambda payload: {**payload, "candidates": ["000111"]}, hold=True)
        bus.register(solver)

        def validate(payload):
            return {"request_id": payload.get("request_id", "r1"), "event": payload.get("event"), "ok": True}

        bus.register(Validator(validate))
        bus.post("user", "spec.ready", {"request_id": "r1"}, "coordinator")
        bus.drain()
        self.assertIsNotNone(solver.held)
        bus.post("user", "timeout", {"request_id": "r1"}, "coordinator")
        bus.drain()
        self.assertEqual(coord.decisions["r1"]["event"], "timeout")
        restarted = Coordinator(persist_path=persist)
        self.assertEqual(restarted.decisions["r1"]["event"], "timeout")
        bus.post("validator", "decision.final", {"request_id": "r1", "event": "late"}, "coordinator")
        bus.drain()
        self.assertEqual(coord.decisions["r1"]["event"], "timeout")

    def test_p2_requires_expected_circuit_hash(self) -> None:
        instance = hardware_instances()[0]
        spec = spec_from_instance(instance, request_id="req-acc")
        greedy = greedy_then_swaps(instance)
        incumbent = {"bitstring": greedy["bitstring"], "utility": greedy["utility"]}
        link = {
            "request_id": spec["request_id"],
            "source_hash": spec["source_hash"],
            "circuit_hash": "nonempty-but-untrusted",
        }
        out = apply_policy("P2", spec, [incumbent["bitstring"]], incumbent, 1.0, link, trusted_source=spec)
        self.assertEqual(out["reason"], "MISSING_EXPECTED_CIRCUIT_HASH")
        self.assertNotEqual(out["status"], "accept")

    def test_prepare_does_not_reset_ledger_with_history(self) -> None:
        from src.ledger import default_ledger

        ledger = default_ledger()
        ledger["jobs_submitted"] = 1
        ledger["history"] = [{"job_id": "keep-me"}]
        self.store.save_ledger(ledger)
        loaded = self.store.load_ledger()
        self.assertEqual(loaded["jobs_submitted"], 1)
        self.assertEqual(loaded["history"][0]["job_id"], "keep-me")


if __name__ == "__main__":
    unittest.main()
