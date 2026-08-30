#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Offline verifier for the raw authority anchor denominator."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tooling.authority_extraction.body_inventory import (  # noqa: E402
    GENERATED_AT, INDEX_PATH, OUTPUT_DIR, SELECTOR_CONTRACT, anchor_counts, artifact_digest, collect_inputs,
)
from tooling.authority_extraction.verify import AuthorityError, assert_exact_keys, assert_no_body_fields  # noqa: E402


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert_no_body_fields(value)
    return value


def verify(root: Path = ROOT) -> dict[str, Any]:
    inputs = collect_inputs(root)
    index = load_json(root / INDEX_PATH.relative_to(ROOT))
    assert_exact_keys(index, {"schema_version", "atlas_id", "generated_at", "status", "input_digest", "tool_digest", "body_storage", "selector_contract", "summary", "documents"}, "Authority body index")
    summary_keys = {"source_entries", "unique_documents", "matched_documents", "stale_documents", "failed_documents", "deferred_documents", "selector_exhaustive_documents", "raw_anchors", "anchors_by_kind", "pending_human_anchors", "human_decided_anchors", "promoted_surface_anchors", "promoted_atomic_behavior_anchors", "core_v2_eligible_artifacts", "raw_anchors_count_as_semantic_surfaces", "authority_semantics_exhaustive"}
    assert_exact_keys(index["summary"], summary_keys, "Authority body summary")
    if index["schema_version"] != 1 or index["atlas_id"] != "flutter-reference-atlas" or index["generated_at"] != GENERATED_AT or index["status"] != "incomplete-human-review-required":
        raise AuthorityError("Authority body index identityが不正です")
    if index["input_digest"] != inputs["input_digest"] or index["tool_digest"] != inputs["tool_digest"] or index["selector_contract"] != SELECTOR_CONTRACT or index["body_storage"] != "digest-locator-and-offset-only":
        raise AuthorityError("Authority body input/tool/selector境界がdriftしています")
    expected_files = sorted(f"{item['document_id']}.json" for item in inputs["documents"])
    actual_files = sorted(path.name for path in (root / OUTPUT_DIR.relative_to(ROOT)).glob("*.json"))
    if actual_files != expected_files:
        raise AuthorityError("Authority body document集合がSource lockと一致しません")
    records = {item["id"]: item for item in index["documents"]}
    if len(records) != len(index["documents"]):
        raise AuthorityError("Authority body document IDが重複しています")
    fetch_counts: Counter[str] = Counter()
    all_anchors = []
    seen_anchor_ids: set[str] = set()
    artifact_keys = {"schema_version", "document_id", "fetch_url", "source_ids", "locked_body_digest", "fetch", "extraction", "anchors"}
    fetch_keys = {"status", "fetched_digest", "locked_digest_match", "http_status", "final_url", "content_type", "fetched_bytes", "error_digest", "deferred_reason"}
    extraction_keys = {"method", "tool", "tool_digest", "selector_contract", "selector_exhaustive_for_locked_body", "authority_semantics_exhaustive", "review_status", "body_storage"}
    anchor_keys = {"id", "locator", "locator_kind", "semantic_kind", "tag", "heading_level", "parent_anchor_id", "context_start", "context_end", "context_unit", "context_digest", "label_digest", "classification_status", "human_decision_id", "surface_ids", "atomic_behavior_ids"}
    for item in inputs["documents"]:
        artifact = load_json(root / OUTPUT_DIR.relative_to(ROOT) / f"{item['document_id']}.json")
        assert_exact_keys(artifact, artifact_keys, f"Authority body artifact {item['document_id']}")
        assert_exact_keys(artifact["fetch"], fetch_keys, f"Authority body fetch {item['document_id']}")
        assert_exact_keys(artifact["extraction"], extraction_keys, f"Authority body extraction {item['document_id']}")
        if artifact["document_id"] != item["document_id"] or artifact["fetch_url"] != item["fetch_url"] or artifact["source_ids"] != item["source_ids"] or artifact["locked_body_digest"] != item["locked_digest"]:
            raise AuthorityError(f"Authority body document identityが不正です: {item['document_id']}")
        extraction = artifact["extraction"]
        if extraction["tool_digest"] != inputs["tool_digest"] or extraction["selector_contract"] != SELECTOR_CONTRACT or extraction["authority_semantics_exhaustive"] is not False or extraction["review_status"] != "automated-unreviewed" or extraction["body_storage"] != "digest-locator-and-offset-only":
            raise AuthorityError(f"Authority body extraction境界が不正です: {item['document_id']}")
        status = artifact["fetch"]["status"]
        fetch_counts[status] += 1
        if status == "matched":
            if artifact["fetch"]["fetched_digest"] != item["locked_digest"] or artifact["fetch"]["locked_digest_match"] is not True or extraction["selector_exhaustive_for_locked_body"] is not True or not artifact["anchors"]:
                raise AuthorityError(f"Matched body境界が不正です: {item['document_id']}")
        elif status == "stale":
            if artifact["fetch"]["fetched_digest"] is None or artifact["fetch"]["fetched_digest"] == item["locked_digest"] or artifact["fetch"]["locked_digest_match"] is not False:
                raise AuthorityError(f"Stale body digest境界が不正です: {item['document_id']}")
            if extraction["selector_exhaustive_for_locked_body"] is not False or artifact["anchors"]:
                raise AuthorityError(f"stale documentからraw anchorを生成できません: {item['document_id']}")
        elif status == "failed":
            if artifact["fetch"]["fetched_digest"] is not None or artifact["fetch"]["error_digest"] is None:
                raise AuthorityError(f"Failed body境界が不正です: {item['document_id']}")
            if extraction["selector_exhaustive_for_locked_body"] is not False or artifact["anchors"]:
                raise AuthorityError(f"failed documentからraw anchorを生成できません: {item['document_id']}")
        elif status == "deferred":
            if artifact["fetch"]["fetched_digest"] is not None or artifact["fetch"]["deferred_reason"] is None:
                raise AuthorityError(f"Deferred body境界が不正です: {item['document_id']}")
            if extraction["selector_exhaustive_for_locked_body"] is not False or artifact["anchors"]:
                raise AuthorityError(f"deferred documentからraw anchorを生成できません: {item['document_id']}")
        else:
            raise AuthorityError(f"未知fetch statusです: {item['document_id']}")
        local_ids: set[str] = set()
        for position, anchor in enumerate(artifact["anchors"]):
            assert_exact_keys(anchor, anchor_keys, f"Authority raw anchor {item['document_id']}:{position}")
            if anchor["id"] in seen_anchor_ids or not re.fullmatch(r"anchor-[a-z0-9-]+", anchor["id"]):
                raise AuthorityError(f"Authority raw anchor IDが不正または重複しています: {anchor['id']}")
            seen_anchor_ids.add(anchor["id"])
            if anchor["classification_status"] != "pending-human" or anchor["human_decision_id"] is not None or anchor["surface_ids"] or anchor["atomic_behavior_ids"]:
                raise AuthorityError(f"人手decisionなしのSurface昇格を拒否します: {anchor['id']}")
            if anchor["context_unit"] != "utf8-byte" or anchor["context_start"] < 0 or anchor["context_end"] <= anchor["context_start"] or not re.fullmatch(r"sha256:[a-f0-9]{64}", anchor["context_digest"]):
                raise AuthorityError(f"Authority raw anchor offset/digestが不正です: {anchor['id']}")
            if anchor["label_digest"] is not None and not re.fullmatch(r"sha256:[a-f0-9]{64}", anchor["label_digest"]):
                raise AuthorityError(f"Authority raw anchor label digestが不正です: {anchor['id']}")
            if position == 0 and (anchor["locator"] != "document-root" or anchor["parent_anchor_id"] is not None):
                raise AuthorityError(f"Authority document root anchorが不正です: {item['document_id']}")
            if position > 0 and anchor["parent_anchor_id"] not in local_ids:
                raise AuthorityError(f"Authority raw anchor parentが先行定義されていません: {anchor['id']}")
            local_ids.add(anchor["id"])
        all_anchors.extend(artifact["anchors"])
        expected_record = {"id": item["document_id"], "path": f"authority/body-inventory-draft/{item['document_id']}.json", "digest": artifact_digest(artifact), "fetch_status": status, "source_entries": len(item["source_ids"]), "raw_anchors": len(artifact["anchors"]), "anchors_by_kind": anchor_counts(artifact["anchors"])}
        if records.get(item["document_id"]) != expected_record:
            raise AuthorityError(f"Authority body index recordが不正です: {item['document_id']}")
    expected_summary = {"source_entries": inputs["source_entries"], "unique_documents": len(inputs["documents"]), "matched_documents": fetch_counts["matched"], "stale_documents": fetch_counts["stale"], "failed_documents": fetch_counts["failed"], "deferred_documents": fetch_counts["deferred"], "selector_exhaustive_documents": fetch_counts["matched"], "raw_anchors": len(all_anchors), "anchors_by_kind": anchor_counts(all_anchors), "pending_human_anchors": len(all_anchors), "human_decided_anchors": 0, "promoted_surface_anchors": 0, "promoted_atomic_behavior_anchors": 0, "core_v2_eligible_artifacts": 0, "raw_anchors_count_as_semantic_surfaces": False, "authority_semantics_exhaustive": False}
    if index["summary"] != expected_summary:
        raise AuthorityError("Authority body summaryがArtifact実体と一致しません")
    return index


def main() -> int:
    try:
        index = verify()
    except (OSError, json.JSONDecodeError, AuthorityError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    summary = index["summary"]
    print(f"Authority body inventory検証済み: documents={summary['unique_documents']} matched={summary['matched_documents']} stale={summary['stale_documents']} failed={summary['failed_documents']} deferred={summary['deferred_documents']} raw_anchors={summary['raw_anchors']} pending_human={summary['pending_human_anchors']} semantic_surface_credit=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
