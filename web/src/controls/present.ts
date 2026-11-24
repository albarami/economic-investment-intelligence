/**
 * What the screen keeps after make_area.
 * A null anchor is an OK answer. A browser circle is never invented.
 */
import type { AreaOutline, AreaAnswer, AreaStatus } from '../api/areas';
import type { AreaMode, PinInput } from './area-request';

export type LineKind = 'accent' | 'strong' | 'none';

export interface Presented {
  namedPlace?: boolean;
  status: AreaStatus | 'INVALID_ARGUMENT';
  caveatKeys: readonly string[];
  line: LineKind;
  outline: AreaOutline | null;
  ownRing: readonly PinInput[];
  showPin: boolean;
  showRefusal: boolean;
  showSummary: boolean;
  showLayers: boolean;
  anchorCell: string | null;
  shapeKind: 'polygon' | 'radius' | 'walk' | 'drive';
  mode: AreaMode | null;
  cutoff: number | null;
  freeFlow: boolean;
}

export interface PresentRequest {
  kind: 'polygon' | 'pin' | 'place';
  mode: AreaMode | null;
  cutoff: number | null;
  ownRing: readonly PinInput[];
  pin: PinInput | null;
}

export function presentAnswer(
  answer: AreaAnswer,
  request: PresentRequest,
): Presented {
  const envelope =
    answer.kind === 'envelope'
      ? answer.envelope
      : { status: 'INVALID_ARGUMENT' as const, caveat_keys: [], payload: null };
  const shapeKind =
    request.kind === 'polygon' ? 'polygon' : shapeOf(request.mode);
  const base = {
    ...(request.kind === 'place' ? { namedPlace: true } : {}),
    status: envelope.status,
    caveatKeys: envelope.caveat_keys,
    ownRing: request.kind === 'polygon' ? request.ownRing : [],
    anchorCell: envelope.payload?.record.anchor_cell ?? null,
    shapeKind,
    mode: request.kind === 'polygon' ? null : request.mode,
    cutoff: request.kind === 'polygon' ? null : request.cutoff,
    freeFlow: request.mode === 'drive' && envelope.status === 'OK',
  } as const;
  if (envelope.status === 'OK' && envelope.payload) {
    return {
      ...base,
      line: 'accent',
      outline: envelope.payload.outline,
      showPin: request.pin !== null,
      showRefusal: false,
      showSummary: true,
      showLayers: true,
    };
  }
  if (envelope.status === 'NO_DATA') {
    return {
      ...base,
      line: 'none',
      outline: null,
      showPin: request.pin !== null,
      showRefusal: true,
      showSummary: true,
      showLayers: false,
      freeFlow: false,
    };
  }
  const refusedPolygon = request.kind === 'polygon';
  return {
    ...base,
    line: refusedPolygon ? 'strong' : 'none',
    outline: null,
    showPin: request.pin !== null,
    showRefusal: true,
    showSummary: true,
    showLayers: false,
    freeFlow: false,
  };
}

export function reasonTextKey(
  presented: Presented,
):
  | 'draw.reason.noData'
  | 'draw.reason.outOfScope'
  | 'draw.reason.shortRing'
  | 'draw.reason.invalid' {
  if (presented.status === 'NO_DATA') return 'draw.reason.noData';
  if (presented.status === 'OUT_OF_SCOPE') return 'draw.reason.outOfScope';
  if (presented.shapeKind === 'polygon' && presented.ownRing.length < 3) {
    return 'draw.reason.shortRing';
  }
  return 'draw.reason.invalid';
}

function shapeOf(mode: AreaMode | null): 'radius' | 'walk' | 'drive' {
  if (mode === 'walk') return 'walk';
  if (mode === 'drive') return 'drive';
  return 'radius';
}
