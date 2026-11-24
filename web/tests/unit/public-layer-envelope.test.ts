/**
 * S3-T12, design amendment 1: the one closed Public-layer NO_DATA envelope.
 * Each negative case changes one field of a valid mounted body.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ACCIDENT_HTTP } from '../fixtures/accident-scene';
import { composeLayers, loadPublicLayer } from '../../src/api/public-layer';

afterEach(() => {
  vi.unstubAllGlobals();
});

function serve(body: unknown) {
  vi.stubGlobal('fetch', async (path: string) => ({
    ok: true,
    status: 200,
    json: async () =>
      structuredClone(
        path === '/api/release'
          ? ACCIDENT_HTTP.release
          : path.startsWith('/api/facts/')
            ? ACCIDENT_HTTP.chains[path.split('/')[3]!]
            : body,
      ),
  }));
}

const missing = ACCIDENT_HTTP.geography_missing as unknown as Record<
  string,
  unknown
>;

describe('public-layer envelope', () => {
  it('returns the closed reason of a NO_DATA body', async () => {
    serve(missing);
    const result = await loadPublicLayer('accidents');
    expect([result.status, result.reason]).toEqual([
      'NO_DATA',
      'accident_geography_missing',
    ]);
  });

  it('keeps the four-key body with no reason', async () => {
    serve(ACCIDENT_HTTP.accidents);
    const result = await loadPublicLayer('accidents');
    expect([result.status, result.reason]).toEqual(['ok', null]);
  });

  it.each([
    ['a reason on an ok body', { status: 'ok' }],
    ['an unknown reason', { reason: 'accident_zero' }],
    ['a reason with a fact', { facts: ACCIDENT_HTTP.accidents.facts }],
    ['a reason with a feature', { payload: ACCIDENT_HTTP.accidents.payload }],
    ['a reason with no layers', { payload: { sources: [] } }],
    ['an extra key', { verdict: 'INVENTED' }],
  ])('refuses %s', async (_name, change) => {
    serve({ ...missing, ...change });
    await expect(loadPublicLayer('accidents')).rejects.toThrow(
      /^layer_refused$/,
    );
  });

  // The four-key body has no reason checks, so these guards stand alone.
  it.each([
    ['an unknown status', { status: 'empty' }],
    ['facts not a list', { facts: {} }],
  ])('refuses a four-key body with %s', async (_name, change) => {
    serve({ ...ACCIDENT_HTTP.accidents, ...change });
    await expect(loadPublicLayer('accidents')).rejects.toThrow(
      /^layer_refused$/,
    );
  });

  it('refuses a body that is not an object', async () => {
    serve(null);
    await expect(loadPublicLayer('accidents')).rejects.toThrow(
      /^layer_refused$/,
    );
  });
});

describe('layer composition', () => {
  async function load(body: unknown) {
    serve(body);
    return loadPublicLayer('accidents');
  }

  it('keeps the chosen reason and draws only the layers with data', async () => {
    const chosen = await load(missing);
    const rail = await load(ACCIDENT_HTTP.rail_plan);
    const joined = composeLayers([chosen, rail]);
    expect([joined.status, joined.reason]).toEqual([
      'NO_DATA',
      'accident_geography_missing',
    ]);
    expect(joined.payload.layers.map((layer) => layer.key)).toEqual([
      'rail_plan',
    ]);
    expect(joined.input.facts.map((row) => row.fact.fact_id)).toEqual(
      ACCIDENT_HTTP.rail_plan.facts.map((fact) => fact.fact_id),
    );
  });

  it('returns a single layer unchanged', async () => {
    const chosen = await load(missing);
    expect(composeLayers([chosen])).toBe(chosen);
  });

  it('refuses two releases', async () => {
    const chosen = await load(ACCIDENT_HTTP.accidents);
    const rail = await load(ACCIDENT_HTTP.rail_plan);
    const other = {
      ...rail,
      input: {
        ...rail.input,
        releases: [{ releaseId: 'INVENTED-other-release' }],
      },
    };
    expect(() => composeLayers([chosen, other])).toThrow(/^chain_conflict$/);
  });

  it('refuses one source id with two contents', async () => {
    const chosen = await load(ACCIDENT_HTTP.accidents);
    const rail = await load(ACCIDENT_HTTP.rail_plan);
    const source = rail.payload.sources[0]!;
    const other = {
      ...rail,
      payload: {
        ...rail.payload,
        sources: [{ ...source, retrievalDate: '2026-01-03' }],
      },
    };
    expect(() => composeLayers([chosen, other])).toThrow(/^chain_conflict$/);
  });

  it('refuses an empty list', () => {
    expect(() => composeLayers([])).toThrow(/^layer_refused$/);
  });
});
