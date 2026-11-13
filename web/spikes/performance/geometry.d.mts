export type ParticlePoint = {
  position: [number, number];
  originLng: number;
  originLat: number;
  destLng: number;
  destLat: number;
  phase: number;
};

export function generateHexagons(): string[];
export function generateParticles(cells: string[]): ParticlePoint[];
export function placeParticles(
  particles: ParticlePoint[],
  timeMs: number,
): void;
