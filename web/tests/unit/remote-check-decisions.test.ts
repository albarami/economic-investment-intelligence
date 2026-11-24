/**
 * Decisions of the remote-check browser runner (S3-T20, plan 4.2 F, 4.3 and
 * 4.4 as amended by R3-F2). Every payload is invented. The hostile-leaf
 * matrix feeds each mutated payload to the page's own reader first, so the
 * card observation is the one the mounted page would give.
 */
import { readFileSync } from 'node:fs';
import { afterEach, describe, expect, it, vi } from 'vitest';
import codes from '../../src/api/reason-codes.generated.json' with { type: 'json' };
import { runPublicStory } from '../../src/api/public-opening';
import { catalogue } from '../../src/brief/catalogue';
import { GLYPH_TEMPLATE, extractStyle } from '../../src/stage/basemap';
import { tableWire } from '../fixtures/facts';
import { contextInput } from '../fixtures/public-context';
import {
  BASEMAP_SOURCE,
  ITEM_REASONS,
  RESULT_SCHEMA,
  STEP_MS,
  decideCard,
  decideMapStyle,
  decideStartPage,
  decideTile,
  readSelection,
  resultDocument,
  resultExact,
  type Answer,
  type CardSeen,
  type MapSeen,
  type Observed,
  type PageSeen,
  type TileSeen,
} from '../remote-check/decide';

const ORIGIN = 'https://remote-check.invalid';
const ARCHIVE = '/tiles/basemap.pmtiles';
const EVENTS = '/api/answers/abc-def/events';
type Json = Record<string, unknown>;
type Frame = { kind: string; data: unknown };
interface Wire {
  start: Json;
  frames: Frame[];
  tool: Json;
  lineage: Json;
}

afterEach(() => vi.unstubAllGlobals());

/** The invented payloads of one accepted story, as the page receives them. */
function wire(): Wire {
  const input = contextInput();
  const held = input.facts[0]!;
  const fact = held.fact;
  const frames: Frame[] = [
    {
      kind: 'stage',
      data: {
        directive: 'fly',
        target: { area_id: 'INVENTED-area' },
        zoom: 'street',
      },
    },
    {
      kind: 'stage',
      data: {
        directive: 'rings',
        area_ids: ['INVENTED-area', 'INVENTED-wider'],
      },
    },
    {
      kind: 'evidence',
      data: {
        kind: 'night_lights',
        facts: [fact],
        fact_ids: [fact.fact_id],
        area_id: 'INVENTED-area',
      },
    },
    {
      kind: 'receipt',
      data: {
        'Checked before display': {
          Sources: true,
          Assumptions: true,
          'Nothing invented': true,
          Scope: true,
          'Limits stated': true,
        },
        egress: [],
      },
    },
    { kind: 'status', data: { writer: 'template' } },
    {
      kind: 'done',
      data: {
        brief: {
          catalogue_version: catalogue.version,
          headline_key: 'foundation_headline',
          decision_template_key: 'foundation_decision',
        },
      },
    },
  ];
  return {
    start: { answer_id: 'abc-def', events_url: EVENTS },
    frames,
    tool: { tool: 'night_lights', status: 'OK', facts: [fact] },
    lineage: {
      fact_id: fact.fact_id,
      release_id: fact.release_id,
      lineage: tableWire(
        input.lineages.find((row) => row.lineageId === fact.lineage_ref)!,
      ),
      sources: input.sources,
      binding: {
        metricKey: held.metricKey,
        presentation: held.presentation,
        qualifiers: held.qualifiers ?? {},
      },
    },
  };
}
const FACT = (wire().tool.facts as Json[])[0]!;
const ID = FACT.fact_id as string;
const LINEAGE_PATH = '/api/facts/' + ID + '/lineage';
function releaseBody(): Json {
  const input = contextInput();
  return {
    release_id: FACT.release_id,
    release_kind: 'public_only',
    rules_version_id: 'INVENTED-rules',
    tables: input.tables,
    artefacts: input.artefacts,
    hour_keys: [],
    day_keys: [],
    month_keys: [],
    basemap_url: ARCHIVE,
  };
}
function streamText(frames: readonly Frame[]): string {
  return frames
    .map(
      (frame) =>
        `event: ${frame.kind}\ndata: ${JSON.stringify(frame.data)}\n\n`,
    )
    .join('');
}

/**
 * What the runner observes when the page's own reader receives these
 * payloads: the answers the page asked for, and the card it accepted.
 */
async function pageSees(sent: Wire): Promise<CardSeen> {
  const bodies: Record<string, string> = {
    '/api/playbooks/site_check': JSON.stringify(sent.start),
    [EVENTS]: streamText(sent.frames),
    '/api/tools/night_lights': JSON.stringify(sent.tool),
    '/api/release': JSON.stringify(releaseBody()),
    [LINEAGE_PATH]: JSON.stringify(sent.lineage),
  };
  const asked = new Set<string>();
  vi.stubGlobal('fetch', async (path: string) => {
    const body = bodies[path];
    if (body === undefined) throw new Error('unexpected_fixture_route');
    asked.add(path);
    return new Response(body, {
      status: path === '/api/playbooks/site_check' ? 202 : 200,
    });
  });
  const cards = await runPublicStory('INVENTED-activity', 'en', {
    shape_id: 'INVENTED-shape',
  }).then(
    (answer) => answer.cards,
    () => [],
  );
  const answer = (path: string, status = 200): Answer | null =>
    asked.has(path)
      ? {
          status,
          body: path === EVENTS ? bodies[path] : JSON.parse(bodies[path]!),
        }
      : null;
  const events = answer(EVENTS);
  return {
    ui: true,
    selected: true,
    start: answer('/api/playbooks/site_check', 202),
    events: events && {
      ...events,
      contentType: 'text/event-stream; charset=utf-8',
    },
    tool: answer('/api/tools/night_lights'),
    lineage: new Map(
      asked.has(LINEAGE_PATH) ? [[ID, answer(LINEAGE_PATH)]] : [],
    ),
    card: cards.length > 0,
    chips: cards.flatMap((card) =>
      card.state === 'ready' ? [card.factId] : [],
    ),
  };
}

const HOSTILE: readonly unknown[] = [{ toString: null }, 7, null, []];
type Path = (string | number)[];
/** Every leaf of a JSON value: a scalar, null or an empty container. */
function leafPaths(value: unknown, at: Path = []): Path[] {
  if (value !== null && typeof value === 'object') {
    const entries = Object.entries(value);
    if (entries.length > 0)
      return entries.flatMap(([key, held]) =>
        leafPaths(held, [...at, Array.isArray(value) ? Number(key) : key]),
      );
  }
  return [at];
}
function replaced<T>(value: T, path: Path, leaf: unknown): T {
  const copy = structuredClone(value);
  let node = copy as unknown as Record<string | number, unknown>;
  for (const key of path.slice(0, -1))
    node = node[key] as Record<string | number, unknown>;
  node[path.at(-1)!] = structuredClone(leaf);
  return copy;
}
const label = (path: Path, index: number) => `${path.join('.')}#${index}`;

const PASS_CARD = { result: { status: 202, reason: null }, eventsPath: EVENTS };

describe('remote-check card decision with the page reader', () => {
  it('passes the unchanged payloads', async () => {
    expect(decideCard(await pageSees(wire()))).toEqual(PASS_CARD);
  });

  it('gives every hostile start-body leaf the playbook reason', async () => {
    const paths = leafPaths(wire().start);
    expect(paths.map((path) => path.join('.'))).toEqual([
      'answer_id',
      'events_url',
    ]);
    for (const path of paths)
      for (const leaf of HOSTILE) {
        const sent = wire();
        sent.start = replaced(sent.start, path, leaf);
        expect(decideCard(await pageSees(sent)), path.join('.')).toEqual({
          result: { status: 202, reason: 'card_playbook_refused' },
          eventsPath: null,
        });
      }
  });

  it('gives every hostile evidence fact id the no-data reason', async () => {
    const at = wire().frames.findIndex((frame) => frame.kind === 'evidence');
    const ids = (wire().frames[at]!.data as Json).fact_ids;
    const paths = leafPaths(ids, [at, 'data', 'fact_ids']);
    expect(paths).toHaveLength(1);
    for (const path of paths)
      for (const leaf of HOSTILE) {
        const sent = wire();
        sent.frames = replaced(sent.frames, path, leaf);
        expect(decideCard(await pageSees(sent)).result.reason).toBe(
          'card_no_data',
        );
      }
  });

  /**
   * Each expected result follows the field's own domain and its reader: a
   * leaf the runner reads ends in the runner's own reason; a substitution
   * inside the field's domain keeps the valid behaviour; any other leaf is
   * refused by the page's own reader, and the card is missing.
   */
  async function matrix(
    part: 'tool' | 'lineage',
    root: Path,
    expected: (path: Path, index: number) => string | null,
  ): Promise<number> {
    const base = root.reduce<unknown>(
      (node, key) => (node as Json)[key],
      wire()[part],
    );
    const paths = leafPaths(base, root);
    for (const path of paths)
      for (const [index, leaf] of HOSTILE.entries()) {
        const sent = wire();
        sent[part] = replaced(sent[part], path, leaf);
        expect(decideCard(await pageSees(sent)), label(path, index)).toEqual({
          result: { status: 202, reason: expected(path, index) },
          eventsPath: EVENTS,
        });
      }
    return paths.length * HOSTILE.length;
  }

  it('follows each tool fact leaf by its field domain', async () => {
    // Pinned valid substitutions: a fact value may be an integer or null.
    const valid = ['facts.0.value#1', 'facts.0.value#2'];
    const cases = await matrix('tool', ['facts'], (path, index) =>
      valid.includes(label(path, index)) ? null : 'card_tool_refused',
    );
    expect(HOSTILE[1]).toBe(7);
    expect(HOSTILE[2]).toBeNull();
    expect(cases).toBe(64);
  });

  it('follows each lineage leaf by its field and reader', async () => {
    const read = ['fact_id', 'lineage.method', 'lineage.methodVersion'];
    const named = ['sha256', 'publisher', 'licenceOrTerms'];
    const cases = await matrix('lineage', [], (path) =>
      read.includes(path.join('.')) ||
      (path[0] === 'sources' && named.includes(String(path.at(-1))))
        ? 'card_lineage_mismatch'
        : 'card_missing',
    );
    expect(cases).toBe(80);
  });
});

function lineageAnswer(): Answer {
  return { status: 200, body: wire().lineage };
}
/** A complete passing observation of the five items. */
function observed(): Observed {
  const page = (lang: string, dir: string): PageSeen => ({
    status: 200,
    rendered: true,
    lang,
    dir,
  });
  return {
    start_page_en: page('en', 'ltr'),
    start_page_ar: page('ar', 'rtl'),
    card: {
      ui: true,
      selected: true,
      start: { status: 202, body: wire().start },
      events: {
        status: 200,
        contentType: 'text/event-stream; charset=utf-8',
        body: streamText(wire().frames),
      },
      tool: { status: 200, body: wire().tool },
      lineage: new Map([[ID, lineageAnswer()]]),
      card: true,
      chips: [ID],
    },
    map: {
      release: [{ status: 200, body: releaseBody() }],
      style: {
        glyphs: ORIGIN + GLYPH_TEMPLATE,
        sources: [{ id: BASEMAP_SOURCE, url: 'pmtiles://' + ARCHIVE }],
        layers: [BASEMAP_SOURCE, BASEMAP_SOURCE],
      },
    },
    tile: { ranged: [{ path: ARCHIVE, status: 206 }], rendered: true },
  };
}
const OTHER_ID = 'f_' + '0'.repeat(32);

describe('remote-check start page decision', () => {
  const seen = observed().start_page_ar;
  it.each<[string, Partial<PageSeen>, number | null]>([
    ['page_no_response', { status: null }, null],
    ['page_status_unexpected', { status: 404 }, 404],
    ['page_not_rendered', { rendered: false }, 200],
    ['page_language_mismatch', { lang: 'en' }, 200],
    ['page_direction_mismatch', { dir: 'ltr' }, 200],
  ])('decides %s on its one changed observation', (reason, change, status) => {
    expect(decideStartPage(seen, 'ar')).toEqual({ status: 200, reason: null });
    expect(decideStartPage({ ...seen, ...change }, 'ar')).toEqual({
      status,
      reason,
    });
  });
  it('decides in the fixed order when every observation is wrong', () => {
    const wrong: PageSeen = {
      status: 404,
      rendered: false,
      lang: 'en',
      dir: 'ltr',
    };
    expect(decideStartPage(wrong, 'ar').reason).toBe('page_status_unexpected');
    expect(decideStartPage({ ...wrong, status: 200 }, 'ar').reason).toBe(
      'page_not_rendered',
    );
    expect(
      decideStartPage({ ...wrong, status: 200, rendered: true }, 'ar').reason,
    ).toBe('page_language_mismatch');
    expect(decideStartPage(observed().start_page_en, 'en').reason).toBeNull();
    expect(decideStartPage(observed().start_page_ar, 'en').reason).toBe(
      'page_language_mismatch',
    );
  });
});

describe('remote-check card decision', () => {
  const body = (answer: Answer, change: Json): Answer => ({
    status: answer.status,
    body: { ...(answer.body as Json), ...change },
  });
  const lineage = (change: Json, status = 200): CardSeen['lineage'] =>
    new Map([[ID, { status, body: { ...wire().lineage, ...change } }]]);
  const source = (change: Json) =>
    lineage({
      sources: (wire().lineage.sources as Json[]).map((row) => ({
        ...row,
        ...change,
      })),
    });
  const framesWith = (ids: unknown): CardSeen['events'] => ({
    ...observed().card.events!,
    body: streamText(
      wire().frames.map((frame) =>
        frame.kind === 'evidence'
          ? {
              kind: frame.kind,
              data: { ...(frame.data as Json), fact_ids: ids },
            }
          : frame,
      ),
    ),
  });
  const card = observed().card;
  const fact = (change: Json): Partial<CardSeen> => ({
    tool: body(card.tool!, { facts: [{ ...FACT, ...change }] }),
  });
  const geography = (change: Json) =>
    fact({ geography: { ...(FACT.geography as Json), ...change } });
  /** Another evidence kind names the fact first; night lights names none. */
  const otherKindFirst = (): CardSeen['events'] => ({
    ...card.events!,
    body: streamText(
      wire().frames.flatMap((frame) =>
        frame.kind === 'evidence'
          ? [
              {
                kind: frame.kind,
                data: { ...(frame.data as Json), kind: 'population_age_sex' },
              },
              {
                kind: frame.kind,
                data: { ...(frame.data as Json), fact_ids: [] },
              },
            ]
          : [frame],
      ),
    ),
  });
  it.each<[string, string, Partial<CardSeen>, number | null]>([
    ['card_ui_unavailable', 'no control', { ui: false }, 202],
    ['card_selection_unresolved', 'no candidate', { selected: false }, 202],
    ['card_playbook_refused', 'no start', { start: null }, null],
    [
      'card_playbook_refused',
      'status',
      { start: { ...card.start!, status: 429 } },
      429,
    ],
    [
      'card_playbook_refused',
      'status 200',
      { start: { ...card.start!, status: 200 } },
      200,
    ],
    [
      'card_playbook_refused',
      'another body',
      { start: body(card.start!, { extra: 'x' }) },
      202,
    ],
    [
      'card_playbook_refused',
      'not an object',
      { start: { status: 202, body: null } },
      202,
    ],
    ['card_stream_refused', 'no stream', { events: null }, 202],
    [
      'card_stream_refused',
      'status',
      { events: { ...card.events!, status: 404 } },
      202,
    ],
    [
      'card_stream_refused',
      'type',
      { events: { ...card.events!, contentType: 'text/plain' } },
      202,
    ],
    [
      'card_stream_refused',
      'no type',
      { events: { ...card.events!, contentType: null } },
      202,
    ],
    [
      'card_stream_refused',
      'unread body',
      { events: { ...card.events!, body: undefined } },
      202,
    ],
    [
      'card_stream_refused',
      'cut short',
      { events: { ...card.events!, body: 'event: stage\n' } },
      202,
    ],
    [
      'card_tool_refused',
      'status',
      { tool: { ...card.tool!, status: 404 } },
      202,
    ],
    [
      'card_tool_refused',
      'another tool',
      { tool: body(card.tool!, { tool: 'population_age_sex' }) },
      202,
    ],
    [
      'card_tool_refused',
      'not OK',
      { tool: body(card.tool!, { status: 'NO_DATA' }) },
      202,
    ],
    [
      'card_tool_refused',
      'not an object',
      { tool: { status: 200, body: [] } },
      202,
    ],
    ['card_no_data', 'no fact id', { events: framesWith([]) }, 202],
    ['card_no_data', 'no id list', { events: framesWith(null) }, 202],
    ['card_no_data', 'malformed id', { events: framesWith(['f_7']) }, 202],
    ['card_no_data', 'ids of another kind', { events: otherKindFirst() }, 202],
    ['card_tool_refused', 'no tool answer', { tool: null }, 202],
    ['card_tool_refused', 'a fact key added', fact({ extra: 'x' }), 202],
    ['card_tool_refused', 'no geography', fact({ geography: null }), 202],
    [
      'card_tool_refused',
      'unit ids that are no words',
      geography({ unit_ids: [7] }),
      202,
    ],
    [
      'card_tool_refused',
      'a geography key added',
      geography({ other: 'x' }),
      202,
    ],
    ['card_tool_refused', 'no coverage list', fact({ coverage_keys: 7 }), 202],
    ['card_tool_refused', 'no caveat list', fact({ caveat_keys: null }), 202],
    [
      'card_tool_refused',
      'no fact list',
      { tool: body(card.tool!, { facts: null }) },
      202,
    ],
    [
      'card_tool_refused',
      'other facts',
      { tool: body(card.tool!, { facts: [] }) },
      202,
    ],
    [
      'card_tool_refused',
      'unnamed fact',
      { tool: body(card.tool!, { facts: [7] }) },
      202,
    ],
    ['card_lineage_unanswered', 'status', { lineage: lineage({}, 404) }, 202],
    [
      'card_lineage_unanswered',
      'never answered',
      { lineage: new Map([[ID, null]]) },
      202,
    ],
    ['card_lineage_unanswered', 'never asked', { lineage: new Map() }, 202],
    [
      'card_lineage_mismatch',
      'another fact',
      { lineage: lineage({ fact_id: OTHER_ID }) },
      202,
    ],
    [
      'card_lineage_mismatch',
      'no method',
      { lineage: lineage({ lineage: { methodVersion: 'v1' } }) },
      202,
    ],
    [
      'card_lineage_mismatch',
      'no version',
      { lineage: lineage({ lineage: { method: 'm' } }) },
      202,
    ],
    [
      'card_lineage_mismatch',
      'no sources',
      { lineage: lineage({ sources: [] }) },
      202,
    ],
    [
      'card_lineage_mismatch',
      'no source list',
      { lineage: lineage({ sources: null }) },
      202,
    ],
    [
      'card_lineage_mismatch',
      'no hash',
      { lineage: source({ sha256: undefined }) },
      202,
    ],
    [
      'card_lineage_mismatch',
      'no publisher',
      { lineage: source({ publisher: ' ' }) },
      202,
    ],
    [
      'card_lineage_mismatch',
      'no licence',
      { lineage: source({ licenceOrTerms: 7 }) },
      202,
    ],
    [
      'card_lineage_mismatch',
      'unread body',
      { lineage: new Map([[ID, { status: 200, body: undefined }]]) },
      202,
    ],
    ['card_missing', 'no card', { card: false, chips: [] }, 202],
    ['card_fact_chip_missing', 'no chip', { chips: [] }, 202],
    ['card_fact_binding_mismatch', 'another id', { chips: [OTHER_ID] }, 202],
    ['card_fact_binding_mismatch', 'no id', { chips: [null] }, 202],
    [
      'card_fact_binding_mismatch',
      'one unbound chip',
      { chips: [ID, OTHER_ID] },
      202,
    ],
  ])(
    'decides %s on one changed observation: %s',
    (reason, _name, change, status) => {
      expect(decideCard(card)).toEqual(PASS_CARD);
      expect(decideCard({ ...card, ...change }).result).toEqual({
        status,
        reason,
      });
    },
  );

  it('decides in the fixed order, transport observations first', () => {
    const order = ITEM_REASONS.card;
    const steps: Partial<CardSeen>[] = [
      { ui: false },
      { selected: false },
      { start: { ...card.start!, status: 429 } },
      { events: { ...card.events!, status: 404 } },
      { tool: { ...card.tool!, status: 404 } },
      { events: framesWith([]) },
      { lineage: lineage({}, 404) },
      { lineage: lineage({ fact_id: OTHER_ID }) },
      { card: false },
      { chips: [] },
      { chips: [OTHER_ID] },
    ];
    // Every later fault is present; the earliest one alone is reported.
    // A later step that replaces an earlier field is left out of that mix.
    for (const [first, reason] of order.entries()) {
      const later = steps
        .slice(first + 1)
        .filter(
          (step) => !Object.keys(step).some((key) => key in steps[first]!),
        );
      const mixed = Object.assign({}, card, ...later.reverse(), steps[first]);
      expect(decideCard(mixed).result.reason, reason).toBe(reason);
    }
  });

  it('names the events address of an accepted start even when the card fails', () => {
    expect(decideCard({ ...card, card: false }).eventsPath).toBe(EVENTS);
    expect(
      decideCard({ ...card, start: { ...card.start!, status: 200 } })
        .eventsPath,
    ).toBeNull();
    expect(
      decideCard({
        ...card,
        start: body(card.start!, { events_url: '/api/answers/x/events' }),
      }).eventsPath,
    ).toBeNull();
  });
});

describe('remote-check map style and tile decisions', () => {
  const map = observed().map;
  const style = map.style!;
  const refusedRead = { status: 503, body: {} };
  it.each<[string, string, Partial<MapSeen>, number | null]>([
    ['map_unavailable', 'no handle', { style: null }, 200],
    ['release_unanswered', 'no read', { release: [] }, null],
    [
      'release_unanswered',
      'first read refused',
      { release: [refusedRead] },
      503,
    ],
    [
      'release_unanswered',
      'later read refused',
      { release: [...map.release, refusedRead] },
      503,
    ],
    [
      'release_unanswered',
      'no address',
      { release: [{ status: 200, body: { basemap_url: null } }] },
      200,
    ],
    [
      'release_unanswered',
      'foreign address',
      {
        release: [
          { status: 200, body: { basemap_url: 'https://other.invalid/a' } },
        ],
      },
      200,
    ],
    [
      'style_source_mismatch',
      'another address',
      {
        style: {
          ...style,
          sources: [
            { id: BASEMAP_SOURCE, url: 'pmtiles:///tiles/other.pmtiles' },
          ],
        },
      },
      200,
    ],
    [
      'style_source_mismatch',
      'another name',
      {
        style: {
          ...style,
          sources: [{ id: 'other', url: 'pmtiles://' + ARCHIVE }],
        },
      },
      200,
    ],
    [
      'style_source_mismatch',
      'no source',
      { style: { ...style, sources: [] } },
      200,
    ],
    [
      'style_glyphs_mismatch',
      'another origin',
      { style: { ...style, glyphs: 'https://other.invalid' + GLYPH_TEMPLATE } },
      200,
    ],
    [
      'style_glyphs_mismatch',
      'no template',
      { style: { ...style, glyphs: null } },
      200,
    ],
    [
      'style_layers_missing',
      'no basemap layer',
      { style: { ...style, layers: ['other', null] } },
      200,
    ],
  ])(
    'decides %s on one changed observation: %s',
    (reason, _name, change, status) => {
      expect(decideMapStyle(map, ORIGIN)).toEqual({
        status: 200,
        reason: null,
      });
      expect(decideMapStyle({ ...map, ...change }, ORIGIN)).toEqual({
        status,
        reason,
      });
    },
  );
  it('decides the map style in the fixed order', () => {
    const wrong = { glyphs: null, sources: [], layers: [] };
    expect(decideMapStyle({ release: [], style: null }, ORIGIN).reason).toBe(
      'map_unavailable',
    );
    expect(decideMapStyle({ release: [], style: wrong }, ORIGIN).reason).toBe(
      'release_unanswered',
    );
    expect(decideMapStyle({ ...map, style: wrong }, ORIGIN).reason).toBe(
      'style_source_mismatch',
    );
    expect(
      decideMapStyle(
        { ...map, style: { ...wrong, sources: style.sources } },
        ORIGIN,
      ).reason,
    ).toBe('style_glyphs_mismatch');
  });
  it('names the basemap source the application style uses', () => {
    vi.stubGlobal('location', { origin: ORIGIN });
    const built = extractStyle({
      extractUrl: ARCHIVE,
      theme: 'dark',
      language: 'en',
    });
    const seen = {
      glyphs: built.glyphs,
      sources: Object.entries(built.sources).map(([id, source]) => ({
        id,
        url: (source as { url?: unknown }).url,
      })),
      layers: built.layers.map((layer) =>
        'source' in layer ? layer.source : null,
      ),
    };
    expect(decideMapStyle({ ...map, style: seen }, ORIGIN)).toEqual({
      status: 200,
      reason: null,
    });
  });

  const tile = observed().tile;
  it.each<[string, string, Partial<TileSeen>, number | null]>([
    ['tile_no_range_response', 'no read', { ranged: [] }, null],
    [
      'tile_no_range_response',
      'another path',
      { ranged: [{ path: '/tiles/other', status: 206 }] },
      null,
    ],
    [
      'tile_status_unexpected',
      'whole body',
      { ranged: [{ path: ARCHIVE, status: 200 }] },
      200,
    ],
    [
      'tile_status_unexpected',
      'later read',
      { ranged: [...tile.ranged, { path: ARCHIVE, status: 404 }] },
      404,
    ],
    ['tile_not_rendered', 'no feature', { rendered: false }, 206],
  ])(
    'decides %s on one changed observation: %s',
    (reason, _name, change, status) => {
      expect(decideTile(tile, map.release)).toEqual({
        status: 206,
        reason: null,
      });
      expect(decideTile({ ...tile, ...change }, map.release)).toEqual({
        status,
        reason,
      });
    },
  );
  it('decides the tile in the fixed order and needs the release address', () => {
    const wrong = { ranged: [{ path: ARCHIVE, status: 200 }], rendered: false };
    expect(decideTile(wrong, map.release).reason).toBe(
      'tile_status_unexpected',
    );
    expect(
      decideTile({ ranged: [], rendered: false }, map.release).reason,
    ).toBe('tile_no_range_response');
    expect(decideTile(tile, [])).toEqual({
      status: null,
      reason: 'tile_no_range_response',
    });
  });
});

describe('remote-check result document', () => {
  const PASSED = {
    schema: RESULT_SCHEMA,
    items: {
      start_page_en: { status: 200, reason: null },
      start_page_ar: { status: 200, reason: null },
      card: { status: 202, reason: null },
      map_style: { status: 200, reason: null },
      tile: { status: 206, reason: null },
    },
    events_path: EVENTS,
  };
  it('is exactly the closed document and holds no origin', () => {
    const made = resultDocument(observed(), ORIGIN);
    expect(made).toEqual(PASSED);
    expect(resultExact(JSON.parse(JSON.stringify(made)))).toBe(true);
    expect(JSON.stringify(made)).not.toContain('remote-check.invalid');
  });
  it('reports the first reason of each item that cannot run', () => {
    const none: PageSeen = {
      status: null,
      rendered: false,
      lang: null,
      dir: null,
    };
    const made = resultDocument(
      {
        start_page_en: none,
        start_page_ar: none,
        card: {
          ...observed().card,
          ui: false,
          start: null,
          events: null,
          tool: null,
          lineage: new Map(),
          card: false,
          chips: [],
        },
        map: { release: [], style: null },
        tile: { ranged: [], rendered: false },
      },
      ORIGIN,
    );
    expect(made).toEqual({
      schema: RESULT_SCHEMA,
      items: {
        start_page_en: { status: null, reason: 'page_no_response' },
        start_page_ar: { status: null, reason: 'page_no_response' },
        card: { status: null, reason: 'card_ui_unavailable' },
        map_style: { status: null, reason: 'map_unavailable' },
        tile: { status: null, reason: 'tile_no_range_response' },
      },
      events_path: null,
    });
    expect(resultExact(made)).toBe(true);
  });
  const item = (change: Json) => ({
    ...PASSED,
    items: { ...PASSED.items, card: { ...PASSED.items.card, ...change } },
  });
  it.each<[string, unknown]>([
    ['another schema', { ...PASSED, schema: 'remote_check_browser.v2' }],
    ['a key added', { ...PASSED, host: 'x' }],
    ['a key missing', { schema: PASSED.schema, items: PASSED.items }],
    [
      'an item missing',
      { ...PASSED, items: { ...PASSED.items, tile: undefined } },
    ],
    [
      'an item added',
      { ...PASSED, items: { ...PASSED.items, health: PASSED.items.tile } },
    ],
    ['an item key added', item({ text: 'x' })],
    ['a boolean status', item({ status: true })],
    ['a string status', item({ status: '202' })],
    ['a fractional status', item({ status: 202.5 })],
    ['a status under the range', item({ status: 99 })],
    ['a status over the range', item({ status: 600 })],
    ['a reason of another item', item({ reason: 'tile_not_rendered' })],
    ['a reason outside the list', item({ reason: 'failed' })],
    ['a null reason with a null status', item({ status: null })],
    [
      'a failed item with a string status',
      item({ status: '202', reason: 'card_missing' }),
    ],
    [
      'a failed item with a status under the range',
      item({ status: 99, reason: 'card_missing' }),
    ],
    [
      'an item that is no object',
      { ...PASSED, items: { ...PASSED.items, card: null } },
    ],
    ['items that are no object', { ...PASSED, items: null }],
    [
      'an events path outside the form',
      { ...PASSED, events_path: '/api/answers/ABC/events' },
    ],
    ['an events path with a tail', { ...PASSED, events_path: EVENTS + '/x' }],
    ['an events path that is no string', { ...PASSED, events_path: 7 }],
    ['not an object', [PASSED]],
  ])('refuses %s', (_name, value) => {
    expect(resultExact(PASSED)).toBe(true);
    expect(resultExact(JSON.parse(JSON.stringify(value)))).toBe(false);
  });
  it('accepts a failed item with or without a status, and a null events path', () => {
    expect(resultExact(item({ reason: 'card_missing' }))).toBe(true);
    expect(
      resultExact(item({ status: null, reason: 'card_ui_unavailable' })),
    ).toBe(true);
    expect(resultExact({ ...PASSED, events_path: null })).toBe(true);
  });
});

describe('remote-check closed vocabulary, selection and bound', () => {
  it('emits only reasons of the generated vocabulary', () => {
    const emitted = Object.values(ITEM_REASONS).flat();
    expect(emitted).toHaveLength(29);
    expect(
      emitted.filter((reason) => !(codes as string[]).includes(reason)),
    ).toEqual([]);
  });
  it('bounds each browser step by the one named constant', () => {
    expect(STEP_MS).toBe(15_000);
  });
  const file = (row: unknown) => JSON.stringify(row);
  const valid = {
    schema: 'remote_check_selection.v1',
    activity_query: 'INVENTED-Craft',
    place_query: 'INVENTED-Garden',
  };
  const NONE = { activity_query: null, place_query: null };
  it('reads the tracked selection file as unresolved', () => {
    const tracked = readFileSync('tests/remote-check/selection.json', 'utf8');
    expect(JSON.parse(tracked)).toEqual({ schema: valid.schema, ...NONE });
    expect(readSelection(tracked)).toEqual(NONE);
  });
  it('reads two labels type-exactly', () => {
    expect(readSelection(file(valid))).toEqual({
      activity_query: 'INVENTED-Craft',
      place_query: 'INVENTED-Garden',
    });
    expect(readSelection(file({ ...valid, place_query: null }))).toEqual({
      activity_query: 'INVENTED-Craft',
      place_query: null,
    });
  });
  it.each<[string, string]>([
    ['not JSON', '{'],
    ['not an object', file([valid])],
    ['another schema', file({ ...valid, schema: 'remote_check_selection.v2' })],
    ['a key added', file({ ...valid, lang: 'en' })],
    ['a key missing', file({ schema: valid.schema, activity_query: 'x' })],
    ['a numeric query', file({ ...valid, activity_query: 7 })],
    ['a blank query', file({ ...valid, place_query: ' ' })],
    ['a list query', file({ ...valid, place_query: [] })],
  ])('reads %s as unresolved', (_name, text) => {
    expect(readSelection(text)).toEqual(NONE);
  });
});
