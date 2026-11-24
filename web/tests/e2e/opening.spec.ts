import { test, expect } from './opening-fixture';
import type { Page } from '@playwright/test';
import { readStoryFrames } from '../../src/api/public-opening';
import { openingProblems } from '../audit/opening-audit';

async function chooseActivity(page: Page, lang: 'en' | 'ar') {
  await page
    .locator('[data-picker="activity"] input')
    .fill(lang === 'en' ? 'INVENTED-Craft' : 'حرفة مخترعة');
  await page.locator('[data-picker="activity"] button[type="submit"]').click();
  await page.locator('[data-picker="activity"] [data-candidate]').click();
}
async function choosePlace(page: Page, lang: 'en' | 'ar') {
  await page
    .locator('[data-picker="place"] input')
    .fill(lang === 'en' ? 'INVENTED-Garden' : 'حديقة مخترعة');
  await page.locator('[data-picker="place"] button[type="submit"]').click();
  await page.locator('[data-picker="place"] [data-candidate]').click();
  await page.locator('[data-place-preset="walk-a"]').click();
  await expect(page.locator('[data-action="story-next"]')).toBeEnabled();
}
type Mode = 'polygon' | 'distance' | 'walk' | 'drive';
/** Opening to a chosen area of the given mode, ready for the story. */
async function selectArea(
  page: Page,
  origin: string,
  lang: 'en' | 'ar',
  mode: Mode,
  theme: 'dark' | 'light' = 'dark',
) {
  await page.goto(origin + '/?lang=' + lang + '&theme=' + theme);
  await page.locator('[data-action="guided-story"]').click();
  await page.locator('.stage[data-state="ready"]').waitFor();
  await chooseActivity(page, lang);
  await page.evaluate(() => {
    const map = (
      globalThis as unknown as {
        eiiMap: { jumpTo: (options: unknown) => void };
      }
    ).eiiMap;
    map.jumpTo({ center: [1, 1], zoom: 14 });
  });
  await page.locator('.drawing-disclosure > summary').click();
  await page
    .locator(
      `[data-tool="${mode === 'polygon' ? 'polygon' : mode === 'distance' ? 'radius' : 'travel'}"]`,
    )
    .click();
  if (mode !== 'polygon') {
    await page.locator('.drawing-disclosure > summary').click();
    await page
      .locator(
        `[data-preset="${mode === 'distance' ? 'distance-b' : mode === 'walk' ? 'walk-c' : 'drive-c'}"]`,
      )
      .click();
  }
  const overlay = page.locator('[data-part="area-overlay"]');
  const box = await overlay.boundingBox();
  if (!box) throw new Error('map overlay missing');
  const x = box.width / 2,
    y = box.height / 2;
  if (mode === 'polygon') {
    for (const [dx, dy] of [
      [-100, 80],
      [100, 80],
      [0, -100],
    ])
      await overlay.click({ position: { x: x + dx!, y: y + dy! } });
    await page.locator('[data-part="knob"]').first().click();
    await expect(overlay).toHaveAttribute('data-closed', 'yes');
    const knob = page.locator('[data-part="knob"]').nth(1);
    const before = await knob.getAttribute('style');
    await knob.click();
    await overlay.click({ position: { x: x + 140, y: y + 100 } });
    expect(await knob.getAttribute('style')).not.toBe(before);
  } else await overlay.click({ position: { x, y } });
  await page.locator('.drawing-disclosure > summary').click();
  await page.locator('[data-part="use-area"]').click();
  await expect(page.locator('[data-action="story-next"]')).toBeEnabled();
}
const WIDER_EN = 'The dashed line marks the wider context area.';
const WIDER_AR = 'الخط المتقطّع يحدّد منطقة السياق الأوسع.';
type Outline = { type: string; coordinates: number[][][] };
/** Ring and legend together; the ring is dashed and lies on exactly `outline`. */
async function expectRing(page: Page, lang: 'en' | 'ar', outline: Outline) {
  await expect(page.locator('.stage')).toHaveAttribute(
    'data-directive',
    'rings',
  );
  const ring = page.locator('[data-part="context-ring"]');
  await expect(ring).toHaveCount(1);
  await expect(page.locator('[data-part="context-area"]')).toHaveText(
    lang === 'en' ? WIDER_EN : WIDER_AR,
  );
  await expect(page.locator('[data-part="context-area"]')).toHaveAttribute(
    'dir',
    lang === 'en' ? 'ltr' : 'rtl',
  );
  const line = ring.locator('.context-ring-line');
  expect(
    await line.evaluate((node) => getComputedStyle(node).strokeDasharray),
  ).toBe('6px, 4px');
  expect(outline.type).toBe('Polygon');
  const gap = () =>
    line.evaluate((node, ringCoordinates) => {
      const map = (
        globalThis as unknown as {
          eiiMap: { project: (p: number[]) => { x: number; y: number } };
        }
      ).eiiMap;
      const drawn = (node.getAttribute('points') ?? '')
        .split(' ')
        .map((pair) => pair.split(',').map(Number));
      if (drawn.length !== ringCoordinates.length) return Infinity;
      return Math.max(
        ...ringCoordinates.map((point, index) => {
          const screen = map.project(point);
          const [x, y] = drawn[index]!;
          return Math.max(Math.abs(screen.x - x!), Math.abs(screen.y - y!));
        }),
      );
    }, outline.coordinates[0]!);
  // The camera may still settle; the drawn ring follows each view revision.
  await expect.poll(gap).toBeLessThan(1);
  // The wider ring is framed on the stage, not left off screen.
  const inside = async () => {
    const stage = (await page.locator('.stage').boundingBox())!;
    const drawn = (await ring.boundingBox())!;
    return (
      drawn.x >= stage.x &&
      drawn.y >= stage.y &&
      drawn.x + drawn.width <= stage.x + stage.width &&
      drawn.y + drawn.height <= stage.y + stage.height
    );
  };
  await expect.poll(inside).toBe(true);
}
async function expectNoRing(page: Page) {
  await expect(page.locator('.stage')).toHaveAttribute(
    'data-directive',
    'none',
  );
  await expect(page.locator('[data-part="context-ring"]')).toHaveCount(0);
  await expect(page.locator('[data-part="context-area"]')).toHaveCount(0);
}
const CHOSEN_EN = 'This card is for the area you chose.';
const CHOSEN_AR = 'هذه البطاقة تخص المنطقة التي اخترتها.';
function watch(page: Page, origin: string) {
  const forbidden: string[] = [];
  const chainIds = new Set<string>();
  const facts = new Set<string>();
  const routes = new Set<string>();
  page.on('request', (req) => {
    const url = new URL(req.url());
    if (url.protocol === 'http:' || url.protocol === 'https:') {
      if (url.origin !== origin || url.pathname === '/api/ask')
        forbidden.push(req.url());
      routes.add(url.pathname);
    }
  });
  page.on('response', async (response) => {
    const url = new URL(response.url());
    if (!response.ok()) return;
    if (/^\/api\/(layers|tools)\//.test(url.pathname)) {
      const body = await response.json();
      for (const fact of body.facts ?? []) {
        expect(fact.provenance).toBe('public');
        expect(fact.input_classes).toEqual(['public']);
        facts.add(fact.fact_id);
      }
    }
    if (url.pathname.startsWith('/api/facts/')) {
      const chain = await response.json();
      expect(chain.lineage.method).toBeTruthy();
      expect(chain.lineage.methodVersion).toBeTruthy();
      for (const source of chain.sources) {
        expect(source.sha256).toMatch(/^[a-f0-9]{64}$/);
        expect(source.publisher).toBeTruthy();
        expect(source.licenceOrTerms).toBeTruthy();
      }
      chainIds.add(chain.fact_id);
    }
  });
  return { forbidden, facts, chainIds, routes };
}

for (const lang of ['en', 'ar'] as const) {
  test(`Public opening to selected-area evidence and reset (${lang})`, async ({
    page,
    mounted,
  }) => {
    const seen = watch(page, mounted.origin);
    await page.goto(mounted.origin + '/?lang=' + lang);
    await expect(page.locator('[data-scene="opening"] h1')).toBeVisible();
    await expect(page.locator('[data-journey]')).toHaveCount(1);
    await expect(
      page.locator('[data-fragment="opening_electricity_unavailable"]'),
    ).toBeVisible();
    await expect(page.locator('[data-fact-chip="value"]')).toHaveCount(0);
    await page.locator('[data-action="guided-story"]').click();
    await page.locator('.stage[data-state="ready"]').waitFor();
    await chooseActivity(page, lang);
    await choosePlace(page, lang);
    await page.locator('[data-action="story-next"]').click();
    await expect(
      page.locator('[data-context-family="night_lights"]'),
    ).toBeVisible();
    await page.locator('[data-context-tab="population_age_sex"]').click();
    await expect(
      page.locator('[data-context-family="population_age_sex"]').first(),
    ).toBeVisible();
    await page.locator('[data-context-tab="night_lights"]').click();
    await expect(page.locator('[role="alert"]')).toHaveCount(0);
    const chip = page.locator(
      '[data-context-family="night_lights"] [data-fact-chip="value"]',
    );
    const id = await chip.getAttribute('data-fact-id');
    const digits = await chip.locator('.chip-num').innerText();
    const card = page.locator('[data-context-family="night_lights"]');
    await card.locator('[data-context-level="comparison"] > button').click();
    await card.locator('[data-context-level="evidence"] > button').click();
    await expect(
      card.locator('[data-context-level="comparison"] [data-fact-chip]'),
    ).toHaveCount(0);
    await expect(
      card.locator('[data-context-level="comparison"] > div'),
    ).toHaveAttribute('data-fact-id', id!);
    await chip.click();
    await expect(page.getByRole('dialog')).toHaveAttribute('data-fact-id', id!);
    await page.keyboard.press('Escape');
    await expect(chip).toBeFocused();
    await page.locator('[data-action="language"]').click();
    await expect(page.locator('html')).toHaveAttribute(
      'lang',
      lang === 'en' ? 'ar' : 'en',
    );
    await expect(chip).toHaveAttribute('data-fact-id', id!);
    await expect(chip.locator('.chip-num')).toHaveText(digits);
    await expect(page.locator('.stage')).toHaveAttribute('dir', 'ltr');
    expect(seen.chainIds.has(id!)).toBe(true);
    for (const route of [
      '/api/tools/resolve',
      '/api/tools/make_area',
      '/api/areas/shapes',
      '/api/playbooks/site_check',
      '/api/tools/night_lights',
      '/api/tools/population_age_sex',
      '/tiles/basemap.pmtiles',
    ])
      expect(seen.routes.has(route), route).toBe(true);
    expect([...seen.routes].some((route) => route.startsWith('/fonts/'))).toBe(
      true,
    );
    expect(seen.forbidden).toEqual([]);
    await page.locator('[data-action="story-reset"]').click();
    await expect(page.locator('[data-scene="opening"]')).toBeVisible();
    await expect(page.locator('[data-context-family]')).toHaveCount(0);
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.locator('[data-part="outline"]')).toHaveCount(0);
    // Caught same-origin model attempts are still recorded and rejected.
    await page.evaluate(
      "fetch('/api/ask', { method: 'POST' }).catch(() => undefined)",
    );
    expect(seen.forbidden).toHaveLength(1);
  });
}

for (const lang of ['en', 'ar'] as const) {
  test(`Public layers and venue context use mounted chains (${lang})`, async ({
    page,
    mounted,
  }) => {
    const seen = watch(page, mounted.origin);
    await page.goto(mounted.origin + '/?lang=' + lang);
    await page.locator('[data-action="guided-story"]').click();
    await page.locator('.stage[data-state="ready"]').waitFor();
    await chooseActivity(page, lang);
    await choosePlace(page, lang);
    await page.locator('.layer-chooser select').selectOption('public_places');
    await expect(
      page.locator('[data-busyness-place="INVENTED-venue-a"]'),
    ).toBeVisible();
    await page.locator('[data-busyness-place="INVENTED-venue-a"]').click();
    const busyness = page.locator('[data-context-family="venue_busyness"]');
    await expect(busyness).toBeVisible();
    await expect(
      busyness.locator('[data-caveat="relative_busyness_not_people"]'),
    ).toBeVisible();
    await expect(
      busyness.locator('[data-kind="calendar_date"]').first(),
    ).toBeVisible();
    await expect(page.locator('[data-part="estimated-people"]')).toHaveCount(0);
    await expect(page.locator('[data-part="chosen-area"]')).toHaveCount(0);
    await page.locator('.layer-inspector > summary').click();
    for (const key of [
      'night_lights',
      'land_prices',
      'parcels',
      'rail_plan',
      'health_centres',
      'zoning',
      'commercial_points',
      'address_points',
      'landmarks',
      'fdi_projects',
      'property_prices',
      'zone_electricity_growth',
    ]) {
      const response = page.waitForResponse(
        (response) => new URL(response.url()).pathname === '/api/layers/' + key,
      );
      await page.locator('.layer-chooser select').selectOption(key);
      expect((await response).ok()).toBe(true);
      await expect(page.locator('[data-part="layer-refusal"]')).toHaveCount(0);
      const source = page
        .locator(
          `[data-action="source-chain"][data-scope="layer"][data-layer="${key}"]`,
        )
        .first();
      await expect(source).toBeAttached();
      const inspector = page.locator('.layer-inspector');
      if (
        !(await inspector.evaluate((node) => (node as HTMLDetailsElement).open))
      )
        await inspector.locator(':scope > summary').click();
      await expect(source).toBeVisible();
    }
    const refused = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/api/layers/fc_firms_per_tower',
    );
    await page
      .locator('.layer-chooser select')
      .selectOption('fc_firms_per_tower');
    expect(await (await refused).json()).toEqual({
      status: 'NO_DATA',
      reason: 'missing_input',
      facts: [],
    });
    // The fixture's thin response is outside the mounted layer projection.
    // Its transport refusal uses the same unavailable alert as a refused chain.
    await expect(page.getByRole('alert')).toHaveText(
      lang === 'en'
        ? 'This map layer is unavailable.'
        : 'طبقة الخريطة هذه غير متاحة.',
    );
    await expect(
      page.getByText(
        lang === 'en' ? 'No data for this layer' : 'لا توجد بيانات لهذه الطبقة',
        { exact: true },
      ),
    ).toHaveCount(0);
    expect(seen.forbidden).toEqual([]);
  });
}

for (const lang of ['en', 'ar'] as const)
  for (const mode of ['polygon', 'distance', 'walk', 'drive'] as const) {
    test(`single-pointer ${mode} preserves its story request (${lang})`, async ({
      page,
      mounted,
    }) => {
      await selectArea(page, mounted.origin, lang, mode);
      const request = page.waitForRequest(
        (req) => new URL(req.url()).pathname === '/api/playbooks/site_check',
      );
      const started = page.waitForResponse(
        (res) => new URL(res.url()).pathname === '/api/playbooks/site_check',
      );
      const stream = page.waitForResponse((res) =>
        /^\/api\/answers\/[a-f0-9-]+\/events$/.test(
          new URL(res.url()).pathname,
        ),
      );
      const firstCard = page.waitForRequest(
        (req) => new URL(req.url()).pathname === '/api/tools/night_lights',
      );
      const cardAreas: string[] = [];
      page.on('request', (req) => {
        const path = new URL(req.url()).pathname;
        if (
          path === '/api/tools/night_lights' ||
          path === '/api/tools/population_age_sex'
        )
          cardAreas.push(req.postDataJSON().area_id);
      });
      const decodes = ['walk', 'distance'].includes(mode)
        ? page.waitForResponse(
            (res) =>
              new URL(res.url()).pathname === '/api/tools/make_area' &&
              'area_id' in (res.request().postDataJSON() ?? {}),
            { timeout: 20_000 },
          )
        : null;
      const decoded: unknown[] = [];
      page.on('request', (req) => {
        if (
          new URL(req.url()).pathname === '/api/tools/make_area' &&
          'area_id' in (req.postDataJSON() ?? {})
        )
          decoded.push(req.postDataJSON());
      });
      await page.locator('[data-action="story-next"]').click();
      const body = (await request).postDataJSON();
      expect((await started).status()).toBe(202);
      if (mode === 'polygon') {
        expect(body.shape_id).toBeTruthy();
        expect(body.pin).toBeUndefined();
      } else {
        expect(body.mode).toBe(mode);
        expect(body.cutoff).toBe(mode === 'distance' ? 500 : 15);
      }
      // S3-T26 A5: the stage directives and both card requests use the chosen area.
      const frames = readStoryFrames(await (await stream).text());
      const fly = frames.find(
        (f) => f.kind === 'stage' && f.data.directive === 'fly',
      );
      const rings = frames.find(
        (f) => f.kind === 'stage' && f.data.directive === 'rings',
      );
      const chosen = (fly?.data.target as { area_id?: unknown } | undefined)
        ?.area_id;
      expect(typeof chosen).toBe('string');
      const ringIds = rings?.data.area_ids as string[];
      expect(ringIds).toContain(chosen);
      expect((await firstCard).postDataJSON().area_id).toBe(chosen);
      await expect(
        page.locator('[data-context-family="night_lights"]'),
      ).toBeVisible();
      await expect(page.locator('[role="alert"]')).toHaveCount(0);
      for (const evidence of frames.filter(
        (f) =>
          f.kind === 'evidence' &&
          ['night_lights', 'population_age_sex'].includes(
            f.data.kind as string,
          ),
      ))
        expect(evidence.data.area_id).toBe(chosen);
      expect(cardAreas).toHaveLength(2);
      for (const area of cardAreas) expect(area).toBe(chosen);
      if (mode !== 'polygon') {
        const walk = await page.request.post(
          mounted.origin + '/api/tools/make_area',
          {
            data: {
              latitude: body.pin.lat,
              longitude: body.pin.lon,
              mode: 'walk',
              cutoff: 5,
            },
          },
        );
        const defaultWalk = (await walk.json()).payload.area_id;
        expect(typeof defaultWalk).toBe('string');
        for (const area of cardAreas) expect(area).not.toBe(defaultWalk);
      }
      // S3-T26 A5: the wider area by its documented role (document 08 section 7,
      // site_check: near, then wider). Walk and distance stories draw the wider
      // member as a dashed ring with its legend; a drive story is itself the wider
      // area and a shape has none, so neither draws or requests a wider ring.
      if (mode === 'walk' || mode === 'distance') {
        expect(ringIds).toHaveLength(2);
        expect(ringIds[0]).toBe(chosen);
        const wider = ringIds[1]!;
        const answer = (await decodes)!;
        expect(answer.request().postDataJSON()).toEqual({ area_id: wider });
        const payload = (await answer.json()).payload;
        expect(payload.area_id).toBe(wider);
        await expectRing(page, lang, payload.outline);
        expect(decoded).toEqual([{ area_id: wider }]);
      } else {
        if (mode === 'drive') expect(ringIds.at(-1)).toBe(chosen);
        await expectNoRing(page);
        expect(decoded).toEqual([]);
      }
      // The chosen-area caption sits on the area card itself (F4).
      await expect(
        page.locator(
          '[data-context-deck="night_lights"] [data-part="chosen-area"]',
        ),
      ).toHaveText(lang === 'en' ? CHOSEN_EN : CHOSEN_AR);
      // A named-place card loaded after the story carries no chosen-area caption.
      await page.locator('.layer-chooser select').selectOption('public_places');
      await page.locator('[data-busyness-place="INVENTED-venue-a"]').click();
      await page.locator('[data-context-tab="venue_busyness"]').click();
      await expect(
        page.locator('[data-context-family="venue_busyness"]'),
      ).toBeVisible();
      await expect(
        page.locator(
          '[data-context-deck="venue_busyness"] [data-part="chosen-area"]',
        ),
      ).toHaveCount(0);
      await expect(
        page.locator(
          '[data-context-deck="night_lights"] [data-part="chosen-area"]',
        ),
      ).toHaveCount(1);
    });
  }

// S3-T26 A5 (findings 2 and 3): a planted outline answer or a malformed rings
// frame leaves no ring, no legend and no bound directive.
// Test-only JSON of the real answer or frame, changed in one field.
type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
type Plant = { kind: 'answer' | 'frame'; change: (body: Json) => unknown };
const PLANTS: Record<string, Plant> = {
  'OK for another area': {
    kind: 'answer',
    change: (body) => ({
      ...body,
      payload: { ...body.payload, area_id: body.payload.area_id + '0' },
    }),
  },
  'malformed envelope': {
    kind: 'answer',
    change: () => ({ tool: 'make_area' }),
  },
  NO_DATA: {
    kind: 'answer',
    change: (b) => ({ ...b, status: 'NO_DATA', payload: null }),
  },
  OUT_OF_SCOPE: {
    kind: 'answer',
    change: (b) => ({ ...b, status: 'OUT_OF_SCOPE', payload: null }),
  },
  SUPPRESSED: {
    kind: 'answer',
    change: (b) => ({ ...b, status: 'SUPPRESSED', payload: null }),
  },
  INVALID_ARGUMENT: {
    kind: 'answer',
    change: () => ({
      error: {
        code: 'INVALID_ARGUMENT',
        message_key: 'errors.invalid_argument',
        error_id: 'INVENTED-error',
      },
    }),
  },
  'three ring ids': {
    kind: 'frame',
    change: (d) => ({ ...d, area_ids: [...d.area_ids, d.area_ids[0] + '0'] }),
  },
  'extra rings field': {
    kind: 'frame',
    change: (d) => ({ ...d, extra: 'INVENTED' }),
  },
};
for (const lang of ['en', 'ar'] as const)
  for (const [name, plant] of Object.entries(PLANTS))
    test(`a planted ${name} draws no wider ring (${lang})`, async ({
      page,
      mounted,
    }) => {
      await selectArea(page, mounted.origin, lang, 'walk');
      const decoded: unknown[] = [];
      await page.route('**/api/tools/make_area', async (route) => {
        const body = route.request().postDataJSON() ?? {};
        if (!('area_id' in body)) return route.continue();
        decoded.push(body);
        const response = await route.fetch();
        if (plant.kind !== 'answer') return route.fulfill({ response });
        const changed = plant.change(await response.json());
        const refused = 'error' in (changed as object);
        await route.fulfill({
          status: refused ? 422 : 200,
          contentType: 'application/json',
          body: JSON.stringify(changed),
        });
      });
      await page.route('**/api/answers/*/events', async (route) => {
        const response = await route.fetch();
        const text = await response.text();
        if (plant.kind !== 'frame')
          return route.fulfill({ response, body: text });
        const blocks = text.replace(/\r\n/g, '\n').split('\n\n');
        const changed = blocks.map((block) => {
          const data = block.split('\n').find((l) => l.startsWith('data: '));
          if (!block.includes('event: stage') || !data) return block;
          const frame = JSON.parse(data.slice(6));
          if (frame.directive !== 'rings') return block;
          return 'event: stage\ndata: ' + JSON.stringify(plant.change(frame));
        });
        await route.fulfill({ response, body: changed.join('\n\n') });
      });
      await page.locator('[data-action="story-next"]').click();
      if (plant.kind === 'frame') {
        await expect(page.locator('[role="alert"]')).toBeVisible();
        expect(decoded).toEqual([]);
      } else {
        await expect(
          page.locator('[data-context-family="night_lights"]'),
        ).toBeVisible();
        await expect.poll(() => decoded.length).toBe(1);
      }
      await expectNoRing(page);
    });

// S3-T26 A5 design audit: the legend is readable and unobscured, and the dashed
// ring is distinct from the map, on phone and desktop, EN/AR, dark/light.
for (const [width, height] of [
  [390, 844],
  [1366, 768],
] as const)
  for (const lang of ['en', 'ar'] as const)
    for (const theme of ['dark', 'light'] as const)
      test(`wider ring audit ${width}x${height} ${lang} ${theme}`, async ({
        page,
        mounted,
      }) => {
        await page.setViewportSize({ width, height });
        await selectArea(page, mounted.origin, lang, 'walk', theme);
        await page.locator('[data-action="story-next"]').click();
        const legend = page.locator('[data-part="context-area"]');
        await expect(legend).toBeVisible();
        expect(await openingProblems(page)).toEqual([]);
        const seen = await legend.evaluate((node) => {
          const box = node.getBoundingClientRect();
          const top = document.elementFromPoint(
            box.left + box.width / 2,
            box.top + box.height / 2,
          );
          const line = document.querySelector(
            '[data-part="context-ring"] .context-ring-line',
          )!;
          const land = getComputedStyle(document.documentElement)
            .getPropertyValue('--eii-map-land')
            .trim();
          // DES-15 against the chosen outline (fix round 2, F4).
          const casing = document.querySelector(
            '[data-part="context-ring"] .context-ring-casing',
          )!;
          const chosen = document.querySelector(
            '[data-part="outline"] .area-line-accent',
          )!;
          // Each line's stacking layer is its nearest overlay container.
          const ringSvg = line.closest('.area-overlay')!;
          const chosenSvg = chosen.closest('.area-overlay')!;
          const width = (item: Element) =>
            parseFloat(getComputedStyle(item).strokeWidth);
          return {
            unobscured: Boolean(top && node.contains(top)),
            inside: box.top >= 0 && box.bottom <= innerHeight,
            stroke: getComputedStyle(line).stroke,
            land,
            casing: getComputedStyle(casing).stroke,
            chosen: getComputedStyle(chosen).stroke,
            halo: (width(casing) - width(line)) / 2,
            ringDash: getComputedStyle(line).strokeDasharray,
            chosenDash: getComputedStyle(chosen).strokeDasharray,
            sameLayer:
              ringSvg.parentElement === chosenSvg.parentElement &&
              getComputedStyle(ringSvg).zIndex ===
                getComputedStyle(chosenSvg).zIndex,
            ringAbove: Boolean(
              chosenSvg.compareDocumentPosition(ringSvg) &
              Node.DOCUMENT_POSITION_FOLLOWING,
            ),
          };
        });
        expect(seen.unobscured).toBe(true);
        expect(seen.inside).toBe(true);
        expect(contrast(seen.stroke, seen.land)).toBeGreaterThanOrEqual(3);
        // Wherever the ring meets the chosen outline it is painted above it on
        // a casing at least one pixel wider on each side: ring against casing
        // and casing against the chosen accent each keep 3:1, with a distinct
        // dash on the ring and none on the chosen outline.
        expect([seen.sameLayer, seen.ringAbove]).toEqual([true, true]);
        expect(seen.halo).toBeGreaterThanOrEqual(1);
        expect(contrast(seen.stroke, seen.casing)).toBeGreaterThanOrEqual(3);
        expect(contrast(seen.casing, seen.chosen)).toBeGreaterThanOrEqual(3);
        expect(seen.ringDash).not.toBe('none');
        expect(seen.chosenDash).toBe('none');
      });

function contrast(a: string, b: string): number {
  const lum = (value: string) => {
    const hex = value.startsWith('#')
      ? [1, 3, 5].map((i) => parseInt(value.slice(i, i + 2), 16))
      : (value.match(/[0-9.]+/g) ?? []).slice(0, 3).map(Number);
    const [r, g, b2] = hex.map((c) => {
      const s = c / 255;
      return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r! + 0.7152 * g! + 0.0722 * b2!;
  };
  const [x, y] = [lum(a), lum(b)];
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

test('the first opening frame waits for the bundled bilingual interface fonts', async ({
  page,
  mounted,
}) => {
  await page.addInitScript(() => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    Object.defineProperty(globalThis, 'releaseOpeningFonts', {
      value: () => release(),
    });
    const load = document.fonts.load.bind(document.fonts);
    document.fonts.load = (...args) => gate.then(() => load(...args));
  });
  await page.goto(mounted.origin + '/?lang=ar');
  await expect(page.locator('#root')).toBeEmpty();
  await page.evaluate(() => Reflect.get(globalThis, 'releaseOpeningFonts')());
  await expect(page.locator('[data-scene="opening"] h1')).toBeVisible();
  expect(
    await page.evaluate(() =>
      document.fonts.check('500 16px "IBM Plex Sans Arabic"', 'المنطقة'),
    ),
  ).toBe(true);
});

test('missing interface faces refuse font readiness and never show a story', async ({
  page,
  mounted,
}) => {
  await page.addInitScript(() => {
    document.fonts.load = async () => [];
  });
  await page.goto(mounted.origin + '/?lang=ar');
  await expect(page.locator('[data-scene="opening"]')).toHaveCount(0);
  await expect(page.getByRole('alert')).toContainText('خطوط الواجهة غير متاحة');
});

for (const lang of ['en', 'ar'] as const) {
  test(`camera buttons pan, zoom, recentre and retain the view on language change (${lang})`, async ({
    page,
    mounted,
  }) => {
    await page.goto(mounted.origin + '/?lang=' + lang);
    await page.locator('.stage[data-state="ready"]').waitFor();
    await page.locator('.map-control-panel > summary').click();
    async function view() {
      return page.evaluate(() => {
        const map = (
          globalThis as unknown as {
            eiiMap: {
              getCenter: () => { lng: number; lat: number };
              getZoom: () => number;
            };
          }
        ).eiiMap;
        const center = map.getCenter();
        return { lon: center.lng, lat: center.lat, zoom: map.getZoom() };
      });
    }
    const home = await view();
    await page.locator('[data-camera="east"]').click();
    expect((await view()).lon).toBeGreaterThan(home.lon);
    await page.locator('[data-camera="north"]').click();
    expect((await view()).lat).toBeGreaterThan(home.lat);
    await page.locator('[data-camera="zoomIn"]').click();
    expect((await view()).zoom).toBeGreaterThan(home.zoom);
    const beforeFlip = await view();
    await page.locator('[data-action="language"]').click();
    await page.locator('.stage[data-state="ready"]').waitFor();
    expect(await view()).toEqual(beforeFlip);
    await page.locator('[data-camera="recentre"]').click();
    expect(await view()).toEqual(home);
  });
}
