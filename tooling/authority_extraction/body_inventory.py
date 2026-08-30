#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Inventory raw semantic anchors from unique locked authority documents."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tooling.authority_extraction.extract import fetch_source, sha256  # noqa: E402
from tooling.non_regression.audit import WorktreeReader, load_structured  # noqa: E402

INDEX_PATH = ROOT / "authority/body-inventory.snapshot.json"
OUTPUT_DIR = ROOT / "authority/body-inventory-draft"
GENERATED_AT = "2026-08-28T00:00:00+09:00"
SELECTOR_CONTRACT = ["document-root", "h1", "h2", "h3", "h4", "h5", "h6", "dfn", "section", "article", "main", "nav", "aside", "table", "figure"]
TAG_PATTERN = rb"h[1-6]|dfn|section|article|main|nav|aside|table|figure"


class BodyInventoryError(RuntimeError):
    pass


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes())


def tool_digest(root: Path) -> str:
    path = root / "tooling/authority_extraction/body_inventory.py"
    return sha256(b"tooling/authority_extraction/body_inventory.py\0" + path.read_bytes())


def document_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def document_id(url: str) -> str:
    host = (urlsplit(url).hostname or "unknown").removeprefix("www.").replace(".", "-")
    return f"document-{host}-{hashlib.sha256(url.encode()).hexdigest()[:12]}"


def collect_inputs(root: Path) -> dict[str, Any]:
    sources = load_structured(WorktreeReader(root), "sources.lock.yaml")["sources"]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for source in sources:
        grouped.setdefault(document_url(source["url"]), []).append(source)
    documents = []
    for url, entries in grouped.items():
        digests = sorted({entry["digest"] for entry in entries})
        if len(digests) != 1:
            raise BodyInventoryError(f"同一document URLに複数のlocked digestがあります: {url}")
        documents.append({
            "document_id": document_id(url), "fetch_url": url, "locked_digest": digests[0],
            "source_ids": sorted(entry["id"] for entry in entries),
            "fetch_policy_source": {**sorted(entries, key=lambda item: item["id"])[0], "url": url},
        })
    documents.sort(key=lambda item: item["document_id"])
    digest_tool = tool_digest(root)
    digest_docs = [{key: item[key] for key in ("document_id", "fetch_url", "locked_digest", "source_ids")} for item in documents]
    input_digest = sha256(json.dumps({"tool_digest": digest_tool, "source_entries": len(sources), "documents": digest_docs}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
    return {"input_digest": input_digest, "tool_digest": digest_tool, "source_entries": len(sources), "documents": documents}


def mask_ignored(body: bytes) -> bytes:
    pattern = re.compile(rb"<!--[\s\S]*?-->|<script\b[\s\S]*?</script\s*>|<style\b[\s\S]*?</style\s*>", re.IGNORECASE)
    return pattern.sub(lambda match: b" " * len(match.group(0)), body)


def attribute_value(attributes: bytes, name: bytes) -> bytes | None:
    match = re.search(rb"(?:^|\s)" + re.escape(name) + rb"\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))", attributes, re.IGNORECASE)
    if not match:
        return None
    return next((value for value in match.groups() if value is not None), None)


def label_digest(inner: bytes) -> str | None:
    value = re.sub(rb"<[^>]+>", b" ", inner).decode("utf-8", errors="replace")
    value = " ".join(html.unescape(value).split())
    return sha256(value.encode()) if value else None


def kind_for(tag: str) -> str:
    if re.fullmatch(r"h[1-6]", tag):
        return "heading"
    return {"dfn": "definition", "section": "section", "table": "data-table", "figure": "figure"}.get(tag, "landmark")


def extract_anchors(body: bytes, exact_digest: str, doc_id: str) -> list[dict[str, Any]]:
    masked = mask_ignored(body)
    raw = []
    matcher = re.compile(rb"<(" + TAG_PATTERN + rb")\b([^>]*)>", re.IGNORECASE)
    for match in matcher.finditer(masked):
        tag = match.group(1).decode().lower()
        start, open_end = match.start(), match.end()
        close = re.search(rb"</" + tag.encode() + rb"\s*>", masked[open_end:], re.IGNORECASE)
        inner_end = open_end + close.start() if close else min(len(body), open_end + 4096)
        end = open_end + close.end() if close else open_end
        fragment = attribute_value(match.group(2), b"id") or attribute_value(match.group(2), b"name")
        digest_label = None
        if re.fullmatch(r"h[1-6]", tag) or tag == "dfn":
            inner = body[open_end:inner_end]
            if fragment is None:
                fragment = attribute_value(inner[:4096], b"id") or attribute_value(inner[:4096], b"name")
            digest_label = label_digest(inner)
        raw.append({"tag": tag, "start": start, "end": end, "fragment": fragment, "label_digest": digest_label, "level": int(tag[1]) if re.fullmatch(r"h[1-6]", tag) else None})
    root_id = "anchor-root-" + hashlib.sha256(f"{doc_id}\0{exact_digest}".encode()).hexdigest()[:20]
    anchors = [{
        "id": root_id, "locator": "document-root", "locator_kind": "document-root",
        "semantic_kind": "document-root", "tag": "document", "heading_level": None,
        "parent_anchor_id": None, "context_start": 0, "context_end": len(body),
        "context_unit": "utf8-byte", "context_digest": exact_digest, "label_digest": None,
        "classification_status": "pending-human", "human_decision_id": None,
        "surface_ids": [], "atomic_behavior_ids": [],
    }]
    heading_stack: dict[int, str] = {}
    for item in raw:
        fragment = item["fragment"]
        locator = "#" + fragment.decode("utf-8", errors="replace") if fragment else f"offset:utf8-byte:{item['start']}"
        locator_kind = "fragment" if fragment else "locked-body-offset"
        parent = root_id
        search_levels = range(item["level"] - 1, 0, -1) if item["level"] else range(6, 0, -1)
        for level in search_levels:
            if level in heading_stack:
                parent = heading_stack[level]
                break
        anchor_id = "anchor-" + hashlib.sha256(f"{doc_id}\0{exact_digest}\0{item['tag']}\0{locator}\0{item['start']}".encode()).hexdigest()[:20]
        context_start = max(0, item["start"] - 1024)
        context_end = min(len(body), max(item["end"], item["start"] + 1) + 4096)
        anchors.append({
            "id": anchor_id, "locator": locator, "locator_kind": locator_kind,
            "semantic_kind": kind_for(item["tag"]), "tag": item["tag"], "heading_level": item["level"],
            "parent_anchor_id": parent, "context_start": context_start, "context_end": context_end,
            "context_unit": "utf8-byte", "context_digest": sha256(body[context_start:context_end]),
            "label_digest": item["label_digest"], "classification_status": "pending-human",
            "human_decision_id": None, "surface_ids": [], "atomic_behavior_ids": [],
        })
        if item["level"]:
            heading_stack[item["level"]] = anchor_id
            for deeper in range(item["level"] + 1, 7):
                heading_stack.pop(deeper, None)
    return anchors


def anchor_counts(anchors: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(item["semantic_kind"] for item in anchors).items()))


def artifact_digest(value: dict[str, Any]) -> str:
    return sha256((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def artifact_for(item: dict[str, Any], fetch: dict[str, Any], body: bytes | None, digest_tool: str) -> dict[str, Any]:
    matched = fetch["status"] == "matched" and body is not None
    anchors = extract_anchors(body, fetch["fetched_digest"], item["document_id"]) if matched else []
    return {
        "schema_version": 1, "document_id": item["document_id"], "fetch_url": item["fetch_url"],
        "source_ids": item["source_ids"], "locked_body_digest": item["locked_digest"], "fetch": fetch,
        "extraction": {
            "method": "html-semantic-anchor-selector-v1", "tool": "flutter-reference-atlas-authority-body-inventory-v1",
            "tool_digest": digest_tool, "selector_contract": SELECTOR_CONTRACT,
            "selector_exhaustive_for_locked_body": matched, "authority_semantics_exhaustive": False,
            "review_status": "automated-unreviewed", "body_storage": "digest-locator-and-offset-only",
        },
        "anchors": anchors,
    }


def generate(root: Path = ROOT) -> dict[str, Any]:
    inputs = collect_inputs(root)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    artifacts = []
    for item in inputs["documents"]:
        fetch, body = fetch_source(item["fetch_policy_source"])
        artifacts.append(artifact_for(item, fetch, body, inputs["tool_digest"]))
    for artifact in artifacts:
        (OUTPUT_DIR / f"{artifact['document_id']}.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    anchors = [anchor for artifact in artifacts for anchor in artifact["anchors"]]
    counts = Counter(artifact["fetch"]["status"] for artifact in artifacts)
    index = {
        "schema_version": 1, "atlas_id": "flutter-reference-atlas", "generated_at": GENERATED_AT,
        "status": "incomplete-human-review-required", "input_digest": inputs["input_digest"],
        "tool_digest": inputs["tool_digest"], "body_storage": "digest-locator-and-offset-only",
        "selector_contract": SELECTOR_CONTRACT,
        "summary": {
            "source_entries": inputs["source_entries"], "unique_documents": len(artifacts),
            "matched_documents": counts["matched"], "stale_documents": counts["stale"],
            "failed_documents": counts["failed"], "deferred_documents": counts["deferred"],
            "selector_exhaustive_documents": counts["matched"], "raw_anchors": len(anchors),
            "anchors_by_kind": anchor_counts(anchors), "pending_human_anchors": len(anchors),
            "human_decided_anchors": 0, "promoted_surface_anchors": 0,
            "promoted_atomic_behavior_anchors": 0, "core_v2_eligible_artifacts": 0,
            "raw_anchors_count_as_semantic_surfaces": False, "authority_semantics_exhaustive": False,
        },
        "documents": [{
            "id": artifact["document_id"], "path": f"authority/body-inventory-draft/{artifact['document_id']}.json",
            "digest": artifact_digest(artifact), "fetch_status": artifact["fetch"]["status"],
            "source_entries": len(artifact["source_ids"]), "raw_anchors": len(artifact["anchors"]),
            "anchors_by_kind": anchor_counts(artifact["anchors"]),
        } for artifact in artifacts],
    }
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    index = generate()
    summary = index["summary"]
    print(f"Authority body inventory: matched={summary['matched_documents']}/{summary['unique_documents']} stale={summary['stale_documents']} failed={summary['failed_documents']} deferred={summary['deferred_documents']} raw_anchors={summary['raw_anchors']} pending_human={summary['pending_human_anchors']} semantic_surface_credit=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
