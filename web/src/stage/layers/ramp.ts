/**
 * Closed class keys of the five-class ramp (DES-19).
 * A class is supplied. Nothing here chooses a break.
 */

export const CLASS_RAMP = {
  band_low: '--eii-seq-1',
  band_mid_low: '--eii-seq-2',
  band_mid: '--eii-seq-3',
  band_mid_high: '--eii-seq-4',
  band_high: '--eii-seq-5',
} as const;

/** A district count with no tower bands. It is not a step of the ramp. */
export const DISTRICT_COUNT_CLASS = 'district_count';

export function fcFeatureClass(classId: string): boolean {
  return (
    Object.prototype.hasOwnProperty.call(CLASS_RAMP, classId) ||
    classId === DISTRICT_COUNT_CLASS
  );
}

export const DIRECTION_KEYS = ['higher', 'lower', 'equal'] as const;

/** Light-theme bytes of DES-19, used when the token is not on the document. */
const LIGHT_BYTES: Record<string, [number, number, number, number]> = {
  '--eii-seq-1': [0x2f, 0x4a, 0x5e, 255],
  '--eii-seq-2': [0x3f, 0x6f, 0x86, 255],
  '--eii-seq-3': [0x5e, 0x97, 0xa6, 255],
  '--eii-seq-4': [0x9c, 0xc4, 0xbb, 255],
  '--eii-seq-5': [0xeb, 0xe3, 0xb0, 255],
};

export function rampToken(classId: string): string | null {
  if (Object.prototype.hasOwnProperty.call(CLASS_RAMP, classId)) {
    return CLASS_RAMP[classId as keyof typeof CLASS_RAMP];
  }
  return null;
}

export function knownDirection(direction: string): boolean {
  return (DIRECTION_KEYS as readonly string[]).includes(direction);
}

export function fillColor(classId: string): [number, number, number, number] {
  if (classId === DISTRICT_COUNT_CLASS) {
    return LIGHT_BYTES['--eii-seq-3'] ?? [0, 0, 0, 0];
  }
  const token = rampToken(classId);
  if (!token) return [0, 0, 0, 0];
  const painted = readToken(token);
  if (painted) return painted;
  return LIGHT_BYTES[token] ?? [0, 0, 0, 0];
}

/** DES-212 dark-column bytes of `--eii-map-boundary`, used when the token is absent. */
const BOUNDARY_BYTES: [number, number, number, number] = [
  0x66, 0x75, 0x8a, 255,
];

export const OUTLINE_WIDTH_PX = 1;

export function boundaryColor(): [number, number, number, number] {
  return readToken('--eii-map-boundary') ?? BOUNDARY_BYTES;
}

/** Display radii for the firms-per-tower classes. The class arrives supplied. */
const POINT_RADIUS_PX: Record<string, number> = {
  band_low: 6,
  band_mid_low: 9,
  band_mid: 12,
  band_mid_high: 15,
  band_high: 18,
};

export function pointRadiusPx(classId: string): number {
  return POINT_RADIUS_PX[classId] ?? 0;
}

function readToken(token: string): [number, number, number, number] | null {
  if (typeof document === 'undefined') return null;
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue(token)
    .trim();
  const match = /^#([0-9a-fA-F]{6})$/u.exec(raw);
  if (!match?.[1]) return null;
  const hex = match[1];
  return [
    Number.parseInt(hex.slice(0, 2), 16),
    Number.parseInt(hex.slice(2, 4), 16),
    Number.parseInt(hex.slice(4, 6), 16),
    255,
  ];
}
