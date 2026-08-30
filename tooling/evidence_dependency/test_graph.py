import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tooling.evidence_dependency import graph as dependency
from tooling.evidence_dependency import platform_state


FIXTURES = dependency.ROOT / "tooling/evidence_dependency/fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class EvidenceDependencyNegativeFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = dependency.load_json(dependency.ROOT, dependency.GRAPH_PATH)
        cls.baseline = dependency.load_json(dependency.ROOT, dependency.BASELINE_PATH)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        paths = {path for item in self.graph["inputs"] for path in item["members"]}
        paths.update(item["path"] for item in self.graph["outputs"])
        paths.update({dependency.GRAPH_PATH.as_posix(), dependency.BASELINE_PATH.as_posix()})
        for relative in sorted(paths):
            source = dependency.ROOT / relative
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        self.document = copy.deepcopy(self.graph)

    def tearDown(self):
        self.temp.cleanup()

    def assert_fixture_rejected(self, fixture_name: str, callback):
        fixture = load_fixture(fixture_name)
        callback(fixture)
        with self.assertRaisesRegex(dependency.DependencyError, fixture["expected_error"]):
            dependency.verify_graph(self.root, self.document)

    def test_changed_input_digest_cannot_close_without_post_change_run(self):
        def mutate(fixture):
            item = next(value for value in self.document["inputs"] if value["id"] == fixture["target"])
            all_members = [member for value in self.document["inputs"] for member in value["members"]]
            unique_member = next(member for member in item["members"] if all_members.count(member) == 1)
            member = self.root / unique_member
            member.write_bytes(member.read_bytes() + b"\nchanged-source\n")
            item["current_digest"] = dependency.digest_members(self.root, item["members"])
            item["observed_at"] = "2026-08-30T00:00:00Z"
            for run in self.document["runs"]:
                for binding in run["input_bindings"]:
                    if binding["input_id"] == item["id"]:
                        binding["digest"] = item["current_digest"]

        self.assert_fixture_rejected("change-input-digest-only", mutate)

    def test_core_v2_depth_reference_change_stales_adapter_and_provenance(self):
        source = next(
            item for item in self.document["inputs"]
            if item["id"] == "source.core-v2-depth-reference"
        )
        self.assertEqual(
            source["members"],
            [
                "authority/FE_DEPTH_REFERENCE.json",
                "definitive/core-v2-fe-depth-reference.lock.json",
            ],
        )
        bound_runs = {
            run["id"]
            for run in self.document["runs"]
            if any(
                binding["input_id"] == source["id"]
                for binding in run["input_bindings"]
            )
        }
        self.assertEqual(
            bound_runs,
            {
                "run.core-v2-root-adapter.2026-08-31",
                "run.provenance.2026-08-29",
            },
        )
        reference = self.root / source["members"][0]
        reference.write_bytes(reference.read_bytes() + b"\nchanged-reference\n")
        source["current_digest"] = dependency.digest_members(self.root, source["members"])
        source["observed_at"] = "2026-09-01T00:00:00Z"
        with self.assertRaisesRegex(dependency.DependencyError, "現在input binding不一致"):
            dependency.verify_graph(self.root, self.document)

    def test_core_v2_source_files_are_not_misclassified_as_generated_outputs(self):
        output_paths = {item["path"] for item in self.document["outputs"]}
        self.assertTrue(dependency.CORE_V2_ADAPTER_OUTPUTS <= output_paths)
        self.assertNotIn("authority/FE_DEPTH_REFERENCE.json", output_paths)
        self.assertNotIn("definitive/core-v2-fe-depth-reference.lock.json", output_paths)

    def test_machine_discovery_rejects_omitted_evidence(self):
        def mutate(fixture):
            output = next(value for value in self.document["outputs"] if value["path"].endswith(fixture["target_suffix"]))
            self.document["outputs"].remove(output)
            self.document["required_outputs"].remove(output["path"])
            run = next(value for value in self.document["runs"] if value["id"] == output["run_id"])
            run["output_ids"].remove(output["id"])

        self.assert_fixture_rejected("omit-required-output", mutate)

    def test_scenario_index_proofs_must_all_be_git_tracked(self):
        index = dependency.load_json(self.root, "evidence/scenarios/index.json")
        tracked = {item["path"] for item in index["files"]}
        tracked.remove(index["files"][-1]["path"])
        with self.assertRaisesRegex(dependency.DependencyError, "git ls-files"):
            dependency.verify_scenario_proofs_are_tracked(self.root, tracked)

    def test_required_output_cannot_be_retreated(self):
        def mutate(fixture):
            self.document["required_outputs"].remove(fixture["target"])

        self.assert_fixture_rejected("retreat-output", mutate)

    def test_proof_structure_cannot_shrink_after_digest_repin(self):
        def mutate(fixture):
            index = dependency.load_json(self.root, fixture["target"])
            index["files"] = index["files"][:-1]
            dependency.write_json(self.root, fixture["target"], index)
            output = next(value for value in self.document["outputs"] if value["path"] == fixture["target"])
            output["digest"] = dependency.sha_file(self.root, fixture["target"])

        self.assert_fixture_rejected("shrink-proof-structure", mutate)

    def test_closure_plan_structure_cannot_shrink_after_digest_repin(self):
        def mutate(fixture):
            plan = dependency.load_json(self.root, fixture["target"])
            removed = plan["rows"].pop()
            for tranche in plan["tranches"]:
                if removed["id"] in tranche["row_ids"]:
                    tranche["row_ids"].remove(removed["id"])
                    tranche["pattern_rows"] -= 1
                    tranche["variant_runs"] -= len(removed["variant_ids"])
                    break
            dependency.write_json(self.root, fixture["target"], plan)
            output = next(value for value in self.document["outputs"] if value["path"] == fixture["target"])
            output["digest"] = dependency.sha_file(self.root, fixture["target"])

        self.assert_fixture_rejected("shrink-closure-structure", mutate)

    def test_non_regression_rejects_threshold_weakening(self):
        fixture = load_fixture("weaken-threshold")
        baseline = copy.deepcopy(self.baseline)
        baseline["thresholds"][fixture["target"]] = 5
        with self.assertRaisesRegex(dependency.DependencyError, fixture["expected_error"]):
            dependency.verify_baseline(self.root, self.document, baseline)

    def test_retry_is_not_first_attempt_evidence(self):
        fixture = load_fixture("retry-run")
        run = next(value for value in self.document["runs"] if value["id"] == fixture["target"])
        run["attempts"] = 2
        with self.assertRaisesRegex(dependency.DependencyError, fixture["expected_error"]):
            dependency.verify_graph(self.root, self.document)

    def test_platform_run_requires_runtime_identity(self):
        fixture = load_fixture("remove-runtime-identity")
        run = next(value for value in self.document["runs"] if value["id"] == fixture["target"])
        del run["runtime_identity"]
        with self.assertRaisesRegex(dependency.DependencyError, fixture["expected_error"]):
            dependency.verify_graph(self.root, self.document)

    def test_closure_progress_preserves_the_540_row_topology_digest(self):
        path = dependency.PLAN_PATH.as_posix()
        before = dependency.structure_digest(self.root, "scenario-closure-plan", path)
        plan = dependency.load_json(self.root, path)
        row = plan["rows"][0]
        row["runtime_status"] = "completed"
        plan["completed_rows"] = [row["id"]]
        plan["summary"]["completed_dedicated_rows"] = 1
        plan["summary"]["remaining_rows"] = 539
        plan["tranches"][0]["status"] = "partially-completed"
        plan["tranches"][0]["completed_pattern_rows"] = 1
        dependency.write_json(self.root, path, plan)
        self.assertEqual(before, dependency.structure_digest(self.root, "scenario-closure-plan", path))

    def test_closure_structure_includes_completed_and_planned_tranches_like_core(self):
        plan = dependency.load_json(self.root, dependency.PLAN_PATH.as_posix())
        structure = dependency.closure_structure(plan)
        completed = plan["completed_tranches"]
        planned = plan["tranches"]
        self.assertEqual(
            [item["id"] for item in structure["tranches"]],
            [item["id"] for item in completed] + [item["id"] for item in planned],
        )
        self.assertEqual(
            structure["ordered_row_ids"],
            [row_id for item in completed for row_id in item["row_ids"]]
            + [item["id"] for item in plan["rows"]],
        )

    def test_security_001_records_runtime_variants_without_rewriting_baseline_topology(self):
        plan = dependency.load_json(dependency.ROOT, dependency.PLAN_PATH)
        tranche = next(item for item in plan["tranches"] if item["id"] == "security-001")
        self.assertEqual(tranche["status"], "completed")
        self.assertEqual(tranche["completed_pattern_rows"], 4)
        self.assertEqual(tranche["completed_variant_runs"], 8)
        rows = {item["id"]: item for item in plan["rows"]}
        for row_id in tranche["row_ids"]:
            self.assertEqual(rows[row_id]["runtime_status"], "completed")
            self.assertEqual(rows[row_id]["variant_contract_status"], "resolved-runtime")
            self.assertEqual(len(rows[row_id]["runtime_variant_ids"]), 2)

    def test_security_runtime_attestation_requires_current_reported_inputs(self):
        report = dependency.load_json(
            self.root,
            "evidence/scenarios/runtime/accessibility/focus-text-scale/security/results.json",
        )
        self.assertTrue(dependency.security_runtime_report_attests_current_inputs(self.root, report["started_at"]))
        harness = self.root / "scripts/scenario-security-tranche-runtime.sh"
        harness.write_bytes(harness.read_bytes() + b"\nmutated-after-run\n")
        self.assertFalse(dependency.security_runtime_report_attests_current_inputs(self.root, report["started_at"]))

    def web_migration_previous_input(self) -> tuple[dict, dict[str, dict]]:
        inputs = {item["id"]: item for item in dependency.input_definitions(self.root)}
        migration = dependency.load_json(self.root, dependency.WEB_BUILD_INPUT_MIGRATION)
        previous = copy.deepcopy(inputs[dependency.WEB_BUILD_INPUT_ID])
        previous["members"] = sorted(set(previous["members"]) | {dependency.WEB_BUILD_TEST_PATH})
        previous["current_digest"] = migration["prior_graph_attestation"]["input_digest"]
        return previous, inputs

    def test_web_input_migration_requires_exact_old_member_set(self):
        previous, inputs = self.web_migration_previous_input()
        previous["members"].append("tooling/scenario_build_web/unrelated-production-member.py")
        self.assertFalse(dependency.web_build_input_migration_matches(self.root, previous, inputs))

    def test_web_input_migration_requires_exact_old_digest(self):
        previous, inputs = self.web_migration_previous_input()
        previous["current_digest"] = "sha256:" + "0" * 64
        self.assertFalse(dependency.web_build_input_migration_matches(self.root, previous, inputs))

    def test_web_input_migration_reason_change_cannot_cover_production_drift(self):
        capture = self.root / "tooling/scenario_build_web/capture.py"
        capture.write_bytes(capture.read_bytes() + b"\nunattested-production-change\n")
        migration = dependency.load_json(self.root, dependency.WEB_BUILD_INPUT_MIGRATION)
        migration["reason"] = "reason text alone must not authorize a production change"
        dependency.write_json(self.root, dependency.WEB_BUILD_INPUT_MIGRATION, migration)
        inputs = {item["id"]: item for item in dependency.input_definitions(self.root)}
        with self.assertRaisesRegex(dependency.DependencyError, "runtime binding不一致"):
            dependency.verify_web_build_input_migration(self.root, inputs)


class AndroidPlatformStateContractTest(unittest.TestCase):
    surface = "input.text-ime"
    variant = "obscured-entry"
    marker = "ATLAS_PLATFORM_STATE surface=input.text-ime variant=obscured-entry\n"

    def test_exact_current_activity_block_and_state_pass(self):
        raw = (
            self.marker
            + "  ACTIVITY com.android.launcher/.Launcher pid=1\n"
            + "    mResumed=false mStopped=true mFinished=false\n"
            + "  ACTIVITY dev.akaitigo.atlas.operations_workspace/.MainActivity pid=2\n"
            + "    mResumed=true mStopped=false mFinished=false\n"
        )
        summary = platform_state.validate_text(raw, self.surface, self.variant)
        self.assertEqual(summary["states"], {"mResumed": True, "mStopped": False, "mFinished": False})

    def test_historical_package_log_without_current_activity_is_rejected(self):
        raw = self.marker + "LauncherAppsCallback packageName=dev.akaitigo.atlas.operations_workspace\n"
        with self.assertRaisesRegex(platform_state.PlatformStateError, "current Activity block"):
            platform_state.validate_text(raw, self.surface, self.variant)

    def test_wrong_activity_with_historical_target_package_is_rejected(self):
        raw = (
            self.marker
            + "  ACTIVITY com.android.launcher/.Launcher pid=1\n"
            + "    mResumed=true mStopped=false mFinished=false\n"
            + "history dev.akaitigo.atlas.operations_workspace/.MainActivity\n"
        )
        with self.assertRaisesRegex(platform_state.PlatformStateError, "current Activity block"):
            platform_state.validate_text(raw, self.surface, self.variant)

    def test_stopped_target_activity_is_rejected(self):
        raw = (
            self.marker
            + "  ACTIVITY dev.akaitigo.atlas.operations_workspace/.MainActivity pid=2\n"
            + "    mResumed=false mStopped=true mFinished=false\n"
        )
        with self.assertRaisesRegex(platform_state.PlatformStateError, "state不一致"):
            platform_state.validate_text(raw, self.surface, self.variant)

    def test_non_target_and_target_cannot_both_be_resumed(self):
        raw = (
            self.marker
            + "  ACTIVITY com.android.launcher/.Launcher pid=1\n"
            + "    mResumed=true mStopped=false mFinished=false\n"
            + "  ACTIVITY dev.akaitigo.atlas.operations_workspace/.MainActivity pid=2\n"
            + "    mResumed=true mStopped=false mFinished=false\n"
        )
        with self.assertRaisesRegex(platform_state.PlatformStateError, "resumed Activity"):
            platform_state.validate_text(raw, self.surface, self.variant)


if __name__ == "__main__":
    unittest.main()
