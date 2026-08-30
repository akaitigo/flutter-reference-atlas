import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import registry from "../packages/registry/generated/registry.json" with { type: "json" };

const root = process.cwd();
const payload = `<img src="/__fba-security-probe.png" onerror="window.__fbaInjected=true">`;
const digest = (value: Buffer | string) => `sha256:${createHash("sha256").update(value).digest("hex")}`;
const filesDigest = async (files: string[]) => {
  const hash = createHash("sha256");
  for (const file of files) hash.update(file).update("\0").update(await readFile(path.join(root, file))).update("\0");
  return `sha256:${hash.digest("hex")}`;
};
const assert = (condition: unknown, message: string): asserts condition => { if (!condition) throw new Error(message); };
type TestRecord = {
  pattern_id: string; variant_id: string; scenario: string; source_digest: string; outcome: string; attempts: number; final_status: string; error: string | null;
  oracle: Record<string, unknown>;
  trace: { path: string; digest: string; bytes: number; action_stream: boolean; network_stream: boolean; resource_stream: boolean };
  screenshot: { path: string; digest: string; bytes: number };
};
type QueueOracle = {
  kind: string; driven_actions: { repeated_start: number; disconnect: number; recover: number }; observed_queue_depths: number[]; maximum_queue_depth: number;
  final_state: { pattern: string; strategy: string; phase: string; connected: boolean; sequence: number; queued: number };
};
type SecurityOracle = {
  kind: string; payload: string; driven_actions: { navigate: number; open: number; fill: number; inert_enter: number };
  sink_contract: { exact_input_value: boolean; rendered_as_text: boolean; rendered_images: number; probe_requests: string[]; script_executed: boolean };
  response_headers: { content_security_policy: string; permissions_policy: string }; rendered_status: string;
  final_state: Record<string, string | number | boolean>;
};
type InteractionSecurityOracle = {
  kind: string; variant_engine: string; driven_actions: Record<string, number>;
  external_effects: { action_requests: string[]; navigations: string[]; popups: string[]; runtime_errors: string[] };
  response_headers: { content_security_policy: string; permissions_policy: string };
  allowed_record_ids?: string[];
  external_drop?: { over_accepted: boolean; drop_accepted: boolean; transfer_types: string[] };
  dom?: { item_ids: string[]; image_count: number; link_count: number; script_executed: boolean };
  bounds?: { x: number; y: number };
  flooded_state?: Record<string, string | number | boolean>;
  trajectory?: { samples: number; all_finite: boolean; all_within_bounds: boolean; maximum_abs_x: number; maximum_abs_y: number };
  snapshots?: unknown[] | { maximum: { state: Record<string, string | number | boolean>; art_aria_hidden: string; art_focusable_descendants: number; semantic_copy_visible: boolean }; minimum: { state: Record<string, string | number | boolean> }; partial: { state: Record<string, string | number | boolean> } };
  maximum_simultaneously_open?: number; final_concealed_regions?: number;
  art_remained_aria_hidden?: boolean; focusable_art_descendants?: number; semantic_copy_remained_visible?: boolean; engine_boundary_valid?: boolean;
  final_state: Record<string, string | number | boolean>;
};
const report = JSON.parse(await readFile(path.join(root, "artifacts/pattern-scenarios/results.json"), "utf8")) as {
  status: string; command: string; profile: string; counts: { rows: number; variants: number; total: number; passed: number; failed: number; flaky: number; skipped: number };
  source_digest: string; harness_digest: string;
  environment: { node: string; platform: string; architecture: string; playwright: string; browser_name: string; browser_version: string; browser_channel: string; workers: number; retries: number; viewport: { width: number; height: number; device_scale_factor: number }; trace_mode: string };
  retention_contract: { publish_on: string; failed_run: string; swap: string };
  tests: TestRecord[];
};
const expectedRows = [
  { patternId: "reactive/background-sync-status", scenario: "boundary" },
  { patternId: "reactive/network-offline-recovery", scenario: "boundary" },
  { patternId: "interaction/combobox-autocomplete", scenario: "security" },
  { patternId: "interaction/command-palette", scenario: "security" },
  { patternId: "direct-manipulation/drag-reorder", scenario: "security" },
  { patternId: "direct-manipulation/inertial-drag", scenario: "security" },
  { patternId: "disclosure/accordion", scenario: "security" },
  { patternId: "disclosure/mask-reveal", scenario: "security" },
];
const expectedKeys = expectedRows.flatMap(({ patternId, scenario }) => {
  const pattern = registry.patterns.find((candidate) => candidate.id === patternId);
  if (!pattern) throw new Error(`Expected Pattern is missing: ${patternId}`);
  return pattern.variants.map((variant) => `${patternId}\0${scenario}\0${variant.id}`);
}).sort();
const actualKeys = report.tests.map((test) => `${test.pattern_id}\0${test.scenario}\0${test.variant_id}`).sort();
assert(JSON.stringify(actualKeys) === JSON.stringify(expectedKeys), "Dedicated Scenario report does not contain the exact second-tranche Pattern/Scenario/Variant rows.");
assert(report.status === "passed" && report.command === "pnpm pattern-scenario:test" && report.profile === "local-real-browser", "Dedicated Scenario run identity is invalid.");
assert(report.counts.rows === 8 && report.counts.variants === 16 && report.counts.total === 16 && report.counts.passed === 16 && report.counts.failed === 0 && report.counts.flaky === 0 && report.counts.skipped === 0, "Dedicated Scenario counts must remain 8 rows / 16 first-attempt passes.");
assert(report.environment.browser_name === "chromium" && /^\d+\.\d+\.\d+(?:\.\d+)?$/.test(report.environment.browser_version) && report.environment.workers === 1 && report.environment.retries === 0 && report.environment.trace_mode === "on", "Dedicated Scenario Browser identity or execution profile is invalid.");
assert(report.retention_contract.publish_on === "full-run-passed" && report.retention_contract.failed_run === "retain-prior-success" && report.retention_contract.swap === "staged-directory-rename-with-rollback", "Dedicated Scenario retention contract is missing or weakened.");
const sourceFiles = [
  "apps/runner/src/main.ts",
  "experiments/_shared/reactive-lab.ts",
  "experiments/interaction/command-palette/shared.ts",
  ...report.tests.map((test) => {
    const pattern = registry.patterns.find((candidate) => candidate.id === test.pattern_id)!;
    const variant = pattern.variants.find((candidate) => candidate.id === test.variant_id)!;
    return `experiments/${test.pattern_id}/${variant.entry}`;
  }),
];
assert(report.source_digest === await filesDigest([...new Set(sourceFiles)]), "Dedicated Scenario source digest is stale.");
const harnessFiles = ["pattern-scenario-e2e/reactive-queue-boundary.spec.ts", "pattern-scenario-e2e/security-input-sinks.spec.ts", "pattern-scenario-e2e/security-interaction-boundaries.spec.ts", "playwright.pattern-scenario.config.ts", "scripts/reporters/pattern-scenario-evidence-reporter.ts", "scripts/verify-pattern-scenario-evidence.ts"];
assert(report.harness_digest === await filesDigest(harnessFiles), "Dedicated Scenario harness digest is stale.");
for (const test of report.tests) {
  const pattern = registry.patterns.find((candidate) => candidate.id === test.pattern_id)!;
  assert(test.source_digest === `sha256:${registry.artifacts.sourceHashes[`${test.pattern_id}::${test.variant_id}`]}`, `Variant source binding drift: ${test.pattern_id} / ${test.variant_id}`);
  assert(pattern.variants.some((variant) => variant.id === test.variant_id), `Unknown Variant record: ${test.pattern_id} / ${test.variant_id}`);
  assert(test.outcome === "expected" && test.attempts === 1 && test.final_status === "passed" && test.error === null, `Dedicated Scenario attempt failed or retried: ${test.pattern_id} / ${test.variant_id}`);
  if (test.scenario === "boundary") {
    const oracle = test.oracle as QueueOracle;
    assert(oracle.kind === "bounded-queue", `Queue Oracle kind is invalid: ${test.pattern_id} / ${test.variant_id}`);
    assert(oracle.driven_actions.repeated_start === 8 && oracle.driven_actions.disconnect === 1 && oracle.driven_actions.recover === 1, `Dedicated Scenario did not drive the declared action sequence: ${test.pattern_id} / ${test.variant_id}`);
    assert(oracle.observed_queue_depths.length === 10 && Math.max(...oracle.observed_queue_depths) === 1 && oracle.maximum_queue_depth === 1, `Queue boundary Oracle failed: ${test.pattern_id} / ${test.variant_id}`);
    assert(oracle.final_state.pattern === test.pattern_id.split("/").at(-1) && oracle.final_state.strategy === test.variant_id && oracle.final_state.phase === "recovered" && oracle.final_state.connected && oracle.final_state.sequence === 9 && oracle.final_state.queued === 0, `Final recovery state drift: ${test.pattern_id} / ${test.variant_id}`);
  } else {
    assert(test.scenario === "security", `Unexpected dedicated Scenario: ${test.pattern_id} / ${test.scenario}`);
    if (test.oracle.kind === "untrusted-input-sink") {
      const oracle = test.oracle as SecurityOracle;
      assert(oracle.payload === payload, `Security payload/Oracle identity drift: ${test.pattern_id} / ${test.variant_id}`);
      assert(oracle.driven_actions.navigate === 1 && oracle.driven_actions.fill === 1 && oracle.driven_actions.open === (test.pattern_id === "interaction/command-palette" ? 1 : 0) && oracle.driven_actions.inert_enter === (test.pattern_id === "interaction/command-palette" ? 1 : 0), `Security Scenario did not drive the declared action sequence: ${test.pattern_id} / ${test.variant_id}`);
      assert(oracle.sink_contract.exact_input_value && oracle.sink_contract.rendered_as_text && oracle.sink_contract.rendered_images === 0 && oracle.sink_contract.probe_requests.length === 0 && !oracle.sink_contract.script_executed, `Untrusted input escaped the text-only sink Oracle: ${test.pattern_id} / ${test.variant_id}`);
      assertSecurityHeaders(oracle.response_headers, test);
      if (test.pattern_id === "interaction/combobox-autocomplete") {
        assert(oracle.rendered_status === `No suggestions for ${payload}.` && oracle.final_state.query === payload && oracle.final_state.phase === "empty" && oracle.final_state.count === 0 && oracle.final_state.active === "none" && oracle.final_state.expanded === true && oracle.final_state.busy === false && oracle.final_state.focus === "input", `Combobox security terminal state drift: ${test.variant_id}`);
      } else {
        assert(oracle.rendered_status === `No commands match ${payload}.` && oracle.final_state.open === true && oracle.final_state.scope === "root" && oracle.final_state.query === payload && oracle.final_state.count === 0 && oracle.final_state.active === "none" && oracle.final_state.focus === "input", `Command palette security terminal state drift: ${test.variant_id}`);
      }
    } else {
      const oracle = test.oracle as InteractionSecurityOracle;
      assert(oracle.variant_engine === test.variant_id, `Pattern Security Oracle is not bound to its Variant: ${test.pattern_id} / ${test.variant_id}`);
      assertSecurityHeaders(oracle.response_headers, test);
      assert(oracle.external_effects.action_requests.length === 0 && oracle.external_effects.navigations.length === 0 && oracle.external_effects.popups.length === 0 && oracle.external_effects.runtime_errors.length === 0, `Pattern Security action escaped its runtime boundary: ${test.pattern_id} / ${test.variant_id}`);
      if (test.pattern_id === "direct-manipulation/drag-reorder") {
        assert(oracle.kind === "reorder-transfer-confinement" && oracle.driven_actions.trusted_keyboard_reorder === 1 && oracle.driven_actions.external_transfer_drop === 1, `Reorder Security action/Oracle drift: ${test.variant_id}`);
        assert(JSON.stringify(oracle.allowed_record_ids) === JSON.stringify(["alpha", "bravo", "charlie", "delta"]) && JSON.stringify(oracle.dom?.item_ids) === JSON.stringify(["bravo", "charlie", "delta", "alpha"]), `Reorder record allowlist drift: ${test.variant_id}`);
        assert(oracle.dom?.image_count === 0 && oracle.dom.link_count === 0 && !oracle.dom.script_executed && oracle.external_drop?.transfer_types.includes("text/html") && oracle.external_drop.transfer_types.includes("text/uri-list"), `External transfer altered the reorder DOM: ${test.variant_id}`);
        assert(oracle.final_state.order === "bravo,charlie,delta,alpha" && oracle.final_state.grabbed === "none", `Reorder final state drift: ${test.variant_id}`);
      } else if (test.pattern_id === "direct-manipulation/inertial-drag") {
        assert(oracle.kind === "kinetic-input-confinement" && oracle.driven_actions.arrow_input_flood === 128 && oracle.driven_actions.inertial_launch === 1, `Inertial Security action/Oracle drift: ${test.variant_id}`);
        assert(Boolean(oracle.bounds && oracle.trajectory) && oracle.trajectory!.samples > 2 && oracle.trajectory!.all_finite && oracle.trajectory!.all_within_bounds && oracle.trajectory!.maximum_abs_x <= oracle.bounds!.x + 1 && oracle.trajectory!.maximum_abs_y <= oracle.bounds!.y + 1, `Inertial trajectory escaped its finite track: ${test.variant_id}`);
        assert(oracle.final_state.vx === 0 && oracle.final_state.vy === 0 && oracle.final_state.phase === "settled" && oracle.final_state.motion === "full", `Inertial terminal state drift: ${test.variant_id}`);
      } else if (test.pattern_id === "disclosure/accordion") {
        assert(oracle.kind === "exclusive-disclosure-integrity" && oracle.driven_actions.sequential_disclosures === 3 && oracle.driven_actions.explicit_close === 1, `Accordion Security action/Oracle drift: ${test.variant_id}`);
        assert(Array.isArray(oracle.snapshots) && oracle.snapshots.length === 3 && oracle.maximum_simultaneously_open === 1 && oracle.final_concealed_regions === 3 && oracle.final_state.open === "none", `Accordion disclosure isolation drift: ${test.variant_id}`);
      } else {
        const snapshots = oracle.snapshots as Exclude<InteractionSecurityOracle["snapshots"], unknown[]>;
        assert(oracle.kind === "visual-semantic-separation" && oracle.driven_actions.clamped_increment === 110 && oracle.driven_actions.clamped_decrement === 110 && oracle.driven_actions.partial_increment === 50, `Mask Security action/Oracle drift: ${test.variant_id}`);
        assert(oracle.art_remained_aria_hidden && oracle.focusable_art_descendants === 0 && oracle.semantic_copy_remained_visible && oracle.engine_boundary_valid, `Mask visual/semantic isolation drift: ${test.variant_id}`);
        assert(snapshots.maximum.state.progress === 1 && snapshots.minimum.state.progress === 0 && snapshots.partial.state.progress === 0.5 && oracle.final_state.progress === 0.5, `Mask clamped progress drift: ${test.variant_id}`);
      }
    }
  }
  for (const artifact of [test.trace, test.screenshot]) {
    const bytes = await readFile(path.join(root, artifact.path));
    assert(bytes.byteLength === artifact.bytes && digest(bytes) === artifact.digest, `Dedicated Scenario Artifact digest drift: ${artifact.path}`);
  }
  assert(test.trace.action_stream && test.trace.network_stream && test.trace.resource_stream, `Dedicated Scenario Trace streams are incomplete: ${test.pattern_id} / ${test.variant_id}`);
}
console.log(`Verified dedicated Pattern Scenario Evidence: ${report.counts.rows} rows / ${report.counts.variants} Variant traces on chromium ${report.environment.browser_version}.`);

function assertSecurityHeaders(headers: { content_security_policy: string; permissions_policy: string }, test: TestRecord) {
  assert(headers.content_security_policy.includes("default-src 'none'") && headers.content_security_policy.includes("object-src 'none'") && headers.content_security_policy.includes("base-uri 'none'"), `Security CSP identity is incomplete: ${test.pattern_id} / ${test.variant_id}`);
  assert(headers.permissions_policy.includes("camera=()") && headers.permissions_policy.includes("microphone=()"), `Permissions Policy identity is incomplete: ${test.pattern_id} / ${test.variant_id}`);
}
