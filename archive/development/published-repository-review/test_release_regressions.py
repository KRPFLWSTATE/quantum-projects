"""Offline review regressions for published commit 3f5b139.

Run: python test_release_regressions.py /path/to/decision-study
These tests express required behaviour and intentionally fail on that commit.
All dispatch calls use an injected fake provider and temporary campaign storage.
No IBM credentials or network access are used.
"""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

if len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
    STUDY = Path(sys.argv.pop(1)).resolve()
else:
    STUDY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDY))

from src.runner import InjectedAdapter, dispatch_block, resume_block
from src.runtime_adapter import FakeSamplerV2, FakeService, FakeRuntimeJob, FakePrimitiveResult, FakePubResult
from src.store import CampaignStore
from src.readiness import engineering_status


class ReleaseRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='offline-release-review-')
        self.addCleanup(self.temp.cleanup)
        self.store = CampaignStore(Path(self.temp.name), label='review_mock')
        self.store.ensure()
        self.sampler = FakeSamplerV2()
        self.service = FakeService()
        self.adapter = InjectedAdapter(self.sampler, self.service)

    def dispatch(self, **kwargs):
        return dispatch_block(physical=False, adapter=self.adapter, store=self.store,
                              live_remaining=554.0, **kwargs)

    def outstanding(self):
        job = self.sampler.run([object()] * 12, shots=1024)
        self.service.jobs[job.job_id()] = job
        ledger = self.store.load_ledger()
        ledger['outstanding_job'] = {'job_id': job.job_id(), 'intent': 'review-intent', 'physical': False}
        ledger['reservations'] = [{'intent': 'review-intent', 'seconds': 45, 'open': True}]
        self.store.save_ledger(ledger)
        return job

    def test_documented_float_usage_archives_and_reconciles(self):
        # RuntimeJobV2.usage in the installed 0.49.0 package returns a scalar.
        with patch.object(FakeRuntimeJob, 'usage', return_value=2.0):
            result = self.dispatch()
        self.assertTrue(result['ok'])
        ledger = self.store.load_ledger()
        self.assertEqual(ledger['usage_reconciled_seconds'], 2.0)
        self.assertEqual(ledger['campaign_remaining_seconds'], 298.0)
        self.assertTrue(list(self.store.raw_dir.glob('*.json')))

    def test_unknown_usage_keeps_reservation(self):
        with patch.object(FakeRuntimeJob, 'usage', return_value=None):
            self.dispatch()
        ledger = self.store.load_ledger()
        self.assertTrue(any(r.get('open') for r in ledger['reservations']),
                        'Unknown usage was cleared instead of retaining its reservation')

    def test_malformed_pub_count_is_not_success(self):
        one_short_pub = FakePrimitiveResult([FakePubResult(['000111'])])
        with patch.object(FakeRuntimeJob, 'result', return_value=one_short_pub):
            result = self.dispatch(usage_seconds=2.0)
        self.assertFalse(result.get('ok'), 'One PUB with one shot was reported successful')

    def test_resume_accounts_for_charged_usage(self):
        self.outstanding()
        with patch.object(FakeRuntimeJob, 'usage', return_value=2.0):
            result = resume_block(adapter=self.adapter, store=self.store)
        self.assertTrue(result['ok'])
        ledger = self.store.load_ledger()
        self.assertEqual(ledger['usage_reconciled_seconds'], 2.0)
        self.assertEqual(ledger['campaign_remaining_seconds'], 298.0)

    def test_existing_raw_does_not_leave_campaign_stuck(self):
        job = self.outstanding()
        resume_block(adapter=self.adapter, store=self.store)
        # Reconstruct the crash boundary: raw exists, but final ledger update was not saved.
        ledger = self.store.load_ledger()
        ledger['outstanding_job'] = {'job_id': job.job_id(), 'intent': 'review-intent', 'physical': False}
        ledger['reservations'][0]['open'] = True
        self.store.save_ledger(ledger)
        result = resume_block(adapter=self.adapter, store=self.store)
        self.assertTrue(result['ok'])
        self.assertIsNone(self.store.load_ledger()['outstanding_job'])
        self.assertFalse(any(r.get('open') for r in self.store.load_ledger()['reservations']))

    def test_corrupted_protocol_blocks_readiness(self):
        # All source study files remain untouched; only the protocol reference is patched.
        corrupted = Path(self.temp.name) / 'corrupt-protocol.json'
        corrupted.write_text(json.dumps({'protocol_hash': 'not-a-valid-frozen-protocol'}))
        with patch('src.readiness.PROTOCOL_PATH', corrupted):
            result = engineering_status(live_usage={'remaining_seconds': 554.0,
                                                    'bound': True, 'plan': 'open'})
        self.assertFalse(result['ready_for_first_hardware'])
        self.assertTrue(result['blockers'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
