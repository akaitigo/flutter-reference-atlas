#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Offline verification for copyright-safe authority locator artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tooling.authority_extraction.extract import (  # noqa: E402
    GENERATED_AT, INDEX_PATH, OUTPUT_DIR, canonical_digest, collect_inputs,
)

FORBIDDEN_BODY_FIELDS = {
    "body", "content", "excerpt", "quote", "raw", "raw_body", "response_body",
    "response_text", "text", "third_party_text",
}


class AuthorityError(RuntimeError):
    pass


def assert_no_body_fields(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in FORBIDDEN_BODY_FIELDS:
                raise AuthorityError(f"第三者本文fieldは禁止です: {path}.{key}")
            assert_no_body_fields(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            assert_no_body_fields(nested, f"{path}[{index}]")


def assert_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise AuthorityError(f"{label}のfield集合が不正です: {sorted(value)}")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AuthorityError(f"JSON rootがobjectではありません: {path}")
    assert_no_body_fields(value)
    return value


def verify(root: Path = ROOT) -> dict[str, Any]:
    inputs = collect_inputs(root)
    index = load_json(root / INDEX_PATH.relative_to(ROOT))
    assert_exact_keys(index, {"schema_version", "atlas_id", "generated_at", "status", "input_digest", "tool_digest", "body_storage", "summary", "sources"}, "Authority index")
    summary_keys = {"locked_sources", "fetched_digest_matched", "fetched_digest_stale", "fetch_failed", "fetch_deferred", "candidate_surfaces", "root_locators", "fragments_found", "fragments_not_found", "locator_evaluations_deferred", "reference_edges_classified", "unclassified_reference_edges", "authority_text_surfaces_exhaustive", "human_reviewed_surfaces", "core_v2_eligible_surfaces"}
    assert_exact_keys(index["summary"], summary_keys, "Authority summary")
    if index["schema_version"] != 1 or index["atlas_id"] != "flutter-reference-atlas":
        raise AuthorityError("Authority index identityが不正です")
    if index["generated_at"] != GENERATED_AT or index["status"] != "incomplete-human-review-required":
        raise AuthorityError("Authority indexの決定論状態が不正です")
    if index["body_storage"] != "digest-and-locator-offset-only":
        raise AuthorityError("Authority本文保存境界が不正です")
    if index["input_digest"] != inputs["input_digest"] or index["tool_digest"] != inputs["tool_digest"]:
        raise AuthorityError("Authority inputまたはtool sourceがdriftしています")
    expected_files = sorted(f"{item['id']}.json" for item in inputs["sources"])
    actual_files = sorted(path.name for path in (root / OUTPUT_DIR.relative_to(ROOT)).glob("*.json"))
    if actual_files != expected_files:
        raise AuthorityError("Authority artifact集合がSource lockと一致しません")
    index_by_id = {item["id"]: item for item in index["sources"]}
    if len(index_by_id) != len(index["sources"]):
        raise AuthorityError("Authority index Source IDが重複しています")
    counts = {key: 0 for key in ("matched", "stale", "failed", "deferred", "root-document", "fragment-found", "fragment-not-found", "locator-open", "candidate")}
    artifact_keys = {"schema_version", "source_id", "source_url", "locked_source_digest", "source_metadata", "fetch", "extraction", "candidate_surfaces"}
    fetch_keys = {"status", "fetched_digest", "locked_digest_match", "http_status", "final_url", "content_type", "fetched_bytes", "error_digest", "deferred_reason"}
    extraction_keys = {"method", "tool", "tool_digest", "review_status", "body_storage"}
    candidate_keys = {"edge_id", "edge_kind", "source_id", "reference_url", "locator", "candidate_behavior_id", "capability_id", "target_ids", "claim_id", "provisional_surface_id", "classification_basis", "domain_reference_metadata_digest", "locator_status", "context_digest", "context_start", "context_end", "context_unit", "heading_digest", "classification"}
    for source in inputs["sources"]:
        path = root / OUTPUT_DIR.relative_to(ROOT) / f"{source['id']}.json"
        artifact = load_json(path)
        assert_exact_keys(artifact, artifact_keys, f"Authority artifact {source['id']}")
        assert_exact_keys(artifact["source_metadata"], {"title", "kind", "version", "retrieved_at", "license", "redistribution"}, f"Authority source metadata {source['id']}")
        assert_exact_keys(artifact["fetch"], fetch_keys, f"Authority fetch {source['id']}")
        assert_exact_keys(artifact["extraction"], extraction_keys, f"Authority extraction {source['id']}")
        if artifact["source_id"] != source["id"] or artifact["source_url"] != source["url"] or artifact["locked_source_digest"] != source["digest"]:
            raise AuthorityError(f"Authority artifact identityが不正です: {source['id']}")
        expected_metadata = {key: source.get(key) for key in ("title", "kind", "version", "retrieved_at", "license", "redistribution")}
        if artifact["source_metadata"] != expected_metadata:
            raise AuthorityError(f"Authority source metadataがdriftしています: {source['id']}")
        if artifact["extraction"] != {"method": "locked-body-locator-context-digest", "tool": "flutter-reference-atlas-authority-extractor-v1", "tool_digest": inputs["tool_digest"], "review_status": "automated-unreviewed", "body_storage": "digest-and-locator-offset-only"}:
            raise AuthorityError(f"Authority extraction境界が不正です: {source['id']}")
        expected_edges = {item["edge_id"]: item for item in inputs["edges_by_source"][source["id"]]}
        if len(artifact["candidate_surfaces"]) != len(expected_edges):
            raise AuthorityError(f"Authority edge数が不正です: {source['id']}")
        fetch = artifact["fetch"]
        status = fetch["status"]
        if status not in {"matched", "stale", "failed", "deferred"}:
            raise AuthorityError(f"未知fetch statusです: {source['id']}")
        counts[status] += 1
        if status == "matched" and (not fetch["locked_digest_match"] or fetch["fetched_digest"] != source["digest"]):
            raise AuthorityError(f"matched digestが不正です: {source['id']}")
        if status == "stale" and (fetch["locked_digest_match"] or fetch["fetched_digest"] in {None, source["digest"]}):
            raise AuthorityError(f"stale digestが不正です: {source['id']}")
        if status == "failed" and (fetch["fetched_digest"] is not None or fetch["error_digest"] is None):
            raise AuthorityError(f"failed stateが不正です: {source['id']}")
        if status == "deferred" and (fetch["fetched_digest"] is not None or fetch["deferred_reason"] is None):
            raise AuthorityError(f"deferred stateが不正です: {source['id']}")
        locator_statuses: dict[str, int] = {}
        for candidate in artifact["candidate_surfaces"]:
            assert_exact_keys(candidate, candidate_keys, f"Authority candidate {candidate.get('edge_id')}")
            expected = expected_edges.get(candidate["edge_id"])
            if expected is None or any(candidate[key] != value for key, value in expected.items()):
                raise AuthorityError(f"Authority edge metadataがdriftしています: {candidate['edge_id']}")
            if candidate["classification"] != "candidate-included-unreviewed":
                raise AuthorityError(f"Human review未完了を隠せません: {candidate['edge_id']}")
            if not isinstance(candidate["domain_reference_metadata_digest"], str) or not candidate["domain_reference_metadata_digest"].startswith("sha256:") or len(candidate["domain_reference_metadata_digest"]) != 71:
                raise AuthorityError(f"Authority metadata digestが不正です: {candidate['edge_id']}")
            locator_status = candidate["locator_status"]
            expected_deferred = {"stale": "not-evaluated-stale-body", "failed": "not-evaluated-fetch-failed", "deferred": "not-evaluated-policy-deferred"}.get(status)
            if expected_deferred and locator_status != expected_deferred:
                raise AuthorityError(f"Locator deferred境界が不正です: {candidate['edge_id']}")
            located = locator_status in {"root-document", "fragment-found"}
            if located != (candidate["context_digest"] is not None and candidate["context_start"] is not None and candidate["context_end"] is not None and candidate["context_unit"] == "byte"):
                raise AuthorityError(f"Locator offset境界が不正です: {candidate['edge_id']}")
            if candidate["context_digest"] is not None and (not candidate["context_digest"].startswith("sha256:") or len(candidate["context_digest"]) != 71):
                raise AuthorityError(f"Locator context digestが不正です: {candidate['edge_id']}")
            if status == "matched" and locator_status.startswith("not-evaluated-"):
                raise AuthorityError(f"Matched bodyのlocatorが未評価です: {candidate['edge_id']}")
            locator_statuses[locator_status] = locator_statuses.get(locator_status, 0) + 1
            if locator_status in counts:
                counts[locator_status] += 1
            elif locator_status.startswith("not-evaluated-"):
                counts["locator-open"] += 1
            counts["candidate"] += 1
        record = index_by_id.get(source["id"])
        expected_record = {
            "id": source["id"], "path": f"authority/surfaces-draft/{source['id']}.json",
            "digest": canonical_digest(artifact), "fetch_status": status,
            "locked_digest_match": fetch["locked_digest_match"],
            "candidate_surfaces": len(artifact["candidate_surfaces"]),
            "locator_status": dict(sorted(locator_statuses.items())),
        }
        if record != expected_record:
            raise AuthorityError(f"Authority index recordが不正です: {source['id']}")
    expected_summary = {
        "locked_sources": len(inputs["sources"]), "fetched_digest_matched": counts["matched"],
        "fetched_digest_stale": counts["stale"], "fetch_failed": counts["failed"],
        "fetch_deferred": counts["deferred"], "candidate_surfaces": counts["candidate"],
        "root_locators": counts["root-document"], "fragments_found": counts["fragment-found"],
        "fragments_not_found": counts["fragment-not-found"], "locator_evaluations_deferred": counts["locator-open"],
        "reference_edges_classified": counts["candidate"], "unclassified_reference_edges": 0,
        "authority_text_surfaces_exhaustive": False, "human_reviewed_surfaces": 0,
        "core_v2_eligible_surfaces": 0,
    }
    if index["summary"] != expected_summary:
        raise AuthorityError("Authority summaryがArtifact実体と一致しません")
    return index


def main() -> int:
    try:
        index = verify()
    except (OSError, json.JSONDecodeError, AuthorityError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    summary = index["summary"]
    print(f"Authority extraction検証済み: matched={summary['fetched_digest_matched']}/{summary['locked_sources']} stale={summary['fetched_digest_stale']} failed={summary['fetch_failed']} deferred={summary['fetch_deferred']} locator_open={summary['locator_evaluations_deferred']} candidates={summary['candidate_surfaces']} human_reviewed=0 exhaustive=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
