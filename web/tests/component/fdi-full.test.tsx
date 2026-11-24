// @vitest-environment jsdom
/**
 * S3-T12 boxes 2 and 9 on the real API response: every contract field loaded
 * and shown on the card, the list and a map pick; collapsed credits on each
 * surface; capex and jobs labelled as announced estimates; numerals in chips.
 */
import { readFileSync } from 'node:fs';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { createRegistry } from '../../src/facts/registry';
import { text } from '../../src/i18n';
import { PublicLayers } from '../../src/stage/layers/PublicLayers';
import {
  FDI_CONTRACT_FIELDS,
  FDI_FACT_FIELDS,
  FDI_WORD_FIELDS,
} from '../../src/stage/layers/fdi';
import type {
  LayerFeature,
  LayerPayload,
} from '../../src/stage/layers/payload';
import { acceptPayload } from '../../src/stage/layers/refuse';
import { publishSelection } from '../../src/stage/layers/selection';
import { apiLayerCases } from '../fixtures/api-layer-cases';

const route = apiLayerCases().fdi!;
const FULL = 'fdi_abcdefabcdefabcd';
const DIRECT = 'fdi_ddcdefabcdefabcd';
// Contract field -> where the loaded feature carries it as a Fact chip.
const FACT_SLOT: Record<(typeof FDI_FACT_FIELDS)[number], keyof LayerFeature> =
  {
    capex_value: 'capex_fact_id',
    jobs: 'jobs_fact_id',
    announced: 'announced',
    lat: 'lat_fact_id',
    lng: 'lon_fact_id',
  };
// The page's caveat, word for word from TASKS.md S3-T12 boxes 2 and 9.
const CAVEAT_ESTIMATES = 'includes estimates of publicly announced projects';
const CAVEAT_COVERAGE = 'does not capture all investment projects';

afterEach(cleanup);

/** Column names of the document 03 section 7.3 `fdi_projects` row. */
function contractColumns(): string[] {
  const doc = readFileSync('../docs/03_DATA_CONTRACTS.md', 'utf8');
  const line = doc
    .split('\n')
    .find((row) => row.startsWith('| `fdi_projects` | `project_key` string'))!;
  const body = line.split('|')[2]!.split('No field is dropped')[0]!;
  const names: string[] = [];
  for (const [, token] of body.matchAll(/`([^`]+)`/g)) {
    if (token === 'fdi_projects' || names.includes(token!)) continue;
    if (/^[a-z][a-z0-9_]*[a-z0-9]$/.test(token!)) names.push(token!);
  }
  return names;
}

function payloadCopy(): LayerPayload {
  return structuredClone(route.body.payload);
}

function fullFeature(payload: LayerPayload): LayerFeature {
  return payload.layers[0]!.features.find((f) => f.feature_id === FULL)!;
}

function refusal(payload: LayerPayload): string {
  const verdict = acceptPayload(payload, createRegistry(route.registry));
  return verdict.ok ? 'accepted' : verdict.code;
}

function mount(language: 'en' | 'ar') {
  return render(
    <PublicLayers
      payload={route.body.payload}
      registry={createRegistry(route.registry)}
      language={language}
      onOpenChain={() => undefined}
    />,
  );
}

function withoutChips(scope: Element): string {
  const copy = scope.cloneNode(true) as Element;
  for (const chip of copy.querySelectorAll('[data-fact-chip]')) chip.remove();
  return copy.textContent ?? '';
}

describe('box 9: no field is dropped at loading', () => {
  it('the browser list equals the document 03 column list', () => {
    const columns = contractColumns();
    expect(columns).toHaveLength(51);
    expect([...FDI_CONTRACT_FIELDS].sort()).toEqual([...columns].sort());
    expect(FDI_CONTRACT_FIELDS).toHaveLength(
      FDI_WORD_FIELDS.length + FDI_FACT_FIELDS.length,
    );
  });

  it("the loaded object's keys equal the contract's field list", () => {
    expect(route.status).toBe(200);
    const verdict = acceptPayload(
      route.body.payload,
      createRegistry(route.registry),
    );
    expect(verdict.ok).toBe(true);
    if (!verdict.ok) return;
    const loaded = verdict.draw.layers
      .find((layer) => layer.key === 'fdi_projects')!
      .features.find((feature) => feature.feature_id === FULL)!;
    const keys = new Set(Object.keys(loaded.field_segments ?? {}));
    for (const [field, slot] of Object.entries(FACT_SLOT))
      if (loaded[slot]) keys.add(field);
    expect([...keys].sort()).toEqual([...contractColumns()].sort());
  });
});

for (const language of ['en', 'ar'] as const) {
  describe(`boxes 2 and 9 on screen in ${language}`, () => {
    it('shows every field on the card, in the list and on a map pick', () => {
      const view = mount(language);
      const unstated = text(language, 'layers.fdi.unstated');
      const scopes = () => [
        view.container.querySelector(`[data-project-card]`)!,
        view.container.querySelector(`[data-project="${FULL}"]`)!,
      ];
      act(() => publishSelection(FULL));
      expect(scopes()[0]!.getAttribute('data-project-card')).toBe(FULL);
      for (const scope of scopes()) {
        for (const field of FDI_WORD_FIELDS) {
          const cell = scope.querySelector(`[data-field="${field}"]`);
          expect(cell, field).toBeTruthy();
          expect(cell!.textContent, field).not.toBe(unstated);
        }
        for (const field of ['capex_value', 'jobs', 'lat', 'lon'])
          expect(
            scope.querySelector(
              `[data-field="${field}"] [data-fact-chip="value"]`,
            ),
            field,
          ).toBeTruthy();
        expect(
          scope.querySelector(
            '[data-field="announced"] [data-fact-chip="reference"]',
          ),
        ).toBeTruthy();
      }
      // A map pick of another project moves the card to it in full.
      act(() => publishSelection(DIRECT));
      const card = view.container.querySelector('[data-project-card]')!;
      expect(card.getAttribute('data-project-card')).toBe(DIRECT);
      for (const field of FDI_WORD_FIELDS)
        expect(
          card.querySelector(`[data-field="${field}"]`),
          field,
        ).toBeTruthy();
    });

    it('carries collapsed credits on the card, the list and the map legend', () => {
      const view = mount(language);
      const credits = route.body.payload.credits!;
      for (const surface of ['card', 'list', 'legend']) {
        const box = view.container.querySelector(
          `details[data-part="fdi-credits"][data-surface="${surface}"]`,
        )!;
        expect(box, surface).toBeTruthy();
        expect(box.hasAttribute('open'), surface).toBe(false);
        expect(box.querySelector('summary')!.textContent).toBe(
          text(language, 'layers.fdi.credits'),
        );
        for (const [field, key] of [
          ['publisher', 'layers.fdi.credit.publisher'],
          ['gatherer', 'layers.fdi.credit.gatherer'],
          ['read_on', 'layers.fdi.credit.read_on'],
        ] as const) {
          expect(
            box.querySelector(`[data-credit-label="${field}"]`)?.textContent,
            `${surface} ${field}`,
          ).toBe(text(language, key));
        }
        expect(
          box.querySelector('[data-credit-field="publisher"]')?.textContent,
        ).toBe(
          credits.publisher
            .map((s) => (s.kind === 'plain' ? s.text : s.value))
            .join(''),
        );
        expect(
          box.querySelector('[data-credit-field="gatherer"]')?.textContent,
        ).toBe(
          credits.gatherer
            .map((s) => (s.kind === 'plain' ? s.text : s.value))
            .join(''),
        );
        expect(
          box.querySelector(
            '[data-credit-field="read_on"] [data-fact-chip="reference"]',
          )?.textContent,
        ).toContain(credits.read_on.slice(0, 4));
        const link = box.querySelector('a[data-credit-field="dashboard"]')!;
        expect(link.getAttribute('href')).toBe(credits.dashboard_url);
        expect(link.textContent).toBe(text(language, 'layers.fdi.dashboard'));
        expect(
          box.querySelector('[data-caveat="fdi_estimates_sentence"]')
            ?.textContent,
        ).toBe(text(language, 'layers.fdi.caveat.estimates'));
        expect(
          box.querySelector('[data-caveat="fdi_coverage_sentence"]')
            ?.textContent,
        ).toBe(text(language, 'layers.fdi.caveat.coverage'));
      }
      // The legend sits with the map's own count chips.
      expect(
        view.container.querySelector(
          '[data-part="fdi-legend"] > [data-part="fdi-credits"]',
        ),
      ).toBeTruthy();
    });

    it('labels each capex and jobs value as an announced estimate', () => {
      const view = mount(language);
      const label = text(language, 'layers.fdi.announced');
      const values = view.container.querySelectorAll(
        '[data-fdi-fields] [data-field="capex_value"], [data-fdi-fields] [data-field="jobs"]',
      );
      let withValue = 0;
      for (const slot of values) {
        if (!slot.querySelector('[data-fact-chip="value"]')) continue;
        withValue += 1;
        expect(
          slot.querySelector('[data-label="announced"]')?.textContent,
        ).toBe(label);
      }
      // Card plus three list rows hold both values (one row publishes none).
      expect(withValue).toBe(8);
    });

    for (const [metric, slot] of [
      ['fdi_capex', 'capex_fact_id'],
      ['fdi_jobs', 'jobs_fact_id'],
    ] as const) {
      it(`a pick whose main metric is ${metric} shows no unlabelled estimate chip`, () => {
        // cf1 of S3-B7: the generic feature panel repeated the main metric's
        // value chip without the announced-estimate label.
        const payload = payloadCopy();
        const feature = fullFeature(payload);
        feature.metric_key = metric;
        feature.fact_id = feature[slot] as string;
        expect(feature.fact_id, slot).toBeTruthy();
        expect(refusal(payload)).toBe('accepted');
        const view = render(
          <PublicLayers
            payload={payload}
            registry={createRegistry(route.registry)}
            language={language}
            onOpenChain={() => undefined}
          />,
        );
        act(() => publishSelection(FULL));
        expect(
          view.container
            .querySelector('[data-project-card]')!
            .getAttribute('data-project-card'),
        ).toBe(FULL);
        const label = text(language, 'layers.fdi.announced');
        const chips = view.container.querySelectorAll(
          `[data-fact-chip="value"][data-fact-id="${feature.fact_id}"]`,
        );
        expect(chips.length).toBeGreaterThan(0);
        for (const chip of chips) {
          const cell = chip.closest('[data-field]');
          expect(cell, 'value chip outside a field slot').toBeTruthy();
          expect(
            cell!.querySelector('[data-label="announced"]')?.textContent,
          ).toBe(label);
        }
        expect(
          view.container.querySelector(
            '[data-part="feature-panel"][data-layer="fdi_projects"] [data-fact-chip="value"]',
          ),
        ).toBeNull();
      });
    }

    it('keeps every numeral of the FDI panel in the Fact chip family', () => {
      const view = mount(language);
      const panel = view.container.querySelector('[data-part="fdi-panel"]')!;
      expect(withoutChips(panel)).not.toMatch(/[0-9٠-٩]/);
    });
  });
}

it('the English caveat is the page caveat word for word', () => {
  expect(text('en', 'layers.fdi.caveat.estimates')).toBe(CAVEAT_ESTIMATES);
  expect(text('en', 'layers.fdi.caveat.coverage')).toBe(CAVEAT_COVERAGE);
  expect(text('ar', 'layers.fdi.caveat.estimates')).not.toBe(CAVEAT_ESTIMATES);
});

describe('plants: each changes one input of the real response', () => {
  it('accepts the unplanted response', () => {
    expect(refusal(payloadCopy())).toBe('accepted');
  });

  it('a field the browser does not carry is refused, never dropped', () => {
    const payload = payloadCopy();
    fullFeature(payload).field_segments = {
      ...fullFeature(payload).field_segments,
      INVENTED_column: [{ kind: 'plain', text: 'INVENTED' }],
    } as LayerFeature['field_segments'];
    expect(refusal(payload)).toBe('measure_on_named_feature');
  });

  it('an estimate without its announced-estimate caveat is refused', () => {
    const payload = payloadCopy();
    fullFeature(payload).caveat_keys = [];
    expect(refusal(payload)).toBe('announced_estimate_unlabelled');
  });

  for (const field of [
    'publisher',
    'gatherer',
    'read_on',
    'dashboard_url',
  ] as const) {
    it(`a missing credit (${field}) is refused`, () => {
      const payload = payloadCopy();
      const credits = payload.credits!;
      if (field === 'read_on' || field === 'dashboard_url') credits[field] = '';
      else credits[field] = [];
      expect(refusal(payload)).toBe('missing_attribution');
    });
  }

  it('absent credits are refused', () => {
    const payload = payloadCopy();
    delete payload.credits;
    expect(refusal(payload)).toBe('missing_attribution');
  });

  it('a numeral outside a Fact chip in a field is refused', () => {
    const payload = payloadCopy();
    fullFeature(payload).field_segments = {
      ...fullFeature(payload).field_segments,
      sector: [{ kind: 'plain', text: 'INVENTED sector 7' }],
    };
    expect(refusal(payload)).toBe('numeral_in_plain_segment');
  });

  it('a numeral outside a Fact chip in a credit is refused', () => {
    const payload = payloadCopy();
    payload.credits!.gatherer = [{ kind: 'plain', text: 'INVENTED 7' }];
    expect(refusal(payload)).toBe('numeral_in_plain_segment');
  });
});
