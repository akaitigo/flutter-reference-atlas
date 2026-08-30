# SPDX-License-Identifier: Apache-2.0
import copy
import json
import unittest

from tooling.scenario_security_tranche.artifact_migration import MANIFEST, MigrationError, ROOT, expected_documents


class ArtifactMigrationTest(unittest.TestCase):
    def test_all_mappings_bind_current_result_and_replacement_digest(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        documents = expected_documents(ROOT, manifest)
        self.assertEqual(len(documents), 4)
        self.assertTrue(all(b'proof-eligible="false"' in content for content in documents.values()))

    def test_missing_mapping_is_rejected(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        weakened = copy.deepcopy(manifest)
        weakened["mappings"].pop()
        with self.assertRaisesRegex(MigrationError, "exactly four"):
            expected_documents(ROOT, weakened)


if __name__ == "__main__":
    unittest.main()
