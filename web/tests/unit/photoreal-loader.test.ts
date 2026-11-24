import { expect, it, vi } from 'vitest';
import { validateGLB, visibleCredits } from '../../src/stage/photoreal-loader';
function fixture(change: object = {}) {
  const body = new TextEncoder().encode(
    JSON.stringify({
      asset: { version: '2.0', copyright: 'Invented credit' },
      ...change,
    }),
  );
  const size = Math.ceil(body.length / 4) * 4;
  const result = new ArrayBuffer(20 + size);
  const view = new DataView(result);
  view.setUint32(0, 0x46546c67, true);
  view.setUint32(4, 2, true);
  view.setUint32(8, result.byteLength, true);
  view.setUint32(12, size, true);
  view.setUint32(16, 0x4e4f534a, true);
  new Uint8Array(result, 20).fill(32);
  new Uint8Array(result, 20).set(body);
  return result;
}
it('rejects unknown codecs, external resources and missing attribution before loading', () => {
  expect(() => validateGLB(fixture())).not.toThrow();
  for (const change of [
    { extensionsRequired: ['unknown'] },
    { images: [{ uri: '//foreign.invalid/texture.png' }] },
    { buffers: [{ uri: 'escape.bin' }] },
    { asset: { version: '2.0' } },
    { images: [{ bufferView: 0, mimeType: 'image/unknown' }] },
  ])
    expect(() => validateGLB(fixture(change))).toThrow('photoreal unavailable');
});
it('aggregates visible tile copyright by count then text and refuses missing credit', () => {
  expect(visibleCredits(['Invented B; Invented A', 'Invented B'])).toBe(
    'Invented B; Invented A',
  );
  expect(visibleCredits(['Invented B; Invented B; Invented A'])).toBe(
    'Invented B; Invented A',
  );
  expect(visibleCredits([])).toBe('');
  expect(() => visibleCredits([undefined])).toThrow('photoreal unavailable');
  expect(() => visibleCredits([' ; '])).toThrow('photoreal unavailable');
});

import { qualifiedLayer } from '../../src/stage/photoreal-loader';
import { photorealSession } from '../../src/stage/photoreal-session';
import { operationalMeter } from '../fixtures/operational-meter';
function container(parts: [number, Uint8Array][], trailing = 0) {
  const length =
    12 + parts.reduce((sum, [, data]) => sum + 8 + data.length, 0) + trailing;
  const result = new ArrayBuffer(length);
  const view = new DataView(result);
  view.setUint32(0, 0x46546c67, true);
  view.setUint32(4, 2, true);
  view.setUint32(8, length, true);
  let offset = 12;
  for (const [type, data] of parts) {
    view.setUint32(offset, data.length, true);
    view.setUint32(offset + 4, type, true);
    new Uint8Array(result, offset + 8).set(data);
    offset += 8 + data.length;
  }
  return result;
}
function json(value: object) {
  const body = new TextEncoder().encode(JSON.stringify(value));
  const padded = new Uint8Array(Math.ceil(body.length / 4) * 4).fill(32);
  padded.set(body);
  return padded;
}
it('accepts one JSON chunk with at most one binary chunk and refuses every other chunk layout', () => {
  const JSON_CHUNK = 0x4e4f534a;
  const BIN_CHUNK = 0x004e4942;
  const benign = json({
    asset: { version: '2.0', copyright: 'Invented credit' },
  });
  const hostile = json({
    asset: { version: '2.0' },
    extensionsRequired: ['EXT_meshopt_compression'],
    buffers: [{ uri: '//foreign.invalid/escape.bin', byteLength: 4 }],
  });
  const bin = new Uint8Array(8);
  expect(() => validateGLB(container([[JSON_CHUNK, benign]]))).not.toThrow();
  expect(() =>
    validateGLB(
      container([
        [JSON_CHUNK, benign],
        [BIN_CHUNK, bin],
      ]),
    ),
  ).not.toThrow();
  expect(() =>
    validateGLB(
      container([
        [JSON_CHUNK, benign],
        [BIN_CHUNK, new Uint8Array(0)],
      ]),
    ),
  ).not.toThrow();
  for (const plant of [
    container([
      [JSON_CHUNK, benign],
      [JSON_CHUNK, hostile],
    ]),
    container([
      [JSON_CHUNK, benign],
      [0, hostile],
    ]),
    container([
      [JSON_CHUNK, benign],
      [BIN_CHUNK, bin],
      [JSON_CHUNK, hostile],
    ]),
    container([
      [JSON_CHUNK, benign],
      [BIN_CHUNK, bin],
      [BIN_CHUNK, bin],
    ]),
    container([
      [JSON_CHUNK, benign],
      [0x12345678, bin],
    ]),
    container([[JSON_CHUNK, benign]], 4),
  ])
    expect(() => validateGLB(plant)).toThrow('photoreal unavailable');
});
it('reports a failed root load through the layer error path with the fixed message', async () => {
  const errors: string[] = [];
  const layer = qualifiedLayer(
    {
      id: 'invented-root',
      data: '/api/photoreal/3dtiles/root.json',
      onError: (error: Error) => {
        errors.push(error.message);
        return true;
      },
    },
    async () => {
      throw new Error('SYN-refusal');
    },
  );
  await (
    layer as unknown as { _loadTileset(url: string): Promise<void> }
  )._loadTileset('/api/photoreal/3dtiles/root.json');
  expect(errors).toEqual(['photoreal unavailable']);
});
it('replaces the decoder text of a malformed root with the fixed message', async () => {
  const errors: string[] = [];
  const layer = qualifiedLayer(
    {
      id: 'invented-malformed-root',
      data: '/api/photoreal/3dtiles/root.json',
      onError: (error: Error) => {
        errors.push(error.message);
        return true;
      },
    },
    async () => {
      const response = new Response('SYN-payload');
      Object.defineProperty(response, 'url', {
        value: '/api/photoreal/3dtiles/root.json',
      });
      return response;
    },
  );
  await (
    layer as unknown as { _loadTileset(url: string): Promise<void> }
  )._loadTileset('/api/photoreal/3dtiles/root.json');
  expect(errors).toEqual(['photoreal unavailable']);
});
it('accepts an image as PNG bytes inside the binary chunk and nothing else, whatever its label says', () => {
  const JSON_CHUNK = 0x4e4f534a;
  const BIN_CHUNK = 0x004e4942;
  const png = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  const gif = [0x47, 0x49, 0x46, 0x38, 0x39, 0x61, 0x01, 0x00];
  const tile = (bytes: number[], view: object, image: object = {}) =>
    container([
      [
        JSON_CHUNK,
        json({
          asset: { version: '2.0', copyright: 'Invented credit' },
          buffers: [{ byteLength: 12 }],
          bufferViews: [{ buffer: 0, byteOffset: 4, byteLength: 8, ...view }],
          images: [{ bufferView: 0, mimeType: 'image/png', ...image }],
        }),
      ],
      [BIN_CHUNK, new Uint8Array([0, 0, 0, 0, ...bytes])],
    ]);
  expect(() => validateGLB(tile(png, {}))).not.toThrow();
  expect(() => validateGLB(tile([...png, 0, 0, 0, 0], {}))).not.toThrow();
  expect(() =>
    validateGLB(
      container([
        [
          JSON_CHUNK,
          json({
            asset: { version: '2.0', copyright: 'Invented credit' },
            bufferViews: [{ buffer: 0, byteLength: 8 }],
            images: [{ bufferView: 0, mimeType: 'image/png' }],
          }),
        ],
        [BIN_CHUNK, new Uint8Array(png)],
      ]),
    ),
  ).not.toThrow();
  for (const plant of [
    tile(gif, {}),
    tile(png, { byteOffset: 0 }),
    tile(png, { byteOffset: 8 }),
    tile(png, { byteLength: 4 }),
    tile(png, { byteLength: 9 }),
    tile([...png, 0, 0, 0, 0], { byteLength: 8.5 }),
    tile([...png, 0, 0, 0, 0], { byteOffset: 4.5 }),
    tile(png, {}, { bufferView: '0' }),
    tile(png, { buffer: 1 }),
    tile(png, {}, { bufferView: 1 }),
    tile(png, {}, { mimeType: 'image/jpeg' }),
    container([
      [
        JSON_CHUNK,
        json({
          asset: { version: '2.0', copyright: 'Invented credit' },
          bufferViews: [{ buffer: 0, byteLength: 8 }],
          images: [{ bufferView: 0, mimeType: 'image/png' }],
        }),
      ],
    ]),
  ])
    expect(() => validateGLB(plant)).toThrow('photoreal unavailable');
});
it('routes an error of a tile sublayer through the layer error path with the fixed message, after the current step', async () => {
  const errors: string[] = [];
  const layer = qualifiedLayer(
    {
      id: 'invented-sublayer',
      data: '/api/photoreal/3dtiles/root.json',
      onError: (error: Error) => {
        errors.push(error.message);
        return true;
      },
    },
    async () => new Response(null, { status: 502 }),
  );
  const sublayer = (
    layer as unknown as {
      _make3DModelLayer(tile: object): {
        context: object;
        raiseError(error: Error, message: string): void;
      };
    }
  )._make3DModelLayer({
    id: '/api/photoreal/3dtiles/invented.glb',
    content: { gltf: {} },
  });
  // Stands in for the default handler of the map-layer library, which prints
  // the sublayer's identifier and the error text.
  sublayer.context = { onError: () => errors.push('SYN-default-handler') };
  sublayer.raiseError(new Error('SYN-payload'), 'initialization of invented');
  // The pinned layer manager drops a layer list that is set while it updates
  // its layers, so nothing is raised inside the caller's step.
  expect(errors).toEqual([]);
  await Promise.resolve();
  expect(errors).toEqual(['photoreal unavailable']);
});
it('routes a refused update and a traversal error of the tile set through the layer error path with the fixed message', async () => {
  const errors: string[] = [];
  const layer = qualifiedLayer(
    {
      id: 'invented-traversal',
      data: '/api/photoreal/3dtiles/root.json',
      onError: (error: Error) => {
        errors.push(error.message);
        return true;
      },
    },
    async () => new Response(null, { status: 502 }),
  );
  // Stands in for the pinned tile set: its update promise rejects and its
  // traversal throws, each with text the page must never report.
  const tileset = {
    seen: [] as unknown[],
    selectTiles(viewports: unknown): Promise<number> {
      this.seen.push(viewports);
      return Promise.reject(new Error('SYN-payload'));
    },
    doUpdate(viewports: unknown): void {
      this.seen.push(viewports);
      throw new Error('SYN-payload');
    },
  };
  const updates = layer as unknown as {
    state: object;
    context: object;
    _updateTileset(viewports: object | null): void;
  };
  updates.state = { tileset3d: tileset };
  updates.context = { timeline: {} };
  updates._updateTileset(null);
  const guard = tileset.doUpdate;
  // A later update of the same tile set must not wrap it again. It reaches the
  // pinned layer's own update, whose promise the layer leaves unobserved.
  updates._updateTileset({ invented: 'SYN-viewport' });
  expect(tileset.doUpdate).toBe(guard);
  expect(() => tileset.doUpdate('SYN-traversal')).not.toThrow();
  expect(errors).toEqual(['photoreal unavailable']);
  const settled: string[] = [];
  void tileset.selectTiles('SYN-update').then(
    () => settled.push('resolved'),
    () => settled.push('rejected'),
  );
  await new Promise((resolve) => setTimeout(resolve));
  expect(tileset.seen).toEqual([
    ['SYN-viewport'],
    'SYN-traversal',
    'SYN-update',
  ]);
  expect(errors).toEqual(Array(3).fill('photoreal unavailable'));
  expect(settled).toEqual([]);
});
it('routes an error raised after a tile has loaded through the layer error path with the fixed message', () => {
  const errors: string[] = [];
  const layer = qualifiedLayer(
    {
      id: 'invented-loaded',
      data: '/api/photoreal/3dtiles/root.json',
      onError: (error: Error) => {
        errors.push(error.message);
        return true;
      },
    },
    async () => new Response(null, { status: 502 }),
  );
  // Stands in for the pinned tile set: the step it runs after a tile's content
  // has loaded throws, with text the page must never report.
  const tileset = {
    seen: [] as unknown[],
    selectTiles: (): Promise<number> => Promise.resolve(0),
    doUpdate(): void {},
    _onTileLoad(tile: unknown, loaded: unknown): void {
      this.seen.push([tile, loaded]);
      throw new Error('SYN-payload');
    },
  };
  const updates = layer as unknown as {
    state: object;
    context: object;
    _updateTileset(viewports: object | null): void;
  };
  updates.state = { tileset3d: tileset };
  updates.context = { timeline: {} };
  updates._updateTileset(null);
  expect(() => tileset._onTileLoad('SYN-tile', true)).not.toThrow();
  expect(tileset.seen).toEqual([['SYN-tile', true]]);
  expect(errors).toEqual(['photoreal unavailable']);
});

function tileFetch(layer: object) {
  return (
    layer as {
      props: { loadOptions: { fetch: (input: string) => Promise<Response> } };
    }
  ).props.loadOptions.fetch;
}

it('returns the tile when the spend callback throws', async () => {
  let called = false;
  const layer = qualifiedLayer(
    { id: 'invented-meter', data: '/api/photoreal/3dtiles/root.json' },
    async () =>
      new Response('{}', {
        headers: {
          'x-spend-meter': JSON.stringify(operationalMeter),
          'x-spend-order': '8',
        },
      }),
    () => {
      called = true;
      throw new Error('SYN-display');
    },
  );
  const response = await tileFetch(layer)('/api/photoreal/3dtiles/root.json');
  expect(called).toBe(true);
  expect(response.status).toBe(200);
});

it.each([
  ['absent', {}],
  ['malformed', { 'x-spend-order': '08' }],
] as const)(
  'a ready meter with a %s order token does not call the meter',
  async (_kind, extra) => {
    let called = false;
    const layer = qualifiedLayer(
      { id: 'invented-meter', data: '/api/photoreal/3dtiles/root.json' },
      async () =>
        new Response('{}', {
          headers: {
            'x-spend-meter': JSON.stringify(operationalMeter),
            ...extra,
          },
        }),
      () => {
        called = true;
      },
    );
    const response = await tileFetch(layer)('/api/photoreal/3dtiles/root.json');
    expect({ called, status: response.status }).toEqual({
      called: false,
      status: 200,
    });
  },
);

it('does not report a malformed spend header and still returns the tile', async () => {
  let called = false;
  const layer = qualifiedLayer(
    { id: 'invented-meter', data: '/api/photoreal/3dtiles/root.json' },
    async () =>
      new Response('{}', { headers: { 'x-spend-meter': 'not-json' } }),
    () => {
      called = true;
    },
  );
  const response = await tileFetch(layer)('/api/photoreal/3dtiles/root.json');
  expect(called).toBe(false);
  expect(response.status).toBe(200);
});

const readyHeader = {
  'x-spend-meter': JSON.stringify(operationalMeter),
  'x-spend-order': '8',
};

async function watchMeter(url: string, status: number) {
  let called = false;
  const fetcher = vi.fn(async (path: string, init?: RequestInit) => {
    if (path === '/api/photoreal/views' && init?.method === 'POST') {
      return new Response(JSON.stringify({ view_id: 'a'.repeat(32) }));
    }
    return new Response('{}', { status, headers: readyHeader });
  });
  const session = photorealSession(fetcher);
  await session.open();
  const layer = qualifiedLayer(
    { id: 'invented-meter', data: '/api/photoreal/3dtiles/root.json' },
    (input, init) => session.fetch(input, init),
    () => {
      called = true;
    },
  );
  let failure: unknown = null;
  try {
    await tileFetch(layer)(url);
  } catch (error) {
    failure = error;
  } finally {
    session.dispose();
  }
  return { called, fetcher, failure };
}

it('reports a valid spend header from a successful photoreal tile', async () => {
  const watched = await watchMeter('/api/photoreal/3dtiles/root.json', 200);
  expect(watched.failure).toBeNull();
  expect(watched.called).toBe(true);
});

function refusalOf(failure: unknown) {
  return failure instanceof Error ? failure.message : null;
}

it('a valid spend header on an error response never reaches the meter callback', async () => {
  const watched = await watchMeter('/api/photoreal/3dtiles/root.json', 500);
  expect({
    called: watched.called,
    fetched: watched.fetcher.mock.calls.some(([path]) =>
      String(path).startsWith('/api/photoreal/3dtiles/'),
    ),
    refusal: refusalOf(watched.failure),
  }).toEqual({
    called: false,
    fetched: true,
    refusal: 'photoreal unavailable',
  });
});

it('a valid spend header on a satellite response never reaches the meter callback', async () => {
  const watched = await watchMeter('/api/imagery/tiles/0/0/0', 200);
  expect({
    called: watched.called,
    imagery: watched.fetcher.mock.calls.some(([path]) =>
      String(path).startsWith('/api/imagery/'),
    ),
    refusal: refusalOf(watched.failure),
  }).toEqual({
    called: false,
    imagery: false,
    refusal: 'photoreal unavailable',
  });
});
