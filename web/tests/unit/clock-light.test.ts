// @vitest-environment jsdom
import { expect, it, vi } from 'vitest';
import { _SunLight as SunLight, WebMercatorViewport } from '@deck.gl/core';
import { ScatterplotLayer } from '@deck.gl/layers';
import { clockTimestamp } from '../../src/stage/clock';
import {
  ClockLight,
  lightPosition,
  nightVisible,
} from '../../src/stage/clock-light';

it('converts incoming sun direction to map-anchored angles and uses the horizon without a dusk threshold', () => {
  expect(lightPosition([0, 0, -1])).toEqual([1, 180, 0]);
  expect(lightPosition([-1, 0, 0])).toEqual([1, 90, 90]);
  expect(lightPosition([0, 1, 0])).toEqual([1, 180, 90]);
  expect(nightVisible([0, 0, -1])).toBe(false);
  expect(nightVisible([0, 0, 0])).toBe(false);
  expect(nightVisible([0, 0, Number.EPSILON])).toBe(true);
});
it('uses the pinned sun calculation on the supplied day and fraction, at any viewport', () => {
  const layer = new ScatterplotLayer({ id: 'SYN-fixture' });
  // Fixture context exercises the actual pinned sun calculation without WebGL.
  layer.context = {
    ...layer.context,
    viewport: new WebMercatorViewport({ longitude: 0, latitude: 0 }),
  };
  const report = vi.fn();
  for (const fraction of [0, 0.25, 0.5, 1]) {
    const timestamp = clockTimestamp('2026-06-01', fraction)!;
    const sun = new ClockLight(timestamp, report);
    const result = sun.getProjectedLight({ layer });
    const expected = new SunLight({ timestamp }).getProjectedLight({ layer });
    expect(result.direction).toEqual(expected.direction);
    expect(report).toHaveBeenLastCalledWith(result.direction);
  }
  expect(report.mock.calls[0]).not.toEqual(report.mock.calls[2]);
});

it('drives light and sky without a data-hour setter, and toggles just the existing night layer', async () => {
  const { attachClock } = await import('../../src/stage/layers/overlay');
  const { MapLibreOverlay } = await import('@deck.gl/maplibre');
  const night = new ScatterplotLayer({ id: 'night_lights:fixture', data: [] });
  const other = new ScatterplotLayer({ id: 'public_places:fixture', data: [] });
  const overlay = new MapLibreOverlay({
    interleaved: true,
    layers: [night, other],
  });
  const setProps = vi.spyOn(overlay, 'setProps');
  const setLight = vi.fn();
  const setSky = vi.fn();
  const clock = attachClock(overlay, [night, other]);
  const originalAdd = vi
    .spyOn(overlay, 'onAdd')
    .mockReturnValue({} as HTMLDivElement);
  // Drive the geometry-only hook with the actual pinned calculation's vector.
  clock.applySun([0, 0, 1], { setLight, setSky });
  expect(setLight).toHaveBeenCalledWith(
    expect.objectContaining({
      anchor: 'map',
      'position-transition': { duration: 0, delay: 0 },
    }),
  );
  expect(setSky).toHaveBeenCalledWith(
    expect.objectContaining({ 'atmosphere-blend': 0 }),
  );
  expect(setProps.mock.lastCall![0].layers[0].props.visible).toBe(true);
  expect(setProps.mock.lastCall![0].layers[1]).toBe(other);
  clock.applySun([0, 0, -1], { setLight, setSky });
  expect(setProps.mock.lastCall![0].layers[0].props.opacity).toBe(0);
  expect(setProps.mock.lastCall![0].layers[1]).toBe(other);
  expect(setSky).toHaveBeenLastCalledWith(
    expect.objectContaining({ 'atmosphere-blend': 1 }),
  );
  originalAdd.mockRestore();
});

it('fades only radiance with the documented scene token and disables the fade under reduced motion', async () => {
  const { readFileSync } = await import('node:fs');
  const style = document.createElement('style');
  style.textContent = readFileSync('src/styles/tokens.css', 'utf8');
  document.head.append(style);
  const { attachClock } = await import('../../src/stage/layers/overlay');
  const { MapLibreOverlay } = await import('@deck.gl/maplibre');
  const layer = new ScatterplotLayer({ id: 'night_lights:fixture', data: [] });
  for (const reduced of [false, true]) {
    vi.stubGlobal('matchMedia', () => ({ matches: reduced }));
    const overlay = new MapLibreOverlay({ layers: [layer] });
    const props = vi.spyOn(overlay, 'setProps');
    const clock = attachClock(overlay, [layer]);
    const target = { setLight: vi.fn(), setSky: vi.fn() };
    clock.applySun([0, 0, 1], target);
    expect(props.mock.lastCall![0].layers[0].props.transitions).toEqual({
      opacity: reduced ? 0 : 800,
    });
    expect(props.mock.lastCall![0].layers[0].props.opacity).toBe(1);
    clock.applySun([0, 0, -1], target);
    expect(props.mock.lastCall![0].layers[0].props.opacity).toBe(0);
    expect(props.mock.lastCall![0].layers[0].props.pickable).toBe(false);
    expect(props.mock.lastCall![0].layers[0].props.visible).toBe(true);
    clock.setClock(clockTimestamp('2026-06-01', 0)!);
    expect(props.mock.lastCall![0].layers[0].props.opacity).toBe(0);
    clock.applySun([0, 0, -1], target);
    expect(target.setLight).toHaveBeenCalledTimes(3);
  }
  style.remove();
  vi.unstubAllGlobals();
});
