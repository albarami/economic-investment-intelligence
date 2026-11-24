/**
 * CF1 finding 2 class sweep: every field that acceptance reads as text (or
 * as a list of keys) in `refuse.ts`, given a value an uncast HTTP body can
 * carry. Each case changes ONE input of a valid baseline and asserts its own
 * closed code; none may throw (L-1409).
 */
import { describe, expect, it } from 'vitest';

import { boundScene, NOT_TEXT } from '../fixtures/accident-scene';
import { FC_CHAIN, fcPayload, fcRegistry } from '../fixtures/fc-firms';
import {
  CHAIN_ID,
  SAMPLE_CREDITS,
  basePayload,
  category,
} from '../fixtures/layers';
import type { FactRegistry } from '../../src/facts/registry';
import type {
  LayerFeature,
  LayerPayload,
} from '../../src/stage/layers/payload';
import { acceptPayload, type RefusalCode } from '../../src/stage/layers/refuse';

type Values = readonly (readonly [string, unknown])[];

/** An optional field: absent and null stay absent; these are not text. */
const NOT_STRING: Values = NOT_TEXT.filter(
  ([, value]) => value !== null && typeof value !== 'string',
);

/** A caveat list that is not a list, including a text that holds the key. */
function notList(key: string): Values {
  return [
    ['null', null],
    ['a text holding the key', key],
    ['a number', 1],
    ['an object', { 0: key }],
  ];
}

interface Case {
  field: string;
  base: () => LayerPayload;
  registry?: () => FactRegistry;
  set: (payload: LayerPayload, value: unknown) => void;
  values: Values;
  /** The baseline's own text: wrapped in a JSON list, it still is not text. */
  valid?: string;
  code: RefusalCode;
}

function first(payload: LayerPayload): Record<string, unknown> {
  return payload.layers[0]!.features[0]! as unknown as Record<string, unknown>;
}

function withFeature(key: string, feature: LayerFeature): LayerPayload {
  return basePayload({
    layers: [{ ...basePayload().layers[0]!, key, features: [feature] }],
  });
}

function apportioned(): LayerPayload {
  return withFeature('property_prices', {
    feature_id: 'feat_sale',
    metric_key: 'district_sale',
    provenance: 'public',
    subject: 'statistic',
    geometry_kind: 'fill',
    fact_id: CHAIN_ID,
    apportioned_from: 'INVENTED-parent',
    evidence_status: 'inferred',
    method_id: 'INVENTED-method',
    geography_code: 'district:INVENTED-part',
  });
}

function night(): LayerPayload {
  return {
    ...withFeature('night_lights', {
      feature_id: 'feat_night',
      metric_key: 'radiance_class',
      provenance: 'public',
      subject: 'statistic',
      geometry_kind: 'hex',
      cell: '89536bc1ea3ffff',
      resolution: 9,
      fact_id: CHAIN_ID,
      class_id: 'band_low',
    }),
    night: {
      month: '2024-03',
      direction: 'higher',
      class_id: 'band_low',
      unit: 'radiance_nw_cm2_sr',
      caveat_key: 'night_lights_not_activity',
    },
  };
}

function split(): LayerPayload {
  const categories = [category('group_b'), category('group_a')];
  return basePayload({
    sources: [
      {
        ...basePayload().sources[0]!,
        year: '2024',
        categories,
        geographyCode: 'sample_geo',
      },
    ],
    split_chip: {
      provenance: 'public',
      evidence_status: 'observed',
      source_id: 'src_places',
      year: '2024',
      categories,
      geography_code: 'sample_geo',
      source_geography: 'sample_geo',
    },
  });
}

function estimate(): LayerPayload {
  return {
    ...withFeature('fdi_projects', {
      feature_id: 'feat_fdi_aleph',
      metric_key: 'fdi_sector',
      provenance: 'public',
      subject: 'fdi_project',
      geometry_kind: 'point',
      place_key: 'gx_sample_aleph',
      fact_id: CHAIN_ID,
      year: '2024',
      capex_fact_id: CHAIN_ID,
      caveat_keys: ['fdi_estimates'],
    }),
    credits: SAMPLE_CREDITS,
  };
}

function nightField(name: 'unit' | 'month' | 'direction' | 'class_id') {
  return (payload: LayerPayload, value: unknown) => {
    (payload.night as unknown as Record<string, unknown>)[name] = value;
  };
}

function splitField(name: 'source_id' | 'year') {
  return (payload: LayerPayload, value: unknown) => {
    (payload.split_chip as unknown as Record<string, unknown>)[name] = value;
  };
}

function featureField(name: string) {
  return (payload: LayerPayload, value: unknown) => {
    first(payload)[name] = value;
  };
}

const CASES: readonly Case[] = [
  {
    field: 'layer source_chain_fact_id',
    valid: CHAIN_ID,
    base: () => basePayload(),
    set: (payload, value) => {
      (payload.layers[0] as unknown as Record<string, unknown>)[
        'source_chain_fact_id'
      ] = value;
    },
    values: NOT_TEXT,
    code: 'incomplete_source_chain',
  },
  {
    field: 'apportioned method_id',
    valid: 'INVENTED-method',
    base: apportioned,
    set: featureField('method_id'),
    values: NOT_TEXT,
    code: 'apportioned_unlabelled',
  },
  {
    field: 'apportioned geography_code',
    valid: 'district:INVENTED-part',
    base: apportioned,
    set: featureField('geography_code'),
    values: NOT_TEXT,
    code: 'apportioned_unlabelled',
  },
  {
    field: 'split source_id',
    valid: 'src_places',
    base: split,
    set: splitField('source_id'),
    values: NOT_TEXT,
    code: 'split_incomplete',
  },
  {
    field: 'split year',
    valid: '2024',
    base: split,
    set: splitField('year'),
    values: NOT_TEXT,
    code: 'split_incomplete',
  },
  {
    field: 'night unit',
    valid: 'radiance_nw_cm2_sr',
    base: night,
    set: nightField('unit'),
    values: NOT_TEXT,
    code: 'night_unit_missing',
  },
  {
    field: 'night month',
    valid: '2024-03',
    base: night,
    set: nightField('month'),
    values: NOT_TEXT,
    code: 'night_month_missing',
  },
  {
    field: 'night direction',
    valid: 'higher',
    base: night,
    set: nightField('direction'),
    values: NOT_TEXT,
    code: 'night_direction_missing',
  },
  {
    field: 'night class_id',
    valid: 'band_low',
    base: night,
    set: nightField('class_id'),
    values: NOT_TEXT,
    code: 'night_class_missing',
  },
  {
    field: 'feature identifier',
    valid: 'INVENTED-identifier',
    base: () => {
      const payload = basePayload();
      first(payload).identifier = 'INVENTED-identifier';
      return payload;
    },
    set: featureField('identifier'),
    values: NOT_STRING,
    code: 'wage_or_synthetic_id',
  },
  {
    field: 'firms point geography_code',
    valid: 'place:INV-TOWER-ALEPH',
    base: () => fcPayload(),
    registry: () => fcRegistry(),
    set: featureField('geography_code'),
    values: NOT_STRING,
    code: 'invented_point',
  },
  {
    field: 'estimate caveat_keys',
    base: estimate,
    set: featureField('caveat_keys'),
    values: notList('fdi_estimates'),
    code: 'announced_estimate_unlabelled',
  },
];

function verdict(item: Case, change?: (payload: LayerPayload) => void) {
  const payload = item.base();
  change?.(payload);
  const result = acceptPayload(payload, item.registry?.());
  return result.ok ? 'ok' : result.code;
}

describe('text fields of an uncast layer body (CF1 finding 2 sweep)', () => {
  it.each(CASES.map((item) => [item.field, item] as const))(
    'accepts the %s baseline (control)',
    (_field, item) => {
      expect(verdict(item)).toBe('ok');
    },
  );

  it.each(
    CASES.flatMap((item) =>
      [
        ...item.values,
        ...(item.valid === undefined
          ? []
          : [['its own text in a list', [item.valid]] as const]),
      ].map(
        ([kind, value]) => [item.field, kind, item.code, item, value] as const,
      ),
    ),
  )('refuses %s as %s with %s', (_field, _kind, code, item, value) => {
    expect(verdict(item, (payload) => item.set(payload, value))).toBe(code);
  });

  it('keeps an absent optional identifier and firms code absent', () => {
    for (const item of CASES.filter((c) => c.values === NOT_STRING))
      for (const value of [null, undefined])
        expect(
          verdict(item, (payload) => item.set(payload, value)),
          item.field,
        ).toBe(
          item.field === 'feature identifier'
            ? 'ok'
            : 'measure_on_named_feature',
        );
  });

  it.each(notList('accidents_recorded_not_risk'))(
    'refuses accident caveat_keys as %s with accident_caveat_missing',
    (_kind, value) => {
      const { body, registry } = boundScene((p) => {
        (p.accident as unknown as Record<string, unknown>).caveat_keys = value;
      });
      const result = acceptPayload(body.payload, registry);
      expect(result.ok ? 'ok' : result.code).toBe('accident_caveat_missing');
    },
  );

  it('binds the firms baseline to its own chain', () => {
    expect(fcPayload().layers[0]!.source_chain_fact_id).toBe(FC_CHAIN);
  });
});
