import { writeAuthorityReviewQueue } from "./lib/authority-review-queue";

const index = await writeAuthorityReviewQueue(process.cwd());
console.log(`Generated Authority review queue: ${index.summary.queued_anchors} anchors / ${index.summary.batches} batches / ${index.summary.stale_document_holds} stale holds.`);
