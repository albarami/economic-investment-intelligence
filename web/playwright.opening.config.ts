import path from 'node:path';
import { defineConfig } from '@playwright/test';
process.env.PLAYWRIGHT_BROWSERS_PATH = path.resolve('../data/tools/playwright');
export default defineConfig({
  testDir: './tests',
  outputDir: '../.overnight/tmp/S3-T10-browser-results',
  testMatch: ['e2e/opening.spec.ts', 'audit/opening.spec.ts'],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  reporter: 'list',
  use: {
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    locale: 'en-QA',
    timezoneId: 'UTC',
    hasTouch: true,
    serviceWorkers: 'block',
    launchOptions: {
      args: [
        '--use-gl=angle',
        '--use-angle=swiftshader',
        '--enable-unsafe-swiftshader',
      ],
    },
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
