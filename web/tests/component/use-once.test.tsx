// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import {
  MAKE_AREA_PATH,
  SHAPES_PATH,
  type FetchLike,
} from '../../src/api/areas';
import { AnswerShell } from '../../src/shell/AnswerShell';
import {
  registerFetch,
  registerPort,
  releaseAreaClient,
  releasePort,
} from '../../src/state/area-actions';
import { clearArea } from '../../src/state/store';
import { plainPort } from '../fixtures/plain-port';

const SHAPE_ID = 'ab'.repeat(32);

interface HeldFetch {
  fetchLike: FetchLike;
  paths: () => string[];
  bodies: () => string[];
  releaseAll: () => Promise<void>;
}

function heldFetch(): HeldFetch {
  const requests: { path: string; body: string }[] = [];
  const waiters: Array<() => void> = [];
  const fetchLike: FetchLike = async (path, init) => {
    requests.push({ path, body: init.body });
    await new Promise<void>((resolve) => {
      waiters.push(resolve);
    });
    if (path.endsWith('/shapes')) {
      return { status: 201, json: async () => ({ shape_id: SHAPE_ID }) };
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
            coordinates: [0.5, 0.5],
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
  return {
    fetchLike,
    paths: () => requests.map((item) => item.path),
    bodies: () => requests.map((item) => item.body),
    releaseAll: async () => {
      for (let turn = 0; turn < 8; turn += 1) {
        if (waiters.length === 0) return;
        const batch = waiters.splice(0, waiters.length);
        await act(async () => {
          for (const resolve of batch) resolve();
          await Promise.resolve();
        });
      }
    },
  };
}

function findUseButton(): HTMLElement {
  return screen.getByRole('button', { name: 'Use this area' });
}

function prepareRadius(): void {
  fireEvent.click(screen.getByRole('button', { name: 'Radius' }));
  fireEvent.keyDown(screen.getByRole('button', { name: 'Crosshair' }), {
    key: 'Enter',
  });
  const preset = document.querySelector('[data-preset="distance-a"]');
  expect(preset).not.toBeNull();
  fireEvent.click(preset as Element);
}

function preparePolygon(): void {
  fireEvent.click(screen.getByRole('button', { name: 'Polygon' }));
  const overlay = document.querySelector('.area-overlay');
  expect(overlay).not.toBeNull();
  for (const point of [
    { clientX: 40, clientY: 40 },
    { clientX: 120, clientY: 40 },
    { clientX: 120, clientY: 120 },
  ]) {
    fireEvent.pointerDown(overlay as Element, {
      isPrimary: true,
      pointerType: 'touch',
      button: 0,
      ...point,
    });
  }
  fireEvent.click(
    screen.getAllByRole('button', { name: 'Vertex' })[0] as HTMLElement,
  );
}

function pointerGesture(pointerType: 'touch' | 'pen' | 'mouse'): void {
  const button = findUseButton();
  fireEvent.pointerDown(button, { pointerType, pointerId: 1, button: 0 });
  fireEvent.pointerUp(button, { pointerType, pointerId: 1, button: 0 });
}

function expectOneValidPair(
  paths: readonly string[],
  bodies: readonly string[],
  tool: 'radius' | 'polygon',
): void {
  if (tool === 'radius') {
    expect(paths).toEqual([MAKE_AREA_PATH]);
    const body = JSON.parse(bodies[0] ?? '{}') as {
      mode?: string;
      cutoff?: number;
      pin?: unknown;
    };
    expect(body).toMatchObject({ mode: 'distance', cutoff: 250 });
    expect(body.pin).toBeUndefined();
    expect(JSON.stringify(body)).not.toContain('situation');
    return;
  }
  expect(paths).toEqual([SHAPES_PATH, MAKE_AREA_PATH]);
  const shape = JSON.parse(bodies[0] ?? '{}') as {
    geometry?: { type?: string };
  };
  expect(shape.geometry?.type).toBe('Polygon');
  const made = JSON.parse(bodies[1] ?? '{}') as { shape_id?: unknown };
  expect(made.shape_id).toBe(SHAPE_ID);
  expect(JSON.stringify(made)).not.toContain('situation');
}

describe.each(['radius', 'polygon'] as const)(
  'Use submits once (%s)',
  (tool) => {
    let token = 0;
    let held: HeldFetch | null = null;

    beforeEach(() => {
      clearArea();
      token = registerPort(plainPort(320, 320));
      held = heldFetch();
      registerFetch(held.fetchLike);
      render(<AnswerShell language="en" theme="dark" extractUrl={null} />);
      if (tool === 'radius') prepareRadius();
      else preparePolygon();
    });

    afterEach(async () => {
      await held?.releaseAll();
      held = null;
      cleanup();
      clearArea();
      releasePort(token);
      releaseAreaClient();
    });

    it('counts one request when a touch click arrives before completion', async () => {
      const fetchHold = held as HeldFetch;
      pointerGesture('touch');
      fireEvent.click(findUseButton(), { detail: 1 });
      if (tool === 'radius')
        expect(fetchHold.paths()).toEqual([MAKE_AREA_PATH]);
      else expect(fetchHold.paths()).toEqual([SHAPES_PATH]);
      await fetchHold.releaseAll();
      expectOneValidPair(fetchHold.paths(), fetchHold.bodies(), tool);
    });

    it('counts one request when a touch click arrives after completion', async () => {
      const fetchHold = held as HeldFetch;
      pointerGesture('touch');
      await fetchHold.releaseAll();
      const settled = fetchHold.paths().slice();
      fireEvent.click(findUseButton(), { detail: 1 });
      await fetchHold.releaseAll();
      expect(fetchHold.paths()).toEqual(settled);
      expectOneValidPair(fetchHold.paths(), fetchHold.bodies(), tool);
    });

    it('counts one request when a pen click arrives after completion', async () => {
      const fetchHold = held as HeldFetch;
      pointerGesture('pen');
      await fetchHold.releaseAll();
      fireEvent.click(findUseButton(), { detail: 1 });
      await fetchHold.releaseAll();
      expectOneValidPair(fetchHold.paths(), fetchHold.bodies(), tool);
    });

    it('counts one request for a touch pointerup with no click', async () => {
      const fetchHold = held as HeldFetch;
      pointerGesture('touch');
      expect(fetchHold.paths().length).toBeGreaterThan(0);
      await fetchHold.releaseAll();
      expectOneValidPair(fetchHold.paths(), fetchHold.bodies(), tool);
      pointerGesture('mouse');
      fireEvent.click(findUseButton(), { detail: 1 });
      await fetchHold.releaseAll();
      expect(
        fetchHold.paths().filter((path) => path === MAKE_AREA_PATH),
      ).toHaveLength(2);
      expect(
        fetchHold.paths().filter((path) => path === SHAPES_PATH),
      ).toHaveLength(tool === 'polygon' ? 2 : 0);
    });

    it('counts one request for a mouse pointerup plus click', async () => {
      const fetchHold = held as HeldFetch;
      pointerGesture('mouse');
      expect(fetchHold.paths()).toEqual([]);
      fireEvent.click(findUseButton(), { detail: 1 });
      await fetchHold.releaseAll();
      expectOneValidPair(fetchHold.paths(), fetchHold.bodies(), tool);
    });

    it.each(['Enter', ' '] as const)(
      'counts one request for keyboard %s',
      async (key) => {
        const fetchHold = held as HeldFetch;
        const button = findUseButton();
        button.focus();
        fireEvent.keyDown(button, { key });
        fireEvent.keyUp(button, { key });
        fireEvent.click(button, { detail: 0 });
        await fetchHold.releaseAll();
        expectOneValidPair(fetchHold.paths(), fetchHold.bodies(), tool);
      },
    );

    it('counts two requests for two separate touch gestures', async () => {
      const fetchHold = held as HeldFetch;
      pointerGesture('touch');
      await fetchHold.releaseAll();
      fireEvent.click(findUseButton(), { detail: 1 });
      pointerGesture('touch');
      await fetchHold.releaseAll();
      fireEvent.click(findUseButton(), { detail: 1 });
      await fetchHold.releaseAll();
      if (tool === 'radius') {
        expect(fetchHold.paths()).toEqual([MAKE_AREA_PATH, MAKE_AREA_PATH]);
      } else {
        expect(fetchHold.paths()).toEqual([
          SHAPES_PATH,
          MAKE_AREA_PATH,
          SHAPES_PATH,
          MAKE_AREA_PATH,
        ]);
      }
    });
  },
);
