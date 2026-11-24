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
import { readFileSync } from 'node:fs';

import { AnswerShell } from '../../src/shell/AnswerShell';
import {
  dispatch,
  registerFetch,
  registerPort,
  releasePort,
  releaseAreaClient,
  resetArea,
  submitArea,
} from '../../src/state/area-actions';
import { getArea } from '../../src/state/store';
import { plainPort } from '../fixtures/plain-port';
import { completeRegistry } from '../fixtures/facts';
import type { MapHandle } from '../../src/stage/map-boot';
import { Stage } from '../../src/stage/Stage';
import { text } from '../../src/i18n';

// This suite tests the map/answer lifecycle with a stubbed map. Keep the deck
// renderer stubbed too: importing the actual renderer adds an unrelated async
// dependency to P6's initial-overlay assertion. Renderer lifecycle has its own
// map-renderer.test.ts coverage, including exactly-once removal.
vi.mock('../../src/stage/layers/overlay', () => ({
  firstLabelLayerId: () => null,
  overlayFor: (
    payload: unknown,
    _beforeId: unknown,
    registry: unknown,
    clockEnabled: boolean,
  ) => ({
    // Record the input boundary, as in probe S, without loading deck.
    layers: payload && registry ? ['fixture-geometry'] : [],
    clockEnabled,
    onAdd: vi.fn(),
    onRemove: vi.fn(),
  }),
}));

const OK = {
  tool: 'make_area',
  call_id: 'INVENTED-review-call',
  engine: 'embedded',
  blocks: [],
  facts: [],
  caveat_keys: [],
  status: 'OK',
  release_id: 'rel-review',
  payload: {
    area_id: 'area-review',
    outline: { type: 'Circle', coordinates: [0.5, 0.5], radius_m: 250 },
    point_feature_ids: {},
    record: { anchor_cell: null, traffic: 'free_flow', shape: 'radius' },
  },
};

describe('accepted geometry review regressions', () => {
  let token = 0;
  beforeEach(() => {
    resetArea();
    token = registerPort(plainPort(320, 320));
  });
  afterEach(() => {
    cleanup();
    resetArea();
    releasePort(token);
    releaseAreaClient();
    vi.unstubAllGlobals();
  });
  function mount(language: 'en' | 'ar' = 'en') {
    return render(
      <AnswerShell language={language} theme="dark" extractUrl={null} />,
    );
  }
  function pin() {
    dispatch({ type: 'select-tool', tool: 'radius' });
    dispatch({ type: 'enter' });
    dispatch({ type: 'preset', mode: 'distance', cutoff: 250 });
  }
  function polygon() {
    dispatch({ type: 'select-tool', tool: 'polygon' });
    for (const [x, y] of [
      [40, 40],
      [120, 40],
      [120, 120],
    ] as const) {
      dispatch({ type: 'pointer', x, y, pointerType: 'touch' });
    }
  }

  it('P1: crosshair focus clears the old knob before an arrow', () => {
    mount();
    act(polygon);
    const vertex = getArea().session.vertices[1];
    fireEvent.focus(screen.getAllByRole('button', { name: 'Vertex' })[1]!);
    const hair = screen.getByRole('button', { name: 'Crosshair' });
    fireEvent.focus(hair);
    const before = getArea().session.crosshairY;
    fireEvent.keyDown(hair, { key: 'ArrowDown' });
    expect(getArea().session.crosshairY).toBe(before + 16);
    expect(getArea().session.vertices[1]).toEqual(vertex);
  });

  it.each([false, true])(
    'P2: tap a knob then tap elsewhere moves it; closed=%s',
    (closed) => {
      mount();
      act(polygon);
      if (closed)
        fireEvent.click(screen.getAllByRole('button', { name: 'Vertex' })[0]!);
      fireEvent.click(screen.getAllByRole('button', { name: 'Vertex' })[1]!);
      fireEvent.pointerDown(document.querySelector('.area-overlay')!, {
        button: 0,
        isPrimary: true,
        pointerType: 'touch',
        clientX: 220,
        clientY: 60,
      });
      expect(getArea().session.vertices).toHaveLength(3);
      expect(getArea().session.vertices[1]).toMatchObject({
        longitude: 220 / 320,
        latitude: 60 / 320,
      });
      expect(getArea().session.focusedKnob).toBeNull();
    },
  );

  it('R1: tap knob zero on a closed ring then tap elsewhere moves vertex zero', () => {
    mount();
    act(polygon);
    fireEvent.click(screen.getAllByRole('button', { name: 'Vertex' })[0]!);
    expect(getArea().session.closed).toBe(true);
    expect(getArea().session.selectedKnob).toBeNull();
    fireEvent.click(screen.getAllByRole('button', { name: 'Vertex' })[0]!);
    fireEvent.pointerDown(document.querySelector('.area-overlay')!, {
      button: 0,
      isPrimary: true,
      pointerType: 'touch',
      clientX: 220,
      clientY: 60,
    });
    expect(getArea().session.vertices).toHaveLength(3);
    expect(getArea().session.vertices[0]).toMatchObject({
      longitude: 220 / 320,
      latitude: 60 / 320,
    });
    expect(getArea().session.closed).toBe(true);
    expect(getArea().session.selectedKnob).toBeNull();
  });

  it.each([1, 0])(
    'A: a drag and its following click on knob %s do not select or close the ring',
    (index) => {
      mount();
      act(polygon);
      const knob = screen.getAllByRole('button', { name: 'Vertex' })[index]!;
      fireEvent.pointerDown(knob, {
        button: 0,
        isPrimary: true,
        pointerId: 9,
        clientX: index === 0 ? 40 : 120,
        clientY: 40,
      });
      fireEvent.pointerMove(knob, {
        pointerId: 9,
        clientX: index === 0 ? 50 : 130,
        clientY: 50,
      });
      fireEvent.pointerUp(knob, { pointerId: 9 });
      fireEvent.click(knob);
      const dragged = getArea().session.vertices[index];
      expect(dragged).toMatchObject({
        longitude: (index === 0 ? 50 : 130) / 320,
        latitude: 50 / 320,
      });
      expect(getArea().session.closed).toBe(false);
      fireEvent.pointerDown(document.querySelector('.area-overlay')!, {
        button: 0,
        isPrimary: true,
        pointerType: 'touch',
        clientX: 40,
        clientY: 200,
      });
      expect(getArea().session.vertices).toHaveLength(4);
      expect(getArea().session.vertices[index]).toEqual(dragged);
    },
  );

  it.each(['en', 'ar'] as const)(
    'F5: pointer Cancel restores gestures in %s',
    (language) => {
      const restore = vi.fn();
      releasePort(token);
      token = registerPort({
        ...plainPort(320, 320),
        restoreGestures: restore,
      });
      mount(language);
      act(polygon);
      fireEvent.click(
        screen.getByRole('button', {
          name: language === 'ar' ? 'إلغاء' : 'Cancel',
        }),
      );
      expect(getArea().session.phase).toBe('idle');
      expect(getArea().session.vertices).toEqual([]);
      expect(restore).toHaveBeenCalled();
    },
  );

  it.each(['escape', 'select-tool', 'reset', 'edit'] as const)(
    'P3: late answer cannot overwrite %s',
    async (change) => {
      let finish!: (
        value: Awaited<ReturnType<import('../../src/api/areas').FetchLike>>,
      ) => void;
      registerFetch(
        () =>
          new Promise((resolve) => {
            finish = resolve;
          }),
      );
      act(pin);
      const pending = submitArea();
      if (change === 'reset') resetArea();
      else if (change === 'select-tool')
        dispatch({ type: change, tool: 'polygon' });
      else if (change === 'edit')
        dispatch({ type: 'pointer', x: 20, y: 30, pointerType: 'touch' });
      else dispatch({ type: change });
      const latest = getArea().session;
      finish({ status: 200, json: async () => OK });
      await pending;
      expect(getArea().session).toEqual(latest);
      expect(getArea().presented).toBeNull();
    },
  );

  it('F6: Arabic presets and summary use Western digits with Arabic units', async () => {
    registerFetch(async () => ({ status: 200, json: async () => OK }));
    const view = mount('ar');
    act(pin);
    expect(
      view.container.querySelector('[data-preset="distance-a"] .chip-num')
        ?.textContent,
    ).toBe('250');
    expect(
      view.container.querySelector('[data-preset="distance-a"] .chip-unit')
        ?.textContent,
    ).toBe('م');
    expect(
      view.container.querySelector('[data-preset="distance-c"] .chip-unit')
        ?.textContent,
    ).toBe('كم');
    await act(submitArea);
    expect(
      view.container.querySelector('[data-part="area-summary"] .chip-num')
        ?.textContent,
    ).toBe('250');
    expect(
      view.container.querySelector('[data-part="area-summary"] .chip-unit')
        ?.textContent,
    ).toBe('م');
    act(() => dispatch({ type: 'select-tool', tool: 'travel' }));
    expect(
      view.container.querySelector('[data-preset="walk-a"] .chip-num')
        ?.textContent,
    ).toBe('5');
    expect(
      view.container.querySelector('[data-preset="walk-a"] .chip-unit')
        ?.textContent,
    ).toBe('دقيقة');
  });

  it.each(['en', 'ar'] as const)(
    'B: every preset and summary input chip carries Your inputs in %s',
    async (language) => {
      registerFetch(async () => ({ status: 200, json: async () => OK }));
      const view = mount(language);
      act(pin);
      function expectTags(expectedCount: number) {
        const chips = view.container.querySelectorAll(
          '[data-part="preset"] [data-fact-chip="input"]',
        );
        expect(chips).toHaveLength(expectedCount);
        for (const chip of chips) {
          expect(chip.querySelector('.chip-tag')?.textContent).toBe(
            text(language, 'input.yours'),
          );
          expect(chip.querySelectorAll('.chip-unit')).toHaveLength(1);
        }
      }
      expectTags(3);
      await act(submitArea);
      const summary = view.container.querySelector(
        '[data-part="area-summary"] [data-fact-chip="input"]',
      );
      expect(summary).not.toBeNull();
      expect(summary?.querySelector('.chip-tag')?.textContent).toBe(
        text(language, 'input.yours'),
      );
      expect(summary?.querySelectorAll('.chip-unit')).toHaveLength(1);
      act(() => dispatch({ type: 'select-tool', tool: 'travel' }));
      expectTags(6);
    },
  );

  it.each([
    { button: 2, isPrimary: true },
    { button: 1, isPrimary: true },
    { button: 0, isPrimary: false },
  ])('N2: ignores non-drawing pointer %j on overlay and knob', (pointer) => {
    mount();
    act(polygon);
    const before = getArea().session;
    fireEvent.pointerDown(document.querySelector('.area-overlay')!, {
      ...pointer,
      pointerId: 9,
      pointerType: 'touch',
      clientX: 220,
      clientY: 60,
    });
    expect(getArea().session).toEqual(before);
    const knob = screen.getAllByRole('button', { name: 'Vertex' })[1]!;
    fireEvent.pointerDown(knob, {
      ...pointer,
      pointerId: 9,
      pointerType: 'touch',
    });
    fireEvent.pointerMove(knob, { pointerId: 9, clientX: 230, clientY: 70 });
    expect(getArea().session.vertices).toEqual(before.vertices);
  });

  it.each(['fetch', 'json'] as const)(
    'N3: %s rejection becomes governed refusal',
    async (failure) => {
      registerFetch(async () => {
        if (failure === 'fetch') throw new Error('fixture unavailable');
        return {
          status: 200,
          json: async () => {
            throw new Error('fixture non-JSON');
          },
        };
      });
      const view = mount();
      act(pin);
      await act(submitArea);
      expect(getArea().presented?.status).toBe('INVALID_ARGUMENT');
      expect(
        view.container.querySelector('[data-part="refusal"]'),
      ).not.toBeNull();
    },
  );

  it('N1: knobs, crosshair and pin do not transition away from the outline', () => {
    const css = readFileSync('src/styles/answer.css', 'utf8');
    const rule = css.match(
      /\.draw-knob,\s*\.draw-crosshair,\s*\.draw-pin\s*\{([^}]+)\}/,
    )?.[1];
    expect(rule).toBeDefined();
    expect(rule).not.toMatch(/transition\s*:[^;]*inset/);
  });

  it('P6: an answer with live source layers keeps one map and focus on Use', async () => {
    releasePort(token);
    vi.stubGlobal('fetch', async () => ({ ok: true, json: async () => ({}) }));
    const fixture = plainPort(320, 320);
    const removed = vi.fn();
    const mountOverlay = vi.fn();
    const handle: MapHandle = {
      ...fixture,
      bind: vi.fn(),
      unbind: vi.fn(),
      bindView: vi.fn(),
      unbindView: vi.fn(),
      remove: removed,
      mountOverlay,
    };
    const starter = vi.fn(async () => handle);
    registerFetch(async () => ({ status: 200, json: async () => OK }));
    const view = render(
      <AnswerShell
        language="en"
        theme="dark"
        extractUrl="pmtiles://fixture.pmtiles"
        mapStarter={starter}
        registry={completeRegistry()}
        sourceLayers={{ layers: [], sources: [], gazetteer_points: [] }}
      />,
    );
    await waitFor(() =>
      expect(
        view.container.querySelector('.stage')?.getAttribute('data-state'),
      ).toBe('ready'),
    );
    await waitFor(() => expect(mountOverlay).toHaveBeenCalledTimes(1));
    act(pin);
    const use = screen.getByRole('button', { name: 'Use this area' });
    act(() => use.focus());
    fireEvent.click(use);
    await waitFor(() => expect(getArea().session.phase).toBe('submitted'));
    expect(starter).toHaveBeenCalledTimes(1);
    expect(removed).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(use);
    await waitFor(() => expect(mountOverlay).toHaveBeenCalledTimes(2));
  });

  it.each(['payload', 'registry'] as const)(
    'mounts no overlay with missing %s and mounts when both inputs arrive',
    async (missing) => {
      vi.stubGlobal('fetch', async () => ({
        ok: true,
        json: async () => ({}),
      }));
      const mountOverlay = vi.fn();
      const remove = vi.fn();
      const starter = vi.fn(async (): Promise<MapHandle> => ({
        ...plainPort(320, 320),
        bind: vi.fn(),
        unbind: vi.fn(),
        bindView: vi.fn(),
        unbindView: vi.fn(),
        remove,
        mountOverlay,
      }));
      const props = {
        language: 'en' as const,
        theme: 'dark' as const,
        extractUrl: 'pmtiles://fixture.pmtiles',
        mapStarter: starter,
        layerPayload: { layers: [], sources: [], gazetteer_points: [] },
        registry: completeRegistry(),
      };
      const view = render(
        <Stage
          {...props}
          layerPayload={missing === 'payload' ? null : props.layerPayload}
          registry={missing === 'registry' ? null : props.registry}
        />,
      );
      await waitFor(() =>
        expect(
          view.container.querySelector('.stage')?.getAttribute('data-state'),
        ).toBe('ready'),
      );
      await act(async () => {
        await Promise.resolve();
      });
      expect(mountOverlay).not.toHaveBeenCalled();
      expect(
        view.container.querySelector('[data-refusal="registry_absent"]') !==
          null,
      ).toBe(missing === 'registry');
      view.rerender(<Stage {...props} />);
      await waitFor(() => expect(mountOverlay).toHaveBeenCalledTimes(1));
      expect(starter).toHaveBeenCalledTimes(1);
      expect(remove).not.toHaveBeenCalled();
    },
  );

  it.each(['registry', 'payload'] as const)(
    'S-%s: clears drawn geometry on the live map when the input turns null',
    async (missing) => {
      vi.stubGlobal('fetch', async () => ({
        ok: true,
        json: async () => ({}),
      }));
      const mountOverlay = vi.fn();
      const remove = vi.fn();
      const starter = vi.fn(async (): Promise<MapHandle> => ({
        ...plainPort(320, 320),
        bind: vi.fn(),
        unbind: vi.fn(),
        bindView: vi.fn(),
        unbindView: vi.fn(),
        remove,
        mountOverlay,
      }));
      const props = {
        language: 'en' as const,
        theme: 'dark' as const,
        extractUrl: 'pmtiles://fixture.pmtiles',
        mapStarter: starter,
        layerPayload: { layers: [], sources: [], gazetteer_points: [] },
        registry: completeRegistry(),
      };
      const view = render(<Stage {...props} />);
      await waitFor(() =>
        expect(mountOverlay.mock.calls.at(-1)?.[0]).toMatchObject({
          layers: ['fixture-geometry'],
        }),
      );
      view.rerender(
        <Stage
          {...props}
          layerPayload={missing === 'payload' ? null : props.layerPayload}
          registry={missing === 'registry' ? null : props.registry}
        />,
      );
      await waitFor(() =>
        expect(mountOverlay.mock.calls.at(-1)?.[0]).toMatchObject({
          layers: [],
          clockEnabled: true,
        }),
      );
      expect(starter).toHaveBeenCalledTimes(1);
      expect(remove).not.toHaveBeenCalled();
    },
  );

  it('installs current layers when a paused map resumes with the same request key', async () => {
    vi.stubGlobal('fetch', async () => ({ ok: true, json: async () => ({}) }));
    const mountOverlay = vi.fn();
    const remove = vi.fn();
    const starter = vi.fn(async (): Promise<MapHandle> => ({
      ...plainPort(320, 320),
      bind: vi.fn(),
      unbind: vi.fn(),
      bindView: vi.fn(),
      unbindView: vi.fn(),
      remove,
      mountOverlay,
    }));
    const props = {
      language: 'en' as const,
      theme: 'dark' as const,
      extractUrl: 'pmtiles://fixture.pmtiles',
      mapStarter: starter,
      layerPayload: { layers: [], sources: [], gazetteer_points: [] },
      registry: completeRegistry(),
      overlayFactory: () => ({ onAdd: vi.fn(), onRemove: vi.fn() }),
    };
    const view = render(<Stage {...props} />);
    await waitFor(() => expect(mountOverlay).toHaveBeenCalledTimes(1));
    view.rerender(<Stage {...props} paused />);
    expect(remove).toHaveBeenCalledTimes(1);
    view.rerender(<Stage {...props} />);
    await waitFor(() => expect(mountOverlay).toHaveBeenCalledTimes(2));
    expect(starter).toHaveBeenCalledTimes(2);
  });
});
