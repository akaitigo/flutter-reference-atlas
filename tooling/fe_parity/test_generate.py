import json
import unittest
from pathlib import Path

from tooling.fe_parity.generate import generate


ROOT = Path(__file__).resolve().parents[2]


class FlutterDepthParityTest(unittest.TestCase):
    def test_uses_exactly_the_locked_eighteen_axes(self):
        lock = json.loads((ROOT / "definitive/fe-depth-reference.lock.json").read_text())
        value = generate(ROOT)
        self.assertEqual(len(value["axes"]), 18)
        self.assertEqual([item["id"] for item in value["axes"]], [item["id"] for item in lock["axes"]])

    def test_does_not_transplant_frontend_absolute_counts(self):
        value = generate(ROOT)
        self.assertFalse(value["denominator_policy"]["transplant_fe_absolute_counts"])
        self.assertEqual(value["denominator_policy"]["state"], "provisional-unreviewed")

    def test_authority_axis_remains_partial_until_full_text_is_reviewed(self):
        value = generate(ROOT)
        authority = next(item for item in value["axes"] if item["id"] == "authority-body-digestion")
        self.assertEqual(authority["status"], "partial")
        self.assertFalse(value["denominator_policy"]["authority_text_surfaces_exhaustive"])
        self.assertEqual(value["denominator_policy"]["authority_human_reviewed_surfaces"], 0)

    def test_raw_anchors_never_count_as_semantic_surfaces(self):
        value = generate(ROOT)
        self.assertFalse(value["denominator_policy"]["raw_anchors_count_as_semantic_surfaces"])
        self.assertGreater(value["denominator_policy"]["authority_raw_anchors"], 0)
        self.assertEqual(value["denominator_policy"]["authority_raw_anchors"], value["denominator_policy"]["authority_pending_human_anchors"])

    def test_review_queue_is_complete_but_never_depth_credit(self):
        value = generate(ROOT)
        policy = value["denominator_policy"]
        self.assertFalse(policy["review_queue_count_as_semantic_surfaces"])
        self.assertEqual(policy["authority_review_pending"], policy["authority_raw_anchors"])
        authority_axis = next(item for item in value["axes"] if item["id"] == "authority-body-digestion")
        queue_check = next(item for item in authority_axis["checks"] if item["id"] == "authority.human-review-queue")
        review_check = next(item for item in authority_axis["checks"] if item["id"] == "authority.human-review")
        self.assertEqual(queue_check["status"], "pass")
        self.assertEqual(review_check["status"], "gap")

    def test_skill_matrix_pass_does_not_mask_routing_or_forward_gaps(self):
        value = generate(ROOT)
        policy = value["denominator_policy"]
        self.assertEqual(policy["definitive_skill_matrix_cells"], 112)
        self.assertEqual(policy["definitive_skill_matrix_passed"], 112)
        self.assertFalse(policy["skill_matrix_pass_implies_complete"])
        self.assertEqual(policy["independent_agent_forward_executed"], 0)
        skill_axis = next(item for item in value["axes"] if item["id"] == "skill-eval")
        self.assertEqual(skill_axis["status"], "partial")
        self.assertEqual(next(item for item in skill_axis["checks"] if item["id"] == "skill.8-outcome-14-surface")["status"], "pass")
        self.assertEqual(next(item for item in skill_axis["checks"] if item["id"] == "skill.agent-execution")["status"], "gap")

    def test_integrated_reference_trace_does_not_mask_surface_scenario_gaps(self):
        value = generate(ROOT)
        policy = value["denominator_policy"]
        self.assertEqual(policy["scenario_proof_rows"], 540)
        self.assertEqual(policy["scenario_integrated_trace_rows"], 540)
        self.assertGreater(policy["scenario_surface_runtime_gap_rows"], 0)
        self.assertEqual(policy["scenario_authority_atomic_rows"], 0)
        self.assertEqual(policy["scenario_completion_eligible_rows"], 0)
        self.assertFalse(policy["integrated_trace_substitutes_surface_proof"])
        for axis_id in (
            "scenario-normal", "scenario-boundary", "scenario-refusal", "scenario-failure", "scenario-recovery",
            "scenario-migration", "scenario-operations", "scenario-security", "scenario-performance", "scenario-compatibility",
        ):
            scenario_axis = next(item for item in value["axes"] if item["id"] == axis_id)
            self.assertEqual(scenario_axis["status"], "partial")
            self.assertEqual(next(item for item in scenario_axis["checks"] if item["id"].endswith(".integrated-trace"))["status"], "pass")
            self.assertEqual(next(item for item in scenario_axis["checks"] if item["id"].endswith(".authority-atomic-row"))["status"], "gap")


if __name__ == "__main__":
    unittest.main()
