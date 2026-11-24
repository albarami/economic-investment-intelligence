import { describe, expect, it, vi } from 'vitest';
import type { LayerSpecification, StyleSpecification } from 'maplibre-gl';

import { ALLOWED_NAME_FIELDS, extractStyle } from '../../src/stage/basemap';
import { EXTRACT_URL } from '../../src/app/App';

const ORIGIN = 'http://map.test';
const EXTRACT = '/tiles/basemap.pmtiles';

function stubOrigin(): void {
  vi.stubGlobal('location', { origin: ORIGIN });
}

function* getFields(value: unknown): Generator<string> {
  if (!Array.isArray(value)) return;
  if (value[0] === 'get' && typeof value[1] === 'string') {
    yield value[1];
    return;
  }
  for (const item of value) yield* getFields(item);
}

function labelFields(layer: LayerSpecification): string[] {
  const layout = layer.layout as Record<string, unknown> | undefined;
  const text = layout?.['text-field'];
  return [...getFields(text)];
}

function assertCleanStyle(style: StyleSpecification): void {
  for (const layer of style.layers) {
    expect(layer.id).not.toMatch(/address|housenumber|shield|pois|poi/);
    for (const field of labelFields(layer)) {
      expect(
        (ALLOWED_NAME_FIELDS as readonly string[]).includes(field),
        `layer ${layer.id} reads ${field}`,
      ).toBe(true);
    }
  }
}

function assertLiveBasemap(style: StyleSpecification): void {
  expect(style.glyphs).toBe(`${ORIGIN}/fonts/{fontstack}/{range}.pbf`);
  expect(style.sources.protomaps).toMatchObject({
    type: 'vector',
    url: 'pmtiles:///tiles/basemap.pmtiles',
  });
  expect(style.layers.some((layer) => layer.id === 'places_country')).toBe(
    true,
  );
}

describe('extractStyle', () => {
  it('uses an absolute same-origin glyph template', () => {
    stubOrigin();
    const style = extractStyle({
      theme: 'dark',
      language: 'en',
      extractUrl: EXTRACT,
    });
    assertLiveBasemap(style);
  });

  it('keeps labels clean in both themes and languages', () => {
    stubOrigin();
    for (const theme of ['dark', 'light'] as const) {
      for (const language of ['en', 'ar'] as const) {
        const style = extractStyle({ theme, language, extractUrl: EXTRACT });
        assertCleanStyle(style);
        assertLiveBasemap(style);
      }
    }
  });

  it('refuses a planted forbidden label and a missing extract', () => {
    stubOrigin();
    const style = extractStyle({
      theme: 'dark',
      language: 'en',
      extractUrl: EXTRACT,
    });
    const planted: StyleSpecification = {
      ...style,
      layers: [
        ...style.layers,
        {
          id: 'pois',
          type: 'symbol',
          source: 'protomaps',
          'source-layer': 'pois',
          layout: { 'text-field': ['get', 'housenumber'] },
        } as LayerSpecification,
      ],
    };
    expect(() => assertCleanStyle(planted)).toThrow();
    expect(() =>
      assertLiveBasemap(
        extractStyle({ theme: 'dark', language: 'en', extractUrl: null }),
      ),
    ).toThrow();
  });
});

describe('App bootstrap', () => {
  it('wires the mounted same-origin extract path', () => {
    expect(EXTRACT_URL).toBe(EXTRACT);
    expect(EXTRACT_URL.startsWith('/tiles/')).toBe(true);
    expect(EXTRACT_URL.endsWith('.pmtiles')).toBe(true);
  });
});
