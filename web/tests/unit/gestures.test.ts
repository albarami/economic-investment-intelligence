import { describe, expect, it } from 'vitest';

import {
  GESTURE_HANDLER_NAMES,
  restoreNamed,
  suspendNamed,
  type GestureBag,
} from '../../src/stage/gestures';
import { createHandle, type MapSurface } from '../../src/stage/map-boot';

function bag(): {
  handlers: GestureBag;
  disabled: string[];
  enabled: string[];
} {
  const disabled: string[] = [];
  const enabled: string[] = [];
  const handlers = {} as GestureBag;
  for (const name of GESTURE_HANDLER_NAMES) {
    handlers[name] = {
      disable() {
        disabled.push(name);
      },
      enable() {
        enabled.push(name);
      },
    };
  }
  return { handlers, disabled, enabled };
}

describe('gesture handle', () => {
  it('suspends and restores the named handlers and never returns the map', () => {
    const made = bag();
    suspendNamed(made.handlers);
    restoreNamed(made.handlers);
    expect(made.disabled).toEqual([...GESTURE_HANDLER_NAMES]);
    expect(made.enabled).toEqual([...GESTURE_HANDLER_NAMES]);
    const surface: MapSurface = {
      on() {},
      off() {},
      project() {
        return { x: 0, y: 0 };
      },
      unproject() {
        return { lng: 0, lat: 0 };
      },
      getCenter() {
        return { lng: 0.5, lat: 0.4 };
      },
      remove() {},
      ...made.handlers,
    };
    const handle = createHandle(surface, {
      mount() {},
      remove() {},
    });
    expect(Object.hasOwn(handle, 'map')).toBe(false);
    expect(handle.centre()).toEqual({ longitude: 0.5, latitude: 0.4 });
    handle.suspendGestures();
    expect(made.disabled).toHaveLength(GESTURE_HANDLER_NAMES.length * 2);
  });

  it('hands the listener primitives and never the map target', () => {
    const map = { kind: 'map-object' };
    let received: unknown = null;
    let bound: ((event: unknown) => void) | null = null;
    let unbound: ((event: unknown) => void) | null = null;
    const surface: MapSurface = {
      on(_type, listener) {
        bound = listener;
      },
      off(_type, listener) {
        unbound = listener;
      },
      project() {
        return { x: 0, y: 0 };
      },
      unproject() {
        return { lng: 0, lat: 0 };
      },
      getCenter() {
        return { lng: 0, lat: 0 };
      },
      remove() {},
      ...bag().handlers,
    };
    const handle = createHandle(surface, {
      mount() {},
      remove() {},
    });
    const listener = (event: unknown) => {
      received = event;
    };
    handle.bind('click', listener);
    const raw = {
      type: 'click',
      point: { x: 4, y: 9 },
      lngLat: { lng: 51.5, lat: 25.3 },
      target: map,
      originalEvent: { key: 'Enter', target: map },
    };
    expect(bound).not.toBeNull();
    bound?.(raw);
    expect(received).not.toBe(raw);
    expect(received).toEqual({
      type: 'click',
      x: 4,
      y: 9,
      longitude: 51.5,
      latitude: 25.3,
      key: 'Enter',
    });
    expect(JSON.stringify(received)).not.toContain('map-object');
    handle.unbind('click', listener);
    expect(unbound).toBe(bound);
  });
});
