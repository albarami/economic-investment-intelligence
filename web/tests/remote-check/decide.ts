/**
 * Pure decisions of the remote-check browser runner (S3-T20). Presence and
 * shape only: nothing here drives a page, and no number is computed.
 */
import {
  readStoryFrames,
  startedEventsUrl,
} from '../../src/api/public-opening';
import { FACT_KEYS } from '../../src/api/release';
import { GLYPH_TEMPLATE } from '../../src/stage/basemap';

/** The bound of each browser step, in milliseconds. */
export const STEP_MS = 15_000;
export const RESULT_SCHEMA = 'remote_check_browser.v1';
export const SELECTION_SCHEMA = 'remote_check_selection.v1';
/** The name the application's style gives its basemap source. */
export const BASEMAP_SOURCE = 'protomaps';
const ARCHIVE_SCHEME = 'pmtiles://';
const FACT_ID = /^f_[0-9a-f]{32}$/;

const PAGE_REASONS = [
  'page_no_response',
  'page_status_unexpected',
  'page_not_rendered',
  'page_language_mismatch',
  'page_direction_mismatch',
] as const;
/** The closed reasons of each item, in the order they are decided. */
export const ITEM_REASONS = {
  start_page_en: PAGE_REASONS,
  start_page_ar: PAGE_REASONS,
  card: [
    'card_ui_unavailable',
    'card_selection_unresolved',
    'card_playbook_refused',
    'card_stream_refused',
    'card_tool_refused',
    'card_no_data',
    'card_lineage_unanswered',
    'card_lineage_mismatch',
    'card_missing',
    'card_fact_chip_missing',
    'card_fact_binding_mismatch',
  ],
  map_style: [
    'map_unavailable',
    'release_unanswered',
    'style_source_mismatch',
    'style_glyphs_mismatch',
    'style_layers_missing',
  ],
  tile: [
    'tile_no_range_response',
    'tile_status_unexpected',
    'tile_not_rendered',
  ],
} as const;
export type Item = keyof typeof ITEM_REASONS;
export type Language = 'en' | 'ar';

export interface ItemResult {
  status: number | null;
  reason: string | null;
}
/** One response of the page: its status and its parsed body. */
export interface Answer {
  status: number;
  body: unknown;
}
export interface PageSeen {
  status: number | null;
  rendered: boolean;
  lang: string | null;
  dir: string | null;
}
export interface CardSeen {
  /** The guided-story control and the story controls answered. */
  ui: boolean;
  /** Both fixed queries were given and each found a candidate. */
  selected: boolean;
  start: Answer | null;
  events: (Answer & { contentType: string | null }) | null;
  tool: Answer | null;
  /** Each fact id whose lineage the page asked for; null while unanswered. */
  lineage: ReadonlyMap<string, Answer | null>;
  card: boolean;
  /** The `data-fact-id` of every chip of the card. */
  chips: readonly (string | null)[];
}
export interface StyleSeen {
  glyphs: unknown;
  sources: readonly { id: string; url: unknown }[];
  /** The source name of every layer, in order. */
  layers: readonly unknown[];
}
export interface MapSeen {
  /** Every release read of the English page, in order. */
  release: readonly Answer[];
  /** The running style; null when the map handle is absent. */
  style: StyleSeen | null;
}
export interface TileSeen {
  /** Every ranged read the English page was answered: its path and status. */
  ranged: readonly { path: string; status: number }[];
  rendered: boolean;
}
export interface Observed {
  start_page_en: PageSeen;
  start_page_ar: PageSeen;
  card: CardSeen;
  map: MapSeen;
  tile: TileSeen;
}
export interface Selection {
  activity_query: string | null;
  place_query: string | null;
}
export interface ResultDocument {
  schema: typeof RESULT_SCHEMA;
  items: Record<Item, ItemResult>;
  events_path: string | null;
}

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}
function words(value: unknown): value is string {
  return typeof value === 'string' && value.trim() !== '';
}

export function decideStartPage(
  seen: PageSeen,
  language: Language,
): ItemResult {
  const reason = (): string | null => {
    if (seen.status === null) return 'page_no_response';
    if (seen.status !== 200) return 'page_status_unexpected';
    if (!seen.rendered) return 'page_not_rendered';
    if (seen.lang !== language) return 'page_language_mismatch';
    if (seen.dir !== (language === 'ar' ? 'rtl' : 'ltr'))
      return 'page_direction_mismatch';
    return null;
  };
  return { status: seen.status, reason: reason() };
}

/** The events address of an accepted start: 202 with the closed start body. */
function eventsPath(start: Answer | null): string | null {
  const body = start === null ? null : record(start.body);
  return start?.status === 202 && body ? startedEventsUrl(body) : null;
}
type Frames = ReturnType<typeof readStoryFrames>;
function storyFrames(events: CardSeen['events']): Frames | null {
  if (
    events === null ||
    events.status !== 200 ||
    typeof events.body !== 'string' ||
    events.contentType?.split(';')[0]?.trim().toLowerCase() !==
      'text/event-stream'
  )
    return null;
  try {
    return readStoryFrames(events.body);
  } catch {
    return null;
  }
}
/** The fact ids the night-lights evidence frame names, when it names any. */
function evidenceIds(frames: Frames): string[] | null {
  const ids = frames.find(
    (frame) => frame.kind === 'evidence' && frame.data.kind === 'night_lights',
  )?.data.fact_ids;
  return Array.isArray(ids) &&
    ids.length > 0 &&
    ids.every((id) => typeof id === 'string' && FACT_ID.test(id))
    ? (ids as string[])
    : null;
}
function toolRefused(tool: Answer): boolean {
  const body = record(tool.body);
  return (
    tool.status !== 200 ||
    body === null ||
    body.tool !== 'night_lights' ||
    body.status !== 'OK'
  );
}
const GEOGRAPHY_KINDS: readonly unknown[] = [
  'release_units',
  'public',
  'national',
  'user_scenario',
  'area_shape',
];
const GEOGRAPHY_TEXTS = ['public_code', 'area_id', 'apportioned_from'];
const EVIDENCE: readonly unknown[] = ['observed', 'inferred', 'still_to_test'];
const RELIABILITY: readonly unknown[] = [
  'standard',
  'low_count',
  'not_applicable',
];
function strings(value: unknown): boolean {
  return (
    Array.isArray(value) && value.every((item) => typeof item === 'string')
  );
}
function geographyShaped(value: unknown): boolean {
  const geography = record(value);
  if (geography === null) return false;
  const { kind, unit_ids: units, ...texts } = geography;
  return (
    GEOGRAPHY_KINDS.includes(kind) &&
    (units === undefined || strings(units)) &&
    Object.entries(texts).every(
      ([key, held]) =>
        GEOGRAPHY_TEXTS.includes(key) && typeof held === 'string',
    )
  );
}
/**
 * A Public fact of document 03's fact object: closed keys, each in its
 * domain. Its id is held to the evidence frame's ids by the caller.
 */
function publicFact(value: unknown): boolean {
  const fact = record(value);
  return (
    fact !== null &&
    Object.keys(fact).sort().join() === [...FACT_KEYS].sort().join() &&
    (fact.value === null || ['number', 'string'].includes(typeof fact.value)) &&
    [
      fact.unit,
      fact.period,
      fact.label_en,
      fact.label_ar,
      fact.lineage_ref,
      fact.release_id,
    ].every(words) &&
    geographyShaped(fact.geography) &&
    fact.provenance === 'public' &&
    JSON.stringify(fact.input_classes) === '["public"]' &&
    EVIDENCE.includes(fact.evidence_status) &&
    RELIABILITY.includes(fact.reliability) &&
    strings(fact.coverage_keys) &&
    strings(fact.caveat_keys)
  );
}
/** The tool answered exactly the named facts, each a Public fact. */
function toolAnswers(tool: Answer | null, ids: readonly string[]): boolean {
  const facts = tool === null ? null : record(tool.body)?.facts;
  if (!Array.isArray(facts) || !facts.every(publicFact)) return false;
  const named = facts.map((fact: Record<string, unknown>) => fact.fact_id);
  return JSON.stringify(named.sort()) === JSON.stringify([...ids].sort());
}
/** The same fact id, a method, a method version and fully named sources. */
function lineageNames(body: unknown, id: string): boolean {
  const chain = record(body);
  const lineage = record(chain?.lineage);
  const sources = chain?.sources;
  return (
    chain?.fact_id === id &&
    words(lineage?.method) &&
    words(lineage?.methodVersion) &&
    Array.isArray(sources) &&
    sources.length > 0 &&
    sources.every((row) => {
      const source = record(row);
      return (
        words(source?.sha256) &&
        words(source?.publisher) &&
        words(source?.licenceOrTerms)
      );
    })
  );
}
function cardReason(seen: CardSeen, path: string | null): string | null {
  if (!seen.ui) return 'card_ui_unavailable';
  if (!seen.selected) return 'card_selection_unresolved';
  if (path === null) return 'card_playbook_refused';
  const frames = storyFrames(seen.events);
  if (frames === null) return 'card_stream_refused';
  if (seen.tool !== null && toolRefused(seen.tool)) return 'card_tool_refused';
  const ids = evidenceIds(frames);
  if (ids === null) return 'card_no_data';
  if (!toolAnswers(seen.tool, ids)) return 'card_tool_refused';
  const asked = ids.filter((id) => seen.lineage.has(id));
  if (asked.some((id) => seen.lineage.get(id)?.status !== 200))
    return 'card_lineage_unanswered';
  if (asked.some((id) => !lineageNames(seen.lineage.get(id)?.body, id)))
    return 'card_lineage_mismatch';
  if (!seen.card) return 'card_missing';
  if (asked.length !== ids.length) return 'card_lineage_unanswered';
  if (seen.chips.length === 0) return 'card_fact_chip_missing';
  if (!seen.chips.every((id) => id !== null && ids.includes(id)))
    return 'card_fact_binding_mismatch';
  return null;
}
export function decideCard(seen: CardSeen): {
  result: ItemResult;
  eventsPath: string | null;
} {
  const path = eventsPath(seen.start);
  return {
    result: {
      status: seen.start?.status ?? null,
      reason: cardReason(seen, path),
    },
    eventsPath: path,
  };
}

/** The basemap address of the first release read, when every read answered. */
function basemapAddress(release: readonly Answer[]): string | null {
  const address = record(release[0]?.body)?.basemap_url;
  return release.every((answer) => answer.status === 200) &&
    typeof address === 'string' &&
    address.startsWith('/')
    ? address
    : null;
}
export function decideMapStyle(seen: MapSeen, origin: string): ItemResult {
  const address = basemapAddress(seen.release);
  const reason = (): string | null => {
    if (seen.style === null) return 'map_unavailable';
    if (address === null) return 'release_unanswered';
    if (
      !seen.style.sources.some(
        (source) =>
          source.id === BASEMAP_SOURCE &&
          source.url === ARCHIVE_SCHEME + address,
      )
    )
      return 'style_source_mismatch';
    if (seen.style.glyphs !== origin + GLYPH_TEMPLATE)
      return 'style_glyphs_mismatch';
    if (!seen.style.layers.includes(BASEMAP_SOURCE))
      return 'style_layers_missing';
    return null;
  };
  const refused = seen.release.find((answer) => answer.status !== 200);
  return {
    status: (refused ?? seen.release[0])?.status ?? null,
    reason: reason(),
  };
}

export function decideTile(
  seen: TileSeen,
  release: readonly Answer[],
): ItemResult {
  const address = record(release[0]?.body)?.basemap_url;
  const reads = seen.ranged.filter((read) => read.path === address);
  const refused = reads.find((read) => read.status !== 206);
  const reason = (): string | null => {
    if (reads.length === 0) return 'tile_no_range_response';
    if (refused) return 'tile_status_unexpected';
    if (!seen.rendered) return 'tile_not_rendered';
    return null;
  };
  return { status: (refused ?? reads[0])?.status ?? null, reason: reason() };
}

/** The tracked selection, read type-exactly; anything else selects nothing. */
export function readSelection(text: string): Selection {
  const none = { activity_query: null, place_query: null };
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    return none;
  }
  const row = record(value);
  const query = (held: unknown) => held === null || words(held);
  if (
    row === null ||
    Object.keys(row).sort().join() !== 'activity_query,place_query,schema' ||
    row.schema !== SELECTION_SCHEMA ||
    !query(row.activity_query) ||
    !query(row.place_query)
  )
    return none;
  return {
    activity_query: row.activity_query as string | null,
    place_query: row.place_query as string | null,
  };
}

export function resultDocument(seen: Observed, origin: string): ResultDocument {
  const card = decideCard(seen.card);
  return {
    schema: RESULT_SCHEMA,
    items: {
      start_page_en: decideStartPage(seen.start_page_en, 'en'),
      start_page_ar: decideStartPage(seen.start_page_ar, 'ar'),
      card: card.result,
      map_style: decideMapStyle(seen.map, origin),
      tile: decideTile(seen.tile, seen.map.release),
    },
    events_path: card.eventsPath,
  };
}

function itemExact(item: Item, value: unknown): boolean {
  const row = record(value);
  if (row === null || Object.keys(row).sort().join() !== 'reason,status')
    return false;
  const { status, reason } = row;
  const coded =
    typeof status === 'number' &&
    Number.isInteger(status) &&
    status >= 100 &&
    status <= 599;
  return reason === null
    ? coded
    : (coded || status === null) &&
        (ITEM_REASONS[item] as readonly unknown[]).includes(reason);
}
/** Whether a value is exactly one result document of plan 4.3. */
export function resultExact(value: unknown): boolean {
  const row = record(value);
  if (
    row === null ||
    Object.keys(row).sort().join() !== 'events_path,items,schema'
  )
    return false;
  const items = record(row.items);
  const names = Object.keys(ITEM_REASONS) as Item[];
  const path = row.events_path;
  return (
    row.schema === RESULT_SCHEMA &&
    items !== null &&
    Object.keys(items).sort().join() === [...names].sort().join() &&
    names.every((item) => itemExact(item, items[item])) &&
    (path === null ||
      (typeof path === 'string' &&
        startedEventsUrl({
          answer_id: path.split('/')[3],
          events_url: path,
        }) === path))
  );
}
