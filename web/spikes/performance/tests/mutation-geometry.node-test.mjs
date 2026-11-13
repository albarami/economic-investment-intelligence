import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import {
  random,
  generateHexagons,
  generateParticles,
  placeParticles,
} from '../geometry.mjs';
import { generateRoads, playbackState } from '../roads.mjs';
import { buildRoadData } from '../build-road-data.mjs';
import {
  ROAD_DASH,
  profileDuration,
  SCENE_CENTER,
  ROAD_EXTENT,
  ROAD_SEGMENT,
} from '../config.mjs';
import data from '../road-data.json' with { type: 'json' };

// BigInt implements unsigned modular arithmetic independently of Math.imul.
function referenceRandom(seed) {
  const mask = (1n << 32n) - 1n;
  let state = BigInt(seed) & mask;
  return () => {
    state = (state + 0x6d2b79f5n) & mask;
    let value = ((state ^ (state >> 15n)) * (state | 1n)) & mask;
    value =
      (value ^
        ((value + (((value ^ (value >> 7n)) * (value | 61n)) & mask)) & mask)) &
      mask;
    return Number((value ^ (value >> 14n)) & mask) / 2 ** 32;
  };
}
test('random words agree with unsigned independent modular arithmetic', () => {
  for (const seed of [0, 1, -1, 17]) {
    const actual = random(seed),
      reference = referenceRandom(seed);
    for (let i = 0; i < 20; i++) assert.equal(actual(), reference());
  }
});
test('roads preserve literal fixture coordinates and independently seeded geometry', () => {
  const roads = generateRoads(data, 12);
  const nodes = new Map(
    data.roads.nodes.map((n) => [n.id, [Number(n.lon), Number(n.lat)]]),
  );
  for (const [i, link] of data.roads.links.entries())
    assert.deepEqual(roads[i].path, [
      nodes.get(link.source),
      nodes.get(link.target),
    ]);
  const next = referenceRandom(1);
  for (const road of roads.slice(data.roads.links.length)) {
    const lng =
      SCENE_CENTER[0] + (next() * 2 - 1) * (ROAD_EXTENT - ROAD_SEGMENT);
    const lat =
      SCENE_CENTER[1] + (next() * 2 - 1) * (ROAD_EXTENT - ROAD_SEGMENT);
    const theta = next() * Math.PI * 2;
    assert.deepEqual(road.path, [
      [lng, lat],
      [
        lng + Math.cos(theta) * ROAD_SEGMENT,
        lat + Math.sin(theta) * ROAD_SEGMENT,
      ],
    ]);
  }
});
test('hexagons reuse the cache and particles start at their independent selected origin', async () => {
  const { cellToLatLng } = await import('h3-js');
  const cells = generateHexagons();
  assert.equal(generateHexagons(), cells);
  const particles = generateParticles(cells.slice(0, 4));
  const next = referenceRandom(1);
  for (const particle of particles.slice(0, 20)) {
    const originIndex = Math.floor(next() * 4);
    let destination = Math.floor(next() * 4);
    if (destination === originIndex) destination = (destination + 1) % 4;
    const phase = next();
    const [lat, lng] = cellToLatLng(cells[originIndex]);
    const [dlat, dlng] = cellToLatLng(cells[destination]);
    assert.deepEqual(particle, {
      originLng: lng,
      originLat: lat,
      destLng: dlng,
      destLat: dlat,
      phase,
      position: [lng, lat],
    });
  }
});
test('particle interpolation has literal endpoints and negative-time wrap', () => {
  for (const [time, expected] of [
    [0, [5, 7]],
    [1000, [8, 10]],
    [-1000, [2, 4]],
    [4000, [5, 7]],
    [8000, [5, 7]],
  ]) {
    const particle = {
      originLng: 2,
      originLat: 4,
      destLng: 14,
      destLat: 16,
      phase: 0.25,
      position: [0, 0],
    };
    placeParticles([particle], time);
    assert.deepEqual(particle.position, expected);
  }
});
test('profile durations and static dash are closed settings', () => {
  assert.deepEqual(ROAD_DASH, [3, 2]);
  assert.equal(profileDuration('gate'), 30000);
  assert.equal(profileDuration('smoke'), 400);
  assert.equal(profileDuration('unknown'), null);
});
test('the exact hold boundary retains the stored endpoint', () => {
  assert.deepEqual(playbackState([5, 8], 2500), {
    index: 0,
    next: 0,
    blend: 0,
    ended: false,
  });
});
test('payload hours sort numerically despite reversed source rows', async () => {
  const folder = fs.mkdtempSync(
    path.join(os.tmpdir(), 'synthetic-hour-order-'),
  );
  try {
    fs.writeFileSync(
      path.join(folder, 'hourly_rows.json'),
      JSON.stringify({ header: data.header, rows: [...data.rows].reverse() }),
    );
    fs.writeFileSync(
      path.join(folder, 'hourly_roads.json'),
      JSON.stringify(data.roads),
    );
    assert.deepEqual(
      JSON.parse(await buildRoadData(pathToFileURL(folder + '/'))).hours,
      [...data.hours],
    );
  } finally {
    fs.rmSync(folder, { recursive: true, force: true });
  }
});
test('importing the payload builder never writes a page artifact', () => {
  const script = new URL('../build-road-data.mjs', import.meta.url).href;
  const result = spawnSync(
    process.execPath,
    [
      '--input-type=module',
      '--eval',
      `import fs from 'node:fs'; fs.writeFileSync=()=>{throw new Error('unexpected artifact write')}; await import(${JSON.stringify(script)});`,
    ],
    { encoding: 'utf8' },
  );
  assert.equal(result.status, 0, result.stderr);
});
