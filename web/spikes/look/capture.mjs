// npm --prefix web run spike:look:capture
// Builds and serves the look page, opens it in the headless shell the glyph
// spike installs, and writes PNG files at a 1920 x 1080 CSS viewport: the
// answer screen of "Where should we operate?" in the four variants, a
// greyscale copy of each dark one, the English dark page at zoom 15 over
// Lusail with the extruded buildings, and the home in the four variants.
// npm --prefix web run spike:look:capture:street writes the sixteen street
// captures of round 5 (four cameras, both themes, both languages) into
// street/. The default target is .overnight/OUT/look/ at the repository
// root, which git must ignore. Without the basemap extract under
// data/basemap/ it fails and names the missing file.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  INSTALL,
  browserHome,
  shellInstalled,
} from '../glyphs/browser-home.mjs';
import { buildPage, removePage } from './build-page.mjs';
import {
  STREET_CAMERAS,
  VARIANTS,
  decodePng,
  encodeGreyPng,
  greyscale,
  judgeRequests,
} from './guards.mjs';
import { locateBasemap } from './release-build.mjs';
import { repositoryRoot, startLookServer } from './server.mjs';

const WALL = { width: 1920, height: 1080 };

export function captureTarget(moduleUrl = import.meta.url) {
  return path.join(repositoryRoot(moduleUrl), '.overnight', 'OUT', 'look');
}

async function shoot(context, origin, variant, view) {
  const page = await context.newPage();
  const seen = [];
  const errors = [];
  page.on('request', (request) => seen.push(request.url()));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('**/*', (route) => {
    const verdict = judgeRequests([route.request().url()], origin);
    return verdict.ok ? route.continue() : route.abort();
  });
  try {
    const home = view === 'home';
    const query = home ? '' : '&answer=operate';
    await page.goto(
      `${origin}/${variant.lang}/_look?theme=${variant.theme}${query}`,
    );
    await page.waitForFunction(
      () =>
        window.__look?.settled === true ||
        (window.__look?.failure ?? '') !== '',
      undefined,
      { timeout: 90_000 },
    );
    const failure = await page.evaluate(() => window.__look?.failure ?? '');
    if (failure !== '') throw new Error(`page failed: ${failure}`);
    // Round 5e, E1: never before the district plate's entrance has ended.
    await page.waitForFunction(() =>
      (
        document.querySelector('[data-part="district"]')?.getAnimations() ?? []
      ).every((animation) => animation.playState !== 'running'),
    );
    if (view === 'buildings') {
      await page.evaluate(() => window.__look?.showBuildings());
    } else if (typeof view === 'object') {
      await page.evaluate((camera) => window.__look?.camera(camera), {
        center: view.center,
        zoom: view.zoom,
        pitch: view.pitch,
        bearing: view.bearing,
      });
    }
    await page.evaluate(() => window.__look?.rendered());
    const requests = judgeRequests(seen, origin);
    if (!requests.ok) throw new Error(requests.detail);
    if (errors.length > 0) throw new Error(`console error: ${errors[0]}`);
    return await page.screenshot({ type: 'png', animations: 'disabled' });
  } finally {
    await page.close();
  }
}

export async function captureLook({
  outDir,
  repository = repositoryRoot(),
  street = false,
}) {
  const located = locateBasemap(repository);
  if (!located.ok) {
    return { ok: false, detail: `missing basemap extract: ${located.detail}` };
  }
  const browsers = browserHome(import.meta.url);
  if (!shellInstalled(browsers)) {
    return { ok: false, detail: `FAIL missing browser. Run: ${INSTALL}` };
  }
  process.env.PLAYWRIGHT_BROWSERS_PATH = browsers;
  const { chromium } = await import('@playwright/test');
  fs.mkdirSync(outDir, { recursive: true });
  const built = await buildPage();
  let server;
  let browser;
  const written = [];
  const write = (name, png) => {
    fs.writeFileSync(path.join(outDir, name), png);
    written.push({ name, bytes: png.length });
  };
  try {
    server = await startLookServer(built, { repositoryRoot: repository });
    browser = await chromium.launch();
    const context = await browser.newContext({
      viewport: WALL,
      deviceScaleFactor: 1,
      reducedMotion: 'no-preference',
      locale: 'en-QA',
      timezoneId: 'UTC',
    });
    if (street) {
      fs.mkdirSync(path.join(outDir, 'street'), { recursive: true });
      for (const camera of STREET_CAMERAS) {
        for (const variant of VARIANTS) {
          const png = await shoot(context, server.origin, variant, camera);
          write(
            path.join(
              'street',
              `${camera.name}-${variant.lang}-${variant.theme}.png`,
            ),
            png,
          );
        }
      }
      await context.close();
      return { ok: true, detail: '', written };
    }
    for (const variant of VARIANTS) {
      const name = `${variant.lang}-${variant.theme}`;
      const png = await shoot(context, server.origin, variant, 'answer');
      write(`${name}.png`, png);
      if (variant.theme === 'dark') {
        const decoded = decodePng(png);
        const grey = encodeGreyPng(
          decoded.width,
          decoded.height,
          greyscale(decoded),
        );
        write(`${name}-greyscale.png`, grey);
      }
    }
    const png = await shoot(
      context,
      server.origin,
      { lang: 'en', theme: 'dark' },
      'buildings',
    );
    write('en-dark-buildings.png', png);
    for (const variant of VARIANTS) {
      const homePng = await shoot(context, server.origin, variant, 'home');
      write(`home-${variant.lang}-${variant.theme}.png`, homePng);
    }
    await context.close();
  } catch (error) {
    return {
      ok: false,
      detail: error instanceof Error ? error.message : String(error),
      written,
    };
  } finally {
    if (browser) await browser.close();
    if (server) await server.close();
    removePage(built);
  }
  return { ok: true, detail: '', written };
}

// git checks the path itself, so nothing is created before the answer.
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
  const result = await captureLook({
    outDir: target,
    street: process.argv[2] === 'street',
  });
  if (!result.ok) {
    console.error(result.detail);
    process.exitCode = 1;
    return;
  }
  for (const item of result.written) {
    console.log(`${path.join(target, item.name)} ${item.bytes} bytes`);
  }
}

if (
  process.argv[1] &&
  fileURLToPath(import.meta.url) === path.resolve(process.argv[1])
) {
  await main();
}
