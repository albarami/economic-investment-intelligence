// @vitest-environment jsdom
/**
 * S3-T10 box 9: drawing an area offers a named-area choice and
 * click-to-place vertices; every drag has a single-pointer alternative and
 * the whole flow runs from the keyboard. Invented fixtures only.
 */
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { FetchLike } from '../../src/api/areas';
import { ARROW_STEP_PX } from '../../src/controls/draw-session';
import { text, type Language } from '../../src/i18n';
import { PublicStory } from '../../src/journeys/PublicStory';
import { AnswerShell } from '../../src/shell/AnswerShell';
import {
  registerFetch,
  registerPort,
  releaseAreaClient,
  releasePort,
} from '../../src/state/area-actions';
import { clearArea, getArea } from '../../src/state/store';
import { plainPort } from '../fixtures/plain-port';

const CANDIDATE = {
  kind: 'place',
  key: 'district:INVENTED-plaza',
  label_en: 'INVENTED-Plaza',
  label_ar: 'ساحة مخترعة',
  source: 'gazetteer',
  match: 'exact',
};

function made(status: string) {
  return {
    tool: 'make_area',
    call_id: 'INVENTED-call',
    engine: 'embedded',
    status,
    blocks: [],
    facts: [],
    caveat_keys: [],
    release_id: 'INVENTED-release',
    payload: {
      area_id: 'INVENTED-area',
      outline: { type: 'Circle', coordinates: [0.5, 0.5], radius_m: 250 },
      units: {},
      snap_report: null,
      point_feature_ids: { public_places: [] },
      record: { anchor_cell: null, traffic: 'free_flow', shape: 'radius' },
    },
  };
}

let token = 0;
let areaCalls: { path: string; body: unknown }[] = [];

beforeEach(() => {
  clearArea();
  token = registerPort(plainPort(320, 320));
  areaCalls = [];
  const client: FetchLike = async (path, init) => {
    areaCalls.push({ path, body: JSON.parse(String(init.body)) });
    return { status: 200, json: async () => made('OK') };
  };
  registerFetch(client);
  vi.stubGlobal('fetch', async (url: string) => {
    if (url === '/api/tools/resolve')
      return new Response(
        JSON.stringify({
          ...made('OK'),
          tool: 'resolve',
          payload: { candidates: [CANDIDATE] },
        }),
        { status: 200 },
      );
    return new Response('{}', { status: 404 });
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  clearArea();
  releasePort(token);
  releaseAreaClient();
});

function mount(language: Language) {
  return render(
    <AnswerShell language={language} theme="light" extractUrl={null} />,
  );
}

/** The mounted area scene: the story's selection beside the drawing tools. */
function mountScene(language: Language) {
  return render(
    <AnswerShell
      language={language}
      theme="light"
      extractUrl={null}
      renderBrief={(open) => (
        <PublicStory
          language={language}
          registry={null}
          cards={[]}
          pending={false}
          failed={false}
          onRun={() => undefined}
          onOpen={open}
          onReset={() => undefined}
        />
      )}
    />,
  );
}

function scene(container: HTMLElement): HTMLElement {
  const node = container.querySelector<HTMLElement>('[data-scene="area"]');
  expect(node).not.toBeNull();
  return node!;
}

describe.each(['en', 'ar'] as const)('drawing an area in %s', (language) => {
  it('offers a named-area choice beside the drawing tools', () => {
    const { container } = mountScene(language);
    const group = scene(container);
    expect(group.querySelector('[data-picker="place"]')).not.toBeNull();
    expect(
      within(group).getByLabelText(text(language, 'draw.namedPlace')),
    ).toBeInstanceOf(HTMLInputElement);
    const drawing = container.querySelector('.drawing-disclosure');
    expect(drawing?.querySelector('summary')?.textContent).toBe(
      text(language, 'draw.tools'),
    );
    expect(
      within(drawing as HTMLElement).getByRole('button', {
        name: text(language, 'draw.polygon'),
      }),
    ).toBeDefined();
  });

  it('chooses a named area from the keyboard alone and posts only its key', async () => {
    const { container } = mountScene(language);
    const group = scene(container);
    const input = within(group).getByLabelText(
      text(language, 'draw.namedPlace'),
    );
    input.focus();
    fireEvent.change(input, {
      target: {
        value: language === 'ar' ? CANDIDATE.label_ar : CANDIDATE.label_en,
      },
    });
    // Enter in a form field submits its form; native buttons take Enter and Space.
    fireEvent.submit(input.closest('form')!);
    const choice = await waitFor(() => {
      const node = group.querySelector<HTMLButtonElement>(
        `[data-candidate="${CANDIDATE.key}"]`,
      );
      expect(node).not.toBeNull();
      return node!;
    });
    expect(choice.tagName).toBe('BUTTON');
    fireEvent.click(choice);
    const selected = group.querySelector('[data-part="place-selected"]');
    expect(selected?.textContent).toContain(
      language === 'ar' ? CANDIDATE.label_ar : CANDIDATE.label_en,
    );
    const preset = group.querySelector<HTMLButtonElement>(
      '[data-place-preset="distance-a"]',
    );
    expect(preset?.tagName).toBe('BUTTON');
    await act(async () => {
      fireEvent.click(preset!);
    });
    expect(areaCalls.map((call) => call.path)).toEqual([
      '/api/tools/make_area',
    ]);
    expect(areaCalls[0]?.body).toEqual({
      place_key: CANDIDATE.key,
      mode: 'distance',
      cutoff: 250,
    });
    expect(getArea().presented).toMatchObject({ namedPlace: true });
  });

  it('places vertices by single clicks and moves one by select-then-click', () => {
    mount(language);
    fireEvent.click(
      screen.getByRole('button', { name: text(language, 'draw.polygon') }),
    );
    const overlay = document.querySelector('.area-overlay')!;
    for (const [clientX, clientY] of [
      [40, 40],
      [120, 40],
      [120, 120],
    ] as const)
      fireEvent.pointerDown(overlay, {
        isPrimary: true,
        pointerType: 'mouse',
        button: 0,
        clientX,
        clientY,
      });
    expect(getArea().session.vertices).toHaveLength(3);
    const knobs = () =>
      screen.getAllByRole('button', { name: text(language, 'draw.vertex') });
    fireEvent.click(knobs()[0]!);
    expect(getArea().session.closed).toBe(true);
    const before = getArea().session.vertices[1]!;
    fireEvent.click(knobs()[1]!);
    expect(getArea().session.selectedKnob).toBe(1);
    expect(screen.getByRole('status').textContent).toBe(
      text(language, 'draw.moveVertex'),
    );
    fireEvent.pointerDown(overlay, {
      isPrimary: true,
      pointerType: 'mouse',
      button: 0,
      clientX: 200,
      clientY: 200,
    });
    const after = getArea().session.vertices;
    expect(after).toHaveLength(3);
    expect(after[1]!.id).toBe(before.id);
    expect(after[1]).not.toEqual(before);
    expect(getArea().session.selectedKnob).toBeNull();
  });

  it('draws, closes and moves a vertex from the keyboard alone', () => {
    mount(language);
    fireEvent.click(
      screen.getByRole('button', { name: text(language, 'draw.polygon') }),
    );
    const hair = () =>
      screen.getByRole('button', { name: text(language, 'draw.crosshair') });
    for (const key of ['Enter', 'ArrowRight', 'Enter', 'ArrowDown', 'Enter'])
      fireEvent.keyDown(hair(), { key });
    const knobs = () =>
      screen.getAllByRole('button', { name: text(language, 'draw.vertex') });
    fireEvent.focus(knobs()[0]!);
    fireEvent.keyDown(knobs()[0]!, { key: 'Enter' });
    expect(getArea().session.closed).toBe(true);
    const port = plainPort(320, 320);
    const before = port.project(getArea().session.vertices[1]!);
    fireEvent.focus(knobs()[1]!);
    fireEvent.keyDown(knobs()[1]!, { key: 'ArrowDown' });
    const after = port.project(getArea().session.vertices[1]!);
    expect(after.x).toBeCloseTo(before.x, 6);
    expect(after.y).toBeCloseTo(before.y + ARROW_STEP_PX, 6);
  });
});
