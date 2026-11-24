/** Functional/pixel companion only. Never native performance evidence. */
import path from 'node:path';
import { defineConfig } from '@playwright/test';
process.env.PLAYWRIGHT_BROWSERS_PATH = path.resolve('../data/tools/playwright');
export default defineConfig({
  testDir: './tests/question_lab',
  testMatch: 'answers.spec.ts',
  outputDir: '../.overnight/tmp/question-lab-browser-results',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  updateSnapshots: 'none',
  snapshotPathTemplate: '{testDir}/baselines/{arg}{ext}',
  reporter: 'list',
  use: {
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
