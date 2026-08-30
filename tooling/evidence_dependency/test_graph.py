import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tooling.evidence_dependency import graph as dependency


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

    def test_machine_discovery_rejects_omitted_evidence(self):
        def mutate(fixture):
            output = next(value for value in self.document["outputs"] if value["path"].endswith(fixture["target_suffix"]))
            self.document["outputs"].remove(output)
            self.document["required_outputs"].remove(output["path"])
            run = next(value for value in self.document["runs"] if value["id"] == output["run_id"])
            run["output_ids"].remove(output["id"])

        self.assert_fixture_rejected("omit-required-output", mutate)

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


if __name__ == "__main__":
    unittest.main()
