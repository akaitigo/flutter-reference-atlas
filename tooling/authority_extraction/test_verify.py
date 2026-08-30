import unittest

from tooling.authority_extraction.extract import locate
from tooling.authority_extraction.verify import AuthorityError, assert_no_body_fields


class AuthorityExtractionTest(unittest.TestCase):
    def test_locator_keeps_digest_and_byte_offsets_only(self):
        body = b'<html><h2 id="lifecycle">Lifecycle</h2><p>third party prose</p></html>'
        result = locate(body, "https://example.invalid/spec#lifecycle", "sha256:" + "0" * 64)
        self.assertEqual(result["locator_status"], "fragment-found")
        self.assertEqual(result["context_unit"], "byte")
        self.assertNotIn("body", result)
        self.assertNotIn("text", result)
        self.assertNotIn("excerpt", result)

    def test_verifier_rejects_body_field_at_any_depth(self):
        for field in ("body", "content", "excerpt", "quote", "raw_body", "response_text", "text"):
            with self.subTest(field=field), self.assertRaises(AuthorityError):
                assert_no_body_fields({"fetch": {field: "must not be stored"}})

    def test_metadata_fields_are_allowed(self):
        assert_no_body_fields({"source_url": "https://example.invalid", "content_type": "text/html", "context_digest": "sha256:" + "0" * 64})


if __name__ == "__main__":
    unittest.main()
