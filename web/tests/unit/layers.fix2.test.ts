import { describe, expect, it } from 'vitest';
import { getResolution } from 'h3-js';

import {
  factId,
  makeBinding,
  makeFact,
  makeLineage,
  makeSource,
} from '../fixtures/facts';
import { layerRegistry } from '../fixtures/layer-registry';
import {
  CHAIN_ID,
  NIGHT_PARENT,
  SAMPLE_CREDITS,
  basePayload,
  category,
  plain,
} from '../fixtures/layers';
import { createRegistry } from '../../src/facts/registry';
import { acceptPayload } from '../../src/stage/layers/refuse';
import { overlayFor } from '../../src/stage/layers/overlay';
import { LAYER_ENTRIES } from '../../src/stage/layers/registry';

const ASYNC_ORIGINAL = Symbol.for('asyncPropOriginal');
const ASYNC_RESOLVED = Symbol.for('asyncPropResolved');

type CarriedLayer = {
  id: string;
  constructor: { layerName: string };
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

const CREDITS = SAMPLE_CREDITS;

function fdiPayload(features: Record<string, unknown>[]) {
  return basePayload({
    layers: [
      {
        key: 'fdi_projects',
        visible: true,
        source_chain_fact_id: CHAIN_ID,
        source_id: 'src_fdi',
        features: features as never,
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
    credits: CREDITS,
  });
}

describe('fix pass 2', () => {
  it('F1 excludes an absent-gazetteer project from overlay data', () => {
    const payload = fdiPayload([
      {
        feature_id: 'feat_fdi_aleph',
        metric_key: 'fdi_sector',
        provenance: 'public',
        subject: 'fdi_project',
        geometry_kind: 'point',
        place_key: 'gx_missing',
        position: [51.5, 25.3],
        fact_id: CHAIN_ID,
        year: '2024',
        words: {
          company: 'Sample Announcement House',
          sector: 'Sample sector',
        },
      },
    ]);
    const accepted = acceptPayload(payload);
    expect(accepted.ok).toBe(true);
    if (!accepted.ok) return;
    expect(accepted.draw.fdiListed).toEqual(['feat_fdi_aleph']);
    const layers = carriedLayers(
      overlayFor(
        payload,
        null,
        layerRegistry([
          { id: CHAIN_ID, metric: 'fdi_sector', table: 'fdi_projects' },
        ]),
      ),
    );
    const scatter = layers.find(
      (layer) => layer.constructor.layerName === 'ScatterplotLayer',
    );
    const data = (suppliedData(scatter!) ?? []) as {
      position?: readonly number[];
    }[];
    expect(data.some((row) => row.position?.[0] === 51.5)).toBe(false);
  });

  it('F2 draws rail and health centres as separate geometry sublayers', () => {
    const shared = {
      provenance: 'public' as const,
      subject: 'gis_feature' as const,
      fact_id: CHAIN_ID,
    };
    const healthId = factId(1);
    const payload = basePayload({
      layers: [
        {
          key: 'rail_plan',
          visible: true,
          source_chain_fact_id: CHAIN_ID,
          source_id: 'src_places',
          features: [
            {
              ...shared,
              feature_id: 'feat_line',
              metric_key: 'rail_feature',
              geometry_kind: 'line',
              path: [
                [51.5, 25.3],
                [51.6, 25.4],
              ],
            },
            {
              ...shared,
              feature_id: 'feat_station',
              metric_key: 'rail_feature',
              geometry_kind: 'point',
              status_key: 'planned',
              position: [51.55, 25.35],
            },
            {
              ...shared,
              feature_id: 'feat_zone',
              metric_key: 'rail_feature',
              geometry_kind: 'outline',
              ring: [
                [51.5, 25.3],
                [51.6, 25.3],
                [51.6, 25.4],
                [51.5, 25.3],
              ],
            },
          ],
        },
        {
          key: 'health_centres',
          visible: true,
          source_chain_fact_id: healthId,
          source_id: 'src_places',
          features: [
            {
              ...shared,
              fact_id: healthId,
              feature_id: 'feat_centre',
              metric_key: 'health_centre_name',
              geometry_kind: 'point',
              position: [51.4, 25.2],
            },
            {
              ...shared,
              fact_id: healthId,
              feature_id: 'feat_catchment',
              metric_key: 'health_centre_name',
              geometry_kind: 'outline',
              ring: [
                [51.4, 25.2],
                [51.5, 25.2],
                [51.5, 25.3],
                [51.4, 25.2],
              ],
            },
          ],
        },
      ],
    });
    const layers = carriedLayers(
      overlayFor(
        payload,
        null,
        layerRegistry([
          { id: CHAIN_ID, metric: 'rail_feature', table: 'pub_rail_plan' },
          {
            id: healthId,
            metric: 'health_centre_name',
            table: 'pub_health_centre',
          },
        ]),
      ),
    );
    const ids = layers.map((layer) => layer.id).sort();
    expect(ids).toContain('rail_plan:PathLayer');
    expect(ids).toContain('rail_plan:ScatterplotLayer');
    expect(ids).toContain('rail_plan:GeoJsonLayer');
    expect(ids).toContain('health_centres:ScatterplotLayer');
    expect(ids).toContain('health_centres:GeoJsonLayer');
    const outlines = layers.filter((layer) =>
      String(layer.id).endsWith('GeoJsonLayer'),
    );
    for (const outline of outlines) {
      expect(outline.props.filled).toBe(false);
      expect(outline.props.lineWidthMinPixels).toBe(1);
    }
    const banned = acceptPayload(
      basePayload({
        layers: [
          {
            ...basePayload().layers[0]!,
            features: [
              {
                ...basePayload().layers[0]!.features[0]!,
                geometry_kind: 'line',
                path: [
                  [51.5, 25.3],
                  [51.6, 25.4],
                ],
              },
            ],
          },
        ],
      }),
    );
    expect(banned.ok).toBe(false);
    if (!banned.ok) expect(banned.code).toBe('wrong_layer_type');
  });

  it('F3 keeps each parent class and refuses an unknown class or direction', () => {
    const child = '89536bc1ea3ffff';
    const payload = basePayload({
      layers: [
        {
          key: 'night_lights',
          visible: true,
          source_chain_fact_id: CHAIN_ID,
          source_id: 'src_places',
          features: [
            {
              feature_id: 'feat_low',
              metric_key: 'radiance_class',
              provenance: 'public',
              subject: 'statistic',
              geometry_kind: 'hex',
              cell: NIGHT_PARENT,
              resolution: 8,
              fact_id: factId(1),
              class_id: 'band_low',
            },
            {
              feature_id: 'feat_high',
              metric_key: 'radiance_class',
              provenance: 'public',
              subject: 'statistic',
              geometry_kind: 'hex',
              cell: child,
              resolution: 9,
              fact_id: factId(2),
              class_id: 'band_high',
            },
          ],
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
    const accepted = acceptPayload(payload);
    expect(accepted.ok).toBe(true);
    if (!accepted.ok) return;
    const hexes = accepted.draw.layers[0]?.hexes ?? [];
    const low = hexes.filter((hex) => hex.factId === factId(1));
    const high = hexes.filter((hex) => hex.factId === factId(2));
    expect(low).toHaveLength(7);
    expect(low.every((hex) => hex.classId === 'band_low')).toBe(true);
    expect(high.every((hex) => hex.classId === 'band_high')).toBe(true);
    expect(hexes.every((hex) => getResolution(hex.cell) === 9)).toBe(true);
    const layers = carriedLayers(
      overlayFor(
        payload,
        null,
        layerRegistry([
          { id: CHAIN_ID, metric: 'radiance_class', table: 'pub_night_lights' },
          {
            id: factId(1),
            metric: 'radiance_class',
            table: 'pub_night_lights',
          },
          {
            id: factId(2),
            metric: 'radiance_class',
            table: 'pub_night_lights',
          },
        ]),
      ),
    );
    const hexLayer = layers.find(
      (layer) => layer.constructor.layerName === 'H3HexagonLayer',
    );
    expect(typeof hexLayer?.props.getFillColor).toBe('function');
    const unknownClass = acceptPayload({
      ...payload,
      night: { ...payload.night!, class_id: 'not_a_class' },
    });
    expect(unknownClass.ok).toBe(false);
    if (!unknownClass.ok) expect(unknownClass.code).toBe('night_class_missing');
    const unknownDirection = acceptPayload({
      ...payload,
      night: { ...payload.night!, direction: 'sideways' },
    });
    expect(unknownDirection.ok).toBe(false);
    if (!unknownDirection.ok)
      expect(unknownDirection.code).toBe('night_direction_missing');
    const native = acceptPayload({
      ...payload,
      layers: [
        {
          ...payload.layers[0]!,
          features: [
            {
              ...payload.layers[0]!.features[1]!,
              cell: NIGHT_PARENT,
              resolution: 9,
            },
          ],
        },
      ],
    });
    expect(native.ok).toBe(false);
    if (!native.ok) expect(native.code).toBe('mixed_resolution');
  });

  it('F5 refuses a synthetic fact behind a public wrapper', () => {
    const registry = createRegistry({
      facts: [
        makeBinding({
          fact: makeFact({
            fact_id: CHAIN_ID,
            provenance: 'synthetic',
            input_classes: ['synthetic'],
          }),
          metricKey: 'place_listing',
        }),
      ],
      releases: [{ releaseId: makeFact().release_id }],
      artefacts: [],
      tables: [{ releaseId: makeFact().release_id, tableName: 'pub_place' }],
      lineages: [
        makeLineage({ tableName: 'pub_place', inputClasses: ['synthetic'] }),
      ],
      sources: [
        makeSource({ kind: 'synthetic_feed', inputClass: 'synthetic' }),
      ],
    });
    const result = acceptPayload(basePayload(), registry as never);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe('not_public');
    const mismatched = acceptPayload(
      basePayload(),
      layerRegistry([{ id: CHAIN_ID, metric: 'people', table: 'pub_place' }]),
    );
    expect(mismatched.ok).toBe(false);
    if (!mismatched.ok)
      expect(mismatched.code).toBe('measure_on_named_feature');
    const missing = basePayload();
    missing.layers[0]!.features[0]!.fact_id = 'f_not_in_the_registry_sample';
    const unresolved = acceptPayload(
      missing,
      layerRegistry([
        { id: CHAIN_ID, metric: 'place_listing', table: 'pub_place' },
      ]),
    );
    expect(unresolved.ok).toBe(false);
    if (!unresolved.ok) expect(unresolved.code).toBe('incomplete_source_chain');
    const undated = acceptPayload(
      basePayload(),
      layerRegistry([
        {
          id: CHAIN_ID,
          metric: 'place_listing',
          table: 'pub_place',
          retrievalDate: '',
        },
      ]),
    );
    expect(undated.ok).toBe(false);
    if (!undated.ok) expect(undated.code).toBe('incomplete_source_chain');
    const low = acceptPayload(
      basePayload(),
      layerRegistry([
        { id: CHAIN_ID, metric: 'place_listing', table: 'pub_place', value: 1 },
      ]),
    );
    const high = acceptPayload(
      basePayload(),
      layerRegistry([
        {
          id: CHAIN_ID,
          metric: 'place_listing',
          table: 'pub_place',
          value: 99,
        },
      ]),
    );
    expect(low.ok).toBe(true);
    expect(high.ok).toBe(true);
    const arabic = acceptPayload(
      basePayload({
        sources: [
          {
            ...basePayload().sources[0]!,
            publisher: [plain('Sample \u0661')],
          },
        ],
      }),
    );
    expect(arabic.ok).toBe(false);
    if (!arabic.ok) expect(arabic.code).toBe('numeral_in_plain_segment');
    const numberedChoice = basePayload();
    numberedChoice.filter_options = {
      sector: ['sample_\u0664'],
      source_country: [],
      period: [],
      stated_location: [],
    };
    const choice = acceptPayload(numberedChoice);
    expect(choice.ok).toBe(false);
    if (!choice.ok) expect(choice.code).toBe('numeral_in_plain_segment');
  });

  it('F8 refuses an unknown split source and an altered category', () => {
    const source = {
      ...basePayload().sources[0]!,
      year: '2024',
      categories: [category('group_b'), category('group_a')],
      geographyCode: 'sample_geo',
    };
    const chip = {
      provenance: 'public' as const,
      evidence_status: 'observed' as const,
      source_id: 'src_places',
      year: '2024',
      categories: [category('group_b'), category('group_a')],
      geography_code: 'sample_geo',
      source_geography: 'sample_geo',
    };
    const unknown = acceptPayload(
      basePayload({
        sources: [source as never],
        split_chip: { ...chip, source_id: 'src_missing' },
      }),
    );
    expect(unknown.ok).toBe(false);
    if (!unknown.ok) expect(unknown.code).toBe('split_incomplete');
    const altered = acceptPayload(
      basePayload({
        sources: [source as never],
        split_chip: {
          ...chip,
          categories: [category('group_b'), category('group_c')],
        },
      }),
    );
    expect(altered.ok).toBe(false);
    if (!altered.ok) expect(altered.code).toBe('split_incomplete');
    const kept = acceptPayload(
      basePayload({
        sources: [source as never],
        split_chip: chip,
      }),
    );
    expect(kept.ok).toBe(true);
    if (!kept.ok) return;
    expect(kept.draw.splitCategories).toEqual([
      [plain('group_b')],
      [plain('group_a')],
    ]);
    expect(kept.draw.layers.some((layer) => layer.key === 'split')).toBe(false);
  });

  it('F6 refuses a record bound to an unknown source', () => {
    const payload = basePayload();
    (payload.layers[0]!.features[0] as { source_id?: string }).source_id =
      'src_missing';
    const result = acceptPayload(payload);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe('missing_attribution');
  });

  it('F10 refuses each parcel label and a wage metric on its own', () => {
    for (const status of ['approved', 'available', 'vacant', 'for_sale']) {
      const result = acceptPayload(
        basePayload({
          layers: [
            {
              ...basePayload().layers[0]!,
              key: 'parcels',
              features: [
                {
                  feature_id: 'feat_parcel',
                  metric_key: 'plot_state',
                  provenance: 'public',
                  subject: 'gis_feature',
                  geometry_kind: 'outline',
                  status_key: status,
                  fact_id: CHAIN_ID,
                },
              ],
            },
          ],
        }),
      );
      expect(result.ok, status).toBe(false);
      if (!result.ok)
        expect(result.code, status).toBe('parcel_forbidden_label');
    }
    const wage = acceptPayload(
      basePayload({
        layers: [
          {
            ...basePayload().layers[0]!,
            features: [
              {
                ...basePayload().layers[0]!.features[0]!,
                metric_key: 'wage',
                identifier: 'sample-place',
              },
            ],
          },
        ],
      }),
    );
    expect(wage.ok).toBe(false);
    if (!wage.ok) expect(wage.code).toBe('wage_or_synthetic_id');
    expect(
      LAYER_ENTRIES.filter((entry) => !entry.implemented).map(
        (entry) => entry.key,
      ),
    ).toContain('firm_density');
  });

  it('refuses a feature word that holds a digit (lead plant of the feature-word guard)', () => {
    for (const sector of ['Sample sector 7', 'Sample sector \u0663']) {
      const result = acceptPayload(
        fdiPayload([
          {
            feature_id: 'feat_fdi_beth',
            metric_key: 'fdi_sector',
            provenance: 'public',
            subject: 'fdi_project',
            geometry_kind: 'point',
            place_key: 'gx_missing',
            position: [51.5, 25.3],
            fact_id: CHAIN_ID,
            year: '2024',
            words: { company: 'Sample Announcement House', sector },
          },
        ]),
      );
      expect(result.ok, sector).toBe(false);
      if (!result.ok)
        expect(result.code, sector).toBe('numeral_in_plain_segment');
    }
  });
});
