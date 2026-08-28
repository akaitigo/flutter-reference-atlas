#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Simulator ProfileのInventoryとIntegration Test Reportを生成する。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def normalized_sdk_root(sdk_root: str, repo_root: str) -> str:
    sdk_path = Path(sdk_root).resolve()
    root_path = Path(repo_root).resolve()
    try:
        return "./" + sdk_path.relative_to(root_path).as_posix()
    except ValueError:
        return "external-sdk-root"


def inventory(args: argparse.Namespace) -> int:
    version_path = Path(args.flutter_version_file)
    devices_path = Path(args.flutter_devices_file)
    doctor_path = Path(args.doctor_log)
    version = json.loads(version_path.read_text(encoding="utf-8"))
    devices = json.loads(devices_path.read_text(encoding="utf-8"))

    observed = {
        "flutter": version.get("frameworkVersion"),
        "dart": version.get("dartSdkVersion"),
        "devtools": version.get("devToolsVersion"),
    }
    expected = {
        "flutter": args.expected_flutter,
        "dart": args.expected_dart,
        "devtools": args.expected_devtools,
    }
    if observed != expected:
        raise SystemExit(f"固定Toolchainと不一致です: expected={expected}, observed={observed}")
    flutter_device = next((item for item in devices if item.get("id") == args.device_id), None)
    if flutter_device is None:
        raise SystemExit(f"FlutterがDeviceを認識していません: {args.device_id}")

    result: dict[str, object] = {
        "schema_version": 1,
        "profile": "simulator",
        "runner": {
            "kind": args.runner_kind,
            "device_id": args.device_id,
            "runtime_name": args.runtime_name,
            "model": args.model,
            "os_version": args.os_version,
            "api_level": int(args.api_level) if args.api_level else None,
            "architecture": args.architecture,
            "physical_device": False,
            "flutter_device": flutter_device,
        },
        "toolchain": {
            "sdk_root": normalized_sdk_root(args.sdk_root, args.repo_root),
            "flutter_version": observed["flutter"],
            "dart_version": observed["dart"],
            "devtools_version": observed["devtools"],
            "framework_revision": version.get("frameworkRevision"),
            "engine_revision": version.get("engineRevision"),
        },
        "diagnostics": {
            "flutter_version_digest": sha256(version_path),
            "flutter_devices_digest": sha256(devices_path),
            "flutter_doctor_digest": sha256(doctor_path),
        },
    }
    write_json(Path(args.output), result)
    return 0


def report(args: argparse.Namespace) -> int:
    inventory_path = Path(args.inventory)
    log_path = Path(args.log)
    test_path = Path(args.test_file)
    lock_path = Path(args.pubspec_lock)
    exit_code = int(args.exit_code)
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    all_tests_passed = "All tests passed!" in log_text
    verdict = "pass" if exit_code == 0 and all_tests_passed else "fail"
    result: dict[str, object] = {
        "schema_version": 1,
        "profile": "simulator",
        "lab_id": "lab.simulator-integration",
        "test_id": "test.simulator-integration",
        "command": args.command,
        "started_at": args.started_at,
        "finished_at": args.finished_at,
        "inventory": json.loads(inventory_path.read_text(encoding="utf-8")),
        "oracle": {
            "exit_code": exit_code,
            "all_tests_passed": all_tests_passed,
            "expected_test_count": 1,
            "assemble_install_run_exercised": exit_code == 0,
        },
        "inputs": {
            "runtime_inventory_digest": sha256(inventory_path),
            "test_file_digest": sha256(test_path),
            "pubspec_lock_digest": sha256(lock_path),
        },
        "log": {
            "digest": sha256(log_path),
            "size_bytes": log_path.stat().st_size,
        },
        "cleanup_contract": {
            "application_only": True,
            "avd_preserved": True,
            "application_data_preserved": True,
            "evidence_preserved": True,
        },
        "verdict": verdict,
    }
    write_json(Path(args.output), result)
    return 0 if verdict == "pass" else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command_name", required=True)

    inventory_parser = commands.add_parser("inventory")
    inventory_parser.add_argument("--output", required=True)
    inventory_parser.add_argument("--flutter-version-file", required=True)
    inventory_parser.add_argument("--flutter-devices-file", required=True)
    inventory_parser.add_argument("--doctor-log", required=True)
    inventory_parser.add_argument("--sdk-root", required=True)
    inventory_parser.add_argument("--repo-root", required=True)
    inventory_parser.add_argument("--runner-kind", required=True, choices=("android-emulator", "ios-simulator"))
    inventory_parser.add_argument("--device-id", required=True)
    inventory_parser.add_argument("--runtime-name", required=True)
    inventory_parser.add_argument("--model", required=True)
    inventory_parser.add_argument("--os-version", required=True)
    inventory_parser.add_argument("--api-level", default="")
    inventory_parser.add_argument("--architecture", required=True)
    inventory_parser.add_argument("--expected-flutter", required=True)
    inventory_parser.add_argument("--expected-dart", required=True)
    inventory_parser.add_argument("--expected-devtools", required=True)
    inventory_parser.set_defaults(handler=inventory)

    report_parser = commands.add_parser("report")
    report_parser.add_argument("--output", required=True)
    report_parser.add_argument("--inventory", required=True)
    report_parser.add_argument("--log", required=True)
    report_parser.add_argument("--test-file", required=True)
    report_parser.add_argument("--pubspec-lock", required=True)
    report_parser.add_argument("--command", required=True)
    report_parser.add_argument("--started-at", required=True)
    report_parser.add_argument("--finished-at", required=True)
    report_parser.add_argument("--exit-code", required=True, type=int)
    report_parser.set_defaults(handler=report)
    return root


def main() -> int:
    args = parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
