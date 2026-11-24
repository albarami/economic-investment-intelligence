import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  INSTALL,
  browserHome,
  shellInstalled,
} from '../../glyphs/browser-home.mjs';
import { buildPage, removePage } from '../build-page.mjs';
import { startLookServer } from '../server.mjs';
import { locateBasemap } from '../release-build.mjs';
import { browserFailures } from './failure-reporter.mjs';

const SPIKE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const WEB = path.resolve(SPIKE, '../..');

export function browserEnvironment(origin, browsers) {
  return {
    ...process.env,
    EII_REGISTER_FILE: '',
    EII_REGISTER_DATE: '',
    EII_REGISTER_SOURCE: '',
    MAPTILE_API_KEY: '',
    PLAYWRIGHT_BROWSERS_PATH: browsers,
    LOOK_BASE_URL: origin,
  };
}

function launch(origin, browsers) {
  return new Promise((resolve) => {
    const child = spawn(
      process.execPath,
      [
        path.join(WEB, 'node_modules', '@playwright', 'test', 'cli.js'),
        'test',
        '--config',
        path.join(SPIKE, 'playwright.config.ts'),
        '--reporter',
        `list,${path.join(SPIKE, 'tests', 'failure-reporter.mjs')}`,
      ],
      {
        cwd: SPIKE,
        env: browserEnvironment(origin, browsers),
        stdio: ['ignore', 'pipe', 'inherit'],
      },
    );
    let output = '';
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', (chunk) => {
      output += chunk;
      process.stdout.write(chunk);
    });
    child.on('close', (code) =>
      resolve({
        status: code === null ? 1 : code,
        failures: browserFailures(output),
      }),
    );
  });
}

// With an extract, the default run selects the committed invented records.
// Without one it uses the empty build root, as the neutral-ground proof
// requires. A supplied repository root controls its own stand-in, including
// the empty root used to prove neutral ground. Ambient register settings,
// credentials and caller-supplied transports cannot enter either run.
export function startTestServer(root, options = {}) {
  const checkout = path.resolve(WEB, '..');
  const hasExtract = locateBasemap(checkout).ok;
  return startLookServer(root, {
    repositoryRoot: options.repositoryRoot ?? (hasExtract ? checkout : root),
    env: {},
    standInFile:
      options.repositoryRoot === undefined && hasExtract
        ? path.join(SPIKE, 'register', 'establishments.csv')
        : undefined,
    apiKey: '',
    sessionFile: path.join(root, 'test-accounting', 'session.json'),
    fetch: () =>
      Promise.reject(new Error('upstream forbidden in browser tests')),
  });
}

// `repositoryRoot` names the folder whose data/basemap/ the server reads;
// a folder without the extract gives the page's neutral ground, as on the
// hosted job.
export async function runSuite(options = {}) {
  const browsers =
    process.env.PLAYWRIGHT_BROWSERS_PATH ?? browserHome(import.meta.url);
  if (!shellInstalled(browsers)) {
    console.error(`FAIL missing browser. Run: ${INSTALL}`);
    return 1;
  }
  const outDir = await buildPage();
  let server;
  try {
    server = await startTestServer(outDir, options);
    const result = await launch(server.origin, browsers);
    if (result.status !== 0) options.onFailure?.(result.failures);
    return result.status;
  } finally {
    if (server) await server.close();
    removePage(outDir);
  }
}

if (
  process.argv[1] &&
  fileURLToPath(import.meta.url) === path.resolve(process.argv[1])
) {
  const status = await runSuite();
  process.exit(status);
}
