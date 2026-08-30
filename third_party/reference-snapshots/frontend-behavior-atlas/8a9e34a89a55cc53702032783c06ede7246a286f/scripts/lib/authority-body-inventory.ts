import { createHash } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { authoritySourceId, sha256 } from "./authority-extraction";

export const authorityBodyInventoryIndexPath = "authority/body-inventory.snapshot.json";
export const authorityBodyInventoryDirectory = "authority/body-inventory-draft";
export const authorityBodySelectorContract = [
  "document-root",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "dfn",
  "section",
  "article",
  "main",
  "nav",
  "aside",
  "table",
  "figure",
] as const;

type LockedSource = {
  url: string;
  digest: string;
  size_bytes: number;
};

export type AuthorityDocumentInput = {
  document_id: string;
  fetch_url: string;
  locked_digest: string;
  source_ids: string[];
};

export type AuthorityBodyInventoryInputs = {
  input_digest: string;
  tool_digest: string;
  source_entries: number;
  documents: AuthorityDocumentInput[];
};

export type AuthorityBodyAnchor = {
  id: string;
  locator: string;
  locator_kind: "document-root" | "fragment" | "locked-body-offset";
  semantic_kind: "document-root" | "heading" | "definition" | "section" | "landmark" | "data-table" | "figure";
  tag: "document" | "h1" | "h2" | "h3" | "h4" | "h5" | "h6" | "dfn" | "section" | "article" | "main" | "nav" | "aside" | "table" | "figure";
  heading_level: number | null;
  parent_anchor_id: string | null;
  context_start: number;
  context_end: number;
  context_unit: "utf16-code-unit";
  context_digest: string;
  label_digest: string | null;
  classification_status: "pending-human";
  surface_ids: [];
};

export type AuthorityBodyInventoryArtifact = {
  schema_version: 1;
  document_id: string;
  fetch_url: string;
  source_ids: string[];
  locked_body_digest: string;
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
    method: "html-semantic-anchor-selector-v1";
    tool: "frontend-behavior-atlas-authority-body-inventory-v1";
    tool_digest: string;
    selector_contract: string[];
    selector_exhaustive_for_locked_body: boolean;
    authority_semantics_exhaustive: false;
    review_status: "automated-unreviewed";
    body_storage: "digest-locator-and-offset-only";
  };
  anchors: AuthorityBodyAnchor[];
};

export type AuthorityBodyInventoryIndex = {
  schema_version: 1;
  atlas_id: "frontend-behavior-atlas";
  generated_at: "2026-08-28T00:00:00+09:00";
  status: "incomplete-human-review-required";
  input_digest: string;
  tool_digest: string;
  body_storage: "digest-locator-and-offset-only";
  selector_contract: string[];
  summary: {
    source_entries: number;
    unique_documents: number;
    matched_documents: number;
    stale_documents: number;
    failed_documents: number;
    selector_exhaustive_documents: number;
    anchors: number;
    anchors_by_kind: Record<string, number>;
    classified_anchors: 0;
    unclassified_anchors: number;
    human_reviewed_anchors: 0;
    core_v2_eligible_artifacts: 0;
    authority_semantics_exhaustive: false;
  };
  documents: Array<{
    id: string;
    path: string;
    digest: string;
    fetch_status: "matched" | "stale" | "failed";
    source_entries: number;
    anchors: number;
    anchors_by_kind: Record<string, number>;
  }>;
};

const digestHex = (value: string): string => createHash("sha256").update(value).digest("hex");

export function authorityDocumentId(fetchUrl: string): string {
  const host = new URL(fetchUrl).hostname.replace(/^www\./, "").replaceAll(".", "-");
  return `document-${host}-${digestHex(fetchUrl).slice(0, 12)}`;
}

export async function authorityBodyInventoryToolDigest(root: string): Promise<string> {
  const files = [
    "scripts/lib/authority-body-inventory.ts",
    "scripts/extract-authority-body-inventory.ts",
    "scripts/test-authority-body-inventory.ts",
  ];
  const contents = await Promise.all(files.map(async (file) => `${file}\0${await readFile(path.join(root, file), "utf8")}`));
  return sha256(contents.join("\0"));
}

export async function collectAuthorityBodyInventoryInputs(root: string): Promise<AuthorityBodyInventoryInputs> {
  const snapshot = JSON.parse(await readFile(path.join(root, "authority/sources.snapshot.json"), "utf8")) as { sources: LockedSource[] };
  const grouped = new Map<string, Array<LockedSource & { source_id: string }>>();
  for (const source of snapshot.sources) {
    const url = new URL(source.url);
    url.hash = "";
    const fetchUrl = url.href;
    const values = grouped.get(fetchUrl) ?? [];
    values.push({ ...source, source_id: authoritySourceId(source.url) });
    grouped.set(fetchUrl, values);
  }
  const documents: AuthorityDocumentInput[] = [];
  for (const [fetchUrl, sources] of grouped) {
    const digests = [...new Set(sources.map((source) => source.digest))];
    if (digests.length !== 1) throw new Error(`同一document URLに複数のlocked digestがあります: ${fetchUrl}`);
    documents.push({
      document_id: authorityDocumentId(fetchUrl),
      fetch_url: fetchUrl,
      locked_digest: digests[0]!,
      source_ids: sources.map((source) => source.source_id).sort(),
    });
  }
  documents.sort((left, right) => left.document_id.localeCompare(right.document_id));
  const toolDigest = await authorityBodyInventoryToolDigest(root);
  const inputDigest = sha256(JSON.stringify({ tool_digest: toolDigest, source_entries: snapshot.sources.length, documents }));
  return { input_digest: inputDigest, tool_digest: toolDigest, source_entries: snapshot.sources.length, documents };
}

const decodeEntities = (value: string): string => value
  .replace(/<[^>]+>/g, " ")
  .replace(/&(?:nbsp|#160);/gi, " ")
  .replace(/&lt;/gi, "<")
  .replace(/&gt;/gi, ">")
  .replace(/&amp;/gi, "&")
  .replace(/&quot;/gi, '"')
  .replace(/&#39;|&apos;/gi, "'")
  .replace(/&#(?:x([a-f0-9]+)|(\d+));/gi, (_match, hex: string | undefined, decimal: string | undefined) => {
    const point = Number.parseInt(hex ?? decimal ?? "", hex ? 16 : 10);
    return Number.isFinite(point) && point > 0 && point <= 0x10ffff ? String.fromCodePoint(point) : " ";
  })
  .replace(/\s+/g, " ")
  .trim();

function attributeValue(attributes: string, name: string): string | null {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = new RegExp(`(?:^|\\s)${escaped}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s>]+))`, "i").exec(attributes);
  return match ? (match[1] ?? match[2] ?? match[3] ?? null) : null;
}

function maskIgnoredMarkup(body: string): string {
  return body.replace(/<!--[\s\S]*?-->|<script\b[\s\S]*?<\/script\s*>|<style\b[\s\S]*?<\/style\s*>/gi, (value) => " ".repeat(value.length));
}

const semanticKind = (tag: AuthorityBodyAnchor["tag"]): AuthorityBodyAnchor["semantic_kind"] => {
  if (/^h[1-6]$/.test(tag)) return "heading";
  if (tag === "dfn") return "definition";
  if (tag === "section") return "section";
  if (tag === "table") return "data-table";
  if (tag === "figure") return "figure";
  return "landmark";
};

export function extractAuthorityBodyAnchors(body: string, exactBodyDigest: string, documentId: string): AuthorityBodyAnchor[] {
  const masked = maskIgnoredMarkup(body);
  const raw: Array<{ tag: AuthorityBodyAnchor["tag"]; start: number; end: number; fragment: string | null; labelDigest: string | null; level: number | null }> = [];
  const matcher = /<(h[1-6]|dfn|section|article|main|nav|aside|table|figure)\b([^>]*)>/gi;
  for (const match of masked.matchAll(matcher)) {
    const tag = match[1]!.toLowerCase() as AuthorityBodyAnchor["tag"];
    const start = match.index!;
    const openEnd = start + match[0].length;
    const close = new RegExp(`</${tag}\\s*>`, "i").exec(masked.slice(openEnd));
    const end = close ? openEnd + close.index + close[0].length : openEnd;
    let fragment = attributeValue(match[2] ?? "", "id") ?? attributeValue(match[2] ?? "", "name");
    let labelDigest: string | null = null;
    if (/^h[1-6]$/.test(tag) || tag === "dfn") {
      const innerEnd = close ? openEnd + close.index : Math.min(body.length, openEnd + 4096);
      const inner = body.slice(openEnd, innerEnd);
      if (!fragment) fragment = attributeValue(inner.slice(0, 4096), "id") ?? attributeValue(inner.slice(0, 4096), "name");
      const label = decodeEntities(inner);
      labelDigest = label ? sha256(label) : null;
    }
    raw.push({ tag, start, end, fragment, labelDigest, level: /^h[1-6]$/.test(tag) ? Number(tag.slice(1)) : null });
  }

  const anchors: AuthorityBodyAnchor[] = [{
    id: `anchor-root-${digestHex(`${documentId}\0${exactBodyDigest}`).slice(0, 20)}`,
    locator: "document-root",
    locator_kind: "document-root",
    semantic_kind: "document-root",
    tag: "document",
    heading_level: null,
    parent_anchor_id: null,
    context_start: 0,
    context_end: body.length,
    context_unit: "utf16-code-unit",
    context_digest: exactBodyDigest,
    label_digest: null,
    classification_status: "pending-human",
    surface_ids: [],
  }];
  const headingStack = new Map<number, string>();
  for (const item of raw) {
    const locator = item.fragment ? `#${item.fragment}` : `offset:utf16:${item.start}`;
    const locatorKind = item.fragment ? "fragment" : "locked-body-offset";
    let parent = anchors[0]!.id;
    if (item.level !== null) {
      for (let level = item.level - 1; level >= 1; level -= 1) if (headingStack.has(level)) { parent = headingStack.get(level)!; break; }
    } else {
      for (let level = 6; level >= 1; level -= 1) if (headingStack.has(level)) { parent = headingStack.get(level)!; break; }
    }
    const id = `anchor-${digestHex(`${documentId}\0${exactBodyDigest}\0${item.tag}\0${locator}\0${item.start}`).slice(0, 20)}`;
    const contextStart = Math.max(0, item.start - 1024);
    const contextEnd = Math.min(body.length, Math.max(item.end, item.start + 1) + 4096);
    anchors.push({
      id,
      locator,
      locator_kind: locatorKind,
      semantic_kind: semanticKind(item.tag),
      tag: item.tag,
      heading_level: item.level,
      parent_anchor_id: parent,
      context_start: contextStart,
      context_end: contextEnd,
      context_unit: "utf16-code-unit",
      context_digest: sha256(body.slice(contextStart, contextEnd)),
      label_digest: item.labelDigest,
      classification_status: "pending-human",
      surface_ids: [],
    });
    if (item.level !== null) {
      headingStack.set(item.level, id);
      for (let deeper = item.level + 1; deeper <= 6; deeper += 1) headingStack.delete(deeper);
    }
  }
  return anchors;
}

export function authorityAnchorCounts(anchors: AuthorityBodyAnchor[]): Record<string, number> {
  const result: Record<string, number> = {};
  for (const anchor of anchors) result[anchor.semantic_kind] = (result[anchor.semantic_kind] ?? 0) + 1;
  return Object.fromEntries(Object.entries(result).sort(([left], [right]) => left.localeCompare(right)));
}

export function digestAuthorityBodyArtifact(artifact: AuthorityBodyInventoryArtifact): string {
  return sha256(`${JSON.stringify(artifact, null, 2)}\n`);
}

function assertExactKeys(value: object, expected: string[], label: string): void {
  const actual = Object.keys(value).sort();
  const allowed = [...expected].sort();
  if (JSON.stringify(actual) !== JSON.stringify(allowed)) throw new Error(`${label}に許可されていないfieldまたは欠落があります: ${actual.join(",")}`);
}

export async function verifyAuthorityBodyInventory(root: string): Promise<AuthorityBodyInventoryIndex> {
  const inputs = await collectAuthorityBodyInventoryInputs(root);
  const index = JSON.parse(await readFile(path.join(root, authorityBodyInventoryIndexPath), "utf8")) as AuthorityBodyInventoryIndex;
  assertExactKeys(index, ["schema_version", "atlas_id", "generated_at", "status", "input_digest", "tool_digest", "body_storage", "selector_contract", "summary", "documents"], "Authority body inventory index");
  assertExactKeys(index.summary, ["source_entries", "unique_documents", "matched_documents", "stale_documents", "failed_documents", "selector_exhaustive_documents", "anchors", "anchors_by_kind", "classified_anchors", "unclassified_anchors", "human_reviewed_anchors", "core_v2_eligible_artifacts", "authority_semantics_exhaustive"], "Authority body inventory summary");
  if (index.schema_version !== 1 || index.atlas_id !== "frontend-behavior-atlas" || index.generated_at !== "2026-08-28T00:00:00+09:00" || index.status !== "incomplete-human-review-required") throw new Error("Authority body inventory index contractが不正です。");
  if (index.input_digest !== inputs.input_digest || index.tool_digest !== inputs.tool_digest || index.body_storage !== "digest-locator-and-offset-only" || JSON.stringify(index.selector_contract) !== JSON.stringify(authorityBodySelectorContract)) throw new Error("Authority body inventory入力または抽出境界がdriftしています。");
  if (index.documents.length !== inputs.documents.length || new Set(index.documents.map((item) => item.id)).size !== index.documents.length) throw new Error("Authority body inventory document集合に欠落または重複があります。");
  const expectedFiles = inputs.documents.map((item) => `${item.document_id}.json`).sort();
  const actualFiles = (await readdir(path.join(root, authorityBodyInventoryDirectory))).filter((file) => file.endsWith(".json")).sort();
  if (JSON.stringify(actualFiles) !== JSON.stringify(expectedFiles)) throw new Error("Authority body inventory artifact集合がSource lockと一致しません。");
  const indexById = new Map(index.documents.map((item) => [item.id, item]));
  let matched = 0;
  let stale = 0;
  let failed = 0;
  let anchors = 0;
  const counts: Record<string, number> = {};
  for (const input of inputs.documents) {
    const relativePath = `${authorityBodyInventoryDirectory}/${input.document_id}.json`;
    const artifact = JSON.parse(await readFile(path.join(root, relativePath), "utf8")) as AuthorityBodyInventoryArtifact;
    assertExactKeys(artifact, ["schema_version", "document_id", "fetch_url", "source_ids", "locked_body_digest", "fetch", "extraction", "anchors"], `Authority body artifact ${input.document_id}`);
    assertExactKeys(artifact.fetch, ["status", "fetched_digest", "locked_digest_match", "http_status", "final_url", "content_type", "fetched_bytes", "error_digest"], `Authority body fetch ${input.document_id}`);
    assertExactKeys(artifact.extraction, ["method", "tool", "tool_digest", "selector_contract", "selector_exhaustive_for_locked_body", "authority_semantics_exhaustive", "review_status", "body_storage"], `Authority body extraction ${input.document_id}`);
    if (artifact.schema_version !== 1 || artifact.document_id !== input.document_id || artifact.fetch_url !== input.fetch_url || artifact.locked_body_digest !== input.locked_digest || JSON.stringify(artifact.source_ids) !== JSON.stringify(input.source_ids)) throw new Error(`Authority body artifact identityが不正です: ${input.document_id}`);
    if (artifact.extraction.method !== "html-semantic-anchor-selector-v1" || artifact.extraction.tool_digest !== inputs.tool_digest || artifact.extraction.review_status !== "automated-unreviewed" || artifact.extraction.authority_semantics_exhaustive !== false || artifact.extraction.body_storage !== "digest-locator-and-offset-only" || JSON.stringify(artifact.extraction.selector_contract) !== JSON.stringify(authorityBodySelectorContract)) throw new Error(`Authority body extraction境界が不正です: ${input.document_id}`);
    if (artifact.fetch.status === "matched") {
      matched += 1;
      if (!artifact.fetch.locked_digest_match || artifact.fetch.fetched_digest !== input.locked_digest || !artifact.extraction.selector_exhaustive_for_locked_body || artifact.anchors.length === 0) throw new Error(`Matched body artifactが不正です: ${input.document_id}`);
    } else if (artifact.fetch.status === "stale") {
      stale += 1;
      if (artifact.fetch.locked_digest_match || artifact.fetch.fetched_digest === null || artifact.fetch.fetched_digest === input.locked_digest || artifact.extraction.selector_exhaustive_for_locked_body || artifact.anchors.length !== 0) throw new Error(`Stale body artifactが不正です: ${input.document_id}`);
    } else {
      failed += 1;
      if (artifact.fetch.fetched_digest !== null || artifact.fetch.error_digest === null || artifact.extraction.selector_exhaustive_for_locked_body || artifact.anchors.length !== 0) throw new Error(`Failed body artifactが不正です: ${input.document_id}`);
    }
    const anchorIds = new Set<string>();
    for (const [position, anchor] of artifact.anchors.entries()) {
      assertExactKeys(anchor, ["id", "locator", "locator_kind", "semantic_kind", "tag", "heading_level", "parent_anchor_id", "context_start", "context_end", "context_unit", "context_digest", "label_digest", "classification_status", "surface_ids"], `Authority body anchor ${input.document_id}:${position}`);
      if (anchorIds.has(anchor.id)) throw new Error(`Authority body anchor IDが重複しています: ${anchor.id}`);
      anchorIds.add(anchor.id);
      if (!/^anchor-[a-z0-9-]+$/.test(anchor.id) || !/^sha256:[a-f0-9]{64}$/.test(anchor.context_digest) || (anchor.label_digest !== null && !/^sha256:[a-f0-9]{64}$/.test(anchor.label_digest))) throw new Error(`Authority body anchor digest/IDが不正です: ${anchor.id}`);
      if (anchor.context_start < 0 || anchor.context_end <= anchor.context_start || anchor.context_unit !== "utf16-code-unit" || anchor.classification_status !== "pending-human" || anchor.surface_ids.length !== 0) throw new Error(`Authority body anchor review/storage境界が不正です: ${anchor.id}`);
      if (position === 0 && (anchor.semantic_kind !== "document-root" || anchor.locator !== "document-root" || anchor.parent_anchor_id !== null)) throw new Error(`Authority body root anchorが不正です: ${input.document_id}`);
      if (position > 0 && (anchor.parent_anchor_id === null || !anchorIds.has(anchor.parent_anchor_id))) throw new Error(`Authority body anchor parentが先行定義されていません: ${anchor.id}`);
    }
    const artifactCounts = authorityAnchorCounts(artifact.anchors);
    for (const [kind, count] of Object.entries(artifactCounts)) counts[kind] = (counts[kind] ?? 0) + count;
    anchors += artifact.anchors.length;
    const record = indexById.get(input.document_id);
    if (record) assertExactKeys(record, ["id", "path", "digest", "fetch_status", "source_entries", "anchors", "anchors_by_kind"], `Authority body index record ${input.document_id}`);
    if (!record || record.path !== relativePath || record.digest !== digestAuthorityBodyArtifact(artifact) || record.fetch_status !== artifact.fetch.status || record.source_entries !== input.source_ids.length || record.anchors !== artifact.anchors.length || JSON.stringify(record.anchors_by_kind) !== JSON.stringify(artifactCounts)) throw new Error(`Authority body index recordが不正です: ${input.document_id}`);
  }
  const sortedCounts = Object.fromEntries(Object.entries(counts).sort(([left], [right]) => left.localeCompare(right)));
  const expectedSummary = {
    source_entries: inputs.source_entries,
    unique_documents: inputs.documents.length,
    matched_documents: matched,
    stale_documents: stale,
    failed_documents: failed,
    selector_exhaustive_documents: matched,
    anchors,
    anchors_by_kind: sortedCounts,
    classified_anchors: 0 as const,
    unclassified_anchors: anchors,
    human_reviewed_anchors: 0 as const,
    core_v2_eligible_artifacts: 0 as const,
    authority_semantics_exhaustive: false as const,
  };
  if (JSON.stringify(index.summary) !== JSON.stringify(expectedSummary)) throw new Error("Authority body inventory summaryがArtifact実体と一致しません。");
  console.log(`Verified Authority body inventory: ${matched}/${inputs.documents.length} locked documents matched, ${anchors} selector anchors, ${anchors} unclassified, 0 human-reviewed.`);
  return index;
}
