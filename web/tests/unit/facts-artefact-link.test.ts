// @vitest-environment jsdom
import { basePayload } from '../fixtures/layers';
import { contextAccepted } from '../../src/cards/PublicContextCard';
import {
  bindingProblem,
  fdiReferenceProblem,
  companyPointsProblem,
  fcSectionProblem,
  publishedFdiPoint,
} from '../../src/stage/layers/checks';
import { layerEntry } from '../../src/stage/layers/registry';
import { contextInput, contextPayloads } from '../fixtures/public-context';
import { createElement } from 'react';
import { cleanup, render } from '@testing-library/react';
import { afterEach } from 'vitest';
import { SourceChainDrawer } from '../../src/facts/SourceChainDrawer';
import { text, type Language } from '../../src/i18n';
import { describe, expect, it } from 'vitest';
import { createRegistry } from '../../src/facts/registry';
import type { RegistryInput } from '../../src/facts/types';
import { completeInput } from '../fixtures/facts';

export function artefactInput(
  input: RegistryInput = completeInput(),
): RegistryInput {
  const { tableName: _table, ...common } = input.lineages[0]!;
  void _table;
  return {
    ...input,
    tables: [],
    artefacts: [
      {
        releaseId: common.releaseId,
        path: 'artefacts/SYN-height.json',
        sha256: 'ab'.repeat(32),
      },
    ],
    lineages: [
      {
        ...common,
        link: 'artefact',
        artefactPath: 'artefacts/SYN-height.json',
        artefactSha256: 'ab'.repeat(32),
      },
    ],
  };
}

const plants: [string, string, (i: RegistryInput) => void][] = [
  ['absent artefact', 'artefact', (i) => Object.assign(i, { artefacts: [] })],
  [
    'stale hash',
    'artefact_hash',
    (i) => Object.assign(i.artefacts[0]!, { sha256: 'cd'.repeat(32) }),
  ],
  [
    'unknown kind',
    'link_kind',
    (i) => Object.assign(i.lineages[0]!, { link: 'unknown' }),
  ],
  [
    'artefact with table',
    'link_kind',
    (i) => Object.assign(i.lineages[0]!, { tableName: 'invented' }),
  ],
  [
    'blank method',
    'method',
    (i) => Object.assign(i.lineages[0]!, { method: '' }),
  ],
  [
    'blank version',
    'method_version',
    (i) => Object.assign(i.lineages[0]!, { methodVersion: '' }),
  ],
  [
    'foreign release',
    'release_identity',
    (i) => Object.assign(i.lineages[0]!, { releaseId: 'foreign' }),
  ],
  [
    'blank source hash',
    'hash',
    (i) => Object.assign(i.sources[0]!, { sha256: '' }),
  ],
  ['no release', 'release', (i) => Object.assign(i, { releases: [] })],
  [
    'artefact release mismatch',
    'release_identity',
    (i) => Object.assign(i.artefacts[0]!, { releaseId: 'foreign' }),
  ],
];
describe('manifest artefact chain', () => {
  it('retains the artefact ready union and snapshot, without any table', () => {
    const input = artefactInput();
    const registry = createRegistry(input);
    Object.assign(input, { artefacts: [] });
    const answer = registry.resolve(input.facts[0]!.fact.fact_id);
    expect(answer).toMatchObject({
      status: 'ready',
      link: 'artefact',
      artefact: { path: 'artefacts/SYN-height.json' },
    });
    expect(answer).not.toHaveProperty('table');
  });
  it.each(plants)('refuses %s as %s', (_name, missing, plant) => {
    const input = artefactInput();
    plant(input);
    expect(createRegistry(input).resolve(input.facts[0]!.fact.fact_id)).toEqual(
      { status: 'refused', missing },
    );
  });
  it.each(['artefactPath', 'artefactSha256'])(
    'refuses table with %s',
    (key) => {
      const input = completeInput();
      Object.assign(input.lineages[0]!, { [key]: 'invented' });
      expect(
        createRegistry(input).resolve(input.facts[0]!.fact.fact_id),
      ).toEqual({ status: 'refused', missing: 'link_kind' });
    },
  );
});

afterEach(cleanup);
it.each(['en', 'ar'] as const)(
  'renders the artefact union without a table in %s',
  (language) => {
    const input = artefactInput();
    const view = render(
      createElement(SourceChainDrawer, {
        factId: input.facts[0]!.fact.fact_id,
        registry: createRegistry(input),
        language,
        onClose: () => undefined,
      }),
    );
    expect(view.container.querySelector('[data-part="table"]')).toBeNull();
    expect(
      view.container.querySelector('[data-part="release"]'),
    ).not.toBeNull();
    expect(view.container.querySelector('[data-part="method"]')).not.toBeNull();
    expect(
      view.container.querySelector('[data-part="release"]')?.textContent,
    ).toBe(input.facts[0]!.fact.release_id);
  },
);
const drawerPlants: readonly (readonly [
  Language,
  'artefact' | 'artefact_hash' | 'link_kind',
  (i: RegistryInput) => void,
])[] = (['en', 'ar'] as const).flatMap((language) => [
  [
    language,
    'artefact',
    (i: RegistryInput) => Object.assign(i, { artefacts: [] }),
  ] as const,
  [
    language,
    'artefact_hash',
    (i: RegistryInput) =>
      Object.assign(i.artefacts[0]!, { sha256: 'cd'.repeat(32) }),
  ] as const,
  [
    language,
    'link_kind',
    (i: RegistryInput) => Object.assign(i.lineages[0]!, { link: 'unknown' }),
  ] as const,
]);
it.each(drawerPlants)('shows %s refusal for %s', (language, reason, plant) => {
  const input = artefactInput();
  plant(input);
  const view = render(
    createElement(SourceChainDrawer, {
      factId: input.facts[0]!.fact.fact_id,
      registry: createRegistry(input),
      language,
      onClose: () => undefined,
    }),
  );
  expect(
    view.container
      .querySelector('[data-missing]')
      ?.getAttribute('data-missing'),
  ).toBe(reason);
  expect(
    view.container.querySelector('[data-part="missing"]')?.textContent,
  ).toBe(text(language, `drawer.link.${reason}`));
});

it('refuses an artefact as the table source of a context card', () => {
  const input = contextInput();
  expect(contextAccepted(contextPayloads[0], createRegistry(input))).toBe(true);
  expect(
    contextAccepted(contextPayloads[0], createRegistry(artefactInput(input))),
  ).toBe(false);
});
it('refuses an artefact as a table-bound map slot with the existing reason', () => {
  const input = artefactInput();
  input.facts[0]!.metricKey = 'fdi_company';
  const registry = createRegistry(input);
  expect(registry.resolve(input.facts[0]!.fact.fact_id).status).toBe('ready');
  const entry = layerEntry('fdi_projects')!;
  expect(
    bindingProblem(
      entry,
      {
        feature_id: 'SYN-feature',
        geometry_kind: 'point',
        metric_key: 'fdi_company',
        provenance: 'public',
        subject: 'fdi_project',
        fact_id: input.facts[0]!.fact.fact_id,
      },
      registry,
    ),
  ).toBe('measure_on_named_feature');
});
it('refuses an artefact as a table-bound published field with the existing reason', () => {
  const input = artefactInput();
  input.facts[0]!.metricKey = 'fdi_field';
  input.facts[0]!.fact.unit = 'published_text';
  input.facts[0]!.fact.value = 'SYN-field-7';
  expect(
    fdiReferenceProblem(
      [
        {
          kind: 'reference',
          referenceKind: 'published_text',
          value: 'SYN-field-7',
          recordId: input.facts[0]!.fact.fact_id,
        },
      ],
      createRegistry(input),
    ),
  ).toBe('measure_on_named_feature');
});

function tableInput(tableName: string, metricKey: string) {
  const input = completeInput();
  Object.assign(input.tables[0]!, { tableName });
  Object.assign(input.lineages[0]!, { tableName });
  input.facts[0]!.metricKey = metricKey;
  return input;
}
it('refuses an artefact as a register-company point source', () => {
  const input = tableInput('pub_register_company', 'register_company_point');
  const id = input.facts[0]!.fact.fact_id;
  const payload = basePayload({
    layers: [
      {
        key: 'company_points',
        visible: true,
        source_chain_fact_id: id,
        source_id: 'src_alpha',
        features: [
          {
            feature_id: 'INVENTED-feature',
            geometry_kind: 'point',
            metric_key: 'register_company_point',
            provenance: 'public',
            subject: 'business',
            fact_id: id,
          },
        ],
      },
    ],
  });
  expect(companyPointsProblem(payload, createRegistry(input))).toBeNull();
  expect(
    companyPointsProblem(payload, createRegistry(artefactInput(input))),
  ).toBe('measure_on_named_feature');
});
it('refuses an artefact as the source of a tower legend count', () => {
  const input = tableInput('pub_register_company', 'firms_per_tower');
  const id = input.facts[0]!.fact.fact_id;
  const section = {
    direction: 'higher',
    companies: [],
    coverage_note_keys: [],
    breaks: [{ class_id: 'band_low', fact_id: id }],
  };
  const counts = [{ fact_id: id, year: '2025' }];
  expect(
    fcSectionProblem(section, createRegistry(input), counts),
  ).toMatchObject({ ok: true });
  expect(
    fcSectionProblem(section, createRegistry(artefactInput(input)), counts),
  ).toEqual({ ok: false, code: 'legend_count_unbound' });
});
it('withholds map placement when coordinate facts are artefact-linked', () => {
  const input = tableInput('fdi_projects', 'fdi_location');
  input.facts[0]!.fact.unit = 'decimal_degree';
  input.facts[0]!.fact.value = 1.25;
  const id = input.facts[0]!.fact.fact_id;
  const feature = {
    feature_id: 'INVENTED-feature',
    geometry_kind: 'point' as const,
    metric_key: 'fdi_company',
    provenance: 'public' as const,
    subject: 'fdi_project' as const,
    lon_fact_id: id,
    lat_fact_id: id,
    position: [1.25, 1.25] as [number, number],
  };
  expect(publishedFdiPoint(feature, createRegistry(input))).toBe(true);
  expect(publishedFdiPoint(feature, createRegistry(artefactInput(input)))).toBe(
    false,
  );
});
