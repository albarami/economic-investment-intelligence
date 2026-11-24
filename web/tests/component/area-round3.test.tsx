// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import type { FetchLike } from '../../src/api/areas';
import { AreaOutline } from '../../src/controls/AreaOutline';
import { AnswerShell } from '../../src/shell/AnswerShell';
import {
  dispatch,
  registerFetch,
  registerPort,
  releaseAreaClient,
  releasePort,
  submitArea,
} from '../../src/state/area-actions';
import { clearArea, getArea } from '../../src/state/store';
import {
  GESTURE_HANDLER_NAMES,
  type GestureBag,
} from '../../src/stage/gestures';
import {
  createHandle,
  type MapHandle,
  type MapSurface,
} from '../../src/stage/map-boot';
import { plainPort } from '../fixtures/plain-port';

const CENTRE = { longitude: 51.53, latitude: 25.28 };

describe('knob pointer ownership', () => {
  let token = 0;

  beforeEach(() => {
    clearArea();
    token = registerPort(plainPort(320, 320));
  });

  afterEach(() => {
    cleanup();
    clearArea();
    releasePort(token);
    releaseAreaClient();
  });

  function placeKnob() {
    render(<AreaOutline language="en" />);
    act(() => {
      dispatch({ type: 'select-tool', tool: 'polygon' });
      dispatch({ type: 'pointer', x: 80, y: 80, pointerType: 'touch' });
    });
    return screen.getByRole('button', { name: 'Vertex' });
  }

  it('accepts consecutive moves and ignores a hover after release', () => {
    const knob = placeKnob();
    fireEvent.pointerDown(knob, {
      pointerId: 4,
      button: 0,
      isPrimary: true,
      pointerType: 'touch',
      clientX: 80,
      clientY: 80,
    });
    fireEvent.pointerMove(knob, {
      pointerId: 4,
      pointerType: 'touch',
      clientX: 100,
      clientY: 90,
    });
    fireEvent.pointerMove(knob, {
      pointerId: 4,
      pointerType: 'touch',
      clientX: 110,
      clientY: 96,
    });
    expect(getArea().session.vertices[0]?.longitude).toBeCloseTo(110 / 320, 4);
    fireEvent.pointerUp(knob, {
      pointerId: 4,
      pointerType: 'touch',
      clientX: 110,
      clientY: 96,
    });
    fireEvent.pointerMove(knob, {
      pointerId: 4,
      pointerType: 'touch',
      clientX: 180,
      clientY: 140,
    });
    expect(getArea().session.vertices[0]?.longitude).toBeCloseTo(110 / 320, 4);
    expect(getArea().session.vertices[0]?.latitude).toBeCloseTo(96 / 320, 4);
  });

  it('drops a drag when the pointer is cancelled', () => {
    const knob = placeKnob();
    fireEvent.pointerDown(knob, {
      pointerId: 4,
      button: 0,
      isPrimary: true,
      pointerType: 'touch',
      clientX: 80,
      clientY: 80,
    });
    fireEvent.pointerMove(knob, {
      pointerId: 4,
      pointerType: 'touch',
      clientX: 110,
      clientY: 96,
    });
    fireEvent.pointerCancel(knob, { pointerId: 4, pointerType: 'touch' });
    fireEvent.pointerMove(knob, {
      pointerId: 4,
      pointerType: 'touch',
      clientX: 180,
      clientY: 140,
    });
    expect(getArea().session.vertices[0]?.longitude).toBeCloseTo(110 / 320, 4);
  });

  it('ignores a move from an unrelated pointer', () => {
    const knob = placeKnob();
    fireEvent.pointerDown(knob, {
      pointerId: 4,
      button: 0,
      isPrimary: true,
      pointerType: 'touch',
      clientX: 80,
      clientY: 80,
    });
    fireEvent.pointerMove(knob, {
      pointerId: 4,
      pointerType: 'touch',
      clientX: 110,
      clientY: 96,
    });
    fireEvent.pointerMove(knob, {
      pointerId: 9,
      pointerType: 'touch',
      clientX: 180,
      clientY: 140,
    });
    expect(getArea().session.vertices[0]?.longitude).toBeCloseTo(110 / 320, 4);
    expect(getArea().session.vertices[0]?.latitude).toBeCloseTo(96 / 320, 4);
  });

  it('drops a drag when pointer capture is lost', () => {
    const knob = placeKnob();
    fireEvent.pointerDown(knob, {
      pointerId: 4,
      button: 0,
      isPrimary: true,
      pointerType: 'touch',
      clientX: 80,
      clientY: 80,
    });
    fireEvent.pointerMove(knob, {
      pointerId: 4,
      pointerType: 'touch',
      clientX: 110,
      clientY: 96,
    });
    fireEvent.lostPointerCapture(knob, {
      pointerId: 4,
      pointerType: 'touch',
    });
    fireEvent.pointerMove(knob, {
      pointerId: 4,
      pointerType: 'touch',
      clientX: 180,
      clientY: 140,
    });
    expect(getArea().session.vertices[0]?.longitude).toBeCloseTo(110 / 320, 4);
  });
});

describe('live map drawing', () => {
  afterEach(() => {
    cleanup();
    clearArea();
    releaseAreaClient();
  });

  function recording(): {
    handle: MapHandle;
    centre: () => { longitude: number; latitude: number };
    nudgeIfLive(): void;
    deliver(type: 'move' | 'resize'): void;
    listenerCount(type: 'move' | 'resize'): number;
    suspended(): boolean;
    shift(dx: number, dy: number): void;
  } {
    const camera = {
      dx: 0,
      dy: 0,
      lng: CENTRE.longitude,
      lat: CENTRE.latitude,
    };
    let live = true;
    const listeners = new Map<string, Set<(event: unknown) => void>>();
    const handlers = {} as GestureBag;
    for (const name of GESTURE_HANDLER_NAMES) {
      handlers[name] = {
        disable() {
          live = false;
        },
        enable() {
          live = true;
        },
      };
    }
    const surface: MapSurface = {
      on(type, listener) {
        const set = listeners.get(type) ?? new Set();
        set.add(listener);
        listeners.set(type, set);
      },
      off(type, listener) {
        listeners.get(type)?.delete(listener);
      },
      project(lngLat) {
        return {
          x: 160 + (lngLat.lng - CENTRE.longitude) * 80 + camera.dx,
          y: 160 - (lngLat.lat - CENTRE.latitude) * 80 + camera.dy,
        };
      },
      unproject(point) {
        return {
          lng: CENTRE.longitude + (point.x - 160 - camera.dx) / 80,
          lat: CENTRE.latitude - (point.y - 160 - camera.dy) / 80,
        };
      },
      getCenter() {
        return { lng: camera.lng, lat: camera.lat };
      },
      remove() {},
      ...handlers,
    };
    const handle = createHandle(surface, {
      mount() {},
      remove() {},
    });
    return {
      handle,
      centre() {
        const point = handle.centre();
        return { longitude: point.longitude, latitude: point.latitude };
      },
      nudgeIfLive() {
        if (live) camera.lng += 0.2;
      },
      deliver(type) {
        for (const listener of listeners.get(type) ?? []) listener({});
      },
      listenerCount(type) {
        return listeners.get(type)?.size ?? 0;
      },
      suspended() {
        return !live;
      },
      shift(dx, dy) {
        camera.dx += dx;
        camera.dy += dy;
      },
    };
  }

  function circleFetch(): { calls: string[] } {
    const calls: string[] = [];
    const fetchLike: FetchLike = async (path, init) => {
      calls.push(init.body);
      if (path.endsWith('/shapes')) {
        return {
          status: 201,
          json: async () => ({ shape_id: 'ab'.repeat(32) }),
        };
      }
      return {
        status: 200,
        json: async () => ({
          tool: 'make_area',
          call_id: 'INVENTED-call',
          engine: 'embedded',
          blocks: [],
          facts: [],
          caveat_keys: [],
          status: 'OK',
          release_id: 'rel-draw',
          payload: {
            area_id: 'area-draw',
            outline: {
              type: 'Circle',
              coordinates: [CENTRE.longitude + 0.4, CENTRE.latitude + 0.2],
              radius_m: 250,
            },
            units: {},
            snap_report: null,
            record: {
              anchor_cell: null,
              traffic: 'free_flow',
              shape: 'circle',
            },
          },
        }),
      };
    };
    registerFetch(fetchLike);
    return { calls };
  }

  it('moves an off-centre pin and outline after a camera event', async () => {
    const map = recording();
    const view = render(
      <AnswerShell
        language="en"
        theme="dark"
        extractUrl="pmtiles://fixture.pmtiles"
        mapStarter={async () => map.handle}
      />,
    );
    await waitFor(() => {
      expect(
        view.container.querySelector('[data-state="ready"]'),
      ).not.toBeNull();
    });
    circleFetch();
    act(() => {
      dispatch({ type: 'select-tool', tool: 'radius' });
      dispatch({ type: 'pointer', x: 220, y: 80, pointerType: 'mouse' });
      dispatch({ type: 'preset', mode: 'distance', cutoff: 250 });
    });
    await act(async () => {
      await submitArea();
    });
    const pin = view.container.querySelector('[data-part="pin"]');
    const line = view.container.querySelector(
      '[data-outline="circle"] polyline',
    );
    expect(pin).not.toBeNull();
    expect(line).not.toBeNull();
    const beforeStyle = pin?.getAttribute('style');
    const beforePoints = line?.getAttribute('points');
    const geo = { ...getArea().ownPin };
    const outline = getArea().presented?.outline;
    const phase = getArea().session.phase;
    const tool = getArea().session.tool;
    map.shift(48, -20);
    act(() => {
      map.deliver('move');
    });
    expect(pin?.getAttribute('style')).not.toBe(beforeStyle);
    expect(line?.getAttribute('points')).not.toBe(beforePoints);
    expect(getArea().ownPin).toEqual(geo);
    expect(getArea().presented?.outline).toEqual(outline);
    expect(getArea().session.phase).toBe(phase);
    expect(getArea().session.tool).toBe(tool);
    expect(getArea().session.pin).toEqual(geo);
  });

  it('refreshes the frame when the map resizes', async () => {
    const map = recording();
    const view = render(
      <AnswerShell
        language="en"
        theme="dark"
        extractUrl="pmtiles://fixture.pmtiles"
        mapStarter={async () => map.handle}
      />,
    );
    await waitFor(() => {
      expect(
        view.container.querySelector('[data-state="ready"]'),
      ).not.toBeNull();
    });
    const host = view.container.querySelector('.stage-host');
    expect(host).not.toBeNull();
    Object.defineProperty(host, 'clientWidth', {
      configurable: true,
      value: 480,
    });
    Object.defineProperty(host, 'clientHeight', {
      configurable: true,
      value: 240,
    });
    const pinBefore = getArea().session.pin;
    act(() => {
      map.deliver('resize');
    });
    expect(getArea().session.frameWidth).toBe(480);
    expect(getArea().session.frameHeight).toBe(240);
    expect(getArea().session.pin).toEqual(pinBefore);
    expect(map.listenerCount('move')).toBeGreaterThan(0);
    expect(map.listenerCount('resize')).toBeGreaterThan(0);
  });

  it('keeps the camera still while drawing and restores it after Escape, submission and unmount', async () => {
    const map = recording();
    const calls: string[] = [];
    registerFetch(async (path, init) => {
      calls.push(init.body);
      if (path.endsWith('/shapes')) {
        return {
          status: 201,
          json: async () => ({ shape_id: 'cd'.repeat(32) }),
        };
      }
      return {
        status: 200,
        json: async () => ({
          tool: 'make_area',
          call_id: 'INVENTED-call',
          engine: 'embedded',
          blocks: [],
          facts: [],
          caveat_keys: [],
          status: 'OK',
          release_id: 'rel-draw',
          payload: {
            area_id: 'area-draw',
            outline: {
              type: 'Polygon',
              coordinates: [
                [
                  [0, 0],
                  [1, 0],
                  [1, 1],
                  [0, 0],
                ],
              ],
            },
            units: {},
            snap_report: null,
            record: {
              anchor_cell: null,
              traffic: 'free_flow',
              shape: 'polygon',
            },
          },
        }),
      };
    });
    const view = render(
      <AnswerShell
        language="en"
        theme="dark"
        extractUrl="pmtiles://fixture.pmtiles"
        mapStarter={async () => map.handle}
      />,
    );
    await waitFor(() => {
      expect(
        view.container.querySelector('[data-state="ready"]'),
      ).not.toBeNull();
    });
    const origin = map.centre();
    act(() => {
      dispatch({ type: 'select-tool', tool: 'polygon' });
    });
    expect(map.suspended()).toBe(true);
    map.nudgeIfLive();
    expect(map.centre()).toEqual(origin);
    fireEvent.keyDown(screen.getByRole('button', { name: 'Crosshair' }), {
      key: 'Enter',
    });
    fireEvent.keyDown(screen.getByRole('button', { name: 'Crosshair' }), {
      key: 'ArrowRight',
    });
    expect(map.centre()).toEqual(origin);
    act(() => {
      dispatch({ type: 'escape' });
    });
    expect(map.suspended()).toBe(false);
    expect(
      view.container
        .querySelector('.area-overlay')
        ?.classList.contains('is-live'),
    ).toBe(false);
    map.nudgeIfLive();
    expect(map.centre()).not.toEqual(origin);

    const again = map.centre();
    act(() => {
      dispatch({ type: 'select-tool', tool: 'polygon' });
      dispatch({ type: 'pointer', x: 40, y: 40, pointerType: 'touch' });
      dispatch({ type: 'pointer', x: 120, y: 48, pointerType: 'touch' });
      dispatch({ type: 'pointer', x: 130, y: 140, pointerType: 'touch' });
    });
    expect(map.suspended()).toBe(true);
    map.nudgeIfLive();
    expect(map.centre()).toEqual(again);
    const knob = screen.getAllByRole('button', { name: 'Vertex' })[1];
    expect(knob).toBeDefined();
    fireEvent.pointerDown(knob as HTMLElement, {
      pointerId: 3,
      button: 0,
      isPrimary: true,
      pointerType: 'touch',
      clientX: 120,
      clientY: 48,
    });
    fireEvent.pointerMove(knob as HTMLElement, {
      pointerId: 3,
      pointerType: 'touch',
      clientX: 150,
      clientY: 70,
    });
    fireEvent.pointerUp(knob as HTMLElement, {
      pointerId: 3,
      pointerType: 'touch',
      clientX: 150,
      clientY: 70,
    });
    fireEvent.pointerDown(
      screen.getAllByRole('button', { name: 'Vertex' })[0] as HTMLElement,
      {
        pointerId: 3,
        button: 0,
        isPrimary: true,
        pointerType: 'touch',
        clientX: 40,
        clientY: 40,
      },
    );
    fireEvent.click(
      screen.getAllByRole('button', { name: 'Vertex' })[0] as HTMLElement,
    );
    expect(getArea().session.closed).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Use this area' }));
    await waitFor(() => {
      expect(calls.length).toBeGreaterThan(0);
    });
    const shaped = JSON.parse(calls[0] ?? '{}') as {
      geometry?: { coordinates?: number[][][] };
    };
    const ring = shaped.geometry?.coordinates?.[0] ?? [];
    const edited = ring[1];
    expect(edited?.[0]).toBeCloseTo(
      map.handle.unproject({ x: 150, y: 70 }).longitude,
      4,
    );
    expect(edited?.[1]).toBeCloseTo(
      map.handle.unproject({ x: 150, y: 70 }).latitude,
      4,
    );
    expect(
      view.container.querySelector('[data-part="no-mode"]'),
    ).not.toBeNull();
    expect(map.suspended()).toBe(false);
    expect(map.centre()).toEqual(again);
    expect(
      view.container
        .querySelector('.area-overlay')
        ?.classList.contains('is-live'),
    ).toBe(false);

    act(() => {
      dispatch({ type: 'select-tool', tool: 'radius' });
    });
    expect(map.suspended()).toBe(true);
    expect(map.listenerCount('move')).toBeGreaterThan(0);
    expect(map.listenerCount('resize')).toBeGreaterThan(0);
    view.unmount();
    expect(map.suspended()).toBe(false);
    expect(map.listenerCount('move')).toBe(0);
    expect(map.listenerCount('resize')).toBe(0);
  });
});
