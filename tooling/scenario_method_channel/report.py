#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Publish dedicated Android MethodChannel Scenario Evidence atomically."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tooling.scenario_proof.atomic_publish import atomic_publish_directory  # noqa: E402

SURFACE_ID = "platform.method-channel"
SCENARIOS = ("refusal", "failure", "recovery", "boundary")
VARIANTS = ("json", "standard")
MARKER = "ATLAS_SCENARIO_OBSERVATION:"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class ReportError(RuntimeError):
    pass


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path, relative: str) -> dict[str, Any]:
    return {"path": relative, "digest": digest(path), "bytes": path.stat().st_size}


def parse_log_spec(value: str) -> tuple[str, str, Path]:
    try:
        row, raw_path = value.split("=", 1)
        scenario, variant = row.split(":", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError("--logはscenario:variant=path形式です") from error
    return scenario, variant, Path(raw_path)


def parse_observation(text: str) -> dict[str, Any]:
    for raw in text.splitlines():
        line = ANSI.sub("", raw)
        if MARKER not in line:
            continue
        payload = line.split(MARKER, 1)[1].strip()
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ReportError("Runtime observation markerが不正なJSONです") from error
        if not isinstance(value, dict):
            raise ReportError("Runtime observation markerはobjectである必要があります")
        return value
    raise ReportError("Runtime observation markerがありません")


def sanitize(text: str, repo_root: Path) -> str:
    value = ANSI.sub("", text).replace(str(repo_root), "<repo-root>")
    mac_home_pattern = "/" + "Users/" + r"[^/\s]+"
    value = re.sub(mac_home_pattern, "<user-home>", value)
    value = re.sub(r"/var/folders/[^ ]+", "<temporary-path>", value)
    return value.rstrip() + "\n"


def assertions_for(scenario: str, observed: dict[str, Any]) -> list[str]:
    common = [
        "Android API 36上でActivity attachedを観測した",
        f"{observed['codec']} codecを実Platform側で確認した",
    ]
    if scenario == "boundary":
        return common + ["64文字を受理した", "65文字をBOUNDARY_EXCEEDEDで拒否した"]
    if scenario == "refusal":
        return common + ["policy拒否をPERMISSION_DENIEDとして観測した"]
    if scenario == "failure":
        return common + ["初回操作をTRANSIENT_FAILUREとして観測した"]
    if scenario == "recovery":
        return common + ["TRANSIENT_FAILURE後の同一codec操作がrecoveredへ回復した"]
    raise ReportError(f"未対応Scenarioです: {scenario}")


def validate_observation(value: dict[str, Any], scenario: str, variant: str, api_level: int) -> None:
    expected = {
        "surface_id": SURFACE_ID,
        "scenario": scenario,
        "variant": variant,
        "platform": "Android",
        "api_level": api_level,
        "activity_attached": True,
        "codec": variant,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise ReportError(f"Runtime observation不一致: {scenario}:{variant}:{key}")
    scenario_values = {
        "boundary": value.get("accepted_length") == 64 and value.get("rejected_length") == 65 and value.get("error_code") == "BOUNDARY_EXCEEDED",
        "refusal": value.get("error_code") == "PERMISSION_DENIED",
        "failure": value.get("error_code") == "TRANSIENT_FAILURE",
        "recovery": value.get("first_error_code") == "TRANSIENT_FAILURE" and value.get("recovered_value") == "recovered",
    }
    if not scenario_values[scenario]:
        raise ReportError(f"Scenario Oracle不一致: {scenario}:{variant}")


def load_surface(root: Path) -> dict[str, Any]:
    inventory = json.loads((root / "atlas/definitive/surface-inventory.json").read_text(encoding="utf-8"))
    return next(item for item in inventory["surfaces"] if item["id"] == SURFACE_ID)


def build_bundle(
    staging: Path,
    *,
    root: Path,
    logs: dict[tuple[str, str], Path],
    screenshots: dict[tuple[str, str], Path],
    harness: Path,
    reporter: Path,
    source: Path,
    runtime_identity: dict[str, Any],
    started_at: str,
    completed_at: str,
) -> None:
    surface = load_surface(root)
    for scenario in SCENARIOS:
        tests = []
        for variant in VARIANTS:
            key = (scenario, variant)
            log = logs[key]
            screenshot = screenshots[key]
            text = log.read_text(encoding="utf-8", errors="replace")
            if "All tests passed!" not in text:
                raise ReportError(f"first-attempt実行がpassしていません: {scenario}:{variant}")
            if not screenshot.is_file() or not screenshot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                raise ReportError(f"実Android screenshotがありません: {scenario}:{variant}")
            observed = parse_observation(text)
            validate_observation(observed, scenario, variant, int(runtime_identity["api_level"]))

            variant_dir = staging / scenario / variant
            variant_dir.mkdir(parents=True, exist_ok=True)
            trace_path = variant_dir / "trace.json"
            artifact_path = variant_dir / "result.json"
            screenshot_path = variant_dir / "screen.png"
            screenshot_path.write_bytes(screenshot.read_bytes())
            trace = {
                "schema_version": 1,
                "surface_id": SURFACE_ID,
                "scenario": scenario,
                "variant": variant,
                "runtime_identity": runtime_identity,
                "streams": {
                    "action": [{"name": scenario, "status": "passed", "observed": observed}],
                    "network": {"applicable": False, "reason": "MethodChannel fixtureはnetworkを使用しない。"},
                    "resource": [{"activity_attached": observed["activity_attached"], "api_level": observed["api_level"]}],
                },
                "sanitized_runtime_log": sanitize(text, root),
            }
            trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            artifact = {
                "schema_version": 1,
                "surface_id": SURFACE_ID,
                "scenario": scenario,
                "variant": variant,
                "first_attempt": True,
                "retries": 0,
                "runtime_identity": runtime_identity,
                "observed": observed,
                "oracle": {"passed": True, "assertions": assertions_for(scenario, observed)},
                "screen_sha256": digest(screenshot_path),
            }
            artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            prefix = f"evidence/scenarios/runtime/platform/method-channel/{scenario}/{variant}"
            tests.append({
                "variant": variant,
                "attempts": 1,
                "outcome": "expected",
                "final_status": "passed",
                "error": None,
                "oracle": artifact["oracle"],
                "source": binding(source, str(source.relative_to(root))),
                "trace": binding(trace_path, f"{prefix}/trace.json"),
                "artifact": binding(artifact_path, f"{prefix}/result.json"),
                "screenshot": binding(screenshot_path, f"{prefix}/screen.png"),
            })

        results_path = staging / scenario / "results.json"
        results = {
            "schema_version": 1,
            "surface_id": SURFACE_ID,
            "scenario": scenario,
            "status": "passed",
            "retries": 0,
            "started_at": started_at,
            "completed_at": completed_at,
            "source_set_digest": surface["sdk_source_set_digest"],
            "sdk_sources": surface["sdk_sources"],
            "variant_contract": list(VARIANTS),
            "runtime_identity": runtime_identity,
            "harness": binding(harness, str(harness.relative_to(root))),
            "reporter": binding(reporter, str(reporter.relative_to(root))),
            "retention_contract": {
                "failed_run": "retain-prior-success",
                "partial_overwrite_allowed": False,
                "publish_on": "all-four-scenarios-and-eight-variant-runs-passed",
                "swap": "staged-directory-rename-with-rollback",
            },
            "tests": tests,
        }
        results_path.write_text(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_bundle(staging: Path) -> None:
    expected = set()
    for scenario in SCENARIOS:
        expected.add(f"{scenario}/results.json")
        for variant in VARIANTS:
            expected.update({
                f"{scenario}/{variant}/trace.json",
                f"{scenario}/{variant}/result.json",
                f"{scenario}/{variant}/screen.png",
            })
    actual = {str(path.relative_to(staging)) for path in staging.rglob("*") if path.is_file()}
    if actual != expected:
        raise ReportError(f"Scenario bundleが部分生成または新旧混在です: {sorted(actual ^ expected)}")
    for scenario in SCENARIOS:
        report = json.loads((staging / scenario / "results.json").read_text(encoding="utf-8"))
        if report.get("status") != "passed" or report.get("retries") != 0 or len(report.get("tests", [])) != 2:
            raise ReportError(f"Scenario report契約不一致: {scenario}")


def publish_bundle(output: Path, **kwargs: Any) -> None:
    atomic_publish_directory(
        output,
        lambda staging: build_bundle(staging, **kwargs),
        validate_bundle,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", action="append", type=parse_log_spec, required=True)
    parser.add_argument("--screenshot", action="append", type=parse_log_spec, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--os-version", required=True)
    parser.add_argument("--api-level", type=int, required=True)
    parser.add_argument("--architecture", required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--completed-at", required=True)
    args = parser.parse_args()
    try:
        root = args.repo_root.resolve()
        logs = {(scenario, variant): path.resolve() for scenario, variant, path in args.log}
        screenshots = {(scenario, variant): path.resolve() for scenario, variant, path in args.screenshot}
        expected = {(scenario, variant) for scenario in SCENARIOS for variant in VARIANTS}
        if set(logs) != expected or set(screenshots) != expected:
            raise ReportError("4 Scenario×2 Variantのlog/screenshotが必要です")
        runtime_identity = {
            "profile": "android-emulator",
            "runner_kind": "android-emulator",
            "os": f"Android {args.os_version}",
            "architecture": args.architecture,
            "api_level": args.api_level,
            "device_id": args.device_id,
            "physical_device": False,
        }
        publish_bundle(
            args.output.resolve(), root=root, logs=logs, screenshots=screenshots,
            harness=args.harness.resolve(), reporter=Path(__file__).resolve(), source=args.source.resolve(),
            runtime_identity=runtime_identity, started_at=args.started_at,
            completed_at=args.completed_at,
        )
    except (OSError, KeyError, StopIteration, ReportError, json.JSONDecodeError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    print("Android MethodChannel専用Scenario Evidenceを原子的に保存しました: 4 scenarios / 8 variant runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
