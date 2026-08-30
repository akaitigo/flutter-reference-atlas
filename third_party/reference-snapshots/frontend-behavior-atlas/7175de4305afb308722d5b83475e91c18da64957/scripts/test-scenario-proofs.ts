import { readFile } from "node:fs/promises";
import path from "node:path";
import { scenarioIds, scenarioProofIndexPath, type ScenarioProofIndex } from "./lib/scenario-proof";

const index = JSON.parse(await readFile(path.join(process.cwd(), scenarioProofIndexPath), "utf8")) as ScenarioProofIndex;
const failures: string[] = [];
const check = (condition: unknown, message: string): void => { if (!condition) failures.push(message); };

check(index.summary.rows === 850 && index.summary.dedicated_artifacts === 850, "Pattern × Scenario dedicated-row contract is not 850/850.");
check(index.summary.pattern_specific_rows === 437 && index.summary.pattern_specific_runtime_rows === 437 && index.summary.pattern_specific_gaps === 413, "security-001 must close exactly eight of the original 421 Pattern Scenario gaps.");
check(index.by_scenario.boundary.pattern_specific === 44 && index.by_scenario.boundary.runtime_identity === 44 && index.by_scenario.boundary.gaps === 41, "Boundary Scenario must include the two Variant-complete queue proofs.");
check(index.by_scenario.security.pattern_specific === 22 && index.by_scenario.security.runtime_identity === 22 && index.by_scenario.security.gaps === 63, "Security Scenario must include all six Variant-complete dedicated proofs.");
check(scenarioIds.every((scenario) => index.by_scenario[scenario].rows === 85), "Each Scenario must retain 85 current-Pattern rows.");
check(index.by_scenario.performance.runtime_identity === 85, "Performance must retain 85 Pattern-specific runtime identities.");
check(index.by_scenario.compatibility.runtime_identity === 85, "Compatibility must retain 85 Pattern-specific runtime identities.");
check(scenarioIds.every((scenario) => index.by_scenario[scenario].runtime_identity === index.by_scenario[scenario].pattern_specific), "Every Pattern-specific row must retain a recaptured Browser runtime identity.");
check(index.summary.integrated_trace_rows === 850, "Every row must bind the matching integrated Scenario Trace.");
check(index.summary.authority_atomic_rows === 0 && index.summary.completion_eligible_rows === 0, "Human Authority review must not be inferred from machine evidence.");
check(["refusal", "migration", "security"].some((scenario) => index.by_scenario[scenario].gaps > 0), "Matrix must preserve known Pattern-specific Scenario gaps instead of laundering integrated Proof.");
check(index.files.every((file) => /^evidence\/scenarios\/patterns\/.+\/(normal|boundary|refusal|failure|recovery|migration|operations|security|performance|compatibility)\.proof\.json$/.test(file.path)), "Scenario files must use stable Pattern/Scenario paths.");

if (failures.length > 0) throw new Error(`Scenario Proof contract tests failed:\n- ${failures.join("\n- ")}`);
console.log("Scenario Proof contract tests passed: dedicated rows, runtime identity, integrated Trace binding, and anti-overclaim invariants.");
