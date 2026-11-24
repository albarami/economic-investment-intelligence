// @vitest-environment jsdom
import { cleanup, render } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';

import {
  contextAccepted,
  PublicContextCard,
} from '../../src/cards/PublicContextCard';
import { answerAccepted, catalogue } from '../../src/brief/catalogue';
import { createRegistry } from '../../src/facts/registry';
import {
  contextInput,
  contextPayloads,
  contextRegistry,
} from '../fixtures/public-context';

afterEach(cleanup);

for (const language of ['en', 'ar'] as const) {
  it(`renders the three closed cards in ${language} with only chip numerals`, () => {
    const { container } = render(
      <div lang={language} dir={language === 'ar' ? 'rtl' : 'ltr'}>
        {contextPayloads.map((payload) => (
          <PublicContextCard
            key={payload.family}
            payload={payload}
            language={language}
            registry={contextRegistry()}
            onOpen={() => undefined}
          />
        ))}
      </div>,
    );
    expect(container.querySelectorAll('article')).toHaveLength(3);
    expect(container.querySelectorAll('[data-fact-chip="value"]')).toHaveLength(
      3,
    );
    const clone = container.cloneNode(true) as HTMLElement;
    clone.querySelectorAll('[data-fact-chip]').forEach((chip) => chip.remove());
    expect(clone.textContent).not.toMatch(/\p{N}/u);
    expect(container.textContent).toContain(
      language === 'ar' ? 'للعرض فقط' : 'Display only',
    );
  });

  it(`shows no provider figure and its reason in ${language}`, () => {
    const { container } = render(
      <PublicContextCard
        language={language}
        registry={contextRegistry()}
        onOpen={() => undefined}
        payload={{
          family: 'venue_busyness',
          state: 'no_data',
          reason: 'no_forecast',
        }}
      />,
    );
    expect(container.querySelector('[data-fact-chip="value"]')).toBeNull();
    expect(container.textContent).toContain(
      language === 'ar' ? 'لا ينشر المزود' : 'provider publishes no figure',
    );
  });
}

it('refuses a busyness component with an estimated-people or extra figure slot', () => {
  const payload = contextPayloads[1];
  expect(
    contextAccepted(
      { ...payload, estimatedPeopleId: 'fixture_people' },
      contextRegistry(),
    ),
  ).toBe(false);
});

it('refuses C38 in ranking, criterion and chart inputs and any mixed component', () => {
  const payload = contextPayloads[2];
  for (const extra of [
    { rank: 'first' },
    { criterion: 'population' },
    { chart: ['fixture_protected'] },
    { simulatedFactId: 'fixture_movement' },
  ]) {
    expect(contextAccepted({ ...payload, ...extra }, contextRegistry())).toBe(
      false,
    );
  }
});

it('refuses a context figure in the generic Brief component', () => {
  expect(
    answerAccepted(
      {
        catalogueVersion: catalogue.version,
        accountingPassed: true,
        subject: 'area',
        componentKey: 'foundation_note',
        props: [],
        directive: null,
        slots: [
          {
            factId:
              contextPayloads[2]?.state === 'ready'
                ? contextPayloads[2].factId
                : '',
            provenance: 'public',
            metric: 'population_grid_people',
          },
        ],
      },
      contextRegistry(),
    ),
  ).toBe(false);
});

it('refuses non-Observed population and incomplete lineage or retrieval', () => {
  const input = contextInput();
  const binding = input.facts[2];
  if (!binding) throw new Error('fixture');
  binding.fact.evidence_status = 'inferred';
  expect(contextAccepted(contextPayloads[2], createRegistry(input))).toBe(
    false,
  );
  expect(
    contextAccepted(
      contextPayloads[0],
      createRegistry({ ...contextInput(), sources: [] }),
    ),
  ).toBe(false);
  expect(
    contextAccepted(
      { ...contextPayloads[1], retrievedOn: null },
      contextRegistry(),
    ),
  ).toBe(false);
  expect(
    contextAccepted(
      { ...contextPayloads[1], providerUpdatedOn: '2025-12-30' },
      contextRegistry(),
    ),
  ).toBe(false);
});

it('refuses business activity wording and an apportioned or summed radiance plant', () => {
  for (const change of [
    { label_en: 'Business activity' },
    { caveat_keys: ['night_lights_not_activity', 'grid_cells_summed'] },
    {
      geography: {
        kind: 'area_shape' as const,
        area_id: 'fixture_area',
        apportioned_from: 'fixture_zone',
      },
    },
  ]) {
    const input = contextInput();
    const binding = input.facts[0];
    if (!binding) throw new Error('fixture');
    Object.assign(binding.fact, change);
    expect(contextAccepted(contextPayloads[0], createRegistry(input))).toBe(
      false,
    );
  }
});

it.each([{ day: 'tuesday' }, { hour: '10' }, { day: 'tuesday', hour: '10' }])(
  'refuses C37 when only its displayed selection changes: %j',
  (change) => {
    const payload = contextPayloads[1];
    expect(contextAccepted(payload, contextRegistry())).toBe(true);
    expect(contextAccepted({ ...payload, ...change }, contextRegistry())).toBe(
      false,
    );
  },
);

it.each([
  { sex: 'male' },
  { ageBand: '25' },
  { sex: 'none' },
  { ageBand: null },
  { sex: 'none', ageBand: null },
])('refuses C38 source-category relabelling: %j', (change) => {
  const payload = contextPayloads[2];
  expect(contextAccepted(payload, contextRegistry())).toBe(true);
  expect(contextAccepted({ ...payload, ...change }, contextRegistry())).toBe(
    false,
  );
});

it('accepts matching C38 aggregate and one-way selections and refuses a split label', () => {
  for (const [ageBand, sex] of [
    [null, 'none'],
    [null, 'female'],
    ['20', 'none'],
    ['20', 'female'],
  ] as const) {
    const input = contextInput();
    const binding = input.facts[2];
    if (!binding) throw new Error('fixture');
    Object.assign(binding, { qualifiers: { age_band: ageBand ?? 'all', sex } });
    const registry = createRegistry(input);
    const payload = { ...contextPayloads[2], ageBand, sex };
    expect(contextAccepted(payload, registry)).toBe(true);
    expect(
      contextAccepted({ ...payload, ageBand: '25', sex: 'male' }, registry),
    ).toBe(false);
  }
});

it.each([1, 2])(
  'refuses missing fixed-reader qualifiers for context fixture %s',
  (index) => {
    const input = contextInput();
    const binding = input.facts[index];
    if (!binding) throw new Error('fixture');
    delete binding.qualifiers;
    expect(contextAccepted(contextPayloads[index], createRegistry(input))).toBe(
      false,
    );
  },
);

it('preserves the source own age-band key beside the fact', () => {
  const input = contextInput();
  input.facts[2]!.qualifiers = { age_band: 'a00_14', sex: 'female' };
  expect(
    contextAccepted(
      { ...contextPayloads[2], ageBand: 'a00_14' },
      createRegistry(input),
    ),
  ).toBe(true);
});
