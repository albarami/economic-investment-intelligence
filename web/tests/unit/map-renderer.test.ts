// @vitest-environment jsdom
/** Renderer fixtures only: no WebGL or provider request. */
import { createElement } from 'react';
import {
  act,
  cleanup,
  fireEvent,
  render,
  waitFor,
} from '@testing-library/react';
import { Stage } from '../../src/stage/Stage';
import { afterEach, expect, it, vi } from 'vitest';
const state = vi.hoisted(() => ({
  maps: [] as object[],
  events: [] as string[],
  protocols: new Map(),
  overlays: [] as object[],
}));
vi.mock('maplibre-gl', async () => {
  const { mapLibreDouble } = await import('../fixtures/renderer-doubles');
  return mapLibreDouble(state);
});
vi.mock('@deck.gl/maplibre', async () => {
  const { overlayDouble } = await import('../fixtures/renderer-doubles');
  return overlayDouble(state);
});
import * as qualified from '../../src/stage/photoreal-loader';
import { startMap } from '../../src/stage/map-boot';
import type { Layer } from '@deck.gl/core';
const style = {
  version: 8,
  sources: { fixture: { type: 'vector', url: '/SYN-map' } },
  layers: [],
} as const;
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  state.maps.length = 0;
  state.overlays.length = 0;
});

it('initialises the lazy plugin once before either map', async () => {
  const first = await startMap({} as HTMLElement, style);
  const second = await startMap({} as HTMLElement, style);
  expect(state.events[0]).toBe('rtl');
  expect(state.events.filter((event) => event === 'rtl')).toHaveLength(1);
  expect(state.events.slice(-2)).toEqual(['map', 'map']);
  first.remove();
  second.remove();
});

it('replaces every base on the shared overlay and disposes the view on exit', async () => {
  const fetcher = vi.fn(
    async () => new Response(JSON.stringify({ view_id: 'a'.repeat(32) })),
  );
  vi.stubGlobal('fetch', fetcher);
  const handle = await startMap({} as HTMLElement, style);
  await handle.setMode!('photoreal', vi.fn());
  expect(state.overlays).toHaveLength(1);
  expect((state.maps[0] as { style: unknown }).style).toEqual({
    version: 8,
    sources: {},
    layers: [],
  });
  const overlay = state.overlays[0] as { props: { layers: { id: string }[] } };
  expect(
    overlay.props.layers.some((layer) => layer.id.startsWith('photoreal:')),
  ).toBe(true);
  handle.setClock!(0);
  expect(
    overlay.props.layers.some((layer) => layer.id.startsWith('photoreal:')),
  ).toBe(true);
  await handle.setMode!('open', vi.fn());
  expect(
    overlay.props.layers.some((layer) => layer.id.startsWith('photoreal:')),
  ).toBe(false);
  expect((state.maps[0] as { style: unknown }).style).toEqual(style);
  expect(fetcher).toHaveBeenCalledWith(
    '/api/photoreal/views/' + 'a'.repeat(32),
    expect.objectContaining({ method: 'DELETE' }),
  );
  handle.remove();
});

it('fetches satellite bytes with no cache and passes runtime credit, then removes the protocol', async () => {
  const raw = new ArrayBuffer(4);
  const fetcher = vi.fn().mockResolvedValue({
    ok: true,
    headers: new Headers({ 'x-attribution': 'SYN-tile-credit' }),
    arrayBuffer: async () => raw,
  });
  vi.stubGlobal('fetch', fetcher);
  const credit = vi.fn();
  const handle = await startMap({} as HTMLElement, style);
  await handle.setMode!('satellite', credit);
  const raster = (
    state.maps[0] as { style: { sources: { imagery: { tiles: string[] } } } }
  ).style.sources.imagery;
  const uri = raster.tiles[0]!.replace('{z}', '0')
    .replace('{x}', '0')
    .replace('{y}', '0');
  const protocol = uri.split(':')[0];
  const response = await state.protocols.get(protocol)(
    { url: uri },
    new AbortController(),
  );
  expect(response.data).toBe(raw);
  expect(response.cacheControl).toBe('no-store');
  expect(fetcher).toHaveBeenCalledWith(
    '/api/imagery/tiles/0/0/0',
    expect.objectContaining({ cache: 'no-store' }),
  );
  expect(credit).toHaveBeenCalledWith('SYN-tile-credit');
  handle.remove();
  expect(state.protocols.has(protocol)).toBe(false);
});

it('mounted Stage replaces the basemap, scopes satellite credit and keeps every tile request no-store', async () => {
  const store = vi.spyOn(Storage.prototype, 'setItem');
  const cache = vi.fn();
  const database = vi.fn();
  const register = vi.fn();
  const write = vi.fn();
  vi.stubGlobal('caches', { open: cache, put: write });
  vi.stubGlobal('indexedDB', { open: database });
  const originalWorker = Object.getOwnPropertyDescriptor(
    navigator,
    'serviceWorker',
  );
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: { register, controller: { postMessage: write } },
  });
  const fetcher = vi.fn(async (path) => {
    if (path === '/api/map-modes')
      return {
        ok: true,
        json: async () => ({
          open: { available: true, reason: null },
          satellite: { available: true, reason: null },
          photoreal: { available: true, reason: null, meter: null },
        }),
      };
    if (path === '/api/photoreal/views')
      return { ok: true, json: async () => ({ view_id: 'a'.repeat(32) }) };
    return {
      ok: true,
      headers: new Headers({ 'x-attribution': 'SYN-integrated-credit' }),
      arrayBuffer: async () => new ArrayBuffer(1),
    };
  });
  vi.stubGlobal('fetch', fetcher);
  const view = render(
    createElement(Stage, {
      language: 'en',
      theme: 'dark',
      extractUrl: '/SYN-map.pmtiles',
      mapStarter: startMap,
    }),
  );
  await waitFor(() =>
    expect(
      view.getByRole('radio', { name: 'Satellite' }).hasAttribute('disabled'),
    ).toBe(false),
  );
  fireEvent.click(view.getByRole('radio', { name: 'Satellite' }));
  await waitFor(() =>
    expect(state.maps.at(-1).style.sources.imagery).toBeTruthy(),
  );
  const uri = state.maps
    .at(-1)
    .style.sources.imagery.tiles[0].replace('{z}', '0')
    .replace('{x}', '0')
    .replace('{y}', '0');
  await state.protocols.get(uri.split(':')[0])(
    { url: uri },
    new AbortController(),
  );
  await waitFor(() =>
    expect(view.queryByText('SYN-integrated-credit')).not.toBeNull(),
  );
  expect(view.getByText('SYN-integrated-credit').closest('details')?.open).toBe(
    false,
  );
  fireEvent.click(view.getByRole('radio', { name: /Photorealistic/ }));
  await waitFor(() => expect(state.maps.at(-1).style.sources).toEqual({}));
  expect(
    view
      .getByRole('radio', { name: /Photorealistic/ })
      .hasAttribute('disabled'),
  ).toBe(false);
  expect(view.queryByText('SYN-integrated-credit')).toBeNull();
  for (const [, options] of fetcher.mock.calls)
    expect(options.cache).toBe('no-store');
  expect(store).not.toHaveBeenCalled();
  expect(cache).not.toHaveBeenCalled();
  expect(database).not.toHaveBeenCalled();
  expect(register).not.toHaveBeenCalled();
  expect(write).not.toHaveBeenCalled();
  if (originalWorker)
    Object.defineProperty(navigator, 'serviceWorker', originalWorker);
  else Reflect.deleteProperty(navigator, 'serviceWorker');
  store.mockRestore();
  fireEvent.click(view.getByRole('radio', { name: 'Open map' }));
  await waitFor(() =>
    expect(state.maps.at(-1).style.sources.protomaps).toBeTruthy(),
  );
  expect(view.queryByText('SYN-integrated-credit')).toBeNull();
});

it('reapplies the chosen clock when replacing a basemap', async () => {
  const handle = await startMap({} as HTMLElement, style);
  const clock = { onAdd: vi.fn(), onRemove: vi.fn(), setClock: vi.fn() };
  handle.mountOverlay(clock);
  const timestamp = Date.parse('2026-06-01T03:00:00Z');
  handle.setClock!(timestamp);
  clock.setClock.mockClear();
  await handle.setMode!('satellite', vi.fn());
  expect(clock.setClock).toHaveBeenCalledWith(timestamp);
  handle.remove();
});

it('replaces only the overlay and removes each mounted overlay exactly once', async () => {
  const handle = await startMap({} as HTMLElement, style);
  const first = { onAdd: vi.fn(), onRemove: vi.fn(), setClock: vi.fn() };
  const second = { onAdd: vi.fn(), onRemove: vi.fn(), setClock: vi.fn() };
  const timestamp = Date.parse('2026-06-01T03:00:00Z');
  handle.setClock!(timestamp);
  handle.mountOverlay(first);
  handle.mountOverlay(second);
  expect(state.maps).toHaveLength(1);
  expect(first.onRemove).toHaveBeenCalledTimes(1);
  expect(second.setClock).toHaveBeenCalledWith(timestamp);
  handle.remove();
  expect(first.onRemove).toHaveBeenCalledTimes(1);
  expect(second.onRemove).toHaveBeenCalledTimes(1);
});

it('keeps verified buildings across overlay replacement and reads the view edges', async () => {
  const handle = await startMap({} as HTMLElement, style);
  const layers = [] as Layer[];
  const first = { onAdd: vi.fn(), onRemove: vi.fn(), setBuildings: vi.fn() };
  const second = { onAdd: vi.fn(), onRemove: vi.fn(), setBuildings: vi.fn() };
  handle.mountOverlay(first);
  handle.setBuildings!(layers, 3);
  expect(first.setBuildings).toHaveBeenCalledWith(layers, 3);
  handle.mountOverlay(second);
  expect(second.setBuildings).toHaveBeenCalledWith(layers, 3);
  // A refused update is never kept for the next overlay.
  const refusing = {
    onAdd: vi.fn(),
    onRemove: vi.fn(),
    setBuildings: vi.fn((_layers: Layer[], cap: number) => {
      if (cap === 1) throw new Error('shadow_over_cap');
    }),
  };
  handle.mountOverlay(refusing);
  expect(() => handle.setBuildings!([{} as Layer], 1)).toThrow(
    'shadow_over_cap',
  );
  const third = { onAdd: vi.fn(), onRemove: vi.fn(), setBuildings: vi.fn() };
  handle.mountOverlay(third);
  expect(third.setBuildings).toHaveBeenCalledWith(layers, 3);
  expect(handle.viewBounds!().bounds).toEqual([51.4, 25.2, 51.6, 25.4]);
});

it('preserves every non-default camera property across open satellite open', async () => {
  const handle = await startMap({} as HTMLElement, style);
  const map = state.maps.at(-1) as {
    jumpTo: (camera: object) => void;
    getCenter: () => number[];
    getZoom: () => number;
    getBearing: () => number;
    getPitch: () => number;
  };
  const camera = { center: [51.3, 25.4], zoom: 12, bearing: 37, pitch: 48 };
  map.jumpTo(camera);
  for (const mode of ['open', 'satellite', 'open'] as const) {
    await handle.setMode!(mode, vi.fn());
    expect(map.getCenter()).toEqual(camera.center);
    expect(map.getZoom()).toBe(camera.zoom);
    expect(map.getBearing()).toBe(camera.bearing);
    expect(map.getPitch()).toBe(camera.pitch);
  }
  handle.remove();
});

it.each([
  ['http', () => new Response('{}', { status: 503 })],
  ['array', () => new Response('[]')],
  ['bad-json', () => new Response('{')],
  ['wrong-id', () => new Response(JSON.stringify({ view_id: 'SYN-invalid' }))],
  [
    'extra',
    () =>
      new Response(JSON.stringify({ view_id: 'a'.repeat(32), extra: true })),
  ],
])(
  'refuses %s view responses without replacing open or retrying',
  async (_name, response) => {
    const fetcher = vi.fn(async () => response());
    vi.stubGlobal('fetch', fetcher);
    const handle = await startMap({} as HTMLElement, style);
    await expect(handle.setMode!('photoreal', vi.fn())).rejects.toThrow(
      /^photoreal unavailable$/,
    );
    expect(state.maps.at(-1).style).toEqual(style);
    expect(
      fetcher.mock.calls.filter(([url]) => url === '/api/photoreal/views'),
    ).toHaveLength(1);
    expect(fetcher.mock.calls.some(([url]) => url.includes('/3dtiles/'))).toBe(
      false,
    );
    handle.remove();
  },
);

it.each(['en', 'ar'] as const)(
  'mounted Stage restores open with the local renderer reason in %s',
  async (language) => {
    const fetcher = vi.fn(
      async (url) =>
        new Response(
          JSON.stringify(
            url === '/api/map-modes'
              ? {
                  open: { available: true, reason: null },
                  satellite: { available: false, reason: 'no_key' },
                  photoreal: { available: true, reason: null, meter: null },
                }
              : { view_id: 'a'.repeat(32) },
          ),
        ),
    );
    vi.stubGlobal('fetch', fetcher);
    const build = vi
      .spyOn(qualified, 'qualifiedLayer')
      .mockImplementationOnce(() => {
        throw new Error('SYN-construction');
      });
    const view = render(
      createElement(Stage, {
        language,
        theme: 'dark',
        extractUrl: '/SYN-map.pmtiles',
        mapStarter: startMap,
      }),
    );
    const radios = view.getAllByRole('radio');
    const control = radios.at(-1)!;
    await waitFor(() => expect(control.hasAttribute('disabled')).toBe(false));
    fireEvent.click(control);
    await waitFor(() =>
      expect(
        view.getByText(
          language === 'en' ? 'Renderer unavailable' : 'عارض المشهد غير متاح',
        ),
      ).toBeTruthy(),
    );
    expect(radios[0].getAttribute('aria-checked')).toBe('true');
    expect(control.hasAttribute('disabled')).toBe(true);
    expect(state.maps.at(-1).style.sources.protomaps).toBeTruthy();
    expect(
      view.container.querySelector('[data-part="attribution"]')?.textContent ??
        '',
    ).not.toContain('SYN-credit');
    expect(build).toHaveBeenCalledTimes(1);
    expect(
      fetcher.mock.calls.filter(([, init]) => init.method === 'POST'),
    ).toHaveLength(1);
    expect(
      fetcher.mock.calls.filter(([, init]) => init.method === 'DELETE'),
    ).toHaveLength(1);
    expect(fetcher.mock.calls.some(([url]) => url.includes('/3dtiles/'))).toBe(
      false,
    );
  },
);

it.each([false, true])(
  'mounted Stage restores open after a child refusal with project availability %s',
  async (projectAvailable) => {
    let capped = false;
    const fetcher = vi.fn(async (url) => {
      if (url === '/api/map-modes')
        return new Response(
          JSON.stringify({
            open: { available: true, reason: null },
            satellite: { available: false, reason: 'no_key' },
            photoreal:
              capped && !projectAvailable
                ? { available: false, reason: 'cap_reached', meter: null }
                : { available: true, reason: null, meter: null },
          }),
        );
      if (url === '/api/photoreal/views')
        return new Response(JSON.stringify({ view_id: 'a'.repeat(32) }));
      if (url.includes('/3dtiles/')) {
        capped = true;
        return new Response('{}', { status: 429 });
      }
      return new Response(null, { status: 204 });
    });
    vi.stubGlobal('fetch', fetcher);
    const view = render(
      createElement(Stage, {
        language: 'en',
        theme: 'dark',
        extractUrl: '/SYN-map.pmtiles',
        mapStarter: startMap,
      }),
    );
    const control = view.getByRole('radio', { name: /Photorealistic/ });
    await waitFor(() => expect(control.hasAttribute('disabled')).toBe(false));
    fireEvent.click(control);
    await waitFor(() => expect(state.maps.at(-1).style.sources).toEqual({}));
    const layer = state.overlays
      .at(-1)
      .props.layers.find((item) => item.id.startsWith('photoreal:'));
    await act(async () => {
      layer.props.loadOptions.tileset.onTraversalComplete([
        { content: { gltf: { asset: { copyright: 'SYN-credit' } } } },
      ]);
    });
    expect(view.getByText('SYN-credit')).toBeTruthy();
    await act(async () => {
      await expect(
        layer.props.loadOptions.fetch('/api/photoreal/3dtiles/invented.glb'),
      ).rejects.toThrow(/^photoreal unavailable$/);
      layer.props.onTileError();
    });
    await waitFor(() =>
      expect(
        view.getByText(
          projectAvailable
            ? 'Connection unavailable'
            : 'Request budget reached',
        ),
      ).toBeTruthy(),
    );
    expect(
      view
        .getByRole('radio', { name: 'Open map' })
        .getAttribute('aria-checked'),
    ).toBe('true');
    expect(control.hasAttribute('disabled')).toBe(true);
    expect(state.maps.at(-1).style.sources.protomaps).toBeTruthy();
    expect(view.queryByText('SYN-credit')).toBeNull();
    expect(
      fetcher.mock.calls.filter(([, init]) => init.method === 'POST'),
    ).toHaveLength(1);
    expect(
      fetcher.mock.calls.filter(([url]) => url === '/api/map-modes'),
    ).toHaveLength(2);
  },
);
