import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";
import type { FullConfig, FullResult, Reporter, Suite } from "@playwright/test/reporter";
import registry from "../../packages/registry/generated/registry.json" with { type: "json" };

const digest = (value: Buffer | string) => createHash("sha256").update(value).digest("hex");
const filesDigest = async (root: string, files: string[]) => {
  const hash = createHash("sha256");
  for (const file of files) hash.update(file).update("\0").update(await readFile(path.join(root, file))).update("\0");
  return hash.digest("hex");
};
const slug = (value: string) => value.replaceAll("/", "__");

export default class PatternScenarioEvidenceReporter implements Reporter {
  private config: FullConfig | undefined;
  private suite: Suite | undefined;

  onBegin(config: FullConfig, suite: Suite): void {
    this.config = config;
    this.suite = suite;
  }

  async onEnd(result: FullResult): Promise<{ status?: FullResult["status"] }> {
    let stagingRoot: string | undefined;
    try {
      if (!this.config || !this.suite) throw new Error("Pattern Scenario reporter did not receive onBegin.");
      const root = process.cwd();
      const outputRoot = path.join(root, "artifacts/pattern-scenarios");
      stagingRoot = path.join(root, "artifacts/.pattern-scenarios-next");
      const traceRoot = path.join(stagingRoot, "traces");
      const screenshotRoot = path.join(stagingRoot, "screenshots");
      await rm(stagingRoot, { recursive: true, force: true });
      await mkdir(traceRoot, { recursive: true });
      await mkdir(screenshotRoot, { recursive: true });
      if (result.status !== "passed") throw new Error(`Dedicated Scenario run ended ${result.status}; prior successful Evidence was retained.`);
      const project = this.config.projects[0];
      if (!project) throw new Error("Pattern Scenario evidence requires one Playwright project.");
      const channel = project.use.channel;
      const browser = await chromium.launch(channel ? { channel, headless: true } : { headless: true });
      const browserVersion = browser.version();
      await browser.close();
      const playwrightPackage = JSON.parse(await readFile(path.join(root, "node_modules/@playwright/test/package.json"), "utf8")) as { version: string };

      const tests = await Promise.all(this.suite.allTests().map(async (test) => {
        const match = test.title.match(/^\[pattern-scenario:([a-z-]+)]\[pattern:([^\]]+)]\[variant:([^\]]+)]/);
        if (!match) throw new Error(`Dedicated test title is missing Pattern/Variant/Scenario identity: ${test.title}`);
        const [, scenario, patternId, variantId] = match;
        const pattern = registry.patterns.find((candidate) => candidate.id === patternId);
        const variant = pattern?.variants.find((candidate) => candidate.id === variantId);
        if (!pattern || !variant) throw new Error(`Dedicated test targets an unknown Pattern/Variant: ${patternId} / ${variantId}`);
        const finalResult = test.results.at(-1);
        const traceAttachment = finalResult?.attachments.find((attachment) => attachment.name === "trace" && attachment.path);
        const screenshotAttachment = finalResult?.attachments.find((attachment) => attachment.name === "scenario-screenshot" && attachment.body);
        const oracleAnnotation = test.annotations.find((annotation) => annotation.type === "scenario-oracle")?.description;
        if (!traceAttachment?.path || !screenshotAttachment?.body || !oracleAnnotation) throw new Error(`Dedicated Evidence attachment is missing: ${patternId} / ${variantId} / ${scenario}`);
        const basename = `${slug(patternId)}__${scenario}__${variantId}`;
        const stagedTracePath = path.join(traceRoot, `${basename}.trace.zip`);
        const stagedScreenshotPath = path.join(screenshotRoot, `${basename}.png`);
        const finalTracePath = path.join(outputRoot, "traces", `${basename}.trace.zip`);
        const finalScreenshotPath = path.join(outputRoot, "screenshots", `${basename}.png`);
        await copyFile(traceAttachment.path, stagedTracePath);
        await writeFile(stagedScreenshotPath, screenshotAttachment.body);
        const traceBytes = await readFile(stagedTracePath);
        const screenshotBytes = await readFile(stagedScreenshotPath);
        return {
          id: test.id,
          pattern_id: patternId,
          variant_id: variantId,
          scenario,
          title: test.titlePath().filter(Boolean).join(" › "),
          file: path.relative(root, test.location.file),
          line: test.location.line,
          source_digest: `sha256:${registry.artifacts.sourceHashes[`${patternId}::${variantId}`]}`,
          outcome: test.outcome(),
          attempts: test.results.length,
          final_status: finalResult?.status ?? "interrupted",
          error: finalResult?.error?.message ?? null,
          oracle: JSON.parse(oracleAnnotation) as unknown,
          trace: {
            path: path.relative(root, finalTracePath),
            digest: `sha256:${digest(traceBytes)}`,
            bytes: traceBytes.byteLength,
            action_stream: traceBytes.includes(Buffer.from("trace.trace")),
            network_stream: traceBytes.includes(Buffer.from("trace.network")),
            resource_stream: traceBytes.includes(Buffer.from("resources/")),
          },
          screenshot: { path: path.relative(root, finalScreenshotPath), digest: `sha256:${digest(screenshotBytes)}`, bytes: screenshotBytes.byteLength },
        };
      }));
      tests.sort((left, right) => `${left.pattern_id}\0${left.variant_id}`.localeCompare(`${right.pattern_id}\0${right.variant_id}`));
      const counts = {
        rows: new Set(tests.map((test) => `${test.pattern_id}\0${test.scenario}`)).size,
        variants: tests.length,
        total: tests.length,
        passed: tests.filter((test) => test.outcome === "expected").length,
        failed: tests.filter((test) => test.outcome === "unexpected").length,
        flaky: tests.filter((test) => test.outcome === "flaky").length,
        skipped: tests.filter((test) => test.outcome === "skipped").length,
      };
      const sourceFiles = [
        "apps/runner/src/main.ts",
        "experiments/_shared/reactive-lab.ts",
        "experiments/interaction/command-palette/shared.ts",
        ...tests.map((test) => {
          const pattern = registry.patterns.find((candidate) => candidate.id === test.pattern_id)!;
          const variant = pattern.variants.find((candidate) => candidate.id === test.variant_id)!;
          return `experiments/${test.pattern_id}/${variant.entry}`;
        }),
      ];
      const harnessFiles = [
        "pattern-scenario-e2e/reactive-queue-boundary.spec.ts",
        "pattern-scenario-e2e/security-input-sinks.spec.ts",
        "pattern-scenario-e2e/security-interaction-boundaries.spec.ts",
        "playwright.pattern-scenario.config.ts",
        "scripts/reporters/pattern-scenario-evidence-reporter.ts",
        "scripts/verify-pattern-scenario-evidence.ts",
      ];
      const report = {
        schema_version: 1,
        id: "frontend-pattern-scenario-runtime-v1",
        created_at: result.startTime.toISOString(),
        status: result.status,
        command: "pnpm pattern-scenario:test",
        profile: "local-real-browser",
        counts,
        source_digest: `sha256:${await filesDigest(root, [...new Set(sourceFiles)])}`,
        harness_digest: `sha256:${await filesDigest(root, harnessFiles)}`,
        environment: {
          node: process.version,
          platform: process.platform,
          architecture: process.arch,
          playwright: playwrightPackage.version,
          browser_name: "chromium",
          browser_version: browserVersion,
          browser_channel: channel ?? "bundled",
          workers: this.config.workers,
          retries: Math.max(0, ...this.suite.allTests().map((test) => test.retries)),
          viewport: { width: 1280, height: 720, device_scale_factor: 1 },
          trace_mode: "on",
        },
        trace_contract: { per_variant: true, required_streams: ["action", "network", "resource"], oracle_attachment: "scenario-oracle" },
        retention_contract: { publish_on: "full-run-passed", failed_run: "retain-prior-success", swap: "staged-directory-rename-with-rollback" },
        completion_limits: [
          "incremental tranches: two boundary rows and six security rows only",
          "does not replace the remaining Pattern-specific Scenario gaps",
          "does not establish external Device, AT, Cloud, or HIL profiles",
          "does not establish independent Agent Forward Eval",
          "does not establish Authority-derived Atomic behavior completion",
        ],
        tests,
      };
      await writeFile(path.join(stagingRoot, "results.json"), `${JSON.stringify(report, null, 2)}\n`);
      const backupRoot = path.join(root, "artifacts/.pattern-scenarios-previous");
      await rm(backupRoot, { recursive: true, force: true });
      let retainedPrevious = false;
      try {
        await rename(outputRoot, backupRoot);
        retainedPrevious = true;
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
      }
      try {
        await rename(stagingRoot, outputRoot);
        stagingRoot = undefined;
      } catch (error) {
        if (retainedPrevious) await rename(backupRoot, outputRoot);
        throw error;
      }
      await rm(backupRoot, { recursive: true, force: true });
      return undefined;
    } catch (error) {
      if (stagingRoot) await rm(stagingRoot, { recursive: true, force: true });
      console.error(`Pattern Scenario Evidence Reporter failed: ${error instanceof Error ? error.stack ?? error.message : String(error)}`);
      return { status: "failed" };
    }
  }

  printsToStdio(): boolean { return false; }
}
