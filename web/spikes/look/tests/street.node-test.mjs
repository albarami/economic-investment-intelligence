import { releaseFacts } from '../release-build.mjs';
// Round 5 of the look: the lit district's name, the building layers, the road
// and district labels, the folding plates and the street cameras. Every name
// and coordinate below is invented, except the four cameras of the brief.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  CARD_FIELDS,
  DISTRICT_PLATE_REACH,
  DISTRICT_PLATE_STRETCH,
  EDGE_MARGIN,
  STREET_CAMERAS,
  STREET_FILES,
  edgeStrips,
  judgeBuildingLayers,
  judgeCard,
  judgeCityFrame,
  judgeDistrictPlate,
  judgeFold,
  judgeFoldedLegend,
  judgeSwatches,
  judgePointKey,
  judgeTypeControl,
  judgeCardChips,
  judgePointColours,
  judgeLegendPeriod,
  judgeDensity,
  judgeAttributionRuns,
  judgeLabelsInside,
  judgeBracketLabel,
  judgePointsUnderLabels,
  judgeStreetCover,
  judgeUniqueNames,
  judgeRoadLabels,
  judgeScreen,
} from '../guards.mjs';
import { majorPlaces, nearestDistrict } from '../release-build.mjs';
import { validateRelease } from '../release-shape.mjs';

const near = (lon, lat, extra = {}) => ({
  kind: 'neighbourhood',
  lon,
  lat,
  name_en: 'Fern Quarter',
  name_ar: 'حي السرخس',
  ...extra,
});

test('the lit district is the nearest named district with both names', () => {
  const found = nearestDistrict(
    [
      near(51.6, 25.5, { name_en: 'Far Quarter', name_ar: 'الحي البعيد' }),
      near(51.501, 25.301),
      near(51.5001, 25.3001, { name_ar: '' }),
      near(51.5002, 25.3002, { kind: 'locality', name_en: 'Big Town' }),
    ],
    [51.5, 25.3],
  );
  assert.deepEqual(found, {
    en: 'Fern Quarter',
    ar: 'حي السرخس',
    lon: 51.501,
    lat: 25.301,
  });
});

test('no district is named when none is within reach', () => {
  assert.equal(nearestDistrict([near(51.6, 25.5)], [51.5, 25.3]), null);
  assert.equal(nearestDistrict([], [51.5, 25.3]), null);
});

test('a planted shop name is never taken as the district', () => {
  const found = nearestDistrict(
    [near(51.5, 25.3, { kind: 'shop', name_en: 'Corner Stall' })],
    [51.5, 25.3],
  );
  assert.equal(found, null);
});

test('the release carries the district and the building archive, and refuses a figure on the district', () => {
  const base = {
    release_id: 'r',
    origin: 'synthetic',
    generator: { name: 'chain.pipeline', version: '1.0.0' },
    basemap: { present: false, missing: 'x' },
    buildings: { present: true, url: '/basemap/buildings.pmtiles' },
    district: { en: 'Fern Quarter', ar: 'حي السرخس', lon: 51.5, lat: 25.3 },
    period: '2026-11-13',
    layer: {
      id: 'l',
      unit_key: 'u',
      provenance: 'public',
      resolution: 9,
      breaks: [1, 2, 3, 4],
      cells: [],
    },
    facts: [],
    firms: [],
  };
  const release = validateRelease(base);
  assert.deepEqual(release.buildings, base.buildings);
  assert.deepEqual(release.district, base.district);
  assert.equal(validateRelease({ ...base, district: null }).district, null);
  assert.throws(
    () =>
      validateRelease({ ...base, district: { ...base.district, value: 9 } }),
    /district carries value/,
  );
  // Round 5g, finding 13 (AI-117, rules 8 and 24): an invented layer names
  // no real district.
  assert.throws(
    () =>
      validateRelease({
        ...base,
        layer: {
          ...base.layer,
          provenance: 'synthetic',
          origin: 'synthetic',
          generator: { name: 'chain.pipeline', version: '1.0.0' },
        },
      }),
    /only on a public layer/,
  );
  assert.equal(
    validateRelease({
      ...base,
      district: null,
      layer: {
        ...base.layer,
        provenance: 'synthetic',
        origin: 'synthetic',
        generator: { name: 'chain.pipeline', version: '1.0.0' },
      },
    }).district,
    null,
  );
});

// Ruling L-143 item 3: the City framing keeps the major place names clear of
// the plates, so the release carries their label points: the localities the
// basemap draws from zoom 9 or lower inside the frame, with the name each
// language shows (empty where that language shows none).
const town = (extra = {}) => ({
  kind: 'locality',
  min_zoom: 6,
  lon: 51.5,
  lat: 25.3,
  name_en: 'Big Town',
  name_ar: 'البلدة الكبيرة',
  ...extra,
});

test('the major places are the localities of the frame drawn from zoom 9, once each', () => {
  const reed = { name_en: 'Reed Port', name_ar: 'ميناء القصب' };
  assert.deepEqual(
    majorPlaces([
      town(),
      town(),
      town({ min_zoom: 9, lon: 51.4, lat: 25.4, ...reed }),
      town({ lon: 51.45, name_en: 'Salt Flat', name_ar: '' }),
    ]),
    [
      { en: 'Big Town', ar: 'البلدة الكبيرة', lon: 51.5, lat: 25.3 },
      { en: 'Reed Port', ar: 'ميناء القصب', lon: 51.4, lat: 25.4 },
      { en: 'Salt Flat', ar: '', lon: 51.45, lat: 25.3 },
    ],
  );
});

test('a planted quarter, a late locality, a place outside the frame or a nameless place is not a major place', () => {
  assert.deepEqual(
    majorPlaces([
      town({ kind: 'neighbourhood' }),
      town({ min_zoom: 10 }),
      town({ min_zoom: undefined }),
      town({ lon: 51.7 }),
      town({ lat: 25.1 }),
      town({ name_en: '', name_ar: '' }),
    ]),
    [],
  );
});

test('the release carries the major places and refuses a figure or no name on one', () => {
  const place = { en: 'Big Town', ar: 'البلدة الكبيرة', lon: 51.5, lat: 25.3 };
  const base = {
    release_id: 'r',
    origin: 'synthetic',
    generator: { name: 'chain.pipeline', version: '1.0.0' },
    basemap: { present: false, missing: 'x' },
    buildings: { present: false },
    district: null,
    places: [place],
    period: '2026-11-13',
    layer: {
      id: 'l',
      unit_key: 'u',
      provenance: 'synthetic',
      origin: 'synthetic',
      generator: { name: 'chain.pipeline', version: '1.0.0' },
      resolution: 9,
      breaks: [1, 2, 3, 4],
      cells: [],
    },
    facts: [],
    firms: [],
  };
  assert.deepEqual(validateRelease(base).places, [place]);
  assert.deepEqual(validateRelease({ ...base, places: undefined }).places, []);
  assert.throws(
    () => validateRelease({ ...base, places: [{ ...place, value: 9 }] }),
    /place carries value/,
  );
  assert.throws(
    () => validateRelease({ ...base, places: [{ ...place, en: '', ar: '' }] }),
    /place has no name/,
  );
});

const flat = {
  id: 'buildings-flat',
  type: 'fill',
  source: 'buildings',
  'source-layer': 'buildings',
  minzoom: 13,
  maxzoom: 14,
};
const raised = {
  id: 'buildings-3d',
  type: 'fill-extrusion',
  source: 'buildings',
  'source-layer': 'buildings',
  minzoom: 14,
  paint: { 'fill-extrusion-height': ['get', 'height'] },
};

test('every footprint is drawn from zoom 13 and raised from zoom 14 with its height', () => {
  assert.equal(judgeBuildingLayers([flat, raised]).ok, true);
});

test('a planted thinning, a late start or a slab height fails', () => {
  const thinned = { ...flat, filter: ['>', ['get', 'height'], 10] };
  assert.equal(judgeBuildingLayers([thinned, raised]).ok, false);
  assert.equal(
    judgeBuildingLayers([{ ...flat, minzoom: 14 }, raised]).ok,
    false,
  );
  const slab = { ...raised, paint: { 'fill-extrusion-height': 12 } };
  assert.equal(judgeBuildingLayers([flat, slab]).ok, false);
  const basemapOnly = { ...flat, source: 'protomaps' };
  assert.equal(judgeBuildingLayers([basemapOnly, raised]).ok, false);
});

const road = (id, minzoom, filter) => ({
  id,
  type: 'symbol',
  source: 'protomaps',
  'source-layer': 'roads',
  minzoom,
  filter,
  layout: { 'symbol-placement': 'line', 'text-field': ['get', 'name:en'] },
});

test('main roads are named from 12, secondary streets from 14, every named street from 15', () => {
  const layers = [
    road('label-road-main', 12, ['all']),
    road('label-road-secondary', 14, ['all']),
    road('label-road-street', 15, ['all']),
  ];
  assert.equal(judgeRoadLabels(layers).ok, true);
});

test('a planted late or missing road label tier fails', () => {
  assert.equal(
    judgeRoadLabels([
      road('label-road-main', 13, ['all']),
      road('label-road-secondary', 14, ['all']),
      road('label-road-street', 15, ['all']),
    ]).ok,
    false,
  );
  assert.equal(
    judgeRoadLabels([
      road('label-road-main', 12, ['all']),
      road('label-road-secondary', 14, ['all']),
    ]).ok,
    false,
  );
});

// Round 5f, F2: the map draws its layers in the style's order, first drawn
// lowest, and a circle takes no part in the labels' collisions, so the
// establishment points must come before every label layer in the style.
const drawn = (id, type, source) =>
  source === undefined ? { id, type } : { id, type, source };
const IN_ORDER = [
  drawn('background', 'background'),
  drawn('lit-1', 'fill'),
  drawn('buildings-raised', 'fill-extrusion'),
  drawn('establishments-cluster', 'circle', 'establishments'),
  drawn('establishments-point', 'circle', 'establishments'),
  drawn('label-road-main', 'symbol'),
  drawn('label-road-secondary', 'symbol'),
  drawn('label-road-street', 'symbol'),
  drawn('label-district', 'symbol'),
  drawn('label-place', 'symbol'),
];

// The layers in IN_ORDER with `id` taken out and put back just after `after`
// (at the top of the style when `after` is null).
function movedAfter(id, after) {
  const rest = IN_ORDER.filter((layer) => layer.id !== id);
  const moving = IN_ORDER.find((layer) => layer.id === id);
  const at =
    after === null
      ? rest.length
      : rest.findIndex((layer) => layer.id === after) + 1;
  return [...rest.slice(0, at), moving, ...rest.slice(at)];
}

test('establishment points drawn under every place, district and road name pass', () => {
  assert.deepEqual(judgePointsUnderLabels(IN_ORDER), { ok: true, detail: '' });
});

test('the densest-areas bracket label is one line, and a planted long label wraps', () => {
  const fitted = {
    lines: 1,
    lang: 'ar',
    textLeft: 80,
    textRight: 200,
    bracketLeft: 100,
    bracketRight: 200,
  };
  assert.equal(judgeBracketLabel(fitted).ok, true);
  assert.equal(
    judgeBracketLabel({ ...fitted, lang: 'en', textLeft: 100, textRight: 160 })
      .ok,
    true,
  );
  const wrapped = judgeBracketLabel({ ...fitted, lines: 2 });
  assert.equal(wrapped.ok, false);
  assert.match(wrapped.detail, /two lines/);
  const ragged = judgeBracketLabel({ ...fitted, textRight: 140 });
  assert.equal(ragged.ok, false);
  assert.match(ragged.detail, /high end/);
});

test('Arabic street plates cover no more lit data than the English plates', () => {
  assert.equal(
    judgeStreetCover([
      { camera: 'c', en: 4, ar: 4 },
      { camera: 'd', en: 2, ar: 1 },
    ]).ok,
    true,
  );
  const over = judgeStreetCover([{ camera: 'c', en: 1, ar: 6 }]);
  assert.equal(over.ok, false);
  assert.match(over.detail, /camera c/);
});

test('a repeated district name fails the unique-name guard', () => {
  assert.equal(judgeUniqueNames(['Bayward', 'Keptward']).ok, true);
  assert.equal(judgeUniqueNames(['Bayward', '']).ok, true);
  const again = judgeUniqueNames(['Bayward', 'bayward']);
  assert.equal(again.ok, false);
  assert.match(again.detail, /bayward/i);
});

test('a firm layer drawn above a name fails even when its id is not one of the two known layers', () => {
  // The ring is the same firm source under a new id, placed after every label.
  // A fixed list of the two known ids does not see it.
  const withRing = [
    ...IN_ORDER.map((layer) =>
      layer.id.startsWith('establishments')
        ? { ...layer, source: 'establishments' }
        : layer,
    ),
    { id: 'establishments-ring', type: 'circle', source: 'establishments' },
  ];
  const verdict = judgePointsUnderLabels(withRing);
  assert.equal(verdict.ok, false);
  assert.match(verdict.detail, /establishments-ring/);
  assert.match(verdict.detail, /label-district/);
});

test('a planted point layer above a name, or a missing layer, fails', () => {
  // Round 5's order: both point layers drawn last, over every label.
  const roundFive = movedAfter('establishments-cluster', null);
  const lastOfAll = [
    ...roundFive.filter((layer) => layer.id !== 'establishments-point'),
    drawn('establishments-point', 'circle'),
  ];
  const top = judgePointsUnderLabels(lastOfAll);
  assert.equal(top.ok, false);
  assert.match(top.detail, /establishments-cluster is drawn above/);
  assert.match(top.detail, /label-district/);
  assert.match(top.detail, /label-place/);
  // The single points over the district names but under the place names.
  const district = judgePointsUnderLabels(
    movedAfter('establishments-point', 'label-district'),
  );
  assert.equal(district.ok, false);
  assert.match(district.detail, /establishments-point is drawn above/);
  assert.match(district.detail, /label-district/);
  assert.doesNotMatch(district.detail, /label-place/);
  // The clusters over the street names only.
  const street = judgePointsUnderLabels(
    movedAfter('establishments-cluster', 'label-road-street'),
  );
  assert.equal(street.ok, false);
  assert.match(street.detail, /label-road-street/);
  assert.doesNotMatch(street.detail, /label-district/);
  // A style without the district names, or without any point layer, cannot
  // show the order, and fails.
  const nameless = judgePointsUnderLabels(
    IN_ORDER.filter((layer) => layer.id !== 'label-district'),
  );
  assert.equal(nameless.ok, false);
  assert.match(nameless.detail, /label-district is missing/);
  const pointless = judgePointsUnderLabels(
    IN_ORDER.filter((layer) => layer.type !== 'circle'),
  );
  assert.equal(pointless.ok, false);
  assert.match(pointless.detail, /no establishment layer/);
});

test('the plates fold at street zoom and come back at city zoom', () => {
  assert.equal(
    judgeFold([
      { zoom: 15.3, brief: 'folded', legend: 'folded' },
      { zoom: 10.8, brief: 'open', legend: 'open' },
    ]).ok,
    true,
  );
  assert.equal(
    judgeFold([{ zoom: 15.3, brief: 'open', legend: 'folded' }]).ok,
    false,
  );
  assert.equal(
    judgeFold([{ zoom: 10.8, brief: 'folded', legend: 'open' }]).ok,
    false,
  );
});

// Ruling L-143 item 3: the City framing rests at a city scale, at or below its
// cap, and the cap sits at or below the unfold zoom, so the answer opens with
// the Brief and the legend open.
test('the City framing at a city scale with the plates open passes', () => {
  assert.equal(
    judgeCityFrame({ zoom: 11.6, brief: 'open', legend: 'open' }, 12).ok,
    true,
  );
});

test('a planted City framing past its cap, a cap past the unfold zoom or a folded plate fails', () => {
  const past = judgeCityFrame(
    { zoom: 13.12, brief: 'open', legend: 'open' },
    12,
  );
  assert.equal(past.ok, false);
  assert.match(past.detail, /past the city cap/);
  const late = judgeCityFrame(
    { zoom: 13.12, brief: 'open', legend: 'open' },
    15,
  );
  assert.equal(late.ok, false);
  assert.match(late.detail, /past the unfold zoom/);
  const shut = judgeCityFrame(
    { zoom: 11.6, brief: 'folded', legend: 'open' },
    12,
  );
  assert.equal(shut.ok, false);
  assert.match(shut.detail, /the brief is folded/);
  assert.equal(
    judgeCityFrame({ zoom: 11.6, brief: 'open', legend: 'open' }, Number.NaN)
      .ok,
    false,
  );
});

// Round 5e, E1: the quiet plate that names the lit district sizes to its name,
// sits just above its cell, shows the whole name on the screen, and has
// finished its entrance when the page reports it settled.
const PLATE_SEEN = {
  name: 'Fern Quarter',
  text: 'Fern Quarter',
  shown: true,
  running: 0,
  plate: { x: 540, y: 400, width: 141, height: 38 },
  textBox: { x: 553, y: 401, width: 115, height: 36 },
  point: { x: 610, y: 486 },
  viewport: { width: 1920, height: 1080 },
};

test('a district plate that sizes to its name just above its cell passes', () => {
  assert.equal(DISTRICT_PLATE_STRETCH, 2);
  assert.equal(DISTRICT_PLATE_REACH, 64);
  const verdict = judgeDistrictPlate(PLATE_SEEN);
  assert.equal(verdict.ok, true, verdict.detail);
});

test('a planted stretched, empty, wrong, far, cut, hidden or entering district plate fails', () => {
  // The band of round 5d: the plate as wide as the map, its name off screen.
  const band = judgeDistrictPlate({
    ...PLATE_SEEN,
    plate: { x: -350, y: 400, width: 1920, height: 38 },
    textBox: { x: -337, y: 401, width: 115, height: 36 },
  });
  assert.equal(band.ok, false);
  assert.match(band.detail, /1920 px wide for a name of 115 px/);
  const empty = judgeDistrictPlate({
    ...PLATE_SEEN,
    text: '',
    textBox: { x: 0, y: 0, width: 0, height: 0 },
  });
  assert.equal(empty.ok, false);
  assert.match(empty.detail, /reads "" and not "Fern Quarter"/);
  const wrong = judgeDistrictPlate({ ...PLATE_SEEN, text: 'Moss Quarter' });
  assert.equal(wrong.ok, false);
  assert.match(wrong.detail, /reads "Moss Quarter"/);
  const far = judgeDistrictPlate({
    ...PLATE_SEEN,
    point: { x: 610, y: 600 },
  });
  assert.equal(far.ok, false);
  assert.match(far.detail, /not just above its cell/);
  const aside = judgeDistrictPlate({
    ...PLATE_SEEN,
    point: { x: 900, y: 486 },
  });
  assert.equal(aside.ok, false);
  assert.match(aside.detail, /not just above its cell/);
  const cut = judgeDistrictPlate({
    ...PLATE_SEEN,
    plate: { x: -40, y: 400, width: 141, height: 38 },
    textBox: { x: -27, y: 401, width: 115, height: 36 },
    point: { x: 30, y: 486 },
  });
  assert.equal(cut.ok, false);
  assert.match(cut.detail, /cut by the screen's edge/);
  const hidden = judgeDistrictPlate({ ...PLATE_SEEN, shown: false });
  assert.equal(hidden.ok, false);
  assert.match(hidden.detail, /is not shown/);
  const entering = judgeDistrictPlate({ ...PLATE_SEEN, running: 1 });
  assert.equal(entering.ok, false);
  assert.match(entering.detail, /entrance has not ended/);
});

// Round 5e, E2: a major place label is wholly inside the screen with a margin
// of EDGE_MARGIN px, or not drawn. The strips are the screen's four edges.
test('the four edge strips of the screen are EDGE_MARGIN px deep', () => {
  assert.equal(EDGE_MARGIN, 8);
  assert.deepEqual(edgeStrips(1920, 1080), [
    { name: 'left', x: 0, y: 0, width: 8, height: 1080 },
    { name: 'right', x: 1912, y: 0, width: 8, height: 1080 },
    { name: 'top', x: 0, y: 0, width: 1920, height: 8 },
    { name: 'bottom', x: 0, y: 1072, width: 1920, height: 8 },
  ]);
});

test('no major place label in an edge strip passes; a planted label cut by an edge fails', () => {
  assert.equal(judgeLabelsInside([]).ok, true);
  const cut = judgeLabelsInside([{ label: 'Big Town', plate: 'left' }]);
  assert.equal(cut.ok, false);
  assert.equal(
    cut.detail,
    'map label "Big Town" is cut by the left edge of the screen or lies within 8 px of it',
  );
});

test('the four street cameras of the brief and their sixteen files are named', () => {
  assert.deepEqual(STREET_CAMERAS, [
    { name: 'a', center: [51.5369, 25.2546], zoom: 15.3, pitch: 0, bearing: 0 },
    {
      name: 'b',
      center: [51.5369, 25.2546],
      zoom: 15.8,
      pitch: 55,
      bearing: -20,
    },
    { name: 'c', center: [51.527, 25.322], zoom: 14, pitch: 0, bearing: 0 },
    { name: 'd', center: [51.53, 25.322], zoom: 15.4, pitch: 55, bearing: -25 },
  ]);
  assert.equal(STREET_FILES.length, 16);
  assert.equal(new Set(STREET_FILES).size, 16);
  assert.ok(STREET_FILES.includes('d-ar-light.png'));
});

// P2: one card at a time; the data layer, its legend and every numeral belong
// to the answer alone; the home asks four questions; every other screen has a
// way back.
const screen = (name, extra = {}) => ({
  screen: name,
  cards: [name],
  lit: [0, 0, 0, 0, 0],
  legend: false,
  numerals: 0,
  questions: name === 'home' ? 4 : 0,
  back: name !== 'home',
  ...extra,
});

test('the home, the place step, the quiet state and the answer each pass as built', () => {
  for (const name of ['home', 'place', 'notyet']) {
    const verdict = judgeScreen(screen(name), name);
    assert.equal(verdict.ok, true, verdict.detail);
  }
  const answer = screen('answer', {
    lit: [1, 1, 1, 1, 1],
    legend: true,
    numerals: 9,
  });
  assert.equal(judgeScreen(answer, 'answer').ok, true);
});

test('a planted lit home, a skipped step, a blank screen or a way back that keeps the data fails', () => {
  const lit = judgeScreen(screen('home', { lit: [1, 1, 1, 1, 1] }), 'home');
  assert.equal(lit.ok, false);
  assert.match(lit.detail, /lights the data layer/);
  const legend = judgeScreen(screen('home', { legend: true }), 'home');
  assert.match(legend.detail, /shows the legend/);
  const numeral = judgeScreen(screen('place', { numerals: 1 }), 'place');
  assert.match(numeral.detail, /shows a numeral/);
  const three = judgeScreen(screen('home', { questions: 3 }), 'home');
  assert.match(three.detail, /asks 3 questions/);
  const skipped = judgeScreen(
    screen('answer', { lit: [1, 1, 1, 1, 1], legend: true }),
    'place',
  );
  assert.equal(skipped.ok, false);
  assert.match(skipped.detail, /not place/);
  const blank = judgeScreen(screen('notyet', { cards: [] }), 'notyet');
  assert.match(blank.detail, /no card/);
  const stranded = judgeScreen(screen('notyet', { back: false }), 'notyet');
  assert.match(stranded.detail, /no way back/);
  const dark = judgeScreen(
    screen('answer', { lit: [1, 1, 0, 0, 0], legend: true }),
    'answer',
  );
  assert.match(dark.detail, /not lit/);
});

// The company card (the owner's decision of 2026-11-13): the published fields
// only, the number of employees among them, no wage and no other figure.
test('the card of published fields with the number of employees passes', () => {
  assert.ok(CARD_FIELDS.includes('field.employees'));
  const found = [
    { field: 'field.business', value: 'bakery' },
    { field: 'field.employees', value: '21' },
    { field: 'field.zone', value: '12' },
  ];
  const verdict = judgeCard(found, { employees: 21 });
  assert.equal(verdict.ok, true, verdict.detail);
  assert.equal(judgeCard(found.slice(0, 1), { employees: null }).ok, true);
});

test('a planted card without the employees, with a wrong count or with a wage fails', () => {
  const missing = judgeCard([{ field: 'field.business', value: 'bakery' }], {
    employees: 21,
  });
  assert.equal(missing.ok, false);
  assert.match(missing.detail, /number of employees/);
  const wrong = judgeCard([{ field: 'field.employees', value: '12' }], {
    employees: 21,
  });
  assert.match(wrong.detail, /not 21/);
  const wage = judgeCard(
    [
      { field: 'field.employees', value: '21' },
      { field: 'field.wageBill', value: '9000' },
    ],
    { employees: 21 },
  );
  assert.match(wage.detail, /field\.wageBill is not a published field/);
});

// Round 5g, findings 4, 17, 21 and 25 (DES-19, DES-20, DES-68): the folded
// legend keeps its four breaks and its direction in words, and "Show as
// table" shows the five-row table at street zoom.
const FOLDED_KEY = {
  zoom: 15.3,
  breaks: 4,
  direction: 'Lighter means more firms',
  table: { shown: true, rows: 5 },
};

test('a folded legend with its breaks, its direction and a working table passes', () => {
  const verdict = judgeFoldedLegend(FOLDED_KEY);
  assert.equal(verdict.ok, true, verdict.detail);
  assert.equal(
    judgeFoldedLegend({ ...FOLDED_KEY, zoom: 10.8, breaks: 0 }).ok,
    true,
  );
});

test('a planted folded legend without breaks, without direction or with no table fails', () => {
  for (const [planted, words] of [
    [{ breaks: 0 }, 'breaks'],
    [{ direction: '' }, 'direction'],
    [{ table: { shown: false, rows: 0 } }, 'table'],
    [{ table: { shown: true, rows: 3 } }, 'table'],
  ]) {
    const verdict = judgeFoldedLegend({ ...FOLDED_KEY, ...planted });
    assert.equal(verdict.ok, false, JSON.stringify(planted));
    assert.match(verdict.detail, new RegExp(words));
  }
});

// Round 5g, finding 9 (WCAG 3.1.2, DES-28): the credits are one Latin line
// with no separator at a line end; the note is in the page's language at
// that language's caption size.
const RUNS = {
  note: { lang: 'ar', size: 31 },
  creditLines: 1,
  creditText: 'OpenStreetMap contributors · Protomaps',
};

test('an attribution with one credits line and a note in the page language passes', () => {
  const verdict = judgeAttributionRuns(RUNS, 'ar', 31);
  assert.equal(verdict.ok, true, verdict.detail);
});

test('a planted attribution note in English, at the Latin size, or wrapped credits fails', () => {
  for (const [planted, words] of [
    [{ note: null }, 'no note'],
    [{ note: { lang: 'en', size: 31 } }, 'tagged en'],
    [{ note: { lang: 'ar', size: 28 } }, '28px'],
    [{ creditLines: 2 }, 'wrap'],
    [{ creditText: 'OpenStreetMap contributors ·' }, 'separator'],
  ]) {
    const verdict = judgeAttributionRuns({ ...RUNS, ...planted }, 'ar', 31);
    assert.equal(verdict.ok, false, JSON.stringify(planted));
    assert.match(verdict.detail, new RegExp(words));
  }
});

// Round 5g, finding 22: one reference chip in the legend head names the date
// of the count; finding 24: the answer card holds three chips of any kind.
test('a legend head with one chip naming the date passes; none, two or another date fails', () => {
  const head = { shown: true, chips: ['13 November 2026'] };
  assert.equal(judgeLegendPeriod(head, '13 November 2026').ok, true);
  for (const planted of [
    { shown: false },
    { chips: [] },
    { chips: ['13 November 2026', '13 November 2026'] },
    { chips: ['12 November 2026'] },
  ]) {
    const verdict = judgeLegendPeriod(
      { ...head, ...planted },
      '13 November 2026',
    );
    assert.equal(verdict.ok, false, JSON.stringify(planted));
    assert.match(verdict.detail, /date/);
  }
});

test('an answer card with a fourth chip of any kind fails the wall density', () => {
  const counts = { headlines: 1, valueChips: 3, chips: 3, caveats: 1 };
  assert.equal(judgeDensity(counts).ok, true);
  const verdict = judgeDensity({ ...counts, chips: 4 });
  assert.equal(verdict.ok, false);
  assert.match(verdict.detail, /three chips/);
});

// Round 5g, finding 15 (rules 7 and 23): the card's counts are value chips of
// released facts with a complete chain; a reference chip stands only for the
// record dates, the zone and the classification; the card has no position.
const CARD_FACTS = [
  {
    id: 'row-a-employees',
    provenance: 'synthetic',
    origin: 'synthetic',
    chain: releaseFacts([['8943a1d8b6bffff', 80, 2]])[0].chain,
  },
  {
    id: 'row-a-branches',
    provenance: 'synthetic',
    origin: 'synthetic',
    chain: releaseFacts([['8943a1d8b6bffff', 80, 2]])[0].chain,
  },
];
const CARD_ROWS = [
  { field: 'field.business', chip: null, fact: null },
  { field: 'field.employees', chip: 'value', fact: 'row-a-employees' },
  { field: 'field.branches', chip: 'value', fact: 'row-a-branches' },
  { field: 'field.licenceIssue', chip: 'reference', fact: null },
  { field: 'field.zone', chip: 'reference', fact: null },
];

test('a card whose counts are chained value chips passes, and it has no position rows', () => {
  const verdict = judgeCardChips(CARD_ROWS, CARD_FACTS);
  assert.equal(verdict.ok, true, verdict.detail);
  assert.equal(CARD_FIELDS.includes('field.longitude'), false);
  assert.equal(CARD_FIELDS.includes('field.latitude'), false);
});

test('a planted reference chip for a count, an unreleased fact or a count in a reference row fails', () => {
  const swap = (field, change) =>
    CARD_ROWS.map((row) => (row.field === field ? { ...row, ...change } : row));
  for (const [rows, words] of [
    [swap('field.employees', { chip: 'reference', fact: null }), 'employees'],
    [swap('field.branches', { fact: 'row-z-branches' }), 'not released'],
    [swap('field.business', { chip: 'reference' }), 'field.business'],
  ]) {
    const verdict = judgeCardChips(rows, CARD_FACTS);
    assert.equal(verdict.ok, false, JSON.stringify(rows));
    assert.match(verdict.detail, new RegExp(words));
  }
});

// Round 5g, findings 1, 18 and 19 (dataviz: no value ramp for categories,
// never cycle): no establishment paint takes a density ramp colour, and the
// type expression gives no two outputs one colour.
const RAMP = ['#2f4a5e', '#3f6f86', '#5e97a6', '#9cc4bb', '#ebe3b0'];
const INK = {
  point: '#e6eaeb',
  cluster: '#e6eaeb',
  halo: '#10151c',
  types: [
    'case',
    ['==', ['get', 'business_type'], 'bakery'],
    '#e6eaeb',
    '#8492a3',
  ],
};

test('establishment paints in ink with a distinct highlight pass', () => {
  const verdict = judgePointColours(INK, RAMP);
  assert.equal(verdict.ok, true, verdict.detail);
  assert.equal(judgePointColours({ ...INK, types: null }, RAMP).ok, true);
});

test('a planted ramp colour on the points or the clusters, or a repeated type colour, fails', () => {
  const cycled = ['match', ['get', 'business_type']];
  for (const [index, type] of ['a', 'b', 'c', 'd', 'e', 'f'].entries())
    cycled.push(type, RAMP[index % RAMP.length]);
  cycled.push(RAMP[4]);
  for (const [planted, words] of [
    [{ point: RAMP[4].toUpperCase() }, 'ramp'],
    [{ cluster: RAMP[2] }, 'ramp'],
    [{ types: cycled }, 'ramp'],
    [
      {
        types: [
          'case',
          ['==', ['get', 'business_type'], 'x'],
          '#e6eaeb',
          '#E6EAEB',
        ],
      },
      'repeat',
    ],
    [
      {
        types: [
          'match',
          ['get', 'business_type'],
          'a',
          '#111111',
          'b',
          '#222222',
          '#111111',
        ],
      },
      'repeat',
    ],
  ]) {
    const verdict = judgePointColours({ ...INK, ...planted }, RAMP);
    assert.equal(verdict.ok, false, JSON.stringify(planted));
    assert.match(verdict.detail, new RegExp(words));
  }
});

test('the legend keys the dots from zoom 14 and the circles from zoom 12, and neither at the City framing', () => {
  const key = (zoom, point, cluster) =>
    judgePointKey({ zoom, point, cluster }, 12, 14);
  assert.equal(key(14.5, true, false).ok, true);
  assert.equal(key(13, false, true).ok, true);
  assert.equal(key(10.8, false, false).ok, true);
  assert.match(key(14.5, false, false).detail, /dots/);
  assert.match(key(13, false, false).detail, /circles/);
  assert.match(key(10.8, true, false).detail, /does not show/);
});

test('the type control offered from zoom 14 with a heading and catalogue names passes; a planted one fails', () => {
  const want = { title: 'Establishments by type', names: { bakery: 'Bakery' } };
  const state = {
    zoom: 14,
    control: true,
    list: true,
    title: 'Establishments by type',
    rows: [{ slug: 'bakery', name: 'Bakery', fact: 'type-bakery' }],
  };
  assert.equal(judgeTypeControl(state, 14, want).ok, true);
  assert.equal(
    judgeTypeControl(
      { ...state, zoom: 11, control: false, list: false },
      14,
      want,
    ).ok,
    true,
  );
  for (const [planted, words] of [
    [{ zoom: 11 }, 'below the point zoom'],
    [{ control: false }, 'not offered'],
    [{ title: '' }, 'heading'],
    [
      { rows: [{ slug: 'bakery', name: 'bakery', fact: 'type-bakery' }] },
      'catalogue',
    ],
  ]) {
    const verdict = judgeTypeControl({ ...state, ...planted }, 14, want);
    assert.equal(verdict.ok, false, JSON.stringify(planted));
    assert.match(verdict.detail, new RegExp(words));
  }
});

// Round 5g, finding 23 (DES-61): each legend swatch is its class's fill at
// the class opacity over the land, as the map draws the lit cells.
test('swatches drawn as the blended cells pass; a planted opaque swatch fails', () => {
  const drawn = [
    [44, 69, 87],
    [204, 199, 157],
  ];
  assert.equal(
    judgeSwatches(drawn, [
      [44, 69, 87],
      [205, 198, 157],
    ]).ok,
    true,
  );
  const verdict = judgeSwatches(
    [
      [44, 69, 87],
      [235, 227, 176],
    ],
    drawn,
  );
  assert.equal(verdict.ok, false);
  assert.match(verdict.detail, /swatch 2/);
});
