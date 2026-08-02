import { defineConfig, devices } from '@playwright/test'

/**
 * E2E smoke tests — boot the real backend (FastAPI + SQLite) and the real
 * frontend (Vite dev server with /api proxy), then exercise the auth flow
 * in a headed browser.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [['list']],
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      // Backend API (FastAPI + SQLite, dev settings)
      // Prefer the local venv; fall back to the system python (CI).
      command:
        'if [ -x .venv/bin/uvicorn ]; then .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000; else python -m uvicorn app.main:app --host 127.0.0.1 --port 8000; fi',
      cwd: '../backend',
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      // Frontend dev server (proxies /api → :8000)
      command: 'npx vite --port 5173 --strictPort',
      cwd: '.',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
})
