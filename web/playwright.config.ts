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
    // Builds into out-e2e/ so the suite can run while `next dev` is up. Both used to write to .next.
    command:
      `npm run build && node scripts/serve-static.mjs ${OUT} --data e2e/fixtures --port ${PORT}`,
    env: { NEXT_DIST_DIR: OUT, NEXT_PUBLIC_CONTACT_ENDPOINT: "https://contact.example.test/send" },
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 240_000,
  },
});
