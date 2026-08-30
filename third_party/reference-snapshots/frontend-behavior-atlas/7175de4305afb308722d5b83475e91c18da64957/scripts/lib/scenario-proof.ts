import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { loadRegistry } from "./registry";

export const scenarioIds = ["normal", "boundary", "refusal", "failure", "recovery", "migration", "operations", "security", "performance", "compatibility"] as const;
export type ScenarioId = typeof scenarioIds[number];
export const scenarioProofRoot = "evidence/scenarios";
export const scenarioProofIndexPath = `${scenarioProofRoot}/index.json`;

type CaptureRecord = { id: string; sourceHash: string; output: string; imageHash: string; bytes: number };
type BenchmarkRecord = { id: string; patternId: string; variantId: string; sourceHash: string; status: string; metrics: Record<string, number>; budgets: Record<string, number> };
type CompatibilityRecord = { id: string; project: string; patternId: string; outcome: string; attempts: number; finalStatus: string; error: string | null };
type ReferenceTest = { scenario: string; outcome: string; attempts: number; final_status: string; trace: { path: string; digest: string; bytes: number }; screenshot: { path: string; digest: string; bytes: number } };
type CaptureEnvironment = { profile: string; node: string; platform: string; architecture: string; playwright: string; browserName: string; browserVersion: string; browserChannel: string; workers: number; retries: number; viewport: { width: number; height: number; deviceScaleFactor: number } };
type PatternScenarioEnvironment = { node: string; platform: string; architecture: string; playwright: string; browser_name: string; browser_version: string; browser_channel: string; workers: number; retries: number; viewport: { width: number; height: number; device_scale_factor: number }; trace_mode: string };
type PatternScenarioTest = { pattern_id: string; variant_id: string; scenario: string; source_digest: string; outcome: string; attempts: number; final_status: string; error: string | null; oracle: Record<string, unknown>; trace: { path: string; digest: string; bytes: number; action_stream: boolean; network_stream: boolean; resource_stream: boolean }; screenshot: { path: string; digest: string; bytes: number } };

export type ScenarioProof = {
  schema_version: 1;
  id: string;
  atlas_id: "frontend-behavior-atlas";
  generated_at: string;
  behavior_scope: "current-domain-pattern-not-authority-atomic";
  pattern_id: string;
  target_id: string;
  target_set: string;
  scenario: ScenarioId;
  status: "bounded-runtime-proof" | "bounded-capture-proof" | "pattern-specific-gap";
  classification: { method: string; matcher_digest: string; state_ids: string[]; semantic_scope_match: boolean };
  source_bindings: Array<{ variant_id: string; path: string; digest: string }>;
  pattern_evidence: {
    capture_environment_identity: CaptureEnvironment;
    capture_harness_digest: string;
    capture_records: CaptureRecord[];
    benchmark_environment: Record<string, unknown> | null;
    benchmark_records: BenchmarkRecord[];
    compatibility_environment: Record<string, unknown> | null;
    compatibility_records: CompatibilityRecord[];
    scenario_runtime_report: string | null;
    scenario_runtime_environment: PatternScenarioEnvironment | null;
    scenario_runtime_records: PatternScenarioTest[];
  };
  integrated_reference: {
    manifest: string;
    result: string;
    pattern_mapped: boolean;
    runtime_boundaries: string[];
    assertions: string[];
    outcome: string;
    attempts: number;
    trace: ReferenceTest["trace"];
    screenshot: ReferenceTest["screenshot"];
  };
  closure: {
    dedicated_row: true;
    dedicated_artifact: true;
    pattern_specific_evidence: boolean;
    real_runtime_identity: boolean;
    integrated_runtime_trace: true;
    authority_atomic_behavior: false;
    completion_eligible: false;
  };
  gaps: string[];
};

export type ScenarioProofIndex = {
  schema_version: 1;
  id: "frontend-scenario-proof-matrix-v1";
  atlas_id: "frontend-behavior-atlas";
  generated_at: string;
  status: "incomplete-authority-atomic-and-runtime-closure";
  denominator: "85-current-domain-patterns-x-10-scenarios";
  tool_digest: string;
  source_digests: Record<string, string>;
  summary: {
    patterns: number;
    scenarios: number;
    rows: number;
    dedicated_artifacts: number;
    pattern_specific_rows: number;
    pattern_specific_runtime_rows: number;
    pattern_specific_capture_rows: number;
    pattern_specific_gaps: number;
    integrated_trace_rows: number;
    authority_atomic_rows: number;
    completion_eligible_rows: number;
  };
  by_scenario: Record<ScenarioId, { rows: number; pattern_specific: number; runtime_identity: number; integrated_pattern_mapped: number; gaps: number }>;
  files: Array<{ id: string; pattern_id: string; scenario: ScenarioId; path: string; digest: string; status: ScenarioProof["status"] }>;
  completion_limits: string[];
};

const sha256 = (value: string | Buffer) => `sha256:${createHash("sha256").update(value).digest("hex")}`;
const normalizedState = (state: unknown) => JSON.stringify(state).toLocaleLowerCase();
const stateMatchers: Partial<Record<ScenarioId, RegExp>> = {
  normal: /initial|start|baseline|ready|rest|idle|closed|default|settled|overview|root|empty|static/,
  boundary: /stress|quarter|middle|midpoint|end|complete|max|min|narrow|wide|zoom|rtl|vertical|reduced|coarse|partial|overflow|edge|clamp|heavy|high-load|last|upper-right|lower-left|rotated/,
  refusal: /denied|refus|reject|blocked|unsupported|unavailable|forbidden/,
  failure: /fail|error|lost|offline|disconnect|missing|invalid|timeout|expired|persistent-error/,
  recovery: /recover|restore|reconnect|reset|retry|fallback|returned|resume|released|undone/,
};
const semanticMatchers: Partial<Record<ScenarioId, RegExp>> = {
  migration: /dependency-version-policy|compatibility-evidence-expiry|ssr-hydration-continuity|contribution-admission|migrat|upgrade|legacy|deprecat|schema version|hydration continuity/,
  operations: /lifecycle-resource-cleanup|offscreen-background-suspension|idle-and-presence-state|background-sync-status|network-offline-recovery|audio-transport|video-player-state|realtime-presence|streaming-data|resource cleanup|observability|suspension/,
  security: /deployment-security-capabilities|provenance-originality-rights|permission-capability-state|camera-preview-permission|microphone-level-permission|device-motion-orientation|security|privacy|permission|sandbox|capability grant|publication rights/,
};
const matcherDigest = sha256(JSON.stringify({ state: Object.fromEntries(Object.entries(stateMatchers).map(([id, matcher]) => [id, matcher?.source])), semantic: Object.fromEntries(Object.entries(semanticMatchers).map(([id, matcher]) => [id, matcher?.source])) }));

function classifyStates(pattern: { id: string; title: string; summary: string; intent: string; retrieval: { acceptanceCriteria: string[] }; testStates: Array<{ id: string; label: string }> }, scenario: ScenarioId): { states: typeof pattern.testStates; semanticMatch: boolean; method: string } {
  if (scenario === "performance" || scenario === "compatibility") return { states: [], semanticMatch: true, method: `${scenario}-record-identity` };
  const semantic = [pattern.id, pattern.title, pattern.summary, pattern.intent, ...pattern.retrieval.acceptanceCriteria, ...pattern.testStates.map((state) => normalizedState(state))].join(" ").toLocaleLowerCase();
  const semanticMatcher = semanticMatchers[scenario];
  if (semanticMatcher) {
    const semanticMatch = semanticMatcher.test(semantic);
    return { states: semanticMatch ? pattern.testStates : [], semanticMatch, method: "pattern-semantic-scope-and-explicit-state" };
  }
  const stateMatcher = stateMatchers[scenario]!;
  const states = pattern.testStates.filter((state) => stateMatcher.test(normalizedState(state)));
  return { states, semanticMatch: states.length > 0, method: "explicit-state-id-label-value" };
}

async function fileDigest(root: string, relativePath: string): Promise<string> { return sha256(await readFile(path.join(root, relativePath))); }

export async function generateScenarioProofMatrix(root: string): Promise<ScenarioProofIndex> {
  const registry = await loadRegistry(root);
  const coverage = JSON.parse(await readFile(path.join(root, "coverage/targets.json"), "utf8")) as { targets: Array<{ id: string; release: string; patternIds: string[] }> };
  const captures = JSON.parse(await readFile(path.join(root, "artifacts/capture-results.json"), "utf8")) as { environment: CaptureEnvironment; harnessHash: string; captures: CaptureRecord[] };
  const benchmarks = JSON.parse(await readFile(path.join(root, "artifacts/benchmark-results.json"), "utf8")) as { environment: Record<string, unknown>; results: BenchmarkRecord[] };
  const compatibility = JSON.parse(await readFile(path.join(root, "artifacts/compatibility-results.json"), "utf8")) as { browsers: Array<{ name: string; version: string }>; sourceDigest: string; harnessDigest: string; tests: CompatibilityRecord[] };
  const referenceManifest = JSON.parse(await readFile(path.join(root, "integrations/reference-system/manifest.json"), "utf8")) as { scenarios: Array<{ id: ScenarioId; patterns: string[]; runtime_boundaries: string[]; assertions: string[] }> };
  const referenceResults = JSON.parse(await readFile(path.join(root, "artifacts/reference-system/results.json"), "utf8")) as { environment: Record<string, unknown>; tests: ReferenceTest[] };
  const scenarioRuntime = JSON.parse(await readFile(path.join(root, "artifacts/pattern-scenarios/results.json"), "utf8")) as { status: string; environment: PatternScenarioEnvironment; tests: PatternScenarioTest[] };
  const captureById = new Map(captures.captures.map((record) => [record.id, record]));
  const targetByPattern = new Map(coverage.targets.flatMap((target) => target.patternIds.map((patternId) => [patternId, target] as const)));
  const referenceByScenario = new Map(referenceResults.tests.map((test) => [test.scenario as ScenarioId, test]));
  const manifestByScenario = new Map(referenceManifest.scenarios.map((scenario) => [scenario.id, scenario]));
  const outputRoot = path.join(root, scenarioProofRoot, "patterns");
  await rm(outputRoot, { recursive: true, force: true });
  const proofs: ScenarioProof[] = [];
  const files: ScenarioProofIndex["files"] = [];

  for (const pattern of registry.patterns) {
    const target = targetByPattern.get(pattern.id);
    if (!target) throw new Error(`Scenario matrix Pattern has no Coverage target: ${pattern.id}`);
    for (const scenario of scenarioIds) {
      const classification = classifyStates(pattern, scenario);
      const captureRecords = classification.states.flatMap((state) => pattern.variants.map((variant) => {
        const id = `${pattern.id}::${variant.id}::${state.id}`;
        const record = captureById.get(id);
        if (!record) throw new Error(`Scenario matrix Capture record is missing: ${id}`);
        return record;
      }));
      const benchmarkRecords = scenario === "performance" ? benchmarks.results.filter((record) => record.patternId === pattern.id) : [];
      const compatibilityRecords = scenario === "compatibility" ? compatibility.tests.filter((record) => record.patternId === pattern.id) : [];
      const scenarioRuntimeRecords = scenarioRuntime.tests.filter((record) => record.pattern_id === pattern.id && record.scenario === scenario);
      const hasDedicatedRuntimeProof = scenarioRuntime.status === "passed"
        && scenarioRuntimeRecords.length === pattern.variants.length
        && pattern.variants.every((variant) => scenarioRuntimeRecords.some((record) => record.variant_id === variant.id && record.outcome === "expected" && record.attempts === 1 && record.final_status === "passed" && record.error === null && record.trace.action_stream && record.trace.network_stream && record.trace.resource_stream));
      const hasCaptureProof = classification.states.length > 0 && captureRecords.length === classification.states.length * pattern.variants.length;
      const hasRuntimeProof = scenario === "performance"
        ? benchmarkRecords.length === pattern.variants.length && benchmarkRecords.every((record) => record.status === "passed")
        : scenario === "compatibility"
          ? compatibilityRecords.length === 3 && compatibilityRecords.every((record) => record.outcome === "expected" && record.attempts === 1 && record.finalStatus === "passed" && record.error === null)
          : hasDedicatedRuntimeProof || (hasCaptureProof && captures.environment.browserName === "chromium" && Boolean(captures.environment.browserVersion));
      const status: ScenarioProof["status"] = hasRuntimeProof ? "bounded-runtime-proof" : hasCaptureProof ? "bounded-capture-proof" : "pattern-specific-gap";
      const reference = referenceByScenario.get(scenario);
      const referenceMapping = manifestByScenario.get(scenario);
      if (!reference || !referenceMapping) throw new Error(`Reference System Scenario Evidence is missing: ${scenario}`);
      const proof: ScenarioProof = {
        schema_version: 1,
        id: `proof.pattern.${pattern.id.replaceAll("/", ".")}.${scenario}`,
        atlas_id: "frontend-behavior-atlas",
        generated_at: "2026-08-28T00:00:00+09:00",
        behavior_scope: "current-domain-pattern-not-authority-atomic",
        pattern_id: pattern.id,
        target_id: target.id,
        target_set: target.release,
        scenario,
        status,
        classification: { method: classification.method, matcher_digest: matcherDigest, state_ids: classification.states.map((state) => state.id), semantic_scope_match: classification.semanticMatch },
        source_bindings: pattern.variants.map((variant) => ({ variant_id: variant.id, path: `experiments/${pattern.id}/${variant.entry}`, digest: `sha256:${registry.artifacts.sourceHashes[`${pattern.id}::${variant.id}`]}` })),
        pattern_evidence: {
          capture_environment_identity: captures.environment,
          capture_harness_digest: `sha256:${captures.harnessHash}`,
          capture_records: captureRecords,
          benchmark_environment: scenario === "performance" ? benchmarks.environment : null,
          benchmark_records: benchmarkRecords,
          compatibility_environment: scenario === "compatibility" ? { browsers: compatibility.browsers, source_digest: `sha256:${compatibility.sourceDigest}`, harness_digest: `sha256:${compatibility.harnessDigest}` } : null,
          compatibility_records: compatibilityRecords,
          scenario_runtime_report: hasDedicatedRuntimeProof ? "artifacts/pattern-scenarios/results.json" : null,
          scenario_runtime_environment: hasDedicatedRuntimeProof ? scenarioRuntime.environment : null,
          scenario_runtime_records: hasDedicatedRuntimeProof ? scenarioRuntimeRecords : [],
        },
        integrated_reference: {
          manifest: "integrations/reference-system/manifest.json",
          result: "artifacts/reference-system/results.json",
          pattern_mapped: referenceMapping.patterns.includes(pattern.id),
          runtime_boundaries: referenceMapping.runtime_boundaries,
          assertions: referenceMapping.assertions,
          outcome: reference.outcome,
          attempts: reference.attempts,
          trace: reference.trace,
          screenshot: reference.screenshot,
        },
        closure: {
          dedicated_row: true,
          dedicated_artifact: true,
          pattern_specific_evidence: hasCaptureProof || hasDedicatedRuntimeProof || hasRuntimeProof,
          real_runtime_identity: hasRuntimeProof,
          integrated_runtime_trace: true,
          authority_atomic_behavior: false,
          completion_eligible: false,
        },
        gaps: [
          ...(!hasCaptureProof && !hasDedicatedRuntimeProof && !hasRuntimeProof ? ["current Patternに当該Scenarioの専用State/recordまたはVariant単位の専用Runtime Oracleがない。"] : []),
          ...(!referenceMapping.patterns.includes(pattern.id) ? ["統合Reference Systemの当該ScenarioへこのPatternは直接Mappingされていない。"] : []),
          "Authority由来Atomic behaviorのHuman reviewが未完了でCompletion対象外。",
        ],
      };
      const relativePath = `${scenarioProofRoot}/patterns/${pattern.id}/${scenario}.proof.json`;
      const absolutePath = path.join(root, relativePath);
      await mkdir(path.dirname(absolutePath), { recursive: true });
      const output = `${JSON.stringify(proof, null, 2)}\n`;
      await writeFile(absolutePath, output);
      proofs.push(proof);
      files.push({ id: proof.id, pattern_id: pattern.id, scenario, path: relativePath, digest: sha256(output), status });
    }
  }

  const sourceFiles = [
    "scripts/lib/scenario-proof.ts", "scripts/generate-scenario-proofs.ts", "scripts/verify-scenario-proofs.ts",
    "integrations/reference-system/manifest.json", "artifacts/reference-system/results.json",
    "artifacts/pattern-scenarios/results.json", "scripts/verify-pattern-scenario-evidence.ts",
    "artifacts/capture-results.json", "artifacts/benchmark-results.json", "artifacts/compatibility-results.json",
  ];
  const sourceDigests = Object.fromEntries(await Promise.all(sourceFiles.map(async (file) => [file, await fileDigest(root, file)])));
  const byScenario = Object.fromEntries(scenarioIds.map((scenario) => {
    const rows = proofs.filter((proof) => proof.scenario === scenario);
    return [scenario, {
      rows: rows.length,
      pattern_specific: rows.filter((proof) => proof.closure.pattern_specific_evidence).length,
      runtime_identity: rows.filter((proof) => proof.closure.real_runtime_identity).length,
      integrated_pattern_mapped: rows.filter((proof) => proof.integrated_reference.pattern_mapped).length,
      gaps: rows.filter((proof) => !proof.closure.pattern_specific_evidence).length,
    }];
  })) as ScenarioProofIndex["by_scenario"];
  const index: ScenarioProofIndex = {
    schema_version: 1,
    id: "frontend-scenario-proof-matrix-v1",
    atlas_id: "frontend-behavior-atlas",
    generated_at: "2026-08-28T00:00:00+09:00",
    status: "incomplete-authority-atomic-and-runtime-closure",
    denominator: "85-current-domain-patterns-x-10-scenarios",
    tool_digest: sha256(JSON.stringify(sourceDigests)),
    source_digests: sourceDigests,
    summary: {
      patterns: registry.patterns.length,
      scenarios: scenarioIds.length,
      rows: proofs.length,
      dedicated_artifacts: files.length,
      pattern_specific_rows: proofs.filter((proof) => proof.closure.pattern_specific_evidence).length,
      pattern_specific_runtime_rows: proofs.filter((proof) => proof.closure.real_runtime_identity).length,
      pattern_specific_capture_rows: proofs.filter((proof) => proof.status === "bounded-capture-proof").length,
      pattern_specific_gaps: proofs.filter((proof) => !proof.closure.pattern_specific_evidence).length,
      integrated_trace_rows: proofs.filter((proof) => proof.closure.integrated_runtime_trace).length,
      authority_atomic_rows: proofs.filter((proof) => proof.closure.authority_atomic_behavior).length,
      completion_eligible_rows: proofs.filter((proof) => proof.closure.completion_eligible).length,
    },
    by_scenario: byScenario,
    files,
    completion_limits: [
      "85 Patternは非後退baselineでありAuthority由来Atomic behavior denominatorではない。",
      "記録済みCapture Browser identityを別Profile、外部Runtime、または未実行Scenarioのidentityとして流用しない。",
      "Pattern Scenario gapは全Variantを対象Scenarioへ駆動した専用TraceとOracleが揃う場合だけ閉じる。",
      "統合Reference Systemの10 Traceを全Pattern固有のRuntime Proofとして流用しない。",
      "Authority Human review完了までCompletion eligible rowは0を維持する。",
    ],
  };
  await mkdir(path.join(root, scenarioProofRoot), { recursive: true });
  await writeFile(path.join(root, scenarioProofIndexPath), `${JSON.stringify(index, null, 2)}\n`);
  return index;
}

export async function listScenarioProofFiles(root: string): Promise<string[]> {
  const files: string[] = [];
  async function walk(directory: string): Promise<void> {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const target = path.join(directory, entry.name);
      if (entry.isDirectory()) await walk(target);
      else if (entry.isFile() && entry.name.endsWith(".proof.json")) files.push(path.relative(root, target));
    }
  }
  const directory = path.join(root, scenarioProofRoot, "patterns");
  if ((await stat(directory).catch(() => null))?.isDirectory()) await walk(directory);
  return files.sort();
}
