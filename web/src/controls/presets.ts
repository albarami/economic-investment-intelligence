/**
 * Closed area chips. Labels reach the screen only through the Fact chip family.
 * The third distance label follows docs/10_FRONTEND.md "Area controls".
 */
import type { AreaMode } from './area-request';

export interface AreaPreset {
  id: string;
  mode: AreaMode;
  cutoff: number;
  value: number;
  unit: 'metres' | 'kilometres' | 'minutes';
  recordId: string;
}

export const DISTANCE_PRESETS: readonly AreaPreset[] = [
  {
    id: 'distance-a',
    mode: 'distance',
    cutoff: 250,
    value: 250,
    unit: 'metres',
    recordId: 'preset-distance-a',
  },
  {
    id: 'distance-b',
    mode: 'distance',
    cutoff: 500,
    value: 500,
    unit: 'metres',
    recordId: 'preset-distance-b',
  },
  {
    id: 'distance-c',
    mode: 'distance',
    cutoff: 1000,
    value: 1,
    unit: 'kilometres',
    recordId: 'preset-distance-c',
  },
];

export const WALK_PRESETS: readonly AreaPreset[] = [
  {
    id: 'walk-a',
    mode: 'walk',
    cutoff: 5,
    value: 5,
    unit: 'minutes',
    recordId: 'preset-walk-a',
  },
  {
    id: 'walk-b',
    mode: 'walk',
    cutoff: 10,
    value: 10,
    unit: 'minutes',
    recordId: 'preset-walk-b',
  },
  {
    id: 'walk-c',
    mode: 'walk',
    cutoff: 15,
    value: 15,
    unit: 'minutes',
    recordId: 'preset-walk-c',
  },
];

export const DRIVE_PRESETS: readonly AreaPreset[] = [
  {
    id: 'drive-a',
    mode: 'drive',
    cutoff: 5,
    value: 5,
    unit: 'minutes',
    recordId: 'preset-drive-a',
  },
  {
    id: 'drive-b',
    mode: 'drive',
    cutoff: 10,
    value: 10,
    unit: 'minutes',
    recordId: 'preset-drive-b',
  },
  {
    id: 'drive-c',
    mode: 'drive',
    cutoff: 15,
    value: 15,
    unit: 'minutes',
    recordId: 'preset-drive-c',
  },
];

export function presetsFor(
  tool: 'polygon' | 'radius' | 'travel' | null,
): readonly AreaPreset[] {
  if (tool === 'radius') return DISTANCE_PRESETS;
  if (tool === 'travel') return [...WALK_PRESETS, ...DRIVE_PRESETS];
  return [];
}
