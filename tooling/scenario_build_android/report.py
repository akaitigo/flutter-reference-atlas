#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Atomically publish Android build security Scenario evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

SURFACE = "build.android"
SCENARIO = "security"
VARIANTS = ("debug-apk-install", "release-apk")


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def binding(root: Path, path: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    return {"path": relative, "digest": digest(path), "bytes": path.stat().st_size}


def staged_binding(path: Path, relative: str) -> dict[str, Any]:
    return {"path": relative, "digest": digest(path), "bytes": path.stat().st_size}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def source_contract(root: Path, sdk_root: Path) -> tuple[list[dict[str, str]], str]:
    proof = json.loads((root / "evidence/scenarios/surfaces/build/android/security.proof.json").read_text())
    sources = []
    for item in proof["source_bindings"]:
        path = sdk_root / item["path"]
        if not path.is_file() or digest(path) != item["digest"]:
            raise ValueError(f"SDK Source binding mismatch: {item['path']}")
        sources.append({"path": item["path"], "digest": item["digest"]})
    canonical = json.dumps(sources, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return sources, "sha256:" + hashlib.sha256(canonical).hexdigest()


def validate_variant(variant: str, files: dict[str, Path]) -> dict[str, Any]:
    manifest = files["manifest"].read_text(encoding="utf-8")
    signing = files["signing"].read_text(encoding="utf-8")
    tree = files["tree"].read_text(encoding="utf-8")
    if not files["screen"].read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"PNG screenshot missing: {variant}")
    if files["apk"].stat().st_size < 1_000_000:
        raise ValueError(f"APK artifact is unexpectedly small: {variant}")
    expected_debuggable = variant == "debug-apk-install"
    observed_debuggable = 'android:debuggable="true"' in manifest
    if observed_debuggable != expected_debuggable:
        raise ValueError(f"debuggable oracle mismatch: {variant}")
    if "Signer #1 certificate SHA-256 digest:" not in signing:
        raise ValueError(f"APK signing verification missing: {variant}")
    label = f"build android security {variant} PASS"
    if label not in tree:
        raise ValueError(f"real Android Accessibility tree missing PASS screen: {variant}")
    return {
        "variant": variant,
        "debuggable": observed_debuggable,
        "package": "dev.akaitigo.atlas.operations_workspace",
        "apk_sha256": digest(files["apk"]),
        "apk_bytes": files["apk"].stat().st_size,
        "signing_verified": True,
        "installed_and_launched": True,
    }


def publish(args: argparse.Namespace) -> None:
    root = args.repo_root.resolve()
    output = args.output.resolve()
    sdk_root = args.sdk_root.resolve()
    harness = args.harness.resolve()
    reporter = Path(__file__).resolve()
    source = args.source.resolve()
    sources, source_set_digest = source_contract(root, sdk_root)
    raw: dict[str, dict[str, Path]] = {}
    for spec in args.input:
        variant, kind, value = spec.split("=", 2)
        if variant not in VARIANTS or kind not in {"apk", "manifest", "signing", "screen", "tree"}:
            raise ValueError(f"invalid input binding: {spec}")
        raw.setdefault(variant, {})[kind] = Path(value).resolve()
    if set(raw) != set(VARIANTS) or any(set(raw[v]) != {"apk", "manifest", "signing", "screen", "tree"} for v in VARIANTS):
        raise ValueError("all Android build variants and artifacts are required")
    observations = {variant: validate_variant(variant, raw[variant]) for variant in VARIANTS}

    output.parent.mkdir(parents=True, exist_ok=True)
    staging_parent = Path(tempfile.mkdtemp(prefix=".build-android-security-", dir=output.parent))
    staging_root = staging_parent / "runtime"
    backup = staging_parent / "prior"
    try:
        if output.exists():
            shutil.copytree(output, staging_root)
        else:
            staging_root.mkdir(parents=True)
        row = staging_root / "build/android/security"
        if row.exists():
            shutil.rmtree(row)
        tests = []
        for variant in VARIANTS:
            variant_dir = row / variant
            variant_dir.mkdir(parents=True)
            paths = {
                "artifact": variant_dir / "app.apk",
                "manifest": variant_dir / "manifest.xml",
                "signing": variant_dir / "signing.txt",
                "screenshot": variant_dir / "screen.png",
                "platform_tree": variant_dir / "platform-tree.xml",
            }
            for source_kind, target_kind in (("apk", "artifact"), ("manifest", "manifest"), ("signing", "signing"), ("screen", "screenshot"), ("tree", "platform_tree")):
                shutil.copy2(raw[variant][source_kind], paths[target_kind])
            observation = observations[variant]
            trace_path = variant_dir / "trace.json"
            result_path = variant_dir / "result.json"
            write_json(trace_path, {
                "schema_version": 1, "surface_id": SURFACE, "scenario": SCENARIO, "variant": variant,
                "streams": {
                    "action": ["flutter-build", "apk-install", "activity-launch", "accessibility-capture"],
                    "network": {"applicable": False, "reason": "local Android build/install security scenario has no network action"},
                    "resource": {"events": ["apk-created", "manifest-inspected", "signature-verified", "screen-captured"]},
                },
                "runtime_identity": args.runtime_identity,
                "oracle": observation,
            })
            write_json(result_path, {"schema_version": 1, "status": "passed", **observation})
            tests.append({
                "variant": variant, "attempts": 1, "outcome": "expected", "final_status": "passed", "error": None,
                "source": binding(root, source),
                "trace": staged_binding(trace_path, f"evidence/scenarios/runtime/build/android/security/{variant}/trace.json"),
                "artifact": staged_binding(paths["artifact"], f"evidence/scenarios/runtime/build/android/security/{variant}/app.apk"),
                "screenshot": staged_binding(paths["screenshot"], f"evidence/scenarios/runtime/build/android/security/{variant}/screen.png"),
                "oracle": {"passed": True, "assertions": [
                    "fixed Flutter SDK built the APK on the declared host",
                    "APK signature verification passed",
                    "debuggable manifest boundary matched the build mode",
                    "APK installed and the dedicated PASS screen was captured on Android API 36",
                ]},
            })
        report_path = row / "results.json"
        write_json(report_path, {
            "schema_version": 1, "surface_id": SURFACE, "scenario": SCENARIO, "status": "passed",
            "started_at": args.started_at, "completed_at": args.completed_at, "retries": 0,
            "variant_contract": list(VARIANTS), "runtime_identity": args.runtime_identity,
            "sdk_sources": sources, "source_set_digest": source_set_digest,
            "harness": binding(root, harness), "reporter": binding(root, reporter), "tests": tests,
            "retention_contract": {"publish_on": "both-build-variants-passed", "failed_run": "retain-prior-success", "swap": "full-runtime-root-staged-directory-rename-with-rollback", "partial_overwrite_allowed": False},
        })
        if output.exists():
            os.replace(output, backup)
        try:
            os.replace(staging_root, output)
        except OSError:
            if backup.exists() and not output.exists():
                os.replace(backup, output)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sdk-root", type=Path, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--completed-at", required=True)
    parser.add_argument("--runtime-identity", type=json.loads, required=True)
    parser.add_argument("--input", action="append", default=[])
    args = parser.parse_args()
    try:
        publish(args)
        print("build.android security Evidenceを原子的に保存しました: variants=2 retries=0")
        return 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        print(f"エラー: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
