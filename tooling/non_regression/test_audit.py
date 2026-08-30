import unittest

from tooling.non_regression.audit import audit, ci_step_is_equal_or_stronger, replacement_is_valid, test_metric


class NonRegressionAuditTest(unittest.TestCase):
    def test_metric_counts_tests_and_assertions(self):
        metric = test_metric("test('kept', () { expect(value, 1); });\n")
        self.assertEqual(metric["test_names"], ["kept"])
        self.assertEqual(metric["test_declaration_count"], 1)
        self.assertEqual(metric["assertion_count"], 1)

    def test_covered_target_cannot_be_weakened(self):
        snapshot = {
            "atlas_id": "atlas",
            "version_and_scope_floor": {"coverage_epoch": "e", "scope_statement": "s", "required_profiles": ["local"], "sdk_baseline": {}},
            "target_sets": {}, "labs": {}, "tests": {}, "capabilities": {}, "claims": {},
            "proof_obligations": {}, "evidence": {}, "artifacts": {}, "sources": {},
            "skill_cases": {}, "skill_forward_cases": {}, "skill_eval_cases": {},
            "ci_jobs": {}, "test_metrics": {},
            "targets": {"t": {"target_set": "s", "kind": "capability", "requirement": "required", "state": "covered", "claim_ids": ["c"], "evidence_ids": ["e"]}},
        }
        current = {**snapshot, "targets": {"t": {**snapshot["targets"]["t"], "state": "infeasible"}}}
        errors = audit(snapshot, current, {"mappings": []})
        self.assertTrue(any("covered state was weakened" in error for error in errors))

    def test_replacement_requires_existing_proof_and_migration_evidence(self):
        mapping = {
            "entity_type": "claims",
            "old_id": "old",
            "new_ids": ["new"],
            "rationale": "より細粒度のClaimへ置換する。",
            "migration_evidence_ids": ["migration.evidence"],
            "equivalent_or_stronger_proof_ids": ["proof.stronger"],
        }
        current = {
            "claims": {"new": {}},
            "evidence": {"migration.evidence": {}},
            "proof_obligations": {"proof.stronger": {}},
        }
        self.assertTrue(replacement_is_valid(mapping, current))
        current["evidence"] = {}
        self.assertFalse(replacement_is_valid(mapping, current))

    def test_ci_action_tag_can_only_be_strengthened_to_same_action_sha(self):
        expected = {"uses": "actions/checkout@v4"}
        pinned = {"uses": "actions/checkout@11d5960a326750d5838078e36cf38b85af677262"}
        wrong_action = {"uses": "example/checkout@11d5960a326750d5838078e36cf38b85af677262"}
        self.assertTrue(ci_step_is_equal_or_stronger(expected, pinned))
        self.assertFalse(ci_step_is_equal_or_stronger(expected, wrong_action))
        self.assertFalse(ci_step_is_equal_or_stronger(pinned, expected))

    def test_checkout_tag_can_be_pinned_and_full_history_added(self):
        expected = {"uses": "actions/checkout@v4"}
        full_history = {
            "uses": "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            "with": {"fetch-depth": 0},
        }
        shallow = {**full_history, "with": {"fetch-depth": 1}}
        self.assertTrue(ci_step_is_equal_or_stronger(expected, full_history))
        self.assertFalse(ci_step_is_equal_or_stronger(expected, shallow))


if __name__ == "__main__":
    unittest.main()
