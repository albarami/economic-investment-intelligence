import { describe, expect, it, vi } from 'vitest';
import { loadBasemapUrl, loadRegistryInput } from '../../src/api/release';
import { createRegistry } from '../../src/facts/registry';
import { completeInput } from '../fixtures/facts';

function transport() {
  const input = completeInput();
  const fact = input.facts[0]!.fact;
  // HTTP projections use the same existing registry types, no manufactured links.
  const release = {
    release_id: fact.release_id,
    release_kind: 'public_only',
    rules_version_id: 'INVENTED-rules',
    tables: input.tables,
    hour_keys: [],
    day_keys: [],
    month_keys: [],
    basemap_url: null as string | null,
  };
  const binding = input.facts[0]!;
  const chain = {
    fact_id: fact.fact_id,
    release_id: fact.release_id,
    lineage: input.lineages[0],
    sources: input.sources,
    binding: {
      metricKey: binding.metricKey,
      presentation: binding.presentation,
      qualifiers: {},
    },
  };
  const requests: string[] = [];
  vi.stubGlobal('fetch', async (path: string) => {
    requests.push(path);
    return {
      ok: true,
      json: async () => (path === '/api/release' ? release : chain),
    };
  });
  return { input, fact, release, chain, requests };
}

describe('mounted registry transport', () => {
  it('gets each chain from the two same-origin paths with its emitted binding', async () => {
    const { fact, requests } = transport();
    const input = await loadRegistryInput([fact]);
    expect(createRegistry(input).resolve(fact.fact_id).status).toBe('ready');
    expect(requests).toEqual([
      '/api/release',
      '/api/facts/' + fact.fact_id + '/lineage',
    ]);
    vi.unstubAllGlobals();
  });
  it.each([
    'unknown',
    'foreign',
    'metric',
    'table',
    'method',
    'version',
    'source',
    'publisher',
    'dataset',
    'licence',
    'date',
    'hash',
    'kind',
    'class',
    'fact',
    'fact_extra',
    'release_extra',
    'source_extra',
    'lineage_extra',
    'binding_extra',
  ] as const)(
    'refuses a %s violation without a guessed source or zero',
    async (cut) => {
      const { fact, chain, release } = transport();
      if (cut === 'fact_extra') Object.assign(fact, { extra: 'INVENTED' });
      if (cut === 'release_extra')
        Object.assign(release, { extra: 'INVENTED' });
      if (cut === 'source_extra')
        Object.assign(chain.sources[0]!, { extra: 'INVENTED' });
      if (cut === 'lineage_extra')
        Object.assign(chain.lineage!, { extra: 'INVENTED' });
      if (cut === 'binding_extra')
        Object.assign(chain.binding, { extra: 'INVENTED' });
      if (cut === 'unknown') Object.assign(chain, { unknown: 'INVENTED' });
      if (cut === 'foreign') chain.release_id = 'INVENTED-foreign';
      if (cut === 'metric') chain.binding.metricKey = '';
      if (cut === 'table')
        chain.lineage = { ...chain.lineage!, tableName: 'INVENTED-foreign' };
      if (cut === 'method') chain.lineage = { ...chain.lineage!, method: '' };
      if (cut === 'version')
        chain.lineage = { ...chain.lineage!, methodVersion: '' };
      if (cut === 'source') chain.sources = [];
      if (cut === 'publisher')
        chain.sources = chain.sources.map((s) => ({ ...s, publisher: '' }));
      if (cut === 'dataset')
        chain.sources = chain.sources.map((s) => ({ ...s, datasetOrPage: '' }));
      if (cut === 'licence')
        chain.sources = chain.sources.map((s) => ({
          ...s,
          licenceOrTerms: '',
        }));
      if (cut === 'date')
        chain.sources = chain.sources.map((s) => ({ ...s, retrievalDate: '' }));
      if (cut === 'hash')
        chain.sources = chain.sources.map((s) => ({ ...s, sha256: '' }));
      if (cut === 'kind')
        chain.sources = chain.sources.map((s) => ({
          ...s,
          kind: 'synthetic_feed',
        }));
      if (cut === 'class') fact.input_classes = ['synthetic'];
      if (cut === 'fact') fact.fact_id = '../INVENTED';
      void release;
      await expect(loadRegistryInput([fact])).rejects.toThrow();
      vi.unstubAllGlobals();
    },
  );
});

it.each(['lineage', 'source'] as const)(
  'refuses conflicting %s records with the same identity',
  async (kind) => {
    const { fact, chain, release } = transport();
    const second = { ...fact, fact_id: 'f_' + 'cd'.repeat(16) };
    vi.stubGlobal('fetch', async (path: string) => {
      const next = structuredClone(chain);
      if (path.includes(second.fact_id)) {
        next.fact_id = second.fact_id;
        if (kind === 'lineage')
          next.lineage = { ...next.lineage!, method: 'INVENTED-other' };
        else
          next.sources = next.sources.map((s) => ({
            ...s,
            sha256: 'ef'.repeat(32),
          }));
      }
      return {
        ok: true,
        json: async () => (path === '/api/release' ? release : next),
      };
    });
    await expect(loadRegistryInput([fact, second])).rejects.toThrow();
    vi.unstubAllGlobals();
  },
);

it('keeps row citations bound to each fact when a stored lineage is shared', async () => {
  const { fact, chain, release } = transport();
  const second = { ...fact, fact_id: 'f_' + 'cd'.repeat(16) };
  vi.stubGlobal('fetch', async (path: string) => {
    const next = structuredClone(chain);
    const other = path.includes(second.fact_id);
    next.fact_id = other ? second.fact_id : fact.fact_id;
    next.lineage = {
      ...next.lineage!,
      rowRetrievalDate: other ? '2026-02-02' : '2026-01-02',
      providerUpdatedOn: null,
    };
    return {
      ok: true,
      json: async () => (path === '/api/release' ? release : next),
    };
  });
  const registry = createRegistry(await loadRegistryInput([fact, second]));
  const left = registry.resolve(fact.fact_id);
  const right = registry.resolve(second.fact_id);
  expect(left.status === 'ready' && left.lineage.rowRetrievalDate).toBe(
    '2026-01-02',
  );
  expect(right.status === 'ready' && right.lineage.rowRetrievalDate).toBe(
    '2026-02-02',
  );
  vi.unstubAllGlobals();
});

describe('mounted basemap selection', () => {
  it.each([null, '/tiles/basemap.pmtiles'])(
    'accepts only the explicitly mounted selection: %s',
    async (url) => {
      const { release, requests } = transport();
      release.basemap_url = url;
      expect(await loadBasemapUrl()).toBe(url);
      expect(requests).toEqual(['/api/release']);
      vi.unstubAllGlobals();
    },
  );
  it.each([
    'https://invented.invalid/basemap.pmtiles',
    '//invented.invalid/basemap.pmtiles',
    '/tiles/other.pmtiles',
    '/tiles/../basemap.pmtiles',
    '',
    undefined,
    {},
  ])('refuses an unbound or malformed selection: %s', async (url) => {
    const { release } = transport();
    Object.assign(release, { basemap_url: url });
    await expect(loadBasemapUrl()).rejects.toThrow('chain_refused');
    vi.unstubAllGlobals();
  });
});
