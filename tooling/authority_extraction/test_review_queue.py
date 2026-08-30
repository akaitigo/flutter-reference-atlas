import copy
import unittest

from tooling.authority_extraction.review_queue import build, expected_binding, validate_decisions
from tooling.authority_extraction.verify import AuthorityError


class AuthorityReviewQueueTest(unittest.TestCase):
    def test_all_eligible_anchors_start_pending_human(self):
        built = build()
        items = [item for batch in built["batches"] for item in batch["items"]]
        self.assertEqual(len(items), len(set(item["anchor_id"] for item in items)))
        self.assertEqual(sorted(item["anchor_id"] for item in items), built["eligible_anchor_ids"])
        self.assertTrue(all(item["state"] == "pending-human" for item in items))
        self.assertFalse(built["index"]["summary"]["queue_count_as_semantic_surfaces"])
        self.assertGreater(built["index"]["summary"]["stale_document_holds"], 0)

    def test_human_decision_requires_exact_digest_locator_mapping_and_result(self):
        built = build()
        item = built["batches"][0]["items"][0]
        decision = {
            "decision_id": "decision.contract-test.include", "action": "include", "anchor_ids": [item["anchor_id"]],
            "source_bindings": [expected_binding(item)],
            "rationale": "一次資料のlocatorと固定digestを人が確認し、独立したobservable surfaceとして扱う理由を記録した。",
            "reviewer": "human-reviewer", "reviewed_at": "2026-08-28T12:00:00+09:00", "review_method": "manual-primary-source",
            "mapping": [{"old_anchor_id": item["anchor_id"], "new_item_ids": ["surface.contract-test"]}],
            "result_items": [{"id": "surface.contract-test", "item_type": "surface"}],
        }
        item_by_id = {item["anchor_id"]: item}
        self.assertEqual(validate_decisions([decision], item_by_id), {item["anchor_id"]})
        automated = copy.deepcopy(decision)
        automated["reviewer"] = "automated-bot"
        with self.assertRaisesRegex(AuthorityError, "人手"):
            validate_decisions([automated], item_by_id)
        drifted = copy.deepcopy(decision)
        drifted["source_bindings"][0]["context_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(AuthorityError, "digest/locator"):
            validate_decisions([drifted], item_by_id)
        unmapped = copy.deepcopy(decision)
        unmapped["result_items"] = []
        with self.assertRaisesRegex(AuthorityError, "mappingとSurface/Atomic behavior"):
            validate_decisions([unmapped], item_by_id)


if __name__ == "__main__":
    unittest.main()
