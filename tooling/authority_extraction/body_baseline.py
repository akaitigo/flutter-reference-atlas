#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Initialize or verify the additive raw-authority-anchor baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = ROOT / "baseline/authority-body-inventory-v1.json"
MIGRATION_PATH = ROOT / "migrations/authority-body-inventory-v1.json"
REPORT_PATH = ROOT / "evidence/artifacts/authority-body-non-regression-report.json"


class BaselineError(RuntimeError):
    pass


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build(root: Path = ROOT) -> dict[str, Any]:
    index = load(root / "authority/body-inventory.snapshot.json")
    documents = []
    for record in index["documents"]:
        artifact = load(root / record["path"])
        documents.append({
            "id": artifact["document_id"], "path": record["path"],
            "locked_body_digest": artifact["locked_body_digest"], "source_ids": artifact["source_ids"],
            "anchor_ids": sorted(anchor["id"] for anchor in artifact["anchors"]),
        })
    return {
        "schema_version": 1, "id": "flutter-authority-body-inventory-v1-2026-08-28",
        "captured_at": "2026-08-28T00:00:00+09:00", "source_entries": index["summary"]["source_entries"],
        "unique_documents": index["summary"]["unique_documents"], "selector_contract": index["selector_contract"],
        "documents": sorted(documents, key=lambda item: item["id"]),
    }


def write(root: Path = ROOT) -> None:
    baseline = build(root)
    BASELINE_PATH.write_text(json.dumps(baseline, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not MIGRATION_PATH.exists():
        MIGRATION_PATH.write_text(json.dumps({"schema_version": 1, "baseline_id": baseline["id"], "replacements": []}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise BaselineError(f"{label}のfield集合が不正です: {sorted(value)}")


def verify(root: Path = ROOT) -> dict[str, Any]:
    baseline = load(root / BASELINE_PATH.relative_to(ROOT))
    migration = load(root / MIGRATION_PATH.relative_to(ROOT))
    index = load(root / "authority/body-inventory.snapshot.json")
    exact_keys(baseline, {"schema_version", "id", "captured_at", "source_entries", "unique_documents", "selector_contract", "documents"}, "Authority body baseline")
    exact_keys(migration, {"schema_version", "baseline_id", "replacements"}, "Authority body migration")
    if baseline["schema_version"] != 1 or baseline["id"] != "flutter-authority-body-inventory-v1-2026-08-28" or migration["baseline_id"] != baseline["id"]:
        raise BaselineError("Authority body baseline identityが不正です")
    if index["summary"]["source_entries"] < baseline["source_entries"] or index["summary"]["unique_documents"] < baseline["unique_documents"] or index["selector_contract"] != baseline["selector_contract"]:
        raise BaselineError("Authority body source/document/selector floorが縮小しています")
    current_documents = {record["id"]: load(root / record["path"]) for record in index["documents"]}
    current_anchor_ids = {anchor["id"] for artifact in current_documents.values() for anchor in artifact["anchors"]}
    baseline_anchor_ids = {anchor_id for document in baseline["documents"] for anchor_id in document["anchor_ids"]}
    if len(baseline_anchor_ids) != sum(len(item["anchor_ids"]) for item in baseline["documents"]):
        raise BaselineError("Baseline anchor IDが重複しています")
    replacements: dict[str, dict[str, Any]] = {}
    replacement_new_ids: set[str] = set()
    for item in migration["replacements"]:
        exact_keys(item, {"old_anchor_id", "new_anchor_ids", "execution_proof", "migration_evidence", "reason"}, f"Authority anchor migration {item.get('old_anchor_id')}")
        if item["old_anchor_id"] not in baseline_anchor_ids or item["old_anchor_id"] in replacements or not item["new_anchor_ids"] or len(item["new_anchor_ids"]) != len(set(item["new_anchor_ids"])) or len(item["reason"]) < 20:
            raise BaselineError(f"Authority anchor migration mappingが不正です: {item['old_anchor_id']}")
        if item["old_anchor_id"] in current_anchor_ids:
            raise BaselineError(f"現存anchorをreplacement扱いにできません: {item['old_anchor_id']}")
        if item["execution_proof"] == item["migration_evidence"]:
            raise BaselineError(f"実行ProofとMigration Evidenceは別Artifactが必要です: {item['old_anchor_id']}")
        for new_id in item["new_anchor_ids"]:
            if new_id not in current_anchor_ids or new_id in replacement_new_ids:
                raise BaselineError(f"Authority anchor replacementが不正または共有されています: {new_id}")
            replacement_new_ids.add(new_id)
        for evidence_path in (item["execution_proof"], item["migration_evidence"]):
            if not (root / evidence_path).is_file():
                raise BaselineError(f"Authority anchor migration Evidenceがありません: {evidence_path}")
        replacements[item["old_anchor_id"]] = item
    retained = replaced = 0
    for expected in baseline["documents"]:
        exact_keys(expected, {"id", "path", "locked_body_digest", "source_ids", "anchor_ids"}, f"Authority baseline document {expected.get('id')}")
        current = current_documents.get(expected["id"])
        if current is None or current["locked_body_digest"] != expected["locked_body_digest"] or current["source_ids"] != expected["source_ids"]:
            raise BaselineError(f"Authority body documentが削除または置換されています: {expected['id']}")
        for anchor_id in expected["anchor_ids"]:
            if anchor_id in current_anchor_ids:
                retained += 1
            elif anchor_id in replacements:
                replaced += 1
            else:
                raise BaselineError(f"Authority raw anchorがMappingなしで削除されています: {anchor_id}")
    report = {
        "schema_version": 1, "baseline_id": baseline["id"], "baseline_anchors": len(baseline_anchor_ids),
        "current_anchors": len(current_anchor_ids), "retained": retained, "replaced": replaced,
        "added": len(current_anchor_ids) - retained - len(replacement_new_ids),
        "document_floor": f"{len(baseline['documents'])}/{len(current_documents)}", "status": "pass",
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        if args.write:
            write()
            print("Authority body baselineを初期化しました")
            return 0
        report = verify()
    except (OSError, json.JSONDecodeError, BaselineError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    print(f"Authority body non-regression検証済み: retained={report['retained']}/{report['baseline_anchors']} replaced={report['replaced']} added={report['added']} documents={report['document_floor']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
