import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DefinitiveMasteryEvalTest(unittest.TestCase):
    def setUp(self):
        self.report = json.loads((ROOT / "evals/flutter-router.definitive-mastery-eval.json").read_text(encoding="utf-8"))
        self.forward = json.loads((ROOT / "evals/flutter-router.agent-forward-eval.json").read_text(encoding="utf-8"))

    def test_matrix_and_boundaries_are_complete_contract_runs(self):
        summary = self.report["summary"]
        self.assertEqual((summary["outcomes"], summary["surfaces"], summary["matrix_cells"]), (8, 14, 112))
        self.assertEqual(summary["passed"], 112)
        self.assertEqual(summary["boundary_passed"], 5)
        self.assertEqual(summary["target_state_cases_passed"], summary["targets"])
        self.assertEqual(len({item["id"] for item in self.report["matrix"]}), 112)
        self.assertTrue(all(all(item["assertions"].values()) for item in self.report["matrix"]))

    def test_routing_runtime_and_target_gaps_remain_visible(self):
        summary = self.report["summary"]
        self.assertEqual(summary["mastery_routing_gaps"], 30)
        self.assertEqual(summary["runtime_evidence_gap_cells"], 24)
        self.assertEqual(summary["target_route_gaps"], 3)
        self.assertEqual(summary["target_states"], {"covered": 23, "infeasible": 2, "partial": 2})
        gap_cells = [item for item in self.report["matrix"] if item["support_status"] == "mastery-routing-gap"]
        self.assertTrue(all(item["target_binding"] is None for item in gap_cells))
        self.assertTrue(all(item["definitive_surface_binding"] is None for item in gap_cells))
        self.assertTrue(all(item["result"] == "pass" for item in self.report["target_state_cases"]))

    def test_fail_closed_boundaries_are_recorded(self):
        boundaries = {item["id"]: item for item in self.report["boundary_cases"]}
        self.assertEqual(boundaries["boundary.ambiguous"]["actual"]["status"], "coverage-gap")
        self.assertEqual(boundaries["boundary.unknown"]["actual"]["status"], "coverage-gap")
        self.assertIn("unauthorized-mutation", boundaries["boundary.unauthorized-build"]["actual"]["blocked_reasons"])
        self.assertIn("external-human-authority-decision-required", boundaries["boundary.human-authority"]["actual"]["blocked_reasons"])
        self.assertIn("stale-source-relock-explicit-procedure-required", boundaries["boundary.stale-relock"]["actual"]["blocked_reasons"])

    def test_matrix_pass_never_claims_completion(self):
        self.assertTrue(self.report["status"].startswith("incomplete-"))
        self.assertEqual(self.report["semantic_scope"], "deterministic-router-contract-not-independent-agent-forward-eval")
        self.assertTrue(any("Matrix pass" in item for item in self.report["completion_limits"]))

    def test_agent_forward_eval_absence_is_machine_recorded(self):
        self.assertEqual(self.forward["status"], "not-executed-required")
        self.assertTrue(self.forward["completion_blocking"])
        self.assertFalse(self.forward["independent_agent"])
        self.assertEqual(self.forward["summary"]["executed"], 0)
        self.assertFalse(self.forward["deterministic_router_matrix_substitutes_forward_eval"])


if __name__ == "__main__":
    unittest.main()
