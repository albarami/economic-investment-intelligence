// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Stage } from '../../src/stage/Stage';
import { resetArea } from '../../src/state/area-actions';
import {
  chooseUse,
  readUseChoice,
  resetUseChoice,
} from '../../src/stage/layers/land-use';
import { operationalMeter } from '../fixtures/operational-meter';
import { sceneRegistry } from '../fixtures/layer-registry';
import { basePayload } from '../fixtures/layers';
import type { LayerPayload } from '../../src/stage/layers/payload';

afterEach(() => {
  cleanup();
  resetUseChoice();
  vi.unstubAllGlobals();
});
it('the quiet opening withholds the selected overlay until the area scene', async () => {
  vi.stubGlobal('fetch', async () => ({ ok: false }));
  const handle = {
    remove: vi.fn(),
    mountOverlay: vi.fn(),
    bind: vi.fn(),
    unbind: vi.fn(),
    project: () => ({ x: 0, y: 0 }),
    unproject: () => ({ longitude: 0, latitude: 0 }),
    suspendGestures: vi.fn(),
    restoreGestures: vi.fn(),
    centre: () => ({ longitude: 0, latitude: 0 }),
    bindView: vi.fn(),
    unbindView: vi.fn(),
  };
  const start = vi.fn(() => handle);
  const registry = sceneRegistry();
  const payload: LayerPayload = basePayload();
  const overlay = vi.fn(() => ({
    onAdd: () => document.createElement('div'),
    onRemove: vi.fn(),
  }));
  const view = render(
    <Stage
      language="en"
      theme="dark"
      extractUrl="/INVENTED.pmtiles"
      layerPayload={payload}
      registry={registry}
      mapStarter={start}
      overlayFactory={overlay}
      quiet
      compactControls
    />,
  );
  await waitFor(() =>
    expect(
      view.container.querySelector('.stage')?.getAttribute('data-state'),
    ).toBe('ready'),
  );
  expect(overlay).not.toHaveBeenCalled();
  expect(view.container.querySelector('.layer-inspector')).toBeNull();
  expect(
    view.container.querySelector('[data-action="source-chain"]'),
  ).toBeNull();
  view.rerender(
    <Stage
      language="en"
      theme="dark"
      extractUrl="/INVENTED.pmtiles"
      layerPayload={payload}
      registry={registry}
      mapStarter={start}
      overlayFactory={overlay}
      compactControls
    />,
  );
  await waitFor(() => expect(overlay).toHaveBeenCalledWith(payload, registry));
  expect(view.container.querySelector('.layer-inspector')).not.toBeNull();
  expect(
    view.container.querySelector('[data-action="source-chain"]'),
  ).not.toBeNull();
  expect(start).toHaveBeenCalledTimes(1);
});

it('the quiet asset-absent stage also withholds its layer disclosure', () => {
  vi.stubGlobal('fetch', async () => ({ ok: false }));
  const view = render(
    <Stage
      language="en"
      theme="dark"
      extractUrl={null}
      layerPayload={basePayload()}
      registry={sceneRegistry()}
      compactControls
      quiet
    />,
  );
  expect(
    view.container.querySelector('.stage')?.getAttribute('data-state'),
  ).toBe('asset-absent');
  expect(view.container.querySelector('.layer-inspector')).toBeNull();
  expect(
    view.container.querySelector('[data-action="source-chain"]'),
  ).toBeNull();
});
it('Reset clears mode, clock input and land-use selection on the same map', async () => {
  vi.stubGlobal('fetch', async () => ({
    ok: true,
    json: async () => ({
      open: { available: true, reason: null },
      satellite: { available: false, reason: 'no_key' },
      photoreal: { available: true, reason: null, meter: operationalMeter },
    }),
  }));
  const seen: string[] = [];
  const start = vi.fn(() => ({
    remove: vi.fn(),
    mountOverlay: vi.fn(),
    bind: vi.fn(),
    unbind: vi.fn(),
    project: () => ({ x: 0, y: 0 }),
    unproject: () => ({ longitude: 0, latitude: 0 }),
    suspendGestures: vi.fn(),
    restoreGestures: vi.fn(),
    centre: () => ({ longitude: 0, latitude: 0 }),
    bindView: vi.fn(),
    unbindView: vi.fn(),
    setMode: async (mode: string) => {
      seen.push(mode);
    },
    setClock: vi.fn(),
    camera: vi.fn(),
  }));
  const view = render(
    <Stage
      language="en"
      theme="dark"
      extractUrl="/INVENTED.pmtiles"
      mapStarter={start}
    />,
  );
  const photo = await view.findByRole('radio', { name: 'Photorealistic view' });
  await waitFor(() => expect(photo.hasAttribute('disabled')).toBe(false));
  const clock = view.getByRole('textbox', {
    name: 'Your inputs',
  }) as HTMLInputElement;
  fireEvent.change(clock, { target: { value: '0.5' } });
  expect(clock.value).toBe('0.5');
  fireEvent.click(photo);
  await waitFor(() => expect(seen.at(-1)).toBe('photoreal'));
  chooseUse('INVENTED-use');
  act(() => resetArea());
  await waitFor(() => expect(seen.at(-1)).toBe('open'));
  expect(readUseChoice()).toEqual({ kind: 'initial' });
  expect(clock.value).toBe('0');
  expect(start.mock.results[0]!.value.setClock.mock.calls.at(-1)).toEqual(
    start.mock.results[0]!.value.setClock.mock.calls[0],
  );
  expect(start).toHaveBeenCalledTimes(1);
});
