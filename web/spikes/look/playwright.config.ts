import os from 'node:os';
import path from 'node:path';
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: 'look.spec.ts',
  // Failure records go to the temporary folder, not into the repository.
  outputDir: path.join(os.tmpdir(), 'eii-look-results'),
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  timeout: 120_000,
  use: {
    baseURL: process.env.LOOK_BASE_URL,
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    locale: 'en-QA',
    timezoneId: 'UTC',
    serviceWorkers: 'block',
    browserName: 'chromium',
  },
});
