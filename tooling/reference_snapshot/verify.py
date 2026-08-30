#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Materialize and verify copyright-permitted locked reference snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


MANIFEST = "SNAPSHOT.json"


class ReferenceSnapshotError(RuntimeError):
    pass


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical_manifest(lock: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mode": "locked-content-snapshot",
        "repository": lock["repository"],
        "commit": lock["commit"],
        "files": lock["files"],
    }


def expected_paths(lock: dict[str, Any]) -> set[str]:
    return {item["path"] for item in lock["files"]}


def verify_snapshot(root: Path, lock: dict[str, Any]) -> None:
    manifest_path = root / MANIFEST
    if not manifest_path.is_file():
        raise ReferenceSnapshotError(f"Reference snapshot manifestがありません: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest != canonical_manifest(lock):
        raise ReferenceSnapshotError("Reference snapshotのcommit/file lockが一致しません")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != MANIFEST
    }
    expected = expected_paths(lock)
    if actual != expected:
        raise ReferenceSnapshotError(
            f"Reference snapshot file setが一致しません: missing={sorted(expected - actual)[:3]} "
            f"extra={sorted(actual - expected)[:3]}"
        )
    for item in lock["files"]:
        observed = digest_bytes((root / item["path"]).read_bytes())
        if observed != item["digest"]:
            raise ReferenceSnapshotError(
                f"Reference snapshot digestが一致しません: {item['path']}"
            )


def verify_locked_reference(root: Path, lock: dict[str, Any]) -> None:
    if (root / ".git").exists():
        commit = subprocess.check_output(
            ["git", "rev-parse", f"{lock['commit']}^{{commit}}"], cwd=root, text=True
        ).strip()
        if commit != lock["commit"]:
            raise ReferenceSnapshotError("Reference commitが一致しません")
        for item in lock["files"]:
            content = subprocess.check_output(
                ["git", "show", f"{commit}:{item['path']}"], cwd=root
            )
            if digest_bytes(content) != item["digest"]:
                raise ReferenceSnapshotError(
                    f"Reference digestが一致しません: {item['path']}"
                )
        return
    verify_snapshot(root, lock)


def materialize(source_root: Path, output_root: Path, lock: dict[str, Any]) -> None:
    if output_root.exists() and any(output_root.rglob("*")):
        raise ReferenceSnapshotError(f"既存の非空Snapshotへの上書きはしません: {output_root}")
    commit = subprocess.check_output(
        ["git", "rev-parse", f"{lock['commit']}^{{commit}}"], cwd=source_root, text=True
    ).strip()
    if commit != lock["commit"]:
        raise ReferenceSnapshotError("Materialize対象commitが一致しません")
    output_root.mkdir(parents=True, exist_ok=True)
    for item in lock["files"]:
        content = subprocess.check_output(
            ["git", "show", f"{commit}:{item['path']}"], cwd=source_root
        )
        if digest_bytes(content) != item["digest"]:
            raise ReferenceSnapshotError(f"Materialize元digestが一致しません: {item['path']}")
        destination = output_root / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    (output_root / MANIFEST).write_text(
        json.dumps(canonical_manifest(lock), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    verify_snapshot(output_root, lock)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        lock = json.loads(args.lock.read_text(encoding="utf-8"))
        if args.write:
            if args.source_root is None:
                raise ReferenceSnapshotError("--writeには--source-rootが必要です")
            materialize(args.source_root.resolve(), args.reference_root.resolve(), lock)
        else:
            verify_locked_reference(args.reference_root.resolve(), lock)
        print(f"Reference snapshot検証済み: commit={lock['commit']} files={len(lock['files'])}")
        return 0
    except (OSError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError, ReferenceSnapshotError) as error:
        print(f"Reference snapshotエラー: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
