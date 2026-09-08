from __future__ import annotations

import unittest
from pathlib import Path
import sys

STUDY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDY_DIR))

from src.agents import Coordinator, Message, Bus, run_actor_workflow, run_monolithic
from src.budget import _extract_remaining_seconds
from src.fixtures import hardware_instances
from src.policies import apply_policy
from src.runner import interrupted_dispatch_then_resume, dispatch_block
from src.spec import spec_from_instance, recompute_current
from src.classical import greedy_then_swaps
from src.optimiser import _refine
import numpy as np


class RepairPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.instance = hardware_instances()[0]
        self.spec = spec_from_instance(self.instance, request_id="req-d1")
        greedy = greedy_then_swaps(self.instance)
        self.incumbent = {"bitstring": greedy["bitstring"], "utility": greedy["utility"]}
        self.link = {
            "request_id": self.spec["request_id"],
            "source_hash": self.spec["source_hash"],
            "circuit_hash": "c1",
            "expected_circuit_hash": "c1",
            "expected_request_id": self.spec["request_id"],
            "expected_source_hash": self.spec["source_hash"],
        }

    def test_p3_rejects_missing_linkage(self) -> None:
        out = apply_policy("P3", self.spec, [self.incumbent["bitstring"]], self.incumbent, 1.0, {}, trusted_source=self.spec)
        self.assertIn(out["reason"], {"MISSING_LINKAGE", "MISSING_EXPECTED_CIRCUIT_HASH"})
        self.assertNotEqual(out["status"], "accept")

    def test_p3_rejects_wrong_source_hash(self) -> None:
        bad = dict(self.link, source_hash="nope")
        out = apply_policy("P3", self.spec, [self.incumbent["bitstring"]], self.incumbent, 1.0, bad, trusted_source=self.spec)
        self.assertNotEqual(out["status"], "accept")

    def test_p3_rejects_unflagged_meaning_change(self) -> None:
        changed = dict(self.spec)
        changed["variable_meanings"] = list(self.spec["variable_meanings"])
        changed["variable_meanings"][0] = "different organisational object"
        changed = recompute_current(changed, self.spec)
        out = apply_policy("P3", changed, [self.incumbent["bitstring"]], self.incumbent, 1.0, self.link, trusted_source=self.spec)
        self.assertNotEqual(out["status"], "accept")

    def test_forged_incumbent_not_trusted(self) -> None:
        fake = {"bitstring": "000111", "utility": 999}
        out = apply_policy("P3", self.spec, [], fake, 1.0, self.link, trusted_source=self.spec)
        self.assertEqual(out["status"], "abstain")
        self.assertEqual(out["reason"], "NO_VALID_INCUMBENT")

    def test_malformed_candidate_does_not_raise(self) -> None:
        out = apply_policy("P3", self.spec, ["bad"], self.incumbent, 1.0, self.link, trusted_source=self.spec)
        self.assertIn(out["status"], {"fallback_incumbent", "abstain", "accept"})
        self.assertIn("bad", out.get("invalid_candidates", []))


class RepairCoordinatorTests(unittest.TestCase):
    def test_final_decision_immutable(self) -> None:
        bus = Bus()
        coord = Coordinator()
        bus.register(coord)
        first = {"request_id": "r1", "choice": "a"}
        second = {"request_id": "r1", "choice": "b"}
        coord.handle(Message("decision.final", first, "validator"), bus)
        coord.handle(Message("decision.final", second, "validator"), bus)
        self.assertEqual(coord.decisions["r1"]["choice"], "a")


class RepairBudgetTests(unittest.TestCase):
    def test_minutes_not_treated_as_seconds(self) -> None:
        self.assertEqual(_extract_remaining_seconds({"period": {"remaining": 8, "unit": "minutes"}}), 480.0)
        self.assertEqual(_extract_remaining_seconds({"remaining": 8, "unit": "minutes"}), 480.0)
        self.assertIsNone(_extract_remaining_seconds({"remaining": 8}))
        self.assertIsNone(_extract_remaining_seconds({"period": {"remaining": 8, "unit": "hours"}}))
        self.assertIsNone(_extract_remaining_seconds({"remaining": float("nan"), "unit": "seconds"}))


class RepairRunnerTests(unittest.TestCase):
    def test_fake_run_resume_no_duplicate(self) -> None:
        trace = interrupted_dispatch_then_resume()
        self.assertEqual(trace["first_run_calls"], 1)
        self.assertEqual(trace["resume_run_calls"], 0)
        self.assertFalse(trace["duplicate"])
        self.assertEqual(trace["n_pubs"], 12)
        self.assertEqual(trace["shots"], 1024)
        self.assertEqual(trace["max_execution_time"], 45)
        self.assertEqual(trace["evidence_type"], "sampled_simulation")


class RepairOptimiserTests(unittest.TestCase):
    def test_best_callback_point_retained(self) -> None:
        instance = hardware_instances()[0]
        # A start that is already a grid-evaluated finite point; callback must keep a finite best.
        result = _refine(instance, np.array([0.3, 0.4], dtype=float), 1)
        self.assertTrue(result["retained_best_callback_point"])
        self.assertTrue(np.isfinite(result["fun"]))


if __name__ == "__main__":
    unittest.main()
