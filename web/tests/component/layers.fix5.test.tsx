// @vitest-environment jsdom
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';

import { createRegistry } from '../../src/facts/registry';
import { PublicLayers } from '../../src/stage/layers/PublicLayers';
import { acceptPayload } from '../../src/stage/layers/refuse';
import { deckLayers } from '../../src/stage/layers/overlay';
import { FDI_WORD_FIELDS } from '../../src/stage/layers/fdi';
import { apiLayerCases } from '../fixtures/api-layer-cases';

const cases = apiLayerCases();
afterEach(cleanup);

for (const language of ['en', 'ar'] as const) {
  it(`F2 mounts all published FDI fields, typed digits, filters and placement in ${language}`, () => {
    const route = cases.fdi!;
    expect(route.status).toBe(200);
    const payload = route.body.payload;
    const registry = createRegistry(route.registry);
    const view = render(
      <PublicLayers
        payload={payload}
        registry={registry}
        language={language}
        onOpenChain={() => undefined}
      />,
    );
    expect(
      view.container.querySelector('[data-part="layer-refusal"]'),
    ).toBeNull();
    expect(
      view.container
        .querySelector('[data-part="public-layers"]')
        ?.getAttribute('dir'),
    ).toBe(language === 'ar' ? 'rtl' : 'ltr');
    const first = view.container.querySelector(
      '[data-project="fdi_abcdefabcdefabcd"]',
    )!;
    for (const field of FDI_WORD_FIELDS) {
      expect(
        first.querySelector(`[data-field="${field}"]`)?.textContent,
        field,
      ).not.toBe(language === 'en' ? 'Not stated' : 'غير مذكور');
      expect(
        first.querySelector(`[data-field="${field}"]`),
        field,
      ).toBeTruthy();
      const supplied = payload.layers[0]!.features[0]!.field_segments![field]!;
      expect(
        first.querySelector(`[data-field="${field}"]`)?.textContent,
        field,
      ).toBe(
        supplied
          .map((segment) =>
            segment.kind === 'plain' ? segment.text : segment.value,
          )
          .join(''),
      );
    }
    for (const field of ['capex_value', 'jobs', 'lon', 'lat']) {
      expect(
        first.querySelector(`[data-field="${field}"] [data-fact-chip="value"]`),
        field,
      ).toBeTruthy();
      expect(
        first.querySelector(
          `[data-field="${field}"] [data-fact-chip="reference"]`,
        ),
        field,
      ).toBeTruthy();
    }
    expect(first.querySelector('[data-label="announced"]')).toBeTruthy();
    expect(
      first.querySelector('[data-field="company"] [data-fact-chip="reference"]')
        ?.textContent,
    ).toContain('INVENTED Company 2');
    expect(
      first.querySelector(
        '[data-field="announced"] [data-fact-chip="reference"]',
      ),
    ).toBeTruthy();
    const verdict = acceptPayload(payload, registry);
    expect(verdict.ok).toBe(true);
    if (!verdict.ok) throw new Error('route refused');
    expect(verdict.draw.fdiListed).toHaveLength(4);
    expect(verdict.draw.fdiMarks).toEqual([
      'fdi_abcdefabcdefabcd',
      'fdi_cccdefabcdefabcd',
      'fdi_ddcdefabcdefabcd',
    ]);
    expect(
      view.container
        .querySelector('[data-project="fdi_bbcdefabcdefabcd"]')
        ?.getAttribute('data-mark'),
    ).toBe('no');
    const data = deckLayers(verdict.draw.layers, null)[0]!.props
      .data as readonly { featureId: string }[];
    expect(data.map((row) => row.featureId)).toEqual(verdict.draw.fdiMarks);
    for (const key of [
      'sector',
      'source_country',
      'period',
      'stated_location',
    ]) {
      const group = view.container.querySelector(`[data-filter="${key}"]`)!;
      const choice = group.querySelector('button')!;
      expect(choice).toBeTruthy();
      fireEvent.click(choice);
      const selected = choice.getAttribute('data-choice');
      const expected = payload.layers[0]!.features.filter(
        (feature) =>
          feature.filter?.[key as keyof NonNullable<typeof feature.filter>] ===
          selected,
      ).map((feature) => feature.feature_id);
      expect(
        [
          ...view.container.querySelectorAll(
            '[data-part="fdi-list"] [data-project]',
          ),
        ].map((row) => row.getAttribute('data-project')),
      ).toEqual(expected);
      fireEvent.click(choice);
    }
    for (const scope of view.container.querySelectorAll('[data-fdi-fields]')) {
      const textOnly = scope.cloneNode(true) as Element;
      for (const chip of textOnly.querySelectorAll('[data-fact-chip]'))
        chip.remove();
      expect(textOnly.textContent).not.toMatch(/[0-9]/);
    }
  });

  it(`F3 mounts actual mixed source credits and removes them independently in ${language}`, () => {
    const mount = (key: string) => {
      const route = cases[key]!;
      expect(route.status).toBe(200);
      return render(
        <PublicLayers
          payload={route.body.payload}
          registry={createRegistry(route.registry)}
          language={language}
          onOpenChain={() => undefined}
        />,
      );
    };
    const mixed = cases.mixed!;
    const publicId = mixed.body.payload.sources.find(
      (source) => source.sourceId !== 'INVENTED-fsq-source',
    )!.sourceId;
    const view = mount('mixed');
    expect(
      view.container.querySelector(
        `[data-credit="public_places"][data-source="${publicId}"]`,
      ),
    ).toBeTruthy();
    const fsq = view.container.querySelector(
      '[data-credit="public_places"][data-source="INVENTED-fsq-source"]',
    );
    expect(fsq).toBeTruthy();
    expect(
      fsq?.querySelector('[data-record="INVENTED-fsq-source-release"]')
        ?.textContent,
    ).toContain('2025');
    cleanup();
    const fsqOnly = mount('fsq_only');
    expect(
      fsqOnly.container.querySelector(`[data-source="${publicId}"]`),
    ).toBeNull();
    expect(
      fsqOnly.container.querySelector('[data-source="INVENTED-fsq-source"]'),
    ).toBeTruthy();
    cleanup();
    const publicOnly = mount('public_only');
    expect(
      publicOnly.container.querySelector(`[data-source="${publicId}"]`),
    ).toBeTruthy();
    expect(
      publicOnly.container.querySelector('[data-source="INVENTED-fsq-source"]'),
    ).toBeNull();
  });
}

it('plants a digit in a plain published field and refuses the payload', () => {
  const route = structuredClone(cases.fdi!);
  route.body.payload.layers[0]!.features[0]!.field_segments!.company = [
    { kind: 'plain', text: 'INVENTED Company 2' },
  ];
  expect(
    acceptPayload(route.body.payload, createRegistry(route.registry)),
  ).toMatchObject({ ok: false, code: 'numeral_in_plain_segment' });
});

it('plants a digit in a plain filter label and refuses the payload', () => {
  const route = structuredClone(cases.fdi!);
  route.body.payload.filter_options!.period = [
    { key: '2025', label: [{ kind: 'plain', text: '2025' }] },
  ];
  expect(
    acceptPayload(route.body.payload, createRegistry(route.registry)),
  ).toMatchObject({ ok: false, code: 'numeral_in_plain_segment' });
});

it('refuses a published field whose reference fact has been removed', () => {
  const route = structuredClone(cases.fdi!);
  const segment =
    route.body.payload.layers[0]!.features[0]!.field_segments!.company![0]!;
  if (segment.kind !== 'reference') throw new Error('fixture reference absent');
  route.registry.facts = route.registry.facts.filter(
    (binding) => binding.fact.fact_id !== segment.recordId,
  );
  expect(
    acceptPayload(route.body.payload, createRegistry(route.registry)),
  ).toMatchObject({ ok: false, code: 'incomplete_source_chain' });
});

it('refuses a published field reference changed after validation', () => {
  const route = structuredClone(cases.fdi!);
  const segment =
    route.body.payload.layers[0]!.features[0]!.field_segments!.company![0]!;
  if (segment.kind !== 'reference') throw new Error('fixture reference absent');
  segment.value = 'INVENTED-changed 2';
  expect(
    acceptPayload(route.body.payload, createRegistry(route.registry)),
  ).toMatchObject({ ok: false, code: 'measure_on_named_feature' });
});

it('refuses a field outside the published FDI contract', () => {
  const route = structuredClone(cases.fdi!);
  Object.assign(route.body.payload.layers[0]!.features[0]!.field_segments!, {
    INVENTED_unknown: [{ kind: 'plain', text: 'INVENTED' }],
  });
  expect(
    acceptPayload(route.body.payload, createRegistry(route.registry)),
  ).toMatchObject({ ok: false, code: 'measure_on_named_feature' });
});

it('refuses an unbound filter reference', () => {
  const route = structuredClone(cases.fdi!);
  route.body.payload.filter_options!.period = [
    {
      key: '2025',
      label: [
        {
          kind: 'reference',
          referenceKind: 'calendar_year',
          value: '2025',
          recordId: 'INVENTED-missing-fact',
        },
      ],
    },
  ];
  expect(
    acceptPayload(route.body.payload, createRegistry(route.registry)),
  ).toMatchObject({ ok: false, code: 'incomplete_source_chain' });
});

it('keeps a point with changed coordinates listed but never places it from the old facts', () => {
  const route = structuredClone(cases.fdi!);
  const direct = route.body.payload.layers[0]!.features.find(
    (feature) => feature.feature_id === 'fdi_ddcdefabcdefabcd',
  )!;
  direct.position = [2, 2];
  const verdict = acceptPayload(
    route.body.payload,
    createRegistry(route.registry),
  );
  expect(verdict.ok).toBe(true);
  if (!verdict.ok) throw new Error('route refused');
  expect(verdict.draw.fdiListed).toContain(direct.feature_id);
  expect(verdict.draw.fdiMarks).not.toContain(direct.feature_id);
});

it('preserves an absent source year and the existing year refusal pending the contract consultation', () => {
  const route = cases.undated!;
  expect(route.status).toBe(200);
  expect(route.body.payload.layers[0]!.features[0]!.year).toBe('');
  expect(route.body.payload.layers[0]!.features[0]!.announced).toBeUndefined();
  const view = render(
    <PublicLayers
      payload={route.body.payload}
      registry={createRegistry(route.registry)}
      language="en"
      onOpenChain={() => undefined}
    />,
  );
  expect(
    view.container.querySelector('[data-refusal="fdi_year_missing"]'),
  ).toBeTruthy();
  expect(view.container.querySelector('[data-part="fdi-panel"]')).toBeNull();
});
