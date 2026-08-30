# SPDX-License-Identifier: Apache-2.0
import unittest

from tooling.ci_supply_chain.verify import (
    checkout_history_violations,
    core_v2_adapter_violations,
    runtime_dependency_violations,
    runtime_reporter_violations,
    reference_snapshot_violations,
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

    def test_runtime_dependencies_use_fixed_sdk_and_lockfile(self):
        workflow = '''
      - name: locked dependencies
        working-directory: reference-systems/operations-workspace
        run: '"$FLUTTER_ROOT/bin/flutter" pub get --enforce-lockfile'
'''
        self.assertEqual(runtime_dependency_violations(workflow, "ci.yml"), [])

    def test_runtime_dependency_restore_without_lock_enforcement_is_rejected(self):
        workflow = '''
      - name: mutable dependencies
        working-directory: reference-systems/operations-workspace
        run: flutter pub get
'''
        errors = runtime_dependency_violations(workflow, "ci.yml")
        self.assertEqual(len(errors), 1)
        self.assertIn("--enforce-lockfile", errors[0])

    def test_runtime_dependency_restore_in_wrong_directory_is_rejected(self):
        workflow = '''
      - name: wrong workspace
        working-directory: .
        run: '"$FLUTTER_ROOT/bin/flutter" pub get --enforce-lockfile'
'''
        errors = runtime_dependency_violations(workflow, "ci.yml")
        self.assertEqual(len(errors), 1)
        self.assertIn("working-directory", errors[0])

    def test_web_runtime_uses_oracle_compatible_reporter(self):
        workflow = "      run: env -u GITHUB_ACTIONS make definitive-web-runtime\n"
        self.assertEqual(runtime_reporter_violations(workflow, "ci.yml"), [])

    def test_github_default_reporter_regression_is_rejected(self):
        workflow = "      run: make definitive-web-runtime\n"
        errors = runtime_reporter_violations(workflow, "ci.yml")
        self.assertEqual(len(errors), 1)
        self.assertIn("GITHUB_ACTIONS", errors[0])

    def test_core_v2_incomplete_adapter_is_explicit(self):
        workflow = """
      - name: Core v2 incomplete migration
        run: |
          python3 -m unittest tooling.ci_supply_chain.test_core_v2_adapter
          python3 tooling/ci_supply_chain/core_v2_adapter.py --check
          python3 tooling/ci_supply_chain/core_v2_adapter.py --audit-incomplete --atlas-bin .tools/bin/atlas-v2
"""
        self.assertEqual(core_v2_adapter_violations(workflow, "ci.yml"), [])

    def test_raw_audit_without_adapter_contract_is_rejected(self):
        errors = core_v2_adapter_violations(
            "      - run: make core-v2-audit\n", "ci.yml"
        )
        self.assertEqual(len(errors), 3)

    def test_self_contained_reference_snapshots_are_required(self):
        workflow = """
      - run: python3 tooling/reference_snapshot/verify.py --lock definitive/fe-depth-reference.lock.json --reference-root third_party/reference-snapshots/frontend-behavior-atlas/8a9e34a89a55cc53702032783c06ede7246a286f
      - run: python3 tooling/fe_parity/generate.py --check
      - run: python3 tooling/reference_snapshot/verify.py --lock definitive/fe-reference-system.lock.json --reference-root third_party/reference-snapshots/frontend-behavior-atlas/7175de4305afb308722d5b83475e91c18da64957
      - run: python3 tooling/scenario_proof/generate.py --check
      - run: python3 -m unittest tooling.reference_snapshot.test_verify
"""
        self.assertEqual(reference_snapshot_violations(workflow, "ci.yml"), [])

    def test_unavailable_sibling_checkout_is_rejected(self):
        errors = reference_snapshot_violations(
            "repository: akaitigo/frontend-behavior-atlas\n", "ci.yml"
        )
        self.assertEqual(len(errors), 6)
        self.assertTrue(any("sibling checkout" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
