import { describe, expect, it, vi } from 'vitest';

import type { FactRegistry } from '../../src/facts/registry';
import { fcSectionProblem } from '../../src/stage/layers/checks';
import { overlayFor } from '../../src/stage/layers/overlay';
import {
  DISTRICT_COUNT_CLASS,
  fcFeatureClass,
  fillColor,
  pointRadiusPx,
  rampToken,
} from '../../src/stage/layers/ramp';
import { LAYER_ENTRIES, layerEntry } from '../../src/stage/layers/registry';
import { acceptPayload, featureProblem } from '../../src/stage/layers/refuse';
import {
  FC_ALEPH,
  FC_BREAKS,
  FC_DISTRICT,
  FC_GIMEL,
  fcFeature,
  fcPayload,
  fcRegistry,
} from '../fixtures/fc-firms';
import { factId } from '../fixtures/facts';
import { layerRegistry } from '../fixtures/layer-registry';
import { CHAIN_ID, SAMPLE_CREDITS, basePayload } from '../fixtures/layers';

function firmsRows(extra?: {
  id: string;
  metric: string;
  table: string;
  provenance?: 'public' | 'synthetic';
  unit?: string;
}) {
  return layerRegistry([
    {
      id: FC_ALEPH,
      metric: 'firms_per_tower',
      table: 'pub_register_company',
      value: 4,
      geography: { kind: 'public', public_code: 'place:INV-TOWER-ALEPH' },
    },
    {
      id: FC_GIMEL,
      metric: 'firms_per_tower',
      table: 'pub_register_company',
      value: 1,
      geography: { kind: 'public', public_code: 'place:INV-TOWER-GIMEL' },
    },
    {
      id: FC_DISTRICT,
      metric: 'firms_per_tower',
      table: 'pub_register_company',
      value: 1,
      geography: { kind: 'public', public_code: 'district:INV-NORTH' },
    },
    ...FC_BREAKS.map((id, index) => ({
      id,
      metric: 'firms_per_tower',
      table: 'pub_register_company',
      value: index + 1,
    })),
    ...(extra ? [{ ...extra, value: 3 }] : []),
  ]);
}

interface CarriedLayer {
  constructor: { layerName: string };
  props: {
    radiusUnits?: string;
    getRadius?: (row: { classId: string }) => number;
    getFillColor?: (row: { classId: string }) => number[];
    data?: unknown[];
  };
}

/** Malformed section at the validator. The object is never the closed section type. */
function uncheckedFcSection(overrides: Record<string, unknown>): unknown {
  return {
    direction: 'higher',
    companies: [],
    coverage_note_keys: ['zone_without_district'],
    breaks: [],
    ...overrides,
  };
}

function validReference(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    kind: 'reference',
    referenceKind: 'calendar_year',
    value: '2024',
    recordId: 'rec-sample-year',
    ...overrides,
  };
}

function validField(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    key: 'trade_name',
    text: 'Invented House Aleph',
    ...overrides,
  };
}

function validCompany(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    feature_id: 'feat-invented-tower-aleph',
    row_id: 'row-aleph-one',
    fields: [validField()],
    ...overrides,
  };
}

function sectionWithCompany(company: Record<string, unknown>): unknown {
  return uncheckedFcSection({ companies: [company] });
}

/** The valid helper section stored on an array, so only `isRecord` fails. */
function arraySection(): unknown {
  const valid = uncheckedFcSection({});
  if (valid === null || typeof valid !== 'object' || Array.isArray(valid)) {
    throw new Error('helper did not return the fixture section');
  }
  return Object.assign([], valid);
}

/**
 * A ready public count on the firms table for any id.
 * Reaching resolve would accept the band; the string check must refuse first.
 */
function registryReadyForAnyId(): FactRegistry {
  return {
    resolve: () => ({
      status: 'ready',
      binding: {
        metricKey: 'firms_per_tower',
        presentation: 'ordinary',
        fact: {
          fact_id: 'not-read',
          value: 1,
          unit: 'count',
          period: '2024',
          geography: { kind: 'public' },
          provenance: 'public',
          input_classes: ['public'],
          evidence_status: 'observed',
          reliability: 'standard',
          coverage_keys: [],
          caveat_keys: [],
          label_en: 'Sample count',
          label_ar: 'Sample count',
          lineage_ref: 'lin-sample',
          release_id: 'rel-sample',
        },
      },
      lineage: {
        lineageId: 'lin-sample',
        releaseId: 'rel-sample',
        tableName: 'pub_register_company',
        method: 'sample',
        methodVersion: 'v0',
        sourceIds: [],
        inputClasses: ['public'],
      },
      sources: [],
      table: { releaseId: 'rel-sample', tableName: 'pub_register_company' },
      display: 'value',
    }),
    directionReferencers: () => [],
  };
}

function scatterLayers(
  payload: ReturnType<typeof basePayload>,
  metric: string,
  table: string,
) {
  const overlay = overlayFor(
    payload,
    null,
    layerRegistry([{ id: CHAIN_ID, metric, table }]),
  );
  const held = overlay as { _props: { layers: CarriedLayer[] } };
  return held._props.layers.filter(
    (layer) => layer.constructor.layerName === 'ScatterplotLayer',
  );
}

describe('firms per tower payload', () => {
  it('test_the_layer_types_are_the_pinned_ones', () => {
    const entry = layerEntry('fc_firms_per_tower');
    expect(entry?.implemented).toBe(true);
    expect(entry?.layerTypes).toEqual(['ScatterplotLayer', 'GeoJsonLayer']);
    expect(entry?.metricKeys).toEqual(['firms_per_tower']);
  });

  it('test_a_feature_with_no_closed_class_key_is_refused', () => {
    const payload = fcPayload();
    const feature = fcFeature({ class_id: undefined });
    payload.layers[0]?.features.splice(
      0,
      payload.layers[0].features.length,
      feature,
    );
    const accepted = acceptPayload(payload, fcRegistry());
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('night_class_missing');
  });

  it('test_a_district_feature_without_metric_or_fact_is_refused', () => {
    const payload = fcPayload();
    const entry = layerEntry('fc_firms_per_tower');
    const request = payload.layers[0];
    if (!entry || !request) throw new Error('missing entry');
    const bare = fcFeature({
      feature_id: 'feat-district-inv-north',
      geometry_kind: 'fill',
      subject: 'statistic',
      geography_code: 'district:INV-NORTH',
      metric_key: 'firms_per_tower',
      fact_id: undefined,
      position: undefined,
      class_id: 'band_low',
    });
    expect(featureProblem(entry, request, bare, payload)).toBe(
      'measure_on_named_feature',
    );
  });

  it('test_a_district_only_count_is_accepted_and_draws_no_point', () => {
    const payload = fcPayload();
    const layer = payload.layers[0];
    const district = layer?.features.find(
      (feature) => feature.geometry_kind === 'fill',
    );
    if (!layer || !district || !payload.fc_firms) throw new Error('missing');
    district.class_id = DISTRICT_COUNT_CLASS;
    expect(fcFeatureClass(DISTRICT_COUNT_CLASS)).toBe(true);
    layer.features = [district];
    payload.fc_firms = {
      ...payload.fc_firms,
      breaks: [],
      companies: [],
      coverage_note_keys: [],
    };
    const accepted = acceptPayload(payload, fcRegistry());
    expect(accepted.ok).toBe(true);
    if (accepted.ok) {
      const features = accepted.draw.layers[0]?.features ?? [];
      expect(features).toHaveLength(1);
      expect(features[0]?.geometry_kind).toBe('fill');
      expect(
        features.every((feature) => feature.geometry_kind !== 'point'),
      ).toBe(true);
    }
  });

  it('test_an_unknown_legend_class_is_refused', () => {
    const fact = FC_BREAKS[0] ?? FC_ALEPH;
    const verdict = fcSectionProblem(
      uncheckedFcSection({
        breaks: [{ class_id: 'not_a_class', fact_id: fact }],
      }),
      fcRegistry(),
      [{ fact_id: fact, year: '2024' }],
    );
    expect(verdict).toEqual({ ok: false, code: 'night_class_missing' });
  });

  it('test_an_unknown_direction_is_refused', () => {
    const verdict = fcSectionProblem(
      uncheckedFcSection({ direction: 'sideways' }),
      fcRegistry(),
      [],
    );
    expect(verdict).toEqual({ ok: false, code: 'legend_count_unbound' });
  });

  it('test_an_unknown_coverage_note_is_refused', () => {
    const verdict = fcSectionProblem(
      uncheckedFcSection({ coverage_note_keys: ['not_a_note'] }),
      fcRegistry(),
      [],
    );
    expect(verdict).toEqual({ ok: false, code: 'legend_count_unbound' });
  });

  it('returns the closed section only after the checks pass', () => {
    const fact = FC_BREAKS[0] ?? FC_ALEPH;
    const verdict = fcSectionProblem(
      uncheckedFcSection({
        breaks: [{ class_id: 'band_low', fact_id: fact }],
      }),
      fcRegistry(),
      [{ fact_id: fact, year: '2024' }],
    );
    expect(verdict).toEqual({
      ok: true,
      section: {
        direction: 'higher',
        companies: [],
        coverage_note_keys: ['zone_without_district'],
        breaks: [{ class_id: 'band_low', fact_id: fact }],
      },
    });
    const payload = fcPayload();
    const carried = fcSectionProblem(
      payload.fc_firms,
      fcRegistry(),
      payload.count_facts,
    );
    expect(carried).toMatchObject({
      ok: true,
      section: {
        direction: 'higher',
        companies: payload.fc_firms?.companies,
        coverage_note_keys: ['zone_without_district'],
      },
    });
  });

  it.each([
    {
      name: 'section_not_record',
      section: arraySection(),
      code: 'legend_count_unbound',
    },
    {
      name: 'coverage_note_keys_not_array',
      section: uncheckedFcSection({ coverage_note_keys: null }),
      code: 'legend_count_unbound',
    },
    {
      name: 'breaks_not_array',
      section: uncheckedFcSection({ breaks: null }),
      code: 'night_class_missing',
    },
    {
      name: 'band_not_record',
      section: uncheckedFcSection({ breaks: [null] }),
      code: 'night_class_missing',
    },
    {
      name: 'companies_not_array',
      section: uncheckedFcSection({ companies: null }),
      code: 'legend_count_unbound',
    },
    {
      name: 'company_row_not_record',
      section: uncheckedFcSection({ companies: [null] }),
      code: 'legend_count_unbound',
    },
    {
      name: 'feature_id_not_string',
      section: sectionWithCompany(validCompany({ feature_id: 1 })),
      code: 'legend_count_unbound',
    },
    {
      name: 'row_id_not_string',
      section: sectionWithCompany(validCompany({ row_id: 1 })),
      code: 'legend_count_unbound',
    },
    {
      name: 'fields_not_array',
      section: sectionWithCompany(validCompany({ fields: null })),
      code: 'legend_count_unbound',
    },
    {
      name: 'wage_key_not_string',
      section: sectionWithCompany(validCompany({ wage_key: 1 })),
      code: 'legend_count_unbound',
    },
    {
      name: 'identifier_not_string',
      section: sectionWithCompany(validCompany({ identifier: 1 })),
      code: 'legend_count_unbound',
    },
    {
      name: 'employee_count_not_string',
      section: sectionWithCompany(validCompany({ employee_count: 1 })),
      code: 'legend_count_unbound',
    },
    {
      name: 'attached_not_string',
      section: sectionWithCompany(validCompany({ attached: 1 })),
      code: 'legend_count_unbound',
    },
    {
      name: 'card_field_not_record',
      section: sectionWithCompany(validCompany({ fields: [null] })),
      code: 'legend_count_unbound',
    },
    {
      name: 'card_key_not_string',
      section: sectionWithCompany(
        validCompany({ fields: [validField({ key: 1 })] }),
      ),
      code: 'legend_count_unbound',
    },
    {
      name: 'card_text_not_string',
      section: sectionWithCompany(
        validCompany({ fields: [validField({ text: 1 })] }),
      ),
      code: 'legend_count_unbound',
    },
    {
      name: 'card_segments_not_array',
      section: sectionWithCompany(
        validCompany({ fields: [validField({ segments: null })] }),
      ),
      code: 'legend_count_unbound',
    },
    {
      name: 'segment_not_record',
      section: sectionWithCompany(
        validCompany({ fields: [validField({ segments: [null] })] }),
      ),
      code: 'legend_count_unbound',
    },
    {
      name: 'plain_text_not_string',
      section: sectionWithCompany(
        validCompany({
          fields: [validField({ segments: [{ kind: 'plain', text: 1 }] })],
        }),
      ),
      code: 'legend_count_unbound',
    },
    {
      name: 'kind_not_plain_or_reference',
      section: sectionWithCompany(
        validCompany({
          fields: [
            validField({ segments: [validReference({ kind: 'other' })] }),
          ],
        }),
      ),
      code: 'legend_count_unbound',
    },
    {
      name: 'reference_kind_not_closed',
      section: sectionWithCompany(
        validCompany({
          fields: [
            validField({
              segments: [validReference({ referenceKind: 'not_a_kind' })],
            }),
          ],
        }),
      ),
      code: 'legend_count_unbound',
    },
    {
      name: 'reference_value_not_string',
      section: sectionWithCompany(
        validCompany({
          fields: [validField({ segments: [validReference({ value: 1 })] })],
        }),
      ),
      code: 'legend_count_unbound',
    },
    {
      name: 'reference_record_id_not_string',
      section: sectionWithCompany(
        validCompany({
          fields: [validField({ segments: [validReference({ recordId: 1 })] })],
        }),
      ),
      code: 'legend_count_unbound',
    },
  ])('test_$name', ({ section, code }) => {
    const verdict = fcSectionProblem(section, fcRegistry(), []);
    expect(verdict).toEqual({ ok: false, code });
  });

  it('test_fact_id_not_string', () => {
    const registry = registryReadyForAnyId();
    const resolve = vi.spyOn(registry, 'resolve');
    const verdict = fcSectionProblem(
      uncheckedFcSection({
        breaks: [{ class_id: 'band_low', fact_id: 1 }],
      }),
      registry,
      [{ fact_id: factId(0), year: '2024' }],
    );
    expect(verdict).toEqual({ ok: false, code: 'legend_count_unbound' });
    expect(resolve).not.toHaveBeenCalled();
  });

  it('test_no_data_is_accepted_only_when_boolean_or_absent', () => {
    const kept = {
      direction: 'higher',
      companies: [],
      coverage_note_keys: ['zone_without_district'],
      breaks: [],
    };
    const withFlag = fcSectionProblem(
      uncheckedFcSection({ no_data: true }),
      fcRegistry(),
      [],
    );
    expect(withFlag).toEqual({
      ok: true,
      section: { ...kept, no_data: true },
    });
    const withoutFlag = fcSectionProblem(
      uncheckedFcSection({}),
      fcRegistry(),
      [],
    );
    expect(withoutFlag).toEqual({ ok: true, section: kept });
    const refused = fcSectionProblem(
      uncheckedFcSection({ no_data: 'yes' }),
      fcRegistry(),
      [],
    );
    expect(refused).toEqual({ ok: false, code: 'legend_count_unbound' });
  });

  it.each([
    ['section property', uncheckedFcSection({ wage: 'planted' })],
    ['row property', sectionWithCompany(validCompany({ wage: 'planted' }))],
    [
      'card field property',
      sectionWithCompany(
        validCompany({ fields: [validField({ wage: 'planted' })] }),
      ),
    ],
    [
      'segment property',
      sectionWithCompany(
        validCompany({
          fields: [
            validField({
              segments: [{ kind: 'plain', text: 'Sample', wage: 'planted' }],
            }),
          ],
        }),
      ),
    ],
    [
      'break property',
      uncheckedFcSection({
        breaks: [
          { class_id: 'band_low', fact_id: FC_BREAKS[0], wage: 'planted' },
        ],
      }),
    ],
    [
      'wrong optional type',
      sectionWithCompany(validCompany({ identifier: false })),
    ],
  ])('refuses an unknown or mistyped %s', (_name, section) => {
    expect(
      fcSectionProblem(section, fcRegistry(), fcPayload().count_facts),
    ).toEqual({
      ok: false,
      code: 'legend_count_unbound',
    });
  });

  it.each([FC_DISTRICT, FC_GIMEL])(
    'refuses another geography count on a tower: %s',
    (id) => {
      const payload = fcPayload();
      const tower = payload.layers[0]?.features[0];
      if (!tower) throw new Error('missing tower');
      tower.fact_id = id;
      expect(acceptPayload(payload, fcRegistry())).toEqual({
        ok: false,
        code: 'measure_on_named_feature',
      });
    },
  );

  it('carries the checked section in accepted draw data', () => {
    const payload = fcPayload();
    const section = payload.fc_firms;
    if (!section) throw new Error('missing section');
    const accepted = acceptPayload(payload, fcRegistry());
    expect(accepted.ok).toBe(true);
    if (!accepted.ok) throw new Error('refused valid fixture');
    expect(accepted.draw).toHaveProperty('fcFirms', section);
    expect(accepted.draw).not.toHaveProperty('fcFirms', undefined);
    const checked = Reflect.get(accepted.draw, 'fcFirms');
    expect(checked).not.toBe(section);
    const company = section.companies[0];
    if (!company) throw new Error('missing company');
    company.fields = [...company.fields, { key: 'wage', text: 'planted' }];
    expect(JSON.stringify(checked)).not.toContain('planted');
  });

  it('gives a district-only count a visible fill outside the ramp', () => {
    expect(rampToken(DISTRICT_COUNT_CLASS)).toBeNull();
    expect(fillColor(DISTRICT_COUNT_CLASS)).toEqual([0x5e, 0x97, 0xa6, 255]);
  });

  it('test_an_unrelated_break_fact_is_refused_without_the_unbound_flag', () => {
    const foreign = factId(8);
    const payload = fcPayload();
    if (!payload.fc_firms) throw new Error('missing');
    payload.fc_firms.breaks = [{ class_id: 'band_low', fact_id: foreign }];
    payload.count_facts = [
      ...(payload.count_facts ?? []),
      { fact_id: foreign, year: '2024' },
    ];
    payload.count_without_fact = undefined;
    const accepted = acceptPayload(
      payload,
      firmsRows({
        id: foreign,
        metric: 'place_listing',
        table: 'pub_register_company',
      }),
    );
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('legend_count_unbound');
  });

  it.each([
    {
      name: 'wrong table',
      metric: 'firms_per_tower',
      table: 'pub_place',
    },
    {
      name: 'synthetic provenance',
      metric: 'firms_per_tower',
      table: 'pub_register_company',
      provenance: 'synthetic' as const,
    },
    {
      name: 'unit other than count',
      metric: 'firms_per_tower',
      table: 'pub_register_company',
      unit: 'ratio',
    },
  ])('refuses a break fact with a $name', (spec) => {
    const foreign = factId(8);
    const payload = fcPayload();
    if (!payload.fc_firms) throw new Error('missing');
    payload.fc_firms.breaks = [{ class_id: 'band_low', fact_id: foreign }];
    payload.count_facts = [
      ...(payload.count_facts ?? []),
      { fact_id: foreign, year: '2024' },
    ];
    const accepted = acceptPayload(
      payload,
      firmsRows({ id: foreign, ...spec }),
    );
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('legend_count_unbound');
  });

  it('refuses a break fact the registry cannot resolve', () => {
    const foreign = factId(8);
    const payload = fcPayload();
    if (!payload.fc_firms) throw new Error('missing');
    payload.fc_firms.breaks = [{ class_id: 'band_low', fact_id: foreign }];
    payload.count_facts = [
      ...(payload.count_facts ?? []),
      { fact_id: foreign, year: '2024' },
    ];
    const accepted = acceptPayload(payload, fcRegistry());
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('legend_count_unbound');
  });

  it('refuses legend breaks when no registry is supplied', () => {
    const accepted = acceptPayload(fcPayload());
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('legend_count_unbound');
  });

  it('test_a_break_without_a_year_binding_is_refused', () => {
    const payload = fcPayload();
    const bound = payload.fc_firms?.breaks[0]?.fact_id ?? '';
    payload.count_fact_ids = (payload.count_fact_ids ?? []).filter(
      (id) => id !== bound,
    );
    payload.count_facts = (payload.count_facts ?? []).filter(
      (row) => row.fact_id !== bound,
    );
    const accepted = acceptPayload(payload, fcRegistry());
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('legend_count_unbound');
  });

  it('test_a_planted_district_firm_drawn_as_a_building_point_fails', () => {
    const payload = fcPayload();
    const entry = layerEntry('fc_firms_per_tower');
    const request = payload.layers[0];
    if (!entry || !request) throw new Error('missing entry');
    const planted = fcFeature({
      geometry_kind: 'point',
      subject: 'statistic',
      geography_code: 'district:INV-NORTH',
      class_id: 'band_low',
      position: [51.5, 25.3],
    });
    expect(featureProblem(entry, request, planted, payload)).toBe(
      'invented_point',
    );
  });

  it('test_two_count_classes_draw_two_radii_on_this_layer', () => {
    const overlay = overlayFor(fcPayload(), null, fcRegistry());
    const held = overlay as { _props: { layers: CarriedLayer[] } };
    const scatter = held._props.layers.find(
      (layer) => layer.constructor.layerName === 'ScatterplotLayer',
    );
    expect(scatter?.props.radiusUnits).toBe('pixels');
    expect(scatter?.props.getRadius?.({ classId: 'band_low' })).toBe(6);
    expect(scatter?.props.getRadius?.({ classId: 'band_mid_low' })).toBe(9);
  });

  it('test_a_point_row_of_this_layer_carries_the_ramp_colour_of_its_class', () => {
    const overlay = overlayFor(fcPayload(), null, fcRegistry());
    const held = overlay as { _props: { layers: CarriedLayer[] } };
    const scatter = held._props.layers.find(
      (layer) => layer.constructor.layerName === 'ScatterplotLayer',
    );
    expect(scatter?.props.getFillColor?.({ classId: 'band_low' })).toEqual(
      fillColor('band_low'),
    );
    expect(scatter?.props.getFillColor?.({ classId: 'band_mid_low' })).toEqual(
      fillColor('band_mid_low'),
    );
  });

  it('test_every_existing_point_layer_keeps_its_current_props', () => {
    const extras: Record<string, Record<string, string>> = {
      rail_plan: { status_key: 'planned' },
      fdi_projects: { subject: 'fdi_project', year: '2024' },
    };
    const pointLayers = LAYER_ENTRIES.filter(
      (entry) =>
        entry.implemented &&
        entry.layerTypes.includes('ScatterplotLayer') &&
        entry.key !== 'fc_firms_per_tower' &&
        // S3-T12's new establishment points carry their own pinned style
        // (tests/component/company-points.test.tsx).
        entry.key !== 'company_points',
    );
    expect(pointLayers.length).toBeGreaterThan(0);
    for (const entry of pointLayers) {
      const metric =
        entry.key === 'fdi_projects'
          ? 'fdi_sector'
          : (entry.metricKeys[0] ?? '');
      const table = entry.table.split(',')[0]?.trim() ?? entry.table;
      const payload = basePayload({
        layers: [
          {
            key: entry.key,
            visible: true,
            source_chain_fact_id: CHAIN_ID,
            source_id: 'src_places',
            features: [
              {
                feature_id: 'feat_sweep',
                metric_key: metric,
                provenance: 'public',
                subject: 'place',
                geometry_kind: 'point',
                fact_id: CHAIN_ID,
                position: [51.5, 25.3],
                ...extras[entry.key],
              },
            ],
          },
        ],
        ...(entry.key === 'fdi_projects' ? { credits: SAMPLE_CREDITS } : {}),
      });
      const layers = scatterLayers(payload, metric, table);
      if (layers.length === 0) {
        const accepted = acceptPayload(
          payload,
          layerRegistry([{ id: CHAIN_ID, metric, table }]),
        );
        const code = accepted.ok ? 'no-scatter' : accepted.code;
        throw new Error(`${entry.key}:${code}`);
      }
      for (const layer of layers) {
        expect(layer.props.radiusUnits).toBe('meters');
        expect(typeof layer.props.getRadius).toBe('number');
        expect(layer.props.getRadius).toBe(1);
      }
    }
  });

  it('test_a_tower_feature_without_a_position_draws_no_mark_but_stays_listed', () => {
    const overlay = overlayFor(fcPayload(), null, fcRegistry());
    const held = overlay as { _props: { layers: CarriedLayer[] } };
    const scatter = held._props.layers.find(
      (layer) => layer.constructor.layerName === 'ScatterplotLayer',
    );
    const data = (scatter?.props.data ?? []) as { featureId: string }[];
    expect(data.map((row) => row.featureId)).not.toContain(
      'feat-invented-tower-gimel',
    );
    expect(data.map((row) => row.featureId)).toContain(
      'feat-invented-tower-aleph',
    );
  });

  it('test_no_count_or_break_is_computed_in_the_browser', () => {
    expect(pointRadiusPx.length).toBe(1);
    expect(pointRadiusPx('band_low')).toBe(6);
    expect(pointRadiusPx('band_high')).toBe(18);
    expect(pointRadiusPx('not_a_class')).toBe(0);
  });
});
