import fs from 'node:fs';
import { createHash } from 'node:crypto';
import { assemble } from '../release-build.mjs';
import type { SourceInput } from '../release-shape.mjs';
import { expect, test, type Browser, type Page } from '@playwright/test';
import catalogue from '../catalogue.json' with { type: 'json' };
import { formatDate } from '../facts.mjs';
import {
  FOLD_ZOOM,
  STREET_CAMERAS,
  UNFOLD_ZOOM,
  VARIANTS,
  judgeAttribution,
  judgeBuildingLayers,
  judgeCard,
  edgeStrips,
  judgeCityFrame,
  judgeDistrictPlate,
  judgeFold,
  judgeFoldedLegend,
  judgeSwatches,
  judgeCardChips,
  judgePointColours,
  judgePointKey,
  judgeTypeControl,
  judgeLegendPeriod,
  judgeAttributionRuns,
  judgeLabelsInside,
  judgeRoadLabels,
  judgeScreen,
  judgeChipChains,
  judgeClassWords,
  judgeCoreClear,
  judgeCsp,
  judgeDensity,
  judgeDigitWidths,
  judgeDigits,
  judgeDocument,
  judgeInside,
  judgeLabelLanguage,
  judgeLabelsClear,
  judgeLitLayers,
  judgeMarks,
  judgeMotion,
  judgeNoOverlap,
  judgeNumerals,
  judgeBracketLabel,
  judgePointsUnderLabels,
  judgeStreetCover,
  judgeUniqueNames,
  judgeRequests,
  judgeTextFloor,
  type ChipFound,
  type FactFound,
  type MapLayer,
  type MarkItem,
  type NumeralItem,
  type Rect,
  type ScreenState,
} from '../guards.mjs';

type Lang = 'en' | 'ar';
type Look = NonNullable<Window['__look']>;
type Opened = { look: Look; consoleErrors: string[]; seen: string[] };

const SAFE = { x: 96, y: 54, width: 1728, height: 972 };
const ORIGIN = new URL(process.env.LOOK_BASE_URL ?? 'http://127.0.0.1').origin;
const BASEMAP = '/basemap/qatar.pmtiles';
const EXPECTED_FACTS = [
  'densest-unit',
  'areas-with-firms',
  'top-classes',
  'break-1',
  'break-2',
  'break-3',
  'break-4',
];

// Empty coverage has no summary to open. Its scale chips still exercise
// every drawer check, rather than skipping that check or inventing a fact.
function evidenceChip(page: Page, opened: Opened, id = 'densest-unit') {
  return page
    .locator(
      `button[data-chip][data-fact="${opened.look.units === 0 ? 'break-1' : id}"]`,
    )
    .filter({ visible: true })
    .first();
}

// Most tests read the page's end state, so the default context asks for
// reduced motion; the tests of the opening make their own context.
test.use({ reducedMotion: 'reduce' });

function word(key: string, lang: Lang): string {
  const entry = (
    catalogue.strings as Record<string, { en: string; ar: string }>
  )[key];
  if (entry === undefined) throw new Error(`missing catalogue key ${key}`);
  return entry[lang];
}

// P2 of round 5: the page opens on the home. A test of the answer screen asks
// for it with ?answer=operate, unless it opens the home ('home' waits until
// the home has settled) or its path names a screen already.
// 'settled' waits, as the captures do, until the answer's opening has ended.
type Until = 'lit' | 'ready' | 'home' | 'settled';

function screenPath(path: string, until: Until): string {
  if (until === 'home') return path;
  const url = new URL(path, ORIGIN);
  if (!url.searchParams.has('answer'))
    url.searchParams.set('answer', 'operate');
  return `${url.pathname}${url.search}`;
}

async function open(
  page: Page,
  path: string,
  until: Until = 'lit',
): Promise<Opened> {
  const seen: string[] = [];
  const consoleErrors: string[] = [];
  page.on('request', (request) => {
    seen.push(request.url());
  });
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => {
    consoleErrors.push(error.message);
  });
  await page.route('**/*', (route) => {
    const verdict = judgeRequests([route.request().url()], ORIGIN);
    if (!verdict.ok) return route.abort();
    return route.continue();
  });
  await page.goto(screenPath(path, until));
  await page.waitForFunction(
    (state) =>
      (state === 'lit'
        ? window.__look?.lit === true
        : state === 'home' || state === 'settled'
          ? window.__look?.settled === true
          : window.__look?.ready === true) ||
      (window.__look?.failure ?? '') !== '',
    until,
    { timeout: 90_000 },
  );
  const look = await page.evaluate(() => window.__look);
  if (look === undefined) throw new Error('look diagnostics are absent');
  if (look.failure !== '') throw new Error(`page failed: ${look.failure}`);
  const verdict = judgeRequests(seen, ORIGIN);
  if (!verdict.ok) throw new Error(verdict.detail);
  return { look, consoleErrors, seen };
}

async function fullMotion(browser: Browser): Promise<Page> {
  const context = await browser.newContext({
    reducedMotion: 'no-preference',
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
  });
  return context.newPage();
}

function numeralItems(page: Page): Promise<NumeralItem[]> {
  return page.evaluate(() => {
    const items: { text: string; inChip: boolean; where: string }[] = [];
    const describe = (element: Element | null): string => {
      if (element === null) return 'document';
      const tag = element.tagName.toLowerCase();
      const name =
        element.getAttribute('data-part') ??
        element.getAttribute('class') ??
        '';
      return name === '' ? tag : `${tag}.${name}`;
    };
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
    );
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const text = node.textContent ?? '';
      if (text.trim() === '') continue;
      const parent = node.parentElement;
      items.push({
        text,
        inChip: parent?.closest('[data-chip]') !== null,
        where: describe(parent),
      });
    }
    const attributes = [
      'aria-label',
      'aria-description',
      'aria-valuetext',
      'title',
      'alt',
      'placeholder',
      'label',
    ];
    for (const element of document.querySelectorAll('*')) {
      for (const attribute of attributes) {
        const value = element.getAttribute(attribute);
        if (value === null || value === '') continue;
        items.push({
          text: value,
          inChip: element.closest('[data-chip]') !== null,
          where: `${describe(element)}[${attribute}]`,
        });
      }
      for (const pseudo of ['::before', '::after']) {
        const content = getComputedStyle(element, pseudo).content;
        if (content === 'none' || content === 'normal' || content === '')
          continue;
        items.push({
          text: content,
          inChip: element.closest('[data-chip]') !== null,
          where: `${describe(element)}${pseudo}`,
        });
      }
    }
    items.push({ text: document.title, inChip: false, where: 'title' });
    return items;
  });
}

// What a viewer can read: the visible text of the page and its title.
function screenText(page: Page): Promise<string> {
  return page.evaluate(() => {
    const attributes = [...document.querySelectorAll('*')]
      .filter((node) => node.getClientRects().length > 0)
      .flatMap((node) =>
        [
          'aria-label',
          'aria-description',
          'aria-valuetext',
          'title',
          'alt',
          'placeholder',
          'label',
        ].map((key) => node.getAttribute(key) ?? ''),
      );
    return [document.body.innerText, document.title, ...attributes].join('\n');
  });
}

function markItems(page: Page): Promise<MarkItem[]> {
  return page.evaluate(() =>
    [...document.querySelectorAll('body *')]
      .filter((element) => element.getClientRects().length > 0)
      .flatMap((element) =>
        ['', '::before', '::after'].map((pseudo) => {
          const style = getComputedStyle(element, pseudo || null);
          return {
            where: `${element.tagName.toLowerCase()}.${element.getAttribute('class') ?? ''}${pseudo}`,
            textDecoration: style.textDecorationLine,
            borderStyle: style.borderStyle,
            backgroundImage: style.backgroundImage,
          };
        }),
      ),
  );
}

function chipsFound(page: Page): Promise<ChipFound[]> {
  return page.evaluate(() =>
    [...document.querySelectorAll('[data-chip]')]
      .filter((element) => element.getClientRects().length > 0)
      .map((element) => ({
        variant: element.getAttribute('data-chip') ?? '',
        ids: (element.getAttribute('data-facts') ?? '')
          .split(' ')
          .filter((id) => id !== ''),
      })),
  );
}

function releasedFacts(page: Page): Promise<FactFound[]> {
  return page.evaluate(() => {
    const text = document.getElementById('eii-release')?.textContent ?? '{}';
    const release = JSON.parse(text) as { facts?: FactFound[] };
    return release.facts ?? [];
  });
}

function plates(page: Page): Promise<Rect[]> {
  return page.evaluate(() =>
    [...document.querySelectorAll('[data-plate]')]
      .filter((element) => element.getClientRects().length > 0)
      .filter((element) => getComputedStyle(element).visibility !== 'hidden')
      .map((element) => {
        const box = element.getBoundingClientRect();
        return {
          name: element.getAttribute('data-plate') ?? '',
          x: box.x,
          y: box.y,
          width: box.width,
          height: box.height,
        };
      }),
  );
}

for (const variant of VARIANTS) {
  test(`${variant.lang}-${variant.theme} loads with no console error and no request to another origin`, async ({
    page,
  }) => {
    const opened = await open(
      page,
      `/${variant.lang}/_look?theme=${variant.theme}`,
    );
    expect(opened.look.ready).toBe(true);
    expect(opened.look.lang).toBe(variant.lang);
    expect(opened.look.theme).toBe(variant.theme);
    expect(opened.consoleErrors).toEqual([]);
    const tiles = opened.seen.filter((url) => url.includes(BASEMAP));
    if (opened.look.basemap) {
      expect(tiles.length).toBeGreaterThan(0);
      expect(opened.look.units).toBeGreaterThan(0);
    } else {
      expect(tiles).toEqual([]);
      expect(opened.look.units).toBe(0);
    }
    expect(judgeRequests(opened.seen, ORIGIN).ok).toBe(true);
    expect(
      await page.evaluate(() => document.documentElement.dataset.theme),
    ).toBe(variant.theme);
  });
}

test('a remote asset attempt is refused', async ({ page }) => {
  await expect(open(page, '/en/_look?plant=remote-asset')).rejects.toThrow(
    /assets\.invalid/,
  );
});

test('the Arabic route is right to left and the map is not mirrored', async ({
  page,
}) => {
  const arabic = await open(page, '/ar/_look');
  const root = await page.evaluate(() => ({
    lang: document.documentElement.lang,
    dir: document.documentElement.dir,
  }));
  const verdict = judgeDocument(root, 'ar');
  expect(verdict.ok, verdict.detail).toBe(true);
  const spacing = await page.evaluate(() =>
    [...document.querySelectorAll(':lang(ar)')].map(
      (element) => getComputedStyle(element).letterSpacing,
    ),
  );
  for (const value of spacing) expect(['normal', '0px']).toContain(value);
  const canvasTransform = await page.evaluate(
    () =>
      getComputedStyle(document.querySelector('canvas') as Element).transform,
  );
  expect(canvasTransform).toBe('none');
  const brief = await page.locator('[data-plate="brief"]').boundingBox();
  expect(brief?.x ?? 2000).toBeLessThan(960);
  const digits = judgeDigits(await page.locator('body').innerText());
  expect(digits.ok, digits.detail).toBe(true);
  const englishPage = await page.context().newPage();
  const english = await open(englishPage, '/en/_look');
  expect(arabic.look.bearing).toBe(english.look.bearing);
  expect(arabic.look.pitch).toBe(english.look.pitch);
  expect(english.look.bearing).toBe(-15);
  expect(english.look.pitch).toBe(45);
  const englishBrief = await englishPage
    .locator('[data-plate="brief"]')
    .boundingBox();
  expect(englishBrief?.x ?? 0).toBeGreaterThan(960);
});

test('no numeral is rendered outside the Fact chip elements', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    await open(page, `/${lang}/_look`);
    const verdict = judgeNumerals(await numeralItems(page));
    expect(verdict.ok, verdict.detail).toBe(true);
    await page.locator('[data-control="table"]').click();
    const table = judgeNumerals(await numeralItems(page));
    expect(table.ok, table.detail).toBe(true);
  }
});

test('a planted numeral outside a chip is caught', async ({ page }) => {
  await open(page, '/en/_look?plant=stray-numeral');
  const verdict = judgeNumerals(await numeralItems(page));
  expect(verdict.ok).toBe(false);
  expect(verdict.detail).toContain('numeral outside a Fact chip');
});

test('no class word is on screen in either language', async ({ page }) => {
  for (const lang of ['en', 'ar'] as const) {
    for (const theme of ['dark', 'light'] as const) {
      const opened = await open(page, `/${lang}/_look?theme=${theme}`);
      await evidenceChip(page, opened).click();
      const verdict = judgeClassWords(await screenText(page));
      expect(verdict.ok, verdict.detail).toBe(true);
      await page.locator('.drawer [data-control="back"]').click();
    }
    await page.locator('[data-control="table"]').click();
    const table = judgeClassWords(await screenText(page));
    expect(table.ok, table.detail).toBe(true);
  }
});

test('a planted class word is caught in both languages', async ({ page }) => {
  for (const lang of ['en', 'ar'] as const) {
    await open(page, `/${lang}/_look?plant=class-word`);
    expect(judgeClassWords(await screenText(page)).ok).toBe(false);
  }
});

test('no element and no map layer carries a class mark', async ({ page }) => {
  for (const lang of ['en', 'ar'] as const) {
    await open(page, `/${lang}/_look`);
    const verdict = judgeMarks(await markItems(page));
    expect(verdict.ok, verdict.detail).toBe(true);
    const layers = judgeLitLayers(
      await page.evaluate(() => window.__look?.litLayers() ?? []),
    );
    expect(layers.ok, layers.detail).toBe(true);
  }
});

test('a planted class underline is caught', async ({ page }) => {
  await open(page, '/en/_look?plant=class-mark');
  const verdict = judgeMarks(await markItems(page));
  expect(verdict.ok).toBe(false);
  expect(verdict.detail).toContain('underline');
});

test('every chip resolves to a fact, a class and a source chain that the drawer opens', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    const opened = await open(page, `/${lang}/_look`);
    const facts = await releasedFacts(page);
    const chips = await chipsFound(page);
    const expected =
      opened.look.units === 0 ? EXPECTED_FACTS.slice(3) : EXPECTED_FACTS;
    const verdict = judgeChipChains(chips, facts, expected);
    expect(verdict.ok, verdict.detail).toBe(true);
    const byId = new Map(facts.map((fact) => [fact.id, fact]));
    const ids = await page.evaluate(() =>
      [...document.querySelectorAll('button[data-chip]')]
        .filter((element) => element.getClientRects().length > 0)
        .map((element) => element.getAttribute('data-fact') ?? ''),
    );
    expect(ids).toHaveLength(expected.length);
    expect(new Set(ids)).toEqual(new Set(expected));
    for (const id of ids) {
      await page
        .locator(`button[data-chip][data-fact="${id}"]`)
        .filter({ visible: true })
        .click();
      const drawer = page.locator('.drawer');
      await expect(drawer).toBeVisible();
      await expect(drawer).toHaveAttribute('data-drawer-fact', id);
      await expect(drawer.locator('h2')).toHaveText(word('drawer.title', lang));
      const fact = byId.get(id);
      expect(fact).toBeDefined();
      expect(judgeClassWords(await screenText(page)).ok).toBe(true);
      await expect(drawer).toContainText(
        word(fact?.chain?.generator.name ?? '', lang),
      );
      await expect(drawer).toContainText(fact?.chain?.generator.version ?? '');
      await expect(drawer).toContainText(fact?.chain?.method_version ?? '');
      await expect(drawer).toContainText(word(fact?.chain?.method ?? '', lang));
      await expect(drawer).toContainText(id);
      await drawer.locator('[data-control="back"]').click();
      await expect(drawer).toHaveCount(0);
    }
    if (opened.look.units === 0) {
      await expect(page.locator('[data-control="more"]')).toHaveCount(0);
    } else {
      await page.locator('[data-control="more"]').click();
      await expect(page.locator('.drawer')).toHaveAttribute(
        'data-drawer-fact',
        'densest-unit',
      );
    }
  }
});

test('a planted fact without its chain is caught', async ({ page }) => {
  await open(page, '/en/_look?plant=chainless-fact');
  const verdict = judgeChipChains(
    await chipsFound(page),
    await releasedFacts(page),
    EXPECTED_FACTS,
  );
  expect(verdict.ok).toBe(false);
});

// Ruling L-119 item 5: the basemap shows major places only (localities the
// basemap itself draws from zoom 9 or lower), and no label sits under or
// touches a plate, in the opening of every variant and in the buildings view.
function labelHits(page: Page): Promise<{ label: string; plate: string }[]> {
  return page.evaluate(() => {
    const rects = [...document.querySelectorAll('[data-plate]')]
      .filter((element) => element.getClientRects().length > 0)
      .filter((element) => getComputedStyle(element).visibility !== 'hidden')
      .map((element) => {
        const box = element.getBoundingClientRect();
        return {
          name: element.getAttribute('data-plate') ?? '',
          x: box.x,
          y: box.y,
          width: box.width,
          height: box.height,
        };
      });
    return window.__look?.labelsUnder(rects) ?? [];
  });
}

for (const variant of VARIANTS) {
  test(`${variant.lang}-${variant.theme} shows major places only, none under or touching a plate`, async ({
    page,
  }) => {
    const opened = await open(
      page,
      `/${variant.lang}/_look?theme=${variant.theme}`,
    );
    await page.evaluate(() => window.__look?.rendered());
    const shown = await page.evaluate(() => window.__look?.labels() ?? []);
    if (opened.look.basemap) {
      expect(shown.length).toBeGreaterThan(0);
      for (const label of shown) {
        expect(label.kind, label.name).toBe('locality');
        expect(label.minZoom, label.name).toBeLessThanOrEqual(9);
      }
    } else {
      expect(shown).toEqual([]);
    }
    const verdict = judgeLabelsClear(await labelHits(page));
    expect(verdict.ok, verdict.detail).toBe(true);
  });
}

test('the buildings view keeps every label clear of the plates', async ({
  page,
}) => {
  await open(page, '/en/_look');
  await page.evaluate(() => window.__look?.showBuildings());
  await page.evaluate(() => window.__look?.rendered());
  const verdict = judgeLabelsClear(await labelHits(page));
  expect(verdict.ok, verdict.detail).toBe(true);
});

test('a planted label under a plate is caught', async ({ page }) => {
  const opened = await open(page, '/en/_look?plant=label-under-plate');
  await page.waitForFunction(() => window.__look?.planted === true);
  await page.evaluate(() => window.__look?.rendered());
  const verdict = judgeLabelsClear(await labelHits(page));
  if (opened.look.basemap) {
    expect(verdict.ok).toBe(false);
    expect(verdict.detail).toContain('touches the topbar-start plate');
  } else {
    expect(verdict.ok).toBe(true);
  }
});

// Round 5e, E2: every major place label stands wholly inside the screen, with
// a margin of EDGE_MARGIN px, or is not drawn: at the City view as the
// captures open it, after Reset from a moved camera, and at the answer
// reached from the home through the question and the place.
async function edgeVerdict(page: Page) {
  await page.evaluate(() => window.__look?.rendered());
  const size = page.viewportSize() ?? { width: 1920, height: 1080 };
  const strips = edgeStrips(size.width, size.height);
  const hits = await page.evaluate(
    (rects) => window.__look?.labelsUnder(rects) ?? [],
    strips,
  );
  return judgeLabelsInside(hits);
}

for (const lang of ['en', 'ar'] as const) {
  test(`${lang}: every major place name stands wholly inside the screen at the City view and at the answer`, async ({
    page,
  }) => {
    await open(page, `/${lang}/_look`);
    const city = await edgeVerdict(page);
    expect(city.ok, `City view: ${city.detail}`).toBe(true);
    await page.evaluate(() =>
      window.__look?.camera({
        center: [51.45, 25.3],
        zoom: 11,
        pitch: 0,
        bearing: 0,
      }),
    );
    await page.locator('[data-control="reset"]').click();
    await page.waitForFunction(() => window.__look?.moving === false);
    const reset = await edgeVerdict(page);
    expect(reset.ok, `after Reset: ${reset.detail}`).toBe(true);
    await open(page, `/${lang}/_look`, 'home');
    await choosePlace(page);
    const answered = await edgeVerdict(page);
    expect(answered.ok, `answer: ${answered.detail}`).toBe(true);
  });
}

test('a planted pan that pushes a major place name half off the screen is caught', async ({
  page,
}) => {
  const opened = await open(page, '/en/_look?plant=label-off-edge');
  await page.waitForFunction(() => window.__look?.planted === true);
  const verdict = await edgeVerdict(page);
  if (opened.look.basemap) {
    expect(verdict.ok).toBe(false);
    expect(verdict.detail).toContain('is cut by the left edge of the screen');
  } else {
    expect(verdict.ok, verdict.detail).toBe(true);
  }
});

// Ruling L-119 item 1: the legend covers no cell of the two highest classes
// in either language.
async function coreVerdict(page: Page) {
  const points = await page.evaluate(
    () => window.__look?.brightCorners() ?? [],
  );
  const legend = (await plates(page)).filter(
    (plate) => plate.name === 'legend',
  );
  expect(legend.length).toBe(1);
  return { points, verdict: judgeCoreClear(points, legend) };
}

test('the legend covers no bright cell in either language', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    const opened = await open(page, `/${lang}/_look`);
    await page.evaluate(() => window.__look?.rendered());
    const { points, verdict } = await coreVerdict(page);
    if (opened.look.basemap) expect(points.length).toBeGreaterThan(0);
    else expect(points).toEqual([]);
    expect(verdict.ok, `${lang}: ${verdict.detail}`).toBe(true);
  }
});

test('a planted legend over the bright core is caught', async ({ page }) => {
  const opened = await open(page, '/ar/_look?plant=legend-over-core');
  await page.waitForFunction(() => window.__look?.planted === true);
  const { verdict } = await coreVerdict(page);
  expect(verdict.ok).toBe(!opened.look.basemap);
});

test('the map attribution is visible in both languages', async ({ page }) => {
  for (const lang of ['en', 'ar'] as const) {
    await open(page, `/${lang}/_look`);
    const found = await page.evaluate(() => {
      const element = document.querySelector('[data-part="attribution"]');
      if (!(element instanceof HTMLElement))
        return { text: '', visible: false };
      const box = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return {
        text: element.innerText,
        visible:
          box.width > 0 &&
          box.height > 0 &&
          style.visibility !== 'hidden' &&
          box.x >= 0 &&
          box.bottom <= window.innerHeight,
      };
    });
    const verdict = judgeAttribution(found);
    expect(verdict.ok, verdict.detail).toBe(true);
  }
});

// Round 5g, finding 9: the credits are one Latin run, the note on building
// heights a run in the page's language at its caption size.
function attributionRuns(page: Page) {
  return page.evaluate(() => {
    const plate = document.querySelector('[data-plate="attribution"]');
    const note = plate?.querySelector<HTMLElement>('[data-word]') ?? null;
    const credits =
      plate?.querySelector<HTMLElement>('.attribution-credits') ?? null;
    const style = credits === null ? null : getComputedStyle(credits);
    return {
      note:
        note === null
          ? null
          : {
              lang: note.lang,
              size: Number.parseFloat(getComputedStyle(note).fontSize),
            },
      creditLines:
        credits === null || style === null
          ? 0
          : Math.round(
              credits.getBoundingClientRect().height /
                Number.parseFloat(style.lineHeight),
            ),
      creditText: credits?.textContent ?? '',
    };
  });
}

test('the attribution credits stay one line and the note takes the page language', async ({
  page,
}) => {
  for (const [lang, size] of [
    ['en', 28],
    ['ar', 31],
  ] as const) {
    await open(page, `/${lang}/_look`);
    const verdict = judgeAttributionRuns(
      await attributionRuns(page),
      lang,
      size,
    );
    expect(verdict.ok, verdict.detail).toBe(true);
  }
});

test('a planted attribution set as one English string is caught', async ({
  page,
}) => {
  await open(page, '/ar/_look?plant=attribution-one-string');
  const verdict = judgeAttributionRuns(await attributionRuns(page), 'ar', 31);
  expect(verdict.ok).toBe(false);
});

test('a planted missing attribution is caught', async ({ page }) => {
  await open(page, '/en/_look?plant=no-attribution');
  const found = await page.evaluate(() => {
    const element = document.querySelector('[data-part="attribution"]');
    const box = element?.getBoundingClientRect();
    return {
      text: element instanceof HTMLElement ? element.innerText : '',
      visible: (box?.width ?? 0) > 0,
    };
  });
  expect(judgeAttribution(found).ok).toBe(false);
});

test('reduced motion from the system shows the end state at once', async ({
  page,
}) => {
  const opened = await open(page, '/en/_look');
  const verdict = judgeMotion({
    reduced: true,
    litMode: opened.look.litMode,
  });
  expect(verdict.ok, verdict.detail).toBe(true);
  expect(await page.evaluate(() => window.__look?.litLevels())).toEqual([
    1, 1, 1, 1, 1,
  ]);
  await evidenceChip(page, opened).click();
  const duration = await page.evaluate(
    () =>
      getComputedStyle(document.querySelector('.drawer') as Element)
        .animationDuration,
  );
  expect(duration).toBe('0.15s');
});

test('a planted page that ignores reduced motion is caught', async ({
  page,
}) => {
  const opened = await open(page, '/en/_look?plant=ignore-reduced-motion');
  const verdict = judgeMotion({ reduced: true, litMode: opened.look.litMode });
  expect(verdict.ok).toBe(false);
});

test('the opening is staged, and Pause motion stops every movement', async ({
  browser,
}) => {
  const page = await fullMotion(browser);
  try {
    const opened = await open(page, '/en/_look', 'ready');
    expect(opened.look.litMode).toBe('staged');
    const control = page.locator('[data-control="motion"]');
    await expect(control).toHaveText(word('motion.pause', 'en'));
    await control.click();
    await expect(control).toHaveText(word('motion.resume', 'en'));
    const after = await page.evaluate(() => ({
      reduced: window.__look?.reduced ?? false,
      moving: window.__look?.moving ?? true,
      lit: window.__look?.lit ?? false,
      levels: window.__look?.litLevels() ?? [],
      brief: getComputedStyle(
        document.querySelector('[data-plate="brief"]') as Element,
      ).opacity,
      running: document
        .getAnimations()
        .filter((animation) => animation.playState === 'running').length,
    }));
    expect(after.reduced).toBe(true);
    expect(after.moving).toBe(false);
    expect(after.lit).toBe(true);
    expect(after.levels).toEqual([1, 1, 1, 1, 1]);
    expect(after.brief).toBe('1');
    expect(after.running).toBe(0);
  } finally {
    await page.context().close();
  }
});

test('Reset during the opening settles every layer and shows the Brief', async ({
  browser,
}) => {
  const page = await fullMotion(browser);
  try {
    await open(page, '/en/_look', 'ready');
    await page.locator('[data-control="reset"]').click();
    await page.waitForFunction(() => window.__look?.lit === true);
    const state = await page.evaluate(() => ({
      levels: window.__look?.litLevels() ?? [],
      brief: getComputedStyle(
        document.querySelector('[data-plate="brief"]') as Element,
      ).opacity,
    }));
    expect(state.levels).toEqual([1, 1, 1, 1, 1]);
    expect(state.brief).toBe('1');
  } finally {
    await page.context().close();
  }
});

test('Reset closes the source chain and the table view and returns to the City framing', async ({
  page,
}) => {
  const opened = await open(page, '/en/_look');
  await page.locator('[data-control="table"]').click();
  await evidenceChip(page, opened).click();
  await expect(page.locator('.drawer')).toBeVisible();
  await page.locator('[data-control="reset"]').click();
  await expect(page.locator('.drawer')).toHaveCount(0);
  await expect(page.locator('.legend-table')).toBeHidden();
  await expect(page.locator('.legend-scale')).toBeVisible();
  const camera = await page.evaluate(() => ({
    bearing: window.__look?.bearing,
    pitch: window.__look?.pitch,
    zoom: window.__look?.zoom,
  }));
  expect(camera).toEqual({
    bearing: opened.look.bearing,
    pitch: opened.look.pitch,
    zoom: opened.look.zoom,
  });
});

test('the theme follows the query and the control without a reload', async ({
  page,
}) => {
  await open(page, '/en/_look?theme=light');
  const light = await page.evaluate(
    () => getComputedStyle(document.body).backgroundColor,
  );
  expect(light).toBe('rgb(216, 213, 206)');
  await page.evaluate(() => {
    (window as unknown as { __marker: number }).__marker = 1;
  });
  await page.locator('[data-control="theme-dark"]').click();
  await page.waitForFunction(
    () => window.__look?.theme === 'dark' && window.__look.mapTheme === 'dark',
  );
  expect(new URL(page.url()).searchParams.get('theme')).toBe('dark');
  expect(
    await page.evaluate(
      () => (window as unknown as { __marker?: number }).__marker,
    ),
  ).toBe(1);
});

test('the language control flips words, keeps numerals and does not move the map', async ({
  page,
}) => {
  const opened = await open(page, '/en/_look');
  const control = page.locator('[data-control="language"]');
  await expect(control).toHaveText(word('language.other', 'en'));
  await expect(control).toHaveAttribute('lang', 'ar');
  const numerals = () =>
    page.evaluate(() =>
      [...document.querySelectorAll('[data-chip] [data-num]')].map(
        (element) => element.textContent ?? '',
      ),
    );
  const english = await numerals();
  expect(english.length).toBeGreaterThan(4);
  const labelsBefore = await page.evaluate(
    () => window.__look?.labelFields() ?? [],
  );
  if (opened.look.basemap) {
    const verdict = judgeLabelLanguage(labelsBefore, 'en');
    expect(verdict.ok, verdict.detail).toBe(true);
  } else {
    expect(labelsBefore).toEqual([]);
  }
  await control.click();
  await page.waitForFunction(
    () =>
      document.documentElement.lang === 'ar' &&
      window.__look?.flipping === false,
  );
  expect(new URL(page.url()).pathname).toBe('/ar/_look');
  expect(await numerals()).toEqual(english);
  await expect(control).toHaveText(word('language.other', 'ar'));
  await expect(control).toHaveAttribute('lang', 'en');
  const after = await page.evaluate(() => ({
    bearing: window.__look?.bearing,
    zoom: window.__look?.zoom,
    labels: window.__look?.labelFields() ?? [],
  }));
  expect(after.bearing).toBe(opened.look.bearing);
  expect(after.zoom).toBe(opened.look.zoom);
  if (opened.look.basemap) {
    expect(after.labels.length).toBe(labelsBefore.length);
    const verdict = judgeLabelLanguage(after.labels, 'ar');
    expect(verdict.ok, verdict.detail).toBe(true);
  }
});

test('the wall density holds: one headline, at most three chips, one caveat', async ({
  page,
}) => {
  const opened = await open(page, '/en/_look');
  const counts = await page.evaluate(() => {
    const brief = document.querySelector('[data-plate="brief"]');
    return {
      headlines: brief?.querySelectorAll('[data-part="headline"]').length ?? 0,
      valueChips: brief?.querySelectorAll('[data-chip="value"]').length ?? 0,
      // Round 5g, finding 24: every chip of the answer card counts.
      chips:
        brief?.querySelectorAll('[data-card="answer"] [data-chip]').length ?? 0,
      caveats: brief?.querySelectorAll('[data-part="caveat"]').length ?? 0,
    };
  });
  if (opened.look.units === 0) {
    expect(counts).toEqual({
      headlines: 1,
      valueChips: 0,
      chips: 0,
      caveats: 1,
    });
  } else {
    const verdict = judgeDensity(counts);
    expect(verdict.ok, verdict.detail).toBe(true);
    expect(counts.valueChips).toBe(3);
    expect(counts.chips).toBe(3);
  }
});

test('a planted fourth chip on the answer card is caught', async ({ page }) => {
  await open(page, '/en/_look?plant=fourth-chip');
  const counts = await page.evaluate(() => {
    const brief = document.querySelector('[data-plate="brief"]');
    return {
      headlines: brief?.querySelectorAll('[data-part="headline"]').length ?? 0,
      valueChips: brief?.querySelectorAll('[data-chip="value"]').length ?? 0,
      chips:
        brief?.querySelectorAll('[data-card="answer"] [data-chip]').length ?? 0,
      caveats: brief?.querySelectorAll('[data-part="caveat"]').length ?? 0,
    };
  });
  const verdict = judgeDensity(counts);
  expect(counts.chips).toBe(4);
  expect(verdict.ok).toBe(false);
  expect(verdict.detail).toBe(
    'the answer card holds more than three chips of any kind',
  );
});

// Round 5g, finding 22 (DES-68): the legend names the date of the count in
// one reference chip; finding 24: it marks the classes the share counts,
// from the third break to the end of the scale.
function legendHead(page: Page) {
  return page.evaluate(() => {
    const shown = (element: Element | null): boolean =>
      element instanceof HTMLElement && element.getClientRects().length > 0;
    const key = document.querySelector('[data-plate="legend"]');
    const period = key?.querySelector('.legend-head .legend-period') ?? null;
    const box = (element: Element | null | undefined) => {
      const rect = element?.getBoundingClientRect();
      return rect === undefined ? null : { left: rect.left, right: rect.right };
    };
    const chip = key?.querySelectorAll('.legend-breaks .chip')[2];
    const swatches = key?.querySelectorAll('.legend-scale .legend-swatch');
    const mark = key?.querySelector('.legend-span-mark') ?? null;
    return {
      shown: shown(period),
      chips: [
        ...(period?.querySelectorAll('[data-chip="reference"]') ?? []),
      ].map((element) => element.textContent ?? ''),
      breakThree: box(chip),
      lastSwatch: box(swatches?.[swatches.length - 1]),
      mark: box(mark),
      markText: mark?.textContent ?? '',
      markShown: shown(mark),
    };
  });
}

async function releasePeriod(page: Page): Promise<string> {
  return page.evaluate(() => {
    const block = document.querySelector('#eii-release');
    const release = JSON.parse(block?.textContent ?? '{}') as {
      period?: string;
    };
    return release.period ?? '';
  });
}

for (const variant of VARIANTS) {
  test(`${variant.lang}-${variant.theme}: the legend names the date of the count and marks the densest areas`, async ({
    page,
  }) => {
    await open(page, `/${variant.lang}/_look?theme=${variant.theme}`);
    const period = await releasePeriod(page);
    expect(period).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    const want = formatDate(period, variant.lang);
    const head = await legendHead(page);
    const verdict = judgeLegendPeriod(head, want);
    expect(verdict.ok, verdict.detail).toBe(true);
    expect(head.markShown).toBe(true);
    expect(head.markText).toBe(word('legend.densest', variant.lang));
    expect(word('fact.topClasses', variant.lang).toLowerCase()).toContain(
      head.markText.toLowerCase(),
    );
    const centre =
      ((head.breakThree?.left ?? 0) + (head.breakThree?.right ?? 0)) / 2;
    expect(Math.abs((head.mark?.left ?? -99) - centre)).toBeLessThanOrEqual(2);
    expect(
      Math.abs((head.mark?.right ?? -99) - (head.lastSwatch?.right ?? 0)),
    ).toBeLessThanOrEqual(2);
    await streetCamera(page);
    const folded = await legendHead(page);
    const kept = judgeLegendPeriod(folded, want);
    expect(kept.ok, kept.detail).toBe(true);
  });
}

test('a planted legend without the date of the count is caught', async ({
  page,
}) => {
  await open(page, '/en/_look?plant=legend-no-period');
  const period = await releasePeriod(page);
  const verdict = judgeLegendPeriod(
    await legendHead(page),
    formatDate(period, 'en'),
  );
  expect(verdict.ok).toBe(false);
});

test('no visible text is below the wall floor, nothing leaves the safe area and nothing scrolls', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    for (const state of ['card', 'table', 'drawer'] as const) {
      const opened = await open(page, `/${lang}/_look`);
      if (state === 'table')
        await page.locator('[data-control="table"]').click();
      if (state === 'drawer') await evidenceChip(page, opened).click();
      const sizes = await page.evaluate(() => {
        const found: { size: number; where: string }[] = [];
        const walker = document.createTreeWalker(
          document.body,
          NodeFilter.SHOW_TEXT,
        );
        while (walker.nextNode()) {
          const node = walker.currentNode;
          if ((node.textContent ?? '').trim() === '') continue;
          const parent = node.parentElement;
          if (parent === null) continue;
          const box = parent.getBoundingClientRect();
          if (box.width === 0 || box.height === 0) continue;
          if (box.bottom < 0) continue;
          found.push({
            size: parseFloat(getComputedStyle(parent).fontSize),
            where: parent.getAttribute('data-part') ?? parent.tagName,
          });
        }
        return found;
      });
      const floor = judgeTextFloor(sizes, 28);
      expect(floor.ok, floor.detail).toBe(true);
      const found = await plates(page);
      const names = found.map((plate) => plate.name).sort();
      const expected = [
        'attribution',
        'legend',
        'topbar-end',
        'topbar-start',
        state === 'drawer' ? 'drawer' : 'brief',
      ].sort();
      expect(names).toEqual(expected);
      const inside = judgeInside(found, SAFE);
      expect(inside.ok, `${lang} ${state}: ${inside.detail}`).toBe(true);
      const apart = judgeNoOverlap(found);
      expect(apart.ok, `${lang} ${state}: ${apart.detail}`).toBe(true);
      const scroll = await page.evaluate(() => ({
        width: document.documentElement.scrollWidth,
        height: document.documentElement.scrollHeight,
        panels: [...document.querySelectorAll('[data-plate]')].filter(
          (element) =>
            element.scrollHeight > element.clientHeight + 1 ||
            element.scrollWidth > element.clientWidth + 1,
        ).length,
      }));
      expect(scroll).toEqual({ width: 1920, height: 1080, panels: 0 });
    }
  }
});

test('the source chain is titled, returns focus to its chip and keeps numerals in chips', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    const opened = await open(page, `/${lang}/_look`);
    const chip = evidenceChip(page, opened, 'areas-with-firms');
    await chip.click();
    const drawer = page.locator('.drawer');
    await expect(drawer.locator('h2')).toHaveText(word('drawer.title', lang));
    await expect(drawer.locator('h2')).toBeFocused();
    await expect(drawer.locator('[data-chip="value"]')).toHaveCount(1);
    const verdict = judgeNumerals(await numeralItems(page));
    expect(verdict.ok, verdict.detail).toBe(true);
    const surface = await page.evaluate(() => {
      const style = getComputedStyle(
        document.querySelector('.drawer') as Element,
      );
      return { shadow: style.boxShadow, background: style.backgroundColor };
    });
    expect(surface.shadow).not.toBe('none');
    expect(surface.background).toBe('rgb(33, 43, 56)');
    await drawer.locator('[data-control="back"]').click();
    await expect(drawer).toHaveCount(0);
    await expect(chip).toBeFocused();
  }
});

test('no audience sees a fallback typeface, and the ten digits share one width at every numeral size', async ({
  page,
}) => {
  await open(page, '/ar/_look');
  const fonts = await page.evaluate(() => ({
    latin: document.fonts.check('500 28px "IBM Plex Sans"'),
    arabic: document.fonts.check('500 31px "IBM Plex Sans Arabic"', 'عام'),
    english: getComputedStyle(
      document.querySelector('[data-control="language"]') as Element,
    ).fontFamily,
    headline: getComputedStyle(
      document.querySelector('[data-part="headline"]') as Element,
    ).fontFamily,
    number: getComputedStyle(
      document.querySelector('[data-chip] [data-num]') as Element,
    ).fontFamily,
  }));
  expect(fonts.latin).toBe(true);
  expect(fonts.arabic).toBe(true);
  expect(fonts.english).toMatch(/^"?IBM Plex Sans"?, "?IBM Plex Sans Arabic"?/);
  expect(fonts.headline).toMatch(
    /^"?IBM Plex Sans Arabic"?, "?IBM Plex Sans"?/,
  );
  expect(fonts.number).toMatch(/^"?IBM Plex Sans"?,/);
  const sizes = await page.evaluate(() => {
    const out: { name: string; widths: number[] }[] = [];
    for (const [name, size] of [
      ['large', 'large'],
      ['standard', 'standard'],
      ['compact', ''],
    ]) {
      const chip = document.createElement('span');
      chip.className = 'chip';
      if (size === '') chip.dataset.chip = 'compact';
      else chip.dataset.size = size as string;
      document.body.append(chip);
      const widths: number[] = [];
      for (let digit = 0; digit < 10; digit += 1) {
        const number = document.createElement('bdi');
        number.className = 'chip-num';
        number.lang = 'en';
        number.textContent = String(digit).repeat(8);
        chip.append(number);
        widths.push(number.getBoundingClientRect().width);
        number.remove();
      }
      chip.remove();
      out.push({ name: name as string, widths });
    }
    return out;
  });
  const verdict = judgeDigitWidths(sizes);
  expect(verdict.ok, verdict.detail).toBe(true);
});

test('the basemap is served by range from this origin, or the page stands on a neutral ground', async ({
  page,
  request,
  baseURL,
}) => {
  const opened = await open(page, '/en/_look');
  const response = await request.get(`${baseURL}${BASEMAP}`, {
    headers: { range: 'bytes=0-126' },
  });
  if (opened.look.basemap) {
    expect(response.status()).toBe(206);
    expect(response.headers()['content-range']).toMatch(/^bytes 0-126\//);
    expect((await response.body()).length).toBe(127);
    const ids = await page.evaluate(
      () => (window.__look?.labelFields() ?? []).length,
    );
    expect(ids).toBe(1);
  } else {
    expect(response.status()).toBe(404);
    expect(opened.look.units).toBe(0);
  }
});

test('the server sends a same-origin content security policy and the font licences', async ({
  request,
  baseURL,
}) => {
  const response = await request.get(`${baseURL}/en/_look`);
  expect(response.status()).toBe(200);
  const verdict = judgeCsp(
    response.headers()['content-security-policy'] ?? null,
  );
  expect(verdict.ok, verdict.detail).toBe(true);
  const licence = await request.get(
    `${baseURL}/licences/ibm-plex-sans-arabic-OFL.txt`,
  );
  expect(licence.status()).toBe(200);
  expect(await licence.text()).toContain('SIL Open Font License');
  expect((await request.get(`${baseURL}/fr/_look`)).status()).toBe(404);
});

// ---- Round 5: the home and its questions (P2), Back, the plates that fold
// at street zoom (V7), the company card (the owner's decision of 2026-11-13)
// and the street layers (V1, V4). Each judge has planted cases in
// tests/street.node-test.mjs; each behaviour has a planted page below.

function screenState(page: Page): Promise<ScreenState> {
  return page.evaluate(() => {
    const shown = (element: Element | null | undefined): boolean => {
      if (!(element instanceof HTMLElement)) return false;
      if (element.getClientRects().length === 0) return false;
      const style = getComputedStyle(element);
      return style.visibility !== 'hidden' && style.opacity !== '0';
    };
    const cards = [
      ...document.querySelectorAll<HTMLElement>(
        '[data-plate="brief"] [data-card]',
      ),
    ].filter((card) => shown(card));
    const questions = [
      ...document.querySelectorAll('[data-card="home"] [data-question]'),
    ];
    return {
      screen: window.__look?.screen ?? '',
      cards: cards.map((card) => card.dataset.card ?? ''),
      lit: window.__look?.litLevels() ?? [],
      legend: shown(document.querySelector('[data-plate="legend"]')),
      numerals: (document.body.innerText.match(/[0-9٠-٩۰-۹]/g) ?? []).length,
      questions: questions.filter((item) => shown(item)).length,
      back: shown(cards[0]?.querySelector('[data-control="back"]')),
    };
  });
}

async function expectScreen(page: Page, want: string, ok = true) {
  const verdict = judgeScreen(await screenState(page), want);
  expect(verdict.ok, verdict.detail).toBe(ok);
  return verdict;
}

async function choosePlace(page: Page): Promise<void> {
  await page.locator('[data-card="home"] [data-question="operate"]').click();
  await page.locator('[data-card="place"] [data-place="frame"]').click();
  await page.waitForFunction(
    () => window.__look?.screen === 'answer' && window.__look.lit === true,
  );
}

function camera(page: Page) {
  return page.evaluate(() => ({
    zoom: window.__look?.zoom ?? 0,
    pitch: window.__look?.pitch ?? 0,
    bearing: window.__look?.bearing ?? 0,
  }));
}

test('the home asks the four questions with no data layer, no legend and no numeral, in both languages', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    for (const theme of ['dark', 'light'] as const) {
      const opened = await open(page, `/${lang}/_look?theme=${theme}`, 'home');
      expect(opened.look.screen).toBe('home');
      expect(opened.consoleErrors).toEqual([]);
      await expectScreen(page, 'home');
      await expect(
        page.locator('[data-card="home"] [data-part="home-headline"]'),
      ).toHaveText(word('home.headline', lang));
      const asked = await page
        .locator('[data-card="home"] [data-question]')
        .allInnerTexts();
      expect(asked.map((text) => text.trim())).toEqual(
        ['q.market', 'q.operate', 'q.supply', 'q.grow'].map((key) =>
          word(key, lang),
        ),
      );
    }
  }
});

test('a planted home that lights the data layer is caught', async ({
  page,
}) => {
  await open(page, '/en/_look?plant=home-lit', 'home');
  await page.waitForFunction(() => window.__look?.planted === true);
  const verdict = await expectScreen(page, 'home', false);
  expect(verdict.detail).toContain('lights the data layer');
});

test('"Where should we operate?" asks for a place, and the place opens the lit answer that names its district', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    const opened = await open(page, `/${lang}/_look`, 'home');
    await page.locator('[data-card="home"] [data-question="operate"]').click();
    await expectScreen(page, 'place');
    await expect(
      page.locator('[data-card="place"] [data-place="frame"]'),
    ).toHaveText(word('place.frame', lang));
    await page.locator('[data-card="place"] [data-place="frame"]').click();
    await page.waitForFunction(
      () => window.__look?.screen === 'answer' && window.__look.lit === true,
    );
    await expectScreen(page, 'answer');
    const district = await page.evaluate(
      () => window.__look?.district() ?? null,
    );
    const headline = page.locator('[data-part="headline"]');
    if (opened.look.units === 0) {
      expect(district).toBeNull();
      await expect(headline).toHaveText(word('coverage.notMeasured', lang));
    } else if (district === null) {
      await expect(headline).toHaveText(word('card.headlineCore', lang));
    } else {
      await expect(headline).toContainText(district.name);
      await expect(page.locator('[data-part="district"]')).toHaveText(
        district.name,
      );
    }
  }
});

// Round 5e, E1: the quiet plate of P1 names the lit district just above its
// cell and sizes to its name (judgeDistrictPlate), in both languages and both
// themes, with motion on and with reduced motion. It is read in the captures'
// own state (settled, then a fresh frame), where its entrance has ended, so a
// capture never catches it entering.
async function districtPlate(page: Page) {
  return page.evaluate(() => {
    const district = window.__look?.district() ?? null;
    const element = document.querySelector('[data-part="district"]');
    if (district === null || !(element instanceof HTMLElement)) {
      return {
        district: district !== null,
        present: element !== null,
        found: null,
      };
    }
    const style = getComputedStyle(element);
    const range = document.createRange();
    range.selectNodeContents(element);
    const box = (rect: DOMRect) => ({
      x: rect.x,
      y: rect.y,
      width: rect.width,
      height: rect.height,
    });
    return {
      district: true,
      present: true,
      found: {
        name: district.name,
        text: element.textContent ?? '',
        shown:
          !element.hidden &&
          element.getClientRects().length > 0 &&
          style.visibility !== 'hidden' &&
          Number(style.opacity) === 1,
        running: element
          .getAnimations()
          .filter((animation) => animation.playState === 'running').length,
        plate: box(element.getBoundingClientRect()),
        textBox: box(range.getBoundingClientRect()),
        point: { x: district.x, y: district.y },
        viewport: { width: window.innerWidth, height: window.innerHeight },
      },
    };
  });
}

for (const variant of VARIANTS) {
  for (const motion of ['on', 'reduced'] as const) {
    test(`${variant.lang}-${variant.theme} names the lit district on a plate sized to its name, motion ${motion}`, async ({
      page,
      browser,
    }) => {
      const target = motion === 'on' ? await fullMotion(browser) : page;
      try {
        await open(
          target,
          `/${variant.lang}/_look?theme=${variant.theme}`,
          'settled',
        );
        await target.evaluate(() => window.__look?.rendered());
        const seen = await districtPlate(target);
        if (seen.found === null) {
          expect(seen.district).toBe(false);
          expect(seen.present).toBe(false);
          return;
        }
        const verdict = judgeDistrictPlate(seen.found);
        expect(verdict.ok, verdict.detail).toBe(true);
      } finally {
        if (motion === 'on') await target.context().close();
      }
    });
  }
}

test('a planted district plate stretched across the map is caught', async ({
  page,
}) => {
  await open(page, '/en/_look?plant=district-stretched', 'settled');
  await page.evaluate(() => window.__look?.rendered());
  const seen = await districtPlate(page);
  if (seen.found === null) {
    expect(seen.district).toBe(false);
    return;
  }
  const verdict = judgeDistrictPlate(seen.found);
  expect(verdict.ok).toBe(false);
  expect(verdict.detail).toMatch(/px wide for a name of/);
});

test('the other three questions open a quiet state with a way back to the home', async ({
  page,
}) => {
  await open(page, '/en/_look', 'home');
  for (const question of ['market', 'supply', 'grow']) {
    await page
      .locator(`[data-card="home"] [data-question="${question}"]`)
      .click();
    await expectScreen(page, 'notyet');
    await expect(page.locator('[data-card="notyet"] .card-eyebrow')).toHaveText(
      word(`q.${question}`, 'en'),
    );
    await page.locator('[data-card="notyet"] [data-control="back"]').click();
    await expectScreen(page, 'home');
  }
});

test('a planted step that skips the place is caught', async ({ page }) => {
  await open(page, '/en/_look?plant=place-skipped', 'home');
  await page.locator('[data-card="home"] [data-question="operate"]').click();
  await page.waitForFunction(() => window.__look?.lit === true);
  const verdict = await expectScreen(page, 'place', false);
  expect(verdict.detail).toContain('not place');
});

test('a planted blank quiet state is caught', async ({ page }) => {
  await open(page, '/en/_look?plant=notyet-blank', 'home');
  await page.locator('[data-card="home"] [data-question="market"]').click();
  const verdict = await expectScreen(page, 'notyet', false);
  expect(verdict.detail).toContain('no card');
});

test('Back from the answer puts the data out and returns to the home over the skyline', async ({
  page,
}) => {
  await open(page, '/en/_look', 'home');
  const home = await camera(page);
  await choosePlace(page);
  expect(await camera(page)).not.toEqual(home);
  await page.locator('[data-card="answer"] [data-control="back"]').click();
  await page.waitForFunction(
    (want) =>
      window.__look?.screen === 'home' &&
      window.__look.moving === false &&
      window.__look.zoom === want.zoom,
    home,
  );
  expect(await camera(page)).toEqual(home);
  await expectScreen(page, 'home');
  expect(
    await page.evaluate(
      () => (document.activeElement as HTMLElement | null)?.dataset.question,
    ),
  ).toBe('market');
});

test('a planted Back that keeps the data on is caught', async ({ page }) => {
  await open(page, '/en/_look?plant=back-keeps-data', 'home');
  await choosePlace(page);
  await page.locator('[data-card="answer"] [data-control="back"]').click();
  await page.waitForFunction(() => window.__look?.screen === 'home');
  const verdict = await expectScreen(page, 'home', false);
  expect(verdict.detail).toContain('lights the data layer');
});

function foldState(page: Page) {
  return page.evaluate(() => {
    const shown = (element: Element | null): boolean =>
      element instanceof HTMLElement && element.getClientRects().length > 0;
    const open = (selector: string) =>
      shown(document.querySelector(selector)) ? 'open' : 'folded';
    const brief = document.querySelector('[data-plate="brief"]');
    const plate = document.querySelector('[data-part="district"]');
    return {
      zoom: window.__look?.zoom ?? 0,
      brief: open('[data-card="answer"] .card-hero'),
      // Round 5g: only the scope line folds; the breaks and the direction
      // stay on the strip (DES-19).
      legend: open('[data-plate="legend"] .legend-scope'),
      // Round 5g, finding 27: the caveat stays on the folded strip (DES-05).
      caveat: shown(
        document.querySelector('[data-card="answer"] [data-part="caveat"]'),
      ),
      height: brief?.getBoundingClientRect().height ?? 0,
      plate: plate instanceof HTMLElement ? !plate.hidden : null,
    } as const;
  });
}

async function foldStates(page: Page) {
  const [a, , c] = STREET_CAMERAS;
  if (a === undefined || c === undefined) throw new Error('no street camera');
  const states = [await foldState(page)];
  for (const view of [a, c, { ...a, zoom: 11, pitch: 0, bearing: 0 }]) {
    await page.evaluate(
      (next) =>
        window.__look?.camera({
          center: next.center,
          zoom: next.zoom,
          pitch: next.pitch,
          bearing: next.bearing,
        }),
      view,
    );
    states.push(await foldState(page));
  }
  return states;
}

test('the Brief and the legend fold to a strip at street zoom and come back at city zoom', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    await open(page, `/${lang}/_look`);
    const states = await foldStates(page);
    const [, street, district, city] = states;
    expect(street?.zoom ?? 0).toBeGreaterThanOrEqual(FOLD_ZOOM);
    expect(city?.zoom ?? 99).toBeLessThanOrEqual(UNFOLD_ZOOM);
    const verdict = judgeFold(states);
    expect(verdict.ok, verdict.detail).toBe(true);
    expect(street?.brief).toBe('folded');
    expect(district?.brief).toBe('folded');
    expect(city?.brief).toBe('open');
    expect(street?.height ?? 0).toBeLessThan((city?.height ?? 0) / 2);
    expect(street?.caveat).toBe(true);
    expect(district?.caveat).toBe(true);
    expect(city?.caveat).toBe(true);
    if (street?.plate !== null) expect(street?.plate).toBe(false);
    if (city?.plate !== null) expect(city?.plate).toBe(true);
  }
});

// Ruling L-143 item 3: the answer opens on the City framing at a city scale,
// at or below the cap token, with the Brief and the legend open.
async function cityFrame(page: Page) {
  const state = await foldState(page);
  const cap = await page.evaluate(() =>
    Number.parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue(
        '--eii-city-max-zoom',
      ),
    ),
  );
  return judgeCityFrame(state, cap);
}

test('the City framing rests at a city scale with the plates open', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    await open(page, `/${lang}/_look`);
    const verdict = await cityFrame(page);
    expect(verdict.ok, verdict.detail).toBe(true);
  }
});

// Without the extract there is no lit unit: the framing fits the whole frame
// of the layer, which needs a zoom below the cap, so the plant has nothing to
// push past it.
test('a planted City framing with no city cap is caught', async ({ page }) => {
  const opened = await open(page, '/en/_look?plant=city-uncapped');
  const verdict = await cityFrame(page);
  if (opened.look.basemap) {
    expect(verdict.ok).toBe(false);
    expect(verdict.detail).toContain('past the city cap');
  } else {
    expect(verdict.ok, verdict.detail).toBe(true);
  }
});

test('a planted plate that stays open at street zoom is caught', async ({
  page,
}) => {
  await open(page, '/en/_look?plant=fold-stuck');
  const verdict = judgeFold(await foldStates(page));
  expect(verdict.ok).toBe(false);
  expect(verdict.detail).toContain('the brief is open');
});

// Round 5g, findings 4, 17, 21 and 25: the folded legend keeps its breaks
// and its direction in words, and "Show as table" works at street zoom.
function legendView(page: Page) {
  return page.evaluate(() => {
    const shown = (element: Element | null): boolean =>
      element instanceof HTMLElement && element.getClientRects().length > 0;
    const key = document.querySelector('[data-plate="legend"]');
    const direction = key?.querySelector('.legend-direction') ?? null;
    return {
      zoom: window.__look?.zoom ?? 0,
      fold: document.documentElement.dataset.fold ?? '',
      breaks: [...(key?.querySelectorAll('.legend-breaks .chip') ?? [])].filter(
        shown,
      ).length,
      direction: shown(direction) ? (direction?.textContent ?? '') : '',
      scale: shown(key?.querySelector('.legend-scale') ?? null),
      table: shown(key?.querySelector('.legend-table') ?? null),
      rows: [...(key?.querySelectorAll('.legend-table tbody tr') ?? [])].filter(
        (row) =>
          shown(row) && shown(row.querySelector('.legend-swatch-row') ?? null),
      ).length,
    };
  });
}

async function streetCamera(page: Page) {
  const [a] = STREET_CAMERAS;
  if (a === undefined) throw new Error('no street camera');
  await page.evaluate((next) => window.__look?.camera(next), a);
}

async function foldedLegend(page: Page) {
  await streetCamera(page);
  const before = await legendView(page);
  await page.locator('[data-control="table"]').click();
  const pressed = await legendView(page);
  await page.locator('[data-control="table"]').click();
  const back = await legendView(page);
  const verdict = judgeFoldedLegend({
    zoom: before.zoom,
    breaks: before.breaks,
    direction: before.direction,
    table: { shown: pressed.table, rows: pressed.rows },
  });
  return { before, pressed, back, verdict };
}

for (const variant of VARIANTS) {
  test(`${variant.lang}-${variant.theme}: the folded legend keeps its breaks and its direction, and shows its table`, async ({
    page,
  }) => {
    await open(page, `/${variant.lang}/_look?theme=${variant.theme}`);
    const seen = await foldedLegend(page);
    expect(seen.before.fold).toBe('street');
    expect(seen.verdict.ok, seen.verdict.detail).toBe(true);
    expect(seen.before.direction).toBe(
      word(`legend.direction.${variant.theme}`, variant.lang),
    );
    expect(seen.pressed.scale).toBe(false);
    expect(seen.back.scale).toBe(true);
    expect(seen.back.breaks).toBe(4);
  });
}

test('the table asked for at the City framing stays shown at street zoom', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    await open(page, `/${lang}/_look`);
    await page.locator('[data-control="table"]').click();
    await streetCamera(page);
    const seen = await legendView(page);
    expect(seen.fold).toBe('street');
    expect(seen.table).toBe(true);
    expect(seen.rows).toBe(5);
    expect(seen.scale).toBe(false);
  }
});

test('a planted fold that hides the breaks and the direction is caught', async ({
  page,
}) => {
  await open(page, '/en/_look?plant=legend-bare');
  const seen = await foldedLegend(page);
  expect(seen.verdict.ok).toBe(false);
  expect(seen.verdict.detail).toContain('breaks');
});

test('a planted fold that hides the table is caught', async ({ page }) => {
  await open(page, '/en/_look?plant=fold-hides-table');
  const seen = await foldedLegend(page);
  expect(seen.verdict.ok).toBe(false);
  expect(seen.verdict.detail).toContain('table');
});

// The first row of the committed invented stand-in (never the real file).
function standInRow(): Record<string, string> {
  const text = fs.readFileSync(
    new URL('../register/establishments.csv', import.meta.url),
    'utf8',
  );
  const [head, first] = text.trim().split('\n');
  if (head === undefined || first === undefined)
    throw new Error('the stand-in is empty');
  const names = head.split(',');
  const values = first.split(',');
  return Object.fromEntries(
    names.map((name, index) => [name, values[index] ?? '']),
  );
}

// Whether the page serves the stand-in's row. The run without the extract
// stands on an empty folder, which holds no register either: there the page
// has no establishment, and opening a key must show no card.
async function rowServed(page: Page, key: string): Promise<boolean> {
  const served = await page.evaluate((wanted) => {
    const text = document.getElementById('eii-release')?.textContent ?? '{}';
    const release = JSON.parse(text) as {
      establishments?: { row_key?: string }[];
    };
    return (release.establishments ?? []).some((row) => row.row_key === wanted);
  }, key);
  if (!served) {
    await page.evaluate((row) => window.__look?.openPoint?.(row), key);
    await expect(page.locator('[data-part="point-card"]')).toBeHidden();
  }
  return served;
}

async function openCard(page: Page, key: string) {
  await page.evaluate((row) => window.__look?.openPoint?.(row), key);
  await expect(page.locator('[data-part="point-card"]')).toBeVisible();
  return page.evaluate(() =>
    [
      ...document.querySelectorAll<HTMLElement>(
        '[data-part="point-card"] [data-field]',
      ),
    ].map((row) => {
      const chip = row.querySelector('[data-chip]');
      return {
        field: row.dataset.field ?? '',
        label: row.querySelector('.point-label')?.textContent ?? '',
        value: row.lastElementChild?.textContent ?? '',
        chip: chip?.getAttribute('data-chip') ?? null,
        fact: (chip?.getAttribute('data-facts') ?? '').split(' ')[0] || null,
      };
    }),
  );
}

test('the company card shows its published fields and the number of employees, in both languages', async ({
  page,
}) => {
  const row = standInRow();
  const employees = Number(row.employees);
  expect(Number.isInteger(employees)).toBe(true);
  for (const lang of ['en', 'ar'] as const) {
    await open(page, `/${lang}/_look`);
    if (!(await rowServed(page, row.row_key ?? ''))) continue;
    const found = await openCard(page, row.row_key ?? '');
    const verdict = judgeCard(found, { employees });
    expect(verdict.ok, verdict.detail).toBe(true);
    for (const item of found) expect(item.label).toBe(word(item.field, lang));
    expect(found.map((item) => item.field)).toContain('field.employees');
    const numerals = judgeNumerals(await numeralItems(page));
    expect(numerals.ok, numerals.detail).toBe(true);
    // Round 5g, finding 15: the counts are chained value chips that open
    // their source chain.
    const chips = judgeCardChips(found, await releasedFacts(page));
    expect(chips.ok, chips.detail).toBe(true);
    const employeesFact = found.find(
      (item) => item.field === 'field.employees',
    )?.fact;
    await page
      .locator(
        '[data-part="point-card"] [data-field="field.employees"] [data-chip]',
      )
      .click();
    await expect(page.locator('[data-drawer-fact]')).toHaveAttribute(
      'data-drawer-fact',
      employeesFact ?? '',
    );
  }
});

test('a planted number of employees in a reference chip is caught', async ({
  page,
}) => {
  const row = standInRow();
  await open(page, '/en/_look?plant=card-reference-employees');
  if (!(await rowServed(page, row.row_key ?? ''))) return;
  const found = await openCard(page, row.row_key ?? '');
  const verdict = judgeCardChips(found, await releasedFacts(page));
  expect(verdict.ok).toBe(false);
  expect(verdict.detail).toContain('employees');
});

// Round 5g, finding 23 (DES-61): each legend swatch is drawn as the map
// draws its class: the fill at the class opacity over the land (sRGB).
function swatchColours(page: Page) {
  return page.evaluate(() => {
    const css = getComputedStyle(document.documentElement);
    const token = (name: string) => css.getPropertyValue(name).trim();
    const hex = (value: string) =>
      [1, 3, 5].map((at) => Number.parseInt(value.slice(at, at + 2), 16));
    const parse = (value: string): number[] => {
      const srgb = /color\(srgb ([\d.]+) ([\d.]+) ([\d.]+)/.exec(value);
      if (srgb !== null)
        return srgb.slice(1, 4).map((part) => Math.round(Number(part) * 255));
      const rgb = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(value);
      return rgb === null ? [] : rgb.slice(1, 4).map(Number);
    };
    const land = hex(token('--eii-map-land'));
    const cells = [1, 2, 3, 4, 5].map((step) => {
      const fill = hex(token(`--eii-seq-${step}`));
      const alpha = Number(
        token(step === 1 ? '--eii-unit-opacity-1' : '--eii-unit-opacity'),
      );
      return fill.map((channel, at) =>
        Math.round(alpha * channel + (1 - alpha) * (land[at] ?? 0)),
      );
    });
    const swatches = [
      ...document.querySelectorAll<HTMLElement>(
        '[data-plate="legend"] .legend-scale .legend-swatch',
      ),
    ].map((swatch) => {
      const style = getComputedStyle(swatch);
      const opacity = Number(style.opacity);
      const colour = parse(style.backgroundColor);
      return colour.map((channel, at) =>
        Math.round(opacity * channel + (1 - opacity) * (land[at] ?? 0)),
      );
    });
    return { swatches, cells };
  });
}

for (const theme of ['dark', 'light'] as const) {
  test(`${theme}: each legend swatch is its class drawn over the land`, async ({
    page,
  }) => {
    await open(page, `/en/_look?theme=${theme}`);
    const seen = await swatchColours(page);
    const verdict = judgeSwatches(seen.swatches, seen.cells);
    expect(verdict.ok, verdict.detail).toBe(true);
  });
}

test('a planted opaque top swatch is caught', async ({ page }) => {
  await open(page, '/en/_look?plant=swatch-opaque');
  const seen = await swatchColours(page);
  const verdict = judgeSwatches(seen.swatches, seen.cells);
  expect(verdict.ok).toBe(false);
  expect(verdict.detail).toContain('swatch 5');
});

// Round 5g, findings 1, 18 and 19: the points in ink with a ring, keyed in
// the legend; findings 11 and 16: the type control from zoom 14, with a
// heading and catalogue names.
function pointPaints(page: Page) {
  return page.evaluate(() => {
    const css = getComputedStyle(document.documentElement);
    const token = (name: string) => css.getPropertyValue(name).trim();
    const layers = (window.__look?.layers() ?? []).map(
      (layer) =>
        JSON.parse(layer) as { id: string; paint?: Record<string, unknown> },
    );
    const paint = (id: string) =>
      layers.find((layer) => layer.id === id)?.paint ?? {};
    const shown = (selector: string) =>
      [...document.querySelectorAll(selector)].some(
        (element) => element.getClientRects().length > 0,
      );
    return {
      ramp: [1, 2, 3, 4, 5].map((step) => token(`--eii-seq-${step}`)),
      ink: token('--eii-map-point'),
      point: paint('establishments-point')['circle-color'],
      cluster: paint('establishments-cluster')['circle-color'],
      halo: paint('establishments-point')['circle-stroke-color'],
      ring: paint('establishments-point')['circle-stroke-width'],
      // The map draws a layer from its exact zoom; the rounded diagnostic
      // can read 12 a hair below the cluster layer's bound.
      zoom: window.__look?.exactZoom?.() ?? 0,
      keyPoint: shown('[data-plate="legend"] [data-key="point"]'),
      keyCluster: shown('[data-plate="legend"] [data-key="cluster"]'),
      keyPointText:
        document.querySelector('[data-plate="legend"] [data-key="point"]')
          ?.textContent ?? '',
      control: shown('[data-control="types"]'),
      list: shown('.type-counts'),
      title: document.querySelector('.type-counts-title')?.textContent ?? '',
      rows: [...document.querySelectorAll('.type-row')].map((row) => ({
        slug: row.getAttribute('data-type') ?? '',
        name: row.querySelector('.type-name')?.textContent ?? '',
        // The count chip names its fact.
        fact:
          row.querySelector('[data-chip]')?.getAttribute('data-facts') ?? '',
      })),
      controls: document.querySelectorAll('[data-control="types"]').length,
    };
  });
}

const TYPE_SLUGS = ['bakery', 'grocery', 'pharmacy', 'tailor', 'workshop'];

for (const variant of VARIANTS) {
  test(`${variant.lang}-${variant.theme}: the points are ink with a key, and one type is picked from zoom 14`, async ({
    page,
  }) => {
    await open(page, `/${variant.lang}/_look?theme=${variant.theme}`);
    const want = {
      title: word('legend.types.title', variant.lang),
      names: Object.fromEntries(
        TYPE_SLUGS.map((slug) => [slug, word(`type.${slug}`, variant.lang)]),
      ),
    };
    const city = await pointPaints(page);
    if (city.controls === 0) {
      expect(city.point).toBeUndefined();
      return;
    }
    const cityKey = judgePointKey(
      { zoom: city.zoom, point: city.keyPoint, cluster: city.keyCluster },
      12,
      14,
    );
    expect(cityKey.ok, `${cityKey.detail} ${JSON.stringify(city)}`).toBe(true);
    const cityControl = judgeTypeControl(city, 14, want);
    expect(cityControl.ok, cityControl.detail).toBe(true);
    const [, , c] = STREET_CAMERAS;
    if (c === undefined) throw new Error('no street camera');
    await page.evaluate(
      (view) => window.__look?.camera({ ...view, zoom: 13 }),
      c,
    );
    const district = await pointPaints(page);
    const districtKey = judgePointKey(
      {
        zoom: district.zoom,
        point: district.keyPoint,
        cluster: district.keyCluster,
      },
      12,
      14,
    );
    expect(districtKey.ok, districtKey.detail).toBe(true);
    expect(district.cluster).toBe(district.ink);
    await page.evaluate((view) => window.__look?.camera(view), c);
    const street = await pointPaints(page);
    const colours = judgePointColours(
      { point: street.point, cluster: street.cluster, halo: street.halo },
      street.ramp,
    );
    expect(colours.ok, colours.detail).toBe(true);
    expect(street.point).toBe(street.ink);
    expect(street.ring).toBe(2);
    const key = judgePointKey(
      { zoom: street.zoom, point: street.keyPoint, cluster: street.keyCluster },
      12,
      14,
    );
    expect(key.ok, key.detail).toBe(true);
    expect(street.keyPointText).toBe(word('legend.point', variant.lang));
    await page.locator('[data-control="types"]').click();
    const listed = await pointPaints(page);
    const control = judgeTypeControl(listed, 14, want);
    expect(control.ok, control.detail).toBe(true);
    expect(listed.rows.map((row) => row.slug)).toEqual(TYPE_SLUGS);
    await page.locator('.type-row[data-type="tailor"] .type-pick').click();
    await expect(
      page.locator('.type-row[data-type="tailor"] .type-pick'),
    ).toHaveAttribute('aria-pressed', 'true');
    const picked = await pointPaints(page);
    const typed = judgePointColours(
      { point: picked.point, types: picked.point },
      picked.ramp,
    );
    expect(typed.ok, typed.detail).toBe(true);
    expect(JSON.stringify(picked.point)).toContain('tailor');
    await page.evaluate(
      (view) =>
        window.__look?.camera({ ...view, zoom: 11, pitch: 0, bearing: 0 }),
      c,
    );
    const away = await pointPaints(page);
    expect(away.control).toBe(false);
    expect(away.list).toBe(false);
  });
}

test('planted points on the ramp, a missing key, a control below zoom 14 or a list without heading are caught', async ({
  page,
}) => {
  const [, , c] = STREET_CAMERAS;
  if (c === undefined) throw new Error('no street camera');
  const want = {
    title: word('legend.types.title', 'en'),
    names: Object.fromEntries(
      TYPE_SLUGS.map((slug) => [slug, word(`type.${slug}`, 'en')]),
    ),
  };
  for (const plant of [
    'points-on-ramp',
    'no-point-key',
    'types-everywhere',
    'types-no-heading',
  ]) {
    await open(page, `/en/_look?plant=${plant}`);
    const city = await pointPaints(page);
    if (city.controls === 0) return;
    if (plant === 'types-everywhere') {
      expect(judgeTypeControl(city, 14, want).ok, plant).toBe(false);
      continue;
    }
    await page.evaluate((view) => window.__look?.camera(view), c);
    if (plant === 'types-no-heading')
      await page.locator('[data-control="types"]').click();
    const street = await pointPaints(page);
    const verdicts = [
      judgePointColours(
        { point: street.point, cluster: street.cluster, halo: street.halo },
        street.ramp,
      ),
      judgePointKey(
        {
          zoom: street.zoom,
          point: street.keyPoint,
          cluster: street.keyCluster,
        },
        12,
        14,
      ),
      judgeTypeControl(street, 14, want),
    ];
    expect(
      verdicts.some((verdict) => !verdict.ok),
      plant,
    ).toBe(true);
  }
});

test('a planted card without the number of employees is caught', async ({
  page,
}) => {
  const row = standInRow();
  await open(page, '/en/_look?plant=card-no-employees');
  if (!(await rowServed(page, row.row_key ?? ''))) return;
  const found = await openCard(page, row.row_key ?? '');
  const verdict = judgeCard(found, { employees: Number(row.employees) });
  expect(verdict.ok).toBe(false);
  expect(verdict.detail).toContain('number of employees');
});

test('every footprint of the archive is drawn from zoom 13 and the roads are named by tier', async ({
  page,
}) => {
  const opened = await open(page, '/en/_look');
  const layers = (await page.evaluate(() => window.__look?.layers() ?? [])).map(
    (layer) => JSON.parse(layer) as MapLayer,
  );
  const archive = layers.filter(
    (layer) =>
      layer.id.startsWith('buildings-') && layer.id !== 'buildings-base',
  );
  if (!opened.look.basemap) {
    expect(archive).toEqual([]);
    return;
  }
  const roads = judgeRoadLabels(layers);
  expect(roads.ok, roads.detail).toBe(true);
  if (archive.length === 0) return;
  const buildings = judgeBuildingLayers(archive);
  expect(buildings.ok, buildings.detail).toBe(true);
  const [, , c] = STREET_CAMERAS;
  if (c === undefined) throw new Error('no street camera');
  await page.evaluate(
    (next) =>
      window.__look?.camera({
        center: next.center,
        zoom: next.zoom,
        pitch: next.pitch,
        bearing: next.bearing,
      }),
    c,
  );
  await page.evaluate(() => window.__look?.rendered());
  expect(
    await page.evaluate(
      () => window.__look?.sourceFeatures('buildings', 'buildings') ?? 0,
    ),
  ).toBeGreaterThan(0);
});

// Round 5f, F2: no establishment point covers a place, district or road
// name. The order is read as the answer opens and again after the theme and
// the language change by their controls (the page restyles by a diff).
// Without the extract the page has no register, so no point layer.
async function pointOrder(page: Page) {
  const layers = (await page.evaluate(() => window.__look?.layers() ?? [])).map(
    (layer) => JSON.parse(layer) as MapLayer,
  );
  return {
    ids: layers.map((layer) => layer.id),
    verdict: judgePointsUnderLabels(layers),
  };
}

test('the establishment points lie under every place, district and road name, after a theme and a language change too', async ({
  page,
}) => {
  const opened = await open(page, '/en/_look?theme=dark');
  const states = [{ name: 'en-dark', ...(await pointOrder(page)) }];
  await page.locator('[data-control="theme-light"]').click();
  await page.waitForFunction(
    () =>
      window.__look?.theme === 'light' && window.__look.mapTheme === 'light',
  );
  states.push({ name: 'en-light', ...(await pointOrder(page)) });
  await page.locator('[data-control="language"]').click();
  await page.waitForFunction(
    () =>
      document.documentElement.lang === 'ar' &&
      window.__look?.flipping === false,
  );
  states.push({ name: 'ar-light', ...(await pointOrder(page)) });
  for (const state of states) {
    if (!opened.look.basemap) {
      expect(state.ids, state.name).not.toContain('establishments-point');
      continue;
    }
    expect(state.verdict.ok, `${state.name}: ${state.verdict.detail}`).toBe(
      true,
    );
  }
});

test('a planted point layer drawn over the labels is caught', async ({
  page,
}) => {
  const opened = await open(page, '/en/_look?plant=points-over-labels');
  await page.waitForFunction(() => window.__look?.planted === true);
  const { ids, verdict } = await pointOrder(page);
  if (opened.look.basemap) {
    expect(verdict.ok).toBe(false);
    expect(verdict.detail).toContain('label-district');
  } else {
    expect(ids).not.toContain('establishments-point');
  }
});

// Round 5g, G2: at the two West Bay street cameras each district name is
// drawn once, in both languages.
test('each district name is drawn once at the West Bay cameras', async ({
  page,
}) => {
  const cameras = STREET_CAMERAS.filter(
    (item) => item.name === 'c' || item.name === 'd',
  );
  for (const lang of ['en', 'ar'] as const) {
    await open(page, `/${lang}/_look`);
    for (const item of cameras) {
      await page.evaluate(
        (next) =>
          window.__look?.camera({
            center: next.center,
            zoom: next.zoom,
            pitch: next.pitch,
            bearing: next.bearing,
          }),
        item,
      );
      const names = await page.evaluate(
        () => window.__look?.districtNames() ?? [],
      );
      const verdict = judgeUniqueNames(names);
      expect(verdict.ok, `${lang} ${item.name}: ${verdict.detail}`).toBe(true);
    }
  }
});

function bracketMeasure(page: Page) {
  return page.evaluate(() => {
    const mark = document.querySelector('.legend-span-mark');
    if (!(mark instanceof HTMLElement)) return null;
    const range = document.createRange();
    range.selectNodeContents(mark);
    const rects = [...range.getClientRects()];
    const tops = new Set(rects.map((rect) => Math.round(rect.top)));
    const text = range.getBoundingClientRect();
    const bracket = mark.getBoundingClientRect();
    return {
      lines: tops.size,
      lang: document.documentElement.lang,
      textLeft: text.left,
      textRight: text.right,
      bracketLeft: bracket.left,
      bracketRight: bracket.right,
    };
  });
}

for (const variant of VARIANTS) {
  test(`${variant.lang}-${variant.theme}: the densest-areas bracket label is one line`, async ({
    page,
  }) => {
    await open(page, `/${variant.lang}/_look?theme=${variant.theme}`);
    const measured = await bracketMeasure(page);
    if (measured === null) throw new Error('the bracket label is absent');
    const verdict = judgeBracketLabel(measured);
    expect(verdict.ok, verdict.detail).toBe(true);
  });
}

test('a planted long densest-areas label that wraps is caught', async ({
  page,
}) => {
  await open(page, '/ar/_look?plant=bracket-wraps');
  await page.waitForFunction(() => window.__look?.planted === true);
  const measured = await bracketMeasure(page);
  if (measured === null) throw new Error('the bracket label is absent');
  const verdict = judgeBracketLabel(measured);
  expect(verdict.ok).toBe(false);
  expect(verdict.detail).toMatch(/wraps/);
});

async function plateRects(page: Page) {
  return page.evaluate(() =>
    [...document.querySelectorAll('[data-plate]')]
      .map((element) => {
        const box = element.getBoundingClientRect();
        return {
          x: box.x,
          y: box.y,
          width: box.width,
          height: box.height,
        };
      })
      .filter((box) => box.width > 0 && box.height > 0),
  );
}

async function streetCover(page: Page, lang: 'en' | 'ar') {
  await open(page, `/${lang}/_look`);
  const counts: number[] = [];
  for (const item of STREET_CAMERAS) {
    await page.evaluate(
      (next) =>
        window.__look?.camera({
          center: next.center,
          zoom: next.zoom,
          pitch: next.pitch,
          bearing: next.bearing,
        }),
      item,
    );
    counts.push(
      await page.evaluate(
        (rects) => window.__look?.litUnder(rects) ?? 0,
        await plateRects(page),
      ),
    );
  }
  return counts;
}

test('at each street camera the Arabic plates cover no more lit data than the English plates', async ({
  page,
}) => {
  const en = await streetCover(page, 'en');
  const ar = await streetCover(page, 'ar');
  const rows = STREET_CAMERAS.map((item, index) => ({
    camera: item.name,
    en: en[index] ?? 0,
    ar: ar[index] ?? 0,
  }));
  const verdict = judgeStreetCover(rows);
  expect(verdict.ok, verdict.detail).toBe(true);
});

test('a street camera that ignores the mirrored plates is caught', async ({
  page,
}) => {
  const counts: Record<'en' | 'ar', number[]> = { en: [], ar: [] };
  for (const lang of ['en', 'ar'] as const) {
    await open(page, `/${lang}/_look?plant=street-unpadded`);
    for (const item of STREET_CAMERAS) {
      await page.evaluate(
        (next) =>
          window.__look?.camera({
            center: next.center,
            zoom: next.zoom,
            pitch: next.pitch,
            bearing: next.bearing,
          }),
        item,
      );
      counts[lang].push(
        await page.evaluate(
          (rects) => window.__look?.litUnder(rects) ?? 0,
          await plateRects(page),
        ),
      );
    }
  }
  const rows = STREET_CAMERAS.map((item, index) => ({
    camera: item.name,
    en: counts.en[index] ?? 0,
    ar: counts.ar[index] ?? 0,
  }));
  const units = await page.evaluate(() => window.__look?.units ?? 0);
  const verdict = judgeStreetCover(rows);
  // With no lit cells there is nothing for a plate to cover.
  if (units === 0) {
    expect(verdict.ok).toBe(true);
    return;
  }
  expect(verdict.ok).toBe(false);
});

async function onScreenBright(page: Page) {
  return page.evaluate(() => {
    const width = window.innerWidth;
    const height = window.innerHeight;
    return (window.__look?.brightCorners() ?? []).filter(
      (point) =>
        point.x >= 0 && point.y >= 0 && point.x <= width && point.y <= height,
    );
  });
}

async function corePlates(page: Page) {
  return page.evaluate(() =>
    ['legend', 'attribution'].flatMap((name) => {
      const element = document.querySelector(`[data-plate="${name}"]`);
      if (!(element instanceof HTMLElement)) return [];
      const box = element.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) return [];
      return [
        { name, x: box.x, y: box.y, width: box.width, height: box.height },
      ];
    }),
  );
}

for (const lang of ['en', 'ar'] as const) {
  test(`${lang}: the buildings view keeps the brightest cells clear of the plates`, async ({
    page,
  }) => {
    await open(page, `/${lang}/_look`);
    await page.evaluate(() => window.__look?.showBuildings());
    await page.evaluate(() => window.__look?.rendered());
    const verdict = judgeCoreClear(
      await onScreenBright(page),
      await corePlates(page),
    );
    expect(verdict.ok, verdict.detail).toBe(true);
  });
}

test('a planted bright cell under the legend is caught', async ({ page }) => {
  await open(page, '/en/_look?plant=buildings-core-under-plate');
  await page.evaluate(() => window.__look?.showBuildings());
  await page.evaluate(() => window.__look?.rendered());
  const points = await onScreenBright(page);
  const verdict = judgeCoreClear(points, await corePlates(page));
  if (points.length === 0) {
    expect(verdict.ok).toBe(true);
    return;
  }
  expect(verdict.ok).toBe(false);
  expect(verdict.detail).toContain('legend');
});

test('origin labels planted in open drawers and accessible names are caught', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    for (const theme of ['dark', 'light']) {
      const opened = await open(page, `/${lang}/_look?theme=${theme}`);
      await evidenceChip(page, opened).click();
      for (const label of [
        lang === 'en' ? 'Synthetic' : 'اصطناعية',
        lang === 'en' ? 'Public' : 'عام',
        lang === 'en' ? 'fixture' : 'تجريبية',
      ]) {
        await page
          .locator('.drawer h2')
          .evaluate(
            (node, text) => node.setAttribute('aria-label', text),
            label,
          );
        expect(judgeClassWords(await screenText(page)).ok).toBe(false);
        await page
          .locator('.drawer h2')
          .evaluate((node) => node.removeAttribute('aria-label'));
        expect(judgeClassWords(await screenText(page)).ok).toBe(true);
        await page.locator('.drawer h2').evaluate((node, text) => {
          node.textContent = text;
        }, label);
        expect(judgeClassWords(await screenText(page)).ok).toBe(false);
        await page.locator('.drawer h2').evaluate(
          (node, text) => {
            node.textContent = text;
          },
          word('drawer.title', lang),
        );
      }
    }
  }
});

// F1: serve a release whose cell table has no measurements. The scale is
// still configuration, but no summary or summary method may appear.
test('empty cell coverage renders not measured without summary chips or methods', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    for (const theme of ['dark', 'light']) {
      await open(page, `/${lang}/_look?theme=${theme}`);
      await page.route(`**/${lang}/_look?**`, async (route) => {
        const response = await route.fetch();
        const html = await response.text();
        const body = html.replace(
          /(<script[^>]*id="eii-release"[^>]*>)([\s\S]*?)(<\/script>)/,
          (_match, before: string, json: string, after: string) => {
            const release = JSON.parse(json);
            release.layer.cells = [];
            release.facts = release.facts.filter(
              (fact: { id: string }) =>
                !['densest-unit', 'areas-with-firms', 'top-classes'].includes(
                  fact.id,
                ),
            );
            return `${before}${JSON.stringify(release).replace(/</g, '\\u003c')}${after}`;
          },
        );
        await route.fulfill({ response, body });
      });
      await page.reload();
      await page.waitForFunction(
        () =>
          window.__look?.lit === true || (window.__look?.failure ?? '') !== '',
      );
      expect(await page.evaluate(() => window.__look?.failure)).toBe('');
      await expect(
        page.locator('[data-card="answer"] [data-part="headline"]'),
      ).toHaveText(word('coverage.notMeasured', lang));
      await expect(
        page.locator('[data-card="answer"] [data-chip]'),
      ).toHaveCount(0);
      await expect(page.locator('[data-control="more"]')).toHaveCount(0);
      const why = page.locator('[data-control="coverage-why"]');
      await expect(why).toHaveText(word('coverage.why', lang));
      await why.click();
      const drawer = page.locator('.drawer');
      await expect(drawer).toContainText(word('coverage.reason', lang));
      await expect(drawer).toContainText(word('coverage.rule', lang));
      await expect(drawer).toContainText(word('coverage.alternative', lang));
      await expect(drawer.locator('[data-chip]')).toHaveCount(0);
      await page.keyboard.press('Escape');
      await expect(drawer).toHaveCount(0);
      await expect(why).toBeFocused();
      // Plant the original defect at the rendered boundary: a cell-dependent
      // chip is present even though the release has no cells.
      await page
        .locator('.legend-breaks button[data-fact="break-1"]')
        .evaluate((node) => {
          const planted = node.cloneNode(true) as HTMLElement;
          planted.dataset.fact = 'densest-unit';
          planted.dataset.facts = 'densest-unit';
          document.querySelector('[data-card="answer"]')?.append(planted);
        });
      expect(
        judgeChipChains(
          await chipsFound(page),
          await releasedFacts(page),
          EXPECTED_FACTS.slice(3),
        ).ok,
      ).toBe(false);
      const facts = await releasedFacts(page);
      expect(
        facts.some((fact) =>
          [
            'chain.methodUnit',
            'chain.methodMean',
            'chain.methodShare',
          ].includes(fact.chain?.method ?? ''),
        ),
      ).toBe(false);
      await page.unroute(`**/${lang}/_look?**`);
    }
  }
});

test('a range chip opens both source chains and a planted missing high chain is caught', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    await open(page, `/${lang}/_look?plant=range-chip`);
    const chip = page.locator('button[data-facts="break-1 break-2"]');
    await chip.click();
    const drawer = page.locator('.drawer');
    await expect(drawer.locator('[data-chip="value"]')).toHaveCount(2);
    const chains = drawer.locator('[data-chain-fact]');
    await expect(chains).toHaveCount(2);
    await expect(chains.nth(0)).toHaveAttribute('data-chain-fact', 'break-1');
    await expect(chains.nth(1)).toHaveAttribute('data-chain-fact', 'break-2');
    const facts = await releasedFacts(page);
    for (const id of ['break-1', 'break-2']) {
      const chain = drawer.locator(`[data-chain-fact="${id}"]`);
      const fact = facts.find((item) => item.id === id);
      if (!fact?.chain) throw new Error('range fact has no chain');
      const choice = drawer.locator(
        `[data-control="range-fact"][data-fact="${id}"]`,
      );
      await choice.click();
      await expect(choice).toHaveAttribute('aria-pressed', 'true');
      await expect(drawer).toHaveAttribute('data-drawer-fact', id);
      await expect(chain).toBeVisible();
      const inside = judgeInside(await plates(page), SAFE);
      expect(inside.ok, inside.detail).toBe(true);
      await expect(chain.locator('[data-chip="value"]')).toHaveAttribute(
        'data-fact',
        id,
      );
      await expect(chain).toContainText(word(fact.chain.method, lang));
      await expect(chain).toContainText(fact.chain.method_version);
    }
    await drawer
      .locator('[data-chain-fact="break-2"]')
      .evaluate((node) => node.remove());
    expect(
      await chains.evaluateAll((nodes) =>
        nodes.map((node) => node.getAttribute('data-chain-fact')),
      ),
    ).not.toEqual(['break-1', 'break-2']);
    await page.keyboard.press('Escape');
    await expect(drawer).toHaveCount(0);
    await expect(chip).toBeFocused();
  }
});

test('Escape closes the source drawer and returns focus to its opening chip', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    const opened = await open(page, `/${lang}/_look`);
    const chip = evidenceChip(page, opened);
    await chip.click();
    await expect(page.locator('.drawer h2')).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(page.locator('.drawer')).toHaveCount(0);
    await expect(chip).toBeFocused();
  }
});

test('release-built Public inputs and generated inputs keep every source link in the drawer', async ({
  page,
}) => {
  const input: SourceInput = {
    provenance: 'public',
    publisher: 'Invented publisher',
    dataset: 'Invented density inputs',
    source: 'Invented source page',
    licence: 'Invented licence',
    retrieved: '2026-11-13',
    sha256: createHash('sha256').update('invented source bytes').digest('hex'),
  };
  const scale = assemble(
    [],
    { present: false, missing: 'test extract absent' },
    { period: input.retrieved },
  ).facts.find((fact) => fact.id === 'break-1')?.chain?.inputs[0];
  if (!scale) throw new Error('release build has no scale input');
  const release = assemble(
    [['8943a1d8b6bffff', 80, 2]],
    { present: false, missing: 'test extract absent' },
    { period: input.retrieved, input: [input, scale] },
  );
  for (const lang of ['en', 'ar'] as const) {
    await open(page, `/${lang}/_look`);
    await page.route(`**/${lang}/_look?**`, async (route) => {
      const response = await route.fetch();
      const html = await response.text();
      const body = html.replace(
        /(<script[^>]*id="eii-release"[^>]*>)([\s\S]*?)(<\/script>)/,
        (_match, before: string, _json: string, after: string) =>
          `${before}${JSON.stringify(release).replace(/</g, '\\u003c')}${after}`,
      );
      await route.fulfill({ response, body });
    });
    await page.reload();
    await page.waitForFunction(
      () =>
        window.__look?.lit === true || (window.__look?.failure ?? '') !== '',
    );
    expect(await page.evaluate(() => window.__look?.failure)).toBe('');
    const facts = await releasedFacts(page);
    for (const id of ['densest-unit', 'break-1']) {
      const fact = facts.find((item) => item.id === id);
      if (!fact?.chain) throw new Error('fixture fact has no source chain');
      const chip = page
        .locator(`button[data-fact="${id}"]`)
        .filter({ visible: true });
      await chip.click();
      const drawer = page.locator('.drawer');
      await drawer.locator('[data-control="source-inputs"]').click();
      for (const [index, source] of fact.chain.inputs.entries()) {
        const sourceNode = drawer
          .locator('[data-row="drawer.source"] .thread-source')
          .filter({ hasText: source.dataset });
        await expect(sourceNode).toBeVisible();
        const inside = judgeInside(await plates(page), SAFE);
        expect(inside.ok, `${lang} source: ${inside.detail}`).toBe(true);
        const links = sourceNode.locator('[data-chip="reference"]');
        await expect(links.filter({ hasText: source.dataset })).toHaveText(
          source.dataset,
        );
        const hash = links.filter({ hasText: source.sha256 });
        await expect(hash).toHaveText(source.sha256);
        if (source.provenance === 'public') {
          for (const text of [source.publisher, source.source, source.licence])
            await expect(links.filter({ hasText: text })).toHaveText(text);
          const date = links.filter({
            hasText: formatDate(source.retrieved, lang),
          });
          await expect(date).toHaveCount(1);
          // Plant a lost source link and prove the rendered chain guard fails.
          await hash.evaluate((node) => node.remove());
          expect(await links.allTextContents()).not.toContain(source.sha256);
        } else {
          await expect(drawer).toContainText(word(source.generator.name, lang));
          await expect(
            links.filter({ hasText: source.generator.version }),
          ).toHaveText(source.generator.version);
        }
        if (index + 1 < fact.chain.inputs.length)
          await drawer
            .locator('[data-control="source-next"]')
            .filter({ visible: true })
            .click();
      }
      await expect(drawer).toContainText(word(fact.chain.method, lang));
      await expect(
        drawer.locator('[data-row="drawer.method"] [data-chip="reference"]'),
      ).toHaveText(fact.chain.method_version);
      expect(judgeNumerals(await numeralItems(page)).ok).toBe(true);
      await page.keyboard.press('Escape');
      await expect(chip).toBeFocused();
    }
    await page.unroute(`**/${lang}/_look?**`);
  }
});
