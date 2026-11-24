import { afterEach, expect, it, vi } from 'vitest';
import {
  outcomeRefusal,
  readApiBody,
  refusalState,
  ApiRefusal,
} from '../../src/api/refusal';
import { loadPublicLayer } from '../../src/api/public-layer';
import { loadBasemapUrl } from '../../src/api/release';
import { loadBusyness } from '../../src/api/public-opening';
import { catalogue } from '../../src/brief/catalogue';
import { runPublicStory } from '../../src/api/public-opening';
import { contextInput } from '../fixtures/public-context';

const httpError = {
  error: {
    code: 'INTERNAL',
    message_key: 'chain_refused',
    error_id: 'INVENTED',
  },
};
const fixtures = [
  httpError,
  { status: 'NO_DATA', reason: 'missing_input', facts: [] },
  {
    tool: 'venue_busyness',
    status: 'NO_DATA',
    facts: [],
    payload: null,
    caveat_keys: ['missing_input'],
  },
  { status: 'SUPPRESSED', reason_key: 'source_missing', facts: [] },
  {
    status: 'NO_DATA',
    payload: { withheld: [{ reason_key: 'chain_refused' }] },
    facts: [],
  },
];
const hostile = [{ toString: null }, 7, null, []];
function leaves(
  value: unknown,
  prefix: (string | number)[] = [],
): (string | number)[][] {
  if (
    value !== null &&
    typeof value === 'object' &&
    Object.keys(value).length
  ) {
    return Object.entries(value).flatMap(([key, child]) =>
      leaves(child, [...prefix, Array.isArray(value) ? Number(key) : key]),
    );
  }
  return [prefix];
}
afterEach(() => vi.unstubAllGlobals());
it('exhaustively mutates every leaf of each refusal fixture without raw exceptions', async () => {
  for (const [index, fixture] of fixtures.entries()) {
    for (const path of leaves(fixture)) {
      for (const bad of hostile) {
        const body = structuredClone(fixture) as Record<string, unknown>;
        let parent = body;
        for (const key of path.slice(0, -1))
          parent = parent[key] as Record<string, unknown>;
        parent[path.at(-1)!] = bad;
        try {
          const parsed = await readApiBody(
            Response.json(body, { status: index === 0 ? 500 : 200 }),
            'layers.unavailable',
            'layer_refused',
          );
          const state = outcomeRefusal(parsed, 200, 'layers.unavailable');
          if (state) {
            expect([
              'missing_input',
              'source_missing',
              'chain_refused',
            ]).toContain(state.message_key);
          }
        } catch (error) {
          expect(error).toBeInstanceOf(ApiRefusal);
          expect(refusalState(error, 'layers.unavailable').message_key).toMatch(
            /^(chain_refused|operation_failed)$/,
          );
        }
      }
    }
  }
});
it.each([
  'constructor',
  '__proto__',
  'https://INVENTED.invalid/?key=secret',
  '/INVENTED/private',
  'SELECT private',
  '',
  'x'.repeat(1_000_000),
])('rejects an unclosed server diagnostic', async (message_key) => {
  vi.stubGlobal('fetch', async () =>
    Response.json(
      { error: { code: message_key, message_key } },
      { status: 500 },
    ),
  );
  await expect(loadPublicLayer('parcels')).rejects.toMatchObject({
    state: {
      http_status: 500,
      code: 'INTERNAL',
      message_key: 'operation_failed',
      catalogue_key: 'layers.unavailable',
    },
  });
});
it.each([null, [], { toString: null }, 7])(
  'refuses malformed layer success bodies safely: %s',
  async (body) => {
    vi.stubGlobal('fetch', async () => Response.json(body));
    await expect(loadPublicLayer('parcels')).rejects.toBeInstanceOf(ApiRefusal);
  },
);
it.each([
  loadPublicLayer.bind(null, 'parcels'),
  loadBasemapUrl,
  loadBusyness.bind(null, 'INVENTED'),
])('refuses a non-JSON reply with its HTTP status', async (call) => {
  vi.stubGlobal(
    'fetch',
    async () =>
      new Response('INVENTED /private upstream prose', { status: 503 }),
  );
  await expect(call()).rejects.toMatchObject({
    state: {
      http_status: 503,
      code: 'INTERNAL',
      message_key: 'operation_failed',
    },
  });
});
it('keeps the standard BE-91 default key', async () => {
  await expect(
    readApiBody(
      Response.json(
        {
          error: {
            code: 'STORE_UNAVAILABLE',
            message_key: 'errors.store_unavailable',
          },
        },
        { status: 503 },
      ),
      'story.unavailable',
      'story_refused',
    ),
  ).rejects.toMatchObject({
    state: {
      http_status: 503,
      code: 'STORE_UNAVAILABLE',
      message_key: 'errors.store_unavailable',
      catalogue_key: 'story.unavailable',
    },
  });
});
it('keeps a null basemap as the explicit documented selection', async () => {
  vi.stubGlobal('fetch', async () =>
    Response.json({
      release_id: 'INVENTED',
      release_kind: 'public_only',
      rules_version_id: 'INVENTED',
      tables: [],
      artefacts: [],
      hour_keys: [],
      day_keys: [],
      month_keys: [],
      basemap_url: null,
    }),
  );
  expect(await loadBasemapUrl()).toBeNull();
});
it('preserves the reason at both remaining story HTTP boundaries', async () => {
  const fact = contextInput().facts[0]!.fact;
  const frames = [
    [
      'stage',
      {
        directive: 'fly',
        target: { area_id: 'INVENTED-area' },
        zoom: 'street',
      },
    ],
    ['stage', { directive: 'rings', area_ids: ['INVENTED-area'] }],
    [
      'evidence',
      {
        kind: 'night_lights',
        area_id: 'INVENTED-area',
        facts: [fact],
        fact_ids: [fact.fact_id],
      },
    ],
    [
      'receipt',
      {
        'Checked before display': Object.fromEntries(
          [
            'Sources',
            'Assumptions',
            'Nothing invented',
            'Scope',
            'Limits stated',
          ].map((key) => [key, true]),
        ),
        egress: [],
      },
    ],
    ['status', { writer: 'template' }],
    [
      'done',
      {
        brief: {
          catalogue_version: catalogue.version,
          headline_key: 'foundation_headline',
          decision_template_key: 'foundation_decision',
        },
      },
    ],
  ];
  for (const boundary of [
    'stream',
    'card',
    'card-NO_DATA',
    'card-SUPPRESSED',
  ]) {
    vi.stubGlobal('fetch', async (path: string) => {
      if (path === '/api/playbooks/site_check')
        return Response.json(
          { answer_id: 'a-b', events_url: '/api/answers/a-b/events' },
          { status: 202 },
        );
      if (path.endsWith('/events') && boundary.startsWith('card'))
        return new Response(
          frames
            .map(
              ([kind, data]) =>
                `event: ${kind}\ndata: ${JSON.stringify(data)}\n\n`,
            )
            .join(''),
        );
      if (boundary.startsWith('card-'))
        return Response.json({
          status: boundary.slice(5),
          reason: 'chain_refused',
          facts: [],
        });
      return Response.json(httpError, { status: 500 });
    });
    await expect(
      runPublicStory('INVENTED', 'en', { shape_id: 'INVENTED' }),
    ).rejects.toMatchObject({
      state: {
        http_status: boundary.startsWith('card-') ? 200 : 500,
        code: boundary.startsWith('card-') ? boundary.slice(5) : 'INTERNAL',
        message_key: 'chain_refused',
        catalogue_key: 'layers.refused.registry',
      },
    });
  }
});

it.each([
  [{ status: 'NO_DATA', reason: 'read_refused' }, 'read_refused'],
  [{ status: 'SUPPRESSED', reason_key: 'chain_refused' }, 'chain_refused'],
  [
    {
      status: 'NO_DATA',
      payload: { withheld: [{ reason_key: 'source_missing' }] },
    },
    'source_missing',
  ],
  [{ status: 'NO_DATA', caveat_keys: ['read_refused'] }, 'read_refused'],
  [{ status: 'NO_DATA', reason: 'INVENTED unknown' }, 'missing_input'],
] as const)('keeps each governed reason location', (body, message_key) => {
  expect(outcomeRefusal(body, 200, 'layers.unavailable')).toMatchObject({
    message_key,
  });
});
it('refuses a SUPPRESSED busyness card with its reason', async () => {
  vi.stubGlobal('fetch', async () =>
    Response.json({
      tool: 'venue_busyness',
      status: 'SUPPRESSED',
      reason: 'read_refused',
      facts: [],
    }),
  );
  await expect(loadBusyness('INVENTED')).rejects.toMatchObject({
    state: {
      http_status: 200,
      code: 'SUPPRESSED',
      message_key: 'read_refused',
      catalogue_key: 'story.unavailable',
    },
  });
});
it('D33 closes a missing asset without showing the reader exception', async () => {
  const { verifyAssets } = await import('../../scripts/photoreal-assets.mjs');
  expect(() =>
    verifyAssets(() => {
      throw new Error('INVENTED /private upstream');
    }),
  ).toThrowError(
    expect.objectContaining({
      code: 'unqualified-asset',
      message_key: 'unqualified-asset:draco_wasm_wrapper.js',
    }),
  );
});

it.each([null, [], 7])(
  'rejects a malformed success body at the shared reader',
  async (body) => {
    await expect(
      readApiBody(Response.json(body), 'layers.unavailable', 'layer_refused'),
    ).rejects.toMatchObject({
      state: {
        http_status: 200,
        code: 'INTERNAL',
        message_key: 'operation_failed',
        catalogue_key: 'layers.unavailable',
      },
    });
  },
);

it('keeps an OK body outside the governed refusal branch', () => {
  expect(outcomeRefusal({ status: 'OK' }, 200, 'story.unavailable')).toBeNull();
});

it('preserves a typed refusal through the optional wider-outline reader', async () => {
  const { decodeAreaOutline } = await import('../../src/api/areas');
  const error = new ApiRefusal({
    http_status: 503,
    code: 'STORE_UNAVAILABLE',
    message_key: 'chain_refused',
    catalogue_key: 'layers.refused.registry',
  });
  await expect(
    decodeAreaOutline('INVENTED', async () => {
      throw error;
    }),
  ).rejects.toBe(error);
});
