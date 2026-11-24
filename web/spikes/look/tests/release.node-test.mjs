import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { latLngToCell } from 'h3-js';
import { decodeTile, ringArea, rings } from '../mvt.mjs';
import {
  BASEMAP_HINT,
  BREAKS,
  FLOOR,
  HERO_VALUE,
  buildRelease,
  buildingFloorArea,
  classOf,
  districtLabels,
  inventCells,
  locateBasemap,
  releaseFacts,
  smooth,
  tileOf,
} from '../release-build.mjs';
import {
  RELEASE_ID,
  SHARE_FROM_STEP,
  factView,
  serialiseRelease,
  validateRelease,
} from '../release-shape.mjs';
import { RELEASE_BLOCK, parseRange } from '../server.mjs';
import { startTestServer } from './run.mjs';
import {
  FRAME,
  RESOLUTION,
  STAND_IN_DATE,
  cellsFromCounts,
  registerPeriod,
} from '../register.mjs';

// A small encoder of the Mapbox Vector Tile protocol buffer, enough to
// write one layer of polygons with properties for the decoder to read.
function varint(value) {
  const out = [];
  let rest = value;
  while (rest >= 0x80) {
    out.push((rest % 0x80) | 0x80);
    rest = Math.floor(rest / 0x80);
  }
  out.push(rest);
  return out;
}

function field(number, wire, payload) {
  return [...varint(number * 8 + wire), ...payload];
}

function bytes(number, content) {
  return field(number, 2, [...varint(content.length), ...content]);
}

const encoder = new TextEncoder();

function zigzag(value) {
  return value >= 0 ? value * 2 : -value * 2 - 1;
}

function square(x, y, side) {
  return [
    9,
    zigzag(x),
    zigzag(y),
    (3 << 3) | 2,
    zigzag(side),
    0,
    0,
    zigzag(side),
    zigzag(-side),
    0,
    15,
  ];
}

function encodeTile(name, extent, features) {
  const keys = [];
  const values = [];
  const layer = [...bytes(1, encoder.encode(name))];
  for (const feature of features) {
    const tags = [];
    for (const [key, value] of Object.entries(feature.properties)) {
      let keyIndex = keys.indexOf(key);
      if (keyIndex < 0) keyIndex = keys.push(key) - 1;
      tags.push(keyIndex, values.push(value) - 1);
    }
    const packedTags = tags.flatMap((item) => varint(item));
    const geometry = feature.geometry.flatMap((item) => varint(item));
    layer.push(
      ...bytes(2, [
        ...bytes(2, packedTags),
        ...field(3, 0, varint(3)),
        ...bytes(4, geometry),
      ]),
    );
  }
  for (const key of keys) layer.push(...bytes(3, encoder.encode(key)));
  for (const value of values) {
    const encoded =
      typeof value === 'string'
        ? bytes(1, encoder.encode(value))
        : field(5, 0, varint(value));
    layer.push(...bytes(4, encoded));
  }
  layer.push(...field(5, 0, varint(extent)));
  layer.push(...field(15, 0, varint(2)));
  return Uint8Array.from(bytes(3, layer));
}

test('the vector tile reader decodes a layer, its properties and a square', () => {
  const tile = encodeTile('buildings', 4096, [
    {
      properties: { kind: 'building', height: 35 },
      geometry: square(100, 200, 50),
    },
  ]);
  const layers = decodeTile(tile, ['buildings']);
  const layer = layers.buildings;
  assert.equal(layer.extent, 4096);
  assert.equal(layer.features.length, 1);
  const feature = layer.features[0];
  assert.deepEqual(feature.properties, { kind: 'building', height: 35 });
  const parts = rings(feature.geometry);
  assert.deepEqual(parts[0], [
    [100, 200],
    [150, 200],
    [150, 250],
    [100, 250],
    [100, 200],
  ]);
  assert.equal(Math.abs(ringArea(parts[0])), 2500);
});

test('a layer that is not asked for is named but not decoded', () => {
  const tile = encodeTile('roads', 4096, [
    { properties: { kind: 'major' }, geometry: square(0, 0, 10) },
  ]);
  assert.equal(decodeTile(tile, ['buildings']).roads.features, null);
});

test('a truncated geometry is refused', () => {
  assert.throws(() => rings([9, 2]), /truncated geometry/);
  assert.throws(() => rings([(1 << 3) | 4]), /unknown command/);
});

test('a building counts its footprint times its storeys at its centre', () => {
  const at = tileOf(51.5, 25.3, 15);
  const tile = { x: at.x, y: at.y, z: 15 };
  const feature = {
    type: 3,
    properties: { height: 35 },
    geometry: square(1000, 1000, 400),
  };
  const counted = buildingFloorArea(feature, tile, 4096);
  assert.ok(counted !== null);
  assert.ok(counted.lon > 51.49 && counted.lon < 51.52, String(counted.lon));
  assert.ok(counted.lat > 25.28 && counted.lat < 25.31, String(counted.lat));
  const flat = buildingFloorArea({ ...feature, properties: {} }, tile, 4096);
  assert.ok(flat !== null);
  assert.equal(Math.round(counted.floorArea / flat.floorArea), 10);
  assert.equal(buildingFloorArea({ ...feature, type: 2 }, tile, 4096), null);
});

test('classes follow the fixed breaks', () => {
  assert.deepEqual(BREAKS, [40, 120, 300, 700]);
  assert.equal(classOf(39), 1);
  assert.equal(classOf(40), 2);
  assert.equal(classOf(299), 3);
  assert.equal(classOf(700), 5);
  assert.equal(classOf(HERO_VALUE), 5);
});

const DOHA = latLngToCell(25.32, 51.53, 9);
const NEAR = latLngToCell(25.33, 51.52, 9);
const FAR = latLngToCell(25.25, 51.45, 9);

test('the densest unit carries the hero value, units under the floor stay dark, order is fixed', () => {
  const weights = new Map([
    [FAR, 1],
    [DOHA, 1000],
    [NEAR, 300],
  ]);
  const cells = inventCells(weights);
  const byCell = new Map(cells.map((row) => [row[0], row]));
  assert.equal(byCell.get(DOHA)[1], HERO_VALUE);
  assert.equal(byCell.get(DOHA)[2], 5);
  assert.equal(byCell.has(FAR), false);
  for (const [, value, step] of cells) {
    assert.ok(value >= FLOOR);
    assert.equal(step, classOf(value));
  }
  const sorted = [...cells].sort((a, b) => (a[0] < b[0] ? -1 : 1));
  assert.deepEqual(cells, sorted);
  assert.deepEqual(inventCells(new Map()), []);
});

test('smoothing keeps only cells that hold buildings', () => {
  const smoothed = smooth(new Map([[DOHA, 100]]));
  assert.deepEqual([...smoothed.keys()], [DOHA]);
  assert.ok(smoothed.get(DOHA) < 100);
});

test('the facts are read from the cell table: densest, mean by area, share of the two highest classes', () => {
  const area = () => 0.5;
  const facts = releaseFacts(
    [
      ['a', 1240, 5],
      ['b', 300, 4],
      ['c', 60, 2],
    ],
    area,
  );
  const byId = new Map(facts.map((fact) => [fact.id, fact]));
  assert.equal(byId.get('densest-unit').value, 1240);
  assert.equal(byId.get('areas-with-firms').value, 533);
  assert.equal(byId.get('top-classes').value, 0.96);
  assert.deepEqual(
    BREAKS.map((_, index) => byId.get(`break-${index + 1}`).value),
    BREAKS,
  );
  for (const fact of facts) {
    assert.equal(fact.provenance, 'synthetic');
    assert.deepEqual(fact.input_classes, ['synthetic']);
    assert.equal(fact.chain.source, 'chain.source');
  }
});

test('the extract is found by its pattern, and its absence is named', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-root-'));
  try {
    assert.deepEqual(locateBasemap(root), { ok: false, detail: BASEMAP_HINT });
    const folder = path.join(root, 'data', 'basemap');
    fs.mkdirSync(folder, { recursive: true });
    assert.equal(locateBasemap(root).ok, false);
    fs.writeFileSync(path.join(folder, 'qatar-2026-11-13.pmtiles'), '');
    const found = locateBasemap(root);
    assert.equal(found.ok, true);
    assert.equal(path.basename(found.file), 'qatar-2026-11-13.pmtiles');
    fs.writeFileSync(path.join(folder, 'qatar-2026-11-14.pmtiles'), '');
    assert.match(locateBasemap(root).detail, /more than one extract/);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('without the extract the release falls back to a neutral ground with every fact chained', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-root-'));
  let server;
  try {
    const built = await buildRelease(root);
    assert.equal(built.file, null);
    assert.deepEqual(built.release.basemap, {
      present: false,
      missing: BASEMAP_HINT,
    });
    assert.deepEqual(built.release.layer.cells, []);
    assert.equal(built.release.release_id, RELEASE_ID);
    assert.equal(built.release.facts.length, 4);
    for (const fact of built.release.facts) assert.notEqual(fact.chain, null);

    // L-119 item 3 applies to the browser harness too: its fixed input must
    // not inject cells from the checkout into an empty repository root.
    fs.writeFileSync(path.join(root, 'index.html'), RELEASE_BLOCK);
    server = await startTestServer(root, { repositoryRoot: root });
    assert.equal(server.basemap, false);
    assert.equal(server.release.layer.cells.length, 0);
    assert.equal(server.release.coverage, 'not_measured');
    assert.deepEqual(server.release, built.release);
  } finally {
    if (server) await server.close();
    fs.rmSync(root, { recursive: true, force: true });
  }
});

function release(overrides = {}) {
  return {
    origin: 'synthetic',
    generator: { name: 'chain.pipeline', version: '1.0.0' },
    release_id: RELEASE_ID,
    basemap: { present: false, missing: BASEMAP_HINT },
    layer: {
      id: 'firm_density',
      unit_key: 'unit.firmsPerSqKm',
      provenance: 'synthetic',
      origin: 'synthetic',
      generator: { name: 'chain.pipeline', version: '1.0.0' },
      resolution: 9,
      breaks: BREAKS,
      cells: [[DOHA, 1240, 5]],
    },
    facts: releaseFacts([[DOHA, 1240, 5]]),
    firms: [],
    period: '2026-11-13',
    ...overrides,
  };
}

test('a release of the documented shape is accepted and a fact reads as a chip view', () => {
  const accepted = validateRelease(release());
  const view = factView(accepted.facts[0]);
  assert.equal(view.id, 'densest-unit');
  assert.equal(view.unitKey, 'unit.firmsPerSqKm');
  assert.deepEqual(view.inputClasses, ['synthetic']);
  const firm = {
    name: 'Firm',
    activity: 'Retail',
    size_band: 'small',
    cell: DOHA,
  };
  assert.deepEqual(validateRelease(release({ firms: [firm] })).firms, [firm]);
});

test('a named firm with wages, a wage bill or a headcount is refused (SYN-21)', () => {
  for (const key of ['wages', 'wage_bill', 'headcount']) {
    const firm = {
      name: 'Firm',
      activity: 'Retail',
      size_band: 'small',
      cell: DOHA,
      [key]: 10,
    };
    assert.throws(
      () => validateRelease(release({ firms: [firm] })),
      /carries only name, activity, size band and cell/,
    );
  }
});

test('a release with a wrong class, unit, break order or cell class is refused', () => {
  const facts = releaseFacts([]);
  assert.throws(() =>
    validateRelease(release({ facts: [{ ...facts[0], provenance: 'real' }] })),
  );
  assert.throws(() =>
    validateRelease(release({ facts: [{ ...facts[0], unit: 'metres' }] })),
  );
  assert.throws(() =>
    validateRelease(release({ facts: [facts[0], facts[0]] })),
  );
  assert.throws(() =>
    validateRelease(
      release({
        layer: { ...release().layer, breaks: [40, 300, 120, 700] },
      }),
    ),
  );
  assert.throws(() =>
    validateRelease(
      release({ layer: { ...release().layer, cells: [[DOHA, 1, 9]] } }),
    ),
  );
});

test('the data block cannot be closed early by the release text', () => {
  const text = serialiseRelease(release({ release_id: '</script><script>' }));
  assert.equal(text.includes('</script>'), false);
  assert.equal(JSON.parse(text).release_id, '</script><script>');
});

test('the server reads one byte range and refuses others', () => {
  assert.equal(parseRange(undefined, 100), null);
  assert.deepEqual(parseRange('bytes=0-9', 100), { start: 0, end: 9 });
  assert.deepEqual(parseRange('bytes=90-', 100), { start: 90, end: 99 });
  assert.deepEqual(parseRange('bytes=-10', 100), { start: 90, end: 99 });
  assert.deepEqual(parseRange('bytes=95-200', 100), { start: 95, end: 99 });
  assert.equal(parseRange('bytes=100-', 100), 'bad');
  assert.equal(parseRange('bytes=5-1', 100), 'bad');
  assert.equal(parseRange('bytes=0-1,4-5', 100), 'bad');
  assert.equal(parseRange('items=0-1', 100), 'bad');
});

// Round 5g, findings 14 and 20: the mean is taken over the units that hold
// at least one firm, and the chip says so; a unit with no firm never enters.
test('the mean of the areas with firms leaves out a unit with no firm, and its caption says so', () => {
  const area = () => 0.5;
  const lit = latLngToCell(25.3, 51.5, RESOLUTION);
  const empty = latLngToCell(25.4, 51.45, RESOLUTION);
  assert.ok(FRAME[0] < 51.45 && 25.4 < FRAME[3]);
  const counts = new Map([[lit, 10]]);
  const options = { area, classOf };
  const before = releaseFacts(cellsFromCounts(counts, options), area);
  const withEmpty = cellsFromCounts(new Map([...counts, [empty, 0]]), options);
  assert.equal(withEmpty.length, 1);
  const after = releaseFacts(withEmpty, area);
  const mean = (facts) => facts.find((fact) => fact.id === 'areas-with-firms');
  assert.equal(mean(after).value, mean(before).value);
  const catalogue = JSON.parse(
    fs.readFileSync(new URL('../catalogue.json', import.meta.url), 'utf8'),
  );
  assert.equal(
    catalogue.strings[mean(after).geography_key].en,
    'Areas with firms',
  );
});

// Round 5g, finding 24: the share counts the classes from SHARE_FROM_STEP,
// whose lower bound is the third break the legend marks.
test('the share of the densest areas counts the classes from the 300 break', () => {
  assert.equal(SHARE_FROM_STEP, 4);
  assert.equal(classOf(BREAKS[SHARE_FROM_STEP - 2]), SHARE_FROM_STEP);
  const facts = releaseFacts(
    [
      ['a', 299, classOf(299)],
      ['b', 300, classOf(300)],
    ],
    () => 1,
  );
  assert.equal(facts.find((fact) => fact.id === 'top-classes').value, 0.5);
});

// Round 5g, finding 22: the release names the date of the register count.
test('the stand-in is dated as its README says, and a register file needs its own date', () => {
  const readme = fs.readFileSync(
    new URL('../register/README.md', import.meta.url),
    'utf8',
  );
  assert.match(readme, new RegExp(`\\| Date written \\| ${STAND_IN_DATE} \\|`));
  assert.equal(registerPeriod({ standIn: true }, {}), STAND_IN_DATE);
  assert.throws(
    () => registerPeriod({ standIn: false }, {}),
    /EII_REGISTER_DATE/,
  );
  for (const bad of ['2026-02-30', '2026-13-01', '13/11/2026', ' 2026-11-13']) {
    assert.throws(
      () => registerPeriod({ standIn: false }, { EII_REGISTER_DATE: bad }),
      /EII_REGISTER_DATE/,
      bad,
    );
  }
  assert.equal(
    registerPeriod({ standIn: false }, { EII_REGISTER_DATE: '2025-12-31' }),
    '2025-12-31',
  );
});

// Round 5g, G2: one label per district name inside the frame. Names here are
// invented; the spelling rule is the one the two English forms of one
// Arabic name need.
function labelCandidate(over = {}) {
  return {
    kind: 'neighbourhood',
    name_en: '',
    name_ar: '',
    lon: 51.5,
    lat: 25.3,
    min_zoom: 13,
    sort_key: 1,
    zoom: 13,
    ...over,
  };
}

test('one Arabic name with two English spellings gives one label, spelled as the lower min zoom', () => {
  const labels = districtLabels(
    [
      labelCandidate({
        name_en: 'Baeward',
        name_ar: 'حي المثال',
        min_zoom: 14,
        lon: 51.51,
        lat: 25.33,
      }),
      labelCandidate({
        name_en: 'Bayward',
        name_ar: 'حي المثال',
        min_zoom: 12,
        lon: 51.5,
        lat: 25.32,
      }),
    ],
    null,
  );
  assert.equal(labels.length, 1);
  assert.equal(labels[0].en, 'Bayward');
  assert.equal(labels[0].ar, 'حي المثال');
  assert.equal(labels[0].min_zoom, 12);
});

test('the same district name twice gives one label', () => {
  const labels = districtLabels(
    [
      labelCandidate({ name_en: 'Bayward', name_ar: 'حي المثال' }),
      labelCandidate({
        name_en: 'Bayward',
        name_ar: 'حي المثال',
        lon: 51.51,
        lat: 25.31,
      }),
    ],
    null,
  );
  assert.equal(labels.length, 1);
});

test('an English-only district is kept and grouped by its English name', () => {
  const labels = districtLabels(
    [
      labelCandidate({ name_en: 'Bayward', min_zoom: 14, sort_key: 2 }),
      labelCandidate({
        name_en: 'bayward',
        min_zoom: 13,
        lon: 51.49,
        sort_key: 1,
      }),
    ],
    null,
  );
  assert.equal(labels.length, 1);
  assert.equal(labels[0].en, 'bayward');
  assert.equal(labels[0].min_zoom, 13);
});

test('two Arabic names that share one English name give one label', () => {
  const labels = districtLabels(
    [
      labelCandidate({
        name_en: 'Bayward',
        name_ar: 'حي المثال',
        min_zoom: 14,
      }),
      labelCandidate({
        name_en: 'Bayward',
        name_ar: 'حي آخر',
        min_zoom: 12,
        lon: 51.48,
      }),
    ],
    null,
  );
  assert.equal(labels.length, 1);
  assert.equal(labels[0].min_zoom, 12);
});

test('the lit district point and spelling win', () => {
  const labels = districtLabels(
    [
      labelCandidate({
        name_en: 'Baeward',
        name_ar: 'حي المثال',
        lon: 51.5,
        lat: 25.3,
      }),
    ],
    { en: 'Bayward', ar: 'حي المثال', lon: 51.45, lat: 25.28 },
  );
  assert.deepEqual(labels, [
    {
      en: 'Bayward',
      ar: 'حي المثال',
      lon: 51.45,
      lat: 25.28,
      min_zoom: 13,
    },
  ]);
});

test('another kind, or a place outside the frame, is dropped', () => {
  const labels = districtLabels(
    [
      labelCandidate({
        kind: 'locality',
        name_en: 'Cityward',
        name_ar: 'مدينة المثال',
      }),
      labelCandidate({
        name_en: 'Farward',
        name_ar: 'حي البعيد',
        lon: 50,
        lat: 24,
      }),
      labelCandidate({ name_en: 'Keptward', name_ar: 'حي الباقي' }),
    ],
    null,
  );
  assert.equal(labels.length, 1);
  assert.equal(labels[0].en, 'Keptward');
});

test('a figure on a district label is refused, and a label needs a name', () => {
  const good = {
    en: 'Bayward',
    ar: '',
    lon: 51.5,
    lat: 25.3,
    min_zoom: 12,
  };
  assert.deepEqual(
    validateRelease(release({ district_labels: [good] })).district_labels,
    [good],
  );
  assert.deepEqual(validateRelease(release()).district_labels, []);
  assert.throws(
    () =>
      validateRelease(release({ district_labels: [{ ...good, firms: 4 }] })),
    /district label carries firms/,
  );
  assert.throws(
    () =>
      validateRelease(
        release({
          district_labels: [{ ...good, en: '', ar: '' }],
        }),
      ),
    /no name/,
  );
});

test('without the extract the release carries no district label', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-labels-'));
  try {
    const built = await buildRelease(root);
    assert.deepEqual(built.release.district_labels, []);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('a release without a calendar date for its period is refused', () => {
  assert.equal(validateRelease(release()).period, '2026-11-13');
  for (const period of [
    undefined,
    '',
    '2026-02-30',
    '2026-11-13T00:00',
    20261113,
  ]) {
    assert.throws(
      () => validateRelease(release({ period })),
      /period/,
      String(period),
    );
  }
});

// F1: an absent measurement cannot be replaced by a plausible number.
test('empty cells release no summary figure or nonexistent-unit method', () => {
  const facts = releaseFacts([]);
  for (const id of ['densest-unit', 'areas-with-firms', 'top-classes']) {
    assert.equal(
      facts.some((fact) => fact.id === id),
      false,
      id,
    );
  }
  for (const method of [
    'chain.methodUnit',
    'chain.methodMean',
    'chain.methodShare',
  ]) {
    assert.equal(
      facts.some((fact) => fact.chain.method === method),
      false,
      method,
    );
  }
});

test('the default browser harness does not inject register cells without an extract', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-default-'));
  let server;
  try {
    fs.writeFileSync(path.join(root, 'index.html'), RELEASE_BLOCK);
    server = await startTestServer(root);
    if (server.basemap) {
      assert.ok(server.release.layer.cells.length > 0);
    } else {
      assert.deepEqual(server.release.layer.cells, []);
      assert.equal(server.release.coverage, 'not_measured');
      assert.equal(server.release.facts.length, 4);
    }
  } finally {
    if (server) await server.close();
    fs.rmSync(root, { recursive: true, force: true });
  }
});
