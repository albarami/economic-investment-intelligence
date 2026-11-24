import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { gunzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { decodeTile } from '../mvt.mjs';
import { RELEASE_BLOCK, startLookServer } from '../server.mjs';

const ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../../..',
);
const SCRIPT = path.join(ROOT, 'web/spikes/look/tools/build_buildings.py');

function square(lon, lat, span) {
  return [
    [lon, lat],
    [lon + span, lat],
    [lon + span, lat + span],
    [lon, lat + span],
    [lon, lat],
  ];
}

test('a fixture of invented footprints carries measured, floor and area heights', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-buildings-'));
  const fixture = path.join(dir, 'footprints.geojson');
  const output = path.join(dir, 'data', 'basemap', 'buildings.pmtiles');
  const document = {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { id: 'measured', height: 22, num_floors: null },
        geometry: {
          type: 'Polygon',
          coordinates: [square(51.53, 25.32, 0.0004)],
        },
      },
      {
        type: 'Feature',
        properties: { id: 'floors', height: null, num_floors: 4 },
        geometry: {
          type: 'Polygon',
          coordinates: [square(51.532, 25.32, 0.0004)],
        },
      },
      {
        type: 'Feature',
        properties: { id: 'small', height: null, num_floors: null },
        geometry: {
          type: 'Polygon',
          coordinates: [square(51.534, 25.32, 0.00004)],
        },
      },
      {
        type: 'Feature',
        properties: { id: 'large', height: null, num_floors: null },
        geometry: { type: 'Polygon', coordinates: [square(51.5, 25.3, 0.02)] },
      },
    ],
  };
  fs.writeFileSync(fixture, JSON.stringify(document));
  const result = spawnSync(
    'uv',
    [
      'run',
      '--locked',
      'python',
      SCRIPT,
      '--input',
      fixture,
      '--output',
      output,
      '--min-zoom',
      '15',
      '--max-zoom',
      '15',
    ],
    { cwd: ROOT, encoding: 'utf8' },
  );
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  assert.match(result.stdout, /tiles [1-9]/);
  const database = path.join(dir, 'data', 'basemap', 'buildings.mbtiles');
  const blobs = path.join(dir, 'blobs');
  const dumped = spawnSync(
    'uv',
    [
      'run',
      '--locked',
      'python',
      '-c',
      'import pathlib, sqlite3, sys\n' +
        'db = sqlite3.connect(sys.argv[1])\n' +
        'out = pathlib.Path(sys.argv[2])\n' +
        'out.mkdir(parents=True)\n' +
        'rows = db.execute("select tile_data from tiles")\n' +
        'for index, (blob,) in enumerate(rows):\n' +
        '    (out / f"{index}.bin").write_bytes(blob)\n',
      database,
      blobs,
    ],
    { cwd: ROOT, encoding: 'utf8' },
  );
  assert.equal(dumped.status, 0, dumped.stderr);
  const heights = new Set();
  for (const name of fs.readdirSync(blobs)) {
    const raw = gunzipSync(fs.readFileSync(path.join(blobs, name)));
    const layer = decodeTile(raw, ['buildings']).buildings;
    for (const feature of layer?.features ?? []) {
      heights.add(Math.round(Number(feature.properties.height) * 10) / 10);
    }
  }
  assert.ok(heights.has(22), [...heights].join(','));
  assert.ok(heights.has(12.8), [...heights].join(','));
  assert.ok(heights.has(6), [...heights].join(','));
  assert.ok(heights.has(36), [...heights].join(','));
  assert.ok(fs.statSync(output).size > 0);
  fs.rmSync(dir, { recursive: true, force: true });
});

test('the page serves the building archive with a byte range', async () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-repo-'));
  const page = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-page-'));
  const folder = path.join(repo, 'data', 'basemap');
  fs.mkdirSync(folder, { recursive: true });
  const archive = path.join(folder, 'overture-buildings-fixture.pmtiles');
  fs.writeFileSync(archive, Buffer.from('abcdefghijklmnopqrstuvwxyz'));
  fs.writeFileSync(
    path.join(page, 'index.html'),
    `<!doctype html><html><body>${RELEASE_BLOCK}</body></html>`,
  );
  const server = await startLookServer(page, { repositoryRoot: repo });
  try {
    const body = await getRange(
      server.origin,
      '/basemap/buildings.pmtiles',
      'bytes=0-3',
    );
    assert.equal(body.status, 206);
    assert.equal(body.text, 'abcd');
  } finally {
    await server.close();
    fs.rmSync(repo, { recursive: true, force: true });
    fs.rmSync(page, { recursive: true, force: true });
  }
});

function getRange(origin, pathname, range) {
  return new Promise((resolve, reject) => {
    const request = http.get(
      origin + pathname,
      { headers: { range } },
      (response) => {
        const chunks = [];
        response.on('data', (chunk) => chunks.push(chunk));
        response.on('end', () => {
          resolve({
            status: response.statusCode,
            text: Buffer.concat(chunks).toString('utf8'),
          });
        });
      },
    );
    request.on('error', reject);
  });
}
