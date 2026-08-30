import { createHash } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { loadRegistry } from "./registry";

export const authorityExtractionIndexPath = "authority/extraction.snapshot.json";
export const authorityExtractionDirectory = "authority/surfaces-draft";

type LockedSource = {
  title: string;
  url: string;
  kind: string;
  retrieved_at: string;
  status: number;
  final_url: string;
  content_type: string | null;
  size_bytes: number;
  digest: string;
};

export type AuthorityEdge = {
  edge_id: string;
  source_id: string;
  reference_url: string;
  locator: string;
  pattern_id: string;
  pattern_kind: string;
  candidate_behavior_id: string;
  capability_id: string;
  target_id: string;
  claim_id: string;
  variant_ids: string[];
  surface_ids: string[];
  classification_basis: "domain-contract-projection-unreviewed";
  domain_reference_metadata_digest: string;
};

export type AuthorityExtractionInputs = {
  input_digest: string;
  tool_digest: string;
  locked_sources: Array<LockedSource & { id: string }>;
  edges_by_source: Record<string, AuthorityEdge[]>;
};

export type LocatorResult = {
  locator_status: "root-document" | "fragment-found" | "fragment-not-found" | "not-evaluated-stale-body" | "not-evaluated-fetch-failed";
  context_digest: string | null;
  context_start: number | null;
  context_end: number | null;
  context_unit: "utf16-code-unit" | null;
  heading_digest: string | null;
};

export type AuthoritySurfaceArtifact = {
  schema_version: 1;
  source_id: string;
  source_url: string;
  locked_source_digest: string;
  fetch: {
    status: "matched" | "stale" | "failed";
    fetched_digest: string | null;
    locked_digest_match: boolean;
    http_status: number | null;
    final_url: string | null;
    content_type: string | null;
    fetched_bytes: number | null;
    error_digest: string | null;
  };
  extraction: {
    method: "locked-body-locator-context-digest";
    tool: "frontend-behavior-atlas-authority-extractor-v1";
    tool_digest: string;
    review_status: "automated-unreviewed";
    body_storage: "digest-and-locator-context-digest-only";
  };
  candidate_surfaces: Array<AuthorityEdge & LocatorResult & { classification: "candidate-included-unreviewed" }>;
};

export type AuthorityExtractionIndex = {
  schema_version: 1;
  atlas_id: "frontend-behavior-atlas";
  generated_at: "2026-08-28T00:00:00+09:00";
  status: "incomplete-human-review-required";
  input_digest: string;
  tool_digest: string;
  body_storage: "digest-and-locator-context-digest-only";
  summary: {
    locked_sources: number;
    fetched_digest_matched: number;
    fetched_digest_stale: number;
    fetch_failed: number;
    candidate_surfaces: number;
    root_locators: number;
    fragments_found: number;
    fragments_not_found: number;
    locator_evaluations_deferred: number;
    reference_edges_classified: number;
    unclassified_reference_edges: number;
    authority_text_surfaces_exhaustive: false;
    human_reviewed_surfaces: 0;
    core_v2_eligible_surfaces: 0;
  };
  sources: Array<{
    id: string;
    path: string;
    digest: string;
    locked_digest_match: boolean;
    candidate_surfaces: number;
    locator_status: Record<string, number>;
  }>;
};

export const sha256 = (value: string | Buffer): string => `sha256:${createHash("sha256").update(value).digest("hex")}`;
const dotted = (value: string): string => value.replaceAll("/", ".");

export function authoritySourceId(url: string): string {
  const host = new URL(url).hostname.replace(/^www\./, "").replaceAll(".", "-");
  return `${host}-${sha256(url).slice("sha256:".length, "sha256:".length + 10)}`;
}

export async function authorityExtractionToolDigest(root: string): Promise<string> {
  const files = ["scripts/lib/authority-extraction.ts", "scripts/extract-authority-surfaces.ts"];
  const contents = await Promise.all(files.map(async (file) => `${file}\0${await readFile(path.join(root, file), "utf8")}`));
  return sha256(contents.join("\0"));
}

function inferredSurfaceIds(pattern: Awaited<ReturnType<typeof loadRegistry>>["patterns"][number], rationale: string): string[] {
  const ids = new Set([
    "orientation-scope",
    "foundations-mechanics",
    "implementation-construction",
    "testing-verification",
    "performance-capacity-cost",
    "compatibility-integration",
    "decision-comparison",
    "provenance-rights",
  ]);
  const searchable = `${pattern.id} ${pattern.kind} ${rationale} ${pattern.testStates.map((state) => state.id).join(" ")} ${pattern.retrieval.acceptanceCriteria.join(" ")}`;
  if (pattern.kind !== "atomic") ids.add("architecture-design");
  if (/fail|error|recover|retry|cancel|lost|offline|disconnect|fallback|denied|missing|invalid/i.test(searchable)) ids.add("failure-recovery");
  if (pattern.kind === "systemic" || /lifecycle|cleanup|offscreen|background|idle|queue|stream|realtime|media|audio|video/i.test(searchable)) ids.add("operations-observability");
  if (/security|permission|privacy|sandbox|provenance|rights|camera|microphone|device-motion/i.test(searchable)) ids.add("security-privacy-safety");
  if (/migrat|upgrade|version|compatibility|deprecat|rollback|dependency|release/i.test(searchable)) ids.add("migration-evolution-deprecation");
  if (/agent|skill|retrieval|delegate/i.test(searchable)) ids.add("agent-skill");
  return [...ids].sort();
}

export async function collectAuthorityExtractionInputs(root: string): Promise<AuthorityExtractionInputs> {
  const registry = await loadRegistry(root);
  const snapshot = JSON.parse(await readFile(path.join(root, "authority/sources.snapshot.json"), "utf8")) as { sources: LockedSource[] };
  const lockedSources = snapshot.sources.map((source) => ({ ...source, id: authoritySourceId(source.url) })).sort((left, right) => left.id.localeCompare(right.id));
  const lockedByUrl = new Map(lockedSources.map((source) => [source.url, source]));
  const targetByPattern = new Map<string, string>();
  for (const target of registry.coverage.targets) for (const patternId of target.patternIds) targetByPattern.set(patternId, `${target.release}.${target.id}`);
  const edgesBySource: Record<string, AuthorityEdge[]> = Object.fromEntries(lockedSources.map((source) => [source.id, []]));
  for (const pattern of registry.patterns) {
    for (const reference of pattern.provenance.references) {
      const source = lockedByUrl.get(reference.url);
      if (!source) throw new Error(`Authority lockにないPattern referenceです: ${pattern.id} -> ${reference.url}`);
      const edge: AuthorityEdge = {
        edge_id: `edge.${dotted(pattern.id)}.${source.id}`,
        source_id: source.id,
        reference_url: reference.url,
        locator: new URL(reference.url).hash || "document-root",
        pattern_id: pattern.id,
        pattern_kind: pattern.kind,
        candidate_behavior_id: `candidate.${dotted(pattern.id)}.${source.id}`,
        capability_id: `capability.${dotted(pattern.id)}`,
        target_id: targetByPattern.get(pattern.id) ?? "unmapped",
        claim_id: `claim.pattern.${dotted(pattern.id)}`,
        variant_ids: pattern.variants.map((variant) => `variant.${dotted(pattern.id)}.${variant.id}`).sort(),
        surface_ids: inferredSurfaceIds(pattern, reference.notes),
        classification_basis: "domain-contract-projection-unreviewed",
        domain_reference_metadata_digest: sha256(JSON.stringify({ title: reference.title, notes: reference.notes })),
      };
      edgesBySource[source.id]!.push(edge);
    }
  }
  for (const edges of Object.values(edgesBySource)) edges.sort((left, right) => left.edge_id.localeCompare(right.edge_id));
  const toolDigest = await authorityExtractionToolDigest(root);
  const inputDigest = sha256(JSON.stringify({
    tool_digest: toolDigest,
    locked_sources: lockedSources.map(({ id, url, digest, size_bytes }) => ({ id, url, digest, size_bytes })),
    edges_by_source: edgesBySource,
  }));
  return { input_digest: inputDigest, tool_digest: toolDigest, locked_sources: lockedSources, edges_by_source: edgesBySource };
}

export function digestAuthorityArtifact(artifact: AuthoritySurfaceArtifact): string {
  return sha256(`${JSON.stringify(artifact, null, 2)}\n`);
}

function assertExactKeys(value: object, expected: string[], label: string): void {
  const actual = Object.keys(value).sort();
  const allowed = [...expected].sort();
  if (JSON.stringify(actual) !== JSON.stringify(allowed)) throw new Error(`${label}に許可されていないfieldまたは欠落があります: ${actual.join(",")}`);
}

export async function verifyAuthorityExtraction(root: string): Promise<AuthorityExtractionIndex> {
  const inputs = await collectAuthorityExtractionInputs(root);
  const index = JSON.parse(await readFile(path.join(root, authorityExtractionIndexPath), "utf8")) as AuthorityExtractionIndex;
  assertExactKeys(index, ["schema_version", "atlas_id", "generated_at", "status", "input_digest", "tool_digest", "body_storage", "summary", "sources"], "Authority extraction index");
  assertExactKeys(index.summary, ["locked_sources", "fetched_digest_matched", "fetched_digest_stale", "fetch_failed", "candidate_surfaces", "root_locators", "fragments_found", "fragments_not_found", "locator_evaluations_deferred", "reference_edges_classified", "unclassified_reference_edges", "authority_text_surfaces_exhaustive", "human_reviewed_surfaces", "core_v2_eligible_surfaces"], "Authority extraction summary");
  if (index.schema_version !== 1 || index.atlas_id !== "frontend-behavior-atlas" || index.status !== "incomplete-human-review-required") throw new Error("Authority extraction index contractが不正です。");
  if (index.generated_at !== "2026-08-28T00:00:00+09:00" || index.body_storage !== "digest-and-locator-context-digest-only") throw new Error("Authority extractionの決定論境界または本文保存境界が不正です。");
  if (index.input_digest !== inputs.input_digest || index.tool_digest !== inputs.tool_digest) throw new Error("Authority extraction inputまたはtool sourceがdriftしています。pnpm authority:extractを明示実行してください。");
  const expectedFiles = inputs.locked_sources.map((source) => `${source.id}.json`).sort();
  const actualFiles = (await readdir(path.join(root, authorityExtractionDirectory))).filter((file) => file.endsWith(".json")).sort();
  if (JSON.stringify(actualFiles) !== JSON.stringify(expectedFiles)) throw new Error("Authority Surface artifact集合がSource lockと一致しません。");
  const indexById = new Map(index.sources.map((source) => [source.id, source]));
  if (index.sources.length !== inputs.locked_sources.length || indexById.size !== index.sources.length) throw new Error("Authority extraction indexのSource集合に欠落または重複があります。");
  let edges = 0;
  let matched = 0;
  let stale = 0;
  let failed = 0;
  let roots = 0;
  let found = 0;
  let missing = 0;
  let deferred = 0;
  for (const source of inputs.locked_sources) {
    const relativePath = `${authorityExtractionDirectory}/${source.id}.json`;
    const artifact = JSON.parse(await readFile(path.join(root, relativePath), "utf8")) as AuthoritySurfaceArtifact;
    assertExactKeys(artifact, ["schema_version", "source_id", "source_url", "locked_source_digest", "fetch", "extraction", "candidate_surfaces"], `Authority Surface artifact ${source.id}`);
    assertExactKeys(artifact.fetch, ["status", "fetched_digest", "locked_digest_match", "http_status", "final_url", "content_type", "fetched_bytes", "error_digest"], `Authority fetch ${source.id}`);
    assertExactKeys(artifact.extraction, ["method", "tool", "tool_digest", "review_status", "body_storage"], `Authority extraction boundary ${source.id}`);
    if (artifact.schema_version !== 1 || artifact.source_id !== source.id || artifact.source_url !== source.url || artifact.locked_source_digest !== source.digest) throw new Error(`Authority Surface artifact identityが不正です: ${source.id}`);
    if (artifact.extraction.tool_digest !== inputs.tool_digest || artifact.extraction.review_status !== "automated-unreviewed" || artifact.extraction.body_storage !== "digest-and-locator-context-digest-only") throw new Error(`Authority review/storage/tool boundaryが不正です: ${source.id}`);
    const expectedEdges = inputs.edges_by_source[source.id] ?? [];
    if (artifact.candidate_surfaces.length !== expectedEdges.length) throw new Error(`Authority edge数が不正です: ${source.id}`);
    const expectedById = new Map(expectedEdges.map((edge) => [edge.edge_id, edge]));
    for (const candidate of artifact.candidate_surfaces) {
      assertExactKeys(candidate, ["edge_id", "source_id", "reference_url", "locator", "pattern_id", "pattern_kind", "candidate_behavior_id", "capability_id", "target_id", "claim_id", "variant_ids", "surface_ids", "classification_basis", "domain_reference_metadata_digest", "locator_status", "context_digest", "context_start", "context_end", "context_unit", "heading_digest", "classification"], `Authority candidate ${candidate.edge_id}`);
      const expected = expectedById.get(candidate.edge_id);
      if (!expected) throw new Error(`未知のAuthority edgeです: ${candidate.edge_id}`);
      for (const [key, value] of Object.entries(expected)) if (JSON.stringify(candidate[key as keyof typeof candidate]) !== JSON.stringify(value)) throw new Error(`Authority edge metadataがdriftしています: ${candidate.edge_id}#${key}`);
      if (candidate.classification !== "candidate-included-unreviewed") throw new Error(`Human review未完了を隠せません: ${candidate.edge_id}`);
      if (candidate.context_digest !== null && !/^sha256:[a-f0-9]{64}$/.test(candidate.context_digest)) throw new Error(`Context digestが不正です: ${candidate.edge_id}`);
      if (candidate.heading_digest !== null && !/^sha256:[a-f0-9]{64}$/.test(candidate.heading_digest)) throw new Error(`Heading digestが不正です: ${candidate.edge_id}`);
      const located = candidate.locator_status === "root-document" || candidate.locator_status === "fragment-found";
      if (located !== (candidate.context_digest !== null && candidate.context_start !== null && candidate.context_end !== null && candidate.context_unit === "utf16-code-unit")) throw new Error(`Locator context境界が不正です: ${candidate.edge_id}`);
      if (candidate.locator === "document-root" && candidate.locator_status !== "root-document" && artifact.fetch.status === "matched") throw new Error(`Document root locatorが不正です: ${candidate.edge_id}`);
      if (artifact.fetch.status === "matched" && candidate.locator_status.startsWith("not-evaluated-")) throw new Error(`Matched bodyのlocatorが未評価です: ${candidate.edge_id}`);
      if (artifact.fetch.status === "stale" && candidate.locator_status !== "not-evaluated-stale-body") throw new Error(`Stale bodyのlocator境界が不正です: ${candidate.edge_id}`);
      if (artifact.fetch.status === "failed" && candidate.locator_status !== "not-evaluated-fetch-failed") throw new Error(`Failed fetchのlocator境界が不正です: ${candidate.edge_id}`);
      if (candidate.locator_status === "root-document") roots += 1;
      else if (candidate.locator_status === "fragment-found") found += 1;
      else if (candidate.locator_status === "fragment-not-found") missing += 1;
      else deferred += 1;
    }
    if (artifact.fetch.status === "matched") matched += 1;
    else if (artifact.fetch.status === "stale") stale += 1;
    else failed += 1;
    if (artifact.fetch.status === "matched" && (!artifact.fetch.locked_digest_match || artifact.fetch.fetched_digest !== source.digest)) throw new Error(`Matched fetchのdigestが不正です: ${source.id}`);
    if (artifact.fetch.status === "stale" && (artifact.fetch.locked_digest_match || artifact.fetch.fetched_digest === null || artifact.fetch.fetched_digest === source.digest)) throw new Error(`Stale fetchのdigestが不正です: ${source.id}`);
    if (artifact.fetch.status === "failed" && (artifact.fetch.fetched_digest !== null || artifact.fetch.error_digest === null)) throw new Error(`Failed fetchの記録が不正です: ${source.id}`);
    edges += artifact.candidate_surfaces.length;
    const indexRecord = indexById.get(source.id);
    if (indexRecord) assertExactKeys(indexRecord, ["id", "path", "digest", "locked_digest_match", "candidate_surfaces", "locator_status"], `Authority index source ${source.id}`);
    const expectedLocatorStatus = Object.fromEntries([...new Set(artifact.candidate_surfaces.map((candidate) => candidate.locator_status))].sort().map((status) => [status, artifact.candidate_surfaces.filter((candidate) => candidate.locator_status === status).length]));
    if (!indexRecord || indexRecord.path !== relativePath || indexRecord.digest !== digestAuthorityArtifact(artifact) || indexRecord.candidate_surfaces !== artifact.candidate_surfaces.length || indexRecord.locked_digest_match !== artifact.fetch.locked_digest_match || JSON.stringify(indexRecord.locator_status) !== JSON.stringify(expectedLocatorStatus)) throw new Error(`Authority extraction index recordが不正です: ${source.id}`);
  }
  const expectedSummary = {
    locked_sources: inputs.locked_sources.length,
    fetched_digest_matched: matched,
    fetched_digest_stale: stale,
    fetch_failed: failed,
    candidate_surfaces: edges,
    root_locators: roots,
    fragments_found: found,
    fragments_not_found: missing,
    locator_evaluations_deferred: deferred,
    reference_edges_classified: edges,
    unclassified_reference_edges: 0,
    authority_text_surfaces_exhaustive: false as const,
    human_reviewed_surfaces: 0 as const,
    core_v2_eligible_surfaces: 0 as const,
  };
  if (JSON.stringify(index.summary) !== JSON.stringify(expectedSummary)) throw new Error("Authority extraction summaryがArtifact実体と一致しません。");
  console.log(`Verified Authority extraction: ${matched}/${inputs.locked_sources.length} locked bodies matched, ${found} fragments found, ${missing} fragments missing, ${deferred} locator evaluations deferred, ${edges} candidate edges, 0 human-reviewed.`);
  return index;
}
