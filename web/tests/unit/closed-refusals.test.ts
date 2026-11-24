import { readFileSync } from 'node:fs';
import { afterEach, expect, it, vi } from 'vitest';
import { assets, verifyAssets } from '../../scripts/photoreal-assets.mjs';
import { loadPublicLayer } from '../../src/api/public-layer';
import { loadBasemapUrl } from '../../src/api/release';
import { loadBusyness, runPublicStory } from '../../src/api/public-opening';

const errorBody = {
  error: {
    code: 'INTERNAL',
    message_key: 'chain_refused',
    error_id: 'INVENTED',
  },
};
afterEach(() => vi.unstubAllGlobals());

// D32 is the pytest row: operations health has no browser/catalogue state.
it.each([
  [
    'D33',
    () => verifyAssets(() => new Uint8Array()),
    {
      code: 'unqualified-asset',
      message_key: 'unqualified-asset:draco_wasm_wrapper.js',
    },
  ],
  [
    'D34',
    () => loadPublicLayer('fc_firms_per_tower'),
    {
      http_status: 200,
      code: 'NO_DATA',
      message_key: 'missing_input',
      catalogue_key: 'layers.not_ranked.missing_input',
    },
  ],
  [
    'D35',
    () => loadBasemapUrl(),
    {
      http_status: 500,
      code: 'INTERNAL',
      message_key: 'chain_refused',
      catalogue_key: 'layers.refused.registry',
    },
  ],
  [
    'D36',
    () => loadBusyness('INVENTED'),
    {
      http_status: 500,
      code: 'INTERNAL',
      message_key: 'chain_refused',
      catalogue_key: 'layers.refused.registry',
    },
  ],
] as const)('%s retains its exact closed reason', async (row, call, state) => {
  vi.stubGlobal('fetch', async () =>
    Response.json(
      row === 'D34'
        ? { status: 'NO_DATA', reason: 'missing_input', facts: [] }
        : errorBody,
      { status: row === 'D34' ? 200 : 500 },
    ),
  );
  await expect(Promise.resolve().then(call)).rejects.toMatchObject(
    row === 'D33' ? state : { state },
  );
});

it.each([422, 403, 404, 429, 503, 504])(
  'keeps the HTTP status %s and closed code',
  async (status) => {
    vi.stubGlobal('fetch', async () => Response.json(errorBody, { status }));
    await expect(loadPublicLayer('parcels')).rejects.toMatchObject({
      state: {
        http_status: status,
        code: 'INTERNAL',
        message_key: 'chain_refused',
        catalogue_key: 'layers.refused.registry',
      },
    });
  },
);

it.each(['NO_DATA', 'SUPPRESSED'])(
  'D36 retains %s without releasing a story',
  async (status) => {
    vi.stubGlobal('fetch', async () =>
      Response.json({ status, reason: 'missing_input', facts: [] }),
    );
    await expect(
      runPublicStory('INVENTED', 'en', { shape_id: 'INVENTED' }),
    ).rejects.toMatchObject({
      state: {
        http_status: 200,
        code: status,
        message_key: 'missing_input',
        catalogue_key: 'layers.not_ranked.missing_input',
      },
    });
  },
);

it('D36 keeps a NO_DATA busyness card rather than failing the story', async () => {
  vi.stubGlobal('fetch', async () =>
    Response.json({
      tool: 'venue_busyness',
      status: 'NO_DATA',
      facts: [],
      payload: null,
      caveat_keys: ['missing_input'],
    }),
  );
  const result = await loadBusyness('INVENTED');
  expect(result.cards).toEqual([
    { family: 'venue_busyness', state: 'no_data', reason: 'missing_input' },
  ]);
  expect(result).toMatchObject({
    refusal: {
      http_status: 200,
      code: 'NO_DATA',
      message_key: 'missing_input',
      catalogue_key: 'layers.not_ranked.missing_input',
    },
  });
});

it('D33 identifies each corrupted asset without a package path', () => {
  for (const asset of assets) {
    let failure;
    try {
      verifyAssets((relative) =>
        relative === asset.path
          ? new Uint8Array()
          : readFileSync(
              new URL('../../node_modules/' + relative, import.meta.url),
            ),
      );
    } catch (error) {
      failure = error;
    }
    expect(failure).toMatchObject({
      code: 'unqualified-asset',
      message_key: 'unqualified-asset:' + asset.path.split('/').at(-1),
    });
  }
});

it('D33 printed diagnostics identify the failed decoder', () => {
  expect(() => verifyAssets(() => new Uint8Array())).toThrow(
    /^unqualified-asset:draco_wasm_wrapper\.js$/,
  );
});
