// @vitest-environment jsdom
import { spawnSync } from 'node:child_process';
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';

import {
  PublicContextCard,
  contextAccepted,
  type ContextPayload,
} from '../../src/cards/PublicContextCard';
import { loadRegistryInput } from '../../src/api/release';
import { createRegistry } from '../../src/facts/registry';
import type { Fact, RegistryInput } from '../../src/facts/types';
import { FactChip } from '../../src/facts/FactChip';
import { SourceChainDrawer } from '../../src/facts/SourceChainDrawer';
import { acceptPayload } from '../../src/stage/layers/refuse';
import type { LayerPayload } from '../../src/stage/layers/payload';

let response: {
  release: unknown;
  body: { facts: Fact[]; payload: LayerPayload };
  chains: Record<string, unknown>;
  cards: Record<
    string,
    { facts: Fact[]; payload: { entries: Record<string, string | null>[] } }
  >;
};
let input: RegistryInput;
let cardsInput: RegistryInput;
beforeAll(async () => {
  const run = spawnSync(
    'uv',
    [
      'run',
      '--locked',
      'python',
      '-m',
      'pytest',
      'product/tests/test_mounted_release_http.py::test_transport_projection_record',
      '-q',
      '-s',
    ],
    { cwd: '..', encoding: 'utf8', env: { ...process.env, UV_OFFLINE: '1' } },
  );
  expect(run.status, run.stderr + run.stdout).toBe(0);
  const line = run.stdout
    .split('\n')
    .find((line) => line.startsWith('MOUNTED_PROJECTION='));
  expect(line).toBeTruthy();
  response = JSON.parse(line!.slice('MOUNTED_PROJECTION='.length));
  vi.stubGlobal('fetch', async (path: string) => ({
    ok: true,
    json: async () =>
      path === '/api/release'
        ? response.release
        : response.chains[path.split('/')[3]!],
  }));
  input = await loadRegistryInput(response.body.facts);
  cardsInput = await loadRegistryInput(
    Object.values(response.cards).flatMap((card) => card.facts),
  );
  vi.unstubAllGlobals();
}, 60_000);
afterEach(cleanup);

for (const language of ['en', 'ar'] as const) {
  for (const theme of ['dark', 'light'] as const) {
    it(`passes actual HTTP projections into chips, layer acceptance and drawer in ${language}/${theme}`, () => {
      const registry = createRegistry(input);
      const factId = response.body.facts[0]!.fact_id;
      expect(acceptPayload(response.body.payload, registry).ok).toBe(true);
      const opened: string[] = [];
      const view = render(
        <div
          lang={language}
          dir={language === 'ar' ? 'rtl' : 'ltr'}
          data-theme={theme}
        >
          <FactChip
            factId={factId}
            registry={registry}
            variant="value"
            size="standard"
            language={language}
            onOpen={(id) => opened.push(id)}
          />
          <SourceChainDrawer
            factId={factId}
            registry={registry}
            language={language}
            onClose={() => undefined}
          />
        </div>,
      );
      const chip = view.container.querySelector('[data-fact-chip="value"]')!;
      fireEvent.click(chip);
      expect(opened).toEqual([factId]);
      expect(
        view.container
          .querySelector('[role="dialog"]')
          ?.getAttribute('data-fact-id'),
      ).toBe(factId);
      const clone = view.container.cloneNode(true) as HTMLElement;
      clone
        .querySelectorAll('[data-fact-chip]')
        .forEach((node) => node.remove());
      expect(clone.textContent).not.toMatch(/\p{Nd}/u);
    });
  }
}

const cuts = {
  fact: (i: RegistryInput) => ({ ...i, facts: [] }),
  release: (i: RegistryInput) => ({ ...i, releases: [] }),
  table: (i: RegistryInput) => ({ ...i, tables: [] }),
  lineage: (i: RegistryInput) => ({ ...i, lineages: [] }),
  method: (i: RegistryInput) => ({
    ...i,
    lineages: i.lineages.map((row) => ({ ...row, method: '' })),
  }),
  method_version: (i: RegistryInput) => ({
    ...i,
    lineages: i.lineages.map((row) => ({ ...row, methodVersion: '' })),
  }),
  source: (i: RegistryInput) => ({ ...i, sources: [] }),
  publisher: (i: RegistryInput) => ({
    ...i,
    sources: i.sources.map((row) => ({ ...row, publisher: '' })),
  }),
  dataset_or_page: (i: RegistryInput) => ({
    ...i,
    sources: i.sources.map((row) => ({ ...row, datasetOrPage: '' })),
  }),
  licence_or_terms: (i: RegistryInput) => ({
    ...i,
    sources: i.sources.map((row) => ({ ...row, licenceOrTerms: '' })),
  }),
  retrieval_date: (i: RegistryInput) => ({
    ...i,
    sources: i.sources.map((row) => ({ ...row, retrievalDate: '' })),
  }),
  hash: (i: RegistryInput) => ({
    ...i,
    sources: i.sources.map((row) => ({ ...row, sha256: '' })),
  }),
  release_identity: (i: RegistryInput) => ({
    ...i,
    releases: [{ releaseId: 'INVENTED-foreign' }],
  }),
  input_class_source: (i: RegistryInput) => ({
    ...i,
    lineages: i.lineages.map((row) => ({ ...row, inputClasses: [] })),
  }),
  source_kind: (i: RegistryInput): RegistryInput => ({
    ...i,
    sources: i.sources.map((row) => ({ ...row, kind: 'synthetic_feed' })),
  }),
  companion: (i: RegistryInput): RegistryInput => ({
    ...i,
    facts: i.facts.map((binding) => ({ ...binding, presentation: 'forecast' })),
  }),
} satisfies Record<
  import('../../src/facts/types').MissingLink,
  (i: RegistryInput) => RegistryInput
>;
for (const language of ['en', 'ar'] as const) {
  for (const theme of ['dark', 'light'] as const) {
    for (const [link, cut] of Object.entries(cuts)) {
      it(`refuses ${link}, its value and dependent geometry in ${language}/${theme}`, () => {
        const registry = createRegistry(cut(input));
        const factId = response.body.facts[0]!.fact_id;
        expect(acceptPayload(response.body.payload, registry).ok).toBe(false);
        const view = render(
          <div lang={language} data-theme={theme}>
            <FactChip
              factId={factId}
              registry={registry}
              variant="value"
              size="standard"
              language={language}
              onOpen={() => undefined}
            />
            <SourceChainDrawer
              factId={factId}
              registry={registry}
              language={language}
              onClose={() => undefined}
            />
          </div>,
        );
        expect(
          view.container.querySelector('[data-fact-chip="value"] bdi.chip-num'),
        ).toBeNull();
        expect(view.container.textContent).not.toMatch(/\p{Nd}/u);
      });
    }
  }
}

for (const language of ['en', 'ar'] as const) {
  for (const theme of ['dark', 'light'] as const) {
    it(`renders all three cards from their real HTTP envelopes in ${language}/${theme}`, () => {
      const registry = createRegistry(cardsInput);
      const night = response.cards.night_lights!.facts[0]!;
      const venue = response.cards.venue_busyness!.payload.entries.find(
        (entry) => entry.fact_id,
      )!;
      const population = response.cards.population_age_sex!.payload.entries[0]!;
      const payloads: ContextPayload[] = [
        { family: 'night_lights', state: 'ready', factId: night.fact_id },
        {
          family: 'venue_busyness',
          state: 'ready',
          factId: venue.fact_id!,
          retrievedOn: venue.retrieved_on!,
          providerUpdatedOn: venue.provider_updated_on!,
          day: venue.weekday as 'monday',
          hour: venue.hour!,
        },
        {
          family: 'population_age_sex',
          state: 'ready',
          factId: population.fact_id!,
          ageBand: population.age_band!,
          sex: population.sex as 'female' | 'male',
        },
      ];
      for (const payload of payloads)
        expect(contextAccepted(payload, registry)).toBe(true);
      const view = render(
        <div data-theme={theme}>
          {payloads.map((payload) => (
            <PublicContextCard
              key={payload.family}
              payload={payload}
              registry={registry}
              language={language}
              onOpen={() => undefined}
            />
          ))}
        </div>,
      );
      expect(view.container.querySelectorAll('article')).toHaveLength(3);
      expect(
        view.container.querySelectorAll('[data-fact-chip="value"]'),
      ).toHaveLength(3);
      const clone = view.container.cloneNode(true) as HTMLElement;
      clone
        .querySelectorAll('[data-fact-chip]')
        .forEach((node) => node.remove());
      expect(clone.textContent).not.toMatch(/\p{Nd}/u);
    });
  }
}
