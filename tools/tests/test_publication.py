from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "decision-study"))

from publication.campaign import campaign_status  # noqa: E402
from publication.export import write_research_archive  # noqa: E402
from publication.hashes import verify_legacy_hashes, verify_protocol  # noqa: E402
from publication.metrics import instance_catalog, pub_rows  # noqa: E402
from publication.paths import LEDGER, RAW, REPO_ROOT  # noqa: E402


class PublicationTests(unittest.TestCase):
    def test_campaign_complete_while_submit_blocked(self):
        status = campaign_status()
        self.assertEqual(status["campaign_status"], "COMPLETE")
        self.assertEqual(status["submission_gate"], "JOB_CAP_REACHED")
        self.assertTrue(status["complete"])

    def test_protocol_and_legacy_hashes(self):
        proto = verify_protocol()
        self.assertTrue(proto["ok"], proto)
        legacy = verify_legacy_hashes()
        self.assertTrue(legacy["ok"], legacy)
        self.assertEqual(legacy["n_expected"], 65)

    def test_malformed_pub_fails(self):
        pubs = pub_rows()
        self.assertEqual(len(pubs), 72)
        bad = json.loads((RAW / "dagjoc8mhr3c73e58uk0.json").read_text())
        bad["pubs"][0]["shots"] = bad["pubs"][0]["shots"][:10]
        from publication.metrics import evaluate_pub, instance_catalog
        catalog = instance_catalog()
        meta = bad["pub_mapping"][0]
        with self.assertRaises(ValueError):
            evaluate_pub(bad, bad["pubs"][0], meta, catalog, 1.0)

    def test_counts_match_shots(self):
        from collections import Counter
        for path in RAW.glob("*.json"):
            data = json.loads(path.read_text())
            self.assertEqual(data.get("evidence_type"), "decision_hardware")
            self.assertFalse(data.get("mock"))
            mapping = {int(m["pub_index"]): m for m in data["pub_mapping"]}
            self.assertEqual(len(data["pubs"]), 12)
            for pub in data["pubs"]:
                shots = pub["shots"]
                self.assertEqual(len(shots), 1024)
                self.assertEqual(Counter(shots), {k: int(v) for k, v in pub["counts"].items()})
                self.assertIn(int(pub["pub_index"]), mapping)

    def test_offline_export_sidecar(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            result = write_research_archive(Path(tmp), members=[REPO / "LICENSE", REPO / "CITATION.cff"])
            zip_path = Path(result["zip"])
            sidecar = Path(result["sidecar"])
            self.assertEqual(sidecar.read_text().strip(), result["sha256"])
            import zipfile
            with zipfile.ZipFile(zip_path) as zf:
                self.assertIn("ARCHIVE_MANIFEST.json", zf.namelist())
                self.assertTrue(all("chatgpt_return_packet" not in n for n in zf.namelist()))

    def test_replay_labels(self):
        from publication.replay_analysis import hardware_pool_map
        from src.replay import replay_fixture
        from src.fixtures import hardware_instances

        pools = hardware_pool_map()
        key = next(iter(sorted(pools)))
        job_id, fixture, depth = key
        inst = {i.instance_id: i for i in hardware_instances()}[fixture]
        replayed = replay_fixture(inst, pools[key])
        self.assertIn("unchanged:P2", replayed["results"])
        self.assertIn("bad_linkage:P2", replayed["results"])
        self.assertEqual(replayed["results"]["empty:P1"].get("status") in {"abstain", "fallback_incumbent", "accept"}, True)

    def test_ledger_unmodified_path(self):
        self.assertTrue(LEDGER.is_file())
        self.assertEqual(json.loads(LEDGER.read_text())["jobs_submitted"], 6)

    def test_doc_links_resolve(self):
        for rel in (
            "docs/reproduce.md",
            "docs/methods.md",
            "docs/results.md",
            "docs/data-and-provenance.md",
            "docs/architecture-and-policies.md",
            "docs/limitations-and-contributions.md",
            "requirements-repro.txt",
            "CITATION.cff",
            "archive/development/PATH_MAP.json",
        ):
            self.assertTrue((REPO / rel).is_file(), rel)


if __name__ == "__main__":
    unittest.main()
