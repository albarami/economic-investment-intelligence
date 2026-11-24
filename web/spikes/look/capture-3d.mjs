// npm --prefix web run spike:look:capture:3d
// The capture of the optional photoreal mode (G1 of round 5). Only the lead
// runs it, with MAPTILE_API_KEY in the environment of this command, which the
// page's own server reads; no test runs it against Google. It builds and
// serves the look page, asks the server for /photoreal/status and refuses
// (exit 1, a clear message, no browser and no request to Google) when the
// mode is unavailable. Otherwise it opens ONE page in ONE session, turns the
// mode on, shows the two views below one after the other, waits for each
// view's tiles (loaded, or held by the per-view budget of the spend guard),
// writes .overnight/OUT/look/3d/westbay.png and lusail.png at 1920 x 1080,
// and prints the project counter of billable root requests before and after.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  INSTALL,
  browserHome,
  shellInstalled,
} from '../glyphs/browser-home.mjs';
import { buildPage, removePage } from './build-page.mjs';
import { captureTarget } from './capture.mjs';
import { judgeRequests } from './guards.mjs';
import { MAX_BILLABLE } from './photoreal.mjs';
import { repositoryRoot, startLookServer } from './server.mjs';

const WALL = { width: 1920, height: 1080 };
const VIEW_WAIT_MS = 180_000;

// The brief's two views; sixty degrees is allowed while the mode is on.
export const VIEWS_3D = [
  {
    name: 'westbay',
    center: [51.53, 25.322],
    zoom: 16,
    pitch: 60,
    bearing: -25,
  },
  {
    name: 'lusail',
    center: [51.524, 25.385],
    zoom: 16,
    pitch: 60,
    bearing: 20,
  },
];

export const REFUSED =
  "REFUSED photoreal-unavailable: the page's server reports the photoreal mode unavailable (no MAPTILE_API_KEY in the environment of this command); no browser was opened and nothing was requested from Google";

// The page's own loopback server, through node:http (FE-11 keeps `fetch`
// for src/api/ alone).
function readStatus(origin) {
  return new Promise((resolve, reject) => {
    const request = http.get(`${origin}/photoreal/status`, (response) => {
      const chunks = [];
      response.on('data', (chunk) => chunks.push(chunk));
      response.on('end', () => {
        if (response.statusCode !== 200) {
          reject(new Error(`photoreal status ${response.statusCode}`));
          return;
        }
        try {
          resolve(JSON.parse(Buffer.concat(chunks).toString('utf8')));
        } catch (error) {
          reject(error);
        }
      });
    });
    request.on('error', reject);
  });
}

function counterLine(when, status) {
  return `photoreal counter ${when}: ${status.count} billable root requests of ${MAX_BILLABLE}, ${status.remaining} remaining, ${status.session} tile requests in this session`;
}

async function launchShell() {
  const browsers = browserHome(import.meta.url);
  if (!shellInstalled(browsers)) {
    throw new Error(`missing browser. Run: ${INSTALL}`);
  }
  process.env.PLAYWRIGHT_BROWSERS_PATH = browsers;
  const { chromium } = await import('@playwright/test');
  return chromium.launch();
}

async function shootViews(browser, origin, outDir, log) {
  const context = await browser.newContext({
    viewport: WALL,
    deviceScaleFactor: 1,
    reducedMotion: 'reduce',
    locale: 'en-QA',
    timezoneId: 'UTC',
  });
  const page = await context.newPage();
  const seen = [];
  page.on('request', (request) => seen.push(request.url()));
  await page.route('**/*', (route) => {
    const verdict = judgeRequests([route.request().url()], origin);
    return verdict.ok ? route.continue() : route.abort();
  });
  const written = [];
  try {
    await page.goto(`${origin}/en/_look?theme=dark`);
    await page.waitForFunction(
      () =>
        window.__look?.settled === true ||
        (window.__look?.failure ?? '') !== '',
      undefined,
      { timeout: 90_000 },
    );
    const failure = await page.evaluate(() => window.__look?.failure ?? '');
    if (failure !== '') throw new Error(`page failed: ${failure}`);
    await page.evaluate(() => window.__look?.photoreal?.toggle());
    await page.waitForFunction(
      () => window.__look?.photoreal?.state().on === true,
    );
    fs.mkdirSync(outDir, { recursive: true });
    for (const view of VIEWS_3D) {
      await page.evaluate((camera) => window.__look?.camera(camera), {
        center: view.center,
        zoom: view.zoom,
        pitch: view.pitch,
        bearing: view.bearing,
      });
      let settled = true;
      try {
        await page.waitForFunction(
          () => {
            const state = window.__look?.photoreal?.state();
            return state?.loaded === true || state?.held === true;
          },
          undefined,
          { timeout: VIEW_WAIT_MS },
        );
      } catch {
        settled = false;
      }
      await page.evaluate(() => window.__look?.rendered());
      const state = await page.evaluate(
        () => window.__look?.photoreal?.state() ?? null,
      );
      const file = path.join(outDir, `${view.name}.png`);
      fs.writeFileSync(
        file,
        await page.screenshot({ type: 'png', animations: 'disabled' }),
      );
      written.push(file);
      log(
        `${file} pitch ${await page.evaluate(() => window.__look?.pitch)} loaded ${state?.loaded === true} held ${state?.held === true}${settled ? '' : ' (not settled within the wait)'}`,
      );
    }
    const verdict = judgeRequests(seen, origin);
    if (!verdict.ok) throw new Error(verdict.detail);
  } finally {
    await context.close();
  }
  return written;
}

// `build`, `launch` and `serverOptions` are open for the test of the refusal,
// which runs with an empty key and an upstream that fails if it is called.
export async function capture3d({
  outDir,
  repository = repositoryRoot(),
  serverOptions = {},
  build = buildPage,
  remove = removePage,
  launch = launchShell,
  log = console.log,
}) {
  const root = await build();
  let server;
  let browser;
  try {
    server = await startLookServer(root, {
      repositoryRoot: repository,
      ...serverOptions,
    });
    const before = await readStatus(server.origin);
    log(counterLine('before', before));
    if (before.available !== true) return { ok: false, detail: REFUSED };
    try {
      browser = await launch();
      const written = await shootViews(browser, server.origin, outDir, log);
      return { ok: true, detail: '', written };
    } catch (error) {
      return {
        ok: false,
        detail: error instanceof Error ? error.message : String(error),
      };
    } finally {
      log(counterLine('after', await readStatus(server.origin)));
    }
  } finally {
    if (browser) await browser.close();
    if (server) await server.close();
    remove(root);
  }
}

function ignoredByGit(target) {
  const result = spawnSync('git', ['check-ignore', '-q', target], {
    cwd: repositoryRoot(import.meta.url),
    encoding: 'utf8',
  });
  return result.status === 0;
}

async function main() {
  const target = captureTarget();
  if (!ignoredByGit(target)) {
    console.error(`FAIL capture-target-not-ignored: ${target}`);
    process.exitCode = 1;
    return;
  }
  const result = await capture3d({ outDir: path.join(target, '3d') });
  if (!result.ok) {
    console.error(result.detail);
    process.exitCode = 1;
  }
}

if (
  process.argv[1] &&
  fileURLToPath(import.meta.url) === path.resolve(process.argv[1])
) {
  await main();
}
