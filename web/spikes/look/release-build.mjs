// The look page's release build, run by its own server in Node. It reads
// the uncommitted PMTiles extract of Qatar under data/basemap/, measures
// the built-up floor area of the extract's buildings per H3 cell of
// resolution 9 over Greater Doha and Lusail, and turns that into invented
// firm densities per release unit. Every value it writes is invented and
// classed Synthetic with the source "look-proof fixture"; only the
// placement follows the real city, so that no lit cell sits on water.
// Nothing derived from the extract is written to the repository: the
// release lives in the server's memory and in the page it serves.
import fs from 'node:fs';
import { createHash } from 'node:crypto';
import {
  PIPELINE,
  REGISTER_PIPELINE,
  VERSION,
  validInput,
} from './lineage.mjs';
import path from 'node:path';
import { cellArea, gridDisk, latLngToCell } from 'h3-js';
import { PMTiles } from 'pmtiles';
import { decodeTile, ringArea, rings } from './mvt.mjs';
import {
  cellsFromCounts,
  countsByCell,
  countsByType,
  STAND_IN_DATE,
  locateRegister,
  parseRegister,
  registerPeriod,
} from './register.mjs';
import {
  RELEASE_ID,
  SHARE_FROM_STEP,
  validateRelease,
} from './release-shape.mjs';

// docs/10_FRONTEND.md section "6. Map layers": release units at
// resolution 9 in Greater Doha.
export const RESOLUTION = 9;
// The frame of the lit layer: Greater Doha and Lusail, west, south, east,
// north. Buildings are read from the extract's full-detail zoom.
export const FRAME = [51.33, 25.18, 51.62, 25.48];
export const BUILDING_ZOOM = 15;
export const BASEMAP_FOLDER = ['data', 'basemap'];
export const BASEMAP_PATTERN = /^qatar-[0-9-]+\.pmtiles$/;
export const BASEMAP_HINT = 'data/basemap/qatar-*.pmtiles';
export const BASEMAP_ROUTE = '/basemap/qatar.pmtiles';
export const BUILDINGS_ROUTE = '/basemap/buildings.pmtiles';
export const BUILDINGS_PATTERN = /^overture-buildings-.+\.pmtiles$/;
export const BUILDINGS_HINT = 'data/basemap/overture-buildings-*.pmtiles';

// The invented layer: the densest unit's value, the class breaks (firms per
// square kilometre), the curve that spreads the other units below it and
// the floor under which a unit stays dark. Fixed for the whole release.
export const HERO_VALUE = 1240;
export const BREAKS = [40, 120, 300, 700];
export const CURVE = 0.9;
export const FLOOR = 24;
// A storey is counted as 3.5 m; a building without a height counts as one
// storey; one footprint counts at most 4,000 square metres, so that a mall
// or a stadium does not read as a business district.
const STOREY = 3.5;
const FOOTPRINT_CAP = 4000;
// Smoothing: a unit keeps 55% of its own floor area and takes 45% from the
// mean of its six neighbours, so that districts read as districts.
const OWN_SHARE = 0.55;

// The equatorial circumference of the WGS 84 ellipsoid, in metres.
const EARTH = 2 * Math.PI * 6378137;

export function locateBasemap(repositoryRoot) {
  const folder = path.join(repositoryRoot, ...BASEMAP_FOLDER);
  if (!fs.existsSync(folder)) return { ok: false, detail: BASEMAP_HINT };
  const found = fs
    .readdirSync(folder)
    .filter((name) => BASEMAP_PATTERN.test(name))
    .sort();
  if (found.length === 0) return { ok: false, detail: BASEMAP_HINT };
  if (found.length > 1) {
    return {
      ok: false,
      detail: `more than one extract in ${BASEMAP_FOLDER.join('/')}: ${found.join(', ')}`,
    };
  }
  return { ok: true, file: path.join(folder, found[0]), detail: '' };
}

export function locateBuildings(repositoryRoot) {
  const folder = path.join(repositoryRoot, ...BASEMAP_FOLDER);
  if (!fs.existsSync(folder)) return { ok: false, detail: BUILDINGS_HINT };
  const found = fs
    .readdirSync(folder)
    .filter((name) => BUILDINGS_PATTERN.test(name))
    .sort();
  if (found.length === 0) return { ok: false, detail: BUILDINGS_HINT };
  if (found.length > 1) {
    return {
      ok: false,
      detail: `more than one building archive in ${BASEMAP_FOLDER.join('/')}`,
    };
  }
  return { ok: true, file: path.join(folder, found[0]), detail: '' };
}

// A pmtiles Source over a local file, read with positioned reads.
export class FileSource {
  constructor(file) {
    this.file = file;
    this.fd = fs.openSync(file, 'r');
  }

  getKey() {
    return this.file;
  }

  async getBytes(offset, length) {
    const buffer = Buffer.alloc(length);
    const read = fs.readSync(this.fd, buffer, 0, length, offset);
    const data = buffer.buffer.slice(
      buffer.byteOffset,
      buffer.byteOffset + read,
    );
    return { data };
  }

  close() {
    fs.closeSync(this.fd);
  }
}

export function tileOf(lon, lat, zoom) {
  const n = 2 ** zoom;
  const x = Math.floor(((lon + 180) / 360) * n);
  const radians = (lat * Math.PI) / 180;
  const y = Math.floor(
    ((1 - Math.log(Math.tan(radians) + 1 / Math.cos(radians)) / Math.PI) / 2) *
      n,
  );
  return { x, y };
}

export function lngLatOf(x, y, zoom) {
  const n = 2 ** zoom;
  const lon = (x / n) * 360 - 180;
  const lat =
    (Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / n))) * 180) / Math.PI;
  return [lon, lat];
}

// The floor-area proxy of one decoded building in square metres, and the
// point it is counted at (the mean of its outer ring).
export function buildingFloorArea(feature, tile, extent) {
  if (feature.type !== 3) return null;
  const parts = rings(feature.geometry);
  const outer = parts[0];
  if (outer === undefined || outer.length < 3) return null;
  let area = 0;
  for (const ring of parts) area += ringArea(ring);
  let x = 0;
  let y = 0;
  const corners = outer.length - 1;
  for (let index = 0; index < corners; index += 1) {
    x += outer[index][0];
    y += outer[index][1];
  }
  const [lon, lat] = lngLatOf(
    tile.x + x / corners / extent,
    tile.y + y / corners / extent,
    tile.z,
  );
  const metre =
    (EARTH * Math.cos((lat * Math.PI) / 180)) / 2 ** tile.z / extent;
  const footprint = Math.min(Math.abs(area) * metre * metre, FOOTPRINT_CAP);
  const height = Number(feature.properties.height);
  const storeys =
    Number.isFinite(height) && height > 0
      ? Math.max(1, Math.round(height / STOREY))
      : 1;
  return { lon, lat, floorArea: footprint * storeys };
}

// Sums the floor-area proxy of every building of the frame per H3 cell.
export async function floorAreas(source, frame = FRAME) {
  const archive = new PMTiles(source);
  const low = tileOf(frame[0], frame[3], BUILDING_ZOOM);
  const high = tileOf(frame[2], frame[1], BUILDING_ZOOM);
  const totals = new Map();
  for (let x = low.x; x <= high.x; x += 1) {
    for (let y = low.y; y <= high.y; y += 1) {
      const response = await archive.getZxy(BUILDING_ZOOM, x, y);
      if (response === undefined) continue;
      const layer = decodeTile(response.data, ['buildings']).buildings;
      if (layer === undefined || layer.features === null) continue;
      for (const feature of layer.features) {
        const building = buildingFloorArea(
          feature,
          { x, y, z: BUILDING_ZOOM },
          layer.extent,
        );
        if (building === null) continue;
        if (
          building.lon < frame[0] ||
          building.lon > frame[2] ||
          building.lat < frame[1] ||
          building.lat > frame[3]
        )
          continue;
        const cell = latLngToCell(building.lat, building.lon, RESOLUTION);
        totals.set(cell, (totals.get(cell) ?? 0) + building.floorArea);
      }
    }
  }
  return totals;
}

// Each cell that holds buildings keeps OWN_SHARE of its own total and takes
// the rest from the mean of its six neighbours. Cells without buildings
// stay out, so no unit is lit over water or empty land.
export function smooth(totals) {
  const out = new Map();
  for (const [cell, own] of totals) {
    const ring = gridDisk(cell, 1).filter((other) => other !== cell);
    let sum = 0;
    for (const other of ring) sum += totals.get(other) ?? 0;
    out.set(
      cell,
      OWN_SHARE * own + ((1 - OWN_SHARE) * sum) / Math.max(1, ring.length),
    );
  }
  return out;
}

export function classOf(value, breaks = BREAKS) {
  let step = 1;
  for (const limit of breaks) if (value >= limit) step += 1;
  return step;
}

// The invented firm density of each unit: the densest unit carries
// HERO_VALUE and every other unit follows the curve below it. Units under
// FLOOR stay dark. Sorted by cell id, so the output is deterministic.
export function inventCells(weights) {
  let top = 0;
  for (const weight of weights.values()) top = Math.max(top, weight);
  if (top <= 0) return [];
  const cells = [];
  for (const [cell, weight] of weights) {
    const value = Math.round(HERO_VALUE * (weight / top) ** CURVE);
    if (value < FLOOR) continue;
    cells.push([cell, value, classOf(value)]);
  }
  cells.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  return cells;
}

// P1 of round 5: the headline names the lit district, an area name from the
// basemap's own labels (never a building or business). The district is the
// nearest neighbourhood or larger quarter label that carries a name in both
// languages, within DISTRICT_REACH metres of the densest unit's centre.
export const DISTRICT_KINDS = ['neighbourhood', 'macrohood'];
export const DISTRICT_REACH = 2500;
const DISTRICT_ZOOM = 13;

export function nearestDistrict(candidates, point) {
  const [lon, lat] = point;
  const metresPerDegree = EARTH / 360;
  let best = null;
  let distance = DISTRICT_REACH;
  for (const item of candidates) {
    if (!DISTRICT_KINDS.includes(item.kind)) continue;
    if (!item.name_en || !item.name_ar) continue;
    const dx =
      (item.lon - lon) * metresPerDegree * Math.cos((lat * Math.PI) / 180);
    const dy = (item.lat - lat) * metresPerDegree;
    const away = Math.hypot(dx, dy);
    if (away > distance) continue;
    distance = away;
    best = { en: item.name_en, ar: item.name_ar, lon: item.lon, lat: item.lat };
  }
  return best;
}

// The place labels of one tile of the extract: their properties and the
// point of each label.
async function tilePlaces(archive, zoom, x, y) {
  const response = await archive.getZxy(zoom, x, y);
  if (response === undefined) return [];
  const layer = decodeTile(response.data, ['places']).places;
  if (layer === undefined || layer.features === null) return [];
  const out = [];
  for (const feature of layer.features) {
    const point = rings(feature.geometry)[0]?.[0];
    if (point === undefined) continue;
    const [lon, lat] = lngLatOf(
      x + point[0] / layer.extent,
      y + point[1] / layer.extent,
      zoom,
    );
    out.push({
      props: feature.properties,
      lon: Math.round(lon * 1e6) / 1e6,
      lat: Math.round(lat * 1e6) / 1e6,
    });
  }
  return out;
}

// The place labels of the extract around one point, at the zoom where the
// basemap carries its neighbourhoods.
export async function districtCandidates(source, lon, lat) {
  const archive = new PMTiles(source);
  const centre = tileOf(lon, lat, DISTRICT_ZOOM);
  const out = [];
  for (let x = centre.x - 1; x <= centre.x + 1; x += 1) {
    for (let y = centre.y - 1; y <= centre.y + 1; y += 1) {
      for (const place of await tilePlaces(archive, DISTRICT_ZOOM, x, y)) {
        out.push({
          kind: String(place.props.kind ?? ''),
          name_en: String(place.props['name:en'] ?? ''),
          name_ar: String(place.props['name:ar'] ?? ''),
          lon: place.lon,
          lat: place.lat,
        });
      }
    }
  }
  return out;
}

// Ruling L-143 item 3: the major places the page labels (ruling L-119 item
// 5: the localities the basemap draws from MAJOR_PLACE_ZOOM or lower, inside
// the frame), once each, with the name each language shows, so that the City
// framing can keep their labels clear of the plates. No figure goes with
// them (C4).
export const MAJOR_PLACE_ZOOM = 9;
const PLACE_TILE_ZOOM = 12;

export function majorPlaces(candidates) {
  const seen = new Set();
  const out = [];
  for (const item of candidates) {
    if (item.kind !== 'locality') continue;
    if (!(Number(item.min_zoom ?? 99) <= MAJOR_PLACE_ZOOM)) continue;
    if (item.lon < FRAME[0] || item.lon > FRAME[2]) continue;
    if (item.lat < FRAME[1] || item.lat > FRAME[3]) continue;
    const en = String(item.name_en ?? '');
    const ar = String(item.name_ar ?? '');
    if (en === '' && ar === '') continue;
    const key = `${en}\u0000${ar}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ en, ar, lon: item.lon, lat: item.lat });
  }
  return out;
}

function inFrame(item) {
  return (
    item.lon >= FRAME[0] &&
    item.lon <= FRAME[2] &&
    item.lat >= FRAME[1] &&
    item.lat <= FRAME[3]
  );
}

function readZoom(item) {
  const given = Number(item.min_zoom);
  if (Number.isFinite(given)) return given;
  const read = Number(item.zoom);
  return Number.isFinite(read) ? read : PLACE_TILE_ZOOM;
}

// Round 5g, G2: one label per district name inside the frame. Candidates that
// share an Arabic name, or an English name ignoring case, are one group, and
// groups join through a shared name. The point and both spellings come from
// one candidate, unless the group holds the lit district, whose own point and
// spelling win. The label's min zoom is the lowest in the group.
export function districtLabels(candidates, lit) {
  const kept = [];
  for (const item of candidates) {
    if (!DISTRICT_KINDS.includes(item.kind)) continue;
    if (!inFrame(item)) continue;
    const en = String(item.name_en ?? '');
    const ar = String(item.name_ar ?? '');
    if (en === '' && ar === '') continue;
    const sort = Number(item.sort_key);
    kept.push({
      en,
      ar,
      lon: item.lon,
      lat: item.lat,
      min_zoom: readZoom(item),
      sort_key: Number.isFinite(sort) ? sort : Number.POSITIVE_INFINITY,
    });
  }
  const parent = kept.map((_, index) => index);
  const find = (index) => {
    let root = index;
    while (parent[root] !== root) root = parent[root];
    let cursor = index;
    while (parent[cursor] !== root) {
      const next = parent[cursor];
      parent[cursor] = root;
      cursor = next;
    }
    return root;
  };
  const union = (left, right) => {
    const a = find(left);
    const b = find(right);
    if (a !== b) parent[b] = a;
  };
  const byAr = new Map();
  const byEn = new Map();
  for (let index = 0; index < kept.length; index += 1) {
    const item = kept[index];
    if (item.ar !== '') {
      const other = byAr.get(item.ar);
      if (other === undefined) byAr.set(item.ar, index);
      else union(index, other);
    }
    if (item.en !== '') {
      const key = item.en.toLowerCase();
      const other = byEn.get(key);
      if (other === undefined) byEn.set(key, index);
      else union(index, other);
    }
  }
  const groups = new Map();
  for (let index = 0; index < kept.length; index += 1) {
    const root = find(index);
    const list = groups.get(root);
    if (list === undefined) groups.set(root, [kept[index]]);
    else list.push(kept[index]);
  }
  const out = [];
  for (const group of groups.values()) {
    const minZoom = Math.min(...group.map((item) => item.min_zoom));
    const holdsLit =
      lit !== null &&
      lit !== undefined &&
      group.some(
        (item) =>
          (lit.en !== '' && item.en.toLowerCase() === lit.en.toLowerCase()) ||
          (lit.ar !== '' && item.ar === lit.ar),
      );
    const ranked = [...group].sort((a, b) => {
      const both = (item) => (item.en !== '' && item.ar !== '' ? 0 : 1);
      if (both(a) !== both(b)) return both(a) - both(b);
      if (a.min_zoom !== b.min_zoom) return a.min_zoom - b.min_zoom;
      if (a.sort_key !== b.sort_key) return a.sort_key - b.sort_key;
      if (a.lon !== b.lon) return a.lon - b.lon;
      return a.lat - b.lat;
    });
    const chosen = holdsLit ? lit : ranked[0];
    out.push({
      en: chosen.en,
      ar: chosen.ar,
      lon: chosen.lon,
      lat: chosen.lat,
      min_zoom: minZoom,
    });
  }
  out.sort((a, b) => {
    if (a.en !== b.en) return a.en < b.en ? -1 : 1;
    if (a.ar !== b.ar) return a.ar < b.ar ? -1 : 1;
    if (a.lon !== b.lon) return a.lon - b.lon;
    return a.lat - b.lat;
  });
  return out;
}

// The localities of the extract over the frame, at the zoom of the City
// framing, named as the page's label layer names them (`nameExpression` in
// stage.ts): English from `name:en`, else `name` when no script is given;
// Arabic from `name:ar`, else `name` when its script is Arabic.
async function placeCandidates(source, zoom = PLACE_TILE_ZOOM) {
  const archive = new PMTiles(source);
  const low = tileOf(FRAME[0], FRAME[3], zoom);
  const high = tileOf(FRAME[2], FRAME[1], zoom);
  const out = [];
  for (let x = low.x; x <= high.x; x += 1) {
    for (let y = low.y; y <= high.y; y += 1) {
      for (const place of await tilePlaces(archive, zoom, x, y)) {
        const props = place.props;
        const name = String(props.name ?? '');
        out.push({
          kind: String(props.kind ?? ''),
          min_zoom: props.min_zoom,
          sort_key: props.sort_key,
          zoom,
          name_en: String(
            props['name:en'] ?? (props.script === undefined ? name : ''),
          ),
          name_ar: String(
            props['name:ar'] ?? (props.script === 'Arabic' ? name : ''),
          ),
          lon: place.lon,
          lat: place.lat,
        });
      }
    }
  }
  return out;
}

// District names from zoom 12 to 15: a neighbourhood is in the tiles only
// from its own zoom up, so each of those zooms is read.
async function districtLabelSet(file) {
  const source = new FileSource(file);
  try {
    const candidates = [];
    for (let zoom = 12; zoom <= 15; zoom += 1) {
      candidates.push(...(await placeCandidates(source, zoom)));
    }
    return districtLabels(candidates, null);
  } finally {
    source.close();
  }
}

async function placesOf(file) {
  if (file === null) return [];
  const source = new FileSource(file);
  try {
    return majorPlaces(await placeCandidates(source));
  } finally {
    source.close();
  }
}

const digest = (bytes) => createHash('sha256').update(bytes).digest('hex');
const generatedInput = (dataset, bytes, generator = PIPELINE) => ({
  provenance: 'synthetic',
  origin: 'synthetic',
  dataset,
  generator: { ...generator },
  sha256: digest(bytes),
});
const SCALE_INPUT = generatedInput(
  'Look scale configuration',
  JSON.stringify(BREAKS),
);

function chain(method, table = 'chain.table', input) {
  return {
    table,
    method,
    method_version: VERSION,
    source: 'chain.source',
    generator: { ...PIPELINE },
    inputs: Array.isArray(input) ? input : [input],
  };
}

function fact(id, value, unit, unitKey, geographyKey, method, table, input) {
  const inputs = Array.isArray(input) ? input : [input];
  const classes = inputs.map((item) => item.provenance);
  const provenance = classes.includes('synthetic') ? 'synthetic' : 'public';
  return {
    id,
    value,
    unit,
    unit_key: unitKey,
    provenance,
    ...(provenance === 'public' ? {} : { origin: provenance }),
    input_classes: classes,
    geography_key: geographyKey,
    chain: chain(method, table, input),
  };
}

// No summary exists without cells. Scale configuration is independent of
// coverage and retains its own method and producing record.
export function releaseFacts(
  cells,
  area = cellArea,
  input = generatedInput('Look cell inputs', JSON.stringify(cells)),
) {
  const facts = [];
  if (cells.length > 0) {
    let firms = 0;
    let land = 0;
    let top = 0;
    let hero = 0;
    for (const [cell, value, step] of cells) {
      const size = area(cell, 'km2');
      firms += value * size;
      land += size;
      if (step >= SHARE_FROM_STEP) top += value * size;
      hero = Math.max(hero, value);
    }
    const mean = Math.round(firms / land);
    const share = Math.round((top / firms) * 100) / 100;
    facts.push(
      fact(
        'densest-unit',
        hero,
        'count',
        'unit.firmsPerSqKm',
        'fact.densest',
        'chain.methodUnit',
        undefined,
        input,
      ),
      fact(
        'areas-with-firms',
        mean,
        'count',
        'unit.firmsPerSqKm',
        'fact.extent',
        'chain.methodMean',
        undefined,
        input,
      ),
      fact(
        'top-classes',
        share,
        'share',
        'unit.ofFirms',
        'fact.topClasses',
        'chain.methodShare',
        undefined,
        input,
      ),
    );
  }
  for (const [index, limit] of BREAKS.entries()) {
    facts.push(
      fact(
        `break-${index + 1}`,
        limit,
        'count',
        'unit.firmsPerSqKm',
        'fact.break',
        'chain.methodBreaks',
        'chain.tableScale',
        SCALE_INPUT,
      ),
    );
  }
  return facts;
}

function typeSlug(type) {
  return type
    .toLowerCase()
    .replace(/[^a-z]+/g, '-')
    .replace(/^-|-$/g, '');
}

function typeFacts(counts, input) {
  const facts = [];
  for (const type of [...counts.keys()].sort()) {
    const slug = typeSlug(type);
    if (slug === '') continue;
    facts.push(
      fact(
        `type-${slug}`,
        counts.get(type),
        'count',
        'unit.establishments',
        'fact.type',
        'chain.methodType',
        'chain.tableRegister',
        input,
      ),
    );
  }
  return facts;
}

// Round 5g, finding 15 (rules 7 and 23): the number of employees and of
// branches on a company card are released facts with a chain to the register
// file, one per establishment and field that carries a value.
const ESTABLISHMENT_COUNTS = [
  ['employees', 'unit.employees', 'chain.methodEmployees'],
  ['branches', 'unit.branches', 'chain.methodBranches'],
];

function establishmentFacts(rows, input) {
  const facts = [];
  const labour = generatedInput(
    'Attached labour records',
    JSON.stringify(rows.map((row) => [row.row_key, row.employees])),
    REGISTER_PIPELINE,
  );
  for (const row of rows) {
    for (const [name, unitKey, method] of ESTABLISHMENT_COUNTS) {
      if (row[name] === null || row[name] === undefined) continue;
      facts.push(
        fact(
          `${row.row_key}-${name}`,
          row[name],
          'count',
          unitKey,
          'fact.establishment',
          method,
          name === 'employees' ? 'chain.tableLabour' : 'chain.tableRegister',
          name === 'employees' ? labour : input,
        ),
      );
    }
  }
  return facts;
}

export function assemble(cells, basemap, extra = {}) {
  const types = extra.types ?? new Map();
  const establishments = extra.establishments ?? [];
  const input =
    extra.input ??
    generatedInput(
      'Look aggregate inputs',
      JSON.stringify({ cells, establishments, types: [...types] }),
    );
  return validateRelease({
    release_id: RELEASE_ID,
    basemap,
    buildings: extra.buildings ?? { present: false },
    district: extra.district ?? null,
    places: extra.places ?? [],
    district_labels: extra.district_labels ?? [],
    period: extra.period,
    layer: {
      id: 'firm_density',
      unit_key: 'unit.firmsPerSqKm',
      provenance: extra.input?.provenance ?? 'synthetic',
      ...(extra.input?.provenance === 'public'
        ? {}
        : { origin: 'synthetic', generator: { ...PIPELINE } }),
      resolution: RESOLUTION,
      breaks: BREAKS,
      cells,
    },
    origin: 'synthetic',
    generator: { ...PIPELINE },
    coverage: cells.length === 0 ? 'not_measured' : 'available',
    facts: [
      ...releaseFacts(cells, cellArea, input),
      ...typeFacts(types, input),
      ...establishmentFacts(establishments, input),
    ],
    firms: [],
    establishments,
  });
}

function publicInput(raw, bytes) {
  let metadata;
  try {
    metadata = JSON.parse(raw);
  } catch {
    throw new Error('release refused: Public source metadata');
  }
  const input = { ...metadata, provenance: 'public' };
  if (!validInput(input))
    throw new Error('release refused: Public source chain metadata');
  if (input.sha256 !== digest(bytes))
    throw new Error('release refused: source hash mismatch');
  return input;
}

function registerLayer(repositoryRoot, env, standInFile) {
  const located = standInFile
    ? { ok: true, standIn: true, file: standInFile }
    : locateRegister(repositoryRoot, env);
  if (!located.ok) return null;
  const period = registerPeriod(located, env);
  const bytes = fs.readFileSync(located.file);
  const rows = parseRegister(bytes.toString('utf8'));
  const input = located.standIn
    ? generatedInput('Look establishment records', bytes, REGISTER_PIPELINE)
    : publicInput(env.EII_REGISTER_SOURCE, bytes);

  const counts = countsByCell(rows, { resolution: RESOLUTION, frame: FRAME });
  return {
    period,
    input,
    establishments: rows,
    types: countsByType(rows),
    cells: cellsFromCounts(counts, { area: cellArea, classOf }),
  };
}

// The release the page is served with. When a register file is present the
// lit layer is the establishment count per cell, as firms per square
// kilometre, and the Brief reads those cells. Without a register the layer
// still follows the extract's buildings, and without either it is empty.
export async function buildRelease(
  repositoryRoot,
  env = process.env,
  standInFile,
) {
  const located = locateBasemap(repositoryRoot);
  const basemap = located.ok
    ? { present: true, url: BASEMAP_ROUTE }
    : { present: false, missing: located.detail };
  const file = located.ok ? located.file : null;
  const buildings = locateBuildings(repositoryRoot).ok
    ? { present: true, url: BUILDINGS_ROUTE }
    : { present: false };
  const fromRegister = registerLayer(repositoryRoot, env, standInFile);
  const places = await placesOf(file);
  const district_labels = file === null ? [] : await districtLabelSet(file);
  // Round 5g, finding 13: the layer is invented (the stand-in, or the
  // buildings' floor area), so no real district is named over it; a district
  // is named only over a public layer (validateRelease refuses otherwise).
  if (fromRegister !== null) {
    return {
      release: assemble(fromRegister.cells, basemap, {
        ...fromRegister,
        buildings,
        places,
        district_labels,
      }),
      file,
    };
  }
  // Without a register the layer is the look proof's own fixture, dated as
  // the stand-in it stands for.
  const period = STAND_IN_DATE;
  if (!located.ok) {
    return {
      release: assemble([], basemap, { buildings, period, district_labels }),
      file: null,
    };
  }
  const source = new FileSource(located.file);
  let cells;
  try {
    cells = inventCells(smooth(await floorAreas(source)));
  } finally {
    source.close();
  }
  return {
    release: assemble(cells, basemap, {
      buildings,
      places,
      period,
      district_labels,
      input: [
        generatedInput(
          'Look building-density inputs',
          JSON.stringify({
            HERO_VALUE,
            CURVE,
            FLOOR,
            STOREY,
            FOOTPRINT_CAP,
            OWN_SHARE,
          }),
        ),
        publicInput(env.EII_BASEMAP_SOURCE, fs.readFileSync(located.file)),
      ],
    }),
    file,
  };
}
