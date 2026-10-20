import { defineConfig, devices } from '@playwright/test'

// Runs the production web build against a real API and PostGIS. Build first: `just e2e`.
const API_PORT = 8100
const WEB_PORT = 3300
const DATABASE_URL = process.env.CROPSTAR_E2E_DATABASE_URL
  ?? 'postgresql+psycopg://cropstar:cropstar@localhost:5432/cropstar'

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: 'retain-on-failure'
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'uv run cropstar-api serve',
      cwd: '../..',
      url: `http://127.0.0.1:${API_PORT}/api/healthz`,
      env: {
        CROPSTAR_HOST: '127.0.0.1',
        CROPSTAR_PORT: String(API_PORT),
        CROPSTAR_DATABASE_URL: DATABASE_URL,
        CROPSTAR_PUBLIC_BASE_URL: `http://localhost:${WEB_PORT}`
      },
      reuseExistingServer: !process.env.CI
    },
    {
      command: 'node .output/server/index.mjs',
      url: `http://127.0.0.1:${WEB_PORT}/healthz`,
      env: {
        NITRO_HOST: '127.0.0.1',
        NITRO_PORT: String(WEB_PORT),
        NUXT_API_BASE_URL: `http://127.0.0.1:${API_PORT}`
      },
      reuseExistingServer: !process.env.CI
    }
  ]
})
