// @vitest-environment jsdom
/**
 * S3-T12 box 12: the commerce register's establishment points. Invented rows
 * only. Each plant puts a wage, a labour or residence detail, a Simulated
 * figure or a Synthetic figure other than the permitted employee count on a
 * point, a label or a card, and each is refused.
 */
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { PublicLayers } from '../../src/stage/layers/PublicLayers';
import { acceptPayload } from '../../src/stage/layers/refuse';
import { layerEntry } from '../../src/stage/layers/registry';
import type {
  CompanyCardRow,
  LayerFeature,
  LayerPayload,
} from '../../src/stage/layers/payload';
import { factId } from '../fixtures/facts';
import { layerRegistry } from '../fixtures/layer-registry';
import { basePayload, plain } from '../fixtures/layers';
import type { Provenance } from '../../src/facts/registry';

afterEach(() => {
  cleanup();
});

const POINT = factId(0);
const FEATURE_ID = 'company_points:invented0aleph00';

function registry(provenance: Provenance = 'public') {
  return layerRegistry([
    {
      id: POINT,
      metric: 'register_company_point',
      table: 'pub_register_company',
      provenance,
      unit: 'calendar_date',
    },
  ]);
}

function point(overrides: Partial<LayerFeature> = {}): LayerFeature {
  return {
    feature_id: FEATURE_ID,
    metric_key: 'register_company_point',
    provenance: 'public',
    fact_id: POINT,
    subject: 'business',
    geometry_kind: 'point',
    source_id: 'src_register',
    position: [51.5, 25.3],
    ...overrides,
  };
}

function card(overrides: Partial<CompanyCardRow> = {}): CompanyCardRow {
  return {
    feature_id: FEATURE_ID,
    row_id: 'company-invented0aleph00',
    fields: [
      {
        key: 'establishment_nationality',
        segments: [plain('Invented nationality')],
      },
    ],
    employee_count: {
      state: 'absent',
      reason_key: 'protected_not_in_public_release',
    },
    ...overrides,
  };
}

function payload(
  feature: LayerFeature = point(),
  cards: readonly unknown[] = [card()],
): LayerPayload {
  return basePayload({
    layers: [
      {
        key: 'company_points',
        visible: true,
        source_chain_fact_id: POINT,
        source_id: 'src_register',
        features: [feature],
      },
    ],
    company_cards: cards as readonly CompanyCardRow[],
    sources: [
      {
        sourceId: 'src_register',
        attribution: [plain('Sample register credit')],
        retrievalDate: '2024-03-14',
        publisher: [plain('Sample Publisher')],
        datasetOrPage: 'Sample register page',
        licenceOrTerms: 'Terms recorded for this sample',
      },
    ],
  });
}

describe('company_points layer', () => {
  it('is implemented as a non-hero points layer over pub_register_company', () => {
    const entry = layerEntry('company_points');
    expect(entry?.implemented).toBe(true);
    expect(entry?.hero).toBe(false);
    expect(entry?.table).toBe('pub_register_company');
    expect(entry?.layerTypes).toEqual(['ScatterplotLayer']);
    expect(entry?.metricKeys).toEqual(['register_company_point']);
  });

  it('accepts a clean point and draws it as a scatterplot point', () => {
    const result = acceptPayload(payload(), registry());
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    const layer = result.draw.layers.find((l) => l.key === 'company_points');
    expect(layer?.layerType).toBe('ScatterplotLayer');
    expect(layer?.marks).toEqual([FEATURE_ID]);
    expect(layer?.labels).toEqual([]);
  });

  for (const language of ['en', 'ar'] as const) {
    it(`a tap opens the company card with the count absent and its reason (${language})`, () => {
      const view = render(
        <PublicLayers
          payload={payload()}
          language={language}
          registry={registry()}
          onOpenChain={() => undefined}
        />,
      );
      expect(view.container.querySelector('[data-part="company-card"]')).toBe(
        null,
      );
      const button = view.container.querySelector(
        `[data-feature="${FEATURE_ID}"]`,
      );
      if (!button) throw new Error('point button missing');
      fireEvent.click(button);
      const shown = view.container.querySelector('[data-part="company-card"]');
      expect(shown).toBeTruthy();
      expect(shown?.textContent).toContain('Invented nationality');
      const count = shown?.querySelector('[data-field="employee_count"]');
      expect(count?.getAttribute('data-state')).toBe('absent');
      expect(count?.getAttribute('data-reason')).toBe(
        'protected_not_in_public_release',
      );
      // Never a zero, and no numeral outside the Fact chip family.
      expect(count?.textContent ?? '').not.toMatch(/[0-9٠-٩۰-۹]/u);
      expect((count?.textContent ?? '').trim().length).toBeGreaterThan(0);
    });
  }
});

const PLANTS: Record<string, () => ReturnType<typeof acceptPayload>> = {
  wage_on_card: () =>
    acceptPayload(
      payload(point(), [
        card({
          fields: [{ key: 'wage', segments: [plain('Invented wage')] }],
        }),
      ]),
      registry(),
    ),
  wage_bill_word_on_point: () =>
    acceptPayload(
      payload(point({ words: { wage_bill: 'Invented bill' } })),
      registry(),
    ),
  wage_metric_on_point: () =>
    acceptPayload(payload(point({ metric_key: 'wage' })), registry()),
  occupation_on_card: () =>
    acceptPayload(
      payload(point(), [
        card({
          fields: [
            { key: 'occupation', segments: [plain('Invented occupation')] },
          ],
        }),
      ]),
      registry(),
    ),
  residence_label_on_point: () =>
    acceptPayload(
      payload(point({ label_key: 'residence_municipality' })),
      registry(),
    ),
  simulated_point: () =>
    acceptPayload(payload(point({ provenance: 'simulated' })), registry()),
  simulated_fact_bound: () => acceptPayload(payload(), registry('simulated')),
  synthetic_fact_other_than_employee_count: () =>
    acceptPayload(payload(), registry('synthetic')),
  synthetic_point: () =>
    acceptPayload(payload(point({ provenance: 'synthetic' })), registry()),
  employee_count_figure_on_card: () =>
    acceptPayload(
      payload(point(), [
        {
          ...card(),
          employee_count: { state: 'released', value: 7 },
        },
      ]),
      registry(),
    ),
  zero_beside_absent_count: () =>
    acceptPayload(
      payload(point(), [
        {
          ...card(),
          employee_count: {
            state: 'absent',
            reason_key: 'protected_not_in_public_release',
            value: 0,
          },
        },
      ]),
      registry(),
    ),
  attached_detail_on_card: () =>
    acceptPayload(
      payload(point(), [{ ...card(), attached: 'Invented attached' }]),
      registry(),
    ),
};

describe('company_points plants', () => {
  for (const [name, run] of Object.entries(PLANTS)) {
    it(`refuses ${name}`, () => {
      const result = run();
      expect(result.ok).toBe(false);
    });
  }
});

// Review round 2. F1: the card is closed at every nesting level.
const NATIONALITY = {
  key: 'establishment_nationality',
  segments: [plain('Invented nationality')],
};

function cardWith(overrides: Record<string, unknown>): unknown {
  return { ...card(), ...overrides };
}

function fieldWith(overrides: Record<string, unknown>): unknown {
  return cardWith({ fields: [{ ...NATIONALITY, ...overrides }] });
}

function segmentWith(overrides: Record<string, unknown>): unknown {
  return fieldWith({
    segments: [{ ...plain('Invented nationality'), ...overrides }],
  });
}

const NESTED_PLANTS: Record<string, unknown> = {
  nested_wage_key_in_field: fieldWith({ wage: 'Invented wage' }),
  nested_unknown_key_in_field: fieldWith({ note: 'Invented note' }),
  nested_wage_key_in_segment: segmentWith({ wage: 'Invented wage' }),
  nested_unknown_key_in_segment: segmentWith({ note: 'Invented note' }),
  nested_object_as_segment_text: segmentWith({
    text: { wage: 'Invented wage' },
  }),
  nested_object_as_segment_kind: segmentWith({
    kind: { wage: 'Invented wage' },
  }),
  nested_object_as_row_id: cardWith({ row_id: { wage: 'Invented wage' } }),
  nested_object_as_feature_id: cardWith({
    feature_id: { wage: 'Invented wage' },
  }),
  text_beside_segments: fieldWith({ text: 'Invented text' }),
  text_instead_of_segments: cardWith({
    fields: [{ key: 'establishment_nationality', text: 'Invented text' }],
  }),
  segments_not_a_list: fieldWith({ segments: { wage: 'Invented wage' } }),
  field_without_segments: fieldWith({ segments: [] }),
  fields_not_a_list: cardWith({
    fields: { key: 'establishment_nationality', wage: 'Invented wage' },
  }),
  field_not_an_object: cardWith({ fields: ['wage'] }),
  unknown_segment_kind: segmentWith({ kind: 'wage' }),
};

describe('company_points nested plants', () => {
  for (const [name, planted] of Object.entries(NESTED_PLANTS)) {
    it(`refuses ${name}`, () => {
      const result = acceptPayload(payload(point(), [planted]), registry());
      expect(result.ok).toBe(false);
      if (result.ok) return;
      expect(result.code).toBe('wage_or_synthetic_id');
    });
  }
});

// The same closure on the point: every value a string, the position a pair.
const POINT_PLANTS: Record<string, Record<string, unknown>> = {
  nested_object_as_point_source: { source_id: { wage: 'Invented wage' } },
  nested_object_as_point_identifier: {
    feature_id: { wage: 'Invented wage' },
  },
  nested_object_in_point_position: {
    position: [51.5, 25.3, { wage: 'Invented wage' }],
  },
  nested_object_as_point_position: { position: { wage: 'Invented wage' } },
};

describe('company_points nested point plants', () => {
  for (const [name, planted] of Object.entries(POINT_PLANTS)) {
    it(`refuses ${name}`, () => {
      const feature = { ...point(), ...planted } as unknown as LayerFeature;
      const result = acceptPayload(payload(feature), registry());
      expect(result.ok).toBe(false);
      if (result.ok) return;
      expect(result.code).toBe('wage_or_synthetic_id');
    });
  }
});

describe('company_points card shape', () => {
  it('refuses a card list that is not a list', () => {
    const planted = payload();
    (planted as unknown as { company_cards: unknown }).company_cards = {
      wage: 'Invented wage',
    };
    const result = acceptPayload(planted, registry());
    expect(result.ok).toBe(false);
  });

  it('refuses a numeral in a plain segment of a card field', () => {
    const result = acceptPayload(
      payload(point(), [segmentWith({ text: 'Invented 7' })]),
      registry(),
    );
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.code).toBe('numeral_in_plain_segment');
  });
});

// F2: a card reference binds a fact of the registry (rules 7 and 23).
const FIELD_FACT = factId(1);
const ABSENT_FACT = factId(5);
const FIELD_TEXT = 'Invented 7';

function referenceCard(
  recordId: string,
  value: string = FIELD_TEXT,
  referenceKind: string = 'published_text',
): unknown {
  return fieldWith({
    segments: [{ kind: 'reference', referenceKind, value, recordId }],
  });
}

function fieldRegistry(
  spec: Partial<{
    metric: string;
    table: string;
    provenance: Provenance;
    unit: string;
    value: string;
  }> = {},
) {
  return layerRegistry([
    {
      id: POINT,
      metric: 'register_company_point',
      table: 'pub_register_company',
      unit: 'calendar_date',
    },
    {
      id: FIELD_FACT,
      metric: spec.metric ?? 'register_company_point',
      table: spec.table ?? 'pub_register_company',
      provenance: spec.provenance ?? 'public',
      unit: spec.unit ?? 'published_text',
      // The fixture types a count; a published text is a string value.
      value: (spec.value ?? FIELD_TEXT) as unknown as number,
    },
  ]);
}

describe('company_points card references', () => {
  it('accepts a reference bound to a Public fact of the register table', () => {
    const result = acceptPayload(
      payload(point(), [referenceCard(FIELD_FACT)]),
      fieldRegistry(),
    );
    expect(result.ok).toBe(true);
  });

  const UNBOUND: Record<string, () => ReturnType<typeof acceptPayload>> = {
    absent_fact_id: () =>
      acceptPayload(
        payload(point(), [referenceCard(ABSENT_FACT)]),
        fieldRegistry(),
      ),
    feature_id_as_record: () =>
      acceptPayload(
        payload(point(), [referenceCard(FEATURE_ID)]),
        fieldRegistry(),
      ),
    no_registry: () =>
      acceptPayload(payload(point(), [referenceCard(FIELD_FACT)])),
    fact_of_another_table: () =>
      acceptPayload(
        payload(point(), [referenceCard(FIELD_FACT)]),
        fieldRegistry({ table: 'pub_place' }),
      ),
    fact_of_another_metric: () =>
      acceptPayload(
        payload(point(), [referenceCard(FIELD_FACT)]),
        fieldRegistry({ metric: 'wage' }),
      ),
    synthetic_fact: () =>
      acceptPayload(
        payload(point(), [referenceCard(FIELD_FACT)]),
        fieldRegistry({ provenance: 'synthetic' }),
      ),
    value_differs_from_its_fact: () =>
      acceptPayload(
        payload(point(), [referenceCard(FIELD_FACT, 'Invented 8')]),
        fieldRegistry(),
      ),
    kind_differs_from_its_fact: () =>
      acceptPayload(
        payload(point(), [referenceCard(FIELD_FACT, FIELD_TEXT)]),
        fieldRegistry({ unit: 'count' }),
      ),
  };
  for (const [name, run] of Object.entries(UNBOUND)) {
    it(`refuses a card reference: ${name}`, () => {
      expect(run().ok).toBe(false);
    });
  }

  it('names the missing chain when the fact id is absent', () => {
    const result = UNBOUND.absent_fact_id!();
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.code).toBe('incomplete_source_chain');
  });
});

// Round 4: a point's fact_id resolves through the fact registry to the
// register table and the layer's own metric, as a card reference does.
describe('company_points point fact', () => {
  const POINT_FACT: Record<string, () => ReturnType<typeof acceptPayload>> = {
    absent_fact_id: () =>
      acceptPayload(payload(point({ fact_id: ABSENT_FACT })), registry()),
    fact_of_another_table: () =>
      acceptPayload(
        payload(),
        layerRegistry([
          {
            id: POINT,
            metric: 'register_company_point',
            table: 'pub_place',
            unit: 'calendar_date',
          },
        ]),
      ),
    fact_of_another_metric: () =>
      acceptPayload(
        payload(),
        layerRegistry([
          {
            id: POINT,
            metric: 'landmark_name',
            table: 'pub_register_company',
            unit: 'calendar_date',
          },
        ]),
      ),
    no_fact_id: () => {
      const bare = point();
      delete bare.fact_id;
      return acceptPayload(payload(bare), registry());
    },
    empty_fact_id: () =>
      acceptPayload(payload(point({ fact_id: '' })), registry()),
    no_registry: () => acceptPayload(payload()),
  };
  for (const [name, run] of Object.entries(POINT_FACT)) {
    it(`refuses a point: ${name}`, () => {
      expect(run().ok).toBe(false);
    });
  }

  it('names the missing chain when the point fact is absent', () => {
    const result = POINT_FACT.absent_fact_id!();
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.code).toBe('incomplete_source_chain');
  });

  for (const name of ['fact_of_another_table', 'fact_of_another_metric']) {
    it(`names the measure on a named feature: ${name}`, () => {
      const result = POINT_FACT[name]!();
      expect(result.ok).toBe(false);
      if (result.ok) return;
      expect(result.code).toBe('measure_on_named_feature');
    });
  }
});

describe('company_points overlay', () => {
  it('draws every establishment point at one size and one neutral colour', async () => {
    const { overlayFor, COMPANY_POINT_RADIUS_PX } =
      await import('../../src/stage/layers/overlay');
    const { boundaryColor } = await import('../../src/stage/layers/ramp');
    const overlay = overlayFor(payload(), null, registry()) as unknown as {
      _props: {
        layers: {
          id: string;
          props: {
            getRadius: unknown;
            radiusUnits: string;
            getFillColor: () => unknown;
          };
        }[];
      };
    };
    const layer = overlay._props.layers.find(
      (item) => item.id === 'company_points:ScatterplotLayer',
    );
    expect(layer?.props.getRadius).toBe(COMPANY_POINT_RADIUS_PX);
    expect(layer?.props.radiusUnits).toBe('pixels');
    expect(layer?.props.getFillColor()).toEqual(boundaryColor());
  });
});
