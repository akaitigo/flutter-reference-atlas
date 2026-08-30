#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build a human-only review queue from stable raw authority anchors."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tooling.authority_extraction.extract import sha256  # noqa: E402
from tooling.authority_extraction.verify import AuthorityError, assert_exact_keys, assert_no_body_fields  # noqa: E402

INDEX_PATH = ROOT / "authority/review-queue.snapshot.json"
QUEUE_DIR = ROOT / "authority/review-queue-draft"
DECISIONS_PATH = ROOT / "authority/reviews/decisions.json"
BODY_INDEX_PATH = ROOT / "authority/body-inventory.snapshot.json"
GENERATED_AT = "2026-08-28T00:00:00+09:00"
TOOL_FILES = (
    "tooling/authority_extraction/review_queue.py",
    "tooling/authority_extraction/verify_review_queue.py",
    "tooling/authority_extraction/test_review_queue.py",
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert_no_body_fields(value)
    return value


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def artifact_digest(value: Any) -> str:
    return sha256(canonical_bytes(value))


def short_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:length]


def tool_digest(root: Path = ROOT) -> str:
    value = b"\0".join(relative.encode() + b"\0" + (root / relative).read_bytes() for relative in TOOL_FILES)
    return sha256(value)


def priority_for(anchor: dict[str, Any], edge_ids: list[str]) -> tuple[int, list[str]]:
    if edge_ids:
        return 0, ["existing-domain-reference-locator-match"]
    if anchor["semantic_kind"] in {"heading", "definition"}:
        return 1, ["semantic-label-anchor"]
    return 2, ["structural-or-document-anchor"]


def batch_id(priority: int, semantic_kind: str, anchor_id: str) -> str:
    bucket = f"{int(short_hash(anchor_id, 2), 16) % 64:02x}"
    return f"review-p{priority}-{semantic_kind}-{bucket}"


def empty_ledger(queue_id: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "atlas_id": "flutter-reference-atlas",
        "queue_id": queue_id,
        "status": "incomplete-human-review-required",
        "decisions": [],
    }


def expected_binding(item: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "anchor_id", "document_id", "document_url", "locked_source_digest",
        "inventory_tool_digest", "review_queue_tool_digest", "locator",
        "context_start", "context_end", "context_unit", "context_digest",
    )
    return {key: item[key] for key in keys}


def validate_decisions(decisions: list[dict[str, Any]], item_by_id: dict[str, dict[str, Any]]) -> set[str]:
    decision_ids: set[str] = set()
    decided_anchors: set[str] = set()
    result_owner: dict[str, str] = {}
    decision_keys = {"decision_id", "action", "anchor_ids", "source_bindings", "rationale", "reviewer", "reviewed_at", "review_method", "mapping", "result_items"}
    binding_keys = {"anchor_id", "document_id", "document_url", "locked_source_digest", "inventory_tool_digest", "review_queue_tool_digest", "locator", "context_start", "context_end", "context_unit", "context_digest"}
    mapping_keys = {"old_anchor_id", "new_item_ids"}
    result_keys = {"id", "item_type"}
    for decision in decisions:
        label = f"Authority review decision {decision.get('decision_id')}"
        assert_exact_keys(decision, decision_keys, label)
        decision_id = decision["decision_id"]
        if not re.fullmatch(r"decision\.[a-z0-9.-]+", decision_id) or decision_id in decision_ids:
            raise AuthorityError(f"Review decision IDが不正または重複しています: {decision_id}")
        decision_ids.add(decision_id)
        if decision["action"] not in {"include", "exclude", "merge", "split"}:
            raise AuthorityError(f"Review decision actionが不正です: {decision_id}")
        reviewer = decision["reviewer"].strip()
        if decision["review_method"] != "manual-primary-source" or len(decision["rationale"].strip()) < 40 or len(reviewer) < 2 or re.match(r"^(auto(?:mated)?|agent|bot|system|machine)(?:$|[-_. ])", reviewer, re.IGNORECASE):
            raise AuthorityError(f"人手による一次資料review provenanceが不足しています: {decision_id}")
        try:
            reviewed_at = datetime.fromisoformat(decision["reviewed_at"].replace("Z", "+00:00"))
        except (TypeError, ValueError) as error:
            raise AuthorityError(f"reviewed_atがISO date-timeではありません: {decision_id}") from error
        if reviewed_at.tzinfo is None:
            raise AuthorityError(f"reviewed_atにtimezoneがありません: {decision_id}")
        anchor_ids = decision["anchor_ids"]
        if not anchor_ids or len(anchor_ids) != len(set(anchor_ids)) or len(decision["source_bindings"]) != len(anchor_ids) or len(decision["mapping"]) != len(anchor_ids):
            raise AuthorityError(f"Decision anchor/binding/mapping cardinalityが不正です: {decision_id}")
        for anchor_id in anchor_ids:
            if anchor_id in decided_anchors:
                raise AuthorityError(f"Anchorに複数decisionがあります: {anchor_id}")
            if anchor_id not in item_by_id:
                raise AuthorityError(f"Queue外またはstale hold中anchorのdecisionです: {anchor_id}")
            decided_anchors.add(anchor_id)
        bindings: dict[str, dict[str, Any]] = {}
        for binding in decision["source_bindings"]:
            assert_exact_keys(binding, binding_keys, f"Decision binding {binding.get('anchor_id')}")
            if binding["anchor_id"] in bindings:
                raise AuthorityError(f"Decision binding IDが重複しています: {binding['anchor_id']}")
            bindings[binding["anchor_id"]] = binding
        mappings: dict[str, dict[str, Any]] = {}
        for mapping in decision["mapping"]:
            assert_exact_keys(mapping, mapping_keys, f"Decision mapping {mapping.get('old_anchor_id')}")
            if mapping["old_anchor_id"] in mappings or len(mapping["new_item_ids"]) != len(set(mapping["new_item_ids"])):
                raise AuthorityError(f"Decision mappingが重複しています: {mapping['old_anchor_id']}")
            if any(not re.fullmatch(r"[a-z][a-z0-9.-]+", item_id) for item_id in mapping["new_item_ids"]):
                raise AuthorityError(f"Decision mapping先IDが不正です: {mapping['old_anchor_id']}")
            mappings[mapping["old_anchor_id"]] = mapping
        if set(bindings) != set(anchor_ids) or set(mappings) != set(anchor_ids):
            raise AuthorityError(f"Decision binding/mappingが全anchorを覆っていません: {decision_id}")
        for anchor_id in anchor_ids:
            if bindings[anchor_id] != expected_binding(item_by_id[anchor_id]):
                raise AuthorityError(f"Decision digest/locator bindingがQueueと一致しません: {anchor_id}")
        results: dict[str, dict[str, Any]] = {}
        for result in decision["result_items"]:
            assert_exact_keys(result, result_keys, f"Decision result {result.get('id')}")
            if not re.fullmatch(r"[a-z][a-z0-9.-]+", result["id"]) or result["item_type"] not in {"surface", "atomic-behavior"} or result["id"] in results:
                raise AuthorityError(f"Decision result itemが不正または重複しています: {result.get('id')}")
            results[result["id"]] = result
        mapped_ids = {item_id for mapping in mappings.values() for item_id in mapping["new_item_ids"]}
        if mapped_ids != set(results):
            raise AuthorityError(f"Decision mappingとSurface/Atomic behavior resultが一致しません: {decision_id}")
        action = decision["action"]
        mapping_lists = [mapping["new_item_ids"] for mapping in mappings.values()]
        if action == "exclude" and any(mapping_lists):
            raise AuthorityError(f"excludeはnew itemへmappingできません: {decision_id}")
        if action == "include" and (any(not ids for ids in mapping_lists) or len(mapped_ids) != sum(map(len, mapping_lists))):
            raise AuthorityError(f"includeには非共有の旧→新mappingが必要です: {decision_id}")
        if action == "merge" and (len(anchor_ids) < 2 or any(not ids for ids in mapping_lists) or len({tuple(sorted(ids)) for ids in mapping_lists}) != 1):
            raise AuthorityError(f"merge mappingが不正です: {decision_id}")
        if action == "split" and (len(anchor_ids) != 1 or len(mapping_lists[0]) < 2):
            raise AuthorityError(f"split mappingが不正です: {decision_id}")
        for result_id in mapped_ids:
            owner = result_owner.get(result_id)
            if owner is not None and owner != decision_id:
                raise AuthorityError(f"new item IDが複数decisionで共有されています: {result_id}")
            result_owner[result_id] = decision_id
    return decided_anchors


def collect_inputs(root: Path = ROOT) -> dict[str, Any]:
    body_index = load_json(root / BODY_INDEX_PATH.relative_to(ROOT))
    artifacts = [load_json(root / record["path"]) for record in body_index["documents"]]
    digest_tool = tool_digest(root)
    anchors = sorted((anchor for artifact in artifacts if artifact["fetch"]["status"] == "matched" for anchor in artifact["anchors"]), key=lambda item: item["id"])
    anchor_ids = [anchor["id"] for anchor in anchors]
    queue_id = f"authority-review-{short_hash(body_index['input_digest'] + chr(0) + chr(0).join(anchor_ids), 20)}"
    input_digest = sha256(json.dumps({"body_input_digest": body_index["input_digest"], "anchor_ids": anchor_ids, "queue_tool_digest": digest_tool}, sort_keys=True, separators=(",", ":")).encode())
    return {"body_index": body_index, "artifacts": artifacts, "tool_digest": digest_tool, "queue_id": queue_id, "input_digest": input_digest}


def build(root: Path = ROOT) -> dict[str, Any]:
    inputs = collect_inputs(root)
    body_index = inputs["body_index"]
    artifacts = inputs["artifacts"]
    edge_ids: dict[tuple[str, str], list[str]] = defaultdict(list)
    for source_id in sorted({source_id for artifact in artifacts for source_id in artifact["source_ids"]}):
        edge_artifact = load_json(root / "authority/surfaces-draft" / f"{source_id}.json")
        for edge in edge_artifact["candidate_surfaces"]:
            edge_ids[(source_id, edge["locator"])].append(edge["edge_id"])
    label_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for artifact in artifacts:
        for anchor in artifact["anchors"]:
            if anchor["label_digest"] and anchor["semantic_kind"] in {"heading", "definition"}:
                label_groups[(anchor["semantic_kind"], anchor["label_digest"])].append(anchor["id"])
    cluster_by_anchor: dict[str, str] = {}
    for (semantic_kind, label_digest), ids in label_groups.items():
        if len(ids) > 1:
            cluster_id = f"candidate-cluster-{short_hash(semantic_kind + chr(0) + label_digest, 20)}"
            cluster_by_anchor.update({anchor_id: cluster_id for anchor_id in ids})
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    eligible_documents = 0
    for artifact in artifacts:
        if artifact["fetch"]["status"] != "matched":
            continue
        eligible_documents += 1
        for anchor in artifact["anchors"]:
            matched_edges = sorted({edge_id for source_id in artifact["source_ids"] for edge_id in edge_ids.get((source_id, anchor["locator"]), [])})
            priority, reasons = priority_for(anchor, matched_edges)
            batch = batch_id(priority, anchor["semantic_kind"], anchor["id"])
            grouped[batch].append({
                "anchor_id": anchor["id"], "document_id": artifact["document_id"], "document_url": artifact["fetch_url"],
                "source_ids": artifact["source_ids"], "locked_source_digest": artifact["locked_body_digest"],
                "inventory_tool_digest": artifact["extraction"]["tool_digest"], "review_queue_tool_digest": inputs["tool_digest"],
                "locator": anchor["locator"], "locator_kind": anchor["locator_kind"], "semantic_kind": anchor["semantic_kind"],
                "tag": anchor["tag"], "heading_level": anchor["heading_level"], "parent_anchor_id": anchor["parent_anchor_id"],
                "context_start": anchor["context_start"], "context_end": anchor["context_end"], "context_unit": anchor["context_unit"],
                "context_digest": anchor["context_digest"], "label_digest": anchor["label_digest"],
                "existing_reference_edge_ids": matched_edges, "priority": priority, "priority_reasons": reasons,
                "candidate_cluster_id": cluster_by_anchor.get(anchor["id"]), "batch_id": batch, "state": "pending-human",
            })
    batches = []
    for batch, items in sorted(grouped.items()):
        batches.append({"schema_version": 1, "queue_id": inputs["queue_id"], "batch_id": batch, "status": "pending-human", "machine_assistance": "ordering-and-candidate-clustering-only", "semantic_decisions": "none", "items": sorted(items, key=lambda item: item["anchor_id"])})
    batch_records = []
    for batch in batches:
        match = re.fullmatch(r"review-p([0-2])-(.+)-([0-9a-f]{2})", batch["batch_id"])
        if match is None:
            raise AuthorityError(f"Review batch IDが不正です: {batch['batch_id']}")
        batch_records.append({"id": batch["batch_id"], "path": f"authority/review-queue-draft/{batch['batch_id']}.json", "digest": artifact_digest(batch), "priority": int(match.group(1)), "semantic_kind": match.group(2), "bucket": match.group(3), "items": len(batch["items"])})
    stale_holds = []
    for artifact in artifacts:
        if artifact["fetch"]["status"] == "stale":
            stale_holds.append({
                "document_id": artifact["document_id"], "document_url": artifact["fetch_url"], "source_ids": artifact["source_ids"],
                "locked_source_digest": artifact["locked_body_digest"], "inventory_tool_digest": artifact["extraction"]["tool_digest"],
                "review_queue_tool_digest": inputs["tool_digest"], "locator": "document-root", "fetched_digest": artifact["fetch"]["fetched_digest"],
                "status": "hold-stale-document-relock-required", "reason": "locked-document-body-digest-mismatch",
            })
    stale_holds.sort(key=lambda item: item["document_id"])
    ledger_path = root / DECISIONS_PATH.relative_to(ROOT)
    ledger = load_json(ledger_path) if ledger_path.is_file() else empty_ledger(inputs["queue_id"])
    assert_exact_keys(ledger, {"schema_version", "atlas_id", "queue_id", "status", "decisions"}, "Authority review decision ledger")
    if ledger["schema_version"] != 1 or ledger["atlas_id"] != "flutter-reference-atlas" or ledger["queue_id"] != inputs["queue_id"] or ledger["status"] != "incomplete-human-review-required":
        raise AuthorityError("Authority review decision ledger identity/statusが現在のQueueと一致しません")
    items = [item for batch in batches for item in batch["items"]]
    item_by_id = {item["anchor_id"]: item for item in items}
    decided = validate_decisions(ledger["decisions"], item_by_id)
    priorities = Counter(item["priority"] for item in items)
    cluster_ids = {item["candidate_cluster_id"] for item in items if item["candidate_cluster_id"] is not None}
    actions = Counter(decision["action"] for decision in ledger["decisions"])
    index = {
        "schema_version": 1, "atlas_id": "flutter-reference-atlas", "generated_at": GENERATED_AT,
        "status": "incomplete-human-review-required", "queue_id": inputs["queue_id"], "input_digest": inputs["input_digest"],
        "tool_digest": inputs["tool_digest"], "decision_ledger": "authority/reviews/decisions.json",
        "body_storage": "digest-locator-and-offset-only", "machine_assistance": "dedupe-candidate-cluster-priority-and-batch-only",
        "semantic_decisions": "human-only",
        "summary": {
            "eligible_documents": eligible_documents, "queued_anchors": len(items), "pending_human": len(items) - len(decided),
            "human_reviewed": len(decided), "priority_counts": {str(key): priorities[key] for key in range(3)},
            "candidate_clusters": len(cluster_ids), "clustered_anchors": sum(item["candidate_cluster_id"] is not None for item in items),
            "batches": len(batches), "stale_document_holds": len(stale_holds), "decisions": len(ledger["decisions"]),
            "included": actions["include"], "excluded": actions["exclude"], "merged": actions["merge"], "split": actions["split"],
            "queue_count_as_semantic_surfaces": False, "authority_semantics_exhaustive": False,
        },
        "batches": batch_records, "stale_holds": stale_holds,
    }
    return {"index": index, "batches": batches, "ledger": ledger, "eligible_anchor_ids": sorted(item_by_id)}


def write(root: Path = ROOT) -> dict[str, Any]:
    built = build(root)
    queue_dir = root / QUEUE_DIR.relative_to(ROOT)
    queue_dir.mkdir(parents=True, exist_ok=True)
    for batch in built["batches"]:
        (queue_dir / f"{batch['batch_id']}.json").write_bytes(canonical_bytes(batch))
    decisions_path = root / DECISIONS_PATH.relative_to(ROOT)
    decisions_path.parent.mkdir(parents=True, exist_ok=True)
    if not decisions_path.is_file():
        decisions_path.write_bytes(canonical_bytes(built["ledger"]))
    (root / INDEX_PATH.relative_to(ROOT)).write_bytes(canonical_bytes(built["index"]))
    return built["index"]


def main() -> int:
    try:
        index = write()
    except (OSError, json.JSONDecodeError, AuthorityError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    summary = index["summary"]
    print(f"Authority review queue生成済み: anchors={summary['queued_anchors']} batches={summary['batches']} pending_human={summary['pending_human']} stale_holds={summary['stale_document_holds']} semantic_surface_credit=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
