/**
 * Hand-written area client.
 * Shapes route: docs/08_BACKEND.md row `POST /api/areas/shapes`.
 * make_area: docs/08_BACKEND.md section "make_area" and the tool route row.
 * The shapes route is called against a stand-in. This module builds no route.
 */
import type { PlaceBody } from '../controls/area-request';
import { plainHoldsDigit } from '../stage/layers/checks';
import { isRecord } from '../guards';

export interface ShapeGeometryBody {
  geometry: {
    type: 'Polygon';
    coordinates: readonly [readonly (readonly [number, number])[]];
  };
}

/** Flat, matching make_area `_PIN_KEYS`: latitude, longitude, mode, cutoff. */
export interface PinBody {
  latitude: number;
  longitude: number;
  mode: string;
  cutoff: number;
}

export interface ShapeIdBody {
  shape_id: string;
}

/** A returned area by its identifier alone (decision 0087; BE-86 decode). */
export interface AreaIdBody {
  area_id: string;
}

export const SHAPES_PATH = '/api/areas/shapes';
export const MAKE_AREA_PATH = '/api/tools/make_area';
export const RESOLVE_PATH = '/api/tools/resolve';

export interface ResolveBody {
  text: string;
  lang: 'en' | 'ar';
  kind: 'place' | 'activity' | 'both';
}

export interface PlaceCandidate {
  kind: 'place';
  key: string;
  label_en: string;
  label_ar: string;
  source: 'gazetteer';
  match: 'exact' | 'normalised';
}

export interface ActivityCandidate {
  kind: 'activity';
  key: string;
  label_en: string;
  label_ar: string;
  source: 'activity_spine';
  match: 'exact' | 'normalised';
  commerce_code: string;
  isic_class: string;
  place_category: string;
  not_mappable: boolean;
}

export type ResolveCandidate = PlaceCandidate | ActivityCandidate;
export interface ResolveEnvelope {
  tool: 'resolve';
  status: 'OK' | 'NO_DATA' | 'OUT_OF_SCOPE';
  call_id: string;
  engine: 'embedded' | 'postgres';
  release_id: string;
  facts: readonly never[];
  blocks: readonly never[];
  caveat_keys: readonly never[];
  payload: { candidates: readonly ResolveCandidate[] } | null;
}
export type ResolveAnswer =
  | { kind: 'envelope'; envelope: ResolveEnvelope }
  | { kind: 'refused'; httpStatus: number; code: string };

/** Only this same-origin tool sees typed text; no address-provider fallback. */
export async function postResolve(
  body: ResolveBody,
  fetchImpl: FetchLike,
): Promise<ResolveAnswer> {
  const response = await fetchImpl(RESOLVE_PATH, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  return readResolveEnvelope(await response.json(), response.status);
}

export function readResolveEnvelope(
  value: unknown,
  httpStatus = 200,
): ResolveAnswer {
  const malformed: ResolveAnswer = {
    kind: 'refused',
    httpStatus,
    code: 'malformed',
  };
  if (!isRecord(value)) return malformed;
  if (
    isRecord(value.error) &&
    Object.keys(value).length === 1 &&
    Object.keys(value.error).sort().join(',') === 'code,error_id,message_key' &&
    typeof value.error.code === 'string' &&
    typeof value.error.message_key === 'string' &&
    typeof value.error.error_id === 'string'
  )
    return { kind: 'refused', httpStatus, code: value.error.code };
  if (
    httpStatus !== 200 ||
    Object.keys(value).sort().join(',') !==
      'blocks,call_id,caveat_keys,engine,facts,payload,release_id,status,tool' ||
    value.tool !== 'resolve' ||
    typeof value.call_id !== 'string' ||
    typeof value.release_id !== 'string' ||
    (value.engine !== 'embedded' && value.engine !== 'postgres') ||
    !Array.isArray(value.facts) ||
    value.facts.length !== 0 ||
    !Array.isArray(value.blocks) ||
    value.blocks.length !== 0 ||
    !Array.isArray(value.caveat_keys) ||
    value.caveat_keys.length !== 0 ||
    (value.status !== 'OK' &&
      value.status !== 'NO_DATA' &&
      value.status !== 'OUT_OF_SCOPE')
  )
    return malformed;
  if (value.status !== 'OK') {
    if (value.payload !== null) return malformed;
    return { kind: 'envelope', envelope: value as unknown as ResolveEnvelope };
  }
  if (
    !isRecord(value.payload) ||
    Object.keys(value.payload).join(',') !== 'candidates' ||
    !Array.isArray(value.payload.candidates) ||
    value.payload.candidates.length < 1 ||
    value.payload.candidates.length > 5 ||
    !value.payload.candidates.every(readCandidate)
  )
    return malformed;
  return { kind: 'envelope', envelope: value as unknown as ResolveEnvelope };
}

function readCandidate(value: unknown): value is ResolveCandidate {
  if (!isRecord(value)) return false;
  const place = value.kind === 'place';
  const fields = place
    ? 'key,kind,label_ar,label_en,match,source'
    : 'commerce_code,isic_class,key,kind,label_ar,label_en,match,not_mappable,place_category,source';
  if (
    Object.keys(value).sort().join(',') !== fields ||
    (value.kind !== 'place' && value.kind !== 'activity') ||
    value.source !== (place ? 'gazetteer' : 'activity_spine') ||
    typeof value.key !== 'string' ||
    value.key.startsWith('register:') ||
    /^(?:[0-9]{8}|[0-9]{11})$/.test(value.key) ||
    typeof value.label_en !== 'string' ||
    typeof value.label_ar !== 'string' ||
    plainHoldsDigit(value.label_en) ||
    plainHoldsDigit(value.label_ar) ||
    (value.match !== 'exact' && value.match !== 'normalised')
  )
    return false;
  return (
    place ||
    (typeof value.commerce_code === 'string' &&
      typeof value.isic_class === 'string' &&
      typeof value.place_category === 'string' &&
      typeof value.not_mappable === 'boolean')
  );
}

export type AreaOutline =
  | {
      type: 'Polygon';
      coordinates: readonly (readonly (readonly [number, number])[])[];
    }
  | {
      type: 'Circle';
      coordinates: readonly [number, number];
      radius_m: number;
    };

/** Identifier lists by partition key. The client never counts them. */
export type UnitLists = Readonly<Record<string, readonly string[]>>;
export type PublicPointIds = Readonly<Record<string, readonly string[]>>;

export interface AreaPayload {
  area_id: string;
  outline: AreaOutline;
  /** Server-owned exact-shape membership. Null means the snapshot is unavailable. */
  point_feature_ids: PublicPointIds | null;
  units: UnitLists;
  /** Opaque. This task never renders it (FE-109). */
  snap_report: unknown;
  record: {
    anchor_cell: string | null;
    traffic: string;
    shape: string;
  };
}

export type AreaStatus = 'OK' | 'SUPPRESSED' | 'OUT_OF_SCOPE' | 'NO_DATA';

export interface MakeAreaEnvelope {
  tool: 'make_area';
  status: AreaStatus;
  call_id: string;
  engine: 'embedded' | 'postgres';
  blocks: readonly unknown[];
  facts: readonly unknown[];
  caveat_keys: readonly string[];
  release_id: string;
  payload: AreaPayload | null;
}

export type AreaAnswer =
  | { kind: 'envelope'; envelope: MakeAreaEnvelope }
  | { kind: 'refused'; httpStatus: number; code: string };

export type FetchLike = (
  input: string,
  init: {
    method: string;
    headers: { 'content-type': string };
    body: string;
  },
) => Promise<{
  status: number;
  json: () => Promise<unknown>;
}>;

/** Same-origin fetch. Callers outside `src/api` never name fetch. */
export function createSameOriginFetch(): FetchLike {
  return (input, init) => fetch(input, init);
}

export async function postShape(
  body: ShapeGeometryBody,
  fetchImpl: FetchLike,
): Promise<{ ok: true; shapeId: string } | { ok: false; status: number }> {
  const response = await fetchImpl(SHAPES_PATH, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (response.status !== 201) return { ok: false, status: response.status };
  const payload = (await response.json()) as { shape_id?: unknown };
  if (typeof payload.shape_id !== 'string') return { ok: false, status: 201 };
  return { ok: true, shapeId: payload.shape_id };
}

export async function postMakeArea(
  body: PinBody | ShapeIdBody | PlaceBody | AreaIdBody,
  fetchImpl: FetchLike,
): Promise<AreaAnswer> {
  const response = await fetchImpl(MAKE_AREA_PATH, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  return readEnvelope(payload, response.status);
}

/** The outline of exactly the requested area, or null. Only an OK envelope whose
 * payload names the requested identifier counts; any other answer is unresolved. */
export async function decodeAreaOutline(
  areaId: string,
  fetchImpl: FetchLike,
): Promise<AreaOutline | null> {
  try {
    const answer = await postMakeArea({ area_id: areaId }, fetchImpl);
    // readEnvelope gives a payload only to an OK envelope.
    if (answer.kind !== 'envelope') return null;
    const payload = answer.envelope.payload;
    if (payload?.area_id !== areaId) return null;
    return readableOutline(payload.outline) ? payload.outline : null;
  } catch {
    return null;
  }
}

/** A finite position on the globe: exactly a longitude and a latitude. */
function onGlobe(position: unknown): boolean {
  if (!Array.isArray(position) || position.length !== 2) return false;
  const [longitude, latitude] = position as unknown[];
  return (
    typeof longitude === 'number' &&
    typeof latitude === 'number' &&
    Math.abs(longitude) <= 180 &&
    Math.abs(latitude) <= 90
  );
}

/** Twice the signed area of a closed ring (shoelace); zero when the ring
 * encloses nothing, as for one repeated position or positions on one line. */
function twiceSignedArea(ring: readonly (readonly [number, number])[]): number {
  let sum = 0;
  ring.slice(1).forEach(([x, y], index) => {
    const [px, py] = ring[index] ?? [x, y];
    sum += px * y - x * py;
  });
  return sum;
}

/** A closed linear ring of at least four positions on the globe that encloses
 * some area. */
function closedRing(ring: unknown): boolean {
  if (!Array.isArray(ring) || ring.length < 4 || !ring.every(onGlobe))
    return false;
  const positions = ring as [number, number][];
  const [first, last] = [positions[0], positions.at(-1)];
  return (
    first !== undefined &&
    last !== undefined &&
    first[0] === last[0] &&
    first[1] === last[1] &&
    twiceSignedArea(positions) !== 0
  );
}

/** A drawable outline: every Polygon ring closed and on the globe, or a Circle
 * whose centre is on the globe and whose radius is finite and positive. */
export function readableOutline(outline: AreaOutline): boolean {
  if (outline.type === 'Circle')
    return (
      onGlobe(outline.coordinates) &&
      Number.isFinite(outline.radius_m) &&
      outline.radius_m > 0
    );
  return (
    outline.coordinates.length > 0 && outline.coordinates.every(closedRing)
  );
}

export function readEnvelope(value: unknown, httpStatus = 200): AreaAnswer {
  const malformed: AreaAnswer = {
    kind: 'refused',
    httpStatus,
    code: 'malformed',
  };
  if (!isRecord(value)) return malformed;
  if (
    isRecord(value.error) &&
    Object.keys(value).length === 1 &&
    Object.keys(value.error).sort().join(',') === 'code,error_id,message_key' &&
    typeof value.error.code === 'string' &&
    typeof value.error.error_id === 'string' &&
    typeof value.error.message_key === 'string'
  ) {
    return { kind: 'refused', httpStatus, code: value.error.code };
  }
  if (
    httpStatus !== 200 ||
    Object.keys(value).sort().join(',') !==
      'blocks,call_id,caveat_keys,engine,facts,payload,release_id,status,tool'
  )
    return malformed;
  if (
    value.tool !== 'make_area' ||
    typeof value.call_id !== 'string' ||
    typeof value.release_id !== 'string' ||
    (value.engine !== 'embedded' && value.engine !== 'postgres') ||
    !Array.isArray(value.blocks) ||
    !Array.isArray(value.facts) ||
    !Array.isArray(value.caveat_keys) ||
    value.caveat_keys.some((k) => typeof k !== 'string') ||
    !readStatus(value.status)
  )
    return malformed;
  const payload = value.status === 'OK' ? readPayload(value.payload) : null;
  if (value.status === 'OK' && !payload) return malformed;
  if (value.status !== 'OK' && value.payload !== null) return malformed;
  return {
    kind: 'envelope',
    envelope: {
      tool: 'make_area',
      call_id: value.call_id,
      engine: value.engine,
      release_id: value.release_id,
      status: value.status as AreaStatus,
      blocks: value.blocks,
      facts: value.facts,
      caveat_keys: value.caveat_keys,
      payload,
    },
  };
}

/** A null anchor_cell stays OK. It is not a refusal. */
export function nullAnchorIsOk(answer: AreaAnswer): boolean {
  if (answer.kind !== 'envelope') return false;
  const envelope = answer.envelope;
  if (envelope.status !== 'OK' || envelope.payload === null) return false;
  return envelope.payload.record.anchor_cell === null;
}

function readStatus(value: unknown): value is AreaStatus {
  return (
    value === 'OK' ||
    value === 'SUPPRESSED' ||
    value === 'OUT_OF_SCOPE' ||
    value === 'NO_DATA'
  );
}

function readPayload(value: unknown): AreaPayload | null {
  if (!isRecord(value)) return null;
  const outline = readOutline(value.outline);
  const areaId = typeof value.area_id === 'string' ? value.area_id : '';
  if (!outline || areaId === '') return null;
  const record = isRecord(value.record) ? value.record : {};
  const anchor = record.anchor_cell;
  return {
    area_id: areaId,
    outline,
    point_feature_ids: readPublicPointIds(value.point_feature_ids),
    units: readUnits(value.units),
    snap_report: value.snap_report ?? null,
    record: {
      anchor_cell: typeof anchor === 'string' ? anchor : null,
      traffic: typeof record.traffic === 'string' ? record.traffic : '',
      shape: typeof record.shape === 'string' ? record.shape : '',
    },
  };
}

function readOutline(value: unknown): AreaOutline | null {
  if (!isRecord(value)) return null;
  if (value.type === 'Polygon' && Array.isArray(value.coordinates)) {
    return {
      type: 'Polygon',
      coordinates: value.coordinates as AreaOutline extends { type: 'Polygon' }
        ? AreaOutline['coordinates']
        : never,
    };
  }
  if (
    value.type === 'Circle' &&
    Array.isArray(value.coordinates) &&
    typeof value.radius_m === 'number'
  ) {
    const pair = value.coordinates;
    if (pair.length !== 2) return null;
    const lon = pair[0];
    const lat = pair[1];
    if (typeof lon !== 'number' || typeof lat !== 'number') return null;
    return {
      type: 'Circle',
      coordinates: [lon, lat],
      radius_m: value.radius_m,
    };
  }
  return null;
}

function readUnits(value: unknown): UnitLists {
  if (!isRecord(value)) return {};
  const units: Record<string, readonly string[]> = {};
  for (const [key, list] of Object.entries(value)) {
    if (!Array.isArray(list)) continue;
    const ids: string[] = [];
    for (const item of list) {
      if (typeof item === 'string') ids.push(item);
    }
    units[key] = ids;
  }
  return units;
}

function readPublicPointIds(value: unknown): PublicPointIds | null {
  if (!isRecord(value)) return null;
  const memberships: Record<string, readonly string[]> = {};
  for (const [key, ids] of Object.entries(value)) {
    if (!Array.isArray(ids) || !ids.every((id) => typeof id === 'string'))
      return null;
    memberships[key] = ids;
  }
  return memberships;
}
