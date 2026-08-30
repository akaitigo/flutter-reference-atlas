import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import {
  authorityAnchorCounts,
  authorityBodyInventoryDirectory,
  authorityBodyInventoryIndexPath,
  authorityBodySelectorContract,
  collectAuthorityBodyInventoryInputs,
  digestAuthorityBodyArtifact,
  extractAuthorityBodyAnchors,
  type AuthorityBodyInventoryArtifact,
  type AuthorityBodyInventoryIndex,
} from "./lib/authority-body-inventory";
import { sha256 } from "./lib/authority-extraction";

const root = process.cwd();
const inputs = await collectAuthorityBodyInventoryInputs(root);
await mkdir(path.join(root, authorityBodyInventoryDirectory), { recursive: true });

const artifacts: AuthorityBodyInventoryArtifact[] = [];
let cursor = 0;
async function worker(): Promise<void> {
  while (cursor < inputs.documents.length) {
    const input = inputs.documents[cursor++]!;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 60_000);
    let fetchRecord: AuthorityBodyInventoryArtifact["fetch"];
    let anchors: AuthorityBodyInventoryArtifact["anchors"] = [];
    try {
      const response = await fetch(input.fetch_url, {
        redirect: "follow",
        signal: controller.signal,
        headers: {
          "user-agent": "frontend-behavior-atlas-authority-body-inventory/1.0 (+https://github.com/akaitigo/frontend-behavior-atlas)",
          accept: "text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.2",
        },
      });
      const bytes = Buffer.from(await response.arrayBuffer());
      if (!response.ok || bytes.byteLength === 0) throw new Error(`HTTP ${response.status} bytes ${bytes.byteLength}`);
      const exactDigest = sha256(bytes);
      const matched = exactDigest === input.locked_digest;
      fetchRecord = {
        status: matched ? "matched" : "stale",
        fetched_digest: exactDigest,
        locked_digest_match: matched,
        http_status: response.status,
        final_url: response.url,
        content_type: response.headers.get("content-type"),
        fetched_bytes: bytes.byteLength,
        error_digest: null,
      };
      if (matched) anchors = extractAuthorityBodyAnchors(bytes.toString("utf8"), exactDigest, input.document_id);
    } catch (error) {
      fetchRecord = {
        status: "failed",
        fetched_digest: null,
        locked_digest_match: false,
        http_status: null,
        final_url: null,
        content_type: null,
        fetched_bytes: null,
        error_digest: sha256(String(error)),
      };
    } finally {
      clearTimeout(timer);
    }
    const artifact: AuthorityBodyInventoryArtifact = {
      schema_version: 1,
      document_id: input.document_id,
      fetch_url: input.fetch_url,
      source_ids: input.source_ids,
      locked_body_digest: input.locked_digest,
      fetch: fetchRecord,
      extraction: {
        method: "html-semantic-anchor-selector-v1",
        tool: "frontend-behavior-atlas-authority-body-inventory-v1",
        tool_digest: inputs.tool_digest,
        selector_contract: [...authorityBodySelectorContract],
        selector_exhaustive_for_locked_body: fetchRecord.status === "matched",
        authority_semantics_exhaustive: false,
        review_status: "automated-unreviewed",
        body_storage: "digest-locator-and-offset-only",
      },
      anchors,
    };
    artifacts.push(artifact);
    await writeFile(path.join(root, authorityBodyInventoryDirectory, `${input.document_id}.json`), `${JSON.stringify(artifact, null, 2)}\n`);
    process.stdout.write(`inventoried ${artifacts.length}/${inputs.documents.length} ${input.document_id} ${fetchRecord.status} anchors=${anchors.length}\n`);
  }
}

await Promise.all(Array.from({ length: Math.min(4, inputs.documents.length) }, () => worker()));
artifacts.sort((left, right) => left.document_id.localeCompare(right.document_id));
const anchors = artifacts.flatMap((artifact) => artifact.anchors);
const counts: Record<string, number> = {};
for (const artifact of artifacts) for (const [kind, count] of Object.entries(authorityAnchorCounts(artifact.anchors))) counts[kind] = (counts[kind] ?? 0) + count;
const anchorsByKind = Object.fromEntries(Object.entries(counts).sort(([left], [right]) => left.localeCompare(right)));
const index: AuthorityBodyInventoryIndex = {
  schema_version: 1,
  atlas_id: "frontend-behavior-atlas",
  generated_at: "2026-08-28T00:00:00+09:00",
  status: "incomplete-human-review-required",
  input_digest: inputs.input_digest,
  tool_digest: inputs.tool_digest,
  body_storage: "digest-locator-and-offset-only",
  selector_contract: [...authorityBodySelectorContract],
  summary: {
    source_entries: inputs.source_entries,
    unique_documents: inputs.documents.length,
    matched_documents: artifacts.filter((artifact) => artifact.fetch.status === "matched").length,
    stale_documents: artifacts.filter((artifact) => artifact.fetch.status === "stale").length,
    failed_documents: artifacts.filter((artifact) => artifact.fetch.status === "failed").length,
    selector_exhaustive_documents: artifacts.filter((artifact) => artifact.extraction.selector_exhaustive_for_locked_body).length,
    anchors: anchors.length,
    anchors_by_kind: anchorsByKind,
    classified_anchors: 0,
    unclassified_anchors: anchors.length,
    human_reviewed_anchors: 0,
    core_v2_eligible_artifacts: 0,
    authority_semantics_exhaustive: false,
  },
  documents: artifacts.map((artifact) => ({
    id: artifact.document_id,
    path: `${authorityBodyInventoryDirectory}/${artifact.document_id}.json`,
    digest: digestAuthorityBodyArtifact(artifact),
    fetch_status: artifact.fetch.status,
    source_entries: artifact.source_ids.length,
    anchors: artifact.anchors.length,
    anchors_by_kind: authorityAnchorCounts(artifact.anchors),
  })),
};
await writeFile(path.join(root, authorityBodyInventoryIndexPath), `${JSON.stringify(index, null, 2)}\n`);
console.log(`Authority body inventory snapshot: ${index.summary.matched_documents}/${index.summary.unique_documents} documents matched, ${index.summary.anchors} selector anchors, ${index.summary.unclassified_anchors} unclassified, 0 human-reviewed.`);
