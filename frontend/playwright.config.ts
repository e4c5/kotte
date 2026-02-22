import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright config for Kotte E2E and automation scripts.
 * Base URL: KOTTE_BASE_URL or http://localhost:5173
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: process.env.KOTTE_BASE_URL || 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  timeout: 60_000,
})
