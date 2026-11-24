// @vitest-environment jsdom
/**
 * S3-T16 in the mounted stage: the fixed heights read, the shadow selection on
 * every view change, building updates through the map handle, picking and the
 * legend. Invented buildings SYN-B-* from the route's own fixture body.
 */
import { act, cleanup, render, waitFor } from '@testing-library/react';
import type { Layer, PickingInfo } from '@deck.gl/core';
import { afterEach, expect, it, vi } from 'vitest';

import { text } from '../../src/i18n';
import { Stage } from '../../src/stage/Stage';
import {
  BUILDINGS_LAYER,
  PROVISIONAL_BUILDING_CAP,
  SHADOWS_LAYER,
  type BuildingRow,
} from '../../src/stage/buildings3d';
import type { MapHandle } from '../../src/stage/map-boot';
import { heightsBody } from '../fixtures/building-heights';
import { EMPTY, fakeMap, serve } from '../fixtures/building-stage';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function keys(layer: Layer | undefined): string[] {
  return ((layer?.props.data ?? []) as BuildingRow[]).map(
    (row) => row.building_key,
  );
}

function stage(handle: MapHandle, buildingCap?: number) {
  const starter = () => handle;
  const props = {
    language: 'en' as const,
    theme: 'dark' as const,
    extractUrl: '/SYN-map.pmtiles',
    dayBasis: '2026-06-01',
    mapStarter: starter,
    buildingCap,
  };
  const view = render(<Stage {...props} />);
  return {
    ...view,
    quiet: () => view.rerender(<Stage {...props} quiet />),
  };
}

it('reads the heights, draws own-height buildings with capped shadows and mounts the legend', async () => {
  serve(heightsBody());
  const map = fakeMap();
  const view = stage(map.handle, 2);
  await waitFor(() =>
    expect(
      view.container.querySelector('[data-part="buildings-legend"]'),
    ).not.toBeNull(),
  );
  await waitFor(() =>
    expect(
      view.container.querySelector('[data-words="shadow-limited"]')
        ?.textContent,
    ).toBe(text('en', 'buildings.shadowLimited')),
  );
  const [layers, cap] = map.setBuildings.mock.lastCall!;
  expect(cap).toBe(2);
  expect(layers.map((layer) => layer.id)).toEqual([
    BUILDINGS_LAYER,
    SHADOWS_LAYER,
  ]);
  expect(keys(layers[1])).toEqual(['SYN-B-0004', 'SYN-B-0005']);
  expect(keys(layers[0])).toEqual(['SYN-B-0001']);
  expect(
    view.container.querySelector('[data-words="heights-estimates"]')
      ?.textContent,
  ).toBe(text('en', 'buildings.estimates'));
});

it('selects again when the view moves, and a view with no building casts none', async () => {
  serve(heightsBody());
  const map = fakeMap();
  const view = stage(map.handle);
  await waitFor(() => expect(map.setBuildings).toHaveBeenCalled());
  expect(map.setBuildings.mock.lastCall![1]).toBe(PROVISIONAL_BUILDING_CAP);
  await waitFor(() =>
    expect(
      view.container.querySelector('[data-words="shadow-estimated"]'),
    ).not.toBeNull(),
  );
  await map.move(EMPTY);
  expect(keys(map.setBuildings.mock.lastCall![0][1])).toEqual([]);
  expect(
    view.container.querySelector('[data-words="shadow-estimated"]'),
  ).toBeNull();
  expect(
    view.container.querySelector('[data-words="shadow-limited"]'),
  ).toBeNull();
  const calls = map.setBuildings.mock.calls.length;
  await map.move({ ...EMPTY, centre: [51.201, 25.1] });
  // The same selection is not drawn twice.
  expect(map.setBuildings.mock.calls.length).toBe(calls);
});

it('a picked building opens its own source in More evidence', async () => {
  serve(heightsBody());
  const map = fakeMap();
  const view = stage(map.handle);
  await waitFor(() => expect(map.setBuildings).toHaveBeenCalled());
  const shadows = map.setBuildings.mock.lastCall![0][1]!;
  const picked = (shadows.props.data as BuildingRow[]).find(
    (row) => row.height_source === 'wsf3d',
  )!;
  const onClick = shadows.props.onClick as (
    info: PickingInfo<BuildingRow>,
  ) => void;
  act(() => onClick({ object: picked } as PickingInfo<BuildingRow>));
  await waitFor(() =>
    expect(
      view.container.querySelector(
        '[data-part="building-evidence"] [data-height-source="wsf3d"]',
      ),
    ).not.toBeNull(),
  );
});

it('a refused read draws no building and mounts no legend', async () => {
  const body = heightsBody();
  const entry = body.fallback_errors[0] as Record<string, unknown>;
  [entry.mean_signed_fact_id, entry.mean_abs_fact_id] = [
    entry.mean_abs_fact_id,
    entry.mean_signed_fact_id,
  ];
  serve(body);
  const map = fakeMap();
  const view = stage(map.handle);
  await waitFor(() =>
    expect(
      view.container.querySelector('.stage')?.getAttribute('data-state'),
    ).toBe('ready'),
  );
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  expect(map.setBuildings).not.toHaveBeenCalled();
  expect(
    view.container.querySelector('[data-part="buildings-legend"]'),
  ).toBeNull();
});

it('unbinds its view listener and clears the buildings when the stage goes quiet', async () => {
  serve(heightsBody());
  const map = fakeMap();
  const view = stage(map.handle);
  await waitFor(() => expect(map.listeners.size).toBe(2));
  view.quiet();
  await waitFor(() => expect(map.listeners.size).toBe(1));
  expect(map.setBuildings.mock.lastCall![0]).toEqual([]);
  expect(
    view.container.querySelector('[data-part="buildings-legend"]'),
  ).toBeNull();
});

it('a map that cannot draw buildings never requests the heights', async () => {
  const fetcher = serve(heightsBody());
  const map = fakeMap();
  const plain: MapHandle = { ...map.handle, setBuildings: undefined };
  const view = stage(plain);
  await waitFor(() =>
    expect(
      view.container.querySelector('.stage')?.getAttribute('data-state'),
    ).toBe('ready'),
  );
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  const paths = fetcher.mock.calls.map((call) => call[0]);
  expect(paths).not.toContain('/api/building-heights');
  expect(
    view.container.querySelector('[data-part="buildings-legend"]'),
  ).toBeNull();
});
