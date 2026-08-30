import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./pattern-scenario-e2e",
  testMatch: "*.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["line"], ["./scripts/reporters/pattern-scenario-evidence-reporter.ts"]],
  use: {
    channel: process.env.CI ? undefined : "chrome",
    headless: true,
    viewport: { width: 1280, height: 720 },
    trace: "on",
    screenshot: "off",
  },
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:5174",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
