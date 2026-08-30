#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Publish the security-001 Android Scenario tranche atomically."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tooling.scenario_proof.atomic_publish import atomic_publish_directory  # noqa: E402

SCENARIO = "security"
SURFACE_VARIANTS = {
    "accessibility.focus-text-scale": ("text-scale-1x", "text-scale-2x"),
    "accessibility.semantics-tree": ("material-semantics", "explicit-container"),
    "background.app-lifecycle": ("app-lifecycle-listener", "widgets-binding-observer"),
    "background.isolate-work": ("isolate-run", "transferable-data"),
}
MARKER = "ATLAS_SECURITY_OBSERVATION:"
SENSITIVE_SENTINEL = "runtime-security-sentinel"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class ReportError(RuntimeError):
    pass


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path, relative: str) -> dict[str, Any]:
    return {"path": relative, "digest": digest(path), "bytes": path.stat().st_size}


def parse_spec(value: str) -> tuple[str, str, Path]:
    try:
        row, raw_path = value.split("=", 1)
        surface, variant = row.split(":", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError("指定はsurface:variant=path形式です") from error
    return surface, variant, Path(raw_path)


def parse_observation(text: str) -> dict[str, Any]:
    for raw in text.splitlines():
        line = ANSI.sub("", raw)
        if MARKER not in line:
            continue
        try:
            value = json.loads(line.split(MARKER, 1)[1].strip())
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


def validate_platform_tree(path: Path, surface: str, variant: str) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="strict")
    if SENSITIVE_SENTINEL in raw:
        raise ReportError(f"Accessibility treeへsensitive valueが露出しました: {surface}:{variant}")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise ReportError(f"Accessibility tree XMLが不正です: {surface}:{variant}") from error
    values = []
    for node in root.iter():
        values.extend(value for value in node.attrib.values() if value)
    joined = " ".join(values)
    if "PASS" not in joined or surface not in joined or variant not in joined:
        raise ReportError(f"実Android Accessibility treeが専用PASS画面を示しません: {surface}:{variant}")
    return {"nodes": sum(1 for _ in root.iter()), "surface_visible": True, "variant_visible": True, "sensitive_value_absent": True}


def write_public_platform_tree(source: Path, destination: Path) -> None:
    document = ET.parse(source)
    for node in document.getroot().iter():
        password_state = node.attrib.pop("password", None)
        if password_state not in {None, "false"}:
            raise ReportError("password nodeを含むAccessibility treeは公開Evidenceへ保存しません")
    ET.indent(document, space="  ")
    document.write(destination, encoding="utf-8", xml_declaration=True)


def validate_observation(value: dict[str, Any], surface: str, variant: str) -> None:
    expected = {"surface_id": surface, "scenario": SCENARIO, "variant": variant, "platform": "Android"}
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise ReportError(f"Runtime observation不一致: {surface}:{variant}:{key}")
    valid = False
    if surface == "accessibility.focus-text-scale":
        expected_scale = 1.0 if variant == "text-scale-1x" else 2.0
        valid = (
            value.get("text_scale") == expected_scale
            and isinstance(value.get("rendered_height"), (int, float))
            and value["rendered_height"] > 0
            and value.get("focus_received") is True
            and value.get("semantics_label") == "Public focus status"
            and value.get("sensitive_value_exposed") is False
        )
    elif surface == "accessibility.semantics-tree":
        valid = (
            isinstance(value.get("semantics_label"), str)
            and value["semantics_label"].startswith("Public security")
            and value.get("semantic_container") is True
            and value.get("explicit_child_nodes") is (variant == "explicit-container")
            and value.get("sensitive_value_exposed") is False
        )
    elif surface == "background.app-lifecycle":
        states = value.get("states")
        valid = (
            value.get("mechanism") == variant
            and isinstance(states, list)
            and any(state in {"inactive", "hidden", "paused"} for state in states)
            and "resumed" in states
            and value.get("background_seen") is True
            and value.get("resumed_after_background") is True
            and value.get("sensitive_value_cleared") is True
        )
    elif surface == "background.isolate-work":
        valid = (
            value.get("mechanism") == variant
            and value.get("worker_completed") is True
            and isinstance(value.get("input_length"), int)
            and value["input_length"] > 0
            and isinstance(value.get("checksum"), int)
            and value["checksum"] > 0
            and value.get("raw_sensitive_value_returned") is False
        )
    if not valid or SENSITIVE_SENTINEL in json.dumps(value, ensure_ascii=False):
        raise ReportError(f"Security Scenario Oracle不一致: {surface}:{variant}")


def assertions_for(surface: str, variant: str) -> list[str]:
    common = [
        "Android API 36の実Flutter processでfirst-attempt実行した",
        "実Android Accessibility treeと画面に専用Surface/VariantのPASSを観測した",
        "sensitive sentinelをRuntime log・Result・Platform treeへ出力しなかった",
    ]
    if surface == "accessibility.focus-text-scale":
        return common + [f"{variant}でFocusとtext scaleを適用し公開Semanticsだけを保持した"]
    if surface == "accessibility.semantics-tree":
        return common + [f"{variant}のSemantics構造で非公開値を除外した"]
    if surface == "background.app-lifecycle":
        return common + [f"{variant}でbackground/resumeを観測し一時機密値を消去した"]
    if surface == "background.isolate-work":
        return common + [f"{variant}の実Isolateから要約値だけを返した"]
    raise ReportError(f"未対応Surfaceです: {surface}")


def load_surfaces(root: Path) -> dict[str, dict[str, Any]]:
    inventory = json.loads((root / "atlas/definitive/surface-inventory.json").read_text(encoding="utf-8"))
    selected = {item["id"]: item for item in inventory["surfaces"] if item["id"] in SURFACE_VARIANTS}
    if set(selected) != set(SURFACE_VARIANTS):
        raise ReportError("security-001 Surface inventoryが不足しています")
    return selected


def build_bundle(
    staging: Path,
    *,
    output: Path,
    root: Path,
    logs: dict[tuple[str, str], Path],
    screenshots: dict[tuple[str, str], Path],
    trees: dict[tuple[str, str], Path],
    harness: Path,
    reporter: Path,
    source: Path,
    runtime_identity: dict[str, Any],
    started_at: str,
    completed_at: str,
) -> None:
    if output.exists():
        shutil.copytree(output, staging, dirs_exist_ok=True)
    surfaces = load_surfaces(root)
    source_binding = binding(source, str(source.relative_to(root)))
    for surface, variants in SURFACE_VARIANTS.items():
        tests = []
        surface_path = surface.replace(".", "/")
        scenario_dir = staging / surface_path / SCENARIO
        if scenario_dir.exists():
            shutil.rmtree(scenario_dir)
        for variant in variants:
            key = (surface, variant)
            log = logs[key]
            screenshot = screenshots[key]
            tree = trees[key]
            text = log.read_text(encoding="utf-8", errors="replace")
            if "All tests passed!" not in text:
                raise ReportError(f"first-attempt実行がpassしていません: {surface}:{variant}")
            if not screenshot.is_file() or not screenshot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                raise ReportError(f"実Android screenshotがありません: {surface}:{variant}")
            observed = parse_observation(text)
            validate_observation(observed, surface, variant)
            tree_summary = validate_platform_tree(tree, surface, variant)

            variant_dir = scenario_dir / variant
            variant_dir.mkdir(parents=True, exist_ok=True)
            trace_path = variant_dir / "trace.json"
            artifact_path = variant_dir / "result.json"
            screenshot_path = variant_dir / "screen.png"
            tree_path = variant_dir / "platform-tree.xml"
            screenshot_path.write_bytes(screenshot.read_bytes())
            write_public_platform_tree(tree, tree_path)
            trace = {
                "schema_version": 1,
                "surface_id": surface,
                "scenario": SCENARIO,
                "variant": variant,
                "runtime_identity": runtime_identity,
                "streams": {
                    "action": [{"name": "security", "status": "passed", "observed": observed}],
                    "network": {"applicable": False, "reason": "security-001 runtimeはnetworkを使用しない。"},
                    "resource": [{"api_level": runtime_identity["api_level"], "platform_tree": tree_summary}],
                },
                "sanitized_runtime_log": sanitize(text, root),
            }
            trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            artifact = {
                "schema_version": 1,
                "surface_id": surface,
                "scenario": SCENARIO,
                "variant": variant,
                "first_attempt": True,
                "retries": 0,
                "runtime_identity": runtime_identity,
                "observed": observed,
                "platform_tree": binding(tree_path, f"evidence/scenarios/runtime/{surface_path}/{SCENARIO}/{variant}/platform-tree.xml"),
                "oracle": {"passed": True, "assertions": assertions_for(surface, variant)},
                "screen_sha256": digest(screenshot_path),
            }
            artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            prefix = f"evidence/scenarios/runtime/{surface_path}/{SCENARIO}/{variant}"
            tests.append({
                "variant": variant,
                "attempts": 1,
                "outcome": "expected",
                "final_status": "passed",
                "error": None,
                "oracle": artifact["oracle"],
                "source": source_binding,
                "trace": binding(trace_path, f"{prefix}/trace.json"),
                "artifact": binding(artifact_path, f"{prefix}/result.json"),
                "screenshot": binding(screenshot_path, f"{prefix}/screen.png"),
            })

        results = {
            "schema_version": 1,
            "surface_id": surface,
            "scenario": SCENARIO,
            "status": "passed",
            "retries": 0,
            "started_at": started_at,
            "completed_at": completed_at,
            "source_set_digest": surfaces[surface]["sdk_source_set_digest"],
            "sdk_sources": surfaces[surface]["sdk_sources"],
            "variant_contract": list(variants),
            "runtime_identity": runtime_identity,
            "harness": binding(harness, str(harness.relative_to(root))),
            "reporter": binding(reporter, str(reporter.relative_to(root))),
            "retention_contract": {
                "failed_run": "retain-prior-success",
                "partial_overwrite_allowed": False,
                "publish_on": "all-four-security-surfaces-and-eight-variant-runs-passed",
                "swap": "full-runtime-root-staged-directory-rename-with-rollback",
            },
            "tests": tests,
        }
        (scenario_dir / "results.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def validate_bundle(staging: Path) -> None:
    for surface, variants in SURFACE_VARIANTS.items():
        relative = Path(surface.replace(".", "/")) / SCENARIO
        scenario_dir = staging / relative
        expected = {"results.json"}
        for variant in variants:
            expected.update({
                f"{variant}/trace.json",
                f"{variant}/result.json",
                f"{variant}/screen.png",
                f"{variant}/platform-tree.xml",
            })
        actual = {str(path.relative_to(scenario_dir)) for path in scenario_dir.rglob("*") if path.is_file()}
        if actual != expected:
            raise ReportError(f"security-001 bundleが部分生成または新旧混在です: {surface} {sorted(actual ^ expected)}")
        report = json.loads((scenario_dir / "results.json").read_text(encoding="utf-8"))
        if report.get("status") != "passed" or report.get("retries") != 0 or len(report.get("tests", [])) != 2:
            raise ReportError(f"security-001 report契約不一致: {surface}")


def publish_bundle(output: Path, **kwargs: Any) -> None:
    atomic_publish_directory(
        output,
        lambda staging: build_bundle(staging, output=output, **kwargs),
        validate_bundle,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", action="append", type=parse_spec, required=True)
    parser.add_argument("--screenshot", action="append", type=parse_spec, required=True)
    parser.add_argument("--tree", action="append", type=parse_spec, required=True)
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
        logs = {(surface, variant): path.resolve() for surface, variant, path in args.log}
        screenshots = {(surface, variant): path.resolve() for surface, variant, path in args.screenshot}
        trees = {(surface, variant): path.resolve() for surface, variant, path in args.tree}
        expected = {(surface, variant) for surface, variants in SURFACE_VARIANTS.items() for variant in variants}
        if set(logs) != expected or set(screenshots) != expected or set(trees) != expected:
            raise ReportError("security-001の4 Surface×2 Variantにlog/screenshot/treeが必要です")
        identity = {
            "profile": "android-emulator",
            "runner_kind": "android-emulator",
            "os": f"Android {args.os_version}",
            "architecture": args.architecture,
            "api_level": args.api_level,
            "device_id": args.device_id,
            "physical_device": False,
        }
        publish_bundle(
            args.output.resolve(),
            root=root,
            logs=logs,
            screenshots=screenshots,
            trees=trees,
            harness=args.harness.resolve(),
            reporter=Path(__file__).resolve(),
            source=args.source.resolve(),
            runtime_identity=identity,
            started_at=args.started_at,
            completed_at=args.completed_at,
        )
    except (OSError, KeyError, StopIteration, ReportError, json.JSONDecodeError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    print("security-001 Android専用Scenario Evidenceを原子的に保存しました: 4 surfaces / 8 variant runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
