import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.SPIKE_BASE_URL ?? 'http://127.0.0.1:4173';

export default defineConfig({
  testDir: './tests',
  testMatch: 'performance.spec.ts',
  fullyParallel: false,
  retries: 0,
  workers: 1,
  timeout: 180_000,
  reporter: 'line',
  use: {
    ...devices['Desktop Chrome'],
    baseURL,
    viewport: { width: 1280, height: 720 },
    deviceScaleFactor: 2,
  },
});
