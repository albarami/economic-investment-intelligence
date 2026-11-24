import { describe, expect, it } from 'vitest';
import { cellToChildren, getResolution } from 'h3-js';

import { factId } from '../fixtures/facts';
import { layerRegistry } from '../fixtures/layer-registry';
import {
  CHAIN_ID,
  NIGHT_PARENT,
  SAMPLE_CREDITS,
  basePayload,
  layerSource,
} from '../fixtures/layers';
import { legendLineSamples } from '../../src/stage/layers/legend';
import {
  LAYER_ENTRIES,
  labelsDrawn,
  selectHero,
} from '../../src/stage/layers/registry';
import { acceptPayload, REFUSAL_CODES } from '../../src/stage/layers/refuse';
import {
  expandNightCells,
  guardHexResolution,
} from '../../src/stage/layers/night';
import { FDI_FILTERS } from '../../src/stage/layers/fdi';
import {
  overlayFor,
  pathRows,
  pointRows,
  polygonRows,
} from '../../src/stage/layers/overlay';

import { PLANTS } from '../fixtures/layer-plants';

describe('layer refusals', () => {
  it('plants every refusal code', () => {
    for (const code of REFUSAL_CODES) {
      const result = acceptPayload(PLANTS[code]);
      expect(result.ok, code).toBe(false);
      if (!result.ok) expect(result.code, code).toBe(code);
    }
  });
});

describe('registry', () => {
  it('holds every closed key and implements only the public writer set', () => {
    const keys = LAYER_ENTRIES.map((entry) => entry.key);
    expect(new Set(keys).size).toBe(keys.length);
    expect(keys).toContain('commercial_points');
    expect(keys).toContain('address_points');
    expect(keys).toContain('parcels');
    expect(keys).toContain('landmarks');
    expect(keys).not.toContain('official_boundaries');
    const built = LAYER_ENTRIES.filter((entry) => entry.implemented);
    expect(built.every((entry) => entry.className.includes('Public'))).toBe(
      true,
    );
    expect(
      LAYER_ENTRIES.find((entry) => entry.key === 'company_points')
        ?.implemented,
    ).toBe(true);
    expect(
      LAYER_ENTRIES.find((entry) => entry.key === 'firm_density')?.implemented,
    ).toBe(false);
    expect(
      LAYER_ENTRIES.find((entry) => entry.key === 'presence')?.implemented,
    ).toBe(false);
  });

  it('keeps one hero and hides labels under a fixture synthetic hero', () => {
    const first = selectHero(
      { visibleHero: null, fixtureHero: null },
      'night_lights',
    );
    expect(first.ok).toBe(true);
    if (!first.ok) return;
    const second = selectHero(first.state, 'land_prices');
    expect(second.ok).toBe(true);
    if (!second.ok) return;
    expect(second.state.visibleHero).toBe('land_prices');
    const hidden = labelsDrawn({
      visibleHero: null,
      fixtureHero: 'synthetic',
    });
    expect(hidden).toBe(false);
    expect(
      labelsDrawn({ visibleHero: 'night_lights', fixtureHero: null }),
    ).toBe(true);
  });
});

describe('night lights geometry', () => {
  it('draws a resolution-8 cell as seven children with the parent fact id', () => {
    const drawn = expandNightCells([
      { cell: NIGHT_PARENT, resolution: 8, factId: factId(1) },
    ]);
    expect(drawn.ok).toBe(true);
    if (!drawn.ok) return;
    expect(drawn.cells).toHaveLength(cellToChildren(NIGHT_PARENT, 9).length);
    expect(drawn.cells).toHaveLength(7);
    expect(drawn.cells.every((cell) => cell.factId === factId(1))).toBe(true);
    expect(drawn.cells.every((cell) => getResolution(cell.cell) === 9)).toBe(
      true,
    );
    expect(guardHexResolution([NIGHT_PARENT]).ok).toBe(false);
  });
});

describe('legend samples', () => {
  it('shows the withheld hatch and lock only, never an origin sample', () => {
    // Decision 0035 items 1 and 2: no legend sample is chosen by origin.
    const samples = legendLineSamples();
    expect(samples).toEqual([
      {
        stateKey: 'withheld',
        pattern: 'hatch-lock',
        colour: 'var(--eii-map-boundary)',
        treatment: 'sample',
      },
    ]);
  });
});

describe('accepted layers', () => {
  it('keeps a project with no gazetteer point in the list and off the map', () => {
    const result = acceptPayload(
      basePayload({
        layers: [
          {
            ...basePayload().layers[0]!,
            key: 'fdi_projects',
            features: [
              {
                feature_id: 'feat_fdi_aleph',
                metric_key: 'fdi_sector',
                provenance: 'public',
                subject: 'fdi_project',
                geometry_kind: 'point',
                place_key: 'gx_missing',
                fact_id: CHAIN_ID,
                year: '2024',
                words: { company: 'Sample Announcement House' },
              },
              {
                feature_id: 'feat_fdi_beth',
                metric_key: 'fdi_sector',
                provenance: 'public',
                subject: 'fdi_project',
                geometry_kind: 'point',
                place_key: 'gx_sample_aleph',
                fact_id: CHAIN_ID,
                year: '2024',
              },
            ],
          },
        ],
        credits: SAMPLE_CREDITS,
      }),
    );
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.draw.fdiListed).toEqual(['feat_fdi_aleph', 'feat_fdi_beth']);
    expect(result.draw.fdiMarks).toEqual(['feat_fdi_beth']);
  });

  it('gives every implemented layer a source-chain fact id', () => {
    const implemented = LAYER_ENTRIES.filter((entry) => entry.implemented);
    for (const entry of implemented) {
      const feature = {
        feature_id: `feat_${entry.key}`,
        metric_key: entry.metricKeys[0] ?? 'place_listing',
        provenance: 'public' as const,
        subject: 'geometry' as const,
        geometry_kind:
          entry.key === 'night_lights'
            ? ('hex' as const)
            : entry.key === 'zoning' || entry.key === 'parcels'
              ? ('outline' as const)
              : entry.key === 'rail_plan'
                ? ('line' as const)
                : entry.key === 'zone_electricity_growth' ||
                    entry.key === 'land_prices' ||
                    entry.key === 'property_prices'
                  ? ('fill' as const)
                  : ('point' as const),
        fact_id: CHAIN_ID,
        year: '2024',
        cell: entry.key === 'night_lights' ? NIGHT_PARENT : undefined,
        resolution: entry.key === 'night_lights' ? (8 as const) : undefined,
        class_id: 'band_low',
        caveat_keys: entry.key === 'fdi_projects' ? ['fdi_estimates'] : [],
        place_key: entry.key === 'fdi_projects' ? 'gx_sample_aleph' : undefined,
      };
      // A register company's point carries no class, year or caveat (S3-T12).
      const drawnFeature =
        entry.key === 'company_points'
          ? {
              feature_id: feature.feature_id,
              metric_key: feature.metric_key,
              provenance: feature.provenance,
              subject: 'business' as const,
              geometry_kind: 'point' as const,
              fact_id: feature.fact_id,
            }
          : feature;
      const result = acceptPayload(
        basePayload({
          layers: [
            {
              key: entry.key,
              visible: true,
              source_chain_fact_id: CHAIN_ID,
              source_id: 'src_places',
              features: [drawnFeature],
            },
          ],
          night:
            entry.key === 'night_lights'
              ? {
                  month: '2024-03',
                  direction: 'higher',
                  class_id: 'band_low',
                  unit: 'radiance_nw_cm2_sr',
                  caveat_key: 'night_lights_not_activity',
                }
              : undefined,
          credits: entry.key === 'fdi_projects' ? SAMPLE_CREDITS : undefined,
        }),
        // A register company's point binds only through the fact registry.
        entry.key === 'company_points'
          ? layerRegistry([
              {
                id: CHAIN_ID,
                metric: entry.metricKeys[0]!,
                table: entry.table,
              },
            ])
          : undefined,
      );
      expect(result.ok, entry.key).toBe(true);
      if (!result.ok) return;
      expect(result.draw.layers[0]?.sourceChainFactId).toBe(CHAIN_ID);
      expect(result.draw.layers[0]?.retrievalDate).toBe('2024-03-14');
      if (entry.key === 'night_lights') {
        expect(result.draw.layers[0]?.hexes).toHaveLength(7);
        expect(
          result.draw.layers[0]?.hexes.every((hex) => hex.factId === CHAIN_ID),
        ).toBe(true);
      }
    }
  });
});

describe('payload fences', () => {
  it('keeps confidence and fetch out of the layer modules', () => {
    const payload = layerSource('payload.ts');
    expect(payload.includes('confidence')).toBe(false);
    for (const name of [
      'payload.ts',
      'refuse.ts',
      'overlay.ts',
      'PublicLayers.tsx',
      'FdiPanel.tsx',
    ]) {
      expect(layerSource(name).includes('fetch(')).toBe(false);
    }
  });

  it('accepts an apportioned district figure when the inferred inputs are present', () => {
    const result = acceptPayload(
      basePayload({
        layers: [
          {
            ...basePayload().layers[0]!,
            key: 'property_prices',
            features: [
              {
                ...basePayload().layers[0]!.features[0]!,
                metric_key: 'district_sale',
                subject: 'statistic',
                geometry_kind: 'fill',
                apportioned_from: 'src_grid',
                evidence_status: 'inferred',
                method_id: 'method_apportion_v1',
                geography_code: 'gx_sample_aleph',
              },
            ],
          },
        ],
      }),
    );
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.draw.layers[0]?.features[0]?.evidence_status).toBe(
      'inferred',
    );
  });

  it('draws only geometry the payload supplies', () => {
    const bare = basePayload().layers[0]!.features;
    expect(pointRows(bare)).toEqual([]);
    expect(pathRows(bare)).toEqual([]);
    expect(polygonRows(bare)).toEqual([]);
    const placed = [
      {
        ...bare[0]!,
        position: [51.5, 25.3] as const,
        path: [
          [51.5, 25.3],
          [51.6, 25.4],
        ] as const,
        ring: [
          [51.5, 25.3],
          [51.6, 25.3],
          [51.6, 25.4],
          [51.5, 25.3],
        ] as const,
      },
    ];
    expect(pointRows(placed)).toEqual([
      {
        position: [51.5, 25.3],
        featureId: placed[0]!.feature_id,
        classId: '',
      },
    ]);
    expect(pathRows(placed)[0]?.path).toHaveLength(2);
    expect(polygonRows(placed)[0]?.geometry.coordinates[0]).toHaveLength(4);
  });

  it('names exactly four FDI filters', () => {
    expect(FDI_FILTERS).toEqual([
      'sector',
      'source_country',
      'period',
      'stated_location',
    ]);
  });
});

const ASYNC_ORIGINAL = Symbol.for('asyncPropOriginal');
const ASYNC_RESOLVED = Symbol.for('asyncPropResolved');

type CarriedLayer = {
  constructor: { layerName: string };
  props: {
    loadOptions: {
      worker?: boolean;
      CDN?: unknown;
      core?: { CDN?: unknown; worker?: boolean };
    } | null;
  };
};

function carriedLayers(overlay: object): CarriedLayer[] {
  const held = overlay as { _props: { layers: CarriedLayer[] } };
  return held._props.layers;
}

function suppliedData(layer: CarriedLayer): unknown {
  const props = layer.props as unknown as Record<symbol, { data?: unknown }>;
  const original = props[ASYNC_ORIGINAL];
  if (original && Object.prototype.hasOwnProperty.call(original, 'data')) {
    return original.data;
  }
  return props[ASYNC_RESOLVED]?.data;
}

function rowsPayload() {
  const sourceId = 'src_places';
  const request = (
    key: string,
    fact: string,
    feature: ReturnType<
      typeof basePayload
    >['layers'][number]['features'][number],
  ) => ({
    key,
    visible: true,
    source_chain_fact_id: fact,
    source_id: sourceId,
    features: [feature],
  });
  const shared = {
    provenance: 'public' as const,
    year: '2024',
  };
  return basePayload({
    layers: [
      request('public_places', factId(0), {
        ...shared,
        fact_id: factId(0),
        feature_id: 'feat_place_aleph',
        metric_key: 'place_listing',
        subject: 'place',
        geometry_kind: 'point',
        position: [51.5, 25.3],
      }),
      request('rail_plan', factId(1), {
        ...shared,
        fact_id: factId(1),
        feature_id: 'feat_rail_aleph',
        metric_key: 'rail_feature',
        subject: 'geometry',
        geometry_kind: 'line',
        path: [
          [51.5, 25.3],
          [51.6, 25.4],
        ],
      }),
      request('zoning', factId(2), {
        ...shared,
        fact_id: factId(2),
        feature_id: 'feat_zone_aleph',
        metric_key: 'permitted_use',
        subject: 'geometry',
        geometry_kind: 'outline',
        ring: [
          [51.5, 25.3],
          [51.6, 25.3],
          [51.6, 25.4],
          [51.5, 25.3],
        ],
      }),
      request('night_lights', factId(3), {
        ...shared,
        fact_id: factId(3),
        feature_id: 'feat_night_aleph',
        metric_key: 'radiance_class',
        subject: 'geometry',
        geometry_kind: 'hex',
        cell: NIGHT_PARENT,
        resolution: 8,
        class_id: 'band_low',
      }),
    ],
    night: {
      month: '2024-03',
      direction: 'higher',
      class_id: 'band_low',
      unit: 'radiance_nw_cm2_sr',
      caveat_key: 'night_lights_not_activity',
    },
  });
}

function rowsRegistry() {
  return layerRegistry([
    { id: factId(0), metric: 'place_listing', table: 'pub_place' },
    { id: factId(1), metric: 'rail_feature', table: 'pub_rail_plan' },
    { id: factId(2), metric: 'permitted_use', table: 'pub_zoning' },
    { id: factId(3), metric: 'radiance_class', table: 'pub_night_lights' },
  ]);
}

describe('overlay load path', () => {
  it('overlayFor sets worker false and sets no CDN', () => {
    const layers = carriedLayers(
      overlayFor(rowsPayload(), null, rowsRegistry()),
    );
    expect(layers.map((layer) => layer.constructor.layerName).sort()).toEqual([
      'GeoJsonLayer',
      'H3HexagonLayer',
      'PathLayer',
      'ScatterplotLayer',
    ]);
    for (const layer of layers) {
      expect(layer.props.loadOptions).toEqual({ worker: false });
      expect(layer.props.loadOptions).not.toHaveProperty('CDN');
      expect(layer.props.loadOptions?.core).toBeUndefined();
    }
  });

  it('overlayFor gives every layer in-memory rows', () => {
    const layers = carriedLayers(
      overlayFor(rowsPayload(), null, rowsRegistry()),
    );
    expect(layers.length).toBeGreaterThan(0);
    for (const layer of layers) {
      const data = suppliedData(layer);
      expect(typeof data).not.toBe('string');
      expect(data !== null && typeof data === 'object').toBe(true);
    }
  });
});
