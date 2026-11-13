import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { defineConfig } from '@playwright/test';

function browserHome(moduleUrl: string): string {
  let dir = fileURLToPath(new URL('.', moduleUrl));
  if (dir.endsWith('/')) dir = dir.slice(0, -1);
  for (let step = 0; step < 8; step += 1) {
    if (
      existsSync(`${dir}/pins.toml`) &&
      existsSync(`${dir}/web/package.json`)
    ) {
      return `${dir}/data/tools/playwright`;
    }
    const slash = dir.lastIndexOf('/');
    const parent = slash <= 0 ? dir : dir.slice(0, slash);
    if (parent === dir) break;
    dir = parent;
  }
  throw new Error('repository root was not found');
}

process.env.PLAYWRIGHT_BROWSERS_PATH = browserHome(import.meta.url);

const capture = process.env.SPIKE_CAPTURE === '1';

export default defineConfig({
  testDir: './tests',
  testMatch: 'glyphs.spec.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  timeout: 30_000,
  updateSnapshots: capture ? 'all' : 'none',
  snapshotPathTemplate: capture
    ? '../../../data/glyph-captures/{arg}-{projectName}-{platform}{ext}'
    : '{testDir}/baselines/{arg}-{projectName}-{platform}{ext}',
  expect: {
    toHaveScreenshot: {
      animations: 'disabled',
      caret: 'hide',
      scale: 'css',
    },
  },
  use: {
    baseURL: process.env.SPIKE_BASE_URL,
    viewport: { width: 960, height: 640 },
    deviceScaleFactor: 1,
    locale: 'en-QA',
    timezoneId: 'UTC',
    colorScheme: 'light',
    serviceWorkers: 'block',
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
