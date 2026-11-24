/**
 * Page driving of the remote-check browser runner (S3-T20). It opens the two
 * start pages, drives the mounted application's own controls, listens to that
 * page's responses and reads its document. It sends no request of its own,
 * sets no cookie and adds no route or page hook.
 */
import type { Page, Response } from '@playwright/test';
import {
  BASEMAP_SOURCE,
  STEP_MS,
  type Answer,
  type CardSeen,
  type Language,
  type Observed,
  type PageSeen,
  type Selection,
  type StyleSeen,
  type TileSeen,
} from './decide';

export const ADDRESSES: Readonly<Record<Language, string>> = {
  en: '/?lang=en&theme=dark',
  ar: '/?lang=ar&theme=dark',
};
const WITHIN = { timeout: STEP_MS } as const;
const CARD = '[data-context-family="night_lights"]';
const LINEAGE = /^\/api\/facts\/([^/]+)\/lineage$/;
const EVENTS = /^\/api\/answers\/[^/]+\/events$/;

/** Whether one bounded step completed. */
async function done(step: Promise<unknown>): Promise<boolean> {
  try {
    await step;
    return true;
  } catch {
    return false;
  }
}

async function openPage(
  page: Page,
  address: string,
  language: Language,
): Promise<PageSeen> {
  const seen: PageSeen = {
    status: null,
    rendered: false,
    lang: null,
    dir: null,
  };
  try {
    seen.status = (await page.goto(address, WITHIN))?.status() ?? null;
  } catch {
    return seen;
  }
  seen.rendered = await done(
    page.locator('[data-scene="opening"]').waitFor(WITHIN),
  );
  if (!seen.rendered) return seen;
  const direction = language === 'ar' ? 'rtl' : 'ltr';
  await done(
    page
      .locator(`html[lang="${language}"][dir="${direction}"]`)
      .waitFor({ state: 'attached', ...WITHIN }),
  );
  const root = page.locator('html');
  seen.lang = await root.getAttribute('lang', WITHIN);
  seen.dir = await root.getAttribute('dir', WITHIN);
  return seen;
}

interface Heard {
  release: Answer[];
  start: Answer | null;
  events: CardSeen['events'];
  tool: Answer | null;
  lineage: Map<string, Answer | null>;
  ranged: TileSeen['ranged'][number][];
}
async function parsed(response: Response): Promise<unknown> {
  try {
    return JSON.parse(await response.text());
  } catch {
    return undefined;
  }
}
async function hear(heard: Heard, response: Response): Promise<void> {
  const request = response.request();
  const path = new URL(response.url()).pathname;
  const status = response.status();
  const lineage = LINEAGE.exec(path)?.[1];
  if (request.headers()['range'] !== undefined)
    heard.ranged.push({ path, status });
  else if (path === '/api/release')
    heard.release.push({ status, body: await parsed(response) });
  else if (path === '/api/playbooks/site_check')
    heard.start ??= { status, body: await parsed(response) };
  else if (path === '/api/tools/night_lights')
    heard.tool ??= { status, body: await parsed(response) };
  else if (lineage !== undefined)
    heard.lineage.set(lineage, { status, body: await parsed(response) });
  else if (EVENTS.test(path)) {
    const contentType = response.headers()['content-type'] ?? null;
    const body = await response.text().catch(() => undefined);
    heard.events ??= { status, contentType, body };
  }
}
/** Listens to the page's own same-origin responses from now on. */
function listen(page: Page, origin: string) {
  const heard: Heard = {
    release: [],
    start: null,
    events: null,
    tool: null,
    lineage: new Map(),
    ranged: [],
  };
  const pending: Promise<void>[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    const id = LINEAGE.exec(url.pathname)?.[1];
    if (url.origin === origin && id !== undefined && !heard.lineage.has(id))
      heard.lineage.set(id, null);
  });
  page.on('response', (response) => {
    if (new URL(response.url()).origin === origin)
      pending.push(hear(heard, response));
  });
  /** Bodies still being read get one more bounded step, then are left out. */
  const settled = async () => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    await Promise.race([
      Promise.allSettled(pending),
      new Promise((resolve) => {
        timer = setTimeout(resolve, STEP_MS);
      }),
    ]);
    clearTimeout(timer);
    return heard;
  };
  return { settled };
}

/** Leaves the opening scene by the page's own guided-story control. */
function startStory(page: Page): Promise<void> {
  return page.locator('[data-action="guided-story"]').click(WITHIN);
}
function stageReady(page: Page): Promise<void> {
  return page.locator('.stage[data-state="ready"]').waitFor(WITHIN);
}
/** The running style through the handle the map tests use, or null. */
async function readStyle(page: Page): Promise<StyleSeen | null> {
  const held = await done(
    page.waitForFunction(
      () => (globalThis as { eiiMap?: unknown }).eiiMap !== undefined,
      undefined,
      WITHIN,
    ),
  );
  if (!held) return null;
  return page
    .evaluate(() => {
      const style = (
        globalThis as unknown as {
          eiiMap: {
            getStyle(): {
              glyphs?: unknown;
              sources: Record<string, { url?: unknown }>;
              layers: { source?: unknown }[];
            };
          };
        }
      ).eiiMap.getStyle();
      return {
        glyphs: style.glyphs ?? null,
        sources: Object.entries(style.sources).map(([id, source]) => ({
          id,
          url: source.url ?? null,
        })),
        layers: style.layers.map((layer) => layer.source ?? null),
      };
    })
    .catch(() => null);
}
function basemapRendered(page: Page): Promise<boolean> {
  return done(
    page.waitForFunction(
      (source) =>
        (
          globalThis as unknown as {
            eiiMap?: { queryRenderedFeatures(): { source: string }[] };
          }
        ).eiiMap
          ?.queryRenderedFeatures()
          .some((feature) => feature.source === source) ?? false,
      BASEMAP_SOURCE,
      { polling: 250, ...WITHIN },
    ),
  );
}

async function pick(page: Page, picker: string, query: string): Promise<void> {
  const box = page.locator(`[data-picker="${picker}"]`);
  await box.locator('input').fill(query, WITHIN);
  await box.locator('button[type="submit"]').click(WITHIN);
  await box.locator('[data-candidate]').first().click(WITHIN);
}
async function runStory(page: Page): Promise<void> {
  await page.locator('[data-place-preset="walk-a"]').click(WITHIN);
  await page.locator('[data-action="story-next"]').click(WITHIN);
}
/** Drives the card on the open English page; the listener holds the rest. */
async function driveCard(
  page: Page,
  started: boolean,
  selection: Selection,
): Promise<Pick<CardSeen, 'ui' | 'selected' | 'card' | 'chips'>> {
  const seen = { ui: started, selected: false, card: false, chips: [] };
  const { activity_query: activity, place_query: place } = selection;
  if (!started || activity === null || place === null) return seen;
  if (
    !(await done(pick(page, 'activity', activity))) ||
    !(await done(pick(page, 'place', place)))
  )
    return seen;
  if (!(await done(runStory(page)))) return { ...seen, ui: false };
  const card = page.locator(CARD);
  if (!(await done(card.first().waitFor(WITHIN))))
    return { ...seen, selected: true };
  const chips = card.locator('[data-fact-chip="value"]');
  await done(chips.first().waitFor(WITHIN));
  return {
    ui: true,
    selected: true,
    card: true,
    chips: await chips.evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute('data-fact-id')),
    ),
  };
}

/**
 * One pass over the five browser items in the page's own context: the Arabic
 * start page in a tab of its own, so that a navigation that fails there
 * cannot disturb the next, then the English start page with its map, tile
 * and card.
 */
export async function observe(
  page: Page,
  origin: string,
  selection: Selection,
  addresses: Readonly<Record<Language, string>> = ADDRESSES,
): Promise<Observed> {
  const tab = await page.context().newPage();
  const arabic = await openPage(tab, origin + addresses.ar, 'ar');
  await tab.close();
  const listener = listen(page, origin);
  const english = await openPage(page, origin + addresses.en, 'en');
  const started = english.rendered && (await done(startStory(page)));
  const staged = english.rendered && (await done(stageReady(page)));
  const style = staged ? await readStyle(page) : null;
  const rendered = style !== null && (await basemapRendered(page));
  const driven = await driveCard(page, started, selection);
  const heard = await listener.settled();
  return {
    start_page_en: english,
    start_page_ar: arabic,
    card: {
      ...driven,
      start: heard.start,
      events: heard.events,
      tool: heard.tool,
      lineage: heard.lineage,
    },
    map: { release: heard.release, style },
    tile: { ranged: heard.ranged, rendered },
  };
}
