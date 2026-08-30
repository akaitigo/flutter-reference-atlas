#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Chrome JavaScript/Wasm integrated Reference App report generator."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


EXPECTED_TEST_COUNT = 5


def digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def observed_test_count(text: str) -> int:
    matches = re.findall(r"\+(\d+): All tests passed!", text)
    return int(matches[-1]) if matches else 0


def sanitized_log(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if "Generated wasm module" in line:
            lines.append("Generated wasm module <temporary-path> and JS init file <temporary-path>.")
            continue
        line = re.sub(r"/[^ ]*/flutter-reference-atlas", "<repo-root>", line)
        lines.append(line)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--js-log", type=Path, required=True)
    parser.add_argument("--wasm-log", type=Path, required=True)
    parser.add_argument("--js-evidence-log", type=Path, required=True)
    parser.add_argument("--wasm-evidence-log", type=Path, required=True)
    parser.add_argument("--test-file", type=Path, required=True)
    parser.add_argument("--pubspec-lock", type=Path, required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--finished-at", required=True)
    parser.add_argument("--js-exit-code", type=int, required=True)
    parser.add_argument("--wasm-exit-code", type=int, required=True)
    args = parser.parse_args()

    js_text = args.js_log.read_text(encoding="utf-8", errors="replace")
    wasm_text = args.wasm_log.read_text(encoding="utf-8", errors="replace")
    js_count = observed_test_count(js_text)
    wasm_count = observed_test_count(wasm_text)
    args.js_evidence_log.parent.mkdir(parents=True, exist_ok=True)
    args.js_evidence_log.write_text(sanitized_log(js_text), encoding="utf-8")
    args.wasm_evidence_log.write_text(sanitized_log(wasm_text), encoding="utf-8")
    passed = (
        args.js_exit_code == 0
        and args.wasm_exit_code == 0
        and js_count == EXPECTED_TEST_COUNT
        and wasm_count == EXPECTED_TEST_COUNT
    )
    report = {
        "schema_version": 2,
        "atlas_id": "flutter-reference-atlas",
        "profile": "web-chrome",
        "runner": {"kind": "browser-runtime", "browser": "Chrome", "physical_device": False},
        "commands": [
            "flutter test --platform chrome test/workspace_app_test.dart --no-pub",
            "flutter test --platform chrome --wasm test/workspace_app_test.dart --no-pub",
        ],
        "started_at": args.started_at,
        "finished_at": args.finished_at,
        "oracle": {
            "expected_test_count_per_variant": EXPECTED_TEST_COUNT,
            "variants": {
                "javascript": {"exit_code": args.js_exit_code, "observed_test_count": js_count},
                "wasm": {"exit_code": args.wasm_exit_code, "observed_test_count": wasm_count},
            },
            "scenario_assertions": {
                "normal": "Adaptive UI、作成、NavigationをBrowserで実行する",
                "boundary": "1200x800の広幅境界で一覧と詳細を同時表示する",
                "rejection": "bidi制御文字を統合UIで拒否する",
                "failure": "Repositoryの初回保存失敗を安全な表示へ変換する",
                "recovery": "同じUIからRetryし状態遷移を完了する",
            },
        },
        "inputs": {
            "test_file_digest": digest(args.test_file),
            "pubspec_lock_digest": digest(args.pubspec_lock),
        },
        "artifacts": {
            "javascript_log_digest": digest(args.js_log),
            "javascript_log_size_bytes": args.js_log.stat().st_size,
            "javascript_sanitized_log": f"evidence/artifacts/{args.js_evidence_log.name}",
            "javascript_sanitized_log_digest": digest(args.js_evidence_log),
            "wasm_log_digest": digest(args.wasm_log),
            "wasm_log_size_bytes": args.wasm_log.stat().st_size,
            "wasm_sanitized_log": f"evidence/artifacts/{args.wasm_evidence_log.name}",
            "wasm_sanitized_log_digest": digest(args.wasm_evidence_log),
        },
        "cleanup": {
            "browser_process_managed_by_flutter_test": True,
            "user_data_deleted": False,
            "existing_evidence_deleted": False,
        },
        "verdict": "pass" if passed else "fail",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
