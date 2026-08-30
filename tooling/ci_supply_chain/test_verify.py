# SPDX-License-Identifier: Apache-2.0
import unittest

from tooling.ci_supply_chain.verify import (
    checkout_history_violations,
    sdk_binding_violations,
    violations,
)


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

    def test_subject_checkout_requires_full_history(self):
        workflow = """jobs:
  validate:
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          fetch-depth: 0
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          repository: akaitigo/reference-atlas-core
"""
        self.assertEqual(checkout_history_violations(workflow, "ci.yml"), [])

    def test_shallow_subject_checkout_is_rejected(self):
        workflow = """jobs:
  validate:
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          fetch-depth: 1
"""
        self.assertEqual(len(checkout_history_violations(workflow, "ci.yml")), 1)

    def test_implicit_shallow_subject_checkout_is_rejected(self):
        workflow = """jobs:
  validate:
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
      - name: verify
        run: make validate
"""
        self.assertEqual(len(checkout_history_violations(workflow, "ci.yml")), 1)

    def test_formal_and_runtime_gates_share_action_sdk(self):
        workflow = '''
      - name: sdk binding
        run: |
          test -n "$FLUTTER_ROOT"
          echo "FORMAL_SDK=$FLUTTER_ROOT" >> "$GITHUB_ENV"
          echo "FLUTTER_ATLAS_SDK_ROOT=$FLUTTER_ROOT" >> "$GITHUB_ENV"
'''
        self.assertEqual(sdk_binding_violations(workflow, "ci.yml"), [])

    def test_missing_runtime_sdk_binding_is_rejected(self):
        workflow = '''
      - name: sdk binding
        run: |
          test -n "$FLUTTER_ROOT"
          echo "FORMAL_SDK=$FLUTTER_ROOT" >> "$GITHUB_ENV"
'''
        errors = sdk_binding_violations(workflow, "ci.yml")
        self.assertEqual(len(errors), 1)
        self.assertIn("FLUTTER_ATLAS_SDK_ROOT", errors[0])

    def test_empty_check_and_local_fixed_runtime_root_are_rejected(self):
        workflow = '''
      - name: sdk binding
        run: |
          echo "FORMAL_SDK=$FLUTTER_ROOT" >> "$GITHUB_ENV"
          echo "FLUTTER_ATLAS_SDK_ROOT=.tools/flutter-3.47.1/flutter" >> "$GITHUB_ENV"
'''
        errors = sdk_binding_violations(workflow, "ci.yml")
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("非空検証" in error for error in errors))
        self.assertTrue(any("FLUTTER_ATLAS_SDK_ROOT" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
