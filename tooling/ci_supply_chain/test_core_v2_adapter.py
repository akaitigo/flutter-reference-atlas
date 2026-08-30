# SPDX-License-Identifier: Apache-2.0

import copy
import unittest

from tooling.ci_supply_chain import core_v2_adapter as adapter


class CoreV2AdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (
            cls.inventory,
            cls.matrix,
            cls.depth,
            cls.skill_eval,
            cls.skill_router,
        ) = adapter.build_documents()

    def validate(self, inventory=None, matrix=None, depth=None, skill_eval=None, skill_router=None):
        adapter.validate_documents(
            inventory or self.inventory,
            matrix or self.matrix,
            depth or self.depth,
            skill_eval or self.skill_eval,
            skill_router or self.skill_router,
        )

    def test_preserves_complete_provisional_denominator(self):
        self.assertEqual(len(self.inventory["items"]), 54)
        self.assertEqual(len(self.matrix["rows"]), 540)
        self.assertTrue(all(row["applicability"] == "required" for row in self.matrix["rows"]))

    def test_surface_omission_is_rejected(self):
        inventory = copy.deepcopy(self.inventory)
        inventory["items"].pop()
        with self.assertRaisesRegex(adapter.AdapterError, "54 Surface"):
            self.validate(inventory=inventory)

    def test_matrix_omission_is_rejected(self):
        matrix = copy.deepcopy(self.matrix)
        matrix["rows"].pop()
        with self.assertRaisesRegex(adapter.AdapterError, "540 row"):
            self.validate(matrix=matrix)

    def test_gap_cannot_retreat_to_not_applicable(self):
        matrix = copy.deepcopy(self.matrix)
        matrix["rows"][0]["applicability"] = "not-applicable"
        with self.assertRaisesRegex(adapter.AdapterError, "not-applicable"):
            self.validate(matrix=matrix)

    def test_fabricated_scenario_evidence_id_is_rejected(self):
        matrix = copy.deepcopy(self.matrix)
        matrix["rows"][0]["evidence_ids"] = ["proof.fabricated"]
        with self.assertRaisesRegex(adapter.AdapterError, "実在Scenario Proof ID"):
            self.validate(matrix=matrix)

    def test_fabricated_target_is_rejected(self):
        inventory = copy.deepcopy(self.inventory)
        inventory["items"][0]["target_id"] = "target.fabricated"
        with self.assertRaisesRegex(adapter.AdapterError, "架空Target"):
            self.validate(inventory=inventory)

    def test_depth_partial_axis_cannot_be_promoted(self):
        depth = copy.deepcopy(self.depth)
        depth["completion_status"] = "parity"
        with self.assertRaisesRegex(adapter.AdapterError, "parityへ昇格"):
            self.validate(depth=depth)

    def test_skill_gaps_and_forward_eval_cannot_be_promoted(self):
        router = copy.deepcopy(self.skill_router)
        router["status"] = "subject-skill-ready"
        with self.assertRaisesRegex(adapter.AdapterError, "readyへ昇格"):
            self.validate(skill_router=router)

    def test_only_exact_current_promotion_gap_is_accepted(self):
        expected = adapter.expected_promotion_gap()
        adapter.validate_expected_audit(1, "Error: " + expected, expected)
        with self.assertRaisesRegex(adapter.AdapterError, "期待する現在Gap"):
            adapter.validate_expected_audit(1, "surface.inventory.yaml missing", expected)
        with self.assertRaisesRegex(adapter.AdapterError, "成功してはいけません"):
            adapter.validate_expected_audit(0, "Subject Definitive監査済み", expected)


if __name__ == "__main__":
    unittest.main()
