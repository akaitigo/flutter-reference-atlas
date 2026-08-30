import json
import unittest

from tooling.authority_extraction.body_inventory import extract_anchors, sha256
from tooling.authority_extraction.verify import AuthorityError, assert_no_body_fields


class AuthorityBodyInventoryTest(unittest.TestCase):
    def test_extracts_stable_pending_raw_anchors_without_plaintext(self):
        body = b'''<!doctype html><html><body>
<!-- <h6 id="comment-fake">ignored</h6> -->
<h1 id=top>Title</h1><section id='one'><h2><span id=nested>Sub</span></h2>
<dfn id="term">Term</dfn><table><tr><td>Value</td></tr></table></section>
<script>const x = '<h3 id="script-fake">ignored</h3>';</script></body></html>'''
        digest = sha256(body)
        first = extract_anchors(body, digest, "document-test")
        self.assertEqual(first, extract_anchors(body, digest, "document-test"))
        self.assertEqual(len(first), 6)
        self.assertEqual([item["semantic_kind"] for item in first], ["document-root", "heading", "section", "heading", "definition", "data-table"])
        self.assertTrue(all(item["classification_status"] == "pending-human" for item in first))
        self.assertTrue(all(not item["surface_ids"] and not item["atomic_behavior_ids"] for item in first))
        serialized = json.dumps(first)
        self.assertNotIn("Title", serialized)
        self.assertNotIn("Term", serialized)
        self.assertNotIn("fake", serialized)

    def test_body_field_guard_applies_to_inventory(self):
        with self.assertRaises(AuthorityError):
            assert_no_body_fields({"anchors": [{"excerpt": "forbidden"}]})


if __name__ == "__main__":
    unittest.main()
