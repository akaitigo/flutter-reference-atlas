#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reproduce locked authority bodies without storing third-party prose."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tooling.non_regression.audit import WorktreeReader, load_structured  # noqa: E402

OUTPUT_DIR = ROOT / "authority/surfaces-draft"
INDEX_PATH = ROOT / "authority/extraction.snapshot.json"
MAX_BODY_BYTES = 32 * 1024 * 1024
GENERATED_AT = "2026-08-28T00:00:00+09:00"


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical_digest(value: Any) -> str:
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    return sha256(data)


def tool_digest(root: Path) -> str:
    path = root / "tooling/authority_extraction/extract.py"
    return sha256(b"tooling/authority_extraction/extract.py\0" + path.read_bytes())


def locator_for(url: str) -> str:
    fragment = urlparse(url).fragment
    return f"#{fragment}" if fragment else "document-root"


def locate(body: bytes, url: str, exact_digest: str) -> dict[str, Any]:
    fragment = urlparse(url).fragment
    if not fragment:
        return {
            "locator_status": "root-document",
            "context_digest": exact_digest,
            "context_start": 0,
            "context_end": len(body),
            "context_unit": "byte",
            "heading_digest": None,
        }
    alternatives = sorted({fragment, unquote(fragment)})
    position = -1
    for alternative in alternatives:
        escaped = re.escape(alternative.encode())
        match = re.search(rb"(?:id|name)\s*=\s*(?:[\"']" + escaped + rb"[\"']|" + escaped + rb"(?=[\s>]))", body, re.IGNORECASE)
        if match:
            position = match.start()
            break
    if position < 0:
        return {
            "locator_status": "fragment-not-found",
            "context_digest": None,
            "context_start": None,
            "context_end": None,
            "context_unit": None,
            "heading_digest": None,
        }
    start = max(0, position - 4096)
    end = min(len(body), position + 32768)
    return {
        "locator_status": "fragment-found",
        "context_digest": sha256(body[start:end]),
        "context_start": start,
        "context_end": end,
        "context_unit": "byte",
        "heading_digest": None,
    }


def metadata_digest(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def collect_inputs(root: Path) -> dict[str, Any]:
    sources_doc = load_structured(WorktreeReader(root), "sources.lock.yaml")
    claims = json.loads((root / "atlas/claims/index.json").read_text(encoding="utf-8"))["claims"]
    capabilities = json.loads((root / "atlas/capabilities/index.json").read_text(encoding="utf-8"))["capabilities"]
    surfaces = json.loads((root / "definitive/requirements.json").read_text(encoding="utf-8"))["surfaces"]
    capability_by_id = {item["id"]: item for item in capabilities}
    edges_by_source: dict[str, list[dict[str, Any]]] = {item["id"]: [] for item in sources_doc["sources"]}
    for claim in claims:
        capability = capability_by_id[claim["capability_id"]]
        for source_id in claim["authority_ids"]:
            source = next(item for item in sources_doc["sources"] if item["id"] == source_id)
            edges_by_source[source_id].append({
                "edge_id": f"edge.claim.{claim['id']}.{source_id}",
                "edge_kind": "claim-authority",
                "source_id": source_id,
                "reference_url": source["url"],
                "locator": locator_for(source["url"]),
                "candidate_behavior_id": f"candidate.claim.{claim['id']}.{source_id}",
                "capability_id": claim["capability_id"],
                "target_ids": sorted(capability["target_ids"]),
                "claim_id": claim["id"],
                "provisional_surface_id": None,
                "classification_basis": "existing-contract-projection-unreviewed",
                "domain_reference_metadata_digest": metadata_digest({
                    "acceptance": claim["acceptance"], "lab_id": claim["lab_id"], "test_id": claim["test_id"]
                }),
            })
    for surface in surfaces:
        for source_id in surface["authority_ids"]:
            source = next(item for item in sources_doc["sources"] if item["id"] == source_id)
            edges_by_source[source_id].append({
                "edge_id": f"edge.provisional-surface.{surface['id']}.{source_id}",
                "edge_kind": "provisional-surface-authority",
                "source_id": source_id,
                "reference_url": source["url"],
                "locator": locator_for(source["url"]),
                "candidate_behavior_id": f"candidate.provisional-surface.{surface['id']}.{source_id}",
                "capability_id": None,
                "target_ids": [],
                "claim_id": None,
                "provisional_surface_id": surface["id"],
                "classification_basis": "existing-contract-projection-unreviewed",
                "domain_reference_metadata_digest": metadata_digest({
                    "capability": surface["capability"], "domain": surface["domain"], "title": surface["title"]
                }),
            })
    for edges in edges_by_source.values():
        edges.sort(key=lambda item: item["edge_id"])
    sources = sorted(sources_doc["sources"], key=lambda item: item["id"])
    digest_tool = tool_digest(root)
    digest_input = {
        "tool_digest": digest_tool,
        "sources": [{key: item.get(key) for key in ("id", "kind", "url", "version", "digest", "redistribution")} for item in sources],
        "edges_by_source": edges_by_source,
    }
    return {"input_digest": metadata_digest(digest_input), "tool_digest": digest_tool, "sources": sources, "edges_by_source": edges_by_source}


def deferred_reason(source: dict[str, Any]) -> str | None:
    parsed = urlparse(source["url"])
    if parsed.path.endswith(".zip"):
        return "binary-distribution-over-body-limit"
    if source["kind"] == "runtime-inventory":
        return "repository-owned-runtime-record-not-remote-authority-body"
    if parsed.hostname == "hub.docker.com":
        return "registry-page-not-versioned-authority-body"
    return None


def fetch_source(source: dict[str, Any]) -> tuple[dict[str, Any], bytes | None]:
    reason = deferred_reason(source)
    if reason:
        return ({
            "status": "deferred", "fetched_digest": None, "locked_digest_match": False,
            "http_status": None, "final_url": None, "content_type": None,
            "fetched_bytes": None, "error_digest": None, "deferred_reason": reason,
        }, None)
    request = urllib.request.Request(source["url"], headers={
        "User-Agent": "flutter-reference-atlas-authority-extractor/1.0",
        "Accept": "text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.1",
    })
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            length = response.headers.get("Content-Length")
            if length is not None and int(length) > MAX_BODY_BYTES:
                return ({
                    "status": "deferred", "fetched_digest": None, "locked_digest_match": False,
                    "http_status": response.status, "final_url": response.url,
                    "content_type": response.headers.get("Content-Type"), "fetched_bytes": None,
                    "error_digest": None, "deferred_reason": "response-over-body-limit",
                }, None)
            body = response.read(MAX_BODY_BYTES + 1)
            if len(body) > MAX_BODY_BYTES:
                return ({
                    "status": "deferred", "fetched_digest": None, "locked_digest_match": False,
                    "http_status": response.status, "final_url": response.url,
                    "content_type": response.headers.get("Content-Type"), "fetched_bytes": None,
                    "error_digest": None, "deferred_reason": "response-over-body-limit",
                }, None)
            fetched_digest = sha256(body)
            matched = fetched_digest == source["digest"]
            return ({
                "status": "matched" if matched else "stale", "fetched_digest": fetched_digest,
                "locked_digest_match": matched, "http_status": response.status,
                "final_url": response.url, "content_type": response.headers.get("Content-Type"),
                "fetched_bytes": len(body), "error_digest": None, "deferred_reason": None,
            }, body)
    except Exception as error:  # Network failures are evidence state, not stored prose.
        status = error.code if isinstance(error, urllib.error.HTTPError) else None
        return ({
            "status": "failed", "fetched_digest": None, "locked_digest_match": False,
            "http_status": status, "final_url": None, "content_type": None,
            "fetched_bytes": None, "error_digest": sha256(type(error).__name__.encode()),
            "deferred_reason": None,
        }, None)


def artifact_for(source: dict[str, Any], edges: list[dict[str, Any]], fetch: dict[str, Any], body: bytes | None, digest_tool: str) -> dict[str, Any]:
    locator_results = []
    for edge in edges:
        if fetch["status"] == "matched" and body is not None:
            locator_results.append(locate(body, edge["reference_url"], fetch["fetched_digest"]))
        else:
            suffix = {"stale": "stale-body", "failed": "fetch-failed", "deferred": "policy-deferred"}[fetch["status"]]
            locator_results.append({
                "locator_status": f"not-evaluated-{suffix}", "context_digest": None,
                "context_start": None, "context_end": None, "context_unit": None, "heading_digest": None,
            })
    return {
        "schema_version": 1,
        "source_id": source["id"],
        "source_url": source["url"],
        "locked_source_digest": source["digest"],
        "source_metadata": {key: source.get(key) for key in ("title", "kind", "version", "retrieved_at", "license", "redistribution")},
        "fetch": fetch,
        "extraction": {
            "method": "locked-body-locator-context-digest",
            "tool": "flutter-reference-atlas-authority-extractor-v1",
            "tool_digest": digest_tool,
            "review_status": "automated-unreviewed",
            "body_storage": "digest-and-locator-offset-only",
        },
        "candidate_surfaces": [
            {**edge, **locator_results[index], "classification": "candidate-included-unreviewed"}
            for index, edge in enumerate(edges)
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    inputs = collect_inputs(ROOT)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        fetched = list(executor.map(fetch_source, inputs["sources"]))
    artifacts = [
        artifact_for(source, inputs["edges_by_source"][source["id"]], fetch, body, inputs["tool_digest"])
        for source, (fetch, body) in zip(inputs["sources"], fetched)
    ]
    for artifact in artifacts:
        path = OUTPUT_DIR / f"{artifact['source_id']}.json"
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    candidates = [candidate for artifact in artifacts for candidate in artifact["candidate_surfaces"]]
    count_fetch = lambda value: sum(item["fetch"]["status"] == value for item in artifacts)
    count_locator = lambda value: sum(item["locator_status"] == value for item in candidates)
    index = {
        "schema_version": 1,
        "atlas_id": "flutter-reference-atlas",
        "generated_at": GENERATED_AT,
        "status": "incomplete-human-review-required",
        "input_digest": inputs["input_digest"],
        "tool_digest": inputs["tool_digest"],
        "body_storage": "digest-and-locator-offset-only",
        "summary": {
            "locked_sources": len(artifacts),
            "fetched_digest_matched": count_fetch("matched"),
            "fetched_digest_stale": count_fetch("stale"),
            "fetch_failed": count_fetch("failed"),
            "fetch_deferred": count_fetch("deferred"),
            "candidate_surfaces": len(candidates),
            "root_locators": count_locator("root-document"),
            "fragments_found": count_locator("fragment-found"),
            "fragments_not_found": count_locator("fragment-not-found"),
            "locator_evaluations_deferred": sum(item["locator_status"].startswith("not-evaluated-") for item in candidates),
            "reference_edges_classified": len(candidates),
            "unclassified_reference_edges": 0,
            "authority_text_surfaces_exhaustive": False,
            "human_reviewed_surfaces": 0,
            "core_v2_eligible_surfaces": 0,
        },
        "sources": [{
            "id": artifact["source_id"],
            "path": f"authority/surfaces-draft/{artifact['source_id']}.json",
            "digest": canonical_digest(artifact),
            "fetch_status": artifact["fetch"]["status"],
            "locked_digest_match": artifact["fetch"]["locked_digest_match"],
            "candidate_surfaces": len(artifact["candidate_surfaces"]),
            "locator_status": {status: sum(item["locator_status"] == status for item in artifact["candidate_surfaces"]) for status in sorted({item["locator_status"] for item in artifact["candidate_surfaces"]})},
        } for artifact in artifacts],
    }
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = index["summary"]
    print(f"Authority extraction snapshot: matched={summary['fetched_digest_matched']}/{summary['locked_sources']} stale={summary['fetched_digest_stale']} failed={summary['fetch_failed']} deferred={summary['fetch_deferred']} locator_open={summary['locator_evaluations_deferred']} candidates={summary['candidate_surfaces']} human_reviewed=0 exhaustive=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
