import { describe, expect, it } from 'vitest';

import { layerRegistry } from '../fixtures/layer-registry';
import {
  CHAIN_ID,
  NIGHT_PARENT,
  SAMPLE_CREDITS,
  basePayload,
  category,
  plain,
} from '../fixtures/layers';
import { acceptPayload } from '../../src/stage/layers/refuse';
import { bindSelection } from '../../src/stage/layers/selection';
import { fillColor } from '../../src/stage/layers/ramp';
import { overlayFor } from '../../src/stage/layers/overlay';
import type {
  InvestmentCredits,
  LayerPayload,
} from '../../src/stage/layers/payload';

const ASYNC_ORIGINAL = Symbol.for('asyncPropOriginal');
const ASYNC_RESOLVED = Symbol.for('asyncPropResolved');

type CarriedLayer = {
  id: string;
  props: Record<string, unknown>;
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

const RING = [
  [51.5, 25.3],
  [51.6, 25.3],
  [51.6, 25.4],
  [51.5, 25.3],
] as const;

const BOUNDARY = [0x66, 0x75, 0x8a, 255];

const RAMP_BYTES = {
  band_low: [0x2f, 0x4a, 0x5e, 255],
  band_mid_low: [0x3f, 0x6f, 0x86, 255],
  band_mid: [0x5e, 0x97, 0xa6, 255],
  band_mid_high: [0x9c, 0xc4, 0xbb, 255],
  band_high: [0xeb, 0xe3, 0xb0, 255],
} as const;

function outlineTable(key: 'rail_plan' | 'health_centres' | 'parcels'): string {
  if (key === 'rail_plan') return 'pub_rail_plan';
  if (key === 'health_centres') return 'pub_health_centre';
  return 'pub_parcel';
}

function outlinePayload(
  key: 'rail_plan' | 'health_centres' | 'parcels',
): LayerPayload {
  const metric =
    key === 'rail_plan'
      ? 'rail_feature'
      : key === 'health_centres'
        ? 'health_centre_name'
        : 'parcel_area';
  return basePayload({
    layers: [
      {
        key,
        visible: true,
        source_chain_fact_id: CHAIN_ID,
        source_id: 'src_places',
        features: [
          {
            feature_id: 'feat_poly',
            metric_key: metric,
            provenance: 'public',
            subject: 'gis_feature',
            geometry_kind: 'fill',
            ring: RING,
            fact_id: CHAIN_ID,
            words: { name: 'Sample outline' },
          },
        ],
      },
    ],
  });
}

function nightPayload(classId: string | undefined): LayerPayload {
  const feature: LayerPayload['layers'][number]['features'][number] = {
    feature_id: 'feat_night',
    metric_key: 'radiance_class',
    provenance: 'public',
    subject: 'statistic',
    geometry_kind: 'hex',
    cell: '89536bc1ea3ffff',
    resolution: 9,
    fact_id: CHAIN_ID,
  };
  if (classId !== undefined) feature.class_id = classId;
  return basePayload({
    layers: [
      {
        key: 'night_lights',
        visible: true,
        source_chain_fact_id: CHAIN_ID,
        source_id: 'src_places',
        features: [feature],
      },
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

function guidePayload(classId: string | undefined): LayerPayload {
  const feature: LayerPayload['layers'][number]['features'][number] = {
    feature_id: 'feat_guide',
    metric_key: 'guide_price_class',
    provenance: 'public',
    subject: 'statistic',
    geometry_kind: 'fill',
    ring: RING,
    fact_id: CHAIN_ID,
  };
  if (classId !== undefined) feature.class_id = classId;
  return basePayload({
    layers: [
      {
        key: 'land_prices',
        visible: true,
        source_chain_fact_id: CHAIN_ID,
        source_id: 'src_places',
        features: [feature],
      },
    ],
  });
}

function fdiFeature(
  extra: Record<string, unknown> = {},
): LayerPayload['layers'][number]['features'][number] {
  return {
    feature_id: 'feat_fdi_aleph',
    metric_key: 'fdi_sector',
    provenance: 'public',
    subject: 'fdi_project',
    geometry_kind: 'point',
    place_key: 'gx_sample_aleph',
    fact_id: CHAIN_ID,
    year: '2024',
    words: { company: 'Sample Announcement House', sector: 'Sample sector' },
    ...extra,
  } as LayerPayload['layers'][number]['features'][number];
}

function fdiPayload(
  features: LayerPayload['layers'][number]['features'],
  credits: InvestmentCredits | undefined = SAMPLE_CREDITS,
  extra: Partial<LayerPayload> = {},
): LayerPayload {
  return basePayload({
    layers: [
      {
        key: 'fdi_projects',
        visible: true,
        source_chain_fact_id: CHAIN_ID,
        source_id: 'src_fdi',
        features,
      },
    ],
    sources: [
      {
        sourceId: 'src_fdi',
        attribution: [plain('Sample investment credit')],
        retrievalDate: '2024-03-14',
        publisher: [plain('Sample Agency')],
        datasetOrPage: 'Sample dashboard',
        licenceOrTerms: 'Terms recorded for this sample',
      },
    ],
    credits,
    ...extra,
  });
}

function splitBase(
  chip: Partial<NonNullable<LayerPayload['split_chip']>> = {},
  source: Record<string, unknown> = {},
): LayerPayload {
  const sourceCategories = [category('group_b'), category('group_a')];
  return basePayload({
    sources: [
      {
        ...basePayload().sources[0]!,
        year: '2024',
        categories: sourceCategories,
        geographyCode: 'sample_geo',
        ...source,
      },
    ],
    split_chip: {
      provenance: 'public',
      evidence_status: 'observed',
      source_id: 'src_places',
      year: '2024',
      categories: sourceCategories,
      geography_code: 'sample_geo',
      source_geography: 'sample_geo',
      ...chip,
    },
  });
}

describe('fix pass 3', () => {
  it('F1 draws rail, health and parcel fills as boundary outlines', () => {
    for (const key of ['rail_plan', 'health_centres', 'parcels'] as const) {
      const payload = outlinePayload(key);
      const metric =
        key === 'rail_plan'
          ? 'rail_feature'
          : key === 'health_centres'
            ? 'health_centre_name'
            : 'parcel_area';
      const registry = layerRegistry([
        { id: CHAIN_ID, metric, table: outlineTable(key) },
      ]);
      const accepted = acceptPayload(payload);
      expect(accepted.ok, key).toBe(true);
      const layers = carriedLayers(overlayFor(payload, null, registry));
      const geo = layers.find((layer) => layer.id.endsWith('GeoJsonLayer'));
      expect(geo, key).toBeTruthy();
      expect(geo?.props.filled, key).toBe(false);
      const paint = geo?.props.getLineColor as (() => number[]) | undefined;
      expect(typeof paint, key).toBe('function');
      expect(paint?.(), key).toEqual(BOUNDARY);
      expect(geo?.props.getLineWidth, key).toBe(1);
      expect(geo?.props.lineWidthUnits, key).toBe('pixels');
      expect(geo?.props.lineWidthMinPixels, key).toBe(1);
      expect(geo?.props.outlineToken, key).toBeUndefined();
    }
  });

  it('F2 refuses a ramp feature whose class is missing', () => {
    for (const payload of [nightPayload(undefined), guidePayload(undefined)]) {
      const result = acceptPayload(payload);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.code).toBe('night_class_missing');
    }
  });

  it('F2 refuses a ramp feature whose class is empty', () => {
    for (const payload of [nightPayload(''), guidePayload('')]) {
      const result = acceptPayload(payload);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.code).toBe('night_class_missing');
    }
  });

  it('F2 refuses a ramp feature whose class is unknown', () => {
    for (const payload of [
      nightPayload('not_a_class'),
      guidePayload('not_a_class'),
    ]) {
      const result = acceptPayload(payload);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.code).toBe('night_class_missing');
    }
  });

  it('F2 paints each closed class through the fill accessor', () => {
    const payload = basePayload({
      layers: [
        {
          key: 'night_lights',
          visible: true,
          source_chain_fact_id: CHAIN_ID,
          source_id: 'src_places',
          features: [
            {
              feature_id: 'feat_night',
              metric_key: 'radiance_class',
              provenance: 'public',
              subject: 'statistic',
              geometry_kind: 'hex',
              cell: NIGHT_PARENT,
              resolution: 8,
              fact_id: CHAIN_ID,
              class_id: 'band_mid',
            },
          ],
        },
      ],
      night: {
        month: '2024-03',
        direction: 'higher',
        class_id: 'band_mid',
        unit: 'radiance_nw_cm2_sr',
        caveat_key: 'night_lights_not_activity',
      },
    });
    const layers = carriedLayers(
      overlayFor(
        payload,
        null,
        layerRegistry([
          { id: CHAIN_ID, metric: 'radiance_class', table: 'pub_night_lights' },
        ]),
      ),
    );
    const hex = layers.find((layer) => layer.id.endsWith('H3HexagonLayer'));
    const paint = hex?.props.getFillColor as
      ((row: { classId: string }) => number[]) | undefined;
    expect(typeof paint).toBe('function');
    for (const [classId, bytes] of Object.entries(RAMP_BYTES)) {
      expect(paint?.({ classId }), classId).toEqual(bytes);
      expect(fillColor(classId), classId).toEqual(bytes);
    }
  });

  it('F3 keeps the parent feature id on every expanded hex row', () => {
    const payload = nightPayload('band_low');
    payload.layers[0]!.features[0]!.cell = NIGHT_PARENT;
    payload.layers[0]!.features[0]!.resolution = 8;
    const layers = carriedLayers(
      overlayFor(
        payload,
        null,
        layerRegistry([
          { id: CHAIN_ID, metric: 'radiance_class', table: 'pub_night_lights' },
        ]),
      ),
    );
    const hex = layers.find((layer) => layer.id.endsWith('H3HexagonLayer'));
    const rows = (suppliedData(hex!) ?? []) as { featureId?: string }[];
    expect(rows).toHaveLength(7);
    expect(rows.every((row) => row.featureId === 'feat_night')).toBe(true);
    const picked: string[] = [];
    bindSelection((id) => {
      picked.push(id);
    });
    const click = hex?.props.onClick as
      ((info: { object?: { featureId?: string } }) => void) | undefined;
    click?.({ object: rows[0] });
    bindSelection(null);
    expect(picked).toEqual(['feat_night']);
  });

  it('F4 draws no geometry when the registry is absent', () => {
    const layers = carriedLayers(overlayFor(basePayload(), null));
    expect(layers).toEqual([]);
  });

  it('F4 draws no geometry when the fact table does not match the layer', () => {
    const payload = basePayload();
    const registry = layerRegistry([
      { id: CHAIN_ID, metric: 'place_listing', table: 'pub_other' },
    ]);
    const accepted = acceptPayload(payload, registry);
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('measure_on_named_feature');
    const layers = carriedLayers(overlayFor(payload, null, registry));
    expect(layers).toEqual([]);
  });

  it('F5 refuses a legend count that has no year', () => {
    const blank = acceptPayload(
      fdiPayload([fdiFeature()], SAMPLE_CREDITS, {
        count_facts: [{ fact_id: CHAIN_ID, year: '' }],
      }),
    );
    expect(blank.ok).toBe(false);
    if (!blank.ok) expect(blank.code).toBe('fdi_year_missing');
    const legacy = acceptPayload(
      fdiPayload([fdiFeature()], SAMPLE_CREDITS, {
        count_fact_ids: [CHAIN_ID],
      }),
    );
    expect(legacy.ok).toBe(false);
    if (!legacy.ok) expect(legacy.code).toBe('fdi_year_missing');
  });

  it('F5 refuses an estimate slot that has no announced-estimate label', () => {
    for (const slot of ['capex_fact_id', 'jobs_fact_id'] as const) {
      const result = acceptPayload(
        fdiPayload([
          fdiFeature({
            [slot]: CHAIN_ID,
            caveat_keys: [],
          }),
        ]),
      );
      expect(result.ok, slot).toBe(false);
      if (!result.ok)
        expect(result.code, slot).toBe('announced_estimate_unlabelled');
    }
    const kept = acceptPayload(
      fdiPayload([
        fdiFeature({
          capex_fact_id: CHAIN_ID,
          jobs_fact_id: CHAIN_ID,
          caveat_keys: ['fdi_estimates'],
        }),
      ]),
    );
    expect(kept.ok).toBe(true);
  });

  it('F5 keeps the feature-word guard and accepts a typed announced date', () => {
    const dated = acceptPayload(
      fdiPayload([
        fdiFeature({
          words: {
            company: 'Sample Announcement House',
            sector: 'Sample sector',
            announced: '2024-03-14',
          },
        }),
      ]),
    );
    expect(dated.ok).toBe(false);
    if (!dated.ok) expect(dated.code).toBe('numeral_in_plain_segment');
    const typed = acceptPayload(
      fdiPayload([
        fdiFeature({
          announced: {
            referenceKind: 'calendar_date',
            value: '2024-03-14',
            recordId: 'announced-date',
          },
        }),
      ]),
    );
    expect(typed.ok).toBe(true);
  });

  it('F8 refuses each missing investment credit field on its own', () => {
    const ready = acceptPayload(fdiPayload([fdiFeature()]));
    expect(ready.ok).toBe(true);
    const cases: Partial<InvestmentCredits>[] = [
      { publisher: [] },
      { gatherer: [plain('   ')] },
      { read_on: ' ' },
      { dashboard_url: '' },
    ];
    for (const credits of cases) {
      const result = acceptPayload(
        fdiPayload([fdiFeature()], { ...SAMPLE_CREDITS, ...credits }),
      );
      expect(result.ok, JSON.stringify(credits)).toBe(false);
      if (!result.ok) expect(result.code).toBe('missing_attribution');
    }
  });

  it('F6 refuses a split whose source geography differs', () => {
    const result = acceptPayload(splitBase({}, { geographyCode: 'other_geo' }));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe('split_incomplete');
  });

  it('F6 refuses a split whose source year differs', () => {
    const result = acceptPayload(splitBase({ year: '2023' }));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe('split_incomplete');
  });

  it('F6 refuses a split whose category list is a different length', () => {
    const result = acceptPayload(
      splitBase({
        categories: [
          category('group_b'),
          category('group_a'),
          category('group_c'),
        ],
      }),
    );
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe('split_incomplete');
  });

  it('F6 refuses each other split condition on its own', () => {
    const cases: Partial<NonNullable<LayerPayload['split_chip']>>[] = [
      { provenance: 'synthetic' },
      { evidence_status: 'inferred' },
      { source_id: '' },
      { year: '' },
      { categories: [] },
    ];
    for (const chip of cases) {
      const result = acceptPayload(splitBase(chip));
      expect(result.ok, JSON.stringify(chip)).toBe(false);
      if (!result.ok) {
        const code =
          chip.provenance === 'synthetic' || chip.evidence_status === 'inferred'
            ? 'split_incomplete'
            : chip.source_id === '' ||
                chip.year === '' ||
                chip.categories?.length === 0
              ? 'split_incomplete'
              : 'split_incomplete';
        expect(result.code, JSON.stringify(chip)).toBe(code);
      }
    }
  });
});
