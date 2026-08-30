import copy
import json
import tempfile
import unittest
from pathlib import Path

from tooling.scenario_proof.dedicated_runtime import evaluate_dedicated_runtime, report_path, sha256


ROOT = Path(__file__).resolve().parents[2]


class ScenarioProofTest(unittest.TestCase):
    def setUp(self):
        self.index = json.loads((ROOT / "evidence/scenarios/index.json").read_text(encoding="utf-8"))

    def test_cartesian_product_has_dedicated_artifacts(self):
        summary = self.index["summary"]
        self.assertEqual((summary["surfaces"], summary["scenarios"], summary["rows"]), (54, 10, 540))
        self.assertEqual(summary["dedicated_artifacts"], 540)
        self.assertEqual(len({item["id"] for item in self.index["files"]}), 540)
        self.assertEqual(len({item["path"] for item in self.index["files"]}), 540)

    def test_integrated_trace_does_not_launder_surface_proof(self):
        summary = self.index["summary"]
        self.assertEqual(summary["integrated_trace_rows"], 540)
        self.assertEqual(summary["surface_specific_runtime_rows"], 14)
        self.assertEqual(summary["dedicated_runtime_rows"], 14)
        self.assertEqual(summary["surface_runtime_gap_rows"], 526)
        self.assertGreater(summary["legacy_observation_rows"], 0)
        self.assertEqual(summary["authority_atomic_rows"], 0)
        self.assertEqual(summary["completion_eligible_rows"], 0)
        self.assertEqual(
            summary["surface_specific_runtime_rows"] + summary["surface_runtime_gap_rows"],
            540,
        )

    def test_every_row_has_runtime_bindings_or_explicit_gap(self):
        for indexed in self.index["files"]:
            proof = json.loads((ROOT / indexed["path"]).read_text(encoding="utf-8"))
            self.assertTrue(proof["source_bindings"])
            self.assertTrue(proof["integrated_reference"]["trace"]["digest"].startswith("sha256:"))
            self.assertTrue(all(not item["eligible_surface_runtime_proof"] for item in proof["surface_evidence"]))
            if proof["closure"]["surface_specific_evidence"]:
                self.assertTrue(proof["dedicated_runtime"]["closed"])
                for field in ("all_variants_driven", "retry_zero", "trace_artifact_per_variant", "screenshot_artifact_per_variant", "trace_streams_per_variant", "oracle_per_variant", "source_harness_digest_bound", "runtime_identity_complete"):
                    self.assertTrue(proof["dedicated_runtime"][field])
            else:
                self.assertTrue(proof["gaps"])
            self.assertFalse(proof["closure"]["authority_atomic_binding"])
            self.assertFalse(proof["closure"]["completion_eligible"])

    def test_security_001_runtime_closes_only_its_four_planned_rows(self):
        closed = {
            (item["surface_id"], item["scenario"])
            for item in self.index["files"]
            if json.loads((ROOT / item["path"]).read_text(encoding="utf-8"))["dedicated_runtime"]["closed"]
        }
        self.assertTrue({
            ("accessibility.focus-text-scale", "security"),
            ("accessibility.semantics-tree", "security"),
            ("background.app-lifecycle", "security"),
            ("background.isolate-work", "security"),
        }.issubset(closed))
        self.assertIn(("build.android", "security"), closed)
        self.assertIn(("build.web", "security"), closed)

    def test_ten_integrated_traces_have_real_runtime_identity(self):
        integrated = json.loads((ROOT / "evidence/scenarios/integrated/index.json").read_text(encoding="utf-8"))
        self.assertEqual(integrated["summary"]["passed"], 10)
        self.assertEqual(integrated["summary"]["dedicated_trace_artifacts"], 10)
        self.assertTrue(integrated["run_id"].startswith("sha256:"))
        self.assertEqual(integrated["retention_contract"], {
            "failed_run": "retain-prior-success",
            "partial_overwrite_allowed": False,
            "publish_on": "full-run-passed",
            "swap": "staged-directory-rename-with-rollback",
        })
        self.assertTrue(all(item["run_id"] == integrated["run_id"] for item in integrated["files"]))
        identity = integrated["runtime_identity"]
        for key in ("browser", "browser_version", "os", "architecture", "flutter_version", "dart_version"):
            self.assertTrue(identity[key])
        self.assertEqual(integrated["summary"]["completion_eligible"], 0)

    def test_dedicated_runtime_requires_exact_variant_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src/variant.dart"
            harness = root / "test/harness.dart"
            reporter = root / "test/reporter.py"
            source.parent.mkdir(parents=True)
            harness.parent.mkdir(parents=True)
            source.write_text("variant", encoding="utf-8")
            harness.write_text("harness", encoding="utf-8")
            reporter.write_text("reporter", encoding="utf-8")
            tests = []
            for variant in ("a", "b"):
                artifact_root = root / f"evidence/scenarios/runtime/platform/method-channel/boundary/{variant}"
                artifact_root.mkdir(parents=True)
                trace = artifact_root / "trace.json"
                artifact = artifact_root / "result.json"
                trace.write_text(json.dumps({"streams": {"action": [{"variant": variant}], "network": {"applicable": False, "reason": "not used"}, "resource": [{"runtime": "test"}]}}), encoding="utf-8")
                artifact.write_text(f"artifact-{variant}", encoding="utf-8")
                screenshot = artifact_root / "screen.png"
                screenshot.write_bytes(b"\x89PNG\r\n\x1a\nactual-screen")
                tests.append({
                    "variant": variant, "attempts": 1, "outcome": "expected", "final_status": "passed", "error": None,
                    "oracle": {"passed": True, "assertions": ["observable state matched"]},
                    "source": {"path": "src/variant.dart", "digest": sha256(source), "bytes": source.stat().st_size},
                    "trace": {"path": str(trace.relative_to(root)), "digest": sha256(trace), "bytes": trace.stat().st_size},
                    "artifact": {"path": str(artifact.relative_to(root)), "digest": sha256(artifact), "bytes": artifact.stat().st_size},
                    "screenshot": {"path": str(screenshot.relative_to(root)), "digest": sha256(screenshot), "bytes": screenshot.stat().st_size},
                })
            report = {
                "schema_version": 1, "surface_id": "platform.method-channel", "scenario": "boundary", "status": "passed", "retries": 0,
                "source_set_digest": "sha256:source-set", "variant_contract": ["a", "b"],
                "runtime_identity": {"profile": "android-emulator", "runner_kind": "android-emulator", "os": "Android 16", "architecture": "arm64", "api_level": 36, "device_id": "emulator-test", "physical_device": False},
                "harness": {"path": "test/harness.dart", "digest": sha256(harness), "bytes": harness.stat().st_size}, "tests": tests,
                "reporter": {"path": "test/reporter.py", "digest": sha256(reporter), "bytes": reporter.stat().st_size},
            }
            path = root / report_path("platform.method-channel", "boundary")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report), encoding="utf-8")
            closed = evaluate_dedicated_runtime(root, surface_id="platform.method-channel", scenario="boundary", baseline_variants=["a", "b"], minimum_variants=2, source_set_digest="sha256:source-set")
            self.assertTrue(closed["closed"])

            integrated_trace = root / "evidence/scenarios/integrated/boundary.trace.json"
            integrated_trace.parent.mkdir(parents=True)
            integrated_trace.write_text("integrated", encoding="utf-8")
            integrated_binding = {"path": str(integrated_trace.relative_to(root)), "digest": sha256(integrated_trace), "bytes": integrated_trace.stat().st_size}

            mutations = {
                "retry": (lambda value: value.update(retries=1), "retry-must-be-zero"),
                "variant": (lambda value: value["tests"].pop(), "all-variants-not-driven-exactly-once"),
                "oracle": (lambda value: value["tests"][0].pop("oracle"), "variant-oracle-invalid:a"),
                "identity": (lambda value: value["runtime_identity"].pop("architecture"), "runtime-identity-architecture-missing"),
                "harness": (lambda value: value["harness"].update(digest="sha256:wrong"), "harness-binding-digest-mismatch"),
                "screenshot": (lambda value: value["tests"][0].pop("screenshot"), "variant-screenshot-binding-missing:a"),
                "other-variant-reuse": (lambda value: value["tests"][0].update(trace=value["tests"][1]["trace"]), "variant-trace-binding-is-not-dedicated-row-artifact:a"),
                "integrated-trace-reuse": (lambda value: value["tests"][0].update(trace=integrated_binding), "variant-trace-binding-is-not-dedicated-row-artifact:a"),
            }
            for name, (mutate, expected_error) in mutations.items():
                with self.subTest(name=name):
                    invalid = copy.deepcopy(report)
                    mutate(invalid)
                    path.write_text(json.dumps(invalid), encoding="utf-8")
                    rejected = evaluate_dedicated_runtime(root, surface_id="platform.method-channel", scenario="boundary", baseline_variants=["a", "b"], minimum_variants=2, source_set_digest="sha256:source-set")
                    self.assertFalse(rejected["closed"])
                    self.assertIn(expected_error, rejected["errors"])


if __name__ == "__main__":
    unittest.main()
