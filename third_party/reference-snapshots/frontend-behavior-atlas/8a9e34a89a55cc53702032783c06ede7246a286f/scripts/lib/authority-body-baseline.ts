import { readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import {
  authorityBodyInventoryIndexPath,
  type AuthorityBodyInventoryArtifact,
  type AuthorityBodyInventoryIndex,
} from "./authority-body-inventory";

export const authorityBodyBaselinePath = "baselines/authority-body-inventory-v1.json";
export const authorityBodyMigrationPath = "migrations/authority-body-inventory-v1.json";

export type AuthorityBodyBaseline = {
  schema_version: 1;
  id: "authority-body-inventory-v1-2026-08-28";
  captured_at: "2026-08-28T00:00:00+09:00";
  source_entries: number;
  unique_documents: number;
  selector_contract: string[];
  documents: Array<{
    id: string;
    path: string;
    locked_body_digest: string;
    source_ids: string[];
    anchor_ids: string[];
  }>;
};

type AuthorityBodyMigration = {
  schema_version: 1;
  baseline_id: AuthorityBodyBaseline["id"];
  replacements: Array<{
    old_anchor_id: string;
    new_anchor_ids: string[];
    execution_proof: string;
    migration_evidence: string;
    reason: string;
  }>;
};

async function readJson<T>(root: string, relativePath: string): Promise<T> {
  return JSON.parse(await readFile(path.join(root, relativePath), "utf8")) as T;
}

export async function buildAuthorityBodyBaseline(root: string): Promise<AuthorityBodyBaseline> {
  const index = await readJson<AuthorityBodyInventoryIndex>(root, authorityBodyInventoryIndexPath);
  const documents = await Promise.all(index.documents.map(async (record) => {
    const artifact = await readJson<AuthorityBodyInventoryArtifact>(root, record.path);
    return {
      id: artifact.document_id,
      path: record.path,
      locked_body_digest: artifact.locked_body_digest,
      source_ids: [...artifact.source_ids],
      anchor_ids: artifact.anchors.map((anchor) => anchor.id).sort(),
    };
  }));
  documents.sort((left, right) => left.id.localeCompare(right.id));
  return {
    schema_version: 1,
    id: "authority-body-inventory-v1-2026-08-28",
    captured_at: "2026-08-28T00:00:00+09:00",
    source_entries: index.summary.source_entries,
    unique_documents: index.summary.unique_documents,
    selector_contract: [...index.selector_contract],
    documents,
  };
}

function exactKeys(value: object, expected: string[], label: string): void {
  const actual = Object.keys(value).sort();
  const required = [...expected].sort();
  if (JSON.stringify(actual) !== JSON.stringify(required)) throw new Error(`${label}のfield集合が不正です: ${actual.join(",")}`);
}

export async function verifyAuthorityBodyBaseline(root: string): Promise<void> {
  const baseline = await readJson<AuthorityBodyBaseline>(root, authorityBodyBaselinePath);
  const migration = await readJson<AuthorityBodyMigration>(root, authorityBodyMigrationPath);
  const index = await readJson<AuthorityBodyInventoryIndex>(root, authorityBodyInventoryIndexPath);
  exactKeys(baseline, ["schema_version", "id", "captured_at", "source_entries", "unique_documents", "selector_contract", "documents"], "Authority body baseline");
  exactKeys(migration, ["schema_version", "baseline_id", "replacements"], "Authority body migration");
  if (baseline.schema_version !== 1 || baseline.id !== "authority-body-inventory-v1-2026-08-28" || baseline.captured_at !== "2026-08-28T00:00:00+09:00") throw new Error("Authority body baseline identityが不正です。");
  if (migration.schema_version !== 1 || migration.baseline_id !== baseline.id) throw new Error("Authority body migration identityが不正です。");
  if (index.summary.source_entries < baseline.source_entries || index.summary.unique_documents < baseline.unique_documents || JSON.stringify(index.selector_contract) !== JSON.stringify(baseline.selector_contract)) throw new Error("Authority body inventoryのSource/document/selector floorが縮小しています。");
  if (baseline.documents.length !== new Set(baseline.documents.map((item) => item.id)).size) throw new Error("Authority body baseline document IDが重複しています。");
  const baselineAnchorIds = new Set(baseline.documents.flatMap((item) => item.anchor_ids));
  if (baselineAnchorIds.size !== baseline.documents.reduce((count, item) => count + item.anchor_ids.length, 0)) throw new Error("Authority body baseline anchor IDがdocument間で重複しています。");

  const currentByDocument = new Map<string, AuthorityBodyInventoryArtifact>();
  const currentAnchorIds = new Set<string>();
  for (const record of index.documents) {
    const artifact = await readJson<AuthorityBodyInventoryArtifact>(root, record.path);
    currentByDocument.set(artifact.document_id, artifact);
    for (const anchor of artifact.anchors) {
      if (currentAnchorIds.has(anchor.id)) throw new Error(`Current Authority anchor IDがdocument間で重複しています: ${anchor.id}`);
      currentAnchorIds.add(anchor.id);
    }
  }

  const replacementByOld = new Map<string, AuthorityBodyMigration["replacements"][number]>();
  const replacementNewIds = new Set<string>();
  for (const item of migration.replacements) {
    exactKeys(item, ["old_anchor_id", "new_anchor_ids", "execution_proof", "migration_evidence", "reason"], `Authority anchor migration ${item.old_anchor_id}`);
    if (!baselineAnchorIds.has(item.old_anchor_id) || replacementByOld.has(item.old_anchor_id) || item.new_anchor_ids.length === 0 || new Set(item.new_anchor_ids).size !== item.new_anchor_ids.length || item.execution_proof === item.migration_evidence || item.reason.length < 20) throw new Error(`Authority anchor migration mappingが不正です: ${item.old_anchor_id}`);
    for (const newId of item.new_anchor_ids) {
      if (!currentAnchorIds.has(newId) || replacementNewIds.has(newId)) throw new Error(`Authority anchor replacementが現行IDでないか共有されています: ${newId}`);
      replacementNewIds.add(newId);
    }
    for (const proofPath of [item.execution_proof, item.migration_evidence]) if (!(await stat(path.join(root, proofPath)).catch(() => null))) throw new Error(`Authority anchor migration Evidenceがありません: ${proofPath}`);
    replacementByOld.set(item.old_anchor_id, item);
  }

  let baselineAnchors = 0;
  let retained = 0;
  let replaced = 0;
  for (const expected of baseline.documents) {
    exactKeys(expected, ["id", "path", "locked_body_digest", "source_ids", "anchor_ids"], `Authority baseline document ${expected.id}`);
    const current = currentByDocument.get(expected.id);
    if (!current || expected.path !== index.documents.find((record) => record.id === expected.id)?.path || current.locked_body_digest !== expected.locked_body_digest || JSON.stringify(current.source_ids) !== JSON.stringify(expected.source_ids)) throw new Error(`Authority body baseline documentが削除または置換されています: ${expected.id}`);
    if (expected.anchor_ids.length !== new Set(expected.anchor_ids).size) throw new Error(`Authority body baseline anchor IDが重複しています: ${expected.id}`);
    for (const anchorId of expected.anchor_ids) {
      baselineAnchors += 1;
      if (currentAnchorIds.has(anchorId)) retained += 1;
      else if (replacementByOld.has(anchorId)) replaced += 1;
      else throw new Error(`Authority body anchorがMappingなしで削除されています: ${anchorId}`);
    }
  }
  for (const oldId of replacementByOld.keys()) if (currentAnchorIds.has(oldId)) throw new Error(`Authority body migrationは現存IDを置換扱いにできません: ${oldId}`);
  const report = {
    schema_version: 1,
    baseline_id: baseline.id,
    baseline_anchors: baselineAnchors,
    current_anchors: currentAnchorIds.size,
    retained,
    replaced,
    added: currentAnchorIds.size - retained - replacementNewIds.size,
    document_floor: `${baseline.documents.length}/${currentByDocument.size}`,
    status: "pass",
  };
  await writeFile(path.join(root, "artifacts/authority-body-non-regression-report.json"), `${JSON.stringify(report, null, 2)}\n`);
  console.log(`Authority body non-regression verified: ${retained}/${baselineAnchors} anchors retained, ${replaced} replaced, ${report.added} added, documents ${report.document_floor}.`);
}
