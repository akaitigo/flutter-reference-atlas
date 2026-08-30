import assert from "node:assert/strict";
import { buildAuthorityReviewQueue, validateAuthorityReviewDecisions, type ReviewDecision } from "./lib/authority-review-queue";

const built = await buildAuthorityReviewQueue(process.cwd());
const items = built.batches.flatMap((batch) => batch.items);
assert.equal(new Set(items.map((item) => item.anchor_id)).size, items.length);
assert.equal(items.length, built.index.summary.queued_anchors);
assert.equal(items.every((item) => item.state === "pending-human"), true);
assert.equal(items.every((item) => item.review_queue_tool_digest === built.index.tool_digest), true);
assert.equal(built.index.stale_holds.length, 3);
assert.equal(built.emptyLedger.decisions.length, 0);
assert.equal(built.index.semantic_decisions, "human-only");
const first = items[0]!;
const validDecision: ReviewDecision = {
  decision_id: "decision.contract-test.include",
  action: "include",
  anchor_ids: [first.anchor_id],
  source_bindings: [{
    anchor_id: first.anchor_id,
    document_id: first.document_id,
    document_url: first.document_url,
    locked_source_digest: first.locked_source_digest,
    inventory_tool_digest: first.inventory_tool_digest,
    review_queue_tool_digest: first.review_queue_tool_digest,
    locator: first.locator,
    context_start: first.context_start,
    context_end: first.context_end,
    context_unit: first.context_unit,
    context_digest: first.context_digest,
  }],
  rationale: "一次資料のlocatorを人が確認し、独立したobservable surfaceとして保持する判断を記録するためのcontract testです。",
  reviewer: "human-reviewer",
  reviewed_at: "2026-08-28T12:00:00+09:00",
  review_method: "manual-primary-source",
  mapping: [{ old_anchor_id: first.anchor_id, new_item_ids: ["surface.contract-test"] }],
  result_items: [{ id: "surface.contract-test", item_type: "surface" }],
};
assert.equal(validateAuthorityReviewDecisions([validDecision], new Map([[first.anchor_id, first]])).size, 1);
assert.throws(() => validateAuthorityReviewDecisions([{ ...validDecision, reviewer: "automated-bot" }], new Map([[first.anchor_id, first]])), /人手review provenance/);
assert.throws(() => validateAuthorityReviewDecisions([{ ...validDecision, result_items: [] }], new Map([[first.anchor_id, first]])), /mappingとSurface\/Atomic behavior result/);
console.log(`Authority review queue tests passed: ${items.length} stable pending-human anchors.`);
