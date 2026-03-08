const path = require("path");
const { defineConfig, devices } = require("@playwright/test");

const repoRoot = __dirname;
const localBaseUrl = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8010";

module.exports = defineConfig({
  testDir: path.join(repoRoot, "e2e"),
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: localBaseUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium-desktop",
      use: {
        browserName: "chromium",
        viewport: { width: 1440, height: 1100 },
      },
    },
    {
      name: "chromium-tablet",
      use: {
        browserName: "chromium",
        viewport: { width: 768, height: 1024 },
      },
    },
    {
      name: "chromium-mobile",
      use: {
        ...devices["Pixel 7"],
      },
    },
  ],
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command:
          "bash -lc 'export APP_RUNTIME_DIR=.playwright-runtime APP_ASSET_VERSION=playwright && source backend/.venv/bin/activate && PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8010'",
        url: `${localBaseUrl}/login`,
        cwd: repoRoot,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
