/**
 * Resolution-8 night-light cells become their resolution-9 children.
 * The parent fact id is copied. No radiance value is averaged or split.
 */
import { cellToChildren, getResolution } from 'h3-js';

const PARENT_RESOLUTION = 8;
const CHILD_RESOLUTION = 9;

export interface NightCell {
  cell: string;
  resolution: 8 | 9;
  factId: string;
}

export interface DrawnHex {
  cell: string;
  factId: string;
}

export function expandNightCells(cells: readonly NightCell[]): {
  ok: true;
  cells: DrawnHex[];
} {
  const drawn: DrawnHex[] = [];
  for (const cell of cells) {
    if (cell.resolution === PARENT_RESOLUTION) {
      for (const child of cellToChildren(cell.cell, CHILD_RESOLUTION)) {
        drawn.push({ cell: child, factId: cell.factId });
      }
    } else {
      drawn.push({ cell: cell.cell, factId: cell.factId });
    }
  }
  return { ok: true, cells: drawn };
}

export function guardHexResolution(
  cells: readonly string[],
): { ok: true } | { ok: false; code: 'mixed_resolution' } {
  const resolutions = new Set(cells.map((cell) => getResolution(cell)));
  if (resolutions.size !== 1 || !resolutions.has(CHILD_RESOLUTION)) {
    return { ok: false, code: 'mixed_resolution' };
  }
  return { ok: true };
}
