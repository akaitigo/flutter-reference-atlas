import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import {
  listScenarioProofFiles,
  scenarioIds,
  scenarioProofIndexPath,
  type ScenarioId,
  type ScenarioProof,
  type ScenarioProofIndex,
} from "./lib/scenario-proof";
import { loadRegistry } from "./lib/registry";

const root = process.cwd();
const sha256 = (value: string | Buffer) => `sha256:${createHash("sha256").update(value).digest("hex")}`;
const readJson = async <T>(relativePath: string): Promise<T> => JSON.parse(await readFile(path.join(root, relativePath), "utf8")) as T;
const assert = (condition: unknown, message: string): asserts condition => { if (!condition) throw new Error(message); };

const index = await readJson<ScenarioProofIndex>(scenarioProofIndexPath);
const registry = await loadRegistry(root);
const coverage = await readJson<{ targets: Array<{ id: string; release: string; patternIds: string[] }> }>("coverage/targets.json");
const captures = await readJson<{ environment: { profile: string; node: string; platform: string; architecture: string; playwright: string; browserName: string; browserVersion: string; browserChannel: string; workers: number; retries: number; viewport: { width: number; height: number; deviceScaleFactor: number } }; harnessHash: string; captures: Array<{ id: string; sourceHash: string; output: string; imageHash: string; bytes: number }> }>("artifacts/capture-results.json");
const benchmarks = await readJson<{ environment: Record<string, unknown>; results: Array<{ id: string; patternId: string; variantId: string; sourceHash: string; status: string }> }>("artifacts/benchmark-results.json");
const compatibility = await readJson<{ browsers: Array<{ name: string; version: string }>; sourceDigest: string; harnessDigest: string; tests: Array<{ id: string; project: string; patternId: string; outcome: string; attempts: number; finalStatus: string; error: string | null }> }>("artifacts/compatibility-results.json");
const referenceManifest = await readJson<{ scenarios: Array<{ id: ScenarioId; patterns: string[]; runtime_boundaries: string[]; assertions: string[] }> }>("integrations/reference-system/manifest.json");
const referenceResults = await readJson<{ environment: Record<string, unknown>; tests: Array<{ scenario: ScenarioId; outcome: string; attempts: number; final_status: string; trace: { path: string; digest: string; bytes: number }; screenshot: { path: string; digest: string; bytes: number } }> }>("artifacts/reference-system/results.json");
const scenarioRuntime = await readJson<{ status: string; environment: Record<string, unknown>; tests: Array<{ pattern_id: string; variant_id: string; scenario: string; source_digest: string; outcome: string; attempts: number; final_status: string; error: string | null; oracle: Record<string, unknown>; trace: { path: string; digest: string; bytes: number; action_stream: boolean; network_stream: boolean; resource_stream: boolean }; screenshot: { path: string; digest: string; bytes: number } }> }>("artifacts/pattern-scenarios/results.json");

assert(index.schema_version === 1 && index.id === "frontend-scenario-proof-matrix-v1" && index.atlas_id === "frontend-behavior-atlas", "Scenario Proof index identity is invalid.");
assert(index.status === "incomplete-authority-atomic-and-runtime-closure", "Scenario Proof index must remain incomplete.");
assert(index.denominator === "85-current-domain-patterns-x-10-scenarios", "Scenario Proof denominator is invalid.");
assert(registry.patterns.length === 85 && scenarioIds.length === 10, "Scenario Proof baseline denominator changed.");

const sourceFiles = [
  "scripts/lib/scenario-proof.ts", "scripts/generate-scenario-proofs.ts", "scripts/verify-scenario-proofs.ts",
  "integrations/reference-system/manifest.json", "artifacts/reference-system/results.json",
  "artifacts/pattern-scenarios/results.json", "scripts/verify-pattern-scenario-evidence.ts",
  "artifacts/capture-results.json", "artifacts/benchmark-results.json", "artifacts/compatibility-results.json",
];
const expectedSourceDigests = Object.fromEntries(await Promise.all(sourceFiles.map(async (file) => [file, sha256(await readFile(path.join(root, file)))])));
assert(JSON.stringify(index.source_digests) === JSON.stringify(expectedSourceDigests), "Scenario Proof source digests are stale.");
assert(index.tool_digest === sha256(JSON.stringify(expectedSourceDigests)), "Scenario Proof tool digest is stale.");

const actualFiles = await listScenarioProofFiles(root);
const indexedFiles = index.files.map((file) => file.path).sort();
assert(actualFiles.length === 850 && indexedFiles.length === 850, `Scenario Proof file count is not 850: actual=${actualFiles.length}, index=${indexedFiles.length}`);
assert(actualFiles.join("\0") === indexedFiles.join("\0"), "Scenario Proof file set differs from the index.");
assert(new Set(index.files.map((file) => file.id)).size === 850, "Scenario Proof IDs are not unique.");
assert(new Set(index.files.map((file) => file.path)).size === 850, "Scenario Proof paths are not unique.");

const targetByPattern = new Map(coverage.targets.flatMap((target) => target.patternIds.map((patternId) => [patternId, target] as const)));
const captureById = new Map(captures.captures.map((record) => [record.id, record]));
const benchmarkByPattern = new Map(registry.patterns.map((pattern) => [pattern.id, benchmarks.results.filter((record) => record.patternId === pattern.id)]));
const compatibilityByPattern = new Map(registry.patterns.map((pattern) => [pattern.id, compatibility.tests.filter((record) => record.patternId === pattern.id)]));
const manifestByScenario = new Map(referenceManifest.scenarios.map((scenario) => [scenario.id, scenario]));
const referenceByScenario = new Map(referenceResults.tests.map((test) => [test.scenario, test]));
const patternById = new Map(registry.patterns.map((pattern) => [pattern.id, pattern]));
const proofs: ScenarioProof[] = [];

for (const indexed of index.files) {
  const text = await readFile(path.join(root, indexed.path), "utf8");
  assert(indexed.digest === sha256(text), `Scenario Proof file digest mismatch: ${indexed.path}`);
  const proof = JSON.parse(text) as ScenarioProof;
  proofs.push(proof);
  assert(proof.id === indexed.id && proof.pattern_id === indexed.pattern_id && proof.scenario === indexed.scenario && proof.status === indexed.status, `Scenario Proof index identity mismatch: ${indexed.path}`);
  assert(proof.schema_version === 1 && proof.atlas_id === "frontend-behavior-atlas" && proof.behavior_scope === "current-domain-pattern-not-authority-atomic", `Scenario Proof scope is invalid: ${proof.id}`);
  assert(proof.closure.dedicated_row && proof.closure.dedicated_artifact && proof.closure.integrated_runtime_trace, `Scenario Proof dedicated closure is missing: ${proof.id}`);
  assert(!proof.closure.authority_atomic_behavior && !proof.closure.completion_eligible, `Scenario Proof overclaims completion: ${proof.id}`);
  assert(proof.gaps.some((item) => item.includes("Authority")), `Scenario Proof must retain its Authority closure gap: ${proof.id}`);

  const pattern = patternById.get(proof.pattern_id);
  const target = targetByPattern.get(proof.pattern_id);
  assert(pattern && target, `Scenario Proof maps an unknown Pattern or Target: ${proof.id}`);
  assert(proof.target_id === target.id && proof.target_set === target.release, `Scenario Proof Coverage mapping mismatch: ${proof.id}`);
  assert(proof.source_bindings.length === pattern.variants.length, `Scenario Proof source binding count mismatch: ${proof.id}`);
  for (const binding of proof.source_bindings) {
    const variant = pattern.variants.find((item) => item.id === binding.variant_id);
    assert(variant, `Scenario Proof maps an unknown Variant: ${proof.id} -> ${binding.variant_id}`);
    assert(binding.path === `experiments/${pattern.id}/${variant.entry}`, `Scenario Proof source path mismatch: ${proof.id} -> ${binding.variant_id}`);
    assert(binding.digest === `sha256:${registry.artifacts.sourceHashes[`${pattern.id}::${variant.id}`]}`, `Scenario Proof source digest mismatch: ${proof.id} -> ${binding.variant_id}`);
    await readFile(path.join(root, binding.path));
  }

  assert(JSON.stringify(proof.pattern_evidence.capture_environment_identity) === JSON.stringify(captures.environment), `Capture runtime identity drift: ${proof.id}`);
  assert(proof.pattern_evidence.capture_harness_digest === `sha256:${captures.harnessHash}`, `Capture harness digest mismatch: ${proof.id}`);
  const expectedCaptureIds = proof.classification.state_ids.flatMap((stateId) => pattern.variants.map((variant) => `${pattern.id}::${variant.id}::${stateId}`));
  assert(proof.pattern_evidence.capture_records.map((record) => record.id).join("\0") === expectedCaptureIds.join("\0"), `Scenario Capture rows do not match classified states: ${proof.id}`);
  for (const record of proof.pattern_evidence.capture_records) {
    assert(JSON.stringify(record) === JSON.stringify(captureById.get(record.id)), `Scenario Capture record drift: ${proof.id} -> ${record.id}`);
  }
  const expectedScenarioRuntime = scenarioRuntime.tests.filter((record) => record.pattern_id === proof.pattern_id && record.scenario === proof.scenario);
  const hasDedicatedRuntime = scenarioRuntime.status === "passed"
    && expectedScenarioRuntime.length === pattern.variants.length
    && pattern.variants.every((variant) => expectedScenarioRuntime.some((record) => record.variant_id === variant.id && record.outcome === "expected" && record.attempts === 1 && record.final_status === "passed" && record.error === null && record.trace.action_stream && record.trace.network_stream && record.trace.resource_stream));
  assert(JSON.stringify(proof.pattern_evidence.scenario_runtime_records) === JSON.stringify(hasDedicatedRuntime ? expectedScenarioRuntime : []), `Dedicated Scenario records drift: ${proof.id}`);
  assert(proof.pattern_evidence.scenario_runtime_report === (hasDedicatedRuntime ? "artifacts/pattern-scenarios/results.json" : null), `Dedicated Scenario report binding drift: ${proof.id}`);
  assert(JSON.stringify(proof.pattern_evidence.scenario_runtime_environment) === JSON.stringify(hasDedicatedRuntime ? scenarioRuntime.environment : null), `Dedicated Scenario environment drift: ${proof.id}`);

  const referenceMapping = manifestByScenario.get(proof.scenario);
  const reference = referenceByScenario.get(proof.scenario);
  assert(referenceMapping && reference, `Scenario integrated reference is missing: ${proof.id}`);
  assert(proof.integrated_reference.manifest === "integrations/reference-system/manifest.json" && proof.integrated_reference.result === "artifacts/reference-system/results.json", `Scenario integrated reference paths are invalid: ${proof.id}`);
  assert(proof.integrated_reference.pattern_mapped === referenceMapping.patterns.includes(pattern.id), `Scenario integrated Pattern mapping mismatch: ${proof.id}`);
  assert(JSON.stringify(proof.integrated_reference.runtime_boundaries) === JSON.stringify(referenceMapping.runtime_boundaries) && JSON.stringify(proof.integrated_reference.assertions) === JSON.stringify(referenceMapping.assertions), `Scenario integrated contract drift: ${proof.id}`);
  assert(proof.integrated_reference.outcome === "expected" && proof.integrated_reference.attempts === 1, `Scenario integrated run was not a first-attempt pass: ${proof.id}`);
  assert(JSON.stringify(proof.integrated_reference.trace) === JSON.stringify(reference.trace) && JSON.stringify(proof.integrated_reference.screenshot) === JSON.stringify(reference.screenshot), `Scenario integrated Artifact binding mismatch: ${proof.id}`);

  if (proof.scenario === "performance") {
    const expected = benchmarkByPattern.get(pattern.id)!;
    assert(expected.length === pattern.variants.length && expected.every((record) => record.status === "passed"), `Performance runtime evidence is incomplete: ${proof.id}`);
    assert(JSON.stringify(proof.pattern_evidence.benchmark_records) === JSON.stringify(expected) && JSON.stringify(proof.pattern_evidence.benchmark_environment) === JSON.stringify(benchmarks.environment), `Performance evidence drift: ${proof.id}`);
    assert(proof.status === "bounded-runtime-proof" && proof.closure.pattern_specific_evidence && proof.closure.real_runtime_identity, `Performance closure is invalid: ${proof.id}`);
  } else if (proof.scenario === "compatibility") {
    const expected = compatibilityByPattern.get(pattern.id)!;
    assert(expected.length === 3 && expected.every((record) => record.outcome === "expected" && record.attempts === 1 && record.finalStatus === "passed" && record.error === null), `Compatibility runtime evidence is incomplete: ${proof.id}`);
    assert(JSON.stringify(proof.pattern_evidence.compatibility_records) === JSON.stringify(expected), `Compatibility evidence drift: ${proof.id}`);
    assert(proof.status === "bounded-runtime-proof" && proof.closure.pattern_specific_evidence && proof.closure.real_runtime_identity, `Compatibility closure is invalid: ${proof.id}`);
  } else {
    assert(proof.pattern_evidence.benchmark_records.length === 0 && proof.pattern_evidence.benchmark_environment === null && proof.pattern_evidence.compatibility_records.length === 0 && proof.pattern_evidence.compatibility_environment === null, `Unrelated runtime evidence leaked into Scenario row: ${proof.id}`);
    const hasCapture = expectedCaptureIds.length > 0;
    assert(proof.closure.pattern_specific_evidence === (hasCapture || hasDedicatedRuntime) && proof.closure.real_runtime_identity === (hasCapture || hasDedicatedRuntime), `Capture/dedicated-runtime/gap closure mismatch: ${proof.id}`);
    assert(proof.status === (hasCapture || hasDedicatedRuntime ? "bounded-runtime-proof" : "pattern-specific-gap"), `Capture/dedicated-runtime/gap status mismatch: ${proof.id}`);
  }
}

const expectedPairs = registry.patterns.flatMap((pattern) => scenarioIds.map((scenario) => `${pattern.id}\0${scenario}`)).sort();
const actualPairs = proofs.map((proof) => `${proof.pattern_id}\0${proof.scenario}`).sort();
assert(actualPairs.join("\n") === expectedPairs.join("\n"), "Scenario Proof Matrix is not the exact Pattern × Scenario Cartesian product.");

const expectedSummary: ScenarioProofIndex["summary"] = {
  patterns: registry.patterns.length,
  scenarios: scenarioIds.length,
  rows: proofs.length,
  dedicated_artifacts: proofs.length,
  pattern_specific_rows: proofs.filter((proof) => proof.closure.pattern_specific_evidence).length,
  pattern_specific_runtime_rows: proofs.filter((proof) => proof.closure.real_runtime_identity).length,
  pattern_specific_capture_rows: proofs.filter((proof) => proof.status === "bounded-capture-proof").length,
  pattern_specific_gaps: proofs.filter((proof) => !proof.closure.pattern_specific_evidence).length,
  integrated_trace_rows: proofs.filter((proof) => proof.closure.integrated_runtime_trace).length,
  authority_atomic_rows: proofs.filter((proof) => proof.closure.authority_atomic_behavior).length,
  completion_eligible_rows: proofs.filter((proof) => proof.closure.completion_eligible).length,
};
assert(JSON.stringify(index.summary) === JSON.stringify(expectedSummary), "Scenario Proof summary drift.");
for (const scenario of scenarioIds) {
  const rows = proofs.filter((proof) => proof.scenario === scenario);
  const expected = {
    rows: rows.length,
    pattern_specific: rows.filter((proof) => proof.closure.pattern_specific_evidence).length,
    runtime_identity: rows.filter((proof) => proof.closure.real_runtime_identity).length,
    integrated_pattern_mapped: rows.filter((proof) => proof.integrated_reference.pattern_mapped).length,
    gaps: rows.filter((proof) => !proof.closure.pattern_specific_evidence).length,
  };
  assert(JSON.stringify(index.by_scenario[scenario]) === JSON.stringify(expected), `Scenario summary drift: ${scenario}`);
}
assert(index.summary.authority_atomic_rows === 0 && index.summary.completion_eligible_rows === 0, "Scenario Proof Matrix must not claim Authority completion.");
assert(index.summary.integrated_trace_rows === 850, "Every Scenario row must bind its integrated Trace without treating it as Pattern-specific runtime proof.");
assert(index.completion_limits.length >= 4, "Scenario Proof completion limits are incomplete.");
console.log(`Verified Scenario Proof Matrix: ${index.summary.rows} dedicated artifacts, ${index.summary.pattern_specific_rows} Pattern-specific rows (${index.summary.pattern_specific_runtime_rows} runtime identity), ${index.summary.pattern_specific_gaps} explicit gaps, 0 Authority-atomic completion rows.`);
