# SPDX-License-Identifier: Apache-2.0

import json
import tempfile
import unittest
from pathlib import Path

from tooling.scenario_proof.dedicated_runtime import evaluate_dedicated_runtime
from tooling.scenario_security_tranche import report


class SecurityTrancheReportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        inventory = self.root / "atlas/definitive/surface-inventory.json"
        inventory.parent.mkdir(parents=True)
        inventory.write_text(json.dumps({
            "surfaces": [
                {
                    "id": surface,
                    "minimum_variants": 2,
                    "sdk_source_set_digest": f"sha256:{surface}",
                    "sdk_sources": [{"path": f"{surface}.dart", "digest": "sha256:source"}],
                }
                for surface in report.SURFACE_VARIANTS
            ],
        }), encoding="utf-8")
        self.harness = self.root / "scripts/harness.sh"
        self.reporter = self.root / "tooling/report.py"
        self.source = self.root / "tooling/security_test.dart"
        self.harness.parent.mkdir(parents=True)
        self.source.parent.mkdir(parents=True)
        self.harness.write_text("harness", encoding="utf-8")
        self.reporter.write_text("reporter", encoding="utf-8")
        self.source.write_text("source", encoding="utf-8")
        self.logs = {}
        self.screenshots = {}
        self.trees = {}
        for surface, variants in report.SURFACE_VARIANTS.items():
            for variant in variants:
                row = self.root / "raw" / surface / variant
                row.mkdir(parents=True)
                observation = self.observation(surface, variant)
                log = row / "runtime.log"
                log.write_text(
                    f"{report.MARKER}{json.dumps(observation)}\n00:01 +1: All tests passed!\n",
                    encoding="utf-8",
                )
                screen = row / "screen.png"
                screen.write_bytes(b"\x89PNG\r\n\x1a\nactual-screen")
                tree = row / "platform-tree.xml"
                password_attribute = "password" + '="false"'
                tree.write_text(
                    f'<hierarchy><node text="{surface} {variant} PASS" content-desc="public" {password_attribute} /></hierarchy>',
                    encoding="utf-8",
                )
                self.logs[(surface, variant)] = log
                self.screenshots[(surface, variant)] = screen
                self.trees[(surface, variant)] = tree
        self.output = self.root / "evidence/scenarios/runtime"
        previous = self.output / "platform/method-channel/keep.txt"
        previous.parent.mkdir(parents=True)
        previous.write_text("retained", encoding="utf-8")
        self.identity = {
            "profile": "android-emulator",
            "runner_kind": "android-emulator",
            "os": "Android 16",
            "architecture": "arm64-v8a",
            "api_level": 36,
            "device_id": "emulator-test",
            "physical_device": False,
        }

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def observation(surface, variant):
        value = {"surface_id": surface, "scenario": "security", "variant": variant, "platform": "Android"}
        if surface == "accessibility.focus-text-scale":
            value.update(text_scale=1.0 if variant == "text-scale-1x" else 2.0, rendered_height=20.0,
                         focus_received=True, semantics_label="Public focus status", sensitive_value_exposed=False)
        elif surface == "accessibility.semantics-tree":
            value.update(semantics_label="Public security action", semantic_container=True,
                         explicit_child_nodes=variant == "explicit-container", sensitive_value_exposed=False)
        elif surface == "background.app-lifecycle":
            value.update(mechanism=variant, states=["inactive", "paused", "resumed"], background_seen=True,
                         resumed_after_background=True, sensitive_value_cleared=True)
        else:
            value.update(mechanism=variant, worker_completed=True, input_length=25, checksum=42,
                         raw_sensitive_value_returned=False)
        return value

    def publish(self):
        report.publish_bundle(
            self.output,
            root=self.root,
            logs=self.logs,
            screenshots=self.screenshots,
            trees=self.trees,
            harness=self.harness,
            reporter=self.reporter,
            source=self.source,
            runtime_identity=self.identity,
            started_at="2026-08-30T00:00:00Z",
            completed_at="2026-08-30T00:01:00Z",
        )

    def snapshot(self):
        return {str(path.relative_to(self.output)): path.read_bytes() for path in self.output.rglob("*") if path.is_file()}

    def test_full_bundle_closes_security_001_and_retains_existing_runtime(self):
        self.publish()
        self.assertEqual(self.snapshot()["platform/method-channel/keep.txt"], b"retained")
        self.assertNotIn(b"password" + b"=", b"".join(
            content for path, content in self.snapshot().items() if path.endswith("platform-tree.xml")
        ))
        for surface, variants in report.SURFACE_VARIANTS.items():
            baseline = ["material-semantics"] if surface == "accessibility.semantics-tree" else []
            result = evaluate_dedicated_runtime(
                self.root,
                surface_id=surface,
                scenario="security",
                baseline_variants=baseline,
                minimum_variants=2,
                source_set_digest=f"sha256:{surface}",
            )
            self.assertTrue(result["closed"], result["errors"])
            self.assertEqual(result["declared_variants"], sorted(variants))

    def test_failed_rerun_retains_prior_complete_runtime_root(self):
        self.publish()
        previous = self.snapshot()
        key = ("background.app-lifecycle", "app-lifecycle-listener")
        self.logs[key].write_text("failed without marker\n", encoding="utf-8")
        with self.assertRaisesRegex(report.ReportError, "first-attempt"):
            self.publish()
        self.assertEqual(self.snapshot(), previous)

    def test_platform_tree_sensitive_value_is_rejected(self):
        self.publish()
        previous = self.snapshot()
        key = ("accessibility.semantics-tree", "material-semantics")
        self.trees[key].write_text(
            f'<hierarchy><node text="{report.SENSITIVE_SENTINEL}" /></hierarchy>', encoding="utf-8"
        )
        with self.assertRaisesRegex(report.ReportError, "sensitive value"):
            self.publish()
        self.assertEqual(self.snapshot(), previous)


if __name__ == "__main__":
    unittest.main()
