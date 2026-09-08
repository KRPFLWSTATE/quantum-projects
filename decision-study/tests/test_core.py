from __future__ import annotations

import json
import unittest
from pathlib import Path
import sys

STUDY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDY_DIR))

from src.fixtures import EXPECTED_FEASIBLE_COUNTS, EXPECTED_OPTIMA, hardware_instances
from src.model import energy_from_definition, energy_from_ising, energy_from_qubo, verify_encodings
from src.oracle import exact_summary
from src.classical import greedy_then_swaps
from src.qaoa import independent_statevector_amplitudes, qiskit_statevector
import numpy as np


class ModelTests(unittest.TestCase):
    def test_encodings_and_expected_optima(self) -> None:
        for instance, n_exp, u_exp in zip(hardware_instances(), EXPECTED_FEASIBLE_COUNTS, EXPECTED_OPTIMA):
            check = verify_encodings(instance)
            self.assertTrue(check["ok"], check["mismatches"])
            summary = exact_summary(instance)
            self.assertEqual(summary["feasible_count"], n_exp)
            self.assertAlmostEqual(summary["optimum_utility"], u_exp)
            self.assertTrue(summary["satisfiable"])

    def test_penalty_dominates(self) -> None:
        for instance in hardware_instances():
            feasible_e = []
            infeasible_e = []
            from src.model import bits_from_int, is_feasible

            for value in range(64):
                bits = bits_from_int(value)
                e = energy_from_definition(instance, bits)
                if is_feasible(instance, bits):
                    feasible_e.append(e)
                else:
                    infeasible_e.append(e)
            self.assertTrue(feasible_e)
            self.assertGreater(min(infeasible_e), max(feasible_e))

    def test_qubo_ising_identity(self) -> None:
        instance = hardware_instances()[0]
        from src.model import bits_from_int

        for value in range(64):
            bits = bits_from_int(value)
            self.assertAlmostEqual(energy_from_definition(instance, bits), energy_from_qubo(instance, bits), places=8)
            self.assertAlmostEqual(energy_from_qubo(instance, bits), energy_from_ising(instance, bits), places=8)


class QaoaTests(unittest.TestCase):
    def test_statevector_agreement(self) -> None:
        instance = hardware_instances()[0]
        a = independent_statevector_amplitudes(instance, [0.2, 0.5], [0.3, 0.1])
        b = qiskit_statevector(instance, [0.2, 0.5], [0.3, 0.1])
        self.assertGreater(abs(np.vdot(a, b)), 1 - 1e-8)
        self.assertAlmostEqual(float(np.sum(np.abs(a) ** 2)), 1.0, places=10)

    def test_greedy_never_uses_infeasible(self) -> None:
        for instance in hardware_instances():
            result = greedy_then_swaps(instance)
            if result["status"] == "ok":
                self.assertTrue(result["feasible"])


class IsolationTests(unittest.TestCase):
    def test_classical_module_does_not_import_oracle(self) -> None:
        source = (STUDY_DIR / "src" / "classical.py").read_text(encoding="utf-8")
        self.assertNotIn("from .oracle", source)
        self.assertNotIn("import oracle", source)

    def test_hardware_disabled(self) -> None:
        from src.hardware import HARDWARE_SUBMIT_ENABLED, submit_sampler_job

        self.assertFalse(HARDWARE_SUBMIT_ENABLED)
        with self.assertRaises(RuntimeError):
            submit_sampler_job()

    def test_no_physical_sampler_submit_in_source(self) -> None:
        root = STUDY_DIR / "src"
        for path in list(root.glob("*.py")) + [STUDY_DIR / "study.py"]:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("Sampler.run(", text)
            self.assertNotIn("session.run", text.lower())


class BudgetGateTests(unittest.TestCase):
    def test_ledger_blocks_outstanding_and_cap(self) -> None:
        from src.ledger import can_submit, default_ledger

        ledger = default_ledger()
        ok, reason = can_submit(ledger, live_free_remaining=1000)
        self.assertTrue(ok)
        ledger["outstanding_job"] = {"job_id": "x"}
        ok, reason = can_submit(ledger, 1000)
        self.assertFalse(ok)
        self.assertEqual(reason, "OUTSTANDING_JOB")
        ledger = default_ledger()
        ledger["jobs_submitted"] = 6
        ok, reason = can_submit(ledger, 1000)
        self.assertEqual(reason, "JOB_CAP_REACHED")
        ledger = default_ledger()
        ok, reason = can_submit(ledger, None)
        self.assertEqual(reason, "BALANCE_UNRESOLVED")
        ledger = default_ledger()
        ledger["reservations"] = [{"open": True, "seconds": 45}]
        ok, reason = can_submit(ledger, 1000)
        self.assertEqual(reason, "UNRESOLVED_INTENT")
    def test_campaign_allowance_uses_usage_remaining_seconds(self) -> None:
        from src.budget import campaign_allowance, _extract_remaining_seconds

        remaining = _extract_remaining_seconds({"usage_remaining_seconds": 554})
        self.assertEqual(remaining, 554.0)
        allowance = campaign_allowance(554)
        self.assertEqual(allowance["allowance_seconds"], 300.0)
        self.assertFalse(allowance["blocked"])


class PolicyTests(unittest.TestCase):
    def test_p2_rejects_version_mismatch_p3_can_revalidate(self) -> None:
        from src.policies import apply_policy
        from src.spec import spec_from_instance
        from src.replay import rotate_benefits

        instance = hardware_instances()[0]
        spec = spec_from_instance(instance, request_id="req-1")
        drifted = rotate_benefits(spec)
        drifted["request_id"] = spec["request_id"]
        greedy = greedy_then_swaps(instance)
        incumbent = {"bitstring": greedy["bitstring"], "utility": greedy["utility"]}
        shots = [greedy["bitstring"]] * 4
        linkage = {
            "request_id": spec["request_id"],
            "source_hash": spec["source_hash"],
            "circuit_hash": "circ-1",
            "expected_circuit_hash": "circ-1",
            "expected_request_id": spec["request_id"],
            "expected_source_hash": spec["source_hash"],
        }
        p2 = apply_policy("P2", drifted, shots, incumbent, 1.0, linkage, trusted_source=spec)
        p3 = apply_policy("P3", drifted, shots, incumbent, 1.0, linkage, trusted_source=spec)
        self.assertNotEqual(p2["status"], "accept")
        self.assertIn(p3["status"], {"accept", "fallback_incumbent", "abstain"})

    def test_actor_monolithic_equivalence(self) -> None:
        from src.agents import run_actor_workflow, run_monolithic

        spec = {"request_id": "abc", "value": 1}

        def encode(payload):
            return {**payload, "encoded": True}

        def solve(payload):
            return {**payload, "candidates": ["000111"]}

        def validate(payload):
            return {"request_id": payload["request_id"], "ok": True, "candidates": payload.get("candidates")}

        actor, trace = run_actor_workflow(spec, encode, solve, validate)
        mono = run_monolithic(spec, encode, solve, validate)
        self.assertEqual(actor["ok"], mono["ok"])
        self.assertTrue(trace)


class LegacyHashTests(unittest.TestCase):
    def test_snapshot_roundtrip(self) -> None:
        expected = json.loads((STUDY_DIR / "data/preservation/legacy_sha256.json").read_text())
        from src.legacy_audit import verify_hashes

        check = verify_hashes(expected)
        self.assertTrue(check["ok"], check)


if __name__ == "__main__":
    unittest.main()
