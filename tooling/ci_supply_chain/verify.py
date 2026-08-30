#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reject mutable third-party GitHub Action references."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
USES = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
ACTION_SHA = re.compile(r"^[0-9a-f]{40}$")
CHECKOUT_BLOCK = re.compile(
    r"(?ms)^      - uses: actions/checkout@[0-9a-f]{40}[^\n]*\n"
    r"(?P<body>.*?)(?=^      - (?:uses|name):|\Z)"
)
SDK_BINDINGS = (
    'echo "FORMAL_SDK=$FLUTTER_ROOT" >> "$GITHUB_ENV"',
    'echo "FLUTTER_ATLAS_SDK_ROOT=$FLUTTER_ROOT" >> "$GITHUB_ENV"',
)
LOCKED_RUNTIME_DEPENDENCY_COMMAND = (
    'run: \'"$FLUTTER_ROOT/bin/flutter" pub get --enforce-lockfile\''
)
RUNTIME_WORKSPACE = "working-directory: reference-systems/operations-workspace"


def violations(text: str, path: str) -> list[str]:
    errors: list[str] = []
    for value in USES.findall(text):
        if value.startswith("./") or value.startswith("docker://"):
            continue
        action, separator, revision = value.partition("@")
        if separator != "@" or not action or ACTION_SHA.fullmatch(revision) is None:
            errors.append(f"{path}: mutable or invalid action reference: {value}")
    return errors


def checkout_history_violations(text: str, path: str) -> list[str]:
    errors: list[str] = []
    subject_checkouts = [
        match.group(0) for match in CHECKOUT_BLOCK.finditer(text)
        if "repository:" not in match.group("body")
    ]
    if not subject_checkouts:
        return [f"{path}: subject repository checkoutがありません"]
    for block in subject_checkouts:
        if re.search(r"(?m)^\s+fetch-depth:\s*0\s*$", block) is None:
            errors.append(f"{path}: subject repository checkoutはfetch-depth: 0が必要です")
    return errors


def sdk_binding_violations(text: str, path: str) -> list[str]:
    """CIのFormal GateとRuntime Gateを同じAction導入SDKへ束縛する。"""
    errors: list[str] = []
    if 'test -n "$FLUTTER_ROOT"' not in text:
        errors.append(f"{path}: FLUTTER_ROOTの非空検証が必要です")
    for binding in SDK_BINDINGS:
        if binding not in text:
            variable = binding.split("=", 1)[0].split('"')[-1]
            errors.append(
                f"{path}: {variable}をFLUTTER_ROOTへ束縛する必要があります"
            )
    return errors


def runtime_dependency_violations(text: str, path: str) -> list[str]:
    """clean CI checkoutのRuntime依存を固定lockfileからのみ復元する。"""
    errors: list[str] = []
    if RUNTIME_WORKSPACE not in text:
        errors.append(f"{path}: Reference Appのworking-directoryが必要です")
    if LOCKED_RUNTIME_DEPENDENCY_COMMAND not in text:
        errors.append(
            f"{path}: 固定FLUTTER_ROOTによるpub get --enforce-lockfileが必要です"
        )
    return errors


def main() -> int:
    errors: list[str] = []
    workflows = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))
    if not workflows:
        errors.append(".github/workflows: workflowがありません")
    for workflow in workflows:
        relative = str(workflow.relative_to(ROOT))
        text = workflow.read_text(encoding="utf-8")
        errors.extend(violations(text, relative))
        errors.extend(checkout_history_violations(text, relative))
        errors.extend(sdk_binding_violations(text, relative))
        errors.extend(runtime_dependency_violations(text, relative))
    if errors:
        for error in errors:
            print(f"CI supply-chainエラー: {error}")
        return 1
    print(f"CI supply-chain検証済み: workflows={len(workflows)} immutable-action-refs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
