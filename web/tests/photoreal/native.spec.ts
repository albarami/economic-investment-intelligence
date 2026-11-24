import { test, expect } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { inventedGLB, inventedPNG } from './fixture.mjs';

let dist = '';
test.beforeAll(() => {
  dist = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-photoreal-'));
  const result = spawnSync(
    process.execPath,
    [
      'node_modules/vite/bin/vite.js',
      'build',
      '--config',
      'tests/photoreal/vite.config.ts',
    ],
    {
      encoding: 'utf8',
      env: {
        PATH: process.env.PATH,
        HOME: process.env.HOME,
        TMPDIR: process.env.TMPDIR,
        EII_PHOTOREAL_TEST_DIST: dist,
      },
    },
  );
  expect(result.status, result.stdout + '\n' + result.stderr).toBe(0);
});
test.afterAll(() => {
  if (dist) fs.rmSync(dist, { recursive: true, force: true });
});

test('native WebGL nested tiles decode Draco and PNG, preserve overlay and camera, then dispose', async ({
  page,
}) => {
  await page.addInitScript(() => {
    globalThis.inventedDecoderFetches = [];
    const original = Object.getOwnPropertyDescriptor(globalThis, 'fetch')!;
    Object.defineProperty(globalThis, 'fetch', {
      ...original,
      value: (input, init) => {
        if (typeof input === 'string' && input.startsWith('/assets/'))
          globalThis.inventedDecoderFetches.push({
            url: input,
            cache: init?.cache,
            redirect: init?.redirect,
          });
        return original.value.call(globalThis, input, init);
      },
    });
  });
  let badTile = false;
  const glb = await inventedGLB();
  const requests: string[] = [];
  const logs: string[] = [];
  page.on('console', (message) => logs.push(message.text()));
  page.on('pageerror', (error) => logs.push(error.message));
  const root = {
    asset: { version: '1.1', gltfUpAxis: 'Z' },
    geometricError: 200,
    root: {
      transform: [0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 6378137, 0, 0, 1],
      boundingVolume: { sphere: [0, 0, 0, 500] },
      geometricError: 100,
      refine: 'REPLACE',
      content: { uri: '/api/photoreal/3dtiles/nested.json' },
    },
  };
  const nested = {
    asset: { version: '1.1', gltfUpAxis: 'Z' },
    geometricError: 0,
    root: {
      boundingVolume: { sphere: [0, 0, 0, 500] },
      geometricError: 0,
      content: { uri: '/api/photoreal/3dtiles/invented.glb' },
    },
  };
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url());
    expect(url.origin).toBe('http://invented.invalid');
    requests.push(url.pathname);
    if (url.pathname.startsWith('/api/imagery/tiles/'))
      return route.fulfill({
        body: inventedPNG(),
        contentType: 'image/png',
        headers: {
          'x-attribution': 'Invented imagery',
          'cache-control': 'no-store',
        },
      });
    if (url.pathname === '/api/photoreal/views')
      return route.fulfill({ json: { view_id: 'a'.repeat(32) } });
    if (route.request().method() === 'DELETE')
      return route.fulfill({ status: 204 });
    if (url.pathname.startsWith('/api/photoreal/3dtiles/')) {
      expect([...url.searchParams.keys()]).toEqual(['view']);
      expect(url.searchParams.get('view')).toBe('a'.repeat(32));
      if (url.pathname.endsWith('root.json')) {
        await page.waitForFunction(() => {
          const layer = globalThis.inventedNative.overlay._props.layers.find(
            (x) => x.id.startsWith('photoreal:'),
          );
          return (
            Object.keys(layer?.state?.lastUpdatedViewports ?? {}).length > 0
          );
        });
        return route.fulfill({
          json: root,
          headers: { 'cache-control': 'no-store' },
        });
      }
      if (url.pathname.endsWith('nested.json'))
        return route.fulfill({
          json: nested,
          headers: { 'cache-control': 'no-store' },
        });
      return route.fulfill({
        body: badTile ? Buffer.from('SYN-payload') : glb,
        contentType: 'model/gltf-binary',
        headers: { 'cache-control': 'no-store' },
      });
    }
    const relative =
      url.pathname === '/'
        ? 'tests/photoreal/index.html'
        : url.pathname.slice(1);
    const file = path.join(dist, relative);
    expect(fs.existsSync(file), relative).toBe(true);
    return route.fulfill({
      body: fs.readFileSync(file),
      contentType: relative.endsWith('.js')
        ? 'text/javascript'
        : relative.endsWith('.wasm')
          ? 'application/wasm'
          : relative.endsWith('.html')
            ? 'text/html'
            : 'application/octet-stream',
    });
  });
  await page.goto('http://invented.invalid');
  await page.evaluate(async () => {
    await globalThis.inventedNative.ready;
    globalThis.inventedWorkerCount = 0;
    globalThis.Worker = class {
      constructor() {
        globalThis.inventedWorkerCount++;
        throw new Error('worker plant');
      }
    };
    globalThis.inventedStorageCount = 0;
    const reject = () => {
      globalThis.inventedStorageCount++;
      throw new Error('storage plant');
    };
    Storage.prototype.setItem = reject;
    indexedDB.open = reject;
    if (globalThis.caches) globalThis.caches.open = reject;
  });
  const camera = () =>
    page.evaluate(() => {
      const map = globalThis.inventedNative.map;
      return [
        map.getCenter().toArray(),
        map.getZoom(),
        map.getPitch(),
        map.getBearing(),
      ];
    });
  const before = await camera();
  await page.evaluate(() => globalThis.inventedNative.setMode('photoreal'));
  expect(await camera()).toEqual(before);
  await expect(page.locator('#credit')).toHaveText('Invented fixture');
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          globalThis.inventedNative.overlay._props.layers.find((x) =>
            x.id.startsWith('photoreal:'),
          )?.state?.tileset3d?.selectedTiles?.[0]?.tileDrawn,
      ),
    )
    .toBe(true);
  const state = await page.evaluate(() => {
    const { map, overlay } = globalThis.inventedNative;
    const layer = overlay._props.layers.find((x) =>
      x.id.startsWith('photoreal:'),
    );
    const tile = layer.state.tileset3d.selectedTiles[0];
    globalThis.inventedBitmap = tile.content.gltf.images[0].image;
    return {
      loader: layer.props.loader.version,
      overlays: map._controls.length,
      bases: map
        .getStyle()
        .layers.map((x) => x.id)
        .filter(
          (x) => x === 'open-base' || x === 'imagery' || x === 'open-buildings',
        ),
      layers: overlay._props.layers.map((x) => x.id),
      vertices:
        tile.content.gltf.meshes[0].primitives[0].attributes.POSITION.value
          .length,
      images: tile.content.gltf.images.length,
      width: tile.content.gltf.images[0].image.width,
      drawn: tile.tileDrawn,
      gl: !!map.getCanvas().getContext('webgl2'),
    };
  });
  const decoderFetches = await page.evaluate(
    () => globalThis.inventedDecoderFetches,
  );
  expect(decoderFetches.some((entry) => entry.url.endsWith('.wasm'))).toBe(
    true,
  );
  expect(decoderFetches.some((entry) => entry.url.endsWith('.js'))).toBe(true);
  for (const entry of decoderFetches)
    expect(entry).toMatchObject({ cache: 'no-store', redirect: 'error' });
  expect(state.loader).toBe('4.5.4');
  expect(state.overlays).toBe(1);
  expect(state.bases).toEqual([]);
  expect(state.layers).toContain('invented-hero');
  expect(state.layers).toContain('invented-context');
  expect(state.layers).toContain('invented-area');
  expect(state.vertices).toBe(9);
  expect(state.images).toBe(1);
  expect(state.width).toBe(1);
  expect(state.drawn).toBe(true);
  expect(state.gl).toBe(true);
  await page.evaluate(() => {
    globalThis.inventedNative.clock();
    globalThis.inventedNative.payload();
  });
  await expect(page.locator('#credit')).toHaveText('Invented fixture');
  expect(
    await page.evaluate(() =>
      globalThis.inventedNative.overlay._props.layers.map((x) => x.id),
    ),
  ).toEqual(
    expect.arrayContaining([
      'invented-hero',
      'invented-context',
      'invented-area',
    ]),
  );
  await page.evaluate(() => globalThis.inventedNative.setMode('satellite'));
  expect(await camera()).toEqual(before);
  expect(
    await page.evaluate(
      () => !!globalThis.inventedNative.map.getStyle().sources.imagery,
    ),
  ).toBe(true);
  await page.evaluate(() => globalThis.inventedNative.setMode('open'));
  await expect(page.locator('#credit')).toHaveText('');
  expect(await page.evaluate(() => globalThis.inventedBitmap.width)).toBe(0);
  expect(await camera()).toEqual(before);
  expect(requests).toContain('/api/photoreal/3dtiles/nested.json');
  expect(requests).toContain('/api/photoreal/3dtiles/invented.glb');
  expect(await page.evaluate(() => globalThis.inventedWorkerCount)).toBe(0);
  expect(await page.evaluate(() => globalThis.inventedStorageCount)).toBe(0);
  expect(
    await page.evaluate(() =>
      globalThis.inventedNative.overlay._props.layers.some((x) =>
        x.id.startsWith('photoreal:'),
      ),
    ),
  ).toBe(false);
  expect(await page.evaluate(() => globalThis.inventedNative.failures)).toEqual(
    [],
  );
  badTile = true;
  await page.evaluate(() => globalThis.inventedNative.setMode('photoreal'));
  try {
    await expect
      .poll(() => requests.filter((x) => x.endsWith('invented.glb')).length)
      .toBe(2);
  } catch (cause) {
    const diagnostic = await page.evaluate(() => {
      const layer = globalThis.inventedNative.overlay._props.layers.find((x) =>
        x.id.startsWith('photoreal:'),
      );
      return {
        layer: !!layer,
        state: !!layer?.state,
        tileset: !!layer?.state?.tileset3d,
        activeViewports: Object.keys(layer?.state?.activeViewports ?? {})
          .length,
        selected: layer?.state?.tileset3d?.selectedTiles?.length,
        pending: layer?.state?.tileset3d?._pendingCount,
        failures: globalThis.inventedNative.failures.length,
        styleLoaded: globalThis.inventedNative.map.isStyleLoaded(),
        root: !!layer?.state?.tileset3d?.root,
        frame: layer?.state?.tileset3d?.frameNumber,
        lastViewports: layer?.state?.tileset3d?.lastUpdatedVieports?.map(
          (v) => ({
            id: v.id,
            zoom: v.zoom,
            latitude: v.latitude,
            longitude: v.longitude,
            width: v.width,
            height: v.height,
          }),
        ),
        rootState: layer?.state?.tileset3d?.root?._contentState,
        visible: layer?.state?.tileset3d?.root?._visible,
        rootKeys: Object.keys(layer?.state?.tileset3d?.roots ?? {}),
      };
    });
    throw new Error(
      JSON.stringify({
        diagnostic,
        roots: requests.filter((x) => x.endsWith('root.json')).length,
        nested: requests.filter((x) => x.endsWith('nested.json')).length,
      }),
      { cause },
    );
  }
  await expect
    .poll(() => page.evaluate(() => globalThis.inventedNative.failures.length))
    .toBe(1);
  await expect(page.locator('#credit')).toHaveText('');
  expect(requests.filter((x) => x === '/api/photoreal/views')).toHaveLength(2);
  expect(
    logs.filter(
      (x) => x.includes('/api/photoreal/') || x.includes('SYN-payload'),
    ),
  ).toEqual([]);
  await page.evaluate(() => globalThis.inventedNative.remove());
});

for (const plant of [
  'gif-labelled-png',
  'tile-sublayer-error',
  'tile-sublayer-held',
  'tile-loaded-error',
  'root-refused',
  'root-malformed',
  'root-missing',
  'root-volume-odd',
  'root-traversal-error',
] as const) {
  test(`fails closed and restores open for ${plant}`, async ({ page }) => {
    // Invented one-pixel GIF, deliberately carried under the PNG label.
    const gif = Buffer.from([
      0x47, 0x49, 0x46, 0x38, 0x39, 0x61, 1, 0, 1, 0, 0x80, 0, 0, 255, 0, 0, 0,
      0, 0, 0x2c, 0, 0, 0, 0, 1, 0, 1, 0, 0, 2, 2, 0x44, 1, 0, 0x3b,
    ]);
    // An invented primitive mode: the tile passes validation and parsing, and
    // the pinned scene builder refuses it inside the tile's sublayer.
    const glb =
      plant === 'tile-sublayer-error' || plant === 'tile-sublayer-held'
        ? await inventedGLB(undefined, (json) => {
            json.meshes[0].primitives[0].mode = 'SYN-payload';
          })
        : plant === 'tile-loaded-error'
          ? // An invented value in place of the list of removed extensions, on
            // a tile with no compressed mesh: the tile passes validation and
            // parsing, and the pinned tile set refuses it after its content
            // has loaded.
            await inventedGLB(undefined, (json) => {
              delete json.meshes[0].primitives[0].extensions;
              delete json.extensionsUsed;
              delete json.extensionsRequired;
              json.extensionsRemoved = { invented: 'SYN-payload' };
            })
          : await inventedGLB(gif);
    const requests: { method: string; path: string }[] = [];
    const logs: string[] = [];
    const errors: string[] = [];
    page.on('console', (message) => logs.push(message.text()));
    page.on('pageerror', (error) => errors.push(error.message));
    await page.route('**/*', async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      expect(url.origin).toBe('http://invented.invalid');
      requests.push({ method: request.method(), path: url.pathname });
      if (url.pathname === '/api/photoreal/views')
        return route.fulfill({ json: { view_id: 'a'.repeat(32) } });
      if (request.method() === 'DELETE') return route.fulfill({ status: 204 });
      if (url.pathname === '/api/photoreal/3dtiles/root.json') {
        if (plant === 'root-refused') return route.fulfill({ status: 502 });
        if (plant === 'root-malformed')
          return route.fulfill({
            body: 'SYN-payload',
            contentType: 'application/json',
          });
        if (plant === 'root-missing') return route.fulfill({ json: {} });
        return route.fulfill({
          json: {
            asset: { version: '1.1', gltfUpAxis: 'Z' },
            geometricError: 0,
            root: {
              transform: [0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 6378137, 0, 0, 1],
              // An invented volume that the pinned tile set refuses when it
              // builds its tiles, and one that its traversal refuses in a timer.
              boundingVolume:
                plant === 'root-volume-odd'
                  ? 'SYN-payload'
                  : plant === 'root-traversal-error'
                    ? { sphere: 'SYN-payload' }
                    : { sphere: [0, 0, 0, 500] },
              geometricError: 0,
              content: { uri: '/api/photoreal/3dtiles/invented.glb' },
            },
          },
        });
      }
      if (url.pathname === '/api/photoreal/3dtiles/invented.glb')
        return route.fulfill({ body: glb, contentType: 'model/gltf-binary' });
      const relative =
        url.pathname === '/'
          ? 'tests/photoreal/index.html'
          : url.pathname.slice(1);
      const file = path.join(dist, relative);
      expect(fs.existsSync(file), relative).toBe(true);
      return route.fulfill({
        body: fs.readFileSync(file),
        contentType: relative.endsWith('.js')
          ? 'text/javascript'
          : relative.endsWith('.wasm')
            ? 'application/wasm'
            : relative.endsWith('.html')
              ? 'text/html'
              : 'application/octet-stream',
      });
    });
    await page.goto('http://invented.invalid');
    // The held page does not return to the open mode: the failed mode must
    // take its layer out of the map-layer library by itself.
    if (plant === 'tile-sublayer-held')
      await page.evaluate(() => globalThis.inventedNative.hold());
    await page.evaluate(async () => {
      await globalThis.inventedNative.ready;
      await globalThis.inventedNative.setMode('photoreal');
    });
    await expect
      .poll(() => page.evaluate(() => globalThis.inventedNative.failures))
      .toEqual(['fixed failure']);
    await expect
      .poll(() => requests.filter((request) => request.method === 'DELETE'))
      .toEqual([
        { method: 'DELETE', path: `/api/photoreal/views/${'a'.repeat(32)}` },
      ]);
    expect(
      await page.evaluate(() =>
        globalThis.inventedNative.overlay._props.layers.some((layer) =>
          layer.id.startsWith('photoreal:'),
        ),
      ),
    ).toBe(false);
    // The layer list of the map-layer library itself, not only the list handed
    // to the overlay.
    await expect
      .poll(() =>
        page.evaluate(() =>
          globalThis.inventedNative.overlay._deck.layerManager.layers.some(
            (layer) => layer.id.startsWith('photoreal:'),
          ),
        ),
      )
      .toBe(false);
    if (plant !== 'tile-sublayer-held')
      expect(
        await page.evaluate(() =>
          globalThis.inventedNative.map
            .getStyle()
            .layers.map((layer) => layer.id),
        ),
      ).toContain('open-base');
    await expect(page.locator('#credit')).toHaveText('');
    expect(
      requests.filter((request) => request.method === 'POST'),
    ).toHaveLength(1);
    if (
      plant === 'gif-labelled-png' ||
      plant === 'tile-sublayer-error' ||
      plant === 'tile-sublayer-held' ||
      plant === 'tile-loaded-error'
    )
      expect(
        requests.filter((request) => request.path.endsWith('invented.glb')),
      ).toHaveLength(1);
    expect(errors).toEqual([]);
    expect(
      logs.filter(
        (text) =>
          text.includes('/api/photoreal/') || text.includes('SYN-payload'),
      ),
    ).toEqual([]);
    await page.evaluate(() => globalThis.inventedNative.remove());
    expect(
      requests.filter((request) => request.method === 'DELETE'),
    ).toHaveLength(1);
  });
}
