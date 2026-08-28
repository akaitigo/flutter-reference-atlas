#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Flutter SDKからVersion固定の公開Surface Inventoryを生成する。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


FRAMEWORK_LIB = Path("packages/flutter/lib")
ENGINE_UI = Path("engine/src/flutter/lib/ui/ui.dart")
ENGINE_WEB_UI = Path("engine/src/flutter/lib/web_ui/lib/ui.dart")
ENGINE_UI_WEB = Path("engine/src/flutter/lib/web_ui/lib/ui_web/src/ui_web.dart")
DART_LIBRARIES = Path("bin/cache/dart-sdk/lib/libraries.json")
VERSION_METADATA = Path("bin/cache/flutter.version.json")
DEVTOOLS_METADATA = Path("bin/cache/dart-sdk/bin/resources/devtools/version.json")
DEPS = Path("DEPS")
INTERNAL_DART_LIBRARIES = {
    "html_common": "公開dart:html実装が共有する内部Library",
    "nativewrappers": "VM/DOM実装用の内部Library",
    "vmservice_io": "VM Service実装用の内部Library",
}

DIRECTIVE_RE = re.compile(
    r"\b(?P<kind>export|part)\s+['\"](?P<uri>[^'\"]+)['\"][^;]*;",
    re.MULTILINE,
)
DEPS_REVISION_RE = re.compile(r"'(?P<key>[^']+_revision|dart_devtools_rev)'\s*:\s*'(?P<value>[a-f0-9]{40})'")


class InventoryError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InventoryError(f"JSONを読めません: {path}: {error}") from error
    if not isinstance(value, dict):
        raise InventoryError(f"JSON rootがobjectではありません: {path}")
    return value


def read_directives(path: Path, kind: str) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return sorted(
        {match.group("uri") for match in DIRECTIVE_RE.finditer(text) if match.group("kind") == kind}
    )


def read_baseline(path: Path) -> dict[str, dict[str, str]]:
    """このRepositoryの固定Baselineから必要なscalarだけを読む。"""
    sections: dict[str, dict[str, str]] = {}
    section: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if not raw_line.startswith(" ") and raw_line.endswith(":"):
            section = raw_line[:-1]
            sections.setdefault(section, {})
            continue
        match = re.match(r"^  ([a-z_]+):\s*(.+?)\s*$", raw_line)
        if section and match:
            sections[section][match.group(1)] = match.group(2).strip("'\"")
    return sections


def git_output(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise InventoryError(f"git {' '.join(arguments)} に失敗しました: {completed.stderr.strip()}")
    return completed.stdout.strip()


def verify_sdk(root: Path, baseline: dict[str, dict[str, str]]) -> dict[str, Any]:
    version = read_json(root / VERSION_METADATA)
    devtools = read_json(root / DEVTOOLS_METADATA)
    deps_text = (root / DEPS).read_text(encoding="utf-8")
    deps_revisions = {match.group("key"): match.group("value") for match in DEPS_REVISION_RE.finditer(deps_text)}

    expected_flutter = baseline.get("flutter", {})
    expected_dart = baseline.get("dart", {})
    expected_devtools = baseline.get("devtools", {})
    checks = {
        "flutter.version": (version.get("flutterVersion"), expected_flutter.get("version")),
        "flutter.channel": (version.get("channel"), expected_flutter.get("channel")),
        "flutter.framework_revision": (
            version.get("frameworkRevision"),
            expected_flutter.get("framework_revision"),
        ),
        "flutter.engine_revision": (
            version.get("engineRevision"),
            expected_flutter.get("engine_revision"),
        ),
        "dart.version": (version.get("dartSdkVersion"), expected_dart.get("version")),
        "dart.revision": (deps_revisions.get("dart_revision"), expected_dart.get("revision")),
        "devtools.version": (devtools.get("version"), expected_devtools.get("version")),
        "devtools.revision": (
            deps_revisions.get("dart_devtools_rev"),
            expected_devtools.get("revision"),
        ),
    }
    mismatches = [f"{name}: actual={actual!r}, expected={expected!r}" for name, (actual, expected) in checks.items() if actual != expected]
    if mismatches:
        raise InventoryError("対象SDKがBaselineと一致しません: " + "; ".join(mismatches))

    head = git_output(root, "rev-parse", "HEAD")
    if head != expected_flutter.get("framework_revision"):
        raise InventoryError(f"SDK Git HEADがBaselineと一致しません: {head}")
    if (root / "bin/internal/engine.version").read_text(encoding="utf-8").strip() != expected_flutter.get("engine_revision"):
        raise InventoryError("bin/internal/engine.versionがBaselineと一致しません")

    return {
        "flutter_version": version["flutterVersion"],
        "channel": version["channel"],
        "framework_revision": version["frameworkRevision"],
        "framework_commit_date": version["frameworkCommitDate"],
        "engine_revision": version["engineRevision"],
        "engine_commit_date": version["engineCommitDate"],
        "engine_content_hash": version["engineContentHash"],
        "dart_version": version["dartSdkVersion"],
        "dart_revision": deps_revisions["dart_revision"],
        "devtools_version": devtools["version"],
        "devtools_revision": deps_revisions["dart_devtools_rev"],
        "skia_revision": deps_revisions["skia_revision"],
        "metadata_digests": {
            str(VERSION_METADATA): sha256_file(root / VERSION_METADATA),
            str(DEVTOOLS_METADATA): sha256_file(root / DEVTOOLS_METADATA),
            str(DEPS): sha256_file(root / DEPS),
            str(DART_LIBRARIES): sha256_file(root / DART_LIBRARIES),
        },
    }


def framework_inventory(root: Path) -> dict[str, Any]:
    library_root = root / FRAMEWORK_LIB
    libraries = []
    for path in sorted(library_root.glob("*.dart")):
        if path.name.startswith("_"):
            continue
        libraries.append(
            {
                "id": f"package:flutter/{path.name}",
                "path": str(path.relative_to(root)),
                "exports": read_directives(path, "export"),
                "source_digest": sha256_file(path),
            }
        )
    return {
        "granularity": "public-library-entrypoint-and-direct-export-edge",
        "library_count": len(libraries),
        "libraries": libraries,
    }


def engine_inventory(root: Path) -> dict[str, Any]:
    definitions = [
        ("dart:ui", "native", ENGINE_UI),
        ("dart:ui", "web", ENGINE_WEB_UI),
        ("dart:ui_web", "web", ENGINE_UI_WEB),
    ]
    libraries = []
    for library_id, platform, relative in definitions:
        path = root / relative
        if not path.is_file():
            raise InventoryError(f"Engine公開Library sourceがありません: {relative}")
        libraries.append(
            {
                "id": library_id,
                "platform": platform,
                "path": str(relative),
                "parts": read_directives(path, "part"),
                "exports": read_directives(path, "export"),
                "source_digest": sha256_file(path),
            }
        )
    return {
        "granularity": "public-library-implementation-entrypoint",
        "implementation_count": len(libraries),
        "logical_library_count": len({item["id"] for item in libraries}),
        "libraries": libraries,
    }


def dart_inventory(root: Path) -> dict[str, Any]:
    document = read_json(root / DART_LIBRARIES)
    platforms: dict[str, set[str]] = {}
    for section_name, section_value in document.items():
        if not isinstance(section_value, dict):
            continue
        libraries = section_value.get("libraries")
        if not isinstance(libraries, dict):
            continue
        for name in libraries:
            if not name.startswith("_") and name not in INTERNAL_DART_LIBRARIES:
                platforms.setdefault(name, set()).add(section_name)
    libraries = [
        {"id": f"dart:{name}", "platform_sections": sorted(sections)}
        for name, sections in sorted(platforms.items())
    ]
    return {
        "granularity": "public-library-entrypoint-by-sdk-platform-section",
        "library_count": len(libraries),
        "libraries": libraries,
        "excluded_registry_libraries": [
            {"id": f"dart:{name}", "reason": reason}
            for name, reason in sorted(INTERNAL_DART_LIBRARIES.items())
        ],
    }


def cli_inventory(root: Path) -> dict[str, Any]:
    commands_root = root / "packages/flutter_tools/lib/src/commands"
    commands = []
    for path in sorted(commands_root.glob("*.dart")):
        if path.name.startswith("_"):
            continue
        commands.append(
            {
                "source_id": path.stem.replace("_", "-"),
                "path": str(path.relative_to(root)),
                "source_digest": sha256_file(path),
            }
        )
    return {
        "granularity": "flutter-command-source-file",
        "note": "Command sourceは公開APIではなく、CLI分類対象の有限集合である。",
        "command_source_count": len(commands),
        "commands": commands,
    }


def generate(root: Path, baseline_path: Path) -> dict[str, Any]:
    baseline = read_baseline(baseline_path)
    verified = verify_sdk(root, baseline)
    return {
        "schema_version": 1,
        "atlas_id": "flutter-reference-atlas",
        "coverage_epoch": "2026-08-28",
        "generator": "tooling/surface_inventory/generate.py",
        "assurance": {
            "state": "complete",
            "meaning": "固定SDKに存在する公開Library entrypointと分類対象CLI sourceを欠落なく列挙した。Symbol単位のAPI互換性は別Gateである。",
            "private_api_included": False,
            "community_packages_included": False,
        },
        "baseline": verified,
        "surfaces": {
            "framework": framework_inventory(root),
            "engine": engine_inventory(root),
            "dart": dart_inventory(root),
            "flutter_cli": cli_inventory(root),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Flutter公開Surface Inventoryを生成・検証します。")
    parser.add_argument("--sdk-root", required=True, type=Path, help="対象Flutter SDK root")
    parser.add_argument(
        "--baseline",
        default=Path("baseline/flutter-3.47.1.yaml"),
        type=Path,
        help="固定Baseline YAML",
    )
    parser.add_argument("--output", type=Path, help="JSON出力先。省略時はstdout")
    parser.add_argument("--check", action="store_true", help="既存出力が再生成結果と一致するか検証")
    args = parser.parse_args()

    try:
        document = generate(args.sdk_root.resolve(), args.baseline.resolve())
        encoded = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.check:
            if args.output is None:
                raise InventoryError("--checkには--outputが必要です")
            existing = args.output.read_text(encoding="utf-8")
            if existing != encoded:
                raise InventoryError(f"Inventoryが再生成結果と一致しません: {args.output}")
            print(f"Surface Inventory検証済み: {args.output}")
            return 0
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
            print(f"Surface Inventory生成済み: {args.output}")
        else:
            sys.stdout.write(encoded)
        return 0
    except (InventoryError, OSError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
