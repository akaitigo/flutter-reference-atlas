# SPDX-License-Identifier: Apache-2.0

import json
import tempfile
import unittest
from pathlib import Path

from tooling.scenario_method_channel import report
from tooling.scenario_proof.dedicated_runtime import evaluate_dedicated_runtime


class MethodChannelScenarioReportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        inventory = self.root / "atlas/definitive/surface-inventory.json"
        inventory.parent.mkdir(parents=True)
        inventory.write_text(json.dumps({
            "surfaces": [{
                "id": report.SURFACE_ID,
                "minimum_variants": 2,
                "sdk_source_set_digest": "sha256:sdk-source-set",
                "sdk_sources": [{"path": "framework.dart", "digest": "sha256:framework"}],
            }],
        }), encoding="utf-8")
        self.harness = self.root / "scripts/harness.sh"
        self.reporter = self.root / "tooling/report.py"
        self.source = self.root / "tooling/scenario_test.dart"
        self.harness.parent.mkdir(parents=True)
        self.source.parent.mkdir(parents=True)
        self.harness.write_text("harness", encoding="utf-8")
        self.reporter.write_text("reporter", encoding="utf-8")
        self.source.write_text("source", encoding="utf-8")
        self.logs = {}
        self.screenshots = {}
        for scenario in report.SCENARIOS:
            for variant in report.VARIANTS:
                row = self.root / "raw" / scenario / variant
                row.mkdir(parents=True)
                observation = {
                    "surface_id": report.SURFACE_ID,
                    "scenario": scenario,
                    "variant": variant,
                    "platform": "Android",
                    "os_version": "16",
                    "api_level": 36,
                    "activity_attached": True,
                    "codec": variant,
                }
                if scenario == "boundary":
                    observation.update(accepted_length=64, rejected_length=65, error_code="BOUNDARY_EXCEEDED")
                elif scenario == "refusal":
                    observation["error_code"] = "PERMISSION_DENIED"
                elif scenario == "failure":
                    observation["error_code"] = "TRANSIENT_FAILURE"
                else:
                    observation.update(first_error_code="TRANSIENT_FAILURE", recovered_value="recovered")
                log = row / "runtime.log"
                log.write_text(
                    f"{report.MARKER}{json.dumps(observation)}\n00:01 +1: All tests passed!\n",
                    encoding="utf-8",
                )
                screen = row / "screen.png"
                screen.write_bytes(b"\x89PNG\r\n\x1a\nactual-screen")
                self.logs[(scenario, variant)] = log
                self.screenshots[(scenario, variant)] = screen
        self.output = self.root / "evidence/scenarios/runtime/platform/method-channel"
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

    def publish(self):
        report.publish_bundle(
            self.output,
            root=self.root,
            logs=self.logs,
            screenshots=self.screenshots,
            harness=self.harness,
            reporter=self.reporter,
            source=self.source,
            runtime_identity=self.identity,
            started_at="2026-08-30T00:00:00Z",
            completed_at="2026-08-30T00:01:00Z",
        )

    def snapshot(self):
        return {str(path.relative_to(self.output)): path.read_bytes() for path in self.output.rglob("*") if path.is_file()}

    def test_full_bundle_closes_four_dedicated_runtime_rows(self):
        self.publish()
        self.assertEqual(len(self.snapshot()), 28)
        for scenario in report.SCENARIOS:
            result = evaluate_dedicated_runtime(
                self.root,
                surface_id=report.SURFACE_ID,
                scenario=scenario,
                baseline_variants=list(report.VARIANTS),
                minimum_variants=2,
                source_set_digest="sha256:sdk-source-set",
            )
            self.assertTrue(result["closed"], result["errors"])
            self.assertTrue(result["screenshot_artifact_per_variant"])
            self.assertTrue(result["trace_streams_per_variant"])

    def test_failed_rerun_retains_prior_complete_bundle(self):
        self.publish()
        previous = self.snapshot()
        self.logs[("failure", "json")].write_text("failed without marker\n", encoding="utf-8")
        with self.assertRaisesRegex(report.ReportError, "first-attempt"):
            self.publish()
        self.assertEqual(self.snapshot(), previous)


if __name__ == "__main__":
    unittest.main()
