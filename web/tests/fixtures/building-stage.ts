/**
 * A stand-in map and fetch for the mounted building tests of S3-T16: the
 * heights route answers the given body, every other path the map modes.
 */
import { act } from '@testing-library/react';
import type { Layer } from '@deck.gl/core';
import { vi } from 'vitest';

import type { ShadowView } from '../../src/stage/buildings3d';
import type { MapHandle } from '../../src/stage/map-boot';

export const MODES = {
  open: { available: true, reason: null },
  satellite: { available: false, reason: 'offline' },
  photoreal: { available: false, reason: 'cap_reached', meter: null },
};
export const NEAR: ShadowView = {
  centre: [51.5015, 25.30025],
  bounds: [51.49, 25.29, 51.51, 25.31],
};
export const EMPTY: ShadowView = {
  centre: [51.2, 25.1],
  bounds: [51.19, 25.09, 51.21, 25.11],
};

export function serve(heights: unknown) {
  const fetcher = vi.fn(async (path: string) => ({
    ok: true,
    json: async () => (path === '/api/building-heights' ? heights : MODES),
  }));
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}

export function fakeMap() {
  let view = NEAR;
  const listeners = new Set<() => void>();
  const setBuildings = vi.fn<(layers: Layer[], cap: number) => void>();
  const handle: MapHandle = {
    bind: vi.fn(),
    unbind: vi.fn(),
    project: vi.fn(() => ({ x: 0, y: 0 })),
    unproject: vi.fn(() => ({ longitude: 0, latitude: 0 })),
    suspendGestures: vi.fn(),
    restoreGestures: vi.fn(),
    centre: vi.fn(() => ({ longitude: 0, latitude: 0 })),
    bindView: (listener) => listeners.add(listener),
    unbindView: (listener) => listeners.delete(listener),
    setClock: vi.fn(),
    mountOverlay: vi.fn(),
    remove: vi.fn(),
    setBuildings,
    viewBounds: () => view,
  };
  const move = async (next: ShadowView) => {
    view = next;
    await act(async () => {
      for (const listener of listeners) listener();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  };
  return { handle, setBuildings, move, listeners };
}
