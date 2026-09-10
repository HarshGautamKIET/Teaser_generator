import { defineConfig } from "@playwright/test";

/**
 * Drives the real stack: the frontend on 3001, the API on 8001, Supabase Auth
 * on 8000, and a real Gemini call. Nothing is mocked -- the point of this suite
 * is that the deployed containers work, which a mocked run cannot tell you.
 *
 * One worker, no retries. The flow signs up an account and pushes a video
 * through it; a retry would fetch and analyse the source a second time, which
 * costs another model call and would report a flaky pass as a pass.
 */
export default defineConfig({
  testDir: ".",
  // Real ingestion plus a real analysis call. The NASA source took 15s to fetch
  // and 57s to analyse when driven directly, so this is roughly 4x headroom.
  timeout: 10 * 60 * 1000,
  expect: { timeout: 30 * 1000 },
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3001",
    screenshot: "only-on-failure",
    video: "off",
    trace: "retain-on-failure",
    actionTimeout: 30 * 1000,
    viewport: { width: 1440, height: 900 },
  },
});
