#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Formal Gateが固定Flutter SDKの同一Source集合を使用することを検証する。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"moduleをloadできません: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SURFACE = load_module(
    "flutter_atlas_surface_inventory", REPO_ROOT / "tooling/surface_inventory/generate.py"
)
DEFINITIVE = load_module(
    "flutter_atlas_definitive_inventory", REPO_ROOT / "tooling/definitive_inventory/generate.py"
)


class BindingError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BindingError(f"JSONを読めません: {path}: {error}") from error
    if not isinstance(document, dict):
        raise BindingError(f"JSON rootがobjectではありません: {path}")
    return document


def normalize_sdk_root(raw: str) -> Path:
    if not raw.strip():
        raise BindingError("SDK rootが空です")
    return Path(raw).expanduser().resolve()


def validate_root_shape(root: Path) -> None:
    if not root.is_dir():
        raise BindingError(f"SDK rootが存在しません: {root}")
    for relative in (Path("bin/flutter"), Path("bin/dart"), Path(".git")):
        path = root / relative
        if not path.exists():
            raise BindingError(f"SDK rootに必須pathがありません: {relative}")
    for relative in (Path("bin/flutter"), Path("bin/dart")):
        if not os.access(root / relative, os.X_OK):
            raise BindingError(f"SDK executableを実行できません: {relative}")


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def collect_source_set(root: Path, patterns: list[str]) -> list[dict[str, str]]:
    try:
        return DEFINITIVE.resolve_sources(root, patterns)
    except (DEFINITIVE.InventoryError, OSError) as error:
        raise BindingError(str(error)) from error


def validate_verified_metadata(
    actual: dict[str, Any], expected: object
) -> None:
    if not isinstance(expected, dict) or actual != expected:
        raise BindingError(
            "SDK version/revision/metadata digestが固定Public Surface Inventoryと一致しません"
        )


def verify_binding(repo_root: Path, sdk_root: Path) -> dict[str, Any]:
    validate_root_shape(sdk_root)
    baseline_path = repo_root / "baseline/flutter-3.47.1.yaml"
    baseline = SURFACE.read_baseline(baseline_path)
    try:
        verified = SURFACE.verify_sdk(sdk_root, baseline)
    except (SURFACE.InventoryError, OSError) as error:
        raise BindingError(str(error)) from error

    public_inventory = load_json(repo_root / "baseline/public-surface-inventory.json")
    expected_metadata = public_inventory.get("baseline")
    validate_verified_metadata(verified, expected_metadata)

    requirements = load_json(repo_root / "definitive/requirements.json")
    definitive_inventory = load_json(repo_root / "atlas/definitive/surface-inventory.json")
    expected_by_id = {
        item.get("id"): item for item in definitive_inventory.get("surfaces", [])
    }
    checked_patterns = 0
    checked_files: set[str] = set()
    for requirement in requirements.get("surfaces", []):
        surface_id = requirement.get("id")
        patterns = requirement.get("source_globs")
        if not isinstance(patterns, list) or not patterns:
            raise BindingError(f"SurfaceのSource patternが空です: {surface_id}")
        expected = expected_by_id.get(surface_id)
        if not isinstance(expected, dict):
            raise BindingError(f"固定Definitive InventoryにSurfaceがありません: {surface_id}")
        actual_sources = collect_source_set(sdk_root, patterns)
        if actual_sources != expected.get("sdk_sources"):
            raise BindingError(f"SDK Source path/digest集合が固定値と一致しません: {surface_id}")
        if canonical_digest(actual_sources) != expected.get("sdk_source_set_digest"):
            raise BindingError(f"SDK Source集合digestが固定値と一致しません: {surface_id}")
        checked_patterns += len(patterns)
        checked_files.update(item["path"] for item in actual_sources)

    if checked_patterns == 0 or not checked_files:
        raise BindingError("SDK Source検証対象が0件です")
    return {
        "flutter_version": verified["flutter_version"],
        "framework_revision": verified["framework_revision"],
        "checked_patterns": checked_patterns,
        "checked_source_files": len(checked_files),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdk-root", required=True)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    args = parser.parse_args()
    try:
        sdk_root = normalize_sdk_root(args.sdk_root)
        result = verify_binding(Path(args.repo_root).resolve(), sdk_root)
    except BindingError as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    print(
        "Flutter SDK binding検証済み: "
        f"version={result['flutter_version']} "
        f"revision={result['framework_revision']} "
        f"patterns={result['checked_patterns']} "
        f"sources={result['checked_source_files']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
