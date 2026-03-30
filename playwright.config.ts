import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: "html",

  use: {
    baseURL: "http://localhost:5173",
    locale: "he-IL",
    colorScheme: "light",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 430, height: 932 },
      },
    },
  ],

  webServer: [
    {
      command: "cd backend && uvicorn app.main:app --port 8000",
      port: 8000,
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command: "cd frontend && npm run dev",
      port: 5173,
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
});
