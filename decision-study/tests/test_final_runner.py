"""Real runner boundaries with injected providers and isolated storage; no IBM calls."""
import json
import tempfile
import threading
import time
import unittest
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from src import runner
from src.runtime_adapter import FakeRuntimeJob, FakeSamplerV2, FakeService, interpret_usage
from src.store import CampaignStore


class FinalRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = CampaignStore(Path(self.tmp.name), label="final_review_mock")
        self.store.ensure()
        self.sampler = FakeSamplerV2()
        self.service = FakeService()
        self.adapter = runner.InjectedAdapter(self.sampler, self.service)

    def dispatch(self):
        return runner.dispatch_block(physical=False, adapter=self.adapter,
                                     store=self.store, live_remaining=554.0)

    def test_done_job_with_pending_billing_is_not_final_zero(self):
        metrics = {"timestamps": {"finished": "2026-09-09T00:00:00Z"},
                   "usage": {"status": "pending", "qpu_charge_time_seconds": 3.1}}
        self.assertNotEqual(interpret_usage(0.0, metrics=metrics, status="DONE")["state"], "resolved")

    def test_final_zero_requires_billing_completion(self):
        metrics = {"usage": {"status": "completed", "qpu_charge_time_seconds": 0}}
        self.assertEqual(interpret_usage(0.0, metrics=metrics, status="DONE")["seconds"], 0.0)
        for raw in (float("nan"), float("inf"), -1.0):
            self.assertNotEqual(interpret_usage(raw)["state"], "resolved")

    def test_default_resume_never_substitutes_fake_usage(self):
        with patch.object(FakeRuntimeJob, "usage", return_value=None):
            first = self.dispatch()
        ledger = self.store.load_ledger()
        with patch("src.budget.bind_open_plan", return_value={"bound": False}), \
             patch.object(FakeRuntimeJob, "usage", side_effect=AssertionError("fake charge used")) as fake_usage:
            result = runner.resume_block(store=self.store)
        fake_usage.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertEqual(self.store.load_ledger()["usage_reconciled_seconds"], 0)
        self.assertTrue(self.store.load_ledger()["outstanding_job"])

    def test_default_resume_recovers_missing_id_by_provider_tags(self):
        with patch.object(FakeRuntimeJob, "usage", return_value=None):
            first = self.dispatch()
        ledger = self.store.load_ledger()
        ledger["outstanding_job"].update(job_id=None)
        self.store.save_ledger(ledger)
        # Patch only connection construction, so the default resume path is exercised.
        bound_service = type("Bound", (), {"backend": lambda self, name: object()})()
        with patch("src.budget.bind_open_plan", return_value={"bound": True, "service": bound_service}), \
             patch.object(runner, "PhysicalAdapter", return_value=self.adapter):
            result = runner.resume_block(store=self.store)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["job_id"], first["job_id"])
        self.assertEqual(result["NEW_PHYSICAL_QPU_JOBS_SUBMITTED"], 0)

    def test_delayed_worker_has_real_fallback_and_no_ledger_lock(self):
        entered, release, done = threading.Event(), threading.Event(), threading.Event()
        original = FakeRuntimeJob.result
        outcomes = []
        def held(job):
            entered.set()
            release.wait(3)
            return original(job)
        def run():
            try:
                outcomes.append(self.dispatch())
            finally:
                done.set()
        with patch.object(FakeRuntimeJob, "result", held), patch.object(runner, "LIVE_DEADLINE_SECONDS", 0.05):
            worker = threading.Thread(target=run)
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                limit = time.monotonic() + 2
                while not self.store.decisions_path.exists() and time.monotonic() < limit:
                    done.wait(0.01)
                with self.store.lock():
                    decisions = json.loads(self.store.decisions_path.read_text())
                self.assertTrue(decisions)
                self.assertTrue(all(r["event"] == "timeout" for r in decisions.values()))
                self.assertTrue(all(r["elapsed_seconds"] >= 0.05 for r in decisions.values()))
                self.assertTrue(all(r["status"] == "fallback_incumbent" for r in decisions.values()))
            finally:
                release.set()
                worker.join(3)
        self.assertTrue(outcomes[0]["ok"])
        final = json.loads(self.store.decisions_path.read_text())
        for key, decision in decisions.items():
            self.assertEqual(final[key], decision)

    def test_failed_job_is_archived_and_counted_once(self):
        with patch.object(FakeRuntimeJob, "result", side_effect=RuntimeError("provider job failed")), \
             patch.object(FakeRuntimeJob, "status", return_value="ERROR"):
            result = self.dispatch()
        self.assertFalse(result["ok"])
        ledger = self.store.load_ledger()
        self.assertEqual(ledger["jobs_submitted"], 1)
        self.assertEqual(ledger["usage_reconciled_seconds"], 2.0)
        self.assertIsNone(ledger["outstanding_job"])
        archive = json.loads((self.store.raw_dir / f"{result['job_id']}.json").read_text())
        self.assertEqual(archive["status"], "ERROR")
        self.assertFalse(archive["shots_valid"])

    def test_actual_qiskit_result_container_is_decoded(self):
        from qiskit.primitives.containers import BitArray, DataBin, SamplerPubResult, PrimitiveResult
        result_obj = PrimitiveResult([SamplerPubResult(DataBin(
            meas=BitArray.from_samples(["000111"] * 1024, num_bits=6))) for _ in range(12)])
        with patch.object(FakeRuntimeJob, "result", return_value=result_obj):
            result = self.dispatch()
        self.assertTrue(result["ok"], result)
        raw = json.loads((self.store.raw_dir / f"{result['job_id']}.json").read_text())
        self.assertEqual(len(raw["pubs"]), 12)
        self.assertTrue(all(r["counts"] == {"000111": 1024} for r in raw["pubs"]))
        self.assertEqual(raw["evidence_type"], "sampled_simulation")
        self.assertEqual(self.sampler.run_calls, 1)

    def test_receipt_is_archived_before_usage_query(self):
        def query(job):
            self.assertTrue((self.store.raw_dir / f"{job.job_id()}.json").is_file())
            return 2.0
        with patch.object(FakeRuntimeJob, "usage", query):
            result = self.dispatch()
        self.assertTrue(result["ok"], result)

    def test_quick_result_is_not_an_immediate_timeout(self):
        result = self.dispatch()
        decisions = json.loads(self.store.decisions_path.read_text())
        self.assertTrue(decisions)
        self.assertFalse(any(r.get("event") == "timeout" for r in decisions.values()))
        self.assertTrue(all("policy" in r or "policy_rows" in r for r in decisions.values()))

    def test_dispatch_timestamp_survives_interruption(self):
        with patch.object(FakeRuntimeJob, "result", side_effect=ConnectionError("test interruption")):
            try:
                self.dispatch()
            except ConnectionError:
                pass
        attempt = json.loads(next(self.store.attempts_dir.glob("*.json")).read_text())
        self.assertTrue(attempt.get("dispatched_utc"))
        result = runner.resume_block(adapter=self.adapter, store=self.store)
        raw = json.loads((self.store.raw_dir / f"{result['job_id']}.json").read_text())
        self.assertEqual(raw["created_utc"], attempt["dispatched_utc"])
        self.assertGreater(raw["client_elapsed_seconds"], 0)
        self.assertEqual(result["NEW_PHYSICAL_QPU_JOBS_SUBMITTED"], 0)

    def test_resume_in_a_fresh_python_process(self):
        program = r'''
import json, sys
from pathlib import Path
from types import SimpleNamespace
from src.runner import InjectedAdapter, dispatch_block, resume_block
from src.runtime_adapter import FakeSamplerV2, FakeService, decode_primitive_result
from src.store import CampaignStore
root, phase = Path(sys.argv[1]), sys.argv[2]
store = CampaignStore(root, label="fresh_process_mock")
provider = root / "offline_provider.json"
if phase == "dispatch":
    class Interrupted(InjectedAdapter):
        def submit(self, pubs, shots=1024, tags=None):
            job = super().submit(pubs, shots, tags)
            provider.write_text(json.dumps({"job_id":job.job_id(), "result":decode_primitive_result(job.result())}))
            def broken():
                raise ConnectionError("injected disconnect after provider accepted")
            job.result = broken
            return job
    adapter = Interrupted(FakeSamplerV2(), FakeService())
    out = dispatch_block(physical=False, adapter=adapter, store=store, live_remaining=554.0)
    assert out["unresolved"] and adapter.sampler.run_calls == 1
else:
    class DiskRetrieval:
        physical = False
        def submit(self, *args, **kwargs):
            raise AssertionError("resume attempted another submission")
        def retrieve(self, job_id):
            payload = json.loads(provider.read_text())
            assert payload["job_id"] == job_id
            return SimpleNamespace(result=lambda: payload["result"], usage=lambda: 3.25,
                                   status=lambda: "DONE", job_id=lambda: job_id)
    out = resume_block(adapter=DiskRetrieval(), store=store)
    assert out["ok"] and out["NEW_PHYSICAL_QPU_JOBS_SUBMITTED"] == 0
    ledger = store.load_ledger()
    assert ledger["jobs_submitted"] == 1 and ledger["usage_reconciled_seconds"] == 3.25
    assert not ledger["outstanding_job"]
    assert all(not row["open"] for row in ledger["reservations"])
    raw = json.loads((store.raw_dir / (out["job_id"] + ".json")).read_text())
    assert raw["evidence_type"] == "sampled_simulation" and len(raw["pub_mapping"]) == 12
'''
        for phase in ("dispatch", "resume"):
            result = subprocess.run([sys.executable, "-c", program, str(self.store.root), phase],
                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
