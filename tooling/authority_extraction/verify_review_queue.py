#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Offline verifier for the human authority review queue."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tooling.authority_extraction.review_queue import DECISIONS_PATH, INDEX_PATH, QUEUE_DIR, build, load_json  # noqa: E402
from tooling.authority_extraction.verify import AuthorityError  # noqa: E402


def verify(root: Path = ROOT) -> dict:
    expected = build(root)
    index = load_json(root / INDEX_PATH.relative_to(ROOT))
    if index != expected["index"]:
        raise AuthorityError("Authority review queue indexが入力・tool・batch実体の期待値と一致しません")
    queue_dir = root / QUEUE_DIR.relative_to(ROOT)
    actual_files = sorted(path.name for path in queue_dir.glob("*.json"))
    expected_files = sorted(f"{batch['batch_id']}.json" for batch in expected["batches"])
    if actual_files != expected_files:
        raise AuthorityError("Authority review batch file集合が不正です")
    queued_ids: list[str] = []
    for batch in expected["batches"]:
        actual = load_json(queue_dir / f"{batch['batch_id']}.json")
        if actual != batch:
            raise AuthorityError(f"Authority review batchが決定論生成値と一致しません: {batch['batch_id']}")
        for item in actual["items"]:
            if item["state"] != "pending-human" or item["review_queue_tool_digest"] != index["tool_digest"]:
                raise AuthorityError(f"Authority review item境界が不正です: {item['anchor_id']}")
            queued_ids.append(item["anchor_id"])
    if len(queued_ids) != len(set(queued_ids)) or sorted(queued_ids) != expected["eligible_anchor_ids"]:
        raise AuthorityError("Eligible raw anchorがstable IDで完全Queue化されていません")
    held_documents = {item["document_id"] for item in index["stale_holds"]}
    if held_documents & {item["document_id"] for batch in expected["batches"] for item in batch["items"]}:
        raise AuthorityError("Stale documentをReview queueへ投入できません")
    ledger = load_json(root / DECISIONS_PATH.relative_to(ROOT))
    if ledger != expected["ledger"]:
        raise AuthorityError("Authority review decision ledgerが検証済み入力と一致しません")
    summary = index["summary"]
    if summary["queue_count_as_semantic_surfaces"] is not False or index["semantic_decisions"] != "human-only":
        raise AuthorityError("Queue件数をSemantic Surfaceまたは機械decisionへ転用できません")
    return index


def main() -> int:
    try:
        index = verify()
    except (OSError, json.JSONDecodeError, AuthorityError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    summary = index["summary"]
    print(f"Authority review queue検証済み: anchors={summary['queued_anchors']} batches={summary['batches']} pending_human={summary['pending_human']} human_reviewed={summary['human_reviewed']} stale_holds={summary['stale_document_holds']} semantic_surface_credit=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
