/**
 * Area request bodies from typed inputs only.
 * make_area inputs: docs/08_BACKEND.md section "make_area".
 * A drive body is exactly latitude, longitude, mode and cutoff.
 * make_area `_PIN_KEYS` are flat. Hour fields are S6-T07.
 */
import { DISTANCE_PRESETS, WALK_PRESETS, DRIVE_PRESETS } from './presets';

export interface PinInput {
  latitude: number;
  longitude: number;
}

export type AreaMode = 'distance' | 'walk' | 'drive';

/** Flat pin request. A nested `pin` object is not a make_area body. */
export interface PinBody {
  latitude: number;
  longitude: number;
  mode: AreaMode;
  cutoff: number;
}

export interface ShapeGeometryBody {
  geometry: {
    type: 'Polygon';
    coordinates: readonly [readonly (readonly [number, number])[]];
  };
}

export interface ShapeIdBody {
  shape_id: string;
}

/** The gazetteer key is opaque. Its coordinates come only from make_area. */
export interface PlaceBody {
  place_key: string;
  mode: AreaMode;
  cutoff: number;
}

export function assemblePlaceBody(
  placeKey: string,
  presetId: string,
): PlaceBody | null {
  if (
    !/^(?:[A-Za-z][A-Za-z0-9-]*|(?:district|zone|municipality):[A-Za-z0-9][A-Za-z0-9_-]*)$/.test(
      placeKey,
    ) ||
    /(?<![0-9])(?:[0-9]{8}|[0-9]{11})(?![0-9])/.test(placeKey)
  )
    return null;
  const preset = [...DISTANCE_PRESETS, ...WALK_PRESETS, ...DRIVE_PRESETS].find(
    (item) => item.id === presetId,
  );
  if (!preset) return null;
  return { place_key: placeKey, mode: preset.mode, cutoff: preset.cutoff };
}

export type AssembleRefusal = 'extra_field' | 'mode' | 'cutoff' | 'ring';

const DISTANCE_M = new Set([250, 500, 1000]);
const TRAVEL_MIN = new Set([5, 10, 15]);
const PIN_KEYS = ['cutoff', 'latitude', 'longitude', 'mode'] as const;
const BANNED = ['situation', 'summer', 'hour_key', 'day_key'] as const;

export function assemblePinBody(
  pin: PinInput,
  mode: AreaMode,
  cutoff: number,
): { ok: true; body: PinBody } | { ok: false; reason: AssembleRefusal } {
  if (mode !== 'distance' && mode !== 'walk' && mode !== 'drive') {
    return { ok: false, reason: 'mode' };
  }
  const allowed = mode === 'distance' ? DISTANCE_M : TRAVEL_MIN;
  if (!allowed.has(cutoff)) return { ok: false, reason: 'cutoff' };
  const body: PinBody = {
    latitude: pin.latitude,
    longitude: pin.longitude,
    mode,
    cutoff,
  };
  if (!driveBodyExact(body) && mode === 'drive') {
    return { ok: false, reason: 'extra_field' };
  }
  return { ok: true, body };
}

/** Drive chips call this. It has no hour, situation or day parameter. */
export function assembleDriveBody(pin: PinInput, cutoff: number): PinBody {
  const assembled = assemblePinBody(pin, 'drive', cutoff);
  if (!assembled.ok) {
    throw new Error('drive cutoff is outside the closed list');
  }
  return assembled.body;
}

export function driveBodyExact(body: object): boolean {
  if ('pin' in body) return false;
  const keys = Object.keys(body).sort();
  if (keys.length !== PIN_KEYS.length) return false;
  for (let index = 0; index < PIN_KEYS.length; index += 1) {
    if (keys[index] !== PIN_KEYS[index]) return false;
  }
  const record = body as Record<string, unknown>;
  return BANNED.every((name) => !(name in record));
}

export function assembleShapeBody(
  vertices: readonly PinInput[],
):
  | { ok: true; body: ShapeGeometryBody }
  | { ok: false; reason: AssembleRefusal } {
  if (vertices.length < 3) return { ok: false, reason: 'ring' };
  const ring = vertices.map(
    (vertex) => [vertex.longitude, vertex.latitude] as const,
  );
  const first = ring[0];
  if (!first) return { ok: false, reason: 'ring' };
  return {
    ok: true,
    body: {
      geometry: {
        type: 'Polygon',
        coordinates: [[...ring, first]],
      },
    },
  };
}

export function assembleShapeIdBody(shapeId: string): ShapeIdBody {
  return { shape_id: shapeId };
}
