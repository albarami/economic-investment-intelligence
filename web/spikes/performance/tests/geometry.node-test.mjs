import assert from 'node:assert/strict';
import { test } from 'node:test';
import { getPentagons, getResolution, isPentagon, latLngToCell } from 'h3-js';
import {
  HEXAGON_COUNT,
  HEXAGON_RESOLUTION,
  PARTICLE_COUNT,
  SCENE_CENTER,
} from '../config.mjs';
import {
  generateHexagons,
  generateParticles,
  includeCell,
  placeParticles,
  separateDestination,
} from '../geometry.mjs';

test('the hexagon generator returns the gate count at one resolution', () => {
  const cells = generateHexagons();
  const again = generateHexagons();
  assert.equal(cells.length, HEXAGON_COUNT);
  assert.equal(again[0], cells[0]);
  assert.equal(again[HEXAGON_COUNT - 1], cells[HEXAGON_COUNT - 1]);
  assert.equal(new Set(cells).size, HEXAGON_COUNT);
  for (const cell of [cells[0], cells[HEXAGON_COUNT - 1]]) {
    assert.equal(getResolution(cell), HEXAGON_RESOLUTION);
    assert.equal(isPentagon(cell), false);
  }
  const pentagon = getPentagons(HEXAGON_RESOLUTION)[0];
  assert.equal(includeCell(pentagon, new Set(), HEXAGON_RESOLUTION), false);
  assert.equal(includeCell(cells[0], new Set(), HEXAGON_RESOLUTION), true);
  assert.equal(
    includeCell(cells[0], new Set([cells[0]]), HEXAGON_RESOLUTION),
    false,
  );
  const coarse = latLngToCell(SCENE_CENTER[1], SCENE_CENTER[0], 1);
  assert.equal(includeCell(coarse, new Set(), HEXAGON_RESOLUTION), false);
  assert.equal(separateDestination(3, 3, 10), 4);
  assert.equal(separateDestination(2, 3, 10), 2);
});

test('particles move with time and repeat the same seed', () => {
  const cells = generateHexagons();
  const particles = generateParticles(cells);
  const again = generateParticles(cells);
  assert.equal(particles.length, PARTICLE_COUNT);
  assert.equal(again[0].originLng, particles[0].originLng);
  assert.notEqual(particles[0].originLng, particles[0].destLng);
  const start = particles[0].position[0];
  placeParticles(particles, 0);
  const atZero = particles[0].position[0];
  placeParticles(particles, 1000);
  assert.notEqual(particles[0].position[0], start);
  assert.notEqual(particles[0].position[0], atZero);
  const moved = particles[0].position[0];
  placeParticles(particles, 1000);
  assert.equal(particles[0].position[0], moved);
});
