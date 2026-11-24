/**
 * Production basemap proof: the built bundle on the application server.
 * Nothing under /tiles or /fonts is intercepted; the tile archive, the
 * glyph files and the invented names are generated test assets only.
 */
import { expect, request, test, type Page } from '@playwright/test';
import type { Map as MapLibreMap } from 'maplibre-gl';
import { spawn, spawnSync, type ChildProcess } from 'node:child_process';
import {
  cpSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  renameSync,
  rmSync,
  symlinkSync,
} from 'node:fs';
import { createServer } from 'node:net';
import { createServer as createHttpServer, type Server } from 'node:http';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const WEB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const ROOT = path.resolve(WEB, '..');
const EXTRACT = '/tiles/basemap.pmtiles';
const FONT_URL = '/fonts/Noto%20Sans%20Medium';
const STACK_DIR = 'Noto Sans Medium';

interface Seen {
  request: string[];
  status: Map<string, number>;
}

interface AssetRoot {
  tiles: string;
  fonts: string;
}

type InspectedMap = Pick<MapLibreMap, 'queryRenderedFeatures' | 'getStyle'>;

let BASE = '';
let BROKEN_BASE = '';
let FOREIGN_BASE = '';
let foreignServer: Server | undefined;
let NAMES: { en: string; ar: string };
let work = '';
let fontsDir = '';
const servers: ChildProcess[] = [];

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const sock = createServer();
    sock.once('error', reject);
    sock.listen(0, '127.0.0.1', () => {
      const address = sock.address();
      sock.close(() =>
        resolve(typeof address === 'object' && address ? address.port : 0),
      );
    });
  });
}

function run(command: string, args: string[], cwd: string): void {
  const result = spawnSync(command, args, {
    cwd,
    encoding: 'utf8',
    timeout: 240_000,
  });
  expect(result.status, `${command} ${args.join(' ')}\n${result.stderr}`).toBe(
    0,
  );
}

async function serve(root: AssetRoot, web: string): Promise<string> {
  const port = await freePort();
  const proc = spawn(
    'uv',
    [
      'run',
      '--locked',
      'python',
      'product/tests/map_assets_server.py',
      '--tile-dir',
      root.tiles,
      '--font-dir',
      root.fonts,
      '--web-dir',
      web,
      '--port',
      String(port),
    ],
    { cwd: ROOT, stdio: 'ignore' },
  );
  servers.push(proc);
  const base = `http://127.0.0.1:${port}`;
  const deadline = Date.now() + 30_000;
  const probeContext = await request.newContext();
  try {
    for (;;) {
      try {
        const probe = await probeContext.get(`${base}/tiles`);
        if (probe.status() === 200) break;
      } catch {
        /* still starting */
      }
      expect(Date.now(), 'application server did not start').toBeLessThan(
        deadline,
      );
      await new Promise((wait) => setTimeout(wait, 100));
    }
  } finally {
    await probeContext.dispose();
  }
  return base;
}

async function serveForeignOrigin(): Promise<string> {
  // A distinct origin whose aborted response is caught by the browser plant.
  // Binding a numeric loopback address avoids any external resolver or egress.
  const server = createHttpServer((incoming) => incoming.socket.destroy());
  foreignServer = server;
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const address = server.address();
  if (!address || typeof address === 'string')
    throw new Error('foreign loopback server did not bind');
  return `http://127.0.0.1:${address.port}`;
}

function watch(page: Page): Seen {
  const seen: Seen = { request: [], status: new Map() };
  page.on('request', (request) => seen.request.push(request.url()));
  page.on('response', (response) =>
    seen.status.set(response.url(), response.status()),
  );
  return seen;
}

function sameOriginViolations(seen: Seen): string[] {
  return seen.request.filter(
    (url) => /^https?:/.test(url) && !url.startsWith(`${BASE}/`),
  );
}

function glyphRanges(seen: Seen): number[] {
  const found: number[] = [];
  for (const [url, status] of seen.status) {
    const match = new RegExp(`${FONT_URL}/(\\d+)-\\d+\\.pbf$`).exec(url);
    if (match && status === 200) found.push(Number(match[1]));
  }
  return found;
}

function routeCoverage(seen: Seen): string[] {
  const bad: string[] = [];
  const extractUrl = `${BASE}${EXTRACT}`;
  if (!seen.request.includes(extractUrl)) bad.push('no extract request');
  if (seen.status.get(extractUrl) !== 206) bad.push('no ranged extract bytes');
  const glyphs = seen.request.filter((url) => url.startsWith(`${BASE}/fonts/`));
  if (!glyphs.length) bad.push('no glyph request');
  if (!glyphs.every((url) => seen.status.get(url) === 200))
    bad.push('glyph request refused');
  if (!seen.request.some((url) => url.startsWith(`${BASE}/assets/`)))
    bad.push('no bundled asset request');
  return bad;
}

async function renderedFeatures(page: Page) {
  return page.evaluate(() => {
    const map = (globalThis as { eiiMap?: InspectedMap }).eiiMap;
    if (!map) return null;
    return map.queryRenderedFeatures().map((feature) => ({
      layer: feature.layer.id,
      sourceLayer: feature.sourceLayer,
      nameEn: feature.properties?.['name:en'],
      nameAr: feature.properties?.['name:ar'],
    }));
  });
}

async function labelProof(
  page: Page,
  seen: Seen,
  language: 'en' | 'ar',
): Promise<string[]> {
  const bad: string[] = [];
  const features = await renderedFeatures(page);
  if (!features?.some((feature) => feature.sourceLayer === 'earth'))
    bad.push('no rendered invented geometry');
  const place = features?.find((feature) => feature.layer === 'places_country');
  if (!place) {
    bad.push('no rendered place label');
  } else {
    if (place.nameEn !== NAMES.en) bad.push('english name missing');
    if (place.nameAr !== NAMES.ar) bad.push('arabic name missing');
  }
  const ranges = glyphRanges(seen);
  if (language === 'ar') {
    if (!ranges.some((start) => start >= 64256))
      bad.push('no shaped arabic glyph range served');
  } else if (!ranges.includes(0)) {
    bad.push('no latin glyph range served');
  }
  return bad;
}

async function attributionViolations(page: Page): Promise<string[]> {
  const text = await page
    .locator('[data-part="attribution"]')
    .first()
    .textContent({ timeout: 3_000 })
    .catch(() => null);
  const bad: string[] = [];
  if (!text?.includes('OpenStreetMap')) bad.push('missing osm credit');
  if (!text?.includes('Protomaps')) bad.push('missing protomaps credit');
  return bad;
}

async function liveCheck(
  page: Page,
  language: 'en' | 'ar',
  theme: 'dark' | 'light',
): Promise<void> {
  const seen = watch(page);
  await page.goto(`${BASE}/?lang=${language}&theme=${theme}`);
  await page.locator('.stage[data-state="ready"]').waitFor({ timeout: 60_000 });
  await expect
    .poll(
      async () =>
        (await renderedFeatures(page))?.some(
          (feature) => feature.layer === 'places_country',
        ),
      { timeout: 30_000 },
    )
    .toBe(true);

  expect(await page.locator('.maplibregl-canvas').count()).toBeGreaterThan(0);
  await expect(page.locator('.stage')).toHaveAttribute('dir', 'ltr');
  await expect(page.locator('.shell')).toHaveAttribute(
    'dir',
    language === 'ar' ? 'rtl' : 'ltr',
  );

  const style = await page.evaluate(() => {
    const map = (globalThis as { eiiMap?: InspectedMap }).eiiMap;
    if (!map) throw new Error('map inspection handle missing');
    return { glyphs: map.getStyle().glyphs };
  });
  expect(style.glyphs).toBe(`${BASE}/fonts/{fontstack}/{range}.pbf`);
  if (language === 'ar') {
    expect(
      seen.request.some((url) => url.includes('rtl-text')),
      'retained rtl plugin was never loaded',
    ).toBe(true);
  }

  const fontsLoaded = await page.evaluate(async () => {
    const faces = await Promise.all([
      document.fonts.load('16px "IBM Plex Sans"'),
      document.fonts.load('16px "IBM Plex Sans Arabic"'),
    ]);
    return faces.flat().length;
  });
  expect(fontsLoaded).toBeGreaterThan(0);

  expect(sameOriginViolations(seen)).toEqual([]);
  expect(routeCoverage(seen)).toEqual([]);
  expect(await labelProof(page, seen, language)).toEqual([]);
  expect(await attributionViolations(page)).toEqual([]);
}

test.beforeAll(async () => {
  work = mkdtempSync(path.join(tmpdir(), 'eii-map-'));
  const tiles = path.join(work, 'tiles');
  const fonts = path.join(work, 'fonts');
  fontsDir = fonts;
  const manifestPath = path.join(work, 'manifest.json');
  run(
    'uv',
    [
      'run',
      '--locked',
      'python',
      'product/tests/map_assets.py',
      '--tile-dir',
      tiles,
      '--font-dir',
      fonts,
      '--manifest',
      manifestPath,
    ],
    ROOT,
  );
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  NAMES = manifest.names;
  expect(existsSync(path.join(tiles, 'basemap.pmtiles'))).toBe(true);

  const web = path.join(work, 'web');
  run(
    'npx',
    ['--no-install', 'vite', 'build', '--outDir', web, '--emptyOutDir'],
    WEB,
  );
  expect(existsSync(path.join(web, 'index.html'))).toBe(true);

  BASE = await serve({ tiles, fonts }, web);
  mkdirSync(path.join(work, 'empty-tiles'));
  mkdirSync(path.join(work, 'empty-fonts'));
  BROKEN_BASE = await serve(
    {
      tiles: path.join(work, 'empty-tiles'),
      fonts: path.join(work, 'empty-fonts'),
    },
    web,
  );
  FOREIGN_BASE = await serveForeignOrigin();
});

test.afterAll(async () => {
  for (const proc of servers) proc.kill('SIGTERM');
  if (foreignServer) {
    await new Promise<void>((resolve, reject) => {
      foreignServer?.close((error) => (error ? reject(error) : resolve()));
    });
  }
  rmSync(work, { recursive: true, force: true });
});

const MATRIX: Array<{ lang: 'en' | 'ar'; theme: 'dark' | 'light' }> = [
  { lang: 'en', theme: 'dark' },
  { lang: 'en', theme: 'light' },
  { lang: 'ar', theme: 'dark' },
  { lang: 'ar', theme: 'light' },
];

for (const combo of MATRIX) {
  test(`offline invented basemap (${combo.lang}/${combo.theme})`, async ({
    page,
  }) => {
    await liveCheck(page, combo.lang, combo.theme);
  });
}

test('planted absent archive and glyphs fail every proof', async ({ page }) => {
  const seen = watch(page);
  await page.goto(`${BROKEN_BASE}/?lang=en&theme=dark`);
  await page.locator('.stage[data-state="ready"]').waitFor({ timeout: 60_000 });
  const features = await renderedFeatures(page);
  expect(
    features?.some((feature) => feature.sourceLayer === 'earth'),
  ).toBeFalsy();
  const coverage = routeCoverage(seen);
  expect(coverage).toContain('no ranged extract bytes');
  expect(coverage).toContain('no glyph request');
  expect(seen.request).toContain(`${BROKEN_BASE}${EXTRACT}`);
  expect(seen.status.get(`${BROKEN_BASE}${EXTRACT}`)).toBe(404);
});

test('a planted missing glyph file fails the arabic proof', async ({
  page,
}) => {
  const missing = path.join(fontsDir, STACK_DIR, '65024-65279.pbf');
  const held = `${missing}.held`;
  renameSync(missing, held);
  try {
    const seen = watch(page);
    await page.goto(`${BASE}/?lang=ar&theme=dark`);
    await page
      .locator('.stage[data-state="ready"]')
      .waitFor({ timeout: 60_000 });
    await page.waitForResponse(
      (response) => response.url().includes('65024-65279.pbf'),
      { timeout: 30_000 },
    );
    expect(seen.status.get(`${BASE}${FONT_URL}/65024-65279.pbf`)).toBe(404);
    expect(routeCoverage(seen)).toContain('glyph request refused');
  } finally {
    renameSync(held, missing);
  }
});

test('a planted wrong-type file and a symlink escape are refused', async ({
  page,
}) => {
  const wrong = path.join(fontsDir, STACK_DIR, '0-255.woff2');
  cpSync(path.join(fontsDir, STACK_DIR, '0-255.pbf'), wrong);
  try {
    const response = await page.request.get(`${BASE}${FONT_URL}/0-255.woff2`);
    expect(response.status()).toBe(404);
  } finally {
    rmSync(wrong);
  }

  const stack = path.join(fontsDir, STACK_DIR);
  const escaped = path.join(work, 'escaped-stack');
  const latin = path.join(escaped, '0-255.pbf');
  mkdirSync(escaped);
  cpSync(path.join(stack, '0-255.pbf'), latin);
  renameSync(stack, `${stack}.held`);
  symlinkSync(escaped, stack, 'dir');
  try {
    const response = await page.request.get(`${BASE}${FONT_URL}/0-255.pbf`);
    expect(response.status()).toBe(404);
    const seen = watch(page);
    await page.goto(`${BASE}/?lang=en&theme=dark`);
    await page
      .locator('.stage[data-state="ready"]')
      .waitFor({ timeout: 60_000 });
    await page.waitForResponse((response) =>
      response.url().includes(`${FONT_URL}/0-255.pbf`),
    );
    expect(routeCoverage(seen)).toContain('glyph request refused');
    expect(await labelProof(page, seen, 'en')).toContain(
      'no latin glyph range served',
    );
  } finally {
    rmSync(stack, { force: true });
    renameSync(`${stack}.held`, stack);
  }
});

test('a foreign request fails the same-origin guard', async ({ page }) => {
  const seen = watch(page);
  await page.goto(`${BASE}/?lang=en&theme=dark`);
  await page.locator('.stage[data-state="ready"]').waitFor({ timeout: 60_000 });
  const foreignUrl = `${FOREIGN_BASE}/pixel.css`;
  expect(new URL(foreignUrl).origin).not.toBe(new URL(BASE).origin);
  expect(new URL(foreignUrl).hostname).toBe('127.0.0.1');
  const outcome = await page.evaluate(
    (url) =>
      new Promise<string>((resolve) => {
        const planted = new XMLHttpRequest();
        planted.open('GET', url);
        planted.addEventListener('error', () => resolve('caught failure'));
        planted.addEventListener('load', () => resolve('unexpected response'));
        planted.send();
      }),
    foreignUrl,
  );
  expect(outcome).toBe('caught failure');
  await expect.poll(() => seen.request.includes(foreignUrl)).toBe(true);
  expect(sameOriginViolations(seen)).toEqual([foreignUrl]);
  expect(seen.status.has(foreignUrl)).toBe(false);
});

test('a removed attribution fails the credit guard', async ({ page }) => {
  await page.goto(`${BASE}/?lang=en&theme=dark`);
  await page.locator('.stage[data-state="ready"]').waitFor({ timeout: 60_000 });
  expect(await attributionViolations(page)).toEqual([]);
  await page.evaluate(() => {
    document.querySelector('[data-part="attribution"]')?.remove();
  });
  expect(await attributionViolations(page)).toContain('missing osm credit');
});

test('a fixture log without production routes fails coverage', async () => {
  const fabricated: Seen = {
    request: [`${BASE}/`, `${BASE}/assets/index.js`],
    status: new Map([
      [`${BASE}/`, 200],
      [`${BASE}/assets/index.js`, 200],
    ]),
  };
  expect(routeCoverage(fabricated).length).toBeGreaterThan(0);
});
