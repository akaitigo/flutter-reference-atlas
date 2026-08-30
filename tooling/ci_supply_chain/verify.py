#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reject mutable third-party GitHub Action references."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
USES = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
ACTION_SHA = re.compile(r"^[0-9a-f]{40}$")


def violations(text: str, path: str) -> list[str]:
    errors: list[str] = []
    for value in USES.findall(text):
        if value.startswith("./") or value.startswith("docker://"):
            continue
        action, separator, revision = value.partition("@")
        if separator != "@" or not action or ACTION_SHA.fullmatch(revision) is None:
            errors.append(f"{path}: mutable or invalid action reference: {value}")
    return errors


def main() -> int:
    errors: list[str] = []
    workflows = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))
    if not workflows:
        errors.append(".github/workflows: workflowがありません")
    for workflow in workflows:
        errors.extend(violations(workflow.read_text(encoding="utf-8"), str(workflow.relative_to(ROOT))))
    if errors:
        for error in errors:
            print(f"CI supply-chainエラー: {error}")
        return 1
    print(f"CI supply-chain検証済み: workflows={len(workflows)} immutable-action-refs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
