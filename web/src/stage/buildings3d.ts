/**
 * All of Qatar in 3D: each building extruded to its own height only, and the
 * clock's shadows for the buildings in view that have a height, under a cap
 * (FE-50, FE-52, FE-143; decision 0048 items 1 to 4). The heights come only
 * from the fixed read `GET /api/building-heights` of the S2-T20 asset.
 */
import type { Layer, PickingInfo } from '@deck.gl/core';
import { SolidPolygonLayer } from '@deck.gl/layers';

import { closed, FACT_KEYS, sourceRow, text } from '../api/release';
import { isRecord } from '../guards';
import { createRegistry, type FactRegistry } from '../facts/registry';
import type { Fact, FactBinding, LineageRow } from '../facts/types';
import { boundaryColor } from './layers/ramp';

export const HEIGHT_SOURCES = [
  'recorded',
  'floor_count',
  '3dglobfp',
  'wsf3d',
  'none',
] as const;
export type HeightSource = (typeof HEIGHT_SOURCES)[number];
export const FALLBACK_SOURCES = ['floor_count', '3dglobfp', 'wsf3d'] as const;
export type FallbackSource = (typeof FALLBACK_SOURCES)[number];

/** One building of the S2-T20 heights asset, as the API's read returns it. */
export interface BuildingRow {
  building_key: string;
  footprint: [number, number][];
  /** The written height's own decimal text in metres, or null for none. */
  height_m: string | null;
  height_source: HeightSource;
}

/** Each statistic slot's fact field, metric key and unit (C47, MTH-125). */
export const FALLBACK_SLOTS = [
  ['pairs_fact_id', 'building_height_pairs', 'count'],
  ['mean_signed_fact_id', 'building_height_mean_signed_error', 'metres'],
  ['mean_abs_fact_id', 'building_height_mean_abs_error', 'metres'],
  ['median_abs_fact_id', 'building_height_median_abs_error', 'metres'],
] as const;
export type FallbackSlot = (typeof FALLBACK_SLOTS)[number][0];
export const HEIGHTS_TABLE = 'asset_heights';
export const HEIGHTS_METHOD = 'MTH-125';

/** Fact ids of one fallback's measured error, or its no-pairs reason. */
export type FallbackError =
  | ({ source: FallbackSource } & Record<FallbackSlot, string>)
  | { source: FallbackSource; reason: 'no_pairs' };

/** A read accepted whole: its slots are bound to facts of its own chain. */
export interface BuildingHeightsRead {
  buildings: BuildingRow[];
  fallback_errors: FallbackError[];
  registry: FactRegistry;
}

export type HeightsRefusal =
  | 'heights_shape'
  | 'height_source_unknown'
  | 'height_source_mismatch'
  | 'height_not_positive'
  | 'duplicate_building_key'
  | 'fallback_error_shape'
  | 'fallback_reason_unknown'
  | 'heights_chain'
  | 'fallback_fact_binding';

export type HeightsRead =
  | { ok: true; read: BuildingHeightsRead }
  | { ok: false; reason: HeightsRefusal };

const HEIGHT_TEXT = /^\d+(\.\d{1,2})?$/;
const READ_KEYS = [
  'buildings',
  'facts',
  'fallback_errors',
  'lineage',
  'release_id',
  'sources',
] as const;
const LINEAGE_KEYS = [
  'lineageId',
  'releaseId',
  'tableName',
  'method',
  'methodVersion',
  'sourceIds',
  'inputClasses',
] as const;

class Refused extends Error {
  constructor(readonly reason: HeightsRefusal) {
    super(reason);
  }
}

function footprint(value: unknown): value is [number, number][] {
  return (
    Array.isArray(value) &&
    value.length >= 3 &&
    value.every(
      (point) =>
        Array.isArray(point) &&
        point.length === 2 &&
        point.every(
          (part) => typeof part === 'number' && Number.isFinite(part),
        ),
    )
  );
}

/** Decimal text of metres that the renderer holds as positive and finite. */
function usableHeight(height: unknown): boolean {
  if (typeof height !== 'string' || !HEIGHT_TEXT.test(height)) return false;
  const metres = Number(height);
  return Number.isFinite(metres) && metres > 0;
}

function rowRefusal(row: unknown): HeightsRefusal | null {
  if (!isRecord(row)) return 'heights_shape';
  const key = row.building_key;
  if (typeof key !== 'string' || key === '' || !footprint(row.footprint))
    return 'heights_shape';
  const source = row.height_source;
  if (!HEIGHT_SOURCES.includes(source as HeightSource))
    return 'height_source_unknown';
  const height = row.height_m;
  if ((source === 'none') !== (height === null))
    return 'height_source_mismatch';
  if (height !== null && !usableHeight(height)) return 'height_not_positive';
  return null;
}

function sameKeys(entry: Record<string, unknown>, keys: readonly string[]) {
  return (
    Object.keys(entry).length === keys.length &&
    keys.every((key) => Object.hasOwn(entry, key))
  );
}

/** Exactly the no-pairs variant or exactly the statistics variant. */
function entryRefusal(entry: unknown): HeightsRefusal | null {
  if (!isRecord(entry)) return 'fallback_error_shape';
  if (Object.hasOwn(entry, 'reason')) {
    if (!sameKeys(entry, ['source', 'reason'])) return 'fallback_error_shape';
    return entry.reason === 'no_pairs' ? null : 'fallback_reason_unknown';
  }
  const slots = FALLBACK_SLOTS.map(([field]) => field);
  if (!sameKeys(entry, ['source', ...slots])) return 'fallback_error_shape';
  return slots.every((field) => typeof entry[field] === 'string')
    ? null
    : 'fallback_error_shape';
}

function errorsRefusal(errors: unknown[]): HeightsRefusal | null {
  const seen = errors.map((entry) => (isRecord(entry) ? entry.source : null));
  const complete =
    errors.length === FALLBACK_SOURCES.length &&
    FALLBACK_SOURCES.every((source) => seen.includes(source));
  if (!complete) return 'fallback_error_shape';
  for (const entry of errors) {
    const reason = entryRefusal(entry);
    if (reason) return reason;
  }
  return null;
}

function factBinding(value: unknown): FactBinding {
  const item = closed(value, ['fact', 'binding']);
  const fact = closed(item.fact, FACT_KEYS) as unknown as Fact;
  const binding = closed(item.binding, ['metricKey', 'qualifiers']);
  const qualifiers = closed(binding.qualifiers, ['height_source']);
  return {
    fact,
    metricKey: text(binding.metricKey),
    presentation: 'ordinary',
    qualifiers: { height_source: text(qualifiers.height_source) },
  };
}

function lineageRow(value: unknown, releaseId: string): LineageRow {
  const row = closed(value, LINEAGE_KEYS);
  if (
    row.releaseId !== releaseId ||
    !Array.isArray(row.sourceIds) ||
    JSON.stringify(row.inputClasses) !== JSON.stringify(['public'])
  )
    throw new Error('chain_refused');
  return {
    lineageId: text(row.lineageId),
    releaseId,
    tableName: text(row.tableName),
    method: text(row.method),
    methodVersion: text(row.methodVersion),
    sourceIds: row.sourceIds.map(text),
    inputClasses: ['public'],
  };
}

/** The read's own chain as a registry; a malformed part refuses it. */
function chainRegistry(value: Record<string, unknown>) {
  try {
    const releaseId = text(value.release_id);
    if (!Array.isArray(value.facts) || !Array.isArray(value.sources))
      throw new Error('chain_refused');
    const facts = value.facts.map(factBinding);
    const lineage = lineageRow(value.lineage, releaseId);
    const registry = createRegistry({
      facts,
      releases: [{ releaseId }],
      tables: [{ releaseId, tableName: lineage.tableName }],
      lineages: [lineage],
      sources: value.sources.map(sourceRow),
    });
    return { releaseId, facts, registry };
  } catch {
    throw new Refused('heights_chain');
  }
}

function slotBound(
  chain: ReturnType<typeof chainRegistry>,
  id: string,
  source: FallbackSource,
  metric: string,
  unit: string,
): boolean {
  const binding = chain.facts.find((item) => item.fact.fact_id === id);
  if (!binding) return false;
  const { fact } = binding;
  const resolved = chain.registry.resolve(id);
  return (
    binding.metricKey === metric &&
    binding.qualifiers?.height_source === source &&
    fact.unit === unit &&
    typeof fact.value === 'number' &&
    Number.isFinite(fact.value) &&
    (unit !== 'count' || Number.isInteger(fact.value)) &&
    fact.release_id === chain.releaseId &&
    resolved.status === 'ready' &&
    resolved.display === 'value' &&
    resolved.lineage.tableName === HEIGHTS_TABLE &&
    resolved.lineage.method === HEIGHTS_METHOD
  );
}

/** Every slot names its own statistic of its own fallback; no fact is spare. */
function bindingRefusal(
  errors: readonly FallbackError[],
  chain: ReturnType<typeof chainRegistry>,
): HeightsRefusal | null {
  const used: string[] = [];
  for (const entry of errors) {
    if ('reason' in entry) continue;
    for (const [field, metric, unit] of FALLBACK_SLOTS) {
      const id = entry[field];
      if (
        used.includes(id) ||
        !slotBound(chain, id, entry.source, metric, unit)
      )
        return 'fallback_fact_binding';
      used.push(id);
    }
  }
  return used.length === chain.facts.length ? null : 'fallback_fact_binding';
}

function readOrRefuse(value: unknown): BuildingHeightsRead {
  if (
    !isRecord(value) ||
    !sameKeys(value, READ_KEYS) ||
    !Array.isArray(value.buildings) ||
    !Array.isArray(value.fallback_errors)
  )
    throw new Refused('heights_shape');
  const keys = new Set<string>();
  for (const row of value.buildings) {
    const reason = rowRefusal(row);
    if (reason) throw new Refused(reason);
    const key = (row as BuildingRow).building_key;
    if (keys.has(key)) throw new Refused('duplicate_building_key');
    keys.add(key);
  }
  const reason = errorsRefusal(value.fallback_errors);
  if (reason) throw new Refused(reason);
  const errors = value.fallback_errors as FallbackError[];
  const chain = chainRegistry(value);
  const unbound = bindingRefusal(errors, chain);
  if (unbound) throw new Refused(unbound);
  return {
    buildings: value.buildings as BuildingRow[],
    fallback_errors: errors,
    registry: chain.registry,
  };
}

/** Accepts the read of the heights asset only whole; refuses with one reason. */
export function readBuildingHeights(value: unknown): HeightsRead {
  try {
    return { ok: true, read: readOrRefuse(value) };
  } catch (error) {
    if (error instanceof Refused) return { ok: false, reason: error.reason };
    throw error;
  }
}

/** The building's own height in metres, or null; never any other value. */
export function ownHeight(row: BuildingRow): number | null {
  if (row.height_m === null) return null;
  const metres = Number(row.height_m);
  return Number.isFinite(metres) && metres > 0 ? metres : null;
}

export interface ShadowView {
  /** Longitude and latitude of the view centre, degrees. */
  centre: [number, number];
  /** West, south, east and north edges of the view, degrees. */
  bounds: [number, number, number, number];
}

export interface ShadowSelection {
  casting: BuildingRow[];
  limited: boolean;
}

type Point = readonly [number, number];

/** Even-odd test; a closed ring's repeated vertex adds a zero-length edge. */
function insideRing(point: Point, ring: readonly Point[]): boolean {
  const [x, y] = point;
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const [xi, yi] = ring[i] as Point;
    const [xj, yj] = ring[j] as Point;
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi)
      inside = !inside;
  }
  return inside;
}

function cross(o: Point, a: Point, b: Point): number {
  return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
}

function onSegment(p: Point, a: Point, b: Point): boolean {
  return (
    Math.min(a[0], b[0]) <= p[0] &&
    p[0] <= Math.max(a[0], b[0]) &&
    Math.min(a[1], b[1]) <= p[1] &&
    p[1] <= Math.max(a[1], b[1])
  );
}

/** Two closed segments meet, touching included. */
function segmentsMeet(a: Point, b: Point, c: Point, d: Point): boolean {
  const d1 = cross(c, d, a);
  const d2 = cross(c, d, b);
  const d3 = cross(a, b, c);
  const d4 = cross(a, b, d);
  if (
    ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) &&
    ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))
  )
    return true;
  return (
    (d1 === 0 && onSegment(a, c, d)) ||
    (d2 === 0 && onSegment(b, c, d)) ||
    (d3 === 0 && onSegment(c, a, b)) ||
    (d4 === 0 && onSegment(d, a, b))
  );
}

function edges(ring: readonly Point[]): [Point, Point][] {
  return ring.map((point, i) => [point, ring[(i + 1) % ring.length] as Point]);
}

/** A footprint is in view when any part of it meets the view rectangle. */
export function footprintInView(
  ring: readonly Point[],
  bounds: ShadowView['bounds'],
): boolean {
  const [west, south, east, north] = bounds;
  const corners: Point[] = [
    [west, south],
    [east, south],
    [east, north],
    [west, north],
  ];
  if (ring.some(([x, y]) => x >= west && x <= east && y >= south && y <= north))
    return true;
  if (corners.some((corner) => insideRing(corner, ring))) return true;
  const sides = edges(corners);
  return edges(ring).some(([a, b]) =>
    sides.some(([c, d]) => segmentsMeet(a, b, c, d)),
  );
}

function segmentDistance(p: Point, a: Point, b: Point): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const length = dx * dx + dy * dy;
  const t =
    length === 0
      ? 0
      : Math.max(
          0,
          Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length),
        );
  return (p[0] - a[0] - t * dx) ** 2 + (p[1] - a[1] - t * dy) ** 2;
}

/**
 * The reference point of a footprint is its point nearest the view centre:
 * squared distance zero when the centre lies inside it. Longitude is scaled
 * by cos(latitude) so both axes are comparable; the value orders only.
 */
export function footprintDistance(
  ring: readonly Point[],
  centre: Point,
): number {
  const shrink = Math.cos((centre[1] * Math.PI) / 180);
  const scaled = (point: Point): Point => [point[0] * shrink, point[1]];
  const origin = scaled(centre);
  const shape = ring.map(scaled);
  if (insideRing(origin, shape)) return 0;
  return Math.min(
    ...edges(shape).map(([a, b]) => segmentDistance(origin, a, b)),
  );
}

function checkCap(cap: number): void {
  if (!Number.isInteger(cap) || cap < 1) throw new Error('shadow_cap_invalid');
}

function checkView(view: ShadowView): void {
  const [west, south, east, north] = view.bounds;
  const numbers = [...view.centre, ...view.bounds];
  if (!numbers.every(Number.isFinite) || west > east || south > north)
    throw new Error('shadow_view_invalid');
}

/**
 * The buildings in view with a height; over the cap, the nearest to the view
 * centre keep their shadows (ties by building key) and the view is limited.
 */
export function shadowSelection(
  rows: readonly BuildingRow[],
  view: ShadowView,
  cap: number,
): ShadowSelection {
  checkCap(cap);
  checkView(view);
  const ranked = rows.flatMap((row) => {
    if (ownHeight(row) === null) return [];
    if (!footprintInView(row.footprint, view.bounds)) return [];
    return [{ row, distance: footprintDistance(row.footprint, view.centre) }];
  });
  ranked.sort(
    (a, b) =>
      a.distance - b.distance ||
      (a.row.building_key < b.row.building_key ? -1 : 1),
  );
  return {
    casting: ranked.slice(0, cap).map((item) => item.row),
    limited: ranked.length > cap,
  };
}

function ownElevation(row: BuildingRow): number {
  const height = ownHeight(row);
  if (height === null) throw new Error('extrusion_not_own_height');
  return height;
}

function buildingLayer(
  id: string,
  data: BuildingRow[],
  shadowEnabled: boolean,
  onPick?: (row: BuildingRow) => void,
): Layer {
  return new SolidPolygonLayer<BuildingRow>({
    id,
    data,
    extruded: true,
    elevationScale: 1,
    getPolygon: (row) => row.footprint,
    getElevation: ownElevation,
    getFillColor: boundaryColor(),
    pickable: true,
    onClick: (info: PickingInfo<BuildingRow>) => {
      if (info.object) onPick?.(info.object);
    },
    // deck.gl's shadow pass draws every layer whose shadowEnabled is not false.
    ...({ shadowEnabled } as object),
  });
}

/**
 * ASSUMPTION: a provisional building cap until box 7's frame-rate run with
 * shadows on measures one (decision 0048 item 3); never a displayed number.
 */
export const PROVISIONAL_BUILDING_CAP = 2000;
export const NO_SHADOWS: ShadowSelection = { casting: [], limited: false };

export const BUILDINGS_LAYER = 'buildings:heights';
export const SHADOWS_LAYER = 'buildings:shadows';
const BUILDING_LAYER_IDS: readonly string[] = [BUILDINGS_LAYER, SHADOWS_LAYER];

/** Heightless buildings stay flat on the basemap and are never extruded. */
export function buildingLayers(
  rows: readonly BuildingRow[],
  selection: ShadowSelection,
  onPick?: (row: BuildingRow) => void,
): Layer[] {
  const casting = new Set(selection.casting);
  const rest = rows.filter(
    (row) => ownHeight(row) !== null && !casting.has(row),
  );
  return [
    buildingLayer(BUILDINGS_LAYER, rest, false, onPick),
    buildingLayer(SHADOWS_LAYER, [...selection.casting], true, onPick),
  ];
}

function checkLayer(layer: Layer, seen: Set<string>): void {
  if (!BUILDING_LAYER_IDS.includes(layer.id) || seen.has(layer.id))
    throw new Error('building_layer_unexpected');
  if (!(layer instanceof SolidPolygonLayer))
    throw new Error('building_layer_type');
  seen.add(layer.id);
}

/** Refuses a building layer that breaks FE-50 or decision 0048 items 1 and 2. */
export function verifyBuildingLayers(layers: readonly Layer[], cap: number) {
  checkCap(cap);
  const seen = new Set<string>();
  let shadows = 0;
  for (const layer of layers) {
    checkLayer(layer, seen);
    const props = layer.props as unknown as {
      data: BuildingRow[];
      elevationScale: number;
      getElevation: (row: BuildingRow) => number;
      shadowEnabled?: boolean;
    };
    const casts = props.shadowEnabled !== false;
    for (const row of props.data) {
      if (casts && ownHeight(row) === null)
        throw new Error('shadow_without_height');
      let elevation: number | null;
      try {
        elevation = props.getElevation(row) * props.elevationScale;
      } catch {
        elevation = null;
      }
      if (ownHeight(row) === null || elevation !== ownHeight(row))
        throw new Error('extrusion_not_own_height');
    }
    if (casts) shadows += props.data.length;
  }
  if (shadows > cap) throw new Error('shadow_over_cap');
}

/** Refuses a legend that omits the words decision 0048 items 2 and 4 require. */
export function verifyBuildingWords(
  root: ParentNode,
  selection: ShadowSelection,
) {
  const words = (name: string) =>
    (root.querySelector(`[data-words="${name}"]`)?.textContent ?? '') !== '';
  if (!words('heights-estimates')) throw new Error('heights_words_missing');
  if (selection.casting.length > 0 && !words('shadow-estimated'))
    throw new Error('estimated_heights_words_missing');
  if (selection.limited && !words('shadow-limited'))
    throw new Error('shadow_limit_words_missing');
}
