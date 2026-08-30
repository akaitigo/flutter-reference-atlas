import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import {
  authorityExtractionDirectory,
  authorityExtractionIndexPath,
  collectAuthorityExtractionInputs,
  digestAuthorityArtifact,
  sha256,
  type AuthorityExtractionIndex,
  type AuthoritySurfaceArtifact,
  type LocatorResult,
} from "./lib/authority-extraction";

const root = process.cwd();
const inputs = await collectAuthorityExtractionInputs(root);
await mkdir(path.join(root, authorityExtractionDirectory), { recursive: true });

const decodeEntities = (value: string): string => value
  .replace(/<[^>]+>/g, " ")
  .replace(/&(?:nbsp|#160);/gi, " ")
  .replace(/&lt;/gi, "<")
  .replace(/&gt;/gi, ">")
  .replace(/&amp;/gi, "&")
  .replace(/&quot;/gi, '"')
  .replace(/&#39;|&apos;/gi, "'")
  .replace(/\s+/g, " ")
  .trim();
const escapeRegex = (value: string): string => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function safeDecode(value: string): string {
  try { return decodeURIComponent(value); } catch { return value; }
}

function locate(body: string, referenceUrl: string, exactBodyDigest: string): LocatorResult {
  const rawFragment = new URL(referenceUrl).hash.slice(1);
  if (!rawFragment) return {
    locator_status: "root-document",
    context_digest: exactBodyDigest,
    context_start: 0,
    context_end: body.length,
    context_unit: "utf16-code-unit",
    heading_digest: null,
  };
  const fragments = [...new Set([rawFragment, safeDecode(rawFragment)])];
  let index = -1;
  for (const fragment of fragments) {
    const escaped = escapeRegex(fragment);
    const matcher = new RegExp(`(?:id|name)\\s*=\\s*(?:["']${escaped}["']|${escaped}(?=[\\s>]))`, "i");
    const match = matcher.exec(body);
    if (match) { index = match.index; break; }
  }
  if (index < 0) return {
    locator_status: "fragment-not-found",
    context_digest: null,
    context_start: null,
    context_end: null,
    context_unit: null,
    heading_digest: null,
  };
  const start = Math.max(0, index - 4096);
  const end = Math.min(body.length, index + 32768);
  const context = body.slice(start, end);
  const preceding = body.slice(Math.max(0, index - 16384), index);
  const headings = [...preceding.matchAll(/<h[1-6][^>]*>([\s\S]*?)<\/h[1-6]>/gi)];
  const heading = headings.length > 0 ? decodeEntities(headings.at(-1)![1] ?? "").slice(0, 240) || null : null;
  return {
    locator_status: "fragment-found",
    context_digest: sha256(context),
    context_start: start,
    context_end: end,
    context_unit: "utf16-code-unit",
    heading_digest: heading === null ? null : sha256(heading),
  };
}

const artifacts: AuthoritySurfaceArtifact[] = [];
let cursor = 0;
async function worker(): Promise<void> {
  while (cursor < inputs.locked_sources.length) {
    const source = inputs.locked_sources[cursor++]!;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 60_000);
    let fetchRecord: AuthoritySurfaceArtifact["fetch"];
    let locatorResults: LocatorResult[];
    try {
      const response = await fetch(source.url, {
        redirect: "follow",
        signal: controller.signal,
        headers: {
          "user-agent": "frontend-behavior-atlas-authority-extractor/1.0 (+https://github.com/akaitigo/frontend-behavior-atlas)",
          accept: "text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.2",
        },
      });
      const bytes = Buffer.from(await response.arrayBuffer());
      if (!response.ok || bytes.byteLength === 0) throw new Error(`HTTP ${response.status} bytes ${bytes.byteLength}`);
      const exactDigest = sha256(bytes);
      const matched = exactDigest === source.digest;
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
      const body = bytes.toString("utf8");
      locatorResults = (inputs.edges_by_source[source.id] ?? []).map((edge) => matched
        ? locate(body, edge.reference_url, exactDigest)
        : { locator_status: "not-evaluated-stale-body", context_digest: null, context_start: null, context_end: null, context_unit: null, heading_digest: null });
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
      locatorResults = (inputs.edges_by_source[source.id] ?? []).map(() => ({
        locator_status: "not-evaluated-fetch-failed",
        context_digest: null,
        context_start: null,
        context_end: null,
        context_unit: null,
        heading_digest: null,
      }));
    } finally {
      clearTimeout(timer);
    }
    const artifact: AuthoritySurfaceArtifact = {
      schema_version: 1,
      source_id: source.id,
      source_url: source.url,
      locked_source_digest: source.digest,
      fetch: fetchRecord,
      extraction: {
        method: "locked-body-locator-context-digest",
        tool: "frontend-behavior-atlas-authority-extractor-v1",
        tool_digest: inputs.tool_digest,
        review_status: "automated-unreviewed",
        body_storage: "digest-and-locator-context-digest-only",
      },
      candidate_surfaces: (inputs.edges_by_source[source.id] ?? []).map((edge, index) => ({
        ...edge,
        ...locatorResults[index]!,
        classification: "candidate-included-unreviewed",
      })),
    };
    artifacts.push(artifact);
    await writeFile(path.join(root, authorityExtractionDirectory, `${source.id}.json`), `${JSON.stringify(artifact, null, 2)}\n`);
    process.stdout.write(`extracted ${artifacts.length}/${inputs.locked_sources.length} ${source.id} ${fetchRecord.status}\n`);
  }
}

await Promise.all(Array.from({ length: Math.min(6, inputs.locked_sources.length) }, () => worker()));
artifacts.sort((left, right) => left.source_id.localeCompare(right.source_id));
const statusCount = (status: string): number => artifacts.filter((artifact) => artifact.fetch.status === status).length;
const candidates = artifacts.flatMap((artifact) => artifact.candidate_surfaces);
const locatorCount = (status: string): number => candidates.filter((candidate) => candidate.locator_status === status).length;
const sources = artifacts.map((artifact) => {
  const statuses = [...new Set(artifact.candidate_surfaces.map((candidate) => candidate.locator_status))].sort();
  return {
    id: artifact.source_id,
    path: `${authorityExtractionDirectory}/${artifact.source_id}.json`,
    digest: digestAuthorityArtifact(artifact),
    locked_digest_match: artifact.fetch.locked_digest_match,
    candidate_surfaces: artifact.candidate_surfaces.length,
    locator_status: Object.fromEntries(statuses.map((status) => [status, artifact.candidate_surfaces.filter((candidate) => candidate.locator_status === status).length])),
  };
});
const index: AuthorityExtractionIndex = {
  schema_version: 1,
  atlas_id: "frontend-behavior-atlas",
  generated_at: "2026-08-28T00:00:00+09:00",
  status: "incomplete-human-review-required",
  input_digest: inputs.input_digest,
  tool_digest: inputs.tool_digest,
  body_storage: "digest-and-locator-context-digest-only",
  summary: {
    locked_sources: inputs.locked_sources.length,
    fetched_digest_matched: statusCount("matched"),
    fetched_digest_stale: statusCount("stale"),
    fetch_failed: statusCount("failed"),
    candidate_surfaces: candidates.length,
    root_locators: locatorCount("root-document"),
    fragments_found: locatorCount("fragment-found"),
    fragments_not_found: locatorCount("fragment-not-found"),
    locator_evaluations_deferred: locatorCount("not-evaluated-stale-body") + locatorCount("not-evaluated-fetch-failed"),
    reference_edges_classified: candidates.length,
    unclassified_reference_edges: 0,
    authority_text_surfaces_exhaustive: false,
    human_reviewed_surfaces: 0,
    core_v2_eligible_surfaces: 0,
  },
  sources,
};
await writeFile(path.join(root, authorityExtractionIndexPath), `${JSON.stringify(index, null, 2)}\n`);
console.log(`Authority extraction snapshot: ${index.summary.fetched_digest_matched}/${index.summary.locked_sources} bodies matched, ${index.summary.fragments_found} fragments found, ${index.summary.fragments_not_found} fragments missing, ${index.summary.locator_evaluations_deferred} locator evaluations deferred, ${index.summary.candidate_surfaces} unreviewed candidates.`);
