import { defineConfig, devices } from "@playwright/test";

const PORT = 3210;
const OUT = "out-e2e";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] }, testIgnore: "**/mobile.spec.ts" },
    { name: "mobile", use: { ...devices["Pixel 7"] }, testMatch: "**/mobile.spec.ts" },
  ],
  webServer: {
    // Build the static site, then serve it with the fixture data behind /data.
    //
    // Into its own build directory and its own export folder, so the suite never collides with a
    // running `next dev`. Both used to write to .next, and the resulting corruption showed up as
    // unrelated failures elsewhere rather than as an obvious conflict.
    command:
      `npm run build && node scripts/serve-static.mjs ${OUT} --data e2e/fixtures --port ${PORT}`,
    // Its own output directory, so the suite never collides with a running `next dev`. They shared
    // `.next` before, and the resulting corruption surfaced as unrelated failures elsewhere rather
    // than as an obvious conflict. Set here rather than in the shell, because `VAR=x cmd` is not
    // portable to Windows.
    env: { NEXT_DIST_DIR: OUT },
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 240_000,
  },
});
