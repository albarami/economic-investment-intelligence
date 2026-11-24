import { completeFactChain, validGenerator } from './lineage.mjs';
// The shape of the release the look page reads, shared by the server's
// release build (Node) and the page (browser). It is the shape a release
// file of task S4-T11 can take in place of the invented one: per-cell
// aggregates of one layer, the facts of the Brief and the legend with their
// chains, and named firms with name, activity, size band and cell only
// (SYN-21: a named firm never carries its wages, wage bill or headcount).

export const RELEASE_ID = 'R2611-A';
export const CLASSES = ['public', 'synthetic', 'simulated', 'suppressed'];
export const UNITS = ['count', 'share'];
// Round 5g, finding 24: the share of firms in the densest areas counts the
// classes from this one up; its lower bound is the third break, which the
// legend marks as "Densest areas".
export const SHARE_FROM_STEP = 4;
export const FIRM_KEYS = ['name', 'activity', 'size_band', 'cell'];

// Published columns of the establishment register. A point and its card
// carry these and nothing else.
export const ESTABLISHMENT_REQUIRED = [
  'row_key',
  'name_ar',
  'establishment_type',
  'legal_form',
  'business_type',
  'registration_status',
  'municipality',
  'lon',
  'lat',
];
export const ESTABLISHMENT_OPTIONAL = [
  'name_en',
  'establishment_subtype',
  'business_category',
  'classification',
  'registration_issue_date',
  'registration_expiry_date',
  'licence_status',
  'licence_issue_date',
  'licence_expiry_date',
  'branches',
  'zone',
  // The owner's decision of 2026-11-13: the company card shows the number
  // of employees. No wage or other labour field is a published field.
  'employees',
];
// Optional fields that hold a whole number or nothing.
const WHOLE_FIELDS = ['branches', 'employees'];
const ESTABLISHMENT_KEYS = [
  ...ESTABLISHMENT_REQUIRED,
  ...ESTABLISHMENT_OPTIONAL,
];

function refuse(detail) {
  throw new Error(`release refused: ${detail}`);
}

function text(value, where) {
  if (typeof value !== 'string' || value.trim() === '') refuse(where);
  return value;
}

function number(value, where) {
  if (typeof value !== 'number' || !Number.isFinite(value)) refuse(where);
  return value;
}

function validateFact(fact, index) {
  const where = `fact ${index + 1}`;
  if (fact === null || typeof fact !== 'object') refuse(where);
  if (!UNITS.includes(fact.unit)) refuse(`${where} unit`);
  if (!CLASSES.includes(fact.provenance)) refuse(`${where} class`);
  if (!Array.isArray(fact.input_classes)) refuse(`${where} input classes`);
  for (const item of fact.input_classes) {
    if (!CLASSES.includes(item)) refuse(`${where} input class`);
  }
  if (!completeFactChain(fact)) refuse(`${where} chain or origin`);
  return {
    ...(fact.origin ? { origin: fact.origin } : {}),
    id: text(fact.id, `${where} id`),
    value: number(fact.value, `${where} value`),
    unit: fact.unit,
    unit_key: text(fact.unit_key, `${where} unit key`),
    provenance: fact.provenance,
    input_classes: [...fact.input_classes],
    geography_key: text(fact.geography_key, `${where} geography`),
    chain: structuredClone(fact.chain),
  };
}

// The view of a fact the Fact chip reads.
export function factView(fact) {
  return {
    id: fact.id,
    ...(fact.origin ? { origin: fact.origin } : {}),
    value: fact.value,
    unit: fact.unit,
    unitKey: fact.unit_key,
    provenance: fact.provenance,
    inputClasses: [...fact.input_classes],
    geographyKey: fact.geography_key,
    chain: fact.chain === null ? null : { ...fact.chain },
  };
}

function validateFirm(firm, index) {
  const where = `firm ${index + 1}`;
  if (firm === null || typeof firm !== 'object') refuse(where);
  for (const key of Object.keys(firm)) {
    if (!FIRM_KEYS.includes(key)) {
      refuse(
        `${where} carries ${key}; a named firm carries only name, activity, size band and cell`,
      );
    }
  }
  return {
    name: text(firm.name, `${where} name`),
    activity: text(firm.activity, `${where} activity`),
    size_band: text(firm.size_band, `${where} size band`),
    cell: text(firm.cell, `${where} cell`),
  };
}

function validateEstablishment(row, index) {
  const where = `establishment ${index + 1}`;
  if (row === null || typeof row !== 'object') refuse(where);
  for (const key of Object.keys(row)) {
    if (!ESTABLISHMENT_KEYS.includes(key)) {
      refuse(`${where} carries ${key}; a point carries only published fields`);
    }
  }
  const out = {};
  for (const key of ESTABLISHMENT_OPTIONAL) {
    if (WHOLE_FIELDS.includes(key)) continue;
    out[key] = typeof row[key] === 'string' ? row[key] : '';
  }
  for (const key of WHOLE_FIELDS) {
    if (row[key] === null || row[key] === undefined || row[key] === '') {
      out[key] = null;
    } else {
      out[key] = number(row[key], `${where} ${key}`);
    }
  }
  for (const key of ESTABLISHMENT_REQUIRED) {
    if (key === 'lon' || key === 'lat') {
      out[key] = number(row[key], `${where} ${key}`);
      continue;
    }
    out[key] = text(row[key], `${where} ${key}`);
  }
  return out;
}

// The lit district: an area name from the basemap's own labels, in both
// languages, and the point of its label. It carries no figure (C4).
// Round 5g, finding 13 (AI-117, CLAUDE.md rules 8 and 24): a district is
// named only over a public layer; an invented layer names no real place.
const DISTRICT_KEYS = ['en', 'ar', 'lon', 'lat'];
function validateDistrict(district, provenance) {
  if (district === null || district === undefined) return null;
  if (provenance !== 'public')
    refuse('a district is named only on a public layer');
  if (typeof district !== 'object') refuse('district');
  for (const key of Object.keys(district)) {
    if (!DISTRICT_KEYS.includes(key)) refuse(`district carries ${key}`);
  }
  return {
    en: text(district.en, 'district en'),
    ar: text(district.ar, 'district ar'),
    lon: number(district.lon, 'district lon'),
    lat: number(district.lat, 'district lat'),
  };
}

// Ruling L-143 item 3: the label points of the major places, with the name
// each language shows (empty where it shows none), so that the City framing
// keeps them clear of the plates. Real names from the basemap's own labels
// only, and no figure (C4).
const PLACE_KEYS = ['en', 'ar', 'lon', 'lat'];
const DISTRICT_LABEL_KEYS = ['en', 'ar', 'lon', 'lat', 'min_zoom'];
function validatePlaces(places) {
  if (places === undefined) return [];
  if (!Array.isArray(places)) refuse('places');
  return places.map((place) => {
    if (place === null || typeof place !== 'object') refuse('place');
    for (const key of Object.keys(place)) {
      if (!PLACE_KEYS.includes(key)) refuse(`place carries ${key}`);
    }
    for (const key of ['en', 'ar']) {
      if (typeof place[key] !== 'string') refuse(`place ${key}`);
    }
    if (place.en === '' && place.ar === '') refuse('place has no name');
    return {
      en: place.en,
      ar: place.ar,
      lon: number(place.lon, 'place lon'),
      lat: number(place.lat, 'place lat'),
    };
  });
}

// Round 5g, G2: one label point per district name. The same keys as a place,
// plus the zoom it may appear from. No figure rides on a name.
function validateDistrictLabels(labels) {
  if (labels === undefined) return [];
  if (!Array.isArray(labels)) refuse('district labels');
  return labels.map((label) => {
    if (label === null || typeof label !== 'object') refuse('district label');
    for (const key of Object.keys(label)) {
      if (!DISTRICT_LABEL_KEYS.includes(key))
        refuse(`district label carries ${key}`);
    }
    for (const key of ['en', 'ar']) {
      if (typeof label[key] !== 'string') refuse(`district label ${key}`);
    }
    if (label.en === '' && label.ar === '')
      refuse('district label has no name');
    return {
      en: label.en,
      ar: label.ar,
      lon: number(label.lon, 'district label lon'),
      lat: number(label.lat, 'district label lat'),
      min_zoom: number(label.min_zoom, 'district label min zoom'),
    };
  });
}

// Round 5g, finding 22 (DES-68): the date of the count the layer shows, a
// calendar date written YYYY-MM-DD. It is a reference, never a fact value.
function validatePeriod(period) {
  if (typeof period !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(period))
    refuse('period is not a date');
  const [year, month, day] = period.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  )
    refuse('period is not a calendar date');
  return period;
}

function validateCells(cells, breaks) {
  if (!Array.isArray(cells)) refuse('layer cells');
  return cells.map((row, index) => {
    if (!Array.isArray(row) || row.length !== 3) refuse(`cell ${index + 1}`);
    const [cell, value, step] = row;
    text(cell, `cell ${index + 1} id`);
    number(value, `cell ${index + 1} value`);
    if (!Number.isInteger(step) || step < 1 || step > breaks.length + 1)
      refuse(`cell ${index + 1} class`);
    return [cell, value, step];
  });
}

export function validateRelease(release) {
  if (release === null || typeof release !== 'object') refuse('not an object');
  const basemap = release.basemap;
  if (basemap === null || typeof basemap !== 'object') refuse('basemap');
  const map =
    basemap.present === true
      ? { present: true, url: text(basemap.url, 'basemap url') }
      : { present: false, missing: text(basemap.missing, 'basemap missing') };
  const layer = release.layer;
  if (layer === null || typeof layer !== 'object') refuse('layer');
  if (!Array.isArray(layer.breaks) || layer.breaks.length !== 4)
    refuse('layer breaks');
  layer.breaks.forEach((value, index) => {
    number(value, `break ${index + 1}`);
    if (index > 0 && value <= layer.breaks[index - 1])
      refuse('layer breaks are not ascending');
  });
  if (!CLASSES.includes(layer.provenance)) refuse('layer class');
  if (!Array.isArray(release.facts)) refuse('facts');
  if (!Array.isArray(release.firms)) refuse('firms');
  const establishments = Array.isArray(release.establishments)
    ? release.establishments
    : [];
  const facts = release.facts.map(validateFact);
  if (
    (facts.some((fact) => fact.origin !== undefined) ||
      ['synthetic', 'simulated'].includes(layer.provenance)) &&
    (release.origin !== 'synthetic' || !validGenerator(release.generator))
  )
    refuse('release origin or generator');
  if (
    ['synthetic', 'simulated'].includes(layer.provenance) &&
    (layer.origin !== layer.provenance || !validGenerator(layer.generator))
  )
    refuse('layer origin or generator');
  if (
    layer.cells.length === 0 &&
    facts.some(
      (fact) =>
        ['densest-unit', 'areas-with-firms', 'top-classes'].includes(fact.id) ||
        ['chain.methodUnit', 'chain.methodMean', 'chain.methodShare'].includes(
          fact.chain.method,
        ),
    )
  )
    refuse('summary without coverage');
  const ids = new Set();
  for (const fact of facts) {
    if (ids.has(fact.id)) refuse(`fact ${fact.id} twice`);
    ids.add(fact.id);
  }
  const archive = release.buildings;
  const buildings =
    archive !== null && typeof archive === 'object' && archive.present === true
      ? { present: true, url: text(archive.url, 'buildings url') }
      : { present: false };
  return {
    origin: release.origin,
    generator: release.generator,
    coverage: layer.cells.length === 0 ? 'not_measured' : 'available',
    release_id: text(release.release_id, 'release id'),
    basemap: map,
    buildings,
    district: validateDistrict(release.district, layer.provenance),
    places: validatePlaces(release.places),
    district_labels: validateDistrictLabels(release.district_labels),
    period: validatePeriod(release.period),
    layer: {
      id: text(layer.id, 'layer id'),
      unit_key: text(layer.unit_key, 'layer unit'),
      provenance: layer.provenance,
      ...(layer.origin
        ? { origin: layer.origin, generator: layer.generator }
        : {}),
      resolution: number(layer.resolution, 'layer resolution'),
      breaks: [...layer.breaks],
      cells: validateCells(layer.cells, layer.breaks),
    },
    facts,
    firms: release.firms.map(validateFirm),
    establishments: establishments.map(validateEstablishment),
  };
}

// The release serialised for a data block inside the page: "<" is escaped,
// so that no "</script>" can close the block early.
export function serialiseRelease(release) {
  return JSON.stringify(release).replace(/</g, '\\u003c');
}
