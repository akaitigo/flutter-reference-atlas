#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate explicit legacy artifact-path mappings without reusing old proof."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "migrations/security-platform-artifact-v1.json"


class MigrationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def expected_documents(root: Path, manifest: dict[str, object]) -> dict[str, bytes]:
    mappings = manifest.get("mappings")
    if not isinstance(mappings, list) or len(mappings) != 4:
        raise MigrationError("exactly four artifact mappings are required")
    documents: dict[str, bytes] = {}
    for mapping in mappings:
        if not isinstance(mapping, dict):
            raise MigrationError("mapping must be an object")
        old_path = mapping.get("old_path")
        new_path = mapping.get("new_path")
        evidence_path = mapping.get("migration_evidence")
        reason = mapping.get("reason")
        if not all(isinstance(value, str) and value for value in (old_path, new_path, evidence_path, reason)):
            raise MigrationError("mapping fields must be non-empty strings")
        if not old_path.endswith("/platform-tree.xml") or not new_path.endswith("/platform-state.txt"):
            raise MigrationError("artifact mapping path kinds are invalid")
        replacement = root / new_path
        evidence = root / evidence_path
        if not replacement.is_file() or not evidence.is_file():
            raise MigrationError(f"replacement or migration evidence missing: {old_path}")
        result = json.loads(evidence.read_text(encoding="utf-8"))
        artifact = result.get("platform_artifact", {})
        digest = sha256(replacement)
        if artifact.get("path") != new_path or artifact.get("digest") != digest:
            raise MigrationError(f"result binding mismatch: {old_path}")
        node = ElementTree.Element(
            "artifact-migration",
            {
                "schema-version": "1",
                "status": "historical-identifier-preserved",
                "proof-eligible": "false",
                "old-path": old_path,
                "replacement-path": new_path,
                "replacement-digest": digest,
                "migration-evidence": evidence_path,
            },
        )
        ElementTree.SubElement(node, "reason").text = reason
        documents[old_path] = ElementTree.tostring(node, encoding="utf-8", xml_declaration=True) + b"\n"
    if len(documents) != len(mappings):
        raise MigrationError("old artifact paths must be unique")
    return documents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        documents = expected_documents(ROOT, manifest)
        for relative, content in documents.items():
            path = ROOT / relative
            if args.check:
                if not path.is_file() or path.read_bytes() != content:
                    raise MigrationError(f"artifact migration drift: {relative}")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
    except (OSError, json.JSONDecodeError, MigrationError) as error:
        print(f"Artifact migrationエラー: {error}")
        return 1
    print(f"Artifact migration検証済み: mappings={len(documents)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
