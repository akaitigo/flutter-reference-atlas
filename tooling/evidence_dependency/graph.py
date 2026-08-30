#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build and verify Flutter's Evidence Dependency Graph.

The graph is file-level and intentionally records incomplete Evidence as
Evidence.  A current dependency graph means that the recorded files match the
inputs and runs which produced them; it never upgrades a scenario gap to a
completed proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from tooling.evidence_dependency import platform_state
except ModuleNotFoundError:  # direct script execution
    import platform_state  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = Path("evidence/dependency-graph.json")
PLAN_PATH = Path("evidence/scenarios/closure-plan.json")
BASELINE_PATH = Path("baseline/evidence-dependency-v1.json")
CORE_COMMIT = "072d7ca77981f51754e824d70c6d4ecd55ea67e5"
GENERATED_AT = "2026-08-29T00:00:00+09:00"
RISK_ORDER = (
    "security", "refusal", "failure", "recovery", "migration",
    "operations", "boundary", "performance", "compatibility", "normal",
)
POLICY = {
    "transitive_staleness": True,
    "digest_only_closure_forbidden": True,
    "actual_rerun_required": True,
    "missing_rerun_targets_fail": True,
    "proof_structure_invariant": True,
    "closure_plan_structure_invariant": True,
}
EXCLUDED_PARTS = {".dart_tool", ".gradle", ".idea", ".atlas-generated", "build", "ephemeral"}
SECURITY_RUNTIME_PREFIXES = (
    "evidence/scenarios/runtime/accessibility/focus-text-scale/security/",
    "evidence/scenarios/runtime/accessibility/semantics-tree/security/",
    "evidence/scenarios/runtime/background/app-lifecycle/security/",
    "evidence/scenarios/runtime/background/isolate-work/security/",
    "evidence/scenarios/runtime/input/focus-traversal/security/",
    "evidence/scenarios/runtime/input/keyboard-shortcuts/security/",
    "evidence/scenarios/runtime/input/pointer-gesture-arena/security/",
    "evidence/scenarios/runtime/input/text-ime/security/",
)
BUILD_ANDROID_SECURITY_PREFIX = "evidence/scenarios/runtime/build/android/security/"
BUILD_WEB_SECURITY_PREFIX = "evidence/scenarios/runtime/build/web/security/"
PLATFORM_STATE_SUMMARY_SUFFIX = "/platform-state.summary.json"
ANDROID_BUILD_INPUT_ID = "harness.scenario-build-android-security"
ANDROID_BUILD_UNIT_INPUT_ID = "harness.scenario-build-android-security-unit"
ANDROID_BUILD_TEST_PATH = "tooling/scenario_build_android/test_report.py"
ANDROID_BUILD_INPUT_MIGRATION = Path("definitive/evidence-dependency-input-migration.android-build-test.json")
WEB_BUILD_INPUT_ID = "harness.scenario-build-web-security"
WEB_BUILD_UNIT_INPUT_ID = "harness.scenario-build-web-security-unit"
WEB_BUILD_TEST_PATH = "tooling/scenario_build_web/test_report.py"
WEB_BUILD_INPUT_MIGRATION = Path("definitive/evidence-dependency-input-migration.web-build-test.json")
SECURITY_ARTIFACT_MIGRATION_PATHS = {
    "evidence/scenarios/runtime/background/app-lifecycle/security/app-lifecycle-listener/platform-tree.xml": "evidence/scenarios/runtime/background/app-lifecycle/security/app-lifecycle-listener/platform-state.txt",
    "evidence/scenarios/runtime/background/app-lifecycle/security/widgets-binding-observer/platform-tree.xml": "evidence/scenarios/runtime/background/app-lifecycle/security/widgets-binding-observer/platform-state.txt",
    "evidence/scenarios/runtime/background/isolate-work/security/isolate-run/platform-tree.xml": "evidence/scenarios/runtime/background/isolate-work/security/isolate-run/platform-state.txt",
    "evidence/scenarios/runtime/background/isolate-work/security/transferable-data/platform-tree.xml": "evidence/scenarios/runtime/background/isolate-work/security/transferable-data/platform-state.txt",
}


class DependencyError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha_file(root: Path, relative: str) -> str:
    return sha_bytes((root / relative).read_bytes())


def digest_members(root: Path, members: Iterable[str]) -> str:
    items = [{"path": path, "digest": sha_file(root, path)} for path in sorted(members)]
    return sha_bytes(canonical(items))


def load_json(root: Path, relative: str | Path) -> dict[str, Any]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def write_json(root: Path, relative: str | Path, value: Any) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_android_build_input_migration(root: Path, inputs: dict[str, dict[str, Any]]) -> None:
    migration = load_json(root, ANDROID_BUILD_INPUT_MIGRATION)
    if migration.get("old_input_id") != ANDROID_BUILD_INPUT_ID or migration.get("new_input_ids") != [
        ANDROID_BUILD_INPUT_ID,
        ANDROID_BUILD_UNIT_INPUT_ID,
    ] or migration.get("moved_member") != ANDROID_BUILD_TEST_PATH or not migration.get("reason"):
        raise DependencyError("Android build test harness migration mappingが不正です")
    bindings = migration.get("runtime_attestation", {}).get("bindings", [])
    expected = {item["path"]: item["digest"] for item in bindings if set(item) == {"path", "digest"}}
    production_members = set(inputs[ANDROID_BUILD_INPUT_ID]["members"])
    if set(expected) != production_members:
        raise DependencyError("Android build production harness migrationが構造縮小または粗い集約です")
    unit_members = set(inputs[ANDROID_BUILD_UNIT_INPUT_ID]["members"])
    if unit_members != {ANDROID_BUILD_TEST_PATH, ANDROID_BUILD_INPUT_MIGRATION.as_posix()}:
        raise DependencyError("Android build unit harness migrationでtestまたはmigration Evidenceが欠落しています")
    for path, digest_value in expected.items():
        if sha_file(root, path) != digest_value:
            raise DependencyError(f"Android build migration runtime binding不一致: {path}")
    report_path = migration.get("runtime_attestation", {}).get("path")
    report = load_json(root, safe_relative(report_path))
    reported = {
        report["harness"]["path"]: report["harness"]["digest"],
        report["reporter"]["path"]: report["reporter"]["digest"],
    }
    for test in report["tests"]:
        reported[test["source"]["path"]] = test["source"]["digest"]
    if any(reported.get(path) != digest_value for path, digest_value in expected.items()):
        raise DependencyError("Android build migrationが既存実Runtime reportへbindingされていません")


def verify_web_build_input_migration(root: Path, inputs: dict[str, dict[str, Any]]) -> None:
    migration = load_json(root, WEB_BUILD_INPUT_MIGRATION)
    if migration.get("old_input_id") != WEB_BUILD_INPUT_ID or migration.get("new_input_ids") != [
        WEB_BUILD_INPUT_ID,
        WEB_BUILD_UNIT_INPUT_ID,
    ] or migration.get("moved_member") != WEB_BUILD_TEST_PATH or not migration.get("reason"):
        raise DependencyError("Web build test harness migration mappingが不正です")
    bindings = migration.get("runtime_attestation", {}).get("bindings", [])
    expected = {item["path"]: item["digest"] for item in bindings if set(item) == {"path", "digest"}}
    production_members = set(inputs[WEB_BUILD_INPUT_ID]["members"])
    if set(expected) != production_members:
        raise DependencyError("Web build production harness migrationが構造縮小または粗い集約です")
    unit_members = set(inputs[WEB_BUILD_UNIT_INPUT_ID]["members"])
    if unit_members != {WEB_BUILD_TEST_PATH, WEB_BUILD_INPUT_MIGRATION.as_posix()}:
        raise DependencyError("Web build unit harness migrationでtestまたはmigration Evidenceが欠落しています")
    for path, digest_value in expected.items():
        if sha_file(root, path) != digest_value:
            raise DependencyError(f"Web build migration runtime binding不一致: {path}")
    prior = migration.get("prior_graph_attestation", {})
    prior_digest = prior.get("input_digest")
    moved_digest = prior.get("moved_member_digest")
    reconstructed = [
        {"path": path, "digest": digest_value} for path, digest_value in expected.items()
    ] + [{"path": WEB_BUILD_TEST_PATH, "digest": moved_digest}]
    if not isinstance(moved_digest, str) or sha_bytes(canonical(sorted(reconstructed, key=lambda item: item["path"]))) != prior_digest:
        raise DependencyError("Web build migrationのprior Graph input digestが再構成できません")
    report_path = migration.get("runtime_attestation", {}).get("path")
    report = load_json(root, safe_relative(report_path))
    reported = {
        report["harness"]["path"]: report["harness"]["digest"],
        report["reporter"]["path"]: report["reporter"]["digest"],
    }
    for test in report["tests"]:
        reported[test["source"]["path"]] = test["source"]["digest"]
    directly_reported = set(expected) - {"tooling/scenario_build_web/capture.py"}
    if any(reported.get(path) != expected[path] for path in directly_reported):
        raise DependencyError("Web build migrationが既存実Runtime reportへbindingされていません")


def web_build_input_migration_matches(
    root: Path,
    previous_web: dict[str, Any] | None,
    candidate_inputs: dict[str, dict[str, Any]],
) -> bool:
    if previous_web is None:
        return False
    verify_web_build_input_migration(root, candidate_inputs)
    migration = load_json(root, WEB_BUILD_INPUT_MIGRATION)
    expected_old_members = set(candidate_inputs[WEB_BUILD_INPUT_ID]["members"]) | {WEB_BUILD_TEST_PATH}
    return (
        set(previous_web["members"]) == expected_old_members
        and previous_web["current_digest"] == migration["prior_graph_attestation"]["input_digest"]
    )


def safe_relative(path: str) -> str:
    candidate = Path(path)
    if not path or candidate.is_absolute() or ".." in candidate.parts or candidate == Path("."):
        raise DependencyError(f"Repository外または不正なPathです: {path}")
    return candidate.as_posix()


def expand(root: Path, patterns: Iterable[str]) -> list[str]:
    result: set[str] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file() and not any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts):
                result.add(path.relative_to(root).as_posix())
    if not result:
        raise DependencyError(f"input member patternが空です: {list(patterns)}")
    return sorted(result)


def input_definitions(root: Path) -> list[dict[str, Any]]:
    definitions = [
        ("source.reference-app", "source", [
            "reference-systems/operations-workspace/lib/**/*.dart",
            "reference-systems/operations-workspace/test/**/*.dart",
            "reference-systems/operations-workspace/integration_test/**/*.dart",
            "reference-systems/operations-workspace/packages/atlas_runtime_probe/lib/**/*.dart",
            "reference-systems/operations-workspace/packages/atlas_runtime_probe/test/**/*.dart",
            "reference-systems/operations-workspace/packages/atlas_runtime_probe/android/src/main/**/*.kt",
            "reference-systems/operations-workspace/pubspec.yaml",
            "reference-systems/operations-workspace/pubspec.lock",
        ]),
        ("source.flutter-labs", "source", [
            "labs/**/*.dart", "labs/**/*.c", "labs/**/*.h", "labs/**/*.kt",
            "labs/**/*.swift", "labs/**/*.json", "labs/**/pubspec.yaml", "labs/**/pubspec.lock",
        ]),
        ("source.atlas-contract", "source", [
            "atlas.yaml", "coverage.yaml", "definitive.yaml", "mastery.yaml", "sources.lock.yaml",
            "skill.package.yaml", "labs/index.json", "definitive/requirements.json",
            "definitive/runtime-observations.json", "definitive/evidence-dependency-contract.json",
            "authority/extraction.snapshot.json", "authority/body-inventory.snapshot.json",
            "authority/review-queue.snapshot.json", "baseline/public-main-non-regression-v1.json",
            "evidence/completion-certificate.json", "evidence/history/**/*.record.yaml",
            "evidence/history/**/completion-certificate.json",
            "evidence/artifacts/core-v2-audit-attempt-*.log",
            "evidence/artifacts/local-compatibility-report.json",
            "migrations/*.json",
        ]),
        ("source.evidence-dependency-baseline", "source", [
            "baseline/evidence-dependency-v1.json",
        ]),
        ("harness.formal-local", "harness", [
            "tooling/evidence_capture/bin/capture.dart", "tooling/evidence_capture/pubspec.yaml",
            "tooling/surface_inventory/generate.py", "tooling/definitive_inventory/generate.py",
            "scripts/labs-local.sh", "Makefile",
        ]),
        ("harness.container", "harness", [
            "scripts/labs-container.sh", "environments/container/Dockerfile",
            "environments/container/harness.json", "environments/container/manifest.yaml",
            "labs/offline-conflict-resolution/**/*.dart",
        ]),
        ("harness.android", "harness", [
            "scripts/labs-simulator.sh", "scripts/definitive-android-runtime.sh",
            "tooling/simulator_profile/report.py", "tooling/definitive_android/report.py",
            "reference-systems/operations-workspace/integration_test/workspace_integration_test.dart",
            "reference-systems/operations-workspace/packages/atlas_runtime_probe/android/src/main/**/*.kt",
        ]),
        ("harness.scenario-method-channel", "harness", [
            "scripts/scenario-method-channel-runtime.sh",
            "tooling/scenario_method_channel/*.py", "tooling/scenario_method_channel/*.dart",
        ]),
        ("harness.scenario-security-tranche", "harness", [
            "scripts/scenario-security-tranche-runtime.sh",
            "tooling/scenario_security_tranche/report.py",
            "tooling/scenario_security_tranche/security_tranche_scenario_test.dart",
        ]),
        ("harness.scenario-security-artifact-migration", "harness", [
            "tooling/scenario_security_tranche/artifact_migration.py",
            "tooling/scenario_security_tranche/test_artifact_migration.py",
        ]),
        ("harness.scenario-build-android-security", "harness", [
            "scripts/scenario-build-android-security-runtime.sh",
            "tooling/scenario_build_android/report.py", "tooling/scenario_build_android/*.dart",
        ]),
        ("harness.scenario-build-android-security-unit", "harness", [
            ANDROID_BUILD_TEST_PATH, ANDROID_BUILD_INPUT_MIGRATION.as_posix(),
        ]),
        ("harness.scenario-build-web-security", "harness", [
            "scripts/scenario-build-web-security-runtime.sh",
            "tooling/scenario_build_web/capture.py", "tooling/scenario_build_web/report.py",
            "tooling/scenario_build_web/*.dart",
        ]),
        ("harness.scenario-build-web-security-unit", "harness", [
            WEB_BUILD_TEST_PATH, WEB_BUILD_INPUT_MIGRATION.as_posix(),
        ]),
        ("harness.web-reference", "harness", [
            "scripts/definitive-web-runtime.sh", "scripts/reference-scenario-runtime.sh",
            "tooling/definitive_web/report.py", "tooling/scenario_proof/*.py",
            "reference-systems/operations-workspace/test/scenario_trace_test.dart",
        ]),
        ("harness.skill", "harness", [
            "evals/*.py", "evals/cases.json", "evals/definitive_cases.json",
            "evals/forward_cases.json", "evals/harness.json", "evals/routes.json",
            ".agents/skills/flutter-reference-router/**/*.py",
            ".agents/skills/flutter-reference-router/**/*.json",
            ".agents/skills/flutter-reference-router/SKILL.md",
        ]),
        ("harness.authority-parity", "harness", [
            "tooling/authority_extraction/*.py", "tooling/fe_parity/*.py",
            "tooling/non_regression/*.py", "tooling/generate_provenance.py",
        ]),
        ("harness.ci-supply-chain", "harness", [
            ".github/workflows/*.yml", "tooling/ci_supply_chain/*.py",
        ]),
        ("harness.evidence-dependency", "harness", [
            "tooling/evidence_dependency/*.py", "tooling/evidence_dependency/fixtures/*.json",
            "definitive/evidence-dependency-contract.json",
        ]),
        ("harness.android-platform-state-validation", "harness", [
            "tooling/evidence_dependency/platform_state.py",
        ]),
        ("runtime.flutter-3.47.1", "runtime", [
            "baseline/flutter-3.47.1.yaml", "environments/definitive/host-capabilities.json",
        ]),
        ("profile.local", "profile", [
            "environments/local/harness.json", "environments/local/runtime-inventory.json",
        ]),
        ("profile.container", "profile", [
            "environments/container/harness.json", "environments/container/manifest.yaml",
        ]),
        ("profile.android-emulator", "profile", [
            "environments/simulator/manifest.yaml", "environments/simulator/runtime-inventory.json",
        ]),
        ("profile.web-chrome", "profile", [
            "environments/local/runtime-inventory.json", "environments/definitive/host-capabilities.json",
        ]),
    ]
    result = []
    for input_id, kind, patterns in definitions:
        members = expand(root, patterns)
        digest = digest_members(root, members)
        result.append({
            "id": input_id, "kind": kind, "members": members,
            "baseline_digest": digest, "current_digest": digest, "observed_at": GENERATED_AT,
        })
    return result


def output_id(path: str) -> str:
    normalized = re.sub(r"[^a-z0-9._:-]+", "-", path.lower().replace("/", ":"))
    return "output:" + normalized.strip("-")


def discover_outputs(root: Path) -> dict[str, str]:
    paths: set[str] = set()
    patterns = [
        "evidence/*.evidence.yaml", "evidence/artifacts/*", "evidence/scenarios/integrated/*.json",
        "evidence/scenarios/runtime/**/*",
        "evidence/scenarios/surfaces/**/*.proof.json", "authority/*.snapshot.json",
        "authority/body-inventory-draft/*.json", "authority/review-queue-draft/*.json",
        "authority/surfaces-draft/*.json", "atlas/definitive/*.json",
    ]
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file() and "core-v2-audit-attempt" not in path.name and path.name != "local-compatibility-report.json":
                paths.add(path.relative_to(root).as_posix())
    for relative in [
        "evidence/scenarios/index.json", PLAN_PATH.as_posix(),
        "evals/flutter-router.skill-eval.json", "evals/flutter-router.definitive-mastery-eval.json",
        "evals/flutter-router.agent-forward-eval.json", "baseline/public-surface-inventory.json",
        ".agents/skills/flutter-reference-router/references/mastery-contract.json",
        "provenance.yaml",
    ]:
        if (root / relative).is_file():
            paths.add(relative)
    return {path: output_id(path) for path in sorted(paths)}


def output_kind(path: str) -> str:
    if path.startswith("evidence/scenarios/runtime/"):
        return "capture" if path.endswith(".png") else "platform-evidence"
    if path.endswith(".proof.json") or path == "evidence/scenarios/index.json":
        return "scenario-proof"
    if path == PLAN_PATH.as_posix():
        return "closure-plan"
    if path.startswith("evidence/scenarios/integrated/"):
        return "reference-system"
    if path.startswith("evals/") or "router-eval" in path or path.startswith(".agents/skills/"):
        return "skill-eval"
    if "android" in path or "simulator" in path or "method-channel" in path:
        return "platform-evidence"
    if "web-chrome" in path:
        return "compatibility"
    if "performance" in path or "benchmark" in path:
        return "benchmark"
    if path.endswith(".evidence.yaml") or "formal-local" in path or "container-conflict" in path:
        return "runtime-evidence"
    return "derived-evidence"


def run_for_path(path: str) -> str:
    if path.endswith(PLATFORM_STATE_SUMMARY_SUFFIX):
        return "run.android-platform-state-validation.2026-08-31"
    if path in SECURITY_ARTIFACT_MIGRATION_PATHS:
        return "run.scenario-security-artifact-migration.2026-08-31"
    if path.startswith(BUILD_WEB_SECURITY_PREFIX):
        return "run.scenario-build-web-security.2026-08-31"
    if path.startswith(BUILD_ANDROID_SECURITY_PREFIX):
        return "run.scenario-build-android-security.2026-08-31"
    if any(path.startswith(prefix) for prefix in SECURITY_RUNTIME_PREFIXES):
        return "run.scenario-security-tranche.2026-08-30"
    if path.startswith("evidence/scenarios/runtime/platform/method-channel/"):
        return "run.scenario-method-channel.2026-08-30"
    if "container-conflict" in path:
        return "run.container-conflict.2026-08-28"
    if "android-emulator" in path:
        return "run.android-integration.2026-08-28"
    if "android-method-channel" in path:
        return "run.android-method-channel.2026-08-28"
    if "web-chrome" in path:
        return "run.web-chrome.2026-08-28"
    if path.startswith("evidence/scenarios/integrated/") or "reference-scenario-runtime" in path:
        return "run.reference-scenarios.2026-08-28"
    if path.startswith("evidence/scenarios/surfaces/") or path in {"evidence/scenarios/index.json", PLAN_PATH.as_posix()}:
        return "run.scenario-proof-generation.2026-08-29"
    if path.startswith("evals/") or "router-eval" in path or path.startswith(".agents/skills/"):
        return "run.skill-eval.2026-08-28"
    if path.startswith("authority/") or "authority-body-non-regression" in path:
        return "run.authority-inventory.2026-08-28"
    if path.startswith("atlas/definitive/"):
        return "run.definitive-parity.2026-08-28"
    if path == "provenance.yaml":
        return "run.provenance.2026-08-29"
    if "core-v2-audit-attempt" in path or "local-compatibility" in path:
        return "run.historical-gap-verification.2026-08-28"
    return "run.formal-local.2026-08-28"


RUN_CONFIG = {
    "run.formal-local.2026-08-28": ("runtime", "make formal-local", "2026-08-28T07:32:22Z", "2026-08-28T07:32:23Z", ["source.reference-app", "source.flutter-labs", "source.atlas-contract", "harness.formal-local", "runtime.flutter-3.47.1", "profile.local"], {"profile": "local", "flutter_version": "3.47.1", "dart_version": "3.13.1", "os": "Darwin", "architecture": "arm64"}),
    "run.container-conflict.2026-08-28": ("runtime", "scripts/labs-container.sh", "2026-08-28T07:15:00Z", "2026-08-28T07:15:01Z", ["source.flutter-labs", "harness.container", "runtime.flutter-3.47.1", "profile.container"], {"profile": "container", "container_runtime": "Docker 29.1.2", "dart_version": "3.13.1"}),
    "run.android-integration.2026-08-28": ("platform", "FLUTTER_ATLAS_DEVICE_ID=emulator-5554 scripts/labs-simulator.sh run", "2026-08-28T08:02:23Z", "2026-08-28T08:02:45Z", ["source.reference-app", "harness.android", "runtime.flutter-3.47.1", "profile.android-emulator"], {"profile": "android-emulator", "device_id": "emulator-5554", "os": "Android 16", "api_level": 36, "architecture": "arm64-v8a", "physical_device": False}),
    "run.android-method-channel.2026-08-28": ("platform", "scripts/definitive-android-runtime.sh", "2026-08-28T11:13:44Z", "2026-08-28T11:14:10Z", ["source.reference-app", "harness.android", "runtime.flutter-3.47.1", "profile.android-emulator"], {"profile": "android-emulator", "device_id": "emulator-5554", "os": "Android 16", "api_level": 36, "physical_device": False}),
    "run.scenario-method-channel.2026-08-30": ("platform", "scripts/scenario-method-channel-runtime.sh", "2026-08-30T10:36:59Z", "2026-08-30T10:44:25Z", ["source.reference-app", "harness.scenario-method-channel", "runtime.flutter-3.47.1", "profile.android-emulator"], {"profile": "android-emulator", "device_id": "emulator-5554", "os": "Android 16", "api_level": 36, "architecture": "arm64-v8a", "physical_device": False}),
    "run.scenario-security-tranche.2026-08-30": ("platform", "scripts/scenario-security-tranche-runtime.sh", "2026-08-30T00:00:00Z", "2026-08-30T00:00:01Z", ["source.reference-app", "harness.scenario-security-tranche", "runtime.flutter-3.47.1", "profile.android-emulator"], {"profile": "android-emulator", "device_id": "emulator-5554", "os": "Android 16", "api_level": 36, "architecture": "arm64-v8a", "physical_device": False}),
    "run.scenario-security-artifact-migration.2026-08-31": ("derived", "python3 tooling/scenario_security_tranche/artifact_migration.py", "2026-08-31T00:00:00+09:00", "2026-08-31T00:00:01+09:00", ["source.atlas-contract", "harness.scenario-security-artifact-migration"], None),
    "run.android-platform-state-validation.2026-08-31": ("derived", "python3 tooling/evidence_dependency/platform_state.py --write", "2026-08-31T00:00:00+09:00", "2026-08-31T00:00:01+09:00", ["harness.android-platform-state-validation"], None),
    "run.scenario-build-android-security.2026-08-31": ("platform", "scripts/scenario-build-android-security-runtime.sh", "2026-08-31T00:00:00Z", "2026-08-31T00:00:01Z", ["source.reference-app", "harness.scenario-build-android-security", "runtime.flutter-3.47.1", "profile.android-emulator"], {"profile": "android-emulator", "device_id": "emulator-5554", "os": "Android 16", "api_level": 36, "architecture": "arm64-v8a", "physical_device": False}),
    "run.scenario-build-web-security.2026-08-31": ("runtime", "scripts/scenario-build-web-security-runtime.sh", "2026-08-31T00:00:00Z", "2026-08-31T00:00:01Z", ["harness.scenario-build-web-security", "runtime.flutter-3.47.1", "profile.web-chrome"], {"profile": "web-chrome", "browser": "Google Chrome", "browser_version": "151.0.7922.175", "os": "macOS 26.1", "architecture": "arm64", "physical_device": False}),
    "run.web-chrome.2026-08-28": ("runtime", "scripts/definitive-web-runtime.sh", "2026-08-28T11:27:00Z", "2026-08-28T11:27:49Z", ["source.reference-app", "harness.web-reference", "runtime.flutter-3.47.1", "profile.web-chrome"], {"profile": "web-chrome", "browser": "Google Chrome", "browser_version": "151.0.7922.175", "os": "Darwin", "architecture": "arm64", "physical_device": False}),
    "run.reference-scenarios.2026-08-28": ("runtime", "scripts/reference-scenario-runtime.sh", "2026-08-28T12:00:00Z", "2026-08-28T12:01:00Z", ["source.reference-app", "harness.web-reference", "runtime.flutter-3.47.1", "profile.web-chrome"], {"profile": "web-chrome", "browser": "Google Chrome", "browser_version": "151.0.7922.175", "os": "Darwin", "architecture": "arm64", "compiler_variants": ["javascript", "wasm"], "physical_device": False}),
    "run.skill-eval.2026-08-28": ("derived", "make skill-eval", "2026-08-28T12:10:00Z", "2026-08-28T12:11:00Z", ["source.atlas-contract", "harness.skill", "runtime.flutter-3.47.1", "profile.local"], None),
    "run.authority-inventory.2026-08-28": ("derived", "make authority-verify", "2026-08-28T12:20:00Z", "2026-08-28T12:21:00Z", ["source.atlas-contract", "harness.authority-parity", "profile.local"], None),
    "run.scenario-proof-generation.2026-08-29": ("derived", "make scenario-proof && python3 tooling/evidence_dependency/graph.py --write", "2026-08-29T00:00:00+09:00", "2026-08-29T00:00:01+09:00", ["source.atlas-contract", "harness.web-reference", "harness.evidence-dependency", ANDROID_BUILD_UNIT_INPUT_ID, WEB_BUILD_UNIT_INPUT_ID, "runtime.flutter-3.47.1", "profile.web-chrome"], None),
    "run.definitive-parity.2026-08-28": ("derived", "python3 tooling/definitive_inventory/generate.py --sdk-root .tools/flutter-3.47.1/flutter && python3 tooling/fe_parity/generate.py", "2026-08-28T12:30:00Z", "2026-08-28T12:31:00Z", ["source.atlas-contract", "harness.authority-parity", "harness.ci-supply-chain", "runtime.flutter-3.47.1", "profile.local"], None),
    "run.provenance.2026-08-29": ("derived", "python3 tooling/generate_provenance.py", "2026-08-29T00:01:00+09:00", "2026-08-29T00:01:01+09:00", ["source.atlas-contract", "source.evidence-dependency-baseline", "harness.authority-parity", "profile.local"], None),
}


def run_configuration(root: Path, run_id: str) -> tuple[Any, ...]:
    configured = RUN_CONFIG[run_id]
    dynamic_report = {
        "run.scenario-method-channel.2026-08-30": "evidence/scenarios/runtime/platform/method-channel/refusal/results.json",
        "run.scenario-security-tranche.2026-08-30": "evidence/scenarios/runtime/accessibility/focus-text-scale/security/results.json",
        "run.scenario-build-android-security.2026-08-31": "evidence/scenarios/runtime/build/android/security/results.json",
        "run.scenario-build-web-security.2026-08-31": "evidence/scenarios/runtime/build/web/security/results.json",
    }.get(run_id)
    if dynamic_report is None:
        return configured
    report = load_json(root, dynamic_report)
    execution_kind, command, _, _, dependencies, _ = configured
    return (
        execution_kind,
        command,
        report["started_at"],
        report["completed_at"],
        dependencies,
        report["runtime_identity"],
    )


def dependencies_for(path: str, output_ids: dict[str, str]) -> list[str]:
    run_id = run_for_path(path)
    direct = list(RUN_CONFIG[run_id][4])
    if path.endswith(PLATFORM_STATE_SUMMARY_SUFFIX):
        raw_path = path.removesuffix(".summary.json") + ".txt"
        direct.append(output_ids[raw_path])
    elif path in SECURITY_ARTIFACT_MIGRATION_PATHS:
        direct.append(output_ids[SECURITY_ARTIFACT_MIGRATION_PATHS[path]])
    elif path.startswith("evidence/scenarios/surfaces/"):
        direct.append(output_ids["evidence/scenarios/integrated/index.json"])
        relative = Path(path).relative_to("evidence/scenarios/surfaces")
        scenario = relative.name.removesuffix(".proof.json")
        runtime_prefix = f"evidence/scenarios/runtime/{relative.parent.as_posix()}/{scenario}/"
        direct.extend(output_ids[item] for item in sorted(output_ids) if item.startswith(runtime_prefix))
    elif path == "evidence/scenarios/index.json":
        direct.extend(output_ids[item] for item in sorted(output_ids) if item.startswith("evidence/scenarios/surfaces/"))
    elif path == PLAN_PATH.as_posix():
        direct.append(output_ids["evidence/scenarios/index.json"])
    elif path.startswith("atlas/definitive/"):
        direct.append(output_ids["evidence/scenarios/index.json"])
    elif run_id == "run.skill-eval.2026-08-28":
        for upstream in ("evidence/scenarios/index.json", "atlas/definitive/flutter-depth-parity.json", "atlas/definitive/gap-ledger.json"):
            if upstream in output_ids:
                direct.append(output_ids[upstream])
    elif path == "provenance.yaml":
        direct.extend(node_id for output_path, node_id in output_ids.items() if output_path != path)
    return sorted(set(direct))


def verify_scenario_proofs_are_tracked(root: Path, tracked_paths: set[str] | None = None) -> None:
    expected = {item["path"] for item in load_json(root, "evidence/scenarios/index.json")["files"]}
    if tracked_paths is None:
        if not (root / ".git").exists():
            return
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", "evidence/scenarios/surfaces"],
            check=True,
            capture_output=True,
        )
        tracked_paths = {value.decode() for value in result.stdout.split(b"\0") if value}
    missing = sorted(expected - tracked_paths)
    if missing:
        raise DependencyError(f"Scenario Proofがgit ls-filesに含まれません: count={len(missing)} first={missing[0]}")


def proof_structure(root: Path, index: dict[str, Any]) -> dict[str, Any]:
    files = []
    for item in index["files"]:
        proof = load_json(root, item["path"])
        bindings = [{"variant_id": binding.get("variant_id"), "path": binding["path"]} for binding in proof["source_bindings"]]
        files.append({
            "id": item["id"], "pattern_id": item.get("pattern_id"), "scenario": item["scenario"],
            "path": item["path"], "proof_id": proof["id"], "target_id": proof.get("target_id"),
            "target_set": proof.get("target_set"), "behavior_scope": proof["behavior_scope"],
            "source_bindings": bindings,
        })
    return {"id": index["id"], "atlas_id": index["atlas_id"], "denominator": index["denominator"], "files": files}


def flutter_proof_structure(root: Path, index: dict[str, Any]) -> dict[str, Any]:
    files = []
    for item in index["files"]:
        proof = load_json(root, item["path"])
        files.append({
            "id": item["id"], "surface_id": item["surface_id"], "scenario": item["scenario"],
            "path": item["path"], "proof_id": proof["id"], "domain": proof["domain"],
            "behavior_scope": proof["behavior_scope"],
            "variant_ids": sorted(proof["dedicated_runtime"]["baseline_variants"]),
            "source_paths": [binding["path"] for binding in proof["source_bindings"]],
        })
    return {"id": index["id"], "atlas_id": index["atlas_id"], "denominator": index["denominator"], "files": files}


def closure_structure(plan: dict[str, Any]) -> dict[str, Any]:
    tranches = [
        {key: item[key] for key in ("id", "risk_rank", "scenario", "row_ids", "pattern_rows", "variant_runs", "commit_policy")}
        for field in ("completed_tranches", "tranches")
        for item in plan.get(field, [])
    ]
    ordered = [
        *(row_id for item in plan.get("completed_tranches", []) for row_id in item["row_ids"]),
        *(item["id"] for item in plan["rows"]),
    ]
    return {"id": plan["id"], "scope": plan["scope"], "policy": plan["policy"], "baseline": plan["baseline"], "tranches": tranches, "ordered_row_ids": ordered}


def structure_digest(root: Path, kind: str, path: str) -> str:
    document = load_json(root, path)
    if kind == "scenario-proof-index":
        value = proof_structure(root, document)
    elif kind == "scenario-closure-plan":
        value = closure_structure(document)
    else:
        raise DependencyError(f"未知の構造kindです: {kind}")
    return sha_bytes(canonical(value))


def build_closure_plan(root: Path) -> dict[str, Any]:
    index = load_json(root, "evidence/scenarios/index.json")
    ranks = {scenario: position + 1 for position, scenario in enumerate(RISK_ORDER)}
    rows = []
    for item in index["files"]:
        proof = load_json(root, item["path"])
        scenario = proof["scenario"]
        variants = sorted(proof["dedicated_runtime"]["baseline_variants"])
        if not variants:
            variants = ["unresolved-variant-contract"]
        rows.append({
            "id": f"closure.{proof['surface_id']}.{scenario}", "pattern_id": proof["surface_id"],
            "target_id": proof["surface_id"], "scenario": scenario, "risk_rank": ranks[scenario],
            "proof": {"path": item["path"], "digest": item["digest"]}, "variant_ids": variants,
            "runtime_variant_ids": proof["dedicated_runtime"]["declared_variants"],
            "variant_contract_status": "resolved-runtime" if proof["dedicated_runtime"]["declared_variants"] else "unresolved",
            "required_closure": {
                "drive_pattern_scenario_and_every_variant": True, "first_attempt_only": True, "retries": 0,
                "dedicated_runtime_identity": True, "dedicated_oracle": True, "separate_trace_per_variant": True,
                "required_trace_streams": ["action", "network", "resource"], "separate_screenshot_per_variant": True,
                "source_and_harness_digests": True,
                "forbidden_substitutions": ["metadata-only", "capture-reuse", "integrated-trace-reuse", "mock-or-static-runtime"],
            },
            "gaps": proof["gaps"],
            "runtime_status": "completed" if proof["closure"]["dedicated_surface_scenario_runtime"] else "open",
        })
    rows.sort(key=lambda row: (row["risk_rank"], row["pattern_id"]))
    tranches = []
    for scenario in RISK_ORDER:
        selected = [row for row in rows if row["scenario"] == scenario]
        for start in range(0, len(selected), 4):
            chunk = selected[start:start + 4]
            tranches.append({
                "id": f"{scenario}-{start // 4 + 1:03d}", "risk_rank": ranks[scenario], "scenario": scenario,
                "status": "planned", "row_ids": [row["id"] for row in chunk], "pattern_rows": len(chunk),
                "variant_runs": sum(len(row["variant_ids"]) for row in chunk),
                "commit_policy": "one-reviewed-tranche-with-non-regression-runtime-identity-and-oracle-validation",
            })
    completed_ids = [row["id"] for row in rows if row["runtime_status"] == "completed"]
    completed_set = set(completed_ids)
    completed_tranches = []
    for tranche in tranches:
        closed = sum(row_id in completed_set for row_id in tranche["row_ids"])
        tranche_rows = [row for row in rows if row["id"] in tranche["row_ids"]]
        tranche["completed_variant_runs"] = sum(
            len(row["runtime_variant_ids"]) for row in tranche_rows if row["runtime_status"] == "completed"
        )
        tranche["completed_pattern_rows"] = closed
        tranche["status"] = "completed" if closed == tranche["pattern_rows"] else "partially-completed" if closed else "planned"
        if tranche["status"] == "completed":
            completed_tranches.append(tranche)
    by_scenario = {
        scenario: {
            "total": sum(row["scenario"] == scenario for row in rows),
            "completed": sum(row["scenario"] == scenario and row["runtime_status"] == "completed" for row in rows),
            "remaining": sum(row["scenario"] == scenario and row["runtime_status"] != "completed" for row in rows),
        }
        for scenario in RISK_ORDER
    }
    next_tranche = next((item for item in tranches if item["status"] != "completed"), None)
    return {
        "schema_version": 1, "id": "flutter-surface-scenario-closure-plan-v1", "atlas_id": "flutter-reference-atlas",
        "generated_at": GENERATED_AT, "status": "incomplete",
        "scope": "54 provisional Flutter Surfaceと10 Scenarioの全540 gapを専用実Platform Runtimeで閉じる計画。",
        "policy": {"risk_order": list(RISK_ORDER), "maximum_pattern_rows_per_tranche": 4, "monotonic_addition": True, "mass_closure_forbidden": True},
        "source_digests": {"evidence/scenarios/index.json": sha_file(root, "evidence/scenarios/index.json"), "evidence/scenarios/integrated/index.json": sha_file(root, "evidence/scenarios/integrated/index.json")},
        "baseline": {"matrix_rows": index["summary"]["rows"], "patterns": index["summary"]["surfaces"], "scenarios": 10, "inherited_gap_rows_at_f0e1633": 540},
        "summary": {"completed_dedicated_rows": len(completed_ids), "remaining_rows": len(rows) - len(completed_ids), "planned_tranches": len(tranches), "completed_tranches": len(completed_tranches), "by_scenario": by_scenario},
        "independent_incomplete": {"authority_atomic_rows": index["summary"]["authority_atomic_rows"], "external_profiles": ["android-device", "ios-device", "ios-simulator", "linux-host", "windows-host"], "agent_forward_eval": "not-executed-required"},
        "completed_rows": completed_ids, "completed_tranches": completed_tranches, "next_tranche": next_tranche,
        "tranches": tranches, "rows": rows,
    }


def input_ancestors(node_id: str, inputs: dict[str, dict[str, Any]], outputs: dict[str, dict[str, Any]], visiting: set[str] | None = None) -> set[str]:
    if node_id in inputs:
        return {node_id}
    visiting = set() if visiting is None else visiting
    if node_id in visiting:
        raise DependencyError(f"Dependency cycleがあります: {node_id}")
    if node_id not in outputs:
        raise DependencyError(f"未知nodeです: {node_id}")
    visiting.add(node_id)
    result: set[str] = set()
    for dependency in outputs[node_id]["depends_on"]:
        result.update(input_ancestors(dependency, inputs, outputs, visiting))
    visiting.remove(node_id)
    return result


def build_graph(root: Path) -> dict[str, Any]:
    inputs_list = input_definitions(root)
    inputs = {item["id"]: item for item in inputs_list}
    paths = discover_outputs(root)
    outputs_list = []
    for path, node_id in paths.items():
        run_id = run_for_path(path)
        outputs_list.append({
            "id": node_id, "kind": output_kind(path), "path": path, "digest": sha_file(root, path),
            "depends_on": dependencies_for(path, paths), "status": "current", "run_id": run_id,
        })
    outputs = {item["id"]: item for item in outputs_list}
    by_run: dict[str, list[str]] = {}
    for output in outputs_list:
        by_run.setdefault(output["run_id"], []).append(output["id"])
    runs = []
    for run_id, output_ids in sorted(by_run.items()):
        execution_kind, command, started, completed, _, identity = run_configuration(root, run_id)
        ancestors: set[str] = set()
        for node_id in output_ids:
            ancestors.update(input_ancestors(node_id, inputs, outputs))
        run = {
            "id": run_id, "execution_kind": execution_kind, "command": command,
            "started_at": started, "completed_at": completed, "result": "passed", "attempts": 1,
            "input_bindings": [{"input_id": item, "digest": inputs[item]["current_digest"]} for item in sorted(ancestors)],
            "output_ids": sorted(output_ids),
        }
        if identity is not None:
            run["runtime_identity"] = identity
        runs.append(run)
    structures = [
        {"id": "structure.scenario-proof-index.v1", "kind": "scenario-proof-index", "path": "evidence/scenarios/index.json", "baseline_digest": structure_digest(root, "scenario-proof-index", "evidence/scenarios/index.json")},
        {"id": "structure.scenario-closure-plan.v1", "kind": "scenario-closure-plan", "path": PLAN_PATH.as_posix(), "baseline_digest": structure_digest(root, "scenario-closure-plan", PLAN_PATH.as_posix())},
    ]
    return {
        "schema_version": 1, "atlas_id": "flutter-reference-atlas", "generated_at": GENERATED_AT,
        "status": "current", "policy": POLICY, "inputs": inputs_list, "outputs": outputs_list,
        "runs": runs, "required_outputs": sorted(paths), "structures": structures,
    }


def evidence_families(paths: Iterable[str]) -> dict[str, dict[str, Any]]:
    path_set = set(paths)
    formal = [path for path in path_set if "formal-local-closure" in path]
    android = [path for path in path_set if "android-emulator-integration" in path]
    method = [path for path in path_set if "android-method-channel" in path]
    web = [path for path in path_set if "web-chrome" in path]
    integrated = [path for path in path_set if path.startswith("evidence/scenarios/integrated/")]
    return {
        "unit": {"status": "present", "paths": sorted(formal)},
        "widget": {"status": "present", "paths": sorted(formal)},
        "integration": {"status": "present", "paths": sorted(android + method)},
        "golden": {"status": "not-present-gap", "paths": []},
        "performance": {"status": "present", "paths": sorted(formal + web)},
        "platform": {"status": "present", "paths": sorted(method + web)},
        "device": {"status": "present-emulator-not-physical-device", "paths": sorted(android + method)},
        "reference-system": {"status": "present", "paths": sorted(integrated)},
        "scenario-proof": {"status": "present-incomplete", "paths": sorted(path for path in path_set if path.endswith(".proof.json"))},
        "scenario-runtime": {"status": "present" if any(path.startswith("evidence/scenarios/runtime/") for path in path_set) else "not-present-gap", "paths": sorted(path for path in path_set if path.startswith("evidence/scenarios/runtime/"))},
    }


def build_baseline(root: Path, graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1, "atlas_id": graph["atlas_id"], "captured_at": GENERATED_AT,
        "core_contract": {"commit": CORE_COMMIT, "release_status": "main-ci-passed"},
        "input_ids": [item["id"] for item in graph["inputs"]],
        "required_output_paths": graph["required_outputs"],
        "run_ids": [item["id"] for item in graph["runs"]],
        "profiles": ["local", "container", "android-emulator", "web-chrome"],
        "evidence_families": evidence_families(graph["required_outputs"]),
        "thresholds": {"attempts": 1, "maximum_pattern_rows_per_tranche": 4, "scenario_count": 10, "scenario_rows": 540, "proof_structure_invariant": True, "closure_plan_structure_invariant": True},
        "structures": {item["kind"]: item["baseline_digest"] for item in graph["structures"]},
        "flutter_structures": {
            "scenario-proof-surface-variant-topology": sha_bytes(canonical(flutter_proof_structure(root, load_json(root, "evidence/scenarios/index.json"))))
        },
        "replacement_policy": {"old_to_new_mapping_required": True, "equal_or_stronger_execution_proof_required": True, "migration_evidence_required": True, "reason_required": True},
    }


def reconcile_additive(root: Path, prior: dict[str, Any], observed_at: str) -> dict[str, Any]:
    """Add new inputs/outputs without erasing the previous digest lineage."""
    parse_time(observed_at)
    candidate = build_graph(root)
    prior_inputs = {item["id"]: item for item in prior["inputs"]}
    candidate_inputs = {item["id"]: item for item in candidate["inputs"]}
    verify_android_build_input_migration(root, candidate_inputs)
    verify_web_build_input_migration(root, candidate_inputs)
    previous_android = prior_inputs.get(ANDROID_BUILD_INPUT_ID)
    android_input_migrated = previous_android is not None and set(previous_android["members"]) == (
        set(candidate_inputs[ANDROID_BUILD_INPUT_ID]["members"]) | {ANDROID_BUILD_TEST_PATH}
    )
    previous_web = prior_inputs.get(WEB_BUILD_INPUT_ID)
    baseline_input_ids = set(load_json(root, BASELINE_PATH)["input_ids"])
    web_input_migrated = (
        WEB_BUILD_UNIT_INPUT_ID not in baseline_input_ids
        and web_build_input_migration_matches(root, previous_web, candidate_inputs)
    )
    changed_inputs: set[str] = set()
    for item in candidate["inputs"]:
        previous = prior_inputs.get(item["id"])
        if previous is None:
            item["observed_at"] = observed_at
            changed_inputs.add(item["id"])
            continue
        if item["id"] == ANDROID_BUILD_INPUT_ID and android_input_migrated:
            item["baseline_digest"] = item["current_digest"]
            item["observed_at"] = previous["observed_at"]
            continue
        if item["id"] == WEB_BUILD_INPUT_ID and web_input_migrated:
            item["baseline_digest"] = item["current_digest"]
            item["observed_at"] = previous["observed_at"]
            continue
        item["baseline_digest"] = previous["baseline_digest"]
        if item["current_digest"] != previous["current_digest"] or item["members"] != previous["members"]:
            item["observed_at"] = observed_at
            changed_inputs.add(item["id"])
        else:
            item["observed_at"] = previous["observed_at"]

    prior_structures = {item["kind"]: item for item in prior["structures"]}
    for item in candidate["structures"]:
        previous = prior_structures.get(item["kind"])
        if previous is None:
            raise DependencyError(f"additive reconcileで未知structureを追加できません: {item['kind']}")
        actual = structure_digest(root, item["kind"], item["path"])
        if actual != previous["baseline_digest"]:
            raise DependencyError(f"additive reconcileでProof/Closure構造を変更できません: {item['kind']}")
        item["baseline_digest"] = previous["baseline_digest"]

    inputs = {item["id"]: item for item in candidate["inputs"]}
    outputs = {item["id"]: item for item in candidate["outputs"]}
    prior_outputs = {item["id"]: item for item in prior["outputs"]}
    stale_runs: set[str] = set()
    for item in candidate["outputs"]:
        previous = prior_outputs.get(item["id"])
        ancestors = input_ancestors(item["id"], inputs, outputs)
        changed = bool(ancestors & changed_inputs)
        if previous is None:
            item["status"] = "stale"
            stale_runs.add(item["run_id"])
            continue
        dependencies_changed = item["depends_on"] != previous["depends_on"] or item["run_id"] != previous["run_id"]
        digest_changed = item["digest"] != previous["digest"]
        item["digest"] = previous["digest"]
        item["status"] = "stale" if changed or dependencies_changed or digest_changed else previous["status"]
        if (
            web_input_migrated
            and item["run_id"] == "run.scenario-build-web-security.2026-08-31"
            and not dependencies_changed
            and not digest_changed
        ):
            item["status"] = "current"
        if item["status"] == "stale":
            stale_runs.add(item["run_id"])

    prior_runs = {item["id"]: item for item in prior["runs"]}
    for run in candidate["runs"]:
        previous = prior_runs.get(run["id"])
        if previous is None:
            continue
        for key in ("started_at", "completed_at", "result", "attempts", "input_bindings"):
            run[key] = previous[key]
        if "runtime_identity" in previous:
            run["runtime_identity"] = previous["runtime_identity"]
        if run["id"] == "run.scenario-build-android-security.2026-08-31" and android_input_migrated:
            for binding in run["input_bindings"]:
                if binding["input_id"] == ANDROID_BUILD_INPUT_ID:
                    binding["digest"] = candidate_inputs[ANDROID_BUILD_INPUT_ID]["current_digest"]
        if run["id"] == "run.scenario-build-web-security.2026-08-31" and web_input_migrated:
            for binding in run["input_bindings"]:
                if binding["input_id"] == WEB_BUILD_INPUT_ID:
                    binding["digest"] = candidate_inputs[WEB_BUILD_INPUT_ID]["current_digest"]

    candidate["generated_at"] = observed_at
    candidate["status"] = "stale" if any(item["status"] == "stale" for item in candidate["outputs"]) else "current"
    return candidate


def extend_baseline(root: Path, graph: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Freeze additive Graph members after the new Evidence has passed."""
    verify_graph(root, graph)
    baseline["input_ids"] = sorted(set(baseline["input_ids"]) | {item["id"] for item in graph["inputs"]})
    baseline["required_output_paths"] = sorted(set(baseline["required_output_paths"]) | set(graph["required_outputs"]))
    baseline["run_ids"] = sorted(set(baseline["run_ids"]) | {item["id"] for item in graph["runs"]})
    current = evidence_families(graph["required_outputs"])
    for family, actual in current.items():
        previous = baseline["evidence_families"].get(family)
        if previous is None:
            baseline["evidence_families"][family] = actual
            continue
        previous["paths"] = sorted(set(previous["paths"]) | set(actual["paths"]))
        if previous["status"].startswith("not-present") and not actual["status"].startswith("not-present"):
            previous["status"] = actual["status"]
    return baseline


def parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as error:
        raise DependencyError(f"RFC3339時刻が不正です: {value}") from error


def security_runtime_report_attests_current_inputs(root: Path, started_at: str) -> bool:
    expected_members = {
        "scripts/scenario-security-tranche-runtime.sh",
        "tooling/scenario_security_tranche/report.py",
        "tooling/scenario_security_tranche/security_tranche_scenario_test.dart",
    }
    input_item = next(
        (item for item in input_definitions(root) if item["id"] == "harness.scenario-security-tranche"),
        None,
    )
    if input_item is None or set(input_item["members"]) != expected_members:
        return False
    reports = [load_json(root, prefix + "results.json") for prefix in SECURITY_RUNTIME_PREFIXES]
    if len(reports) != 8:
        return False
    for report in reports:
        if report.get("started_at") != started_at or report.get("status") != "passed" or report.get("retries") != 0:
            return False
        bindings = [report.get("harness"), report.get("reporter")]
        bindings.extend(test.get("source") for test in report.get("tests", []))
        for binding in bindings:
            if not isinstance(binding, dict) or binding.get("path") not in expected_members:
                return False
            if binding.get("digest") != sha_file(root, binding["path"]):
                return False
    return True


def verify_graph(root: Path, graph: dict[str, Any]) -> dict[str, int]:
    platform_state.verify_all(root, write=False)
    verify_scenario_proofs_are_tracked(root)
    if graph.get("policy") != POLICY:
        raise DependencyError("Evidence dependency policyがCore契約と一致しません")
    if graph.get("status") != "current":
        raise DependencyError("Evidence dependency graphはstaleです")
    inputs: dict[str, dict[str, Any]] = {}
    changed: dict[str, datetime] = {}
    expected_inputs = {item["id"]: item for item in input_definitions(root)}
    if set(expected_inputs) != {item["id"] for item in graph["inputs"]}:
        raise DependencyError("input ID機械列挙が現在の定義と一致しません")
    verify_android_build_input_migration(root, expected_inputs)
    verify_web_build_input_migration(root, expected_inputs)
    for item in graph["inputs"]:
        if item["id"] in inputs:
            raise DependencyError(f"input ID重複: {item['id']}")
        members = [safe_relative(path) for path in item["members"]]
        if item["kind"] != expected_inputs[item["id"]]["kind"] or members != expected_inputs[item["id"]]["members"]:
            raise DependencyError(f"input member機械列挙が現在の定義と一致しません: {item['id']}")
        actual = digest_members(root, members)
        if actual != item["current_digest"]:
            raise DependencyError(f"input current_digest不一致: {item['id']}")
        inputs[item["id"]] = item
        if item["baseline_digest"] != item["current_digest"]:
            changed[item["id"]] = parse_time(item["observed_at"])
    outputs: dict[str, dict[str, Any]] = {}
    output_paths: dict[str, str] = {}
    for item in graph["outputs"]:
        path = safe_relative(item["path"])
        if item["id"] in outputs or path in output_paths:
            raise DependencyError(f"output ID/Path重複: {item['id']} {path}")
        if sha_file(root, path) != item["digest"]:
            raise DependencyError(f"output digest不一致: {item['id']}")
        if item["status"] != "current":
            raise DependencyError(f"outputがstaleです: {item['id']}")
        outputs[item["id"]] = item
        output_paths[path] = item["id"]
    discovered = set(discover_outputs(root))
    required = set(graph["required_outputs"])
    if discovered != required:
        missing = sorted(discovered - required)
        retreat = sorted(required - discovered)
        raise DependencyError(f"必要output機械列挙不一致 missing={missing[:3]} retreat={retreat[:3]}")
    if required != set(output_paths):
        raise DependencyError("required_outputsとoutputsの集合が一致しません")
    for node_id in outputs:
        ancestors = input_ancestors(node_id, inputs, outputs)
        if not ancestors:
            raise DependencyError(f"outputが入力へ到達しません: {node_id}")
    runs = {item["id"]: item for item in graph["runs"]}
    if len(runs) != len(graph["runs"]):
        raise DependencyError("run IDが重複しています")
    affected = 0
    for node_id, output in outputs.items():
        run = runs.get(output.get("run_id"))
        if run is None or node_id not in run["output_ids"]:
            raise DependencyError(f"outputの実runまたはrerun対象がありません: {node_id}")
        if run["result"] != "passed" or run["attempts"] != 1:
            raise DependencyError(f"first-attempt passではありません: {run['id']}")
        started, completed = parse_time(run["started_at"]), parse_time(run["completed_at"])
        if completed < started:
            raise DependencyError(f"run時刻が逆転しています: {run['id']}")
        if run["execution_kind"] != "derived" and not run.get("runtime_identity"):
            raise DependencyError(f"実Runtime identityがありません: {run['id']}")
        bindings = {item["input_id"]: item["digest"] for item in run["input_bindings"]}
        ancestors = input_ancestors(node_id, inputs, outputs)
        for input_id in ancestors:
            if bindings.get(input_id) != inputs[input_id]["current_digest"]:
                raise DependencyError(f"現在input binding不一致: run={run['id']} input={input_id} output={node_id}")
            if input_id in changed:
                affected += 1
                if started < changed[input_id]:
                    raise DependencyError(f"digest-only closure拒否: input={input_id} output={node_id}")
    for run in runs.values():
        unknown = set(run["output_ids"]) - set(outputs)
        if unknown:
            raise DependencyError(f"runが未知outputを参照しています: {run['id']} {sorted(unknown)}")
    kinds = set()
    for structure in graph["structures"]:
        if structure["kind"] in kinds:
            raise DependencyError(f"構造baseline重複: {structure['kind']}")
        kinds.add(structure["kind"])
        actual = structure_digest(root, structure["kind"], structure["path"])
        if actual != structure["baseline_digest"]:
            raise DependencyError(f"Proof/Closure Plan構造縮小または差替え: {structure['kind']}")
    if kinds != {"scenario-proof-index", "scenario-closure-plan"}:
        raise DependencyError("Proof/Closure Plan構造baselineが不足しています")
    return {"inputs": len(inputs), "outputs": len(outputs), "runs": len(runs), "changed_inputs": len(changed), "affected_bindings": affected}


def verify_baseline(root: Path, graph: dict[str, Any], baseline: dict[str, Any]) -> None:
    if baseline["core_contract"] != {"commit": CORE_COMMIT, "release_status": "main-ci-passed"}:
        raise DependencyError("Core main/CI成功commit pinが不正です")
    if not set(baseline["input_ids"]).issubset(item["id"] for item in graph["inputs"]):
        raise DependencyError("inputをbaseline外へ退避または削除しました")
    if not set(baseline["required_output_paths"]).issubset(graph["required_outputs"]):
        raise DependencyError("Evidence outputをbaseline外へ退避または削除しました")
    if not set(baseline["run_ids"]).issubset(item["id"] for item in graph["runs"]):
        raise DependencyError("実行runをbaseline外へ退避または削除しました")
    expected_thresholds = {"attempts": 1, "maximum_pattern_rows_per_tranche": 4, "scenario_count": 10, "scenario_rows": 540, "proof_structure_invariant": True, "closure_plan_structure_invariant": True}
    if baseline["thresholds"] != expected_thresholds:
        raise DependencyError("試験・Scenario・tranche閾値が縮小または変更されました")
    graph_structures = {item["kind"]: item["baseline_digest"] for item in graph["structures"]}
    if baseline["structures"] != graph_structures:
        raise DependencyError("Proof/Closure Plan構造baselineが変化しました")
    flutter_structures = {
        "scenario-proof-surface-variant-topology": sha_bytes(canonical(flutter_proof_structure(root, load_json(root, "evidence/scenarios/index.json"))))
    }
    if baseline.get("flutter_structures") != flutter_structures:
        raise DependencyError("Flutter Surface/Variant/Source topologyが縮小または差替えされました")
    current_families = evidence_families(graph["required_outputs"])
    for family, expected in baseline["evidence_families"].items():
        actual = current_families.get(family)
        if actual is None or expected["status"] != actual["status"] or not set(expected["paths"]).issubset(actual["paths"]):
            raise DependencyError(f"Evidence familyが縮小または退避されました: {family}")


def refresh_stale(root: Path, graph: dict[str, Any], observed_at: str) -> dict[str, Any]:
    parse_time(observed_at)
    inputs = {item["id"]: item for item in graph["inputs"]}
    outputs = {item["id"]: item for item in graph["outputs"]}
    changed_ids = set()
    for item in graph["inputs"]:
        actual = digest_members(root, item["members"])
        if actual != item["current_digest"]:
            item["current_digest"] = actual
            item["observed_at"] = observed_at
            changed_ids.add(item["id"])
    if not changed_ids:
        return graph
    for node_id, output in outputs.items():
        if input_ancestors(node_id, inputs, outputs) & changed_ids:
            output["status"] = "stale"
    graph["status"] = "stale"
    graph["generated_at"] = observed_at
    return graph


def record_rerun(root: Path, graph: dict[str, Any], run_id: str, started_at: str, completed_at: str) -> dict[str, Any]:
    started, completed = parse_time(started_at), parse_time(completed_at)
    if completed < started:
        raise DependencyError("rerun完了時刻が開始時刻より前です")
    inputs = {item["id"]: item for item in graph["inputs"]}
    outputs = {item["id"]: item for item in graph["outputs"]}
    run = next((item for item in graph["runs"] if item["id"] == run_id), None)
    if run is None:
        raise DependencyError(f"未知のrerun IDです: {run_id}")
    target_ids = set(run["output_ids"])
    for node_id in target_ids:
        output = outputs[node_id]
        for dependency in output["depends_on"]:
            if dependency in outputs and outputs[dependency]["status"] != "current" and dependency not in target_ids:
                raise DependencyError(f"上流outputがstaleのためrerun順序が不正です: {dependency} -> {node_id}")
    ancestors: set[str] = set()
    for node_id in target_ids:
        ancestors.update(input_ancestors(node_id, inputs, outputs))
    for input_id in ancestors:
        actual = digest_members(root, inputs[input_id]["members"])
        if actual != inputs[input_id]["current_digest"]:
            raise DependencyError(f"rerun前に--refresh-staleが必要です: {input_id}")
        if inputs[input_id]["baseline_digest"] != inputs[input_id]["current_digest"] and started < parse_time(inputs[input_id]["observed_at"]):
            attested = (
                run_id == "run.scenario-security-tranche.2026-08-30"
                and input_id == "harness.scenario-security-tranche"
                and security_runtime_report_attests_current_inputs(root, started_at)
            )
            if not attested:
                raise DependencyError(f"rerun開始が入力変更観測前です: {input_id}")
            inputs[input_id]["observed_at"] = started_at
    for node_id in target_ids:
        output = outputs[node_id]
        output["digest"] = sha_file(root, output["path"])
        output["status"] = "current"
    run["started_at"] = started_at
    run["completed_at"] = completed_at
    run["result"] = "passed"
    run["attempts"] = 1
    run["input_bindings"] = [{"input_id": input_id, "digest": inputs[input_id]["current_digest"]} for input_id in sorted(ancestors)]
    for structure in graph["structures"]:
        actual = structure_digest(root, structure["kind"], structure["path"])
        if actual != structure["baseline_digest"]:
            raise DependencyError(f"rerunで構造baselineを変更できません: {structure['kind']}")
    graph["generated_at"] = completed_at
    graph["status"] = "current" if all(item["status"] == "current" for item in graph["outputs"]) else "stale"
    if graph["status"] == "current":
        verify_graph(root, graph)
    return graph


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--initialize-baseline", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--check-baseline", action="store_true")
    parser.add_argument("--refresh-stale", action="store_true")
    parser.add_argument("--observed-at")
    parser.add_argument("--record-rerun")
    parser.add_argument("--reconcile-additive", action="store_true")
    parser.add_argument("--extend-baseline", action="store_true")
    parser.add_argument("--started-at")
    parser.add_argument("--completed-at")
    args = parser.parse_args()
    try:
        if args.reconcile_additive:
            if not args.observed_at:
                raise DependencyError("--reconcile-additiveには--observed-atが必要です")
            write_json(ROOT, PLAN_PATH, build_closure_plan(ROOT))
            graph = reconcile_additive(ROOT, load_json(ROOT, GRAPH_PATH), args.observed_at)
            write_json(ROOT, GRAPH_PATH, graph)
            pending = sorted({item["run_id"] for item in graph["outputs"] if item["status"] == "stale"})
            print(f"Evidence Dependency Graphをadditive reconcileしました: status={graph['status']} pending={pending}")
            return 0
        if args.write:
            write_json(ROOT, PLAN_PATH, build_closure_plan(ROOT))
            graph = build_graph(ROOT)
            write_json(ROOT, GRAPH_PATH, graph)
            if args.initialize_baseline:
                write_json(ROOT, BASELINE_PATH, build_baseline(ROOT, graph))
        else:
            graph = load_json(ROOT, GRAPH_PATH)
        if args.extend_baseline:
            baseline = extend_baseline(ROOT, graph, load_json(ROOT, BASELINE_PATH))
            write_json(ROOT, BASELINE_PATH, baseline)
            verify_baseline(ROOT, graph, baseline)
            print("Evidence Dependency baselineを加法更新しました")
            return 0
        if args.refresh_stale:
            if not args.observed_at:
                raise DependencyError("--refresh-staleには--observed-atが必要です")
            graph = refresh_stale(ROOT, graph, args.observed_at)
            write_json(ROOT, GRAPH_PATH, graph)
            print(f"Evidence Dependency Graphを{graph['status']}へ更新しました")
            return 0
        if args.record_rerun:
            if not args.started_at or not args.completed_at:
                raise DependencyError("--record-rerunには--started-atと--completed-atが必要です")
            graph = record_rerun(ROOT, graph, args.record_rerun, args.started_at, args.completed_at)
            write_json(ROOT, GRAPH_PATH, graph)
            print(f"Evidence rerunを記録しました: {args.record_rerun} graph_status={graph['status']}")
            return 0
        result = verify_graph(ROOT, graph)
        if args.check_baseline or args.initialize_baseline:
            verify_baseline(ROOT, graph, load_json(ROOT, BASELINE_PATH))
        print("Evidence Dependency Graph検証済み: " + " ".join(f"{key}={value}" for key, value in result.items()))
        return 0
    except (DependencyError, FileNotFoundError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"Evidence Dependency Graphエラー: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
