# SPDX-License-Identifier: Apache-2.0
import unittest

from tooling.ci_supply_chain.verify import violations


class CiSupplyChainVerifyTest(unittest.TestCase):
    def test_full_sha_is_accepted(self):
        workflow = "steps:\n  - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262\n"
        self.assertEqual(violations(workflow, "ci.yml"), [])

    def test_mutable_tag_regression_is_rejected(self):
        workflow = "steps:\n  - uses: actions/checkout@v4\n  - uses: subosito/flutter-action@v2\n"
        errors = violations(workflow, "ci.yml")
        self.assertEqual(len(errors), 2)
        self.assertTrue(all("mutable or invalid action reference" in error for error in errors))

    def test_short_sha_is_rejected(self):
        errors = violations("steps:\n  - uses: actions/setup-go@40f1582\n", "ci.yml")
        self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
