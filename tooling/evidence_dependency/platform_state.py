#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate and summarize Android ``dumpsys activity top`` evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
COMPONENT = "dev.akaitigo.atlas.operations_workspace/.MainActivity"
EXPECTED_ROWS = {
    "background.app-lifecycle": ("app-lifecycle-listener", "widgets-binding-observer"),
    "background.isolate-work": ("isolate-run", "transferable-data"),
    "input.focus-traversal": ("ordered-traversal", "skip-sensitive"),
    "input.keyboard-shortcuts": ("callback-shortcuts", "shortcuts-actions"),
    "input.pointer-gesture-arena": ("horizontal-drag", "tap-recognizer"),
    "input.text-ime": ("bidi-rejection", "obscured-entry"),
}
ACTIVITY = re.compile(r"^\s*ACTIVITY\s+(\S+)(?:\s|$)")
STATE = re.compile(r"\bmResumed=(true|false)\s+mStopped=(true|false)\s+mFinished=(true|false)\b")


class PlatformStateError(RuntimeError):
    pass


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def state_contract(surface: str) -> str:
    if surface == "background.app-lifecycle":
        return "resumed-after-background"
    if surface == "background.isolate-work":
        return "foreground-after-isolate-result"
    if surface.startswith("input."):
        return "foreground-input-observation"
    raise PlatformStateError(f"未対応のPlatform state Surfaceです: {surface}")


def validate_text(raw: str, surface: str, variant: str) -> dict[str, Any]:
    marker = f"ATLAS_PLATFORM_STATE surface={surface} variant={variant}"
    if raw.splitlines()[:1] != [marker]:
        raise PlatformStateError(f"Surface/Variant markerが先頭にありません: {surface}:{variant}")
    lines = raw.splitlines()
    starts = [(index, match.group(1)) for index, line in enumerate(lines) if (match := ACTIVITY.match(line))]
    blocks = []
    for position, (start, component) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        state_matches = [STATE.search(line) for line in lines[start:end]]
        states = [match for match in state_matches if match is not None]
        if len(states) != 1:
            raise PlatformStateError(
                f"Activity blockのlifecycle stateが一意でありません: {surface}:{variant} component={component}"
            )
        resumed, stopped, finished = (value == "true" for value in states[0].groups())
        blocks.append({
            "component": component,
            "start_line": start + 1,
            "end_line": end,
            "states": {"mResumed": resumed, "mStopped": stopped, "mFinished": finished},
        })
    matches = [block for block in blocks if block["component"] == COMPONENT]
    if len(matches) != 1:
        raise PlatformStateError(
            f"current Activity blockはexact componentで1件必要です: {surface}:{variant} count={len(matches)}"
        )
    expected = {"mResumed": True, "mStopped": False, "mFinished": False}
    actual = matches[0]["states"]
    if actual != expected:
        raise PlatformStateError(
            f"Surface固有のcurrent Activity state不一致: {surface}:{variant} expected={expected} actual={actual}"
        )
    resumed_blocks = [block for block in blocks if block["states"]["mResumed"]]
    if len(resumed_blocks) != 1 or resumed_blocks[0]["component"] != COMPONENT:
        raise PlatformStateError(
            f"single-display profileのresumed Activityはexact target 1件必要です: {surface}:{variant} "
            f"resumed={[block['component'] for block in resumed_blocks]}"
        )
    return {
        "schema_version": 1,
        "surface_id": surface,
        "variant": variant,
        "component": COMPONENT,
        "activity_block": {"start_line": matches[0]["start_line"], "end_line": matches[0]["end_line"]},
        "activity_blocks": {
            "count": len(blocks),
            "resumed_count": len(resumed_blocks),
            "resumed_component": resumed_blocks[0]["component"],
        },
        "runtime_profile": "android-emulator-single-internal-display-non-multiwindow",
        "state_contract": state_contract(surface),
        "states": actual,
        "historical_package_match_accepted": False,
        "non_target_resumed_accepted": False,
        "validation": "passed",
    }


def raw_path(root: Path, surface: str, variant: str) -> Path:
    return root / "evidence/scenarios/runtime" / surface.replace(".", "/") / "security" / variant / "platform-state.txt"


def summary_path(root: Path, surface: str, variant: str) -> Path:
    return raw_path(root, surface, variant).with_name("platform-state.summary.json")


def build_summary(root: Path, surface: str, variant: str) -> dict[str, Any]:
    path = raw_path(root, surface, variant)
    value = validate_text(path.read_text(encoding="utf-8", errors="strict"), surface, variant)
    value["raw_artifact"] = {
        "path": path.relative_to(root).as_posix(),
        "digest": digest(path),
        "bytes": path.stat().st_size,
    }
    return value


def verify_all(root: Path, *, write: bool) -> int:
    count = 0
    for surface, variants in EXPECTED_ROWS.items():
        for variant in variants:
            expected = build_summary(root, surface, variant)
            path = summary_path(root, surface, variant)
            if write:
                path.write_text(json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            elif not path.is_file() or json.loads(path.read_text(encoding="utf-8")) != expected:
                raise PlatformStateError(f"bounded canonical summaryがraw dumpと一致しません: {surface}:{variant}")
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        count = verify_all(args.repo_root.resolve(), write=args.write)
        print(f"Android current Activity state検証済み: rows={count}")
        return 0
    except (PlatformStateError, FileNotFoundError, json.JSONDecodeError) as error:
        print(f"Android current Activity stateエラー: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
