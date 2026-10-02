import { defineConfig } from "@playwright/test";

// The servers are started by `python scripts/dev.py e2e`, which also supplies the test password.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5174",
    channel: "chrome",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
    { name: "phone", use: { viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true } },
  ],
});
