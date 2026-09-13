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
            "docs/claim-evidence-limitation.md",
            "docs/contribution-note.md",
            "docs/archive-zip-navigation.md",
            "docs/related-work.md",
            "archive/historical-public-docs/related-work-handoff.md",
            "archive/historical-exports/CHECKSUMS.md",
            "archive/development/PATH_MAP.json",
            "dba-qpu-run/README.md",
        ):
            self.assertTrue((REPO / rel).is_file(), rel)


    def test_export_inventory_closed(self):
        from publication.export import missing_inventory, source_inventory

        rels = {str(p.relative_to(REPO)).replace("\\", "/") for p in source_inventory()}
        self.assertIn("decision-study/tools/verify_isa.py", rels)
        self.assertTrue(any("ibm-runtime-exports/run_01" in r for r in rels))
        self.assertFalse(any(r.endswith(".zip") for r in rels))
        self.assertFalse(any("/dist/" in r for r in rels))
        self.assertEqual(missing_inventory(), [])

    def test_default_output_does_not_write_publication(self):
        from publication.paths import PUBLICATION, validate_output_root
        from pathlib import Path

        validate_output_root(REPO / "build" / "reproduction")
        with self.assertRaises(ValueError):
            validate_output_root(REPO / "decision-study" / "data" / "raw" / "out")

    def test_p2_metadata_only_not_version_gate(self):
        from src.fixtures import hardware_instances
        from src.policies import apply_policy
        from src.spec import spec_from_instance

        inst = hardware_instances()[0]
        spec = spec_from_instance(inst, request_id="t-p2-meta")
        drifted = dict(spec)
        drifted["current_version"] = "label-only"
        greedy_bits = "011001"
        linkage = {
            "request_id": spec["request_id"],
            "source_hash": spec["source_hash"],
            "circuit_hash": "c",
            "expected_circuit_hash": "c",
            "expected_request_id": spec["request_id"],
            "expected_source_hash": spec["source_hash"],
        }
        out = apply_policy("P2", drifted, [greedy_bits] * 8, None, 1.0, linkage, trusted_source=spec)
        self.assertNotEqual(out.get("reason"), "VERSION_MISMATCH")

    def test_ibm_tripwire(self):
        from publication.ibm_guard import OfflineIbmBlocked, install_tripwires
        import qiskit_ibm_runtime

        install_tripwires()
        with self.assertRaises(OfflineIbmBlocked):
            qiskit_ibm_runtime.QiskitRuntimeService()

    def test_publication_output_rejected(self):
        from publication.paths import PUBLICATION, validate_output_root
        import tempfile

        with self.assertRaises(ValueError):
            validate_output_root(PUBLICATION)
        with self.assertRaises(ValueError):
            validate_output_root(PUBLICATION / "tables")
        nested = PUBLICATION / "nested-out"
        with self.assertRaises(ValueError):
            validate_output_root(nested)

    def test_wrong_isa_identity_fails(self):
        from publication.metrics import evaluate_pub, instance_catalog

        pubs = json.loads((RAW / "dagjoc8mhr3c73e58uk0.json").read_text())
        meta = dict(pubs["pub_mapping"][0])
        meta["isa_qpy_sha256"] = "deliberately-wrong-test-digest"
        catalog = instance_catalog()
        with self.assertRaises(ValueError) as ctx:
            evaluate_pub(pubs, pubs["pubs"][0], meta, catalog, 1.0)
        self.assertIn("ISA", str(ctx.exception))

    def test_duplicate_mapping_fails_validation(self):
        from publication.job_validation import validate_physical_job_archive

        data = json.loads((RAW / "dagjoc8mhr3c73e58uk0.json").read_text())
        data["pub_mapping"] = list(data["pub_mapping"]) + [data["pub_mapping"][0]]
        with self.assertRaises(ValueError):
            validate_physical_job_archive(data, job_id=data["job_id"], ledger_row=None, attempt=None)

    def test_missing_mapping_combo_fails(self):
        from publication.job_validation import validate_physical_job_archive

        data = json.loads((RAW / "dagjoc8mhr3c73e58uk0.json").read_text())
        data["pub_mapping"] = data["pub_mapping"][:11]
        data["pubs"] = data["pubs"][:11]
        with self.assertRaises(ValueError):
            validate_physical_job_archive(data, job_id=data["job_id"], ledger_row=None, attempt=None)

    def test_export_includes_path_map_and_legacy_readme(self):
        from publication.export import source_inventory

        rels = {str(p.relative_to(REPO)).replace("\\", "/") for p in source_inventory()}
        self.assertIn("archive/development/PATH_MAP.json", rels)
        self.assertIn("dba-qpu-run/README.md", rels)
        self.assertIn("dba-qpu-run/run_circuit.py", rels)
        self.assertIn("decision-study/tools/verify_isa.py", rels)

    def test_dictionary_version_matches_analysis(self):
        from publication import ANALYSIS_VERSION
        from publication.dictionary import DATA_DICTIONARY

        self.assertEqual(ANALYSIS_VERSION, "publication-analysis-v3")
        self.assertEqual(DATA_DICTIONARY["analysis_version"], ANALYSIS_VERSION)

    def test_refresh_same_directory_rejected(self):
        from reproduce import _refresh_publication
        from publication.paths import PUBLICATION
        import sys

        sys.path.insert(0, str(REPO / "tools"))
        with self.assertRaises(ValueError):
            _refresh_publication(PUBLICATION)

    def test_isa_failure_leaves_prior_generation(self):
        import tempfile
        from unittest.mock import patch
        import reproduce

        marker = {"tables": True}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "rebuild"
            out.mkdir()
            prior = out / "tables"
            prior.mkdir()
            (prior / "sentinel.txt").write_text("keep-me", encoding="utf-8")

            def fake_run(*args, **kwargs):
                class R:
                    returncode = 1
                    stderr = "forced-isa-failure"
                    stdout = ""
                return R()

            with patch.object(reproduce.subprocess, "run", side_effect=fake_run):
                code = reproduce.run(out, refresh_publication=False)
            self.assertEqual(code, 1)
            self.assertTrue((out / "tables" / "sentinel.txt").is_file())
            self.assertTrue((out / "diagnostics" / "errors.json").is_file())
            self.assertFalse((out / "analysis_manifest.json").exists())

    def test_refresh_copy_failure_restores(self):
        import tempfile
        from unittest.mock import patch
        import reproduce
        from publication.paths import PUBLICATION

        with tempfile.TemporaryDirectory() as tmp:
            fake_pub = Path(tmp) / "publication"
            fake_pub.mkdir()
            (fake_pub / "keep.json").write_text("{\"ok\": true}", encoding="utf-8")
            src = Path(tmp) / "good-src"
            for name in reproduce.REQUIRED_GENERATION:
                p = src / name
                if name.endswith(".json"):
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text("{}", encoding="utf-8")
                else:
                    p.mkdir(parents=True)
                    (p / "x.txt").write_text("x", encoding="utf-8")
            original_copy = reproduce.shutil.copytree

            def boom(*args, **kwargs):
                raise OSError("injected copy failure")

            with patch.object(reproduce, "PUBLICATION", fake_pub), patch.object(
                reproduce, "PUBLICATION_BACKUP_ROOT", Path(tmp) / "backups"
            ), patch.object(reproduce.shutil, "copytree", side_effect=boom):
                with self.assertRaises(OSError):
                    reproduce._refresh_publication(src)
            self.assertTrue((fake_pub / "keep.json").is_file())

    def test_refresh_success_from_isolated_tree(self):
        import tempfile
        import reproduce
        from publication.paths import PUBLICATION

        with tempfile.TemporaryDirectory() as tmp:
            fake_pub = Path(tmp) / "publication"
            fake_pub.mkdir()
            (fake_pub / "old.txt").write_text("old", encoding="utf-8")
            src = Path(tmp) / "good-src"
            for name in reproduce.REQUIRED_GENERATION:
                p = src / name
                if name.endswith(".json"):
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text('{"fresh": true}', encoding="utf-8")
                else:
                    p.mkdir(parents=True)
                    (p / "fresh.txt").write_text("fresh", encoding="utf-8")
            with patch_publication(reproduce, fake_pub, Path(tmp) / "backups"):
                reproduce._refresh_publication(src)
            self.assertTrue((fake_pub / "tables" / "fresh.txt").is_file())
            self.assertFalse((fake_pub / "old.txt").exists())


def patch_publication(reproduce_mod, fake_pub, backup_root):
    from unittest.mock import patch

    return patch.multiple(
        reproduce_mod,
        PUBLICATION=fake_pub,
        PUBLICATION_BACKUP_ROOT=backup_root,
        HISTORICAL_PUBLICATION_BACKUP=backup_root / "historical-untouched",
    )


if __name__ == "__main__":
    unittest.main()
