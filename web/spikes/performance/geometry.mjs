import {
  cellToLatLng,
  getResolution,
  gridDisk,
  isPentagon,
  latLngToCell,
} from 'h3-js';
import {
  HEXAGON_COUNT,
  HEXAGON_RESOLUTION,
  PARTICLE_COUNT,
  SCENE_CENTER,
  SEED,
} from './config.mjs';

/** Ring whose disk holds 3 * k * (k + 1) + 1 cells, just above the gate count. */
const DISK_RING = 191;
const MOTION_PERIOD_MS = 4000;

let hexagonCache;

export function random(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

export function includeCell(cell, seen, resolution) {
  if (!cell || seen.has(cell)) return false;
  if (isPentagon(cell)) return false;
  if (getResolution(cell) !== resolution) return false;
  return true;
}

export function separateDestination(destIndex, originIndex, length) {
  if (destIndex === originIndex) return (destIndex + 1) % length;
  return destIndex;
}

export function generateHexagons() {
  if (hexagonCache) return hexagonCache;
  const origin = latLngToCell(
    SCENE_CENTER[1],
    SCENE_CENTER[0],
    HEXAGON_RESOLUTION,
  );
  const disk = gridDisk(origin, DISK_RING);
  const cells = [];
  const seen = new Set();
  for (const cell of disk) {
    if (!includeCell(cell, seen, HEXAGON_RESOLUTION)) continue;
    seen.add(cell);
    cells.push(cell);
    if (cells.length === HEXAGON_COUNT) break;
  }
  if (cells.length !== HEXAGON_COUNT) {
    throw new Error(`hexagon generator stopped at ${cells.length}`);
  }
  hexagonCache = cells;
  return cells;
}

export function generateParticles(cells) {
  const next = random(SEED);
  const particles = [];
  for (let index = 0; index < PARTICLE_COUNT; index += 1) {
    const originIndex = Math.floor(next() * cells.length);
    const destIndex = separateDestination(
      Math.floor(next() * cells.length),
      originIndex,
      cells.length,
    );
    const origin = cellToLatLng(cells[originIndex]);
    const dest = cellToLatLng(cells[destIndex]);
    const phase = next();
    particles.push({
      originLng: origin[1],
      originLat: origin[0],
      destLng: dest[1],
      destLat: dest[0],
      phase,
      position: [origin[1], origin[0]],
    });
  }
  return particles;
}

export function placeParticles(particles, timeMs) {
  const unit = (((timeMs / MOTION_PERIOD_MS) % 1) + 1) % 1;
  for (const particle of particles) {
    const along = (unit + particle.phase) % 1;
    particle.position[0] =
      particle.originLng + (particle.destLng - particle.originLng) * along;
    particle.position[1] =
      particle.originLat + (particle.destLat - particle.originLat) * along;
  }
}
