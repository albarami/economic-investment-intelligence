// Establishment points from the register: clustered from district zoom to
// zoom 14, single points from zoom 14, a card of published fields, and one
// business type highlighted when the legend asks for it. A cluster is drawn by
// its size alone: no numeral is drawn on the map outside a Fact chip.
import type {
  ExpressionSpecification,
  GeoJSONSource,
  LayerSpecification,
  Map as MapLibreMap,
} from 'maplibre-gl';
import { compactChip, referenceChip, valueChip } from './fact-chip';
import { bind, bindText, has, lang, t } from './i18n';
import type { EstablishmentRecord } from './release-shape.mjs';
import type { Loaded } from './release';
import { token, tokenNumber } from './tokens';

export const CLUSTER_LAYER = 'establishments-cluster';
export const POINT_LAYER = 'establishments-point';
export const FIRM_SOURCE = 'establishments';
export const POINT_ZOOM = 14;
// A dot is this wide, and the ring adds this many pixels around it. The
// district name's clearing is the sum, so a dot centred on a stroke cannot
// show through the letter.
export const POINT_RADIUS = 6;
export const POINT_RING = 2;

const DIGIT = /\p{Nd}/u;

export function establishmentCollection(rows: EstablishmentRecord[]) {
  return {
    type: 'FeatureCollection' as const,
    features: rows.map((row) => ({
      type: 'Feature' as const,
      geometry: {
        type: 'Point' as const,
        coordinates: [row.lon, row.lat] as [number, number],
      },
      properties: {
        row_key: row.row_key,
        business_type: row.business_type,
      },
    })),
  };
}

// Round 5g, finding 1 (DES-21, dataviz: no value ramp for a category, never
// cycle): one chosen type in ink, every other point in the strong line
// colour; colouring every type in its own hue needs a decision record.
export function highlightType(
  chosen: string,
  ink: string,
  rest: string,
): ExpressionSpecification {
  return ['case', ['==', ['get', 'business_type'], chosen], ink, rest];
}

// The stand-in's business types, named from the catalogue. A type of a
// register file with no key is shown as published.
export const TYPE_KEYS = [
  'type.bakery',
  'type.grocery',
  'type.pharmacy',
  'type.tailor',
  'type.workshop',
];

// Round 5g, findings 1, 18 and 19: a dot and a circle are ink, never a
// colour of the density ramp, with a ring of the ground's colour that parts
// a dot from the brightest class (DES-68: the legend keys both).
export function establishmentLayers(paint: {
  point: string;
  ring: string;
  visible: boolean;
}): LayerSpecification[] {
  const visibility = paint.visible ? 'visible' : 'none';
  return [
    {
      id: CLUSTER_LAYER,
      type: 'circle',
      source: FIRM_SOURCE,
      filter: ['has', 'point_count'],
      minzoom: tokenNumber('--eii-cluster-zoom'),
      maxzoom: POINT_ZOOM,
      layout: { visibility },
      paint: {
        'circle-color': paint.point,
        'circle-radius': ['step', ['get', 'point_count'], 10, 8, 14, 24, 18],
        'circle-stroke-width': POINT_RING,
        'circle-stroke-color': paint.ring,
      },
    },
    {
      id: POINT_LAYER,
      type: 'circle',
      source: FIRM_SOURCE,
      filter: ['!', ['has', 'point_count']],
      minzoom: POINT_ZOOM,
      layout: { visibility },
      paint: {
        'circle-color': paint.point,
        'circle-radius': POINT_RADIUS,
        'circle-stroke-width': POINT_RING,
        'circle-stroke-color': paint.ring,
      },
    },
  ];
}

function slug(type: string): string {
  return type
    .toLowerCase()
    .replace(/[^a-z]+/g, '-')
    .replace(/^-|-$/g, '');
}

function shownName(row: EstablishmentRecord): string {
  if (lang() === 'ar') return row.name_ar;
  return row.name_en !== '' ? row.name_en : row.name_ar;
}

// Round 5g, finding 15: a digit stands in a reference chip only in the
// record dates, the zone and the classification code; a count is a value
// chip of a released fact (below), so no count falls back to a reference.
const REFERENCE_FIELDS = [
  'field.registrationIssue',
  'field.registrationExpiry',
  'field.licenceIssue',
  'field.licenceExpiry',
  'field.zone',
  'field.classification',
];

function fieldRow(label: string, body: HTMLElement): HTMLElement {
  const row = document.createElement('div');
  row.className = 'point-field';
  row.dataset.field = label;
  const name = document.createElement('span');
  name.className = 'point-label';
  bindText(name, () => t(label));
  row.append(name, body);
  return row;
}

function field(label: string, value: string): HTMLElement | null {
  if (value.trim() === '') return null;
  if (DIGIT.test(value)) {
    if (!REFERENCE_FIELDS.includes(label))
      throw new Error(`${label} carries a digit outside a fact`);
    return fieldRow(label, referenceChip(value));
  }
  const body = document.createElement('span');
  body.textContent = value;
  return fieldRow(label, body);
}

function fillCard(
  card: HTMLElement,
  row: EstablishmentRecord,
  loaded: Loaded,
  openDrawer: (fact: ReturnType<Loaded['fact']>) => void,
): void {
  card.replaceChildren();
  const head = document.createElement('div');
  head.className = 'point-head';
  const title = document.createElement('h2');
  title.className = 'point-title';
  const paint = () => {
    title.textContent = shownName(row);
    title.lang = lang();
  };
  bind(paint);
  const close = document.createElement('button');
  close.type = 'button';
  close.className = 'control';
  close.dataset.control = 'point-close';
  bindText(close, () => t('point.close'));
  close.addEventListener('click', () => {
    card.hidden = true;
    card.replaceChildren();
  });
  head.append(title, close);
  const fields = document.createElement('div');
  fields.className = 'point-fields';
  // The ministry's card fields plus the number of employees; the position
  // is the map's, not a card field (round 5g, finding 15).
  const pairs: [string, string | 'branches' | 'employees'][] = [
    ['field.business', row.business_type],
    ['field.category', row.business_category],
    ['field.kind', row.establishment_type],
    ['field.subtype', row.establishment_subtype],
    ['field.legal', row.legal_form],
    ['field.classification', row.classification],
    ['field.registration', row.registration_status],
    ['field.registrationIssue', row.registration_issue_date],
    ['field.registrationExpiry', row.registration_expiry_date],
    ['field.licence', row.licence_status],
    ['field.licenceIssue', row.licence_issue_date],
    ['field.licenceExpiry', row.licence_expiry_date],
    ['field.branches', 'branches'],
    ['field.employees', 'employees'],
    ['field.municipality', row.municipality],
    ['field.zone', row.zone],
  ];
  for (const [label, value] of pairs) {
    if (value === 'branches' || value === 'employees') {
      if (row[value] === null) continue;
      fields.append(
        fieldRow(
          label,
          valueChip(
            loaded.fact(`${row.row_key}-${value}`),
            'standard',
            openDrawer,
          ),
        ),
      );
      continue;
    }
    const line = field(label, value);
    if (line !== null) fields.append(line);
  }
  card.append(head, fields);
}

export function mountEstablishments(
  map: MapLibreMap,
  loaded: Loaded,
  legend: HTMLElement,
  overlay: HTMLElement,
  openDrawer: (fact: ReturnType<Loaded['fact']>) => void,
): void {
  const rows = loaded.release.establishments;
  if (rows.length === 0) return;
  const byKey = new Map(rows.map((row) => [row.row_key, row]));
  const card = document.createElement('section');
  card.className = 'point-card';
  card.hidden = true;
  card.dataset.part = 'point-card';
  overlay.append(card);

  const open = (key: string) => {
    const row = byKey.get(key);
    if (row === undefined) return;
    fillCard(card, row, loaded, openDrawer);
    card.hidden = false;
  };

  // The street tests open a card by its row key, as a click would.
  if (window.__look !== undefined) window.__look.openPoint = open;
  map.on('click', POINT_LAYER, (event) => {
    const key = event.features?.[0]?.properties?.row_key;
    if (typeof key === 'string') open(key);
  });
  map.on('click', CLUSTER_LAYER, async (event) => {
    const feature = event.features?.[0];
    const source = map.getSource('establishments');
    const raw = feature?.properties?.cluster_id;
    const cluster = typeof raw === 'number' ? raw : Number(raw);
    if (!(source instanceof Object) || !Number.isInteger(cluster)) return;
    const geo = source as GeoJSONSource;
    const zoom = await geo.getClusterExpansionZoom(cluster);
    map.easeTo({ center: event.lngLat, zoom });
  });

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'control';
  button.dataset.control = 'types';
  button.setAttribute('aria-pressed', 'false');
  bindText(button, () => t('legend.byType'));
  const list = document.createElement('div');
  list.className = 'type-counts';
  list.hidden = true;
  const types = [...new Set(rows.map((row) => row.business_type))]
    .filter((type) => slug(type) !== '')
    .sort();
  const foot = legend.querySelector('.legend-foot');
  const toggle = foot?.querySelector('[data-control="table"]');
  if (foot instanceof HTMLElement && toggle instanceof HTMLElement) {
    const actions = document.createElement('div');
    actions.className = 'legend-actions';
    actions.append(toggle, button);
    foot.append(actions);
  }

  // Rounds 5g, findings 18 and 19 (DES-68): the key of the marks the map
  // shows, the dot from the point zoom and the circle between the cluster
  // zoom and it; neither at the City framing. It stays on the folded strip.
  const marks = document.createElement('div');
  marks.className = 'legend-points';
  const mark = (name: 'point' | 'cluster', read: () => string) => {
    const line = document.createElement('p');
    line.className = 'legend-mark';
    const sample = document.createElement('span');
    sample.className = `legend-mark-sample legend-mark-${name}`;
    sample.setAttribute('aria-hidden', 'true');
    const words = document.createElement('span');
    words.dataset.key = name;
    bindText(words, read);
    line.append(sample, words);
    marks.append(line);
    return line;
  };
  const dotKey = mark('point', () => t('legend.point'));
  const circleKey = mark('cluster', () => t('legend.cluster'));
  if (foot instanceof HTMLElement) legend.insertBefore(marks, foot);
  else legend.append(marks);
  legend.append(list);

  let coloured = false;
  let chosen: string | null = null;
  const paintPoints = () => {
    const ink = token('--eii-map-point');
    map.setPaintProperty(
      POINT_LAYER,
      'circle-color',
      chosen === null
        ? ink
        : highlightType(chosen, ink, token('--eii-line-strong')),
    );
  };
  // Round 5g, finding 11: the control acts on the single points alone,
  // drawn from POINT_ZOOM; below it the control and its type list are
  // hidden, and the choice is kept. 'zoom' fires on a jump too.
  const clusterZoom = tokenNumber('--eii-cluster-zoom');
  const offered = () => {
    const zoom = map.getZoom();
    const shown = zoom >= POINT_ZOOM;
    button.hidden = !shown;
    list.hidden = !shown || !coloured;
    dotKey.hidden = !shown;
    circleKey.hidden = shown || zoom < clusterZoom;
  };
  map.on('zoom', offered);
  offered();
  map.on('style.load', () => {
    if (map.getLayer(POINT_LAYER) !== undefined) paintPoints();
  });
  const picks: HTMLButtonElement[] = [];
  const pick = (type: string | null) => {
    chosen = type;
    for (const item of picks)
      item.setAttribute(
        'aria-pressed',
        String(item.dataset.pick === (type ?? '')),
      );
    paintPoints();
  };
  button.addEventListener('click', () => {
    coloured = !coloured;
    button.setAttribute('aria-pressed', String(coloured));
    offered();
    if (!coloured) pick(null);
    if (!coloured || list.childElementCount > 0) return;
    // Round 5g, finding 16: the list names its unit in a heading, as the
    // legend's title does for the breaks.
    const title = document.createElement('h3');
    title.className = 'type-counts-title';
    title.id = 'type-counts-title';
    bindText(title, () => t('legend.types.title'));
    list.append(title);
    list.setAttribute('role', 'group');
    list.setAttribute('aria-labelledby', title.id);
    for (const type of types) {
      const slugged = slug(type);
      const line = document.createElement('div');
      line.className = 'type-row';
      line.dataset.type = slugged;
      const choice = document.createElement('button');
      choice.type = 'button';
      choice.className = 'type-pick';
      choice.dataset.pick = type;
      choice.setAttribute('aria-pressed', 'false');
      const swatch = document.createElement('span');
      swatch.className = 'type-swatch';
      swatch.setAttribute('aria-hidden', 'true');
      const name = document.createElement('span');
      name.className = 'type-name';
      const key = `type.${slugged}`;
      if (has(key)) bindText(name, () => t(key));
      else {
        const raw = document.createElement('bdi');
        raw.dir = 'auto';
        raw.textContent = type;
        name.append(raw);
      }
      choice.append(swatch, name);
      choice.addEventListener('click', () =>
        pick(chosen === type ? null : type),
      );
      picks.push(choice);
      line.append(
        choice,
        compactChip(loaded.fact(`type-${slugged}`), openDrawer),
      );
      list.append(line);
    }
  });
}
