#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Write a sanitized row-specific failure record into raw staging."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


PHASES = {"marker-timeout", "post-marker-timeout", "test-exit"}


def sanitize_tail(path: Path, repo_root: Path, lines: int = 40) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    value = text.replace(str(repo_root), "<repo-root>")
    value = re.sub("/" + "Users/" + r"[^/\s]+", "<user-home>", value)
    value = re.sub(r"/var/folders/[^\s]+", "<temporary-path>", value)
    return value.splitlines()[-lines:]


def build_record(args: argparse.Namespace) -> dict[str, object]:
    if args.phase not in PHASES:
        raise ValueError(f"unknown failure phase: {args.phase}")
    return {
        "schema_version": 1,
        "run_id": args.run_id,
        "status": "failed",
        "phase": args.phase,
        "surface_id": args.surface,
        "variant": args.variant,
        "first_attempt": True,
        "retries": 0,
        "exit_code": args.exit_code,
        "terminated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "runtime_identity": {
            "profile": "android-emulator",
            "runner_kind": "android-emulator",
            "device_id": args.device_id,
            "os": f"Android {args.os_version}",
            "api_level": args.api_level,
            "architecture": args.architecture,
            "physical_device": False,
        },
        "input_bindings": {
            "source_sha256": args.source_digest,
            "harness_sha256": args.harness_digest,
        },
        "sanitized_log_tail": sanitize_tail(args.log, args.repo_root),
        "published": False,
        "prior_success_evidence_retained": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--surface", required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--os-version", required=True)
    parser.add_argument("--api-level", type=int, required=True)
    parser.add_argument("--architecture", required=True)
    parser.add_argument("--source-digest", required=True)
    parser.add_argument("--harness-digest", required=True)
    args = parser.parse_args()
    record = build_record(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
