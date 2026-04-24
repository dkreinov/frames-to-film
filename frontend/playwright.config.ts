import { defineConfig, devices } from '@playwright/test'

// CI uses pre-built static assets via `vite preview` — dev-mode on-demand
// module compilation is too slow on cold CI hardware, blows the 30s
// default setInputFiles timeout. Local dev keeps HMR via `npm run dev`.
const frontendCmd = process.env.CI
  ? 'npm run build && npx vite preview --host 127.0.0.1 --port 5173 --strictPort'
  : 'npm run dev'

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  fullyParallel: false,
  retries: 2,
  workers: 1,
  reporter: 'line',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      // Override via OLGA_PYTHON env var if your Python isn't on PATH.
      // e.g. OLGA_PYTHON=C:/path/to/python.exe npx playwright test
      command: `${process.env.OLGA_PYTHON ?? 'python'} -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`,
      cwd: '..',
      port: 8000,
      reuseExistingServer: !process.env.CI,
      stdout: 'pipe',
      stderr: 'pipe',
    },
    {
      command: frontendCmd,
      port: 5173,
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      stdout: 'pipe',
      stderr: 'pipe',
    },
  ],
})
