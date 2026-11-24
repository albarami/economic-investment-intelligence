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

export default defineConfig({
  testDir: './tests',
  testMatch: [
    '**/answer.spec.ts',
    '**/draw.spec.ts',
    '**/source-geometry.spec.ts',
  ],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  timeout: 30_000,
  use: {
    baseURL: 'http://127.0.0.1:41731',
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    locale: 'en-QA',
    timezoneId: 'UTC',
    hasTouch: true,
    serviceWorkers: 'block',
  },
  webServer: {
    command: 'npx --no-install vite --host 127.0.0.1 --port 41731 --strictPort',
    url: 'http://127.0.0.1:41731',
    reuseExistingServer: false,
    timeout: 30_000,
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
