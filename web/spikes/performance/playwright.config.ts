import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.SPIKE_BASE_URL ?? 'http://127.0.0.1:4173';

export default defineConfig({
  testDir: './tests',
  testMatch: ['performance.spec.ts', 'pause-click.spec.ts'],
  // This spike's own artifact folder: Playwright failure contexts, the
  // last-run marker and the JSON report all stay under it, so this run never
  // writes outside this spike and cannot collide with another browser
  // runner's artifacts when the web-checks suite runs one beside this run.
  outputDir: 'test-results',
  fullyParallel: false,
  retries: 0,
  workers: 1,
  timeout: 180_000,
  reporter: [
    ['list'],
    ['json', { outputFile: 'test-results/performance-timings.json' }],
  ],
  use: {
    ...devices['Desktop Chrome'],
    baseURL,
    viewport: { width: 1280, height: 720 },
    deviceScaleFactor: 2,
  },
});
