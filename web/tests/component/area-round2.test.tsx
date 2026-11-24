// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { catalogue, type AnswerDraft } from '../../src/brief/catalogue';
import { AreaOutline } from '../../src/controls/AreaOutline';
import type { MapPort } from '../../src/controls/draw-session';
import { AnswerShell } from '../../src/shell/AnswerShell';
import {
  dispatch,
  registerFetch,
  registerPort,
  releaseAreaClient,
  releasePort,
  setFrame,
} from '../../src/state/area-actions';
import { plainPort } from '../fixtures/plain-port';
import { clearArea, getArea } from '../../src/state/store';
import { Stage } from '../../src/stage/Stage';
import type { MapHandle } from '../../src/stage/map-boot';
import { basePayload } from '../fixtures/layers';
import { completeRegistry, factId } from '../fixtures/facts';
import { sceneRegistry } from '../fixtures/layer-registry';

const CENTRE = { longitude: 51.53, latitude: 25.28 };

function camera(scale: number, width = 320, height = 320): MapPort {
  return {
    unproject(point) {
      return {
        longitude: CENTRE.longitude + (point.x - width / 2) / scale,
        latitude: CENTRE.latitude - (point.y - height / 2) / scale,
      };
    },
    project(vertex) {
      return {
        x: width / 2 + (vertex.longitude - CENTRE.longitude) * scale,
        y: height / 2 - (vertex.latitude - CENTRE.latitude) * scale,
      };
    },
    suspendGestures() {},
    restoreGestures() {},
    centre() {
      return CENTRE;
    },
  };
}

function draft(): AnswerDraft {
  return {
    catalogueVersion: catalogue.version,
    accountingPassed: true,
    subject: 'area',
    componentKey: 'foundation_note',
    props: [],
    directive: null,
    slots: [
      {
        factId: factId(0),
        provenance: 'public',
        metric: 'people',
      },
    ],
  };
}

describe('round 2 area drawing', () => {
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
    vi.unstubAllGlobals();
  });

  it('keeps a registered geographic projection when the frame is measured', () => {
    token = registerPort(camera(100));
    setFrame(400, 300);
    dispatch({ type: 'select-tool', tool: 'radius' });
    dispatch({ type: 'pointer', x: 160, y: 160, pointerType: 'mouse' });
    expect(getArea().session.pin?.longitude).toBeCloseTo(CENTRE.longitude, 4);
    expect(getArea().session.pin?.latitude).toBeCloseTo(CENTRE.latitude, 4);
  });

  it('keeps the same knob focused across consecutive arrow presses', () => {
    const view = render(<AreaOutline language="en" />);
    act(() => {
      dispatch({ type: 'select-tool', tool: 'polygon' });
      dispatch({ type: 'pointer', x: 40, y: 40, pointerType: 'pen' });
    });
    const knob = screen.getByRole('button', { name: 'Vertex' });
    knob.focus();
    fireEvent.keyDown(knob, { key: 'ArrowRight' });
    fireEvent.keyDown(knob, { key: 'ArrowRight' });
    expect(document.activeElement).toBe(knob);
    expect(view.container.querySelector('[data-part="knob"]')).toBe(knob);
    expect(getArea().session.vertices[0]?.longitude).toBeGreaterThan(40 / 320);
  });

  it('drags one knob twice by touch without replacing the button', () => {
    render(<AreaOutline language="en" />);
    act(() => {
      dispatch({ type: 'select-tool', tool: 'polygon' });
      dispatch({ type: 'pointer', x: 80, y: 80, pointerType: 'touch' });
    });
    const knob = screen.getByRole('button', { name: 'Vertex' });
    fireEvent.pointerDown(knob, {
      pointerId: 1,
      button: 0,
      isPrimary: true,
      pointerType: 'touch',
      clientX: 80,
      clientY: 80,
      buttons: 1,
    });
    fireEvent.pointerMove(knob, {
      pointerId: 1,
      pointerType: 'touch',
      clientX: 110,
      clientY: 90,
      buttons: 1,
    });
    fireEvent.pointerMove(knob, {
      pointerId: 1,
      pointerType: 'touch',
      clientX: 140,
      clientY: 100,
      buttons: 1,
    });
    expect(screen.getByRole('button', { name: 'Vertex' })).toBe(knob);
    expect(knob.dataset.activePointer).toBe('1');
    expect(getArea().session.vertices[0]?.longitude).toBeCloseTo(140 / 320, 4);
  });

  it('keeps the closed ring on screen until submission', () => {
    const view = render(<AreaOutline language="en" />);
    act(() => {
      dispatch({ type: 'select-tool', tool: 'polygon' });
      for (const point of [
        { x: 40, y: 40 },
        { x: 120, y: 40 },
        { x: 120, y: 120 },
      ]) {
        dispatch({ type: 'pointer', ...point, pointerType: 'touch' });
      }
      dispatch({ type: 'focus-knob', index: 0 });
      dispatch({ type: 'enter' });
    });
    expect(getArea().session.closed).toBe(true);
    expect(
      view.container.querySelector('[data-part="progress-ring"]'),
    ).not.toBeNull();
  });

  it('lets the map receive pointers after Escape and after submission', () => {
    const view = render(<AreaOutline language="en" />);
    act(() => {
      dispatch({ type: 'select-tool', tool: 'radius' });
    });
    const overlay = view.container.querySelector('.area-overlay');
    expect(overlay?.classList.contains('is-live')).toBe(true);
    act(() => {
      dispatch({ type: 'escape' });
    });
    expect(overlay?.classList.contains('is-live')).toBe(false);
    fireEvent.pointerDown(overlay as Element, {
      button: 0,
      isPrimary: true,
      pointerType: 'mouse',
      clientX: 20,
      clientY: 20,
    });
    expect(getArea().session.pin).toBeNull();
    act(() => {
      dispatch({ type: 'select-tool', tool: 'radius' });
      dispatch({ type: 'submit' });
    });
    expect(overlay?.classList.contains('is-live')).toBe(false);
  });

  it('draws a returned circle boundary and no browser circle', async () => {
    const calls: string[] = [];
    registerFetch(async (path, init) => {
      calls.push(init.body);
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
            point_feature_ids: { public_places: ['feat_place_in'] },
            outline: {
              type: 'Circle',
              coordinates: [0.5, 0.5],
              radius_m: 250,
            },
            units: { cells: ['unit-a'] },
            snap_report: { opaque: true },
            record: {
              anchor_cell: null,
              traffic: 'free_flow',
              shape: 'circle',
            },
          },
        }),
      };
    });
    const view = render(
      <AnswerShell language="en" theme="dark" extractUrl={null} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Radius' }));
    fireEvent.keyDown(screen.getByRole('button', { name: 'Crosshair' }), {
      key: 'Enter',
    });
    fireEvent.click(
      view.container.querySelector('[data-preset="distance-a"]') as Element,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Use this area' }));
    await waitFor(() => {
      expect(calls.length).toBeGreaterThan(0);
    });
    const line = view.container.querySelector(
      '[data-outline="circle"] polyline',
    );
    expect(line?.getAttribute('points')?.split(' ').length).toBeGreaterThan(8);
    expect(view.container.querySelector('circle')).toBeNull();
    const body = JSON.parse(calls[0] ?? '{}') as Record<string, unknown>;
    expect(body.pin).toBeUndefined();
    expect(Object.keys(body).sort()).toEqual([
      'cutoff',
      'latitude',
      'longitude',
      'mode',
    ]);
  });

  it('posts through the shell button without a registered client', async () => {
    const calls: string[] = [];
    vi.stubGlobal('fetch', async (input: string, init: { body: string }) => {
      calls.push(`${input}:${init.body}`);
      if (input.endsWith('/shapes')) {
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
            point_feature_ids: { public_places: ['feat_place_in'] },
            outline: {
              type: 'Polygon',
              coordinates: [
                [
                  [0, 0],
                  [1, 0],
                  [1, 1],
                  [0, 1],
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
    const layers = basePayload({
      layers: [
        {
          key: 'public_places',
          visible: true,
          source_chain_fact_id: factId(0),
          source_id: 'src_places',
          features: [
            {
              feature_id: 'feat_place_in',
              metric_key: 'place_listing',
              provenance: 'public',
              subject: 'place',
              geometry_kind: 'point',
              position: [0.2, 0.2],
            },
            {
              feature_id: 'feat_place_out',
              metric_key: 'place_listing',
              provenance: 'public',
              subject: 'place',
              geometry_kind: 'point',
              position: [2, 2],
            },
          ],
        },
      ],
    });
    const view = render(
      <AnswerShell
        language="en"
        theme="dark"
        extractUrl={null}
        registry={sceneRegistry()}
        sourceLayers={layers}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Polygon' }));
    const hair = () => screen.getByRole('button', { name: 'Crosshair' });
    fireEvent.keyDown(hair(), { key: 'Enter' });
    fireEvent.keyDown(hair(), { key: 'ArrowRight' });
    fireEvent.keyDown(hair(), { key: 'Enter' });
    fireEvent.keyDown(hair(), { key: 'ArrowDown' });
    fireEvent.keyDown(hair(), { key: 'Enter' });
    const first = screen.getAllByRole('button', { name: 'Vertex' })[0];
    fireEvent.focus(first as HTMLElement);
    fireEvent.keyDown(first as HTMLElement, { key: 'Enter' });
    fireEvent.click(screen.getByRole('button', { name: 'Use this area' }));
    await waitFor(() => {
      expect(calls.some((call) => call.includes('/api/tools/make_area'))).toBe(
        true,
      );
      expect(
        view.container.querySelector('[data-feature="feat_place_in"]'),
      ).not.toBeNull();
    });
    expect(
      view.container.querySelector('[data-feature="feat_place_in"]'),
    ).not.toBeNull();
    expect(
      view.container.querySelector('[data-feature="feat_place_out"]'),
    ).toBeNull();
  });

  it('makes drawing controls inert under the open drawer in both languages', () => {
    for (const language of ['en', 'ar'] as const) {
      const view = render(
        <AnswerShell
          language={language}
          theme="dark"
          extractUrl={null}
          registry={completeRegistry()}
          draft={draft()}
        />,
      );
      const chip = view.container.querySelector('.brief [data-fact-chip]');
      expect(chip).not.toBeNull();
      fireEvent.click(chip as Element);
      const tools = view.container.querySelector('.draw-tools');
      expect(tools?.closest('[inert]')).not.toBeNull();
      const drawer = view.container.querySelector('.drawer');
      expect(drawer).not.toBeNull();
      cleanup();
      clearArea();
    }
  });

  it('projects pins through the live stage port when the camera changes', async () => {
    const scale = { value: 100 };
    const port = camera(1);
    const handle: MapHandle = {
      remove() {},
      mountOverlay() {},
      bind() {},
      unbind() {},
      project(vertex) {
        return {
          x: 160 + (vertex.longitude - CENTRE.longitude) * scale.value,
          y: 160 - (vertex.latitude - CENTRE.latitude) * scale.value,
        };
      },
      unproject(point) {
        return {
          longitude: CENTRE.longitude + (point.x - 160) / scale.value,
          latitude: CENTRE.latitude - (point.y - 160) / scale.value,
        };
      },
      suspendGestures() {},
      restoreGestures() {},
      centre() {
        return CENTRE;
      },
      bindView() {},
      unbindView() {},
    };
    void port;
    const view = render(
      <Stage
        language="en"
        theme="dark"
        extractUrl="pmtiles://fixture.pmtiles"
        mapStarter={async () => handle}
        canvas={<AreaOutline language="en" />}
      />,
    );
    await waitFor(() => {
      expect(
        view.container.querySelector('[data-state="ready"]'),
      ).not.toBeNull();
    });
    dispatch({ type: 'select-tool', tool: 'radius' });
    dispatch({ type: 'pointer', x: 160, y: 160, pointerType: 'mouse' });
    expect(getArea().session.pin).toEqual(CENTRE);
    scale.value = 40;
    const moved = handle.project(CENTRE);
    expect(moved).toEqual({ x: 160, y: 160 });
    const shifted = handle.project({
      longitude: CENTRE.longitude + 0.5,
      latitude: CENTRE.latitude,
    });
    expect(shifted.x).not.toBe(160);
  });
});
