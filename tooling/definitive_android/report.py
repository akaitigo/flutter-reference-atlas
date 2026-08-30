#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Android MethodChannel Definitive Runtime Artifactを生成する。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def sanitized_log(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = re.sub(r"/[^ ]*/flutter-reference-atlas", "<repo-root>", line)
        line = re.sub(r"/var/folders/[^ ]+", "<temporary-path>", line)
        lines.append(line)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--evidence-log", type=Path, required=True)
    parser.add_argument("--test-file", type=Path, required=True)
    parser.add_argument("--dart-plugin", type=Path, required=True)
    parser.add_argument("--android-plugin", type=Path, required=True)
    parser.add_argument("--pubspec-lock", type=Path, required=True)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--api-level", type=int, required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--finished-at", required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    args = parser.parse_args()

    log_text = args.log.read_text(encoding="utf-8", errors="replace")
    args.evidence_log.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_log.write_text(sanitized_log(log_text), encoding="utf-8")
    count_matches = re.findall(r"\+(\d+): All tests passed!", log_text)
    observed_count = int(count_matches[-1]) if count_matches else 0
    scenarios = ["normal", "boundary", "rejection", "failure", "recovery"]
    variants = ["standard", "json"]
    passed = args.exit_code == 0 and observed_count == 3
    result = {
        "schema_version": 2,
        "atlas_id": "flutter-reference-atlas",
        "surface_id": "platform.method-channel",
        "profile": "android-emulator",
        "runner": {
            "kind": "android-emulator",
            "device_id": args.device_id,
            "api_level": args.api_level,
            "physical_device": False,
        },
        "command": ".tools/flutter-3.47.1/flutter/bin/flutter test integration_test/workspace_integration_test.dart -d <android-emulator> --no-pub",
        "started_at": args.started_at,
        "finished_at": args.finished_at,
        "oracle": {
            "exit_code": args.exit_code,
            "expected_test_count": 3,
            "observed_test_count": observed_count,
            "variants": variants,
            "scenarios_per_variant": scenarios,
            "assertions": [
                "PluginはActivityへattachされAndroid API 36を返す",
                "StandardMethodCodecとJSONMethodCodecが同じObservable Contractを満たす",
                "64文字を受理し65文字をBOUNDARY_EXCEEDEDで拒否する",
                "policy denialをPERMISSION_DENIEDとして返す",
                "初回TRANSIENT_FAILURE後の再試行がrecoveredを返す",
            ],
        },
        "inputs": {
            "test_file_digest": digest(args.test_file),
            "dart_plugin_digest": digest(args.dart_plugin),
            "android_plugin_digest": digest(args.android_plugin),
            "pubspec_lock_digest": digest(args.pubspec_lock),
        },
        "artifacts": {
            "log_digest": digest(args.log),
            "log_size_bytes": args.log.stat().st_size,
            "integration_sanitized_log": f"evidence/artifacts/{args.evidence_log.name}",
            "integration_sanitized_log_digest": digest(args.evidence_log),
        },
        "cleanup": {
            "application_force_stopped": True,
            "avd_deleted": False,
            "application_data_deleted": False,
            "existing_evidence_deleted": False,
        },
        "verdict": "pass" if passed else "fail",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
