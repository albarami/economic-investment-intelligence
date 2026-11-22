import os from 'node:os';
import path from 'node:path';
import { defineConfig } from '@playwright/test';
import { browserHome } from './spikes/glyphs/browser-home.mjs';

process.env.PLAYWRIGHT_BROWSERS_PATH = browserHome(import.meta.url);

export default defineConfig({
  testDir: './tests/buildings',
  testMatch: 'shadow.spec.ts',
  workers: 1,
  retries: 0,
  reporter: 'list',
  timeout: 30000,
  outputDir: path.join(os.tmpdir(), 'buildings-results'),
  use: {
    viewport: { width: 640, height: 480 },
    deviceScaleFactor: 1,
    headless: true,
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
