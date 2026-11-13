import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { INSTALL, browserHome, shellInstalled } from '../browser-home.mjs';
import { buildPage, removePage } from '../build-page.mjs';
import { startServer } from '../server.mjs';

const SPIKE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const WEB = path.resolve(SPIKE, '../..');

export const PIXEL_LINE =
  "no pixel was compared; the pixel comparison runs in the hosted job's own step, or a direct run of the command with CI=true, and does not run in ./eii test, anywhere";

const SCREENSHOT_NAMES = [
  'arabic-labels',
  'english-labels',
  'hexagons-below-labels',
];

export function comparisonReport(ci) {
  if (ci === 'true') return { compared: true, line: '' };
  return { compared: false, line: PIXEL_LINE };
}

export function baselineRelative(name) {
  return `spikes/glyphs/tests/baselines/${name}-chromium-linux.png`;
}

export function missingBaseline(present) {
  for (const name of SCREENSHOT_NAMES) {
    const relative = baselineRelative(name);
    if (!present(relative)) return relative;
  }
  return '';
}

export function runChild(executable, args) {
  const result = spawnSync(executable, args, { encoding: 'utf8' });
  if (result.error) return 1;
  return result.status === null ? 1 : result.status;
}

function browserMissing() {
  return !shellInstalled(browserHome(import.meta.url));
}

function playwright(origin, capture) {
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
          PLAYWRIGHT_BROWSERS_PATH: browserHome(import.meta.url),
          SPIKE_BASE_URL: origin,
          SPIKE_CAPTURE: capture ? '1' : '0',
        },
        stdio: 'inherit',
      },
    );
    child.on('exit', (code) => resolve(code === null ? 1 : code));
  });
}

export function gateStatus(input) {
  if (input.capture && input.ci !== 'true') return 2;
  if (!input.browserPresent) return 1;
  return 0;
}

export function gateDetail(input) {
  const status = gateStatus(input);
  if (status === 2) {
    return {
      status,
      detail:
        'spike screenshot captures are created only in the CI environment',
    };
  }
  if (status === 1) {
    return { status, detail: `FAIL missing browser. Run: ${INSTALL}` };
  }
  return { status: 0, detail: '' };
}

export async function runSuite() {
  const capture = process.argv.includes('--capture');
  const report = comparisonReport(process.env.CI);
  if (report.compared && !capture) {
    const relative = missingBaseline((item) =>
      fs.existsSync(path.join(WEB, item)),
    );
    if (relative) {
      console.error(`missing baseline: ${relative}`);
      return 1;
    }
  }
  const gated = gateDetail({
    capture,
    ci: process.env.CI,
    browserPresent: !browserMissing(),
  });
  if (gated.status !== 0) {
    console.error(gated.detail);
    return gated.status;
  }
  if (!report.compared) console.log(report.line);
  const built = buildPage();
  if (!built.ok) {
    console.error(built.detail);
    return 1;
  }
  let server;
  try {
    server = await startServer(built.outDir);
    return await playwright(server.origin, capture);
  } finally {
    if (server) await server.close();
    removePage(built.outDir);
  }
}

if (
  process.argv[1] &&
  fileURLToPath(import.meta.url) === path.resolve(process.argv[1])
) {
  const status = await runSuite();
  process.exit(status);
}
