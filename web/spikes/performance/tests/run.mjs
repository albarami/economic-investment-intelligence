import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  INSTALL,
  browserHome,
  shellInstalled,
} from '../../glyphs/browser-home.mjs';
import { buildPage } from '../build-page.mjs';
import { startStaticServer } from '../server.mjs';

const SPIKE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const WEB = path.resolve(SPIKE, '../..');

function launch(origin, browsers) {
  return new Promise((resolve) => {
    const child = spawn(
      process.execPath,
      [
        path.join(WEB, 'node_modules', '@playwright', 'test', 'cli.js'),
        'test',
        '--config',
        path.join(SPIKE, 'playwright.config.ts'),
      ],
      {
        cwd: SPIKE,
        env: {
          ...process.env,
          PLAYWRIGHT_BROWSERS_PATH: browsers,
          SPIKE_BASE_URL: origin,
        },
        stdio: 'inherit',
      },
    );
    child.on('exit', (code) => resolve(code === null ? 1 : code));
  });
}

export async function runSuite() {
  const browsers = browserHome(import.meta.url);
  if (!shellInstalled(browsers)) {
    console.error(`FAIL missing browser. Run: ${INSTALL}`);
    return 1;
  }
  const outDir = await buildPage();
  const sink = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-perf-trace-'));
  const server = await startStaticServer({
    mode: 'development',
    root: outDir,
    sink,
    evidenceDir: path.join(SPIKE, 'evidence'),
    native: false,
  });
  if (!server.ok) {
    console.error(`FAIL ${server.failure}`);
    fs.rmSync(outDir, { recursive: true, force: true });
    return 1;
  }
  try {
    return await launch(server.origin, browsers);
  } finally {
    await server.close();
    fs.rmSync(outDir, { recursive: true, force: true });
    fs.rmSync(sink, { recursive: true, force: true });
  }
}

if (
  process.argv[1] &&
  fileURLToPath(import.meta.url) === path.resolve(process.argv[1])
) {
  const status = await runSuite();
  process.exit(status);
}
