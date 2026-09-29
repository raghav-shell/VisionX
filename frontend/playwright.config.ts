import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  retries: process.env.CI ? 1 : 0,
  use: { baseURL: process.env.VS_E2E_URL ?? "http://127.0.0.1:4173", trace: "retain-on-failure" },
  webServer: process.env.VS_E2E_URL ? undefined : [
    {
      // GitHub Actions installs Python with setup-python; it does not create
      // the repository-local .venv used by the Makefile development workflow.
      command: "python e2e_server.py",
      cwd: "../tests/e2e",
      url: "http://127.0.0.1:8000/api/system/info",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: "npm run start -- -p 4173",
      cwd: ".",
      url: "http://127.0.0.1:4173/workspace",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});
