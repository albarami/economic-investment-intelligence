/**
 * Theme style, local pmtiles source, name-field allow-list, flat buildings.
 * The map is never mirrored.
 */
import { layers, namedFlavor, type Flavor } from '@protomaps/basemaps';
import type { LayerSpecification, StyleSpecification } from 'maplibre-gl';

export const ALLOWED_NAME_FIELDS = [
  'name',
  'name:en',
  'name:ar',
  'name:latin',
  'name:nonlatin',
  'label',
] as const;

const NUMERIC_LABEL = /address|housenumber|shield|pois|poi/;

export interface BasemapRequest {
  theme: 'dark' | 'light';
  language: 'en' | 'ar';
  extractUrl: string | null;
}

function flavorName(theme: 'dark' | 'light'): string {
  return theme === 'light' ? 'light' : 'dark';
}

function isNumericLabel(layer: LayerSpecification): boolean {
  return NUMERIC_LABEL.test(layer.id);
}

function readsForbiddenField(value: unknown): boolean {
  if (!Array.isArray(value)) return false;
  if (value[0] === 'get') {
    const field = value[1];
    if (typeof field !== 'string') return true;
    return !ALLOWED_NAME_FIELDS.includes(
      field as (typeof ALLOWED_NAME_FIELDS)[number],
    );
  }
  return value.some((item) => readsForbiddenField(item));
}

function flatten(
  layer: LayerSpecification,
  building: string,
): LayerSpecification {
  if (layer.type !== 'fill-extrusion') return layer;
  return {
    id: layer.id,
    type: 'fill',
    source: layer.source,
    'source-layer': layer['source-layer'],
    paint: { 'fill-color': building },
  };
}

function keep(
  layer: LayerSpecification,
  building: string,
): LayerSpecification | null {
  if (isNumericLabel(layer)) return null;
  const layout = layer.layout;
  if (
    layout &&
    'text-field' in layout &&
    readsForbiddenField(layout['text-field'])
  )
    return null;
  return flatten(layer, building);
}

export function plainStyle(theme: 'dark' | 'light'): StyleSpecification {
  const flavor: Flavor = namedFlavor(flavorName(theme));
  return {
    version: 8,
    sources: {},
    layers: [
      {
        id: 'sea',
        type: 'background',
        paint: { 'background-color': flavor.water },
      },
      {
        id: 'land',
        type: 'background',
        paint: { 'background-color': flavor.earth },
      },
    ],
  };
}

function localTiles(extractUrl: string): string {
  const scheme = 'pmtiles:';
  const mark = '/' + '/';
  return scheme + mark + extractUrl;
}

export const GLYPH_TEMPLATE = '/fonts/{fontstack}/{range}.pbf';

function glyphTemplate(): string {
  const origin = globalThis.location?.origin;
  if (typeof origin !== 'string' || origin.length === 0) {
    throw new Error('glyph template needs a page origin');
  }
  return origin + GLYPH_TEMPLATE;
}

export function extractStyle(request: BasemapRequest): StyleSpecification {
  if (request.extractUrl === null) return plainStyle(request.theme);
  const flavor = namedFlavor(flavorName(request.theme));
  const lang = request.language === 'ar' ? 'ar' : 'en';
  const built = layers('protomaps', flavor, { lang }).flatMap((layer) => {
    const next = keep(layer, flavor.buildings);
    return next ? [next] : [];
  });
  return {
    version: 8,
    glyphs: glyphTemplate(),
    sources: {
      protomaps: {
        type: 'vector',
        url: localTiles(request.extractUrl),
      },
    },
    layers: built,
  };
}
