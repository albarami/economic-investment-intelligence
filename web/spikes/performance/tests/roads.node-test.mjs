import assert from 'node:assert/strict';
import fs from 'node:fs';
import { test } from 'node:test';
import { buildRoadData } from '../build-road-data.mjs';
import { generateRoads, bandsAt, playbackState } from '../roads.mjs';
import {
  ROAD_LOADS,
  HOUR_HOLD_MS,
  SCENE_MS,
  VOLUME_BANDS,
} from '../config.mjs';
const data = JSON.parse(
  fs.readFileSync(new URL('../road-data.json', import.meta.url)),
);
const source = JSON.parse(
  fs.readFileSync(
    new URL(
      '../../../../product/tests/fixtures/areas_spike/assignment/hourly_rows.json',
      import.meta.url,
    ),
  ),
);
const graph = JSON.parse(
  fs.readFileSync(
    new URL(
      '../../../../product/tests/fixtures/areas_spike/assignment/hourly_roads.json',
      import.meta.url,
    ),
  ),
);

test('the page payload rebuilds byte for byte from the recorded assignment', async () => {
  assert.equal(
    await buildRoadData(),
    fs.readFileSync(new URL('../road-data.json', import.meta.url), 'utf8'),
  );
  assert.deepEqual(data.header, source.header);
  assert.deepEqual(data.rows, source.rows);
  assert.deepEqual(data.roads, graph);
  assert.notEqual(
    await buildRoadData(),
    (await buildRoadData()).replace('Simulated', 'Public'),
  );
});
for (const count of Object.values(ROAD_LOADS)) {
  test(`the seeded road load of ${count} preserves the fixture cycle and counts`, () => {
    const roads = generateRoads(data, count);
    assert.equal(roads.length, count + graph.links.length);
    assert.deepEqual(roads, generateRoads(data, count));
    const hours = [...new Set(source.rows.map((row) => row.hour))].sort(
      (a, b) => a - b,
    );
    const states = [];
    for (const hour of hours) {
      const bands = bandsAt(roads, hour);
      const expected = graph.links.map(
        (link) =>
          source.rows.find(
            (row) => row.link_id === link.link_id && row.hour === hour,
          )?.volume_band ?? VOLUME_BANDS[0],
      );
      assert.deepEqual(bands.slice(0, graph.links.length), expected);
      for (let index = graph.links.length; index < roads.length; index++) {
        assert.equal(
          bands[index],
          expected[(index - graph.links.length) % graph.links.length],
        );
        assert.equal(
          roads[index].roadClass,
          graph.links[(index - graph.links.length) % graph.links.length]
            .road_class,
        );
        assert.equal(roads[index].provenance, 'Simulated');
        assert.equal(Object.hasOwn(roads[index], 'name'), false);
      }
      states.push(JSON.stringify(expected));
    }
    assert.ok(new Set(states).size > 1);
    assert.deepEqual(data.hours, hours);
  });
}
test('playback holds, cross-fades stored endpoints and stops at the last hour', () => {
  const hours = data.hours;
  const step = HOUR_HOLD_MS + SCENE_MS;
  for (let index = 0; index < hours.length - 1; index++) {
    assert.deepEqual(playbackState(hours, index * step), {
      index,
      next: index,
      blend: 0,
      ended: false,
    });
    assert.deepEqual(
      playbackState(hours, index * step + HOUR_HOLD_MS + SCENE_MS / 2),
      { index, next: index + 1, blend: 0.5, ended: false },
    );
    assert.equal(playbackState(hours, (index + 1) * step).index, index + 1);
  }
  const last = hours.length - 1;
  assert.deepEqual(playbackState(hours, hours.length * step), {
    index: last,
    next: last,
    blend: 0,
    ended: true,
  });
});

test('rendered road counts exclude path padding, hidden layers and empty paths', async () => {
  const { drawnRoadCount } = await import('../roads.mjs');
  const layer = {
    props: { visible: true },
    state: {
      pathTesselator: {
        vertexStarts: [0, 2, 2, 4],
        getPathSegmentIndices: (index) => (index === 1 ? [] : [index]),
      },
    },
  };
  assert.equal(drawnRoadCount(layer), 2);
  layer.props.visible = false;
  assert.equal(drawnRoadCount(layer), 0);
});

test('configuration follows the owner sizes, design timing and closed parameter band list', () => {
  assert.deepEqual(Object.values(ROAD_LOADS), [100000, 250000]);
  assert.equal(HOUR_HOLD_MS, 2500);
  assert.equal(SCENE_MS, 800);
  const parameters = JSON.parse(
    fs.readFileSync(
      new URL(
        '../../../../custodian/tests/fixtures/assignment_spike/parameters_v1.json',
        import.meta.url,
      ),
    ),
  );
  assert.deepEqual(
    VOLUME_BANDS,
    Array.from(
      { length: Number(parameters.band_count.value) },
      (_, index) => `vb${index + 1}`,
    ),
  );
});

test('the named regeneration command writes exactly the canonical payload', async () => {
  const { spawnSync } = await import('node:child_process');
  const { fileURLToPath } = await import('node:url');
  const script = fileURLToPath(
    new URL('../build-road-data.mjs', import.meta.url),
  );
  const result = spawnSync(
    process.execPath,
    [
      '--input-type=module',
      '--eval',
      `
    import fs from 'node:fs';
    import {pathToFileURL} from 'node:url';
    fs.writeFileSync=(destination, text)=>{
      if (!String(destination).endsWith('/road-data.json')) throw new Error('wrong page payload destination');
      process.stdout.write(text);
    };
    await import(pathToFileURL(process.argv[1]));
  `,
      script,
    ],
    { encoding: 'utf8' },
  );
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout, await buildRoadData());
});

for (const patch of [{ day_type: 'weekend' }, { summer: true }]) {
  test(`page payload refuses another situation ${JSON.stringify(patch)}`, async () => {
    const { mkdtempSync, writeFileSync, rmSync } = fs;
    const { tmpdir } = await import('node:os');
    const { join } = await import('node:path');
    const { pathToFileURL } = await import('node:url');
    const folder = mkdtempSync(join(tmpdir(), 'synthetic-road-input-'));
    try {
      const recorded = structuredClone(source);
      Object.assign(recorded.rows[0], patch);
      writeFileSync(join(folder, 'hourly_rows.json'), JSON.stringify(recorded));
      writeFileSync(join(folder, 'hourly_roads.json'), JSON.stringify(graph));
      await assert.rejects(
        buildRoadData(pathToFileURL(folder + '/')),
        /row 0.*weekday.*summer/,
      );
    } finally {
      rmSync(folder, { recursive: true });
    }
  });
}
