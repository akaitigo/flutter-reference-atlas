import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import {
  masteryOutcomes,
  masterySurfaces,
  outcomeExecutionContracts,
  type MasteryOutcomeId,
  type MasterySurfaceId,
} from "./mastery-contract";

type AdvisorRequest = {
  id: string;
  outcome: MasteryOutcomeId;
  surface: MasterySurfaceId;
  query: string;
  authorized_change?: boolean;
  authority_semantic_decision?: boolean;
  stale_source_relock?: boolean;
};

type AdvisorPlan = Record<string, unknown> & {
  id: string;
  status: string;
  outcome: string;
  surface: string;
  mode: string;
  pattern_id: string | null;
  target_id: string | null;
  target_set: string | null;
  target_set_allowed?: boolean;
  coverage_state: string;
  coverage_disposition: string;
  required_deliverables: string[];
  required_output_fields: string[];
  mutation_policy: string;
  mutation_status: string;
  blocked_reasons: string[];
  stop_conditions: string[];
  implementation_bindings: Array<{ id: string; path: string; digest: string }>;
  source_bindings: Array<{ url: string; digest: string; bytes: number }>;
  evidence_bindings: Array<{ path: string; digest: string; bytes: number; claim_scope: string }>;
  evidence_records?: { capture_ids: string[]; benchmark_ids: string[]; compatibility_ids: string[]; local_e2e_status: string; container_e2e_status: string };
};

const exemplarBySurface: Record<MasterySurfaceId, { query: string; pattern_id: string }> = {
  "orientation-scope": { query: "build a learning path tied to reproducible releases", pattern_id: "production/learning-paths-and-releases" },
  "foundations-mechanics": { query: "smooth acceleration", pattern_id: "foundations/easing-curve" },
  "architecture-design": { query: "prove every listener timer and observer is cleaned up", pattern_id: "production/lifecycle-resource-cleanup" },
  "implementation-construction": { query: "open a searchable command menu with a shortcut then enter a nested scope", pattern_id: "interaction/command-palette" },
  "testing-verification": { query: "review deterministic visual diffs without hiding changes", pattern_id: "production/visual-regression-evidence" },
  "failure-recovery": { query: "queue optimistic work offline and replay it safely", pattern_id: "reactive/network-offline-recovery" },
  "operations-observability": { query: "pause animation offscreen and in background tabs", pattern_id: "production/offscreen-background-suspension" },
  "security-privacy-safety": { query: "sandbox an experiment and deny undeclared capabilities", pattern_id: "production/deployment-security-capabilities" },
  "performance-capacity-cost": { query: "degrade visual quality before interaction performance", pattern_id: "production/performance-energy-budgets" },
  "compatibility-integration": { query: "expire browser support claims until they are retested", pattern_id: "production/compatibility-evidence-expiry" },
  "migration-evolution-deprecation": { query: "audit the full dependency graph before updating", pattern_id: "production/dependency-version-policy" },
  "decision-comparison": { query: "keep a tooltip open across the hover gap and flip it at the viewport edge", pattern_id: "interaction/tooltip-popover-positioning" },
  "provenance-rights": { query: "track source license originality and removable assets", pattern_id: "production/provenance-originality-rights" },
  "agent-skill": { query: "evaluate agent routing implementation and review", pattern_id: "production/agent-retrieval-implementation-evals" },
};

function exemplarFor(outcome: MasteryOutcomeId, surface: MasterySurfaceId): { query: string; pattern_id: string } {
  if (outcome === "operate" && surface === "implementation-construction") {
    return { query: "move canvas drawing to a worker without flooding it with stale render messages", pattern_id: "graphics/offscreen-canvas-worker" };
  }
  if (outcome === "operate" && surface === "decision-comparison") {
    return { query: "degrade visual quality before interaction performance", pattern_id: "production/performance-energy-budgets" };
  }
  return exemplarBySurface[surface];
}

const outcomePrompt: Record<MasteryOutcomeId, string> = {
  understand: "原理と境界を理解したい",
  choose: "制約から方式を選びたい",
  build: "許可された範囲へ実装したい",
  verify: "主張を証拠で検証したい",
  operate: "Lifecycleを監視して運用したい",
  troubleshoot: "失敗を再現して復旧したい",
  evolve: "非後退で移行したい",
  delegate: "停止条件付きで委任してReviewしたい",
};

const sha256 = (value: string | Buffer) => `sha256:${createHash("sha256").update(value).digest("hex")}`;
const equal = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right);

function matrixRequests(): AdvisorRequest[] {
  return masteryOutcomes.flatMap((outcome) => masterySurfaces.map((surface) => ({
    id: `skill.${outcome.id}.${surface.id}`,
    outcome: outcome.id,
    surface: surface.id,
    query: `${exemplarFor(outcome.id, surface.id).query} ${outcomePrompt[outcome.id]}`,
    authorized_change: outcomeExecutionContracts[outcome.id].mutation_policy === "explicit-authorization-required",
  })));
}

async function loadPlanner(root: string): Promise<{ planAdvisorRequests: (requests: AdvisorRequest[], root?: string) => Promise<AdvisorPlan[]> }> {
  const moduleUrl = pathToFileURL(path.join(root, ".agents/skills/fe-behavior-advisor/scripts/advisor-router.mjs")).href;
  return await import(moduleUrl) as { planAdvisorRequests: (requests: AdvisorRequest[], root?: string) => Promise<AdvisorPlan[]> };
}

function evaluateMatrixPlan(plan: AdvisorPlan, request: AdvisorRequest): { result: "pass" | "fail"; support_status: "routed" | "mastery-routing-gap"; assertions: Record<string, boolean> } {
  const outcome = masteryOutcomes.find((candidate) => candidate.id === request.outcome)!;
  const surface = masterySurfaces.find((candidate) => candidate.id === request.surface)!;
  const execution = outcomeExecutionContracts[request.outcome];
  const exemplar = exemplarFor(request.outcome, request.surface);
  const targetSetIntersection = outcome.target_sets.filter((targetSet) => surface.target_sets.includes(targetSet as never));
  const shouldRoute = targetSetIntersection.length > 0;
  const assertions = {
    identity: plan.id === request.id && plan.outcome === request.outcome && plan.surface === request.surface,
    pattern: plan.pattern_id === exemplar.pattern_id,
    mode: plan.mode === execution.mode,
    target_set_contract: plan.target_set_allowed === shouldRoute && (shouldRoute ? targetSetIntersection.includes(plan.target_set as never) : true),
    coverage_honesty: plan.coverage_state === "partial" && plan.coverage_disposition === (shouldRoute ? "coverage-gap" : "mastery-routing-gap"),
    deliverables: equal(plan.required_deliverables, surface.required_deliverables),
    output_contract: equal(plan.required_output_fields, execution.required_output_fields),
    permission_boundary: plan.mutation_policy === execution.mutation_policy && plan.blocked_reasons.length === 0 && plan.mutation_status === (execution.mutation_policy === "read-only" ? "read-only" : "authorized-for-request-scope"),
    implementation_binding: plan.implementation_bindings.length >= 2 && plan.implementation_bindings.every((binding) => binding.path.startsWith(`experiments/${plan.pattern_id}/`) && /^sha256:[a-f0-9]{64}$/.test(binding.digest)),
    authority_binding: plan.source_bindings.length >= 1 && plan.source_bindings.every((binding) => /^https:\/\//.test(binding.url) && /^sha256:[a-f0-9]{64}$/.test(binding.digest) && binding.bytes > 0),
    evidence_binding: plan.evidence_bindings.length === 6 && plan.evidence_bindings.every((binding) => /^sha256:[a-f0-9]{64}$/.test(binding.digest) && binding.bytes > 0 && binding.claim_scope.length > 0),
    pattern_evidence_records: Boolean(plan.evidence_records && plan.evidence_records.capture_ids.length >= 1 && plan.evidence_records.benchmark_ids.length >= 2 && plan.evidence_records.compatibility_ids.length === 3 && plan.evidence_records.local_e2e_status === "passed" && plan.evidence_records.container_e2e_status === "passed"),
    stop_conditions: plan.stop_conditions.includes("coverage-gap") && plan.stop_conditions.includes("unauthorized-mutation") && plan.stop_conditions.includes("external-human-decision-required"),
  };
  return {
    result: Object.values(assertions).every(Boolean) ? "pass" : "fail",
    support_status: shouldRoute ? "routed" : "mastery-routing-gap",
    assertions,
  };
}

export async function runDefinitiveSkillEval(root: string): Promise<void> {
  const planner = await loadPlanner(root);
  const requests = matrixRequests();
  const plans = await planner.planAdvisorRequests(requests, root);
  if (plans.length !== requests.length) throw new Error(`Definitive Skill Matrix plan count mismatch: ${plans.length}/${requests.length}`);
  const matrix = plans.map((plan, index) => {
    const request = requests[index]!;
    const evaluation = evaluateMatrixPlan(plan, request);
    return { ...plan, expected_pattern_id: exemplarFor(request.outcome, request.surface).pattern_id, ...evaluation };
  });

  const boundaryRequests: AdvisorRequest[] = [
    { id: "boundary.ambiguous", outcome: "choose", surface: "decision-comparison", query: "drag the element" },
    { id: "boundary.unknown", outcome: "understand", surface: "orientation-scope", query: "quantum hologram telepathy interface" },
    { id: "boundary.unauthorized-build", outcome: "build", surface: "implementation-construction", query: exemplarBySurface["implementation-construction"].query },
    { id: "boundary.human-authority-decision", outcome: "delegate", surface: "agent-skill", query: exemplarBySurface["agent-skill"].query, authorized_change: true, authority_semantic_decision: true },
    { id: "boundary.stale-relock", outcome: "evolve", surface: "provenance-rights", query: exemplarBySurface["provenance-rights"].query, authorized_change: true, stale_source_relock: true },
  ];
  const boundaryPlans = await planner.planAdvisorRequests(boundaryRequests, root);
  const expectedBoundary: Record<string, { pattern_id: string | null; status: string; blocked_reason?: string }> = {
    "boundary.ambiguous": { pattern_id: null, status: "coverage-gap" },
    "boundary.unknown": { pattern_id: null, status: "coverage-gap" },
    "boundary.unauthorized-build": { pattern_id: exemplarBySurface["implementation-construction"].pattern_id, status: "blocked", blocked_reason: "unauthorized-mutation" },
    "boundary.human-authority-decision": { pattern_id: exemplarBySurface["agent-skill"].pattern_id, status: "blocked", blocked_reason: "external-human-decision-required" },
    "boundary.stale-relock": { pattern_id: exemplarBySurface["provenance-rights"].pattern_id, status: "blocked", blocked_reason: "stale-source-relock-explicit-procedure-required" },
  };
  const boundary_cases = boundaryPlans.map((plan) => {
    const expected = expectedBoundary[plan.id]!;
    const result = plan.pattern_id === expected.pattern_id && plan.status === expected.status && (!expected.blocked_reason || plan.blocked_reasons.includes(expected.blocked_reason)) ? "pass" : "fail";
    return { ...plan, expected, result };
  });
  const failedMatrix = matrix.filter((item) => item.result !== "pass");
  const failedBoundaries = boundary_cases.filter((item) => item.result !== "pass");
  const routingGaps = matrix.filter((item) => item.support_status === "mastery-routing-gap");
  const sourcePaths = {
    mastery_contract_source: "scripts/lib/mastery-contract.ts",
    evaluator: "scripts/lib/definitive-skill-eval.ts",
    router: ".agents/skills/fe-behavior-advisor/scripts/advisor-router.mjs",
    skill: ".agents/skills/fe-behavior-advisor/SKILL.md",
    generated_mastery_contract: ".agents/skills/fe-behavior-advisor/references/mastery-contract.json",
    legacy_skill_eval: "evals/fe-behavior-advisor.skill-eval.json",
  } as const;
  const sourceBindings = Object.fromEntries(await Promise.all(Object.entries(sourcePaths).map(async ([id, relativePath]) => {
    const bytes = await readFile(path.join(root, relativePath));
    return [id, { path: relativePath, digest: sha256(bytes), bytes: bytes.byteLength }];
  })));
  const artifact = {
    schema_version: 1,
    id: "fe-behavior-advisor.definitive-mastery-v1",
    atlas_id: "frontend-behavior-atlas",
    generated_at: "2026-08-28T00:00:00+09:00",
    status: routingGaps.length === 0 ? "evaluated-not-completion-certificate" : "incomplete-mastery-routing-gaps",
    semantic_scope: "deterministic-router-contract-not-independent-agent-forward-eval",
    source_bindings: sourceBindings,
    summary: {
      outcomes: masteryOutcomes.length,
      surfaces: masterySurfaces.length,
      matrix_cells: matrix.length,
      passed: matrix.length - failedMatrix.length,
      failed: failedMatrix.length,
      routed: matrix.length - routingGaps.length,
      mastery_routing_gaps: routingGaps.length,
      partial_coverage_cells: matrix.filter((item) => item.coverage_state === "partial").length,
      boundary_cases: boundary_cases.length,
      boundary_passed: boundary_cases.length - failedBoundaries.length,
      boundary_failed: failedBoundaries.length,
    },
    completion_limits: [
      "全Coverage Targetがpartialであり、matrix passはTarget completeを意味しない。",
      "operate/troubleshoot × foundations-mechanicsはMastery target_set交差がなくrouting gapである。",
      "実Projectへの変更品質を測る独立Agent forward evalは未実施である。",
      "人によるAuthority semantic decisionをAgent結果として扱わない。",
    ],
    matrix,
    boundary_cases,
  };
  await writeFile(path.join(root, "evals/fe-behavior-advisor.definitive-skill-eval.json"), `${JSON.stringify(artifact, null, 2)}\n`);
  if (matrix.length !== masteryOutcomes.length * masterySurfaces.length || failedMatrix.length > 0 || failedBoundaries.length > 0) {
    throw new Error(`Definitive Skill Eval failed: matrix=${failedMatrix.length}, boundary=${failedBoundaries.length}`);
  }
  console.log(`Definitive Skill Eval: ${matrix.length}/${matrix.length} cells contract-pass, ${matrix.length - routingGaps.length} routed, ${routingGaps.length} mastery routing gaps, boundary ${boundary_cases.length}/${boundary_cases.length}.`);
}
