/**
 * Planted cases of the remote-check browser runner (S3-T20, plan 4.2 F), on
 * the opening fixture only: the built bundle on the actual application. The
 * unplanted pass is the positive control; each case then changes one thing
 * in this test alone, by a route or a document change, and the runner's own
 * observation and decisions must give the reason of that row and leave every
 * other item as the control has it.
 */
import type { Browser, BrowserContext, Route } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { test, expect } from './opening-fixture';
import {
  BASEMAP_SOURCE,
  RESULT_SCHEMA,
  resultDocument,
  resultExact,
  type Item,
  type ItemResult,
  type Language,
  type ResultDocument,
  type Selection,
} from '../remote-check/decide';
import { ADDRESSES, observe } from '../remote-check/observe';

const SELECTION: Selection = {
  activity_query: 'INVENTED-Craft',
  place_query: 'INVENTED-Garden',
};
const PASS: Record<Item, ItemResult> = {
  start_page_en: { status: 200, reason: null },
  start_page_ar: { status: 200, reason: null },
  card: { status: 202, reason: null },
  map_style: { status: 200, reason: null },
  tile: { status: 206, reason: null },
};
const OTHER_ID = 'f_' + '0'.repeat(32);
const CARD = '[data-context-family="night_lights"]';
const CHIP = CARD + ' [data-fact-chip="value"]';
const ARCHIVE = '**/tiles/basemap.pmtiles';
const LINEAGE = '**/api/facts/*/lineage';
const EVENTS = '**/api/answers/*/events';
const TOOL = '**/api/tools/night_lights';
const START = '**/api/playbooks/site_check';

type Cleanup = () => void;
/** A planted change; it may hand back what lets a held request go. */
type Plant = (context: BrowserContext) => Promise<unknown>;
interface Options {
  selection?: Selection;
  addresses?: Readonly<Record<Language, string>>;
}
/** One runner pass in a fresh context, with at most one planted change. */
async function run(
  browser: Browser,
  origin: string,
  plant?: Plant,
  options: Options = {},
): Promise<ResultDocument> {
  const context = await browser.newContext();
  let cleanup: unknown;
  try {
    cleanup = await plant?.(context);
    const page = await context.newPage();
    const seen = await observe(
      page,
      origin,
      options.selection ?? SELECTION,
      options.addresses,
    );
    const result = resultDocument(seen, origin);
    expect(resultExact(result)).toBe(true);
    return result;
  } finally {
    if (typeof cleanup === 'function') (cleanup as Cleanup)();
    await context.close();
  }
}
function changed(items: Partial<Record<Item, ItemResult>>) {
  return { ...PASS, ...items };
}

/** The language of the start page the context is on, by its last document. */
async function pageLanguage(
  context: BrowserContext,
): Promise<() => string | null> {
  let language: string | null = null;
  await context.route(
    (url) => url.pathname === '/',
    (route) => {
      language = new URL(route.request().url()).searchParams.get('lang');
      return route.fallback();
    },
  );
  return () => language;
}
const arabicDocument = (url: URL) =>
  url.pathname === '/' && url.searchParams.get('lang') === 'ar';

/** A document change of one start page, kept as the application renders. */
function inDocument(
  language: Language,
  change: 'remove' | 'attribute' | 'root',
  selector: string,
  name = '',
  value: string | null = null,
): Plant {
  return (context) =>
    context.addInitScript(
      ([language, change, selector, name, value]) => {
        if (!location.search.includes('lang=' + language)) return;
        const apply = () => {
          const nodes =
            change === 'root'
              ? [document.documentElement]
              : [...document.querySelectorAll(selector!)];
          for (const node of nodes)
            if (change === 'remove') node.remove();
            else if (value === null) node.removeAttribute(name!);
            else if (node.getAttribute(name!) !== value)
              node.setAttribute(name!, value);
        };
        new MutationObserver(apply).observe(document, {
          attributes: true,
          childList: true,
          subtree: true,
        });
      },
      [language, change, selector, name, value] as const,
    );
}
/** The answer of the real route with one change of its JSON body. */
function withBody(change: (body: Record<string, unknown>) => void) {
  return async (route: Route) => {
    const response = await route.fetch();
    const body = (await response.json()) as Record<string, unknown>;
    change(body);
    await route.fulfill({ response, json: body });
  };
}
/** Plants one lineage read alone: the first after the card's tool answered. */
function lineagePlant(handler: (route: Route) => Promise<void>): Plant {
  return async (context) => {
    let armed = false;
    context.on('response', (response) => {
      if (new URL(response.url()).pathname === '/api/tools/night_lights')
        armed = true;
    });
    await context.route(LINEAGE, (route) => {
      if (!armed) return route.fallback();
      armed = false;
      return handler(route);
    });
  };
}
/** Wraps the style read of the map handle and touches nothing else. */
function stylePlant(kind: 'source' | 'glyphs' | 'layers'): Plant {
  return (context) =>
    context.addInitScript(
      ([kind, basemap]) => {
        type Style = {
          glyphs?: string;
          sources: Record<string, { url?: string }>;
          layers: { source?: string }[];
        };
        let held: { getStyle(): Style } | undefined;
        const read = (map: { getStyle(): Style }) => () => {
          const style = structuredClone(map.getStyle());
          if (kind === 'source')
            style.sources[basemap!]!.url =
              'pmtiles:///tiles/INVENTED-other.pmtiles';
          if (kind === 'glyphs')
            style.glyphs =
              'https://other-origin.invalid/fonts/{fontstack}/{range}.pbf';
          if (kind === 'layers')
            style.layers = style.layers.filter(
              (layer) => layer.source !== basemap,
            );
          return style;
        };
        Object.defineProperty(globalThis, 'eiiMap', {
          configurable: true,
          set: (map) => {
            held = map;
          },
          get: () =>
            held &&
            new Proxy(held, {
              get(map, key) {
                if (key === 'getStyle') return read(map);
                const value: unknown = Reflect.get(map, key);
                return typeof value === 'function' ? value.bind(map) : value;
              },
            }),
        });
      },
      [kind, BASEMAP_SOURCE] as const,
    );
}

test('control: unplanted pass', async ({ browser, mounted }) => {
  const result = await run(browser, mounted.origin);
  expect(result.schema).toBe(RESULT_SCHEMA);
  expect(result.items).toEqual(PASS);
  expect(result.events_path).not.toBeNull();
  expect(JSON.stringify(result)).not.toContain(new URL(mounted.origin).host);
});

test('start page: no response', async ({ browser, mounted }) => {
  const result = await run(browser, mounted.origin, (context) =>
    context.route(arabicDocument, (route) => route.abort()),
  );
  expect(result.items).toEqual(
    changed({ start_page_ar: { status: null, reason: 'page_no_response' } }),
  );
});

test('start page: status', async ({ browser, mounted }) => {
  const result = await run(browser, mounted.origin, (context) =>
    context.route(arabicDocument, (route) =>
      route.fulfill({ status: 404, contentType: 'text/plain', body: '' }),
    ),
  );
  expect(result.items).toEqual(
    changed({
      start_page_ar: { status: 404, reason: 'page_status_unexpected' },
    }),
  );
});

test('start page: not rendered', async ({ browser, mounted }) => {
  const result = await run(browser, mounted.origin, async (context) => {
    const language = await pageLanguage(context);
    await context.route('**/*', (route) =>
      language() === 'ar' && route.request().resourceType() === 'script'
        ? route.abort()
        : route.fallback(),
    );
  });
  expect(result.items).toEqual(
    changed({ start_page_ar: { status: 200, reason: 'page_not_rendered' } }),
  );
});

test('start page: language', async ({ browser, mounted }) => {
  const expected = changed({
    start_page_ar: { status: 200, reason: 'page_language_mismatch' },
  });
  // Arabic is expected and the English address is requested.
  const requested = await run(browser, mounted.origin, undefined, {
    addresses: { en: ADDRESSES.en, ar: ADDRESSES.en },
  });
  expect(requested.items).toEqual(expected);
  // The Arabic page's root language alone is forced back.
  const forced = await run(
    browser,
    mounted.origin,
    inDocument('ar', 'root', '', 'lang', 'en'),
  );
  expect(forced.items).toEqual(expected);
});

test('start page: direction', async ({ browser, mounted }) => {
  const result = await run(
    browser,
    mounted.origin,
    inDocument('ar', 'root', '', 'dir', 'ltr'),
  );
  expect(result.items).toEqual(
    changed({
      start_page_ar: { status: 200, reason: 'page_direction_mismatch' },
    }),
  );
});

test('card: ui', async ({ browser, mounted }) => {
  const result = await run(
    browser,
    mounted.origin,
    inDocument('en', 'remove', '[data-action="guided-story"]'),
  );
  // The stage and its map start with the page, not behind that control, so
  // the map and tile items still run and are as the control has them.
  expect(result.items).toEqual(
    changed({ card: { status: null, reason: 'card_ui_unavailable' } }),
  );
  expect(result.events_path).toBeNull();
});

test('card: selection', async ({ browser, mounted }) => {
  const result = await run(browser, mounted.origin, undefined, {
    selection: { ...SELECTION, activity_query: 'INVENTED-no-such-activity' },
  });
  expect(result.items).toEqual(
    changed({ card: { status: null, reason: 'card_selection_unresolved' } }),
  );
});

test('card: playbook', async ({ browser, mounted }) => {
  const limited = await run(browser, mounted.origin, (context) =>
    context.route(START, (route) => route.fulfill({ status: 429, json: {} })),
  );
  expect(limited.items).toEqual(
    changed({ card: { status: 429, reason: 'card_playbook_refused' } }),
  );
  expect(limited.events_path).toBeNull();
  const other = await run(browser, mounted.origin, (context) =>
    context.route(START, (route) =>
      route.fulfill({ status: 202, json: { answer_id: 'abc-def' } }),
    ),
  );
  expect(other.items).toEqual(
    changed({ card: { status: 202, reason: 'card_playbook_refused' } }),
  );
  expect(other.events_path).toBeNull();
});

test('card: stream', async ({ browser, mounted }) => {
  const expected = changed({
    card: { status: 202, reason: 'card_stream_refused' },
  });
  const absent = await run(browser, mounted.origin, (context) =>
    context.route(EVENTS, (route) => route.fulfill({ status: 404, json: {} })),
  );
  expect(absent.items).toEqual(expected);
  expect(absent.events_path).not.toBeNull();
  const typed = await run(browser, mounted.origin, (context) =>
    context.route(EVENTS, async (route) => {
      const response = await route.fetch();
      await route.fulfill({ response, contentType: 'text/plain' });
    }),
  );
  expect(typed.items).toEqual(expected);
});

test('card: tool', async ({ browser, mounted }) => {
  const expected = changed({
    card: { status: 202, reason: 'card_tool_refused' },
  });
  const absent = await run(browser, mounted.origin, (context) =>
    context.route(TOOL, (route) => route.fulfill({ status: 404, json: {} })),
  );
  expect(absent.items).toEqual(expected);
  const named = await run(browser, mounted.origin, (context) =>
    context.route(
      TOOL,
      withBody((body) => {
        body.tool = 'population_age_sex';
      }),
    ),
  );
  expect(named.items).toEqual(expected);
});

test('card: no data', async ({ browser, mounted }) => {
  const result = await run(browser, mounted.origin, (context) =>
    context.route(EVENTS, async (route) => {
      const response = await route.fetch();
      const text = (await response.text()).replace(/\r\n/g, '\n');
      const blocks = text.split('\n\n').map((block) => {
        if (!block.split('\n').includes('event: evidence')) return block;
        return block
          .split('\n')
          .map((line) => {
            if (!line.startsWith('data: ')) return line;
            const data = JSON.parse(line.slice(6)) as Record<string, unknown>;
            if (data.kind === 'night_lights') data.fact_ids = [];
            return 'data: ' + JSON.stringify(data);
          })
          .join('\n');
      });
      await route.fulfill({ response, body: blocks.join('\n\n') });
    }),
  );
  expect(result.items).toEqual(
    changed({ card: { status: 202, reason: 'card_no_data' } }),
  );
});

test('card: lineage unanswered', async ({ browser, mounted }) => {
  const expected = changed({
    card: { status: 202, reason: 'card_lineage_unanswered' },
  });
  const absent = await run(
    browser,
    mounted.origin,
    lineagePlant((route) => route.fulfill({ status: 404, json: {} })),
  );
  expect(absent.items).toEqual(expected);
  // The lineage route never answers; the held request is let go afterwards.
  let release: Cleanup = () => undefined;
  const silent = await run(browser, mounted.origin, async (context) => {
    await lineagePlant(
      () =>
        new Promise<void>((resolve) => {
          release = resolve;
        }),
    )(context);
    return () => release();
  });
  expect(silent.items).toEqual(expected);
});

test('card: lineage mismatch', async ({ browser, mounted }) => {
  const plants: ((body: Record<string, unknown>) => void)[] = [
    (body) => {
      body.fact_id = OTHER_ID;
    },
    (body) => {
      delete (body.lineage as Record<string, unknown>).method;
    },
    (body) => {
      delete (body.sources as Record<string, unknown>[])[0]!.sha256;
    },
  ];
  for (const plant of plants) {
    const result = await run(
      browser,
      mounted.origin,
      lineagePlant(withBody(plant)),
    );
    expect(result.items).toEqual(
      changed({ card: { status: 202, reason: 'card_lineage_mismatch' } }),
    );
  }
});

test('card: missing', async ({ browser, mounted }) => {
  const result = await run(
    browser,
    mounted.origin,
    inDocument('en', 'remove', CARD),
  );
  expect(result.items).toEqual(
    changed({ card: { status: 202, reason: 'card_missing' } }),
  );
});

test('card: chip missing', async ({ browser, mounted }) => {
  const result = await run(
    browser,
    mounted.origin,
    inDocument('en', 'remove', CHIP),
  );
  expect(result.items).toEqual(
    changed({ card: { status: 202, reason: 'card_fact_chip_missing' } }),
  );
});

test('card: chip binding', async ({ browser, mounted }) => {
  const expected = changed({
    card: { status: 202, reason: 'card_fact_binding_mismatch' },
  });
  const rewritten = await run(
    browser,
    mounted.origin,
    inDocument('en', 'attribute', CHIP, 'data-fact-id', OTHER_ID),
  );
  expect(rewritten.items).toEqual(expected);
  const removed = await run(
    browser,
    mounted.origin,
    inDocument('en', 'attribute', CHIP, 'data-fact-id', null),
  );
  expect(removed.items).toEqual(expected);
});

test('map: handle', async ({ browser, mounted }) => {
  const result = await run(browser, mounted.origin, (context) =>
    context.addInitScript(() => {
      Object.defineProperty(globalThis, 'eiiMap', {
        configurable: true,
        get: () => undefined,
        set: () => undefined,
      });
    }),
  );
  // Rendered features are read through the same handle: without it the tile
  // was answered and cannot be seen rendered.
  expect(result.items).toEqual(
    changed({
      map_style: { status: 200, reason: 'map_unavailable' },
      tile: { status: 206, reason: 'tile_not_rendered' },
    }),
  );
});

test('map: release', async ({ browser, mounted }) => {
  // The English page's second release read, the one of its layer, answers
  // 503. Its first supplies the basemap address and is left as it is: a 503
  // there replaces the whole page, which is the start page's own failure.
  const result = await run(browser, mounted.origin, async (context) => {
    const language = await pageLanguage(context);
    let reads = 0;
    await context.route('**/api/release', (route) => {
      if (language() !== 'en') return route.fallback();
      reads += 1;
      return reads === 2
        ? route.fulfill({ status: 503, json: {} })
        : route.fallback();
    });
  });
  expect(result.items).toEqual(
    changed({ map_style: { status: 503, reason: 'release_unanswered' } }),
  );
});

test('map: source', async ({ browser, mounted }) => {
  const result = await run(browser, mounted.origin, stylePlant('source'));
  expect(result.items).toEqual(
    changed({ map_style: { status: 200, reason: 'style_source_mismatch' } }),
  );
});

test('map: glyphs', async ({ browser, mounted }) => {
  const result = await run(browser, mounted.origin, stylePlant('glyphs'));
  expect(result.items).toEqual(
    changed({ map_style: { status: 200, reason: 'style_glyphs_mismatch' } }),
  );
});

test('map: layers', async ({ browser, mounted }) => {
  const result = await run(browser, mounted.origin, stylePlant('layers'));
  expect(result.items).toEqual(
    changed({ map_style: { status: 200, reason: 'style_layers_missing' } }),
  );
});

test('tile: no response', async ({ browser, mounted }) => {
  const result = await run(browser, mounted.origin, (context) =>
    context.route(ARCHIVE, (route) => route.abort()),
  );
  expect(result.items).toEqual(
    changed({ tile: { status: null, reason: 'tile_no_range_response' } }),
  );
});

test('tile: status', async ({ browser, mounted }) => {
  const result = await run(browser, mounted.origin, (context) =>
    context.route(ARCHIVE, async (route) => {
      const response = await route.fetch();
      await route.fulfill({ response, status: 200 });
    }),
  );
  expect(result.items).toEqual(
    changed({ tile: { status: 200, reason: 'tile_status_unexpected' } }),
  );
});

test('tile: not rendered', async ({ browser, mounted }) => {
  const result = await run(browser, mounted.origin, (context) =>
    context.route(ARCHIVE, async (route) => {
      const response = await route.fetch();
      const zeros = Buffer.alloc((await response.body()).length);
      await route.fulfill({ response, body: zeros });
    }),
  );
  expect(result.items).toEqual(
    changed({ tile: { status: 206, reason: 'tile_not_rendered' } }),
  );
});

/** The production runner itself, as the command starts it. */
function startRunner(origin: string, result: string, tmp?: string) {
  const held = tmp ?? process.env.TMPDIR;
  return spawnSync(
    process.execPath,
    [
      'node_modules/playwright/cli.js',
      'test',
      '--config',
      'playwright.remote-check.config.ts',
    ],
    {
      cwd: process.cwd(),
      encoding: 'utf8',
      timeout: 120_000,
      env: {
        PATH: process.env.PATH ?? '',
        HOME: process.env.HOME ?? '',
        ...(held ? { TMPDIR: held } : {}),
        PLAYWRIGHT_BROWSERS_PATH: process.env.PLAYWRIGHT_BROWSERS_PATH ?? '',
        EII_REMOTE_CHECK_ORIGIN: origin,
        EII_REMOTE_CHECK_RESULT: result,
      },
    },
  );
}

test('runner: writes the closed result file once', async ({ mounted }) => {
  // Against the fixture origin. The tracked selection names no label, so
  // the card item reports the unresolved selection; the other four pass.
  const folder = path.join(mounted.work, 'remote-check');
  mkdirSync(folder);
  const target = path.join(folder, 'result.json');
  const child = startRunner(mounted.origin, target);
  expect(child.status, child.stdout + child.stderr).toBe(0);
  const text = readFileSync(target, 'utf8');
  expect(text).not.toContain(new URL(mounted.origin).host);
  const written: unknown = JSON.parse(text);
  expect(resultExact(written)).toBe(true);
  expect(written).toEqual({
    schema: RESULT_SCHEMA,
    items: changed({
      card: { status: null, reason: 'card_selection_unresolved' },
    }),
    events_path: null,
  });
  // Written once: a second run on the same path fails and leaves the file.
  expect(startRunner(mounted.origin, target).status).not.toBe(0);
  expect(readFileSync(target, 'utf8')).toBe(text);
});

test('runner: refuses its environment before any page', async ({ mounted }) => {
  // One input changed in each case; no result file is written by any.
  const folder = path.join(mounted.work, 'remote-check-refused');
  mkdirSync(folder);
  const target = path.join(folder, 'result.json');
  const cases: [string, string][] = [
    [mounted.origin + '/x', target],
    ['remote-check.invalid', target],
    [mounted.origin, 'remote-check-refused-result.json'],
  ];
  for (const [origin, result] of cases) {
    const child = startRunner(origin, result, folder);
    expect(child.status).not.toBe(0);
    expect(child.stdout + child.stderr).toContain('remote_check_environment');
    expect(existsSync(result)).toBe(false);
  }
});
