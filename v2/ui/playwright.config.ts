import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  timeout: 30000,
  use: {
    baseURL: "http://127.0.0.1:8088",
    trace: "on-first-retry",
  },
  webServer: {
    command: "cd .. && /Users/khaxis/.local/bin/uv run plynx ui --no-browser --port 8088",
    url: "http://127.0.0.1:8088/health",
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
