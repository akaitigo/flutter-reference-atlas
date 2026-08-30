#!/usr/bin/env node
import { createHash } from "node:crypto";
import { access, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const skillDirectory = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const defaultRepositoryRoot = path.resolve(skillDirectory, "../../..");
const sha256 = (value) => `sha256:${createHash("sha256").update(value).digest("hex")}`;
const stopWords = new Set(["a", "an", "and", "as", "at", "for", "from", "in", "into", "it", "of", "on", "or", "the", "this", "to", "with"]);

const tokenize = (value) => value
  .toLocaleLowerCase()
  .split(/[^\p{L}\p{N}]+/u)
  .map((term) => term.trim())
  .filter((term) => term.length > 1 && !stopWords.has(term));

export function searchRegistry(registry, query) {
  const terms = tokenize(query);
  if (terms.length === 0) return registry.patterns;
  return registry.patterns
    .map((pattern) => {
      const strong = [pattern.title, ...pattern.aliases.map((alias) => alias.term)].join(" ").toLocaleLowerCase();
      const broad = [pattern.summary, pattern.intent, ...pattern.retrieval.phrases, ...Object.values(pattern.taxonomy).flat()].join(" ").toLocaleLowerCase();
      const strongTerms = new Set(tokenize(strong));
      const broadTerms = new Set(tokenize(broad));
      const matches = (candidate, candidateTerms, term) => /[^\x00-\x7f]/.test(term) ? candidate.includes(term) : candidateTerms.has(term);
      let strongMatches = 0;
      let broadMatches = 0;
      const positiveScore = terms.reduce((total, term) => {
        if (matches(strong, strongTerms, term)) { strongMatches += 1; return total + 4; }
        if (matches(broad, broadTerms, term)) { broadMatches += 1; return total + 1; }
        return total;
      }, 0);
      const normalizedQuery = terms.join(" ");
      const negativeMatches = pattern.retrieval.negativeCues.filter((cue) => {
        const normalizedCue = tokenize(cue).join(" ");
        return normalizedCue.length > 0 && normalizedQuery.includes(normalizedCue);
      }).length;
      return { pattern, score: positiveScore - negativeMatches * 8, strongMatches, broadMatches };
    })
    .filter((result) => {
      const minimumBroadMatches = terms.some((term) => /[^\x00-\x7f]/.test(term)) ? 1 : Math.max(2, Math.ceil(terms.length * .4));
      return result.score > 0 && (result.strongMatches > 0 || result.broadMatches >= minimumBroadMatches);
    })
    .sort((left, right) => right.score - left.score || left.pattern.title.localeCompare(right.pattern.title))
    .map((result) => result.pattern);
}

async function readJson(repositoryRoot, relativePath) {
  return JSON.parse(await readFile(path.join(repositoryRoot, relativePath), "utf8"));
}

async function artifactBinding(repositoryRoot, relativePath, claimScope) {
  const bytes = await readFile(path.join(repositoryRoot, relativePath));
  return { path: relativePath, digest: sha256(bytes), bytes: bytes.byteLength, claim_scope: claimScope };
}

export async function loadAdvisorContext(repositoryRoot = defaultRepositoryRoot) {
  const [registry, coverage, authority, mastery, captures, benchmarks, compatibility, localE2e, containerE2e] = await Promise.all([
    readJson(repositoryRoot, "packages/registry/generated/registry.json"),
    readJson(repositoryRoot, "coverage/targets.json"),
    readJson(repositoryRoot, "authority/sources.snapshot.json"),
    readJson(repositoryRoot, ".agents/skills/fe-behavior-advisor/references/mastery-contract.json"),
    readJson(repositoryRoot, "artifacts/capture-results.json"),
    readJson(repositoryRoot, "artifacts/benchmark-results.json"),
    readJson(repositoryRoot, "artifacts/compatibility-results.json"),
    readJson(repositoryRoot, "artifacts/e2e-results.json"),
    readJson(repositoryRoot, "artifacts/e2e-results.container.json"),
  ]);
  return {
    repositoryRoot,
    registry,
    coverage,
    authorityByUrl: new Map(authority.sources.map((source) => [source.url, source])),
    mastery,
    captures,
    benchmarks,
    compatibility,
    localE2e,
    containerE2e,
  };
}

function targetForPattern(coverage, patternId) {
  return coverage.targets.find((target) => target.patternIds.includes(patternId));
}

function boundaryBlocks(request, executionContract) {
  const blocks = [];
  if (executionContract.mutation_policy === "explicit-authorization-required" && request.authorized_change !== true) blocks.push("unauthorized-mutation");
  if (request.authority_semantic_decision === true) blocks.push("external-human-decision-required");
  if (request.stale_source_relock === true) blocks.push("stale-source-relock-explicit-procedure-required");
  return blocks;
}

export async function planAdvisorRequest(context, request) {
  const outcome = context.mastery.outcomes.find((candidate) => candidate.id === request.outcome);
  const surface = context.mastery.surfaces.find((candidate) => candidate.id === request.surface);
  if (!outcome) throw new Error(`Unknown mastery outcome: ${request.outcome}`);
  if (!surface) throw new Error(`Unknown mastery surface: ${request.surface}`);
  const executionContract = context.mastery.execution_contracts[request.outcome];
  if (!executionContract) throw new Error(`Missing execution contract: ${request.outcome}`);
  const pattern = searchRegistry(context.registry, request.query)[0] ?? null;
  const blocks = boundaryBlocks(request, executionContract);
  if (!pattern) {
    return {
      id: request.id,
      status: "coverage-gap",
      outcome: request.outcome,
      surface: request.surface,
      mode: executionContract.mode,
      query: request.query,
      pattern_id: null,
      target_id: null,
      target_set: null,
      coverage_state: "missing",
      coverage_disposition: "coverage-gap",
      required_deliverables: [...surface.required_deliverables],
      required_output_fields: [...executionContract.required_output_fields],
      mutation_policy: executionContract.mutation_policy,
      mutation_status: executionContract.mutation_policy === "read-only" ? "read-only" : "blocked",
      blocked_reasons: blocks,
      stop_conditions: [...context.mastery.stop_conditions],
      evidence_bindings: [],
      source_bindings: [],
      implementation_bindings: [],
    };
  }
  const target = targetForPattern(context.coverage, pattern.id);
  if (!target) throw new Error(`Pattern is not connected to a Coverage target: ${pattern.id}`);
  const targetAllowed = outcome.target_sets.includes(target.release) && surface.target_sets.includes(target.release);
  const coverageDisposition = !targetAllowed
    ? "mastery-routing-gap"
    : context.mastery.coverage_policy.complete_states.includes(target.state) ? "verified-coverage" : "coverage-gap";
  const patternPath = `experiments/${pattern.id}/pattern.json`;
  const implementationBindings = await Promise.all(pattern.variants.map(async (variant) => {
    const relativePath = `experiments/${pattern.id}/${variant.entry}`;
    if (!(await access(path.join(context.repositoryRoot, relativePath)).then(() => true).catch(() => false))) throw new Error(`Variant source is missing: ${relativePath}`);
    return { id: variant.id, path: relativePath, digest: `sha256:${context.registry.artifacts.sourceHashes[`${pattern.id}::${variant.id}`]}` };
  }));
  const sourceBindings = pattern.provenance.references.map((reference) => {
    const locked = context.authorityByUrl.get(reference.url);
    if (!locked) throw new Error(`Pattern reference is not locked: ${pattern.id} -> ${reference.url}`);
    return { url: reference.url, digest: locked.digest, bytes: locked.size_bytes };
  });
  const evidenceBindings = await Promise.all([
    artifactBinding(context.repositoryRoot, patternPath, "pattern-contract"),
    artifactBinding(context.repositoryRoot, "artifacts/capture-results.json", "pattern-filtered-capture-records"),
    artifactBinding(context.repositoryRoot, "artifacts/benchmark-results.json", "pattern-filtered-variant-benchmarks"),
    artifactBinding(context.repositoryRoot, "artifacts/compatibility-results.json", "pattern-filtered-browser-matrix"),
    artifactBinding(context.repositoryRoot, "artifacts/e2e-results.json", "aggregate-local-harness-not-dedicated-behavior-proof"),
    artifactBinding(context.repositoryRoot, "artifacts/e2e-results.container.json", "aggregate-container-harness-not-dedicated-behavior-proof"),
  ]);
  const captureIds = context.captures.captures.filter((capture) => capture.id.startsWith(`${pattern.id}::`)).map((capture) => capture.id);
  const benchmarkIds = context.benchmarks.results.filter((result) => result.patternId === pattern.id).map((result) => result.id);
  const compatibilityIds = context.compatibility.tests.filter((test) => test.patternId === pattern.id).map((test) => test.id);
  return {
    id: request.id,
    status: blocks.length > 0 ? "blocked" : coverageDisposition,
    outcome: request.outcome,
    surface: request.surface,
    mode: executionContract.mode,
    query: request.query,
    pattern_id: pattern.id,
    target_id: target.id,
    target_set: target.release,
    target_set_allowed: targetAllowed,
    coverage_state: target.state,
    coverage_disposition: coverageDisposition,
    required_deliverables: [...surface.required_deliverables],
    required_output_fields: [...executionContract.required_output_fields],
    mutation_policy: executionContract.mutation_policy,
    mutation_status: executionContract.mutation_policy === "read-only" ? "read-only" : request.authorized_change === true && blocks.length === 0 ? "authorized-for-request-scope" : "blocked",
    blocked_reasons: blocks,
    stop_conditions: [...context.mastery.stop_conditions],
    acceptance_criteria: pattern.retrieval.acceptanceCriteria,
    implementation_bindings: implementationBindings,
    source_bindings: sourceBindings,
    evidence_bindings: evidenceBindings,
    evidence_records: {
      capture_ids: captureIds,
      benchmark_ids: benchmarkIds,
      compatibility_ids: compatibilityIds,
      local_e2e_status: context.localE2e.status,
      container_e2e_status: context.containerE2e.status,
    },
  };
}

export async function planAdvisorRequests(requests, repositoryRoot = defaultRepositoryRoot) {
  const context = await loadAdvisorContext(repositoryRoot);
  return Promise.all(requests.map((request) => planAdvisorRequest(context, request)));
}

async function main() {
  const args = process.argv.slice(2);
  const value = (flag) => {
    const index = args.indexOf(flag);
    return index >= 0 ? args[index + 1] : undefined;
  };
  const outcome = value("--outcome");
  const surface = value("--surface");
  const query = value("--query");
  if (!outcome || !surface || !query) {
    console.error("使い方: node scripts/advisor-router.mjs --outcome <outcome> --surface <surface> --query <挙動> [--authorized-change]");
    process.exitCode = 2;
    return;
  }
  const [result] = await planAdvisorRequests([{ id: "cli-request", outcome, surface, query, authorized_change: args.includes("--authorized-change") }]);
  console.log(JSON.stringify(result, null, 2));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
