import unittest

from tooling.authority_extraction.body_baseline import build


class AuthorityBodyBaselineTest(unittest.TestCase):
    def test_baseline_uses_stable_document_and_anchor_ids(self):
        value = build()
        document_ids = [item["id"] for item in value["documents"]]
        anchor_ids = [anchor for item in value["documents"] for anchor in item["anchor_ids"]]
        self.assertEqual(len(document_ids), len(set(document_ids)))
        self.assertEqual(len(anchor_ids), len(set(anchor_ids)))
        self.assertEqual(value["unique_documents"], len(document_ids))


if __name__ == "__main__":
    unittest.main()
