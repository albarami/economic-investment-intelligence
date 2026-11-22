import * as registryModule from '../../src/facts/registry';
import { describe, expect, it, vi } from 'vitest';
import { loadBasemapUrl, loadRegistryInput } from '../../src/api/release';
import { createRegistry } from '../../src/facts/registry';
import { completeInput, tableWire } from '../fixtures/facts';

function transport() {
  const input = completeInput();
  const fact = input.facts[0]!.fact;
  // HTTP projections use the same existing registry types, no manufactured links.
  const release = {
    release_id: fact.release_id,
    release_kind: 'public_only',
    rules_version_id: 'INVENTED-rules',
    tables: input.tables,
    artefacts: input.artefacts,
    hour_keys: [],
    day_keys: [],
    month_keys: [],
    basemap_url: null as string | null,
  };
  const binding = input.facts[0]!;
  const chain = {
    fact_id: fact.fact_id,
    release_id: fact.release_id,
    lineage: tableWire(input.lineages[0]!),
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

// D0 new transport cases; table wire fixtures above retain their closed shape.
function artefactTransport() {
  const held = transport();
  const { tableName: _table, ...common } = held.chain.lineage!;
  void _table;
  const lineage = {
    ...common,
    link: 'artefact',
    artefactPath: 'artefacts/SYN-height.json',
    artefactSha256: 'ab'.repeat(32),
  };
  const artefact = {
    releaseId: held.fact.release_id,
    path: lineage.artefactPath,
    sha256: lineage.artefactSha256,
  };
  Object.assign(held.chain, { lineage });
  Object.assign(held.release, { artefacts: [artefact] });
  return { ...held, lineage, artefact };
}
it('adapts the exact legacy table wire shape in the decoder only', async () => {
  const { fact } = transport();
  const input = await loadRegistryInput([fact]);
  expect(input.lineages[0]!.link).toBe('table');
  expect(input.artefacts).toEqual([]);
  vi.unstubAllGlobals();
});
it('decodes and retains the trusted release artefact inventory', async () => {
  const { fact, artefact } = artefactTransport();
  const input = await loadRegistryInput([fact]);
  expect(input.artefacts).toEqual([artefact]);
  expect(createRegistry(input).resolve(fact.fact_id)).toMatchObject({
    status: 'ready',
    link: 'artefact',
    artefact,
  });
  vi.unstubAllGlobals();
});
it.each([
  'unknown',
  'table-link',
  'missing',
  'hash',
  'mixed',
  'inventory-release',
  'inventory-hash',
  'inventory-path',
  'inventory-extra',
])(
  'refuses the independent %s link plant with chain_refused',
  async (plant) => {
    const { fact, chain, release, lineage, artefact } = artefactTransport();
    if (plant === 'unknown') lineage.link = 'unknown';
    if (plant === 'table-link') {
      const held = transport();
      Object.assign(held.chain.lineage!, { link: 'table' });
      await expect(loadRegistryInput([held.fact])).rejects.toThrow(
        /^chain_refused$/,
      );
      vi.unstubAllGlobals();
      return;
    }
    if (plant === 'missing') Object.assign(release, { artefacts: [] });
    if (plant === 'hash') lineage.artefactSha256 = 'cd'.repeat(32);
    if (plant === 'mixed')
      Object.assign(lineage, { tableName: 'sample_counts' });
    if (plant === 'inventory-release') artefact.releaseId = 'foreign';
    if (plant === 'inventory-hash') artefact.sha256 = 'not-a-hash';
    if (plant === 'inventory-path') artefact.path = '';
    if (plant === 'inventory-extra')
      Object.assign(artefact, { extra: 'INVENTED' });
    void chain;
    await expect(loadRegistryInput([fact])).rejects.toThrow(/^chain_refused$/);
    vi.unstubAllGlobals();
  },
);
it('refuses an artefact lineage conflict rather than overwriting it', async () => {
  const { fact, chain, release } = artefactTransport();
  const second = { ...fact, fact_id: 'f_' + 'cd'.repeat(16) };
  vi.stubGlobal('fetch', async (path: string) => {
    const next = structuredClone(chain);
    if (path.includes(second.fact_id)) {
      next.fact_id = second.fact_id;
      Object.assign(next.lineage!, { methodVersion: 'v2' });
    }
    return {
      ok: true,
      json: async () => (path === '/api/release' ? release : next),
    };
  });
  await expect(loadRegistryInput([fact, second])).rejects.toThrow(
    /^chain_refused$/,
  );
  vi.unstubAllGlobals();
});

it.each(['missing', 'hash'])(
  'the decoder refuses %s before constructing a registry',
  async (plant) => {
    const { fact, release, lineage } = artefactTransport();
    const spy = vi.spyOn(registryModule, 'createRegistry');
    try {
      if (plant === 'missing') Object.assign(release, { artefacts: [] });
      else lineage.artefactSha256 = 'cd'.repeat(32);
      await expect(loadRegistryInput([fact])).rejects.toThrow(
        /^chain_refused$/,
      );
      expect(spy).not.toHaveBeenCalled();
    } finally {
      spy.mockRestore();
      vi.unstubAllGlobals();
    }
  },
);
it.each(['release', 'hash'])(
  'validates inventory %s even without any fact',
  async (plant) => {
    const { artefact } = artefactTransport();
    if (plant === 'release') artefact.releaseId = 'foreign';
    else artefact.sha256 = 'not-a-hash';
    await expect(loadBasemapUrl()).rejects.toThrow(/^chain_refused$/);
    vi.unstubAllGlobals();
  },
);
it('refuses table-only citation fields on an artefact lineage', async () => {
  const { fact, lineage } = artefactTransport();
  Object.assign(lineage, {
    rowRetrievalDate: '2026-01-02',
    providerUpdatedOn: null,
  });
  await expect(loadRegistryInput([fact])).rejects.toThrow(/^chain_refused$/);
  vi.unstubAllGlobals();
});

it('compares artefact identity in the shared-lineage conflict check', async () => {
  const { fact, chain, release, artefact } = artefactTransport();
  const second = { ...fact, fact_id: 'f_' + 'cd'.repeat(16) };
  const otherPath = 'artefacts/SYN-other-height.json';
  Object.assign(release, {
    artefacts: [artefact, { ...artefact, path: otherPath }],
  });
  vi.stubGlobal('fetch', async (path: string) => {
    const next = structuredClone(chain);
    if (path.includes(second.fact_id)) {
      next.fact_id = second.fact_id;
      Object.assign(next.lineage!, { artefactPath: otherPath });
    }
    return {
      ok: true,
      json: async () => (path === '/api/release' ? release : next),
    };
  });
  const spy = vi.spyOn(registryModule, 'createRegistry');
  try {
    await expect(loadRegistryInput([fact, second])).rejects.toThrow(
      /^chain_refused$/,
    );
    expect(spy).not.toHaveBeenCalled();
  } finally {
    spy.mockRestore();
    vi.unstubAllGlobals();
  }
});
