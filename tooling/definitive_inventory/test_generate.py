# SPDX-License-Identifier: Apache-2.0

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("generate.py")
SPEC = importlib.util.spec_from_file_location("definitive_generate", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DefinitiveInventoryTest(unittest.TestCase):
    def test_rejects_single_variant_requirement(self):
        document = {
            "schema_version": 2,
            "surfaces": [
                {
                    "id": "framework.lifecycle",
                    "source_globs": ["source.dart"],
                    "required_runtime_profiles": ["android-emulator"],
                    "minimum_variants": 1,
                }
            ],
        }
        with self.assertRaises(MODULE.InventoryError):
            MODULE.validate_requirements(document)

    def test_static_contract_is_not_runtime_evidence(self):
        self.assertNotIn("source-contract", MODULE.RUNTIME_KINDS)

    def test_five_scenarios_are_fixed(self):
        self.assertEqual(
            MODULE.SCENARIOS,
            ("normal", "boundary", "rejection", "failure", "recovery"),
        )

    def test_each_runtime_profile_requires_every_scenario_and_two_variants(self):
        observations = [
            {
                "runtime_profile": "web-chrome",
                "scenario": "normal",
                "variant": "javascript",
                "reference_app": True,
            }
        ]
        gaps = MODULE.runtime_profile_gaps(
            observations,
            ["web-chrome", "macos-host"],
            list(MODULE.SCENARIOS),
            2,
            True,
        )
        self.assertIn(
            {"kind": "profile-scenario", "id": "web-chrome:failure"}, gaps
        )
        self.assertIn(
            {"kind": "profile-variant", "id": "web-chrome:1/2"}, gaps
        )
        self.assertIn({"kind": "runtime-profile", "id": "macos-host"}, gaps)
        self.assertIn(
            {"kind": "profile-reference-app", "id": "macos-host"}, gaps
        )


if __name__ == "__main__":
    unittest.main()
