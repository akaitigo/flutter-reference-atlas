import { expect, test, type Page } from "@playwright/test";
import registry from "../packages/registry/generated/registry.json" with { type: "json" };

const scenario = "boundary";
const patternIds = [
  "reactive/background-sync-status",
  "reactive/network-offline-recovery",
] as const;

type AtlasState = {
  pattern: string;
  strategy: string;
  phase: string;
  connected: boolean;
  sequence: number;
  queued: number;
};

const readState = async (page: Page): Promise<AtlasState> => page.evaluate(() => {
  const state = window.__atlasState;
  if (!state) throw new Error("Runner state is missing.");
  return state as AtlasState;
});

for (const patternId of patternIds) {
  const pattern = registry.patterns.find((candidate) => candidate.id === patternId);
  if (!pattern) throw new Error(`Dedicated Scenario Pattern is missing: ${patternId}`);
  const observablePatternId = patternId.split("/").at(-1)!;
  for (const variant of pattern.variants) {
    test(`[pattern-scenario:${scenario}][pattern:${patternId}][variant:${variant.id}] bounds queued work under repeated input`, async ({ page }, testInfo) => {
      const runtimeErrors: string[] = [];
      page.on("console", (message) => {
        if (message.type() !== "error") return;
        const location = message.location().url;
        if (message.text().startsWith("Failed to load resource") && location.endsWith("/favicon.ico")) return;
        runtimeErrors.push(`console: ${message.text()} @ ${location}`);
      });
      page.on("pageerror", (error) => runtimeErrors.push(`pageerror: ${error.message}`));
      const parameters = new URLSearchParams({ pattern: patternId, variant: variant.id, parentOrigin: "http://localhost:5174", motion: "reduced" });
      const response = await page.goto(`http://localhost:5174/?${parameters}`);
      expect(response?.ok()).toBe(true);
      const lab = page.locator(".react-lab");
      await expect(lab).toHaveAttribute("data-phase", "initial");

      const observedQueueDepths: number[] = [];
      for (let index = 0; index < 8; index += 1) {
        await page.getByRole("button", { name: "Start fixture" }).click();
        const state = await readState(page);
        expect(state).toMatchObject({ pattern: observablePatternId, strategy: variant.id, phase: "active", connected: true, sequence: index + 1 });
        expect(state.queued).toBe(1);
        observedQueueDepths.push(state.queued);
      }

      await page.getByRole("button", { name: "Deny / disconnect" }).click();
      const disconnected = await readState(page);
      expect(disconnected).toMatchObject({ pattern: observablePatternId, strategy: variant.id, phase: "failed", connected: false, sequence: 8, queued: 1 });
      observedQueueDepths.push(disconnected.queued);

      await page.getByRole("button", { name: "Recover" }).click();
      const recovered = await readState(page);
      expect(recovered).toMatchObject({ pattern: observablePatternId, strategy: variant.id, phase: "recovered", connected: true, sequence: 9, queued: 0 });
      observedQueueDepths.push(recovered.queued);
      expect(Math.max(...observedQueueDepths)).toBe(1);
      expect(runtimeErrors).toEqual([]);

      testInfo.annotations.push({
        type: "scenario-oracle",
        description: JSON.stringify({
          kind: "bounded-queue",
          scenario,
          driven_actions: { repeated_start: 8, disconnect: 1, recover: 1 },
          observed_queue_depths: observedQueueDepths,
          maximum_queue_depth: 1,
          final_state: recovered,
        }),
      });
      await testInfo.attach("scenario-screenshot", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });
    });
  }
}

declare global {
  interface Window {
    __atlasState?: Record<string, string | number | boolean>;
  }
}
