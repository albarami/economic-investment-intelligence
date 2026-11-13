import names from './names.json' with { type: 'json' };

export const SYNTHETIC_NOTE =
  'Synthetic fixture. Invented geometry and invented names. No real place.';
export const LABEL_LAYER_ID = 'labels';
export const SCENE_CENTER: LngLat = [0.015, 0.015];
export const SCENE_ZOOM = 15.2;
export const OVERLAP_ZOOM = 16.6;
const BOX_WEST = 0.01;
const BOX_EAST = 0.02;
const BOX_SOUTH = 0.01;
const BOX_NORTH = 0.02;
const BUILDING_HALF = 0.00045;
const BUILDING_SHIFT = 0.0008;
const HEX_RADIUS = 0.0015;
const HEX_SIDES = 6;

export type LngLat = [number, number];
export type Lang = 'ar' | 'en';

type Place = {
  id: string;
  nameEn: string;
  nameAr: string;
  review: string;
};

const COORDINATES: Record<string, LngLat> = {
  aleph: [0.012, 0.012],
  bet: [0.018, 0.012],
  gimel: [0.012, 0.018],
  dalet: [0.018, 0.018],
  he: [0.015, 0.015],
};

export type FixtureFeature = {
  type: 'Feature';
  properties: { kind: string; label: string; id: string; note?: string };
  geometry:
    | { type: 'Polygon'; coordinates: LngLat[][] }
    | { type: 'Point'; coordinates: LngLat };
};

export type Fixture = {
  featureKey: string;
  labelNames: string[];
  collection: {
    type: 'FeatureCollection';
    features: FixtureFeature[];
  };
};

function placeList(): Place[] {
  return names.places;
}

function coordinateFor(id: string): LngLat {
  const point = COORDINATES[id];
  if (point === undefined)
    throw new Error(`missing synthetic coordinate: ${id}`);
  return point;
}

function closed(ring: LngLat[]): LngLat[] {
  const first = ring[0];
  if (first === undefined) throw new Error('ring is empty');
  return [...ring, [first[0], first[1]]];
}

function buildingRing(center: LngLat): LngLat[] {
  const lng = center[0] + BUILDING_SHIFT;
  const lat = center[1] - BUILDING_SHIFT;
  return closed([
    [lng - BUILDING_HALF, lat - BUILDING_HALF],
    [lng + BUILDING_HALF, lat - BUILDING_HALF],
    [lng + BUILDING_HALF, lat + BUILDING_HALF],
    [lng - BUILDING_HALF, lat + BUILDING_HALF],
  ]);
}

export function hexagonRing(center: LngLat): LngLat[] {
  const ring: LngLat[] = [];
  for (let side = 0; side < HEX_SIDES; side += 1) {
    const angle = (Math.PI / 3) * side;
    ring.push([
      center[0] + HEX_RADIUS * Math.cos(angle),
      center[1] + HEX_RADIUS * Math.sin(angle),
    ]);
  }
  return closed(ring);
}

export function firstLabelCenter(): LngLat {
  const first = placeList()[0];
  if (first === undefined) throw new Error('synthetic places are empty');
  return coordinateFor(first.id);
}

export function fixture(lang: Lang): Fixture {
  const places = placeList();
  const features: FixtureFeature[] = [
    {
      type: 'Feature',
      properties: { kind: 'land', label: '', id: 'land', note: SYNTHETIC_NOTE },
      geometry: {
        type: 'Polygon',
        coordinates: [
          closed([
            [BOX_WEST, BOX_SOUTH],
            [BOX_EAST, BOX_SOUTH],
            [BOX_EAST, BOX_NORTH],
            [BOX_WEST, BOX_NORTH],
          ]),
        ],
      },
    },
  ];
  const labelNames: string[] = [];
  for (const place of places) {
    const center = coordinateFor(place.id);
    const label = lang === 'ar' ? place.nameAr : place.nameEn;
    labelNames.push(label);
    features.push({
      type: 'Feature',
      properties: { kind: 'building', label: '', id: place.id },
      geometry: { type: 'Polygon', coordinates: [buildingRing(center)] },
    });
    features.push({
      type: 'Feature',
      properties: { kind: 'label', label, id: place.id },
      geometry: { type: 'Point', coordinates: center },
    });
  }
  return {
    featureKey: places.map((place) => place.id).join('.'),
    labelNames,
    collection: {
      type: 'FeatureCollection',
      features,
    },
  };
}
