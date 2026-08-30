import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, unlink, writeFile } from "node:fs/promises";
import path from "node:path";
import {
  authorityBodyInventoryDirectory,
  authorityBodyInventoryIndexPath,
  type AuthorityBodyAnchor,
  type AuthorityBodyInventoryArtifact,
  type AuthorityBodyInventoryIndex,
} from "./authority-body-inventory";
import {
  authorityExtractionDirectory,
  sha256,
  type AuthoritySurfaceArtifact,
} from "./authority-extraction";

export const authorityReviewQueueIndexPath = "authority/review-queue.snapshot.json";
export const authorityReviewQueueDirectory = "authority/review-queue-draft";
export const authorityReviewDecisionPath = "authority/reviews/decisions.json";

type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
type Priority = 0 | 1 | 2;
type ReviewAction = "include" | "exclude" | "merge" | "split";

export type AuthorityReviewQueueItem = {
  anchor_id: string;
  document_id: string;
  document_url: string;
  source_ids: string[];
  locked_source_digest: string;
  inventory_tool_digest: string;
  review_queue_tool_digest: string;
  locator: string;
  locator_kind: AuthorityBodyAnchor["locator_kind"];
  semantic_kind: AuthorityBodyAnchor["semantic_kind"];
  tag: AuthorityBodyAnchor["tag"];
  heading_level: number | null;
  parent_anchor_id: string | null;
  context_start: number;
  context_end: number;
  context_unit: "utf16-code-unit";
  context_digest: string;
  label_digest: string | null;
  existing_reference_edge_ids: string[];
  priority: Priority;
  priority_reasons: string[];
  candidate_cluster_id: string | null;
  batch_id: string;
  state: "pending-human";
};

export type AuthorityReviewQueueBatch = {
  schema_version: 1;
  queue_id: string;
  batch_id: string;
  status: "pending-human";
  machine_assistance: "ordering-and-candidate-clustering-only";
  semantic_decisions: "none";
  items: AuthorityReviewQueueItem[];
};

export type AuthorityReviewQueueIndex = {
  schema_version: 1;
  atlas_id: "frontend-behavior-atlas";
  generated_at: "2026-08-28T00:00:00+09:00";
  status: "incomplete-human-review-required";
  queue_id: string;
  input_digest: string;
  tool_digest: string;
  decision_ledger: string;
  body_storage: "digest-locator-and-offset-only";
  machine_assistance: "dedupe-candidate-cluster-priority-and-batch-only";
  semantic_decisions: "human-only";
  summary: {
    eligible_documents: number;
    queued_anchors: number;
    pending_human: number;
    human_reviewed: number;
    priority_counts: Record<string, number>;
    candidate_clusters: number;
    clustered_anchors: number;
    batches: number;
    stale_document_holds: number;
    decisions: number;
    included: number;
    excluded: number;
    merged: number;
    split: number;
    authority_semantics_exhaustive: false;
  };
  batches: Array<{ id: string; path: string; digest: string; priority: Priority; semantic_kind: string; bucket: string; items: number }>;
  stale_holds: Array<{
    document_id: string;
    document_url: string;
    source_ids: string[];
    locked_source_digest: string;
    inventory_tool_digest: string;
    review_queue_tool_digest: string;
    locator: "document-root";
    fetched_digest: string;
    status: "hold-stale-document-relock-required";
    reason: "locked-document-body-digest-mismatch";
  }>;
};

type ReviewBinding = Pick<AuthorityReviewQueueItem,
  "anchor_id" | "document_id" | "document_url" | "locked_source_digest" | "inventory_tool_digest" | "review_queue_tool_digest" | "locator" | "context_start" | "context_end" | "context_unit" | "context_digest">;

export type ReviewDecision = {
  decision_id: string;
  action: ReviewAction;
  anchor_ids: string[];
  source_bindings: ReviewBinding[];
  rationale: string;
  reviewer: string;
  reviewed_at: string;
  review_method: "manual-primary-source";
  mapping: Array<{ old_anchor_id: string; new_item_ids: string[] }>;
  result_items: Array<{ id: string; item_type: "surface" | "atomic-behavior" }>;
};

type ReviewDecisionLedger = {
  schema_version: 1;
  atlas_id: "frontend-behavior-atlas";
  queue_id: string;
  status: "incomplete-human-review-required";
  decisions: ReviewDecision[];
};

const exactKeys = (value: object, expected: string[], label: string): void => {
  const actual = Object.keys(value).sort();
  if (JSON.stringify(actual) !== JSON.stringify([...expected].sort())) throw new Error(`${label}のfield集合が不正です: ${actual.join(",")}`);
};

const shortHash = (value: string, length = 16): string => createHash("sha256").update(value).digest("hex").slice(0, length);
const artifactDigest = (value: Json): string => sha256(`${JSON.stringify(value, null, 2)}\n`);

export async function authorityReviewQueueToolDigest(root: string): Promise<string> {
  const files = [
    "scripts/lib/authority-review-queue.ts",
    "scripts/generate-authority-review-queue.ts",
    "scripts/verify-authority-review-queue.ts",
    "scripts/test-authority-review-queue.ts",
  ];
  return sha256((await Promise.all(files.map(async (file) => `${file}\0${await readFile(path.join(root, file), "utf8")}`))).join("\0"));
}

function priorityFor(anchor: AuthorityBodyAnchor, edges: string[]): { priority: Priority; reasons: string[] } {
  if (edges.length > 0) return { priority: 0, reasons: ["existing-domain-reference-locator-match"] };
  if (anchor.semantic_kind === "heading" || anchor.semantic_kind === "definition") return { priority: 1, reasons: ["semantic-label-anchor"] };
  return { priority: 2, reasons: ["structural-or-document-anchor"] };
}

function batchId(priority: Priority, semanticKind: string, anchorId: string): string {
  const bucket = (Number.parseInt(shortHash(anchorId, 2), 16) % 64).toString(16).padStart(2, "0");
  return `review-p${priority}-${semanticKind}-${bucket}`;
}

type QueueBuild = { index: AuthorityReviewQueueIndex; batches: AuthorityReviewQueueBatch[]; emptyLedger: ReviewDecisionLedger };

export async function buildAuthorityReviewQueue(root: string): Promise<QueueBuild> {
  const bodyIndex = JSON.parse(await readFile(path.join(root, authorityBodyInventoryIndexPath), "utf8")) as AuthorityBodyInventoryIndex;
  const queueToolDigest = await authorityReviewQueueToolDigest(root);
  const artifacts = await Promise.all(bodyIndex.documents.map(async (record) => JSON.parse(await readFile(path.join(root, record.path), "utf8")) as AuthorityBodyInventoryArtifact));
  const anchorIds = artifacts.flatMap((artifact) => artifact.anchors.map((anchor) => anchor.id)).sort();
  const queueId = `authority-review-${shortHash(`${bodyIndex.input_digest}\0${anchorIds.join("\0")}`, 20)}`;
  const inputDigest = sha256(JSON.stringify({ body_input_digest: bodyIndex.input_digest, anchor_ids: anchorIds }));

  const edgeIdsBySourceLocator = new Map<string, string[]>();
  for (const sourceId of [...new Set(artifacts.flatMap((artifact) => artifact.source_ids))]) {
    const artifactPath = path.join(root, authorityExtractionDirectory, `${sourceId}.json`);
    const extracted = JSON.parse(await readFile(artifactPath, "utf8")) as AuthoritySurfaceArtifact;
    for (const edge of extracted.candidate_surfaces) {
      const key = `${sourceId}\0${edge.locator}`;
      const values = edgeIdsBySourceLocator.get(key) ?? [];
      values.push(edge.edge_id);
      edgeIdsBySourceLocator.set(key, values);
    }
  }

  const labelGroups = new Map<string, string[]>();
  for (const artifact of artifacts) for (const anchor of artifact.anchors) {
    if (anchor.label_digest && (anchor.semantic_kind === "heading" || anchor.semantic_kind === "definition")) {
      const key = `${anchor.semantic_kind}\0${anchor.label_digest}`;
      const values = labelGroups.get(key) ?? [];
      values.push(anchor.id);
      labelGroups.set(key, values);
    }
  }
  const clusterIdByAnchor = new Map<string, string>();
  for (const [key, ids] of labelGroups) if (ids.length > 1) {
    const clusterId = `candidate-cluster-${shortHash(key, 20)}`;
    for (const id of ids) clusterIdByAnchor.set(id, clusterId);
  }

  const grouped = new Map<string, AuthorityReviewQueueItem[]>();
  for (const artifact of artifacts.filter((item) => item.fetch.status === "matched")) for (const anchor of artifact.anchors) {
    const edgeIds = [...new Set(artifact.source_ids.flatMap((sourceId) => edgeIdsBySourceLocator.get(`${sourceId}\0${anchor.locator}`) ?? []))].sort();
    const { priority, reasons } = priorityFor(anchor, edgeIds);
    const id = batchId(priority, anchor.semantic_kind, anchor.id);
    const item: AuthorityReviewQueueItem = {
      anchor_id: anchor.id,
      document_id: artifact.document_id,
      document_url: artifact.fetch_url,
      source_ids: artifact.source_ids,
      locked_source_digest: artifact.locked_body_digest,
      inventory_tool_digest: artifact.extraction.tool_digest,
      review_queue_tool_digest: queueToolDigest,
      locator: anchor.locator,
      locator_kind: anchor.locator_kind,
      semantic_kind: anchor.semantic_kind,
      tag: anchor.tag,
      heading_level: anchor.heading_level,
      parent_anchor_id: anchor.parent_anchor_id,
      context_start: anchor.context_start,
      context_end: anchor.context_end,
      context_unit: anchor.context_unit,
      context_digest: anchor.context_digest,
      label_digest: anchor.label_digest,
      existing_reference_edge_ids: edgeIds,
      priority,
      priority_reasons: reasons,
      candidate_cluster_id: clusterIdByAnchor.get(anchor.id) ?? null,
      batch_id: id,
      state: "pending-human",
    };
    const values = grouped.get(id) ?? [];
    values.push(item);
    grouped.set(id, values);
  }
  const batches = [...grouped.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([id, items]): AuthorityReviewQueueBatch => ({
    schema_version: 1,
    queue_id: queueId,
    batch_id: id,
    status: "pending-human",
    machine_assistance: "ordering-and-candidate-clustering-only",
    semantic_decisions: "none",
    items: items.sort((left, right) => left.anchor_id.localeCompare(right.anchor_id)),
  }));
  const batchRecords = batches.map((batch) => {
    const [, p, ...rest] = batch.batch_id.split("-");
    return {
      id: batch.batch_id,
      path: `${authorityReviewQueueDirectory}/${batch.batch_id}.json`,
      digest: artifactDigest(batch as unknown as Json),
      priority: Number(p!.slice(1)) as Priority,
      semantic_kind: rest.slice(0, -1).join("-"),
      bucket: rest.at(-1)!,
      items: batch.items.length,
    };
  });
  const allItems = batches.flatMap((batch) => batch.items);
  const priorityCounts = Object.fromEntries([0, 1, 2].map((priority) => [String(priority), allItems.filter((item) => item.priority === priority).length]));
  const clusterIds = new Set(allItems.flatMap((item) => item.candidate_cluster_id ? [item.candidate_cluster_id] : []));
  const staleHolds = artifacts.filter((artifact) => artifact.fetch.status === "stale").map((artifact) => ({
    document_id: artifact.document_id,
    document_url: artifact.fetch_url,
    source_ids: artifact.source_ids,
    locked_source_digest: artifact.locked_body_digest,
    inventory_tool_digest: artifact.extraction.tool_digest,
    review_queue_tool_digest: queueToolDigest,
    locator: "document-root" as const,
    fetched_digest: artifact.fetch.fetched_digest!,
    status: "hold-stale-document-relock-required" as const,
    reason: "locked-document-body-digest-mismatch" as const,
  })).sort((left, right) => left.document_id.localeCompare(right.document_id));
  const emptyLedger: ReviewDecisionLedger = { schema_version: 1, atlas_id: "frontend-behavior-atlas", queue_id: queueId, status: "incomplete-human-review-required", decisions: [] };
  let ledger = emptyLedger;
  try { ledger = JSON.parse(await readFile(path.join(root, authorityReviewDecisionPath), "utf8")) as ReviewDecisionLedger; }
  catch { /* The generator creates the empty ledger after this pure build. */ }
  if (ledger.schema_version !== 1 || ledger.atlas_id !== "frontend-behavior-atlas" || ledger.queue_id !== queueId || ledger.status !== "incomplete-human-review-required") throw new Error("Review decision ledger identity/statusが現在のqueueと一致しません。");
  const itemById = new Map(allItems.map((item) => [item.anchor_id, item]));
  const decidedAnchors = validateAuthorityReviewDecisions(ledger.decisions, itemById);
  const index: AuthorityReviewQueueIndex = {
    schema_version: 1,
    atlas_id: "frontend-behavior-atlas",
    generated_at: "2026-08-28T00:00:00+09:00",
    status: "incomplete-human-review-required",
    queue_id: queueId,
    input_digest: inputDigest,
    tool_digest: queueToolDigest,
    decision_ledger: authorityReviewDecisionPath,
    body_storage: "digest-locator-and-offset-only",
    machine_assistance: "dedupe-candidate-cluster-priority-and-batch-only",
    semantic_decisions: "human-only",
    summary: {
      eligible_documents: artifacts.filter((artifact) => artifact.fetch.status === "matched").length,
      queued_anchors: allItems.length,
      pending_human: allItems.length - decidedAnchors.size,
      human_reviewed: decidedAnchors.size,
      priority_counts: priorityCounts,
      candidate_clusters: clusterIds.size,
      clustered_anchors: allItems.filter((item) => item.candidate_cluster_id !== null).length,
      batches: batches.length,
      stale_document_holds: staleHolds.length,
      decisions: ledger.decisions.length,
      included: ledger.decisions.filter((decision) => decision.action === "include").length,
      excluded: ledger.decisions.filter((decision) => decision.action === "exclude").length,
      merged: ledger.decisions.filter((decision) => decision.action === "merge").length,
      split: ledger.decisions.filter((decision) => decision.action === "split").length,
      authority_semantics_exhaustive: false,
    },
    batches: batchRecords,
    stale_holds: staleHolds,
  };
  return {
    index,
    batches,
    emptyLedger,
  };
}

export async function writeAuthorityReviewQueue(root: string): Promise<AuthorityReviewQueueIndex> {
  const built = await buildAuthorityReviewQueue(root);
  await mkdir(path.join(root, authorityReviewQueueDirectory), { recursive: true });
  const expectedFiles = new Set(built.batches.map((batch) => `${batch.batch_id}.json`));
  for (const file of await readdir(path.join(root, authorityReviewQueueDirectory))) if (file.endsWith(".json") && !expectedFiles.has(file)) await unlink(path.join(root, authorityReviewQueueDirectory, file));
  for (const batch of built.batches) await writeFile(path.join(root, authorityReviewQueueDirectory, `${batch.batch_id}.json`), `${JSON.stringify(batch, null, 2)}\n`);
  await mkdir(path.dirname(path.join(root, authorityReviewDecisionPath)), { recursive: true });
  try { await readFile(path.join(root, authorityReviewDecisionPath)); }
  catch { await writeFile(path.join(root, authorityReviewDecisionPath), `${JSON.stringify(built.emptyLedger, null, 2)}\n`); }
  await writeFile(path.join(root, authorityReviewQueueIndexPath), `${JSON.stringify(built.index, null, 2)}\n`);
  return built.index;
}

function validateDecision(decision: ReviewDecision, itemById: Map<string, AuthorityReviewQueueItem>, seen: Set<string>): void {
  exactKeys(decision, ["decision_id", "action", "anchor_ids", "source_bindings", "rationale", "reviewer", "reviewed_at", "review_method", "mapping", "result_items"], `Decision ${decision.decision_id}`);
  if (!/^decision\.[a-z0-9.-]+$/.test(decision.decision_id) || !(["include", "exclude", "merge", "split"] as string[]).includes(decision.action)) throw new Error(`Decision identity/actionが不正です: ${decision.decision_id}`);
  if (decision.review_method !== "manual-primary-source" || decision.rationale.trim().length < 40 || decision.reviewer.trim().length < 2 || /^(?:auto(?:mated)?|agent|bot|system|machine)(?:$|[-_. ])/i.test(decision.reviewer.trim())) throw new Error(`人手review provenanceが不足しています: ${decision.decision_id}`);
  if (Number.isNaN(Date.parse(decision.reviewed_at)) || !/^\d{4}-\d{2}-\d{2}T/.test(decision.reviewed_at)) throw new Error(`reviewed_atがISO date-timeではありません: ${decision.decision_id}`);
  if (decision.anchor_ids.length === 0 || new Set(decision.anchor_ids).size !== decision.anchor_ids.length || decision.source_bindings.length !== decision.anchor_ids.length || decision.mapping.length !== decision.anchor_ids.length) throw new Error(`Decision anchor/binding/mapping cardinalityが不正です: ${decision.decision_id}`);
  const anchorSet = new Set(decision.anchor_ids);
  for (const anchorId of decision.anchor_ids) {
    if (seen.has(anchorId)) throw new Error(`Anchorに複数decisionがあります: ${anchorId}`);
    seen.add(anchorId);
    if (!itemById.has(anchorId)) throw new Error(`Queue外anchorのdecisionです: ${anchorId}`);
  }
  const bindingById = new Map(decision.source_bindings.map((binding) => [binding.anchor_id, binding]));
  const mappingById = new Map(decision.mapping.map((mapping) => [mapping.old_anchor_id, mapping]));
  if (bindingById.size !== anchorSet.size || mappingById.size !== anchorSet.size) throw new Error(`Decision binding/mapping IDが重複しています: ${decision.decision_id}`);
  for (const anchorId of anchorSet) {
    const item = itemById.get(anchorId)!;
    const binding = bindingById.get(anchorId);
    if (binding) exactKeys(binding, ["anchor_id", "document_id", "document_url", "locked_source_digest", "inventory_tool_digest", "review_queue_tool_digest", "locator", "context_start", "context_end", "context_unit", "context_digest"], `Decision binding ${anchorId}`);
    const expected: ReviewBinding = { anchor_id: item.anchor_id, document_id: item.document_id, document_url: item.document_url, locked_source_digest: item.locked_source_digest, inventory_tool_digest: item.inventory_tool_digest, review_queue_tool_digest: item.review_queue_tool_digest, locator: item.locator, context_start: item.context_start, context_end: item.context_end, context_unit: item.context_unit, context_digest: item.context_digest };
    if (!binding || JSON.stringify(binding) !== JSON.stringify(expected)) throw new Error(`Decision source/tool/locator bindingがQueueと一致しません: ${anchorId}`);
    const mapping = mappingById.get(anchorId);
    if (mapping) exactKeys(mapping, ["old_anchor_id", "new_item_ids"], `Decision mapping ${anchorId}`);
    if (!mapping || new Set(mapping.new_item_ids).size !== mapping.new_item_ids.length || mapping.new_item_ids.some((id) => !/^[a-z][a-z0-9.-]+$/.test(id))) throw new Error(`Decision mappingが不正です: ${anchorId}`);
  }
  const resultSets = decision.mapping.map((mapping) => JSON.stringify([...mapping.new_item_ids].sort()));
  for (const result of decision.result_items) {
    exactKeys(result, ["id", "item_type"], `Decision result ${decision.decision_id}`);
    if (!/^[a-z][a-z0-9.-]+$/.test(result.id) || !(["surface", "atomic-behavior"] as string[]).includes(result.item_type)) throw new Error(`Decision result itemが不正です: ${decision.decision_id}`);
  }
  if (new Set(decision.result_items.map((result) => result.id)).size !== decision.result_items.length) throw new Error(`Decision result itemが重複しています: ${decision.decision_id}`);
  const mappedIds = [...new Set(decision.mapping.flatMap((mapping) => mapping.new_item_ids))].sort();
  const resultIds = decision.result_items.map((result) => result.id).sort();
  if (JSON.stringify(mappedIds) !== JSON.stringify(resultIds)) throw new Error(`Decision mappingとSurface/Atomic behavior resultが一致しません: ${decision.decision_id}`);
  if (decision.action === "exclude" && decision.mapping.some((mapping) => mapping.new_item_ids.length !== 0)) throw new Error(`excludeはnew itemへmappingできません: ${decision.decision_id}`);
  if (decision.action === "include" && decision.mapping.some((mapping) => mapping.new_item_ids.length === 0)) throw new Error(`includeには旧→新mappingが必要です: ${decision.decision_id}`);
  if (decision.action === "include" && new Set(decision.mapping.flatMap((mapping) => mapping.new_item_ids)).size !== decision.mapping.reduce((count, mapping) => count + mapping.new_item_ids.length, 0)) throw new Error(`includeでnew item IDを共有する場合はmerge decisionが必要です: ${decision.decision_id}`);
  if (decision.action === "merge" && (decision.anchor_ids.length < 2 || decision.mapping.some((mapping) => mapping.new_item_ids.length === 0) || new Set(resultSets).size !== 1)) throw new Error(`merge mappingが不正です: ${decision.decision_id}`);
  if (decision.action === "split" && (decision.anchor_ids.length !== 1 || decision.mapping[0]!.new_item_ids.length < 2)) throw new Error(`split mappingが不正です: ${decision.decision_id}`);
}

export function validateAuthorityReviewDecisions(decisions: ReviewDecision[], itemById: Map<string, AuthorityReviewQueueItem>): Set<string> {
  const decisionIds = new Set<string>();
  const decidedAnchors = new Set<string>();
  const newItemOwner = new Map<string, string>();
  for (const decision of decisions) {
    if (decisionIds.has(decision.decision_id)) throw new Error(`Decision IDが重複しています: ${decision.decision_id}`);
    decisionIds.add(decision.decision_id);
    validateDecision(decision, itemById, decidedAnchors);
    for (const id of new Set(decision.mapping.flatMap((mapping) => mapping.new_item_ids))) {
      const owner = newItemOwner.get(id);
      if (owner && owner !== decision.decision_id) throw new Error(`new item IDが複数decisionで共有されています: ${id}`);
      newItemOwner.set(id, decision.decision_id);
    }
  }
  return decidedAnchors;
}

export async function verifyAuthorityReviewQueue(root: string): Promise<AuthorityReviewQueueIndex> {
  const expected = await buildAuthorityReviewQueue(root);
  const index = JSON.parse(await readFile(path.join(root, authorityReviewQueueIndexPath), "utf8")) as AuthorityReviewQueueIndex;
  exactKeys(index, ["schema_version", "atlas_id", "generated_at", "status", "queue_id", "input_digest", "tool_digest", "decision_ledger", "body_storage", "machine_assistance", "semantic_decisions", "summary", "batches", "stale_holds"], "Review queue index");
  if (JSON.stringify(index) !== JSON.stringify(expected.index)) throw new Error("Authority review queue indexが入力・tool・batch実体の期待値と一致しません。");
  const files = (await readdir(path.join(root, authorityReviewQueueDirectory))).filter((file) => file.endsWith(".json")).sort();
  const expectedFiles = expected.batches.map((batch) => `${batch.batch_id}.json`).sort();
  if (JSON.stringify(files) !== JSON.stringify(expectedFiles)) throw new Error("Authority review batch file集合が不正です。");
  const itemById = new Map<string, AuthorityReviewQueueItem>();
  for (const batch of expected.batches) {
    const actual = JSON.parse(await readFile(path.join(root, authorityReviewQueueDirectory, `${batch.batch_id}.json`), "utf8")) as AuthorityReviewQueueBatch;
    exactKeys(actual, ["schema_version", "queue_id", "batch_id", "status", "machine_assistance", "semantic_decisions", "items"], `Review batch ${batch.batch_id}`);
    if (JSON.stringify(actual) !== JSON.stringify(batch)) throw new Error(`Review batchが決定論生成値と一致しません: ${batch.batch_id}`);
    for (const item of actual.items) {
      exactKeys(item, ["anchor_id", "document_id", "document_url", "source_ids", "locked_source_digest", "inventory_tool_digest", "review_queue_tool_digest", "locator", "locator_kind", "semantic_kind", "tag", "heading_level", "parent_anchor_id", "context_start", "context_end", "context_unit", "context_digest", "label_digest", "existing_reference_edge_ids", "priority", "priority_reasons", "candidate_cluster_id", "batch_id", "state"], `Review item ${item.anchor_id}`);
      if (itemById.has(item.anchor_id)) throw new Error(`Review queue anchorが重複しています: ${item.anchor_id}`);
      itemById.set(item.anchor_id, item);
    }
  }
  const ledger = JSON.parse(await readFile(path.join(root, authorityReviewDecisionPath), "utf8")) as ReviewDecisionLedger;
  exactKeys(ledger, ["schema_version", "atlas_id", "queue_id", "status", "decisions"], "Review decision ledger");
  if (ledger.schema_version !== 1 || ledger.atlas_id !== "frontend-behavior-atlas" || ledger.queue_id !== index.queue_id || ledger.status !== "incomplete-human-review-required") throw new Error("Review decision ledger identity/statusが不正です。");
  const decidedAnchors = validateAuthorityReviewDecisions(ledger.decisions, itemById);
  if (itemById.size !== index.summary.queued_anchors || decidedAnchors.size !== index.summary.human_reviewed || index.summary.pending_human !== itemById.size - decidedAnchors.size) throw new Error("Review queue pending/human集計が不正です。");
  console.log(`Verified Authority review queue: ${itemById.size} stable anchors in ${index.summary.batches} batches, ${index.summary.candidate_clusters} machine candidate clusters, ${index.summary.stale_document_holds} stale holds, ${ledger.decisions.length} human decisions.`);
  return index;
}
