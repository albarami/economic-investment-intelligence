/**
 * S3-T12, RV1 finding 4: the built application in a real browser through
 * `App`. Invented accident outlines, a planned rail line, a planned station
 * and a rail protection polygon are drawn on the map together with the
 * accident count and the access-pending panel, in both languages. Map
 * rendering is proven by the GPU picking of each drawn geometry under a
 * pointer click. The bundle is served on a port the system assigns; every
 * `/api/` route is answered in the page from the mounted invented bodies of
 * `web/tests/fixtures/accident-layer.json`; nothing leaves the loopback.
 */
import { expect, test, type Page } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  statSync,
} from 'node:fs';
import { createServer, type Server } from 'node:http';
import path from 'node:path';

import mounted from '../fixtures/accident-layer.json' with { type: 'json' };
import { text, type Language } from '../../src/i18n';
import type { LayerFeature } from '../../src/stage/layers/payload';

const WEB = process.cwd();
const ROOT = path.resolve(WEB, '..');

test.use({
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
});
test.describe.configure({ mode: 'serial', timeout: 120_000 });

type Ring = [number, number][];
const square = (x: number, y: number, w: number, h: number): Ring => [
  [x, y],
  [x + w, y],
  [x + w, y + h],
  [x, y + h],
  [x, y],
];
const plain = (name: string) => [{ kind: 'plain' as const, text: name }];

/** Invented geometry: two separate accident zones and three rail features. */
const ZONE_A = square(0, 0, 1, 1);
const ZONE_B = square(2, 0, 1, 1);
const LINE: [number, number][] = [
  [0, 2.5],
  [3, 2.5],
];
const PROTECTION = square(1.8, 1.4, 0.8, 0.6);
const STATION: [number, number] = [1, 2];

function bodies() {
  const http = structuredClone(mounted) as unknown as {
    release: { basemap_url: string | null };
    chains: Record<string, unknown>;
    accidents: { payload: { layers: { features: LayerFeature[] }[] } };
    rail_plan: { payload: { layers: { features: LayerFeature[] }[] } };
  };
  // The basemap archive itself is absent (404); the stage still draws.
  http.release.basemap_url = '/tiles/basemap.pmtiles';
  const [a, b] = http.accidents.payload.layers[0]!.features;
  a!.ring = ZONE_A;
  b!.ring = ZONE_B;
  const rail = http.rail_plan.payload.layers[0]!;
  const station = rail.features[0]!;
  station.position = STATION;
  const shared = {
    metric_key: 'rail_feature',
    provenance: 'public',
    subject: 'gis_feature',
    source_id: station.source_id,
  } as const;
  rail.features.push(
    {
      ...shared,
      feature_id: 'rail_plan:INVENTED-line',
      geometry_kind: 'line',
      path: LINE,
      name_segments: plain('INVENTED-planned-line'),
    },
    {
      ...shared,
      feature_id: 'rail_plan:INVENTED-protection',
      geometry_kind: 'outline',
      ring: PROTECTION,
      name_segments: plain('INVENTED-protection-zone'),
    },
  );
  return http;
}

const CONTENT: Record<string, string> = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.woff2': 'font/woff2',
  '.png': 'image/png',
};

let work = '';
let server: Server;
let origin = '';

test.beforeAll(async () => {
  const tmp = path.join(ROOT, '.overnight/tmp');
  mkdirSync(tmp, { recursive: true });
  work = mkdtempSync(path.join(tmp, 'accident-browser-'));
  const build = spawnSync(
    'npx',
    ['--no-install', 'vite', 'build', '--outDir', work, '--emptyOutDir'],
    { cwd: WEB, encoding: 'utf8', timeout: 120_000 },
  );
  expect(build.status, build.stdout + build.stderr).toBe(0);
  server = createServer((request, response) => {
    const url = new URL(request.url ?? '/', 'http://loopback.invalid');
    const relative = url.pathname === '/' ? 'index.html' : url.pathname;
    const file = path.join(work, path.normalize(relative));
    const inside = file.startsWith(work + path.sep);
    if (!inside || !statSync(file, { throwIfNoEntry: false })?.isFile()) {
      response.writeHead(404).end();
      return;
    }
    response
      .writeHead(200, {
        'content-type':
          CONTENT[path.extname(file)] ?? 'application/octet-stream',
      })
      .end(readFileSync(file));
  });
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('no port');
  origin = `http://127.0.0.1:${address.port}`;
});

test.afterAll(async () => {
  await new Promise<void>((resolve) => server?.close(() => resolve()));
  if (work) rmSync(work, { recursive: true, force: true });
});

/** Answers every `/api/` request in the page; records every request. */
async function serveApi(page: Page): Promise<string[]> {
  const http = bodies();
  const seen: string[] = [];
  page.on('request', (request) => seen.push(request.url()));
  await page.route(`${origin}/api/**`, (route) => {
    const pathname = new URL(route.request().url()).pathname;
    const body =
      pathname === '/api/release'
        ? http.release
        : pathname === '/api/layers/accidents'
          ? http.accidents
          : pathname === '/api/layers/rail_plan'
            ? http.rail_plan
            : pathname.startsWith('/api/facts/')
              ? http.chains[pathname.split('/')[3]!]
              : {};
    return route.fulfill({ json: body });
  });
  return seen;
}

async function chooseAccidents(page: Page, language: Language) {
  await page.goto(`${origin}/?lang=${language}&theme=dark`);
  await page.locator('[data-action="guided-story"]').click();
  await page.locator('.stage[data-state="ready"]').waitFor({ timeout: 60_000 });
  await page.locator('.layer-chooser select').selectOption('accidents');
  await expect(page.locator('[data-part="access-pending"]')).toHaveText(
    text(language, 'layers.access.pending'),
  );
  await page.evaluate(() => {
    const map = (
      globalThis as unknown as {
        eiiMap: { jumpTo: (options: unknown) => void };
      }
    ).eiiMap;
    map.jumpTo({ center: [1.5, 1.25], zoom: 7, bearing: 0, pitch: 0 });
  });
}

/** The page pixel of a coordinate, and the element drawn at it. */
async function pixel(page: Page, lon: number, lat: number) {
  return page.evaluate(
    ([x, y]) => {
      const map = (
        globalThis as unknown as {
          eiiMap: {
            project: (at: [number, number]) => { x: number; y: number };
            getCanvas: () => HTMLCanvasElement;
          };
        }
      ).eiiMap;
      const point = map.project([x, y]);
      const box = map.getCanvas().getBoundingClientRect();
      const at = { x: box.left + point.x, y: box.top + point.y };
      const hit = document.elementFromPoint(at.x, at.y);
      return { ...at, canvas: hit === map.getCanvas() };
    },
    [lon, lat] as const,
  );
}

const panel = (page: Page, layer: string) =>
  page.locator(`[data-part="feature-panel"][data-layer="${layer}"]`);

/**
 * Clicks the map where a drawn geometry lies; the GPU picking of that
 * geometry is what selects it. A one-pixel stroke may round to the next
 * pixel, so the neighbouring pixels are tried too.
 */
async function pick(
  page: Page,
  at: readonly [number, number],
  selected: () => Promise<boolean>,
) {
  const centre = await pixel(page, at[0], at[1]);
  expect(centre.canvas, 'the map canvas is under the pointer').toBe(true);
  await expect(async () => {
    for (const [dx, dy] of [
      [0, 0],
      [1, 0],
      [-1, 0],
      [0, 1],
      [0, -1],
    ] as const) {
      await page.mouse.click(centre.x + dx, centre.y + dy);
      if (await selected()) return;
    }
    throw new Error(`nothing drawn was picked at ${at.join(',')}`);
  }).toPass({ timeout: 20_000 });
}

/** Clicks a coordinate and resolves once the map has handled the click. */
async function clickHandled(page: Page, at: readonly [number, number]) {
  const point = await pixel(page, at[0], at[1]);
  expect(point.canvas, 'the map canvas is under the pointer').toBe(true);
  await page.evaluate(() => {
    const scope = globalThis as unknown as {
      eiiMap: { once: (event: string, run: () => void) => void };
      eiiClicked?: Promise<void>;
    };
    scope.eiiClicked = new Promise<void>((done) => {
      scope.eiiMap.once('click', () =>
        requestAnimationFrame(() => requestAnimationFrame(() => done())),
      );
    });
  });
  await page.mouse.click(point.x, point.y);
  await page.evaluate(
    () => (globalThis as unknown as { eiiClicked: Promise<void> }).eiiClicked,
  );
}

async function nameShown(page: Page, layer: string, name: string) {
  const shown = panel(page, layer).locator('[data-label="name"]');
  return (await shown.count()) === 1 && (await shown.textContent()) === name;
}

/** Opens the map evidence inspector for a check, then closes it again. */
async function inspect(page: Page, check: () => Promise<void>) {
  const summary = page.locator('details.layer-inspector > summary');
  await summary.click();
  await expect(page.locator('details.layer-inspector')).toHaveAttribute(
    'open',
    '',
  );
  await check();
  await summary.click();
  await expect(page.locator('details.layer-inspector')).not.toHaveAttribute(
    'open',
  );
}

function noDigitOutsideChips(page: Page) {
  return page.locator('[data-part="public-layers"]').evaluate((plate) => {
    const clone = plate.cloneNode(true) as HTMLElement;
    clone.querySelectorAll('[data-fact-chip]').forEach((node) => node.remove());
    return /\p{Nd}/u.test(clone.textContent ?? '');
  });
}

for (const language of ['en', 'ar'] as const) {
  test(`draws accident outlines with planned rail, the count and pending access in ${language}`, async ({
    page,
  }, info) => {
    const seen = await serveApi(page);
    await chooseAccidents(page, language);
    const plate = page.locator('[data-part="public-layers"]');
    await expect(plate).toHaveAttribute(
      'dir',
      language === 'ar' ? 'rtl' : 'ltr',
    );
    await expect(plate.locator('[data-legend="station"]')).toHaveText(
      text(language, 'layers.station.planned'),
    );
    await expect(plate.locator('[data-part="layer-refusal"]')).toHaveCount(0);
    await expect(plate.locator('[data-part="layer-no-data"]')).toHaveCount(0);

    const accidents = bodies().accidents.payload.layers[0]!.features;
    const facts = (
      mounted as unknown as {
        accidents: { facts: { fact_id: string; period: string }[] };
      }
    ).accidents.facts;
    for (const [feature, edge] of [
      [accidents[0]!, [0, 0.5]],
      [accidents[1]!, [3, 0.5]],
    ] as const) {
      const count = panel(page, 'accidents').locator(
        `[data-fact-chip="value"][data-fact-id="${feature.fact_id}"]`,
      );
      await pick(page, edge, async () => (await count.count()) === 1);
      await expect(count).toHaveAttribute('data-state', 'ready');
      const context = panel(page, 'accidents').locator(
        '[data-part="accident-context"]',
      );
      await expect(context).toHaveAttribute('data-zone', feature.source_zone!);
      await expect(context).toHaveAttribute(
        'data-period',
        facts.find((fact) => fact.fact_id === feature.fact_id)!.period,
      );
      await expect(
        context.locator(`[data-record="${feature.source_zone_fact_id}"]`),
      ).toContainText(feature.source_zone!);
      await expect(context.locator('[data-caveat="accidents"]')).toHaveText(
        text(language, 'layers.accidents.caveat'),
      );
      // The count and the pending access stand together on the screen.
      await inspect(page, async () => {
        await expect(count).toBeVisible();
        await expect(
          page.locator('[data-part="access-pending"]'),
        ).toBeVisible();
        await page.screenshot({
          path: info.outputPath(
            `accident-${language}-${feature.source_zone}.png`,
          ),
        });
      });
    }

    await pick(page, [1.5, 2.5], () =>
      nameShown(page, 'rail_plan', 'INVENTED-planned-line'),
    );
    await pick(page, [1.8, 1.7], () =>
      nameShown(page, 'rail_plan', 'INVENTED-protection-zone'),
    );
    await pick(
      page,
      STATION,
      async () =>
        (await panel(page, 'rail_plan')
          .locator('[data-label="station"]')
          .count()) === 1,
    );
    await expect(
      panel(page, 'rail_plan').locator('[data-label="station"]'),
    ).toHaveText(text(language, 'layers.station.planned'));

    // An outline is drawn unfilled: its interior picks nothing. Each click
    // comes after the layers proved pickable above, and is read only after
    // the map's own click and two frames; the station stays selected.
    for (const inside of [
      [0.5, 0.5],
      [2.5, 0.5],
      [2.2, 1.7],
    ] as const) {
      await clickHandled(page, inside);
      await expect(page.locator('[data-part="feature-panel"]')).toHaveCount(1);
      await expect(
        panel(page, 'rail_plan').locator('[data-label="station"]'),
      ).toHaveCount(1);
    }

    expect(await noDigitOutsideChips(page)).toBe(false);
    expect(
      seen.filter((url) => /^https?:/.test(url) && !url.startsWith(origin)),
    ).toEqual([]);
  });
}
