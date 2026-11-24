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
  testDir: './tests/map',
  testMatch: 'answer.spec.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  timeout: 120_000,
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
