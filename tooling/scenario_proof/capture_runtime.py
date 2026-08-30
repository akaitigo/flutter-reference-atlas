#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Capture ten dedicated Flutter Reference App scenario traces from machine logs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCENARIOS = ("normal", "boundary", "refusal", "failure", "recovery", "migration", "operations", "security", "performance", "compatibility")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tooling.scenario_proof.atomic_publish import atomic_publish_directory  # noqa: E402

GENERATED_AT = "2026-08-28T00:00:00+09:00"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def binding(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    return {"path": relative, "digest": digest(path), "bytes": path.stat().st_size}


def run_digest(paths: tuple[Path, Path], identity: dict[str, Any]) -> str:
    value = hashlib.sha256()
    for variant, path in zip(("javascript", "wasm"), paths):
        value.update(variant.encode())
        value.update(b"\0")
        value.update(path.read_bytes())
        value.update(b"\0")
    value.update(json.dumps(identity, sort_keys=True).encode())
    return "sha256:" + value.hexdigest()


def parse_log(path: Path) -> tuple[dict[str, dict[str, Any]], bool]:
    names: dict[int, tuple[str, int]] = {}
    results: dict[str, dict[str, Any]] = {}
    done = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "testStart":
            test = event.get("test", {})
            match = re.match(r"^\[scenario:([a-z-]+)\]", str(test.get("name", "")))
            if match:
                names[int(test["id"])] = (match.group(1), int(event.get("time", 0)))
        elif event.get("type") == "testDone" and int(event.get("testID", -1)) in names:
            scenario, started = names[int(event["testID"])]
            results[scenario] = {
                "result": event.get("result"),
                "skipped": bool(event.get("skipped")),
                "duration_ms": int(event.get("time", 0)) - started,
            }
        elif event.get("type") == "done":
            done = event.get("success") is True
    return results, done


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--js-log", type=Path, required=True)
    parser.add_argument("--wasm-log", type=Path, required=True)
    parser.add_argument("--browser-version", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--architecture", required=True)
    parser.add_argument("--flutter-version", required=True)
    parser.add_argument("--dart-version", required=True)
    parser.add_argument("--output-root", default="evidence/scenarios/integrated")
    args = parser.parse_args()
    variants = {}
    for variant, path in (("javascript", args.js_log), ("wasm", args.wasm_log)):
        results, done = parse_log(path)
        if not done or tuple(sorted(results)) != tuple(sorted(SCENARIOS)):
            raise SystemExit(f"{variant} Scenario setまたは完了Eventが不正です: {sorted(results)}")
        if any(item["result"] != "success" or item["skipped"] for item in results.values()):
            raise SystemExit(f"{variant} Scenarioに失敗またはskipがあります")
        variants[variant] = results

    source_files = [
        "reference-systems/operations-workspace/lib/src/presentation/workspace_app.dart",
        "reference-systems/operations-workspace/lib/src/presentation/workspace_controller.dart",
        "reference-systems/operations-workspace/lib/src/data/incident_snapshot_migration.dart",
        "reference-systems/operations-workspace/lib/src/domain/incident_input_policy.dart",
        "reference-systems/operations-workspace/lib/src/observability/frame_performance_monitor.dart",
        "integrations/reference-system/manifest.json",
    ]
    harness_files = [
        "reference-systems/operations-workspace/test/scenario_trace_test.dart",
        "scripts/reference-scenario-runtime.sh",
        "tooling/scenario_proof/atomic_publish.py",
        "tooling/scenario_proof/capture_runtime.py",
    ]
    runtime_identity = {
        "profile": "web-chrome",
        "runner_kind": "browser-runtime",
        "browser": "Google Chrome",
        "browser_version": args.browser_version,
        "os": args.platform,
        "architecture": args.architecture,
        "flutter_version": args.flutter_version,
        "dart_version": args.dart_version,
        "physical_device": False,
        "compiler_variants": ["javascript", "wasm"],
    }
    output_relative = Path(args.output_root)
    if output_relative.is_absolute() or ".." in output_relative.parts:
        raise SystemExit("output-rootはRepository内の相対Pathである必要があります")
    output_dir = ROOT / output_relative
    run_id = run_digest((args.js_log, args.wasm_log), runtime_identity)

    def build_bundle(staging: Path) -> None:
        files = []
        for scenario in SCENARIOS:
            trace = {
                "schema_version": 1,
                "id": f"trace.reference-system.{scenario}",
                "atlas_id": "flutter-reference-atlas",
                "generated_at": GENERATED_AT,
                "run_id": run_id,
                "scenario": scenario,
                "status": "passed",
                "runtime_identity": runtime_identity,
                "source_bindings": [binding(item) for item in source_files],
                "harness_bindings": [binding(item) for item in harness_files],
                "variants": [
                    {"id": variant, **variants[variant][scenario]}
                    for variant in ("javascript", "wasm")
                ],
                "trace_contract": {
                    "format": "flutter-test-machine-scenario-events",
                    "event_streams": ["testStart", "testDone", "done"],
                    "dedicated_scenario_artifact": True,
                },
                "closure": {
                    "bounded_integrated_trace": True,
                    "surface_specific_proof": False,
                    "authority_atomic_binding": False,
                    "completion_eligible": False,
                },
                "completion_limits": [
                    "このTraceはReference AppのCross-behavior観測であり全Surface固有Proofではない。",
                    "Platform fixtureをMethodChannelまたは実Device Runtime Evidenceへ拡張しない。",
                    "Authority atomic bindingがないためCompletion対象外である。",
                ],
            }
            relative = f"{output_relative.as_posix()}/{scenario}.trace.json"
            staged_path = staging / f"{scenario}.trace.json"
            staged_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            files.append({"id": trace["id"], "scenario": scenario, "run_id": run_id, "path": relative, "digest": digest(staged_path), "status": "passed"})
        index = {
            "schema_version": 1,
            "id": "flutter-reference-system-integrated-traces-v1",
            "atlas_id": "flutter-reference-atlas",
            "generated_at": GENERATED_AT,
            "run_id": run_id,
            "status": "bounded-integration-proof-not-surface-completion",
            "runtime_identity": runtime_identity,
            "summary": {"scenarios": 10, "passed": 10, "failed": 0, "dedicated_trace_artifacts": 10, "completion_eligible": 0},
            "files": files,
            "retention_contract": {
                "publish_on": "full-run-passed",
                "failed_run": "retain-prior-success",
                "swap": "staged-directory-rename-with-rollback",
                "partial_overwrite_allowed": False,
            },
            "completion_limits": [
                "10 Scenario passを全Flutter Surface固有Proofへ流用しない。",
                "Surface固有Proof MatrixとAuthority atomic bindingを別に検証する。",
            ],
        }
        (staging / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def validate_bundle(staging: Path) -> None:
        expected = {"index.json", *(f"{scenario}.trace.json" for scenario in SCENARIOS)}
        actual = {path.name for path in staging.iterdir() if path.is_file()}
        if actual != expected or any(path.is_dir() for path in staging.iterdir()):
            raise ValueError(f"統合Trace staging file setが不正です: {sorted(actual)}")
        index = json.loads((staging / "index.json").read_text(encoding="utf-8"))
        entries = index.get("files", [])
        if index.get("run_id") != run_id or len(entries) != len(SCENARIOS):
            raise ValueError("統合Trace staging indexのrun identityが不正です")
        if {entry.get("scenario") for entry in entries} != set(SCENARIOS):
            raise ValueError("統合Trace staging indexのScenario集合が不正です")
        for entry in entries:
            trace_path = staging / Path(entry["path"]).name
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            expected_path = f"{output_relative.as_posix()}/{entry.get('scenario')}.trace.json"
            if entry.get("path") != expected_path or entry.get("status") != "passed":
                raise ValueError(f"統合Trace staging index path/statusが不正です: {entry.get('scenario')}")
            if trace.get("run_id") != run_id or trace.get("scenario") != entry.get("scenario") or trace.get("status") != "passed" or entry.get("run_id") != run_id or digest(trace_path) != entry.get("digest"):
                raise ValueError(f"統合Trace stagingに新旧混在またはdigest driftがあります: {entry.get('scenario')}")

    atomic_publish_directory(output_dir, build_bundle, validate_bundle)
    print("Flutter Reference App統合Traceを生成しました: 10/10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
