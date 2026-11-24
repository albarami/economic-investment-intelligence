// @vitest-environment jsdom
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';

import { postResolve } from '../../src/api/areas';
import { text } from '../../src/i18n';
import { AnswerShell } from '../../src/shell/AnswerShell';
import {
  registerFetch,
  releaseAreaClient,
  resetArea,
  submitPlaceArea,
} from '../../src/state/area-actions';
import { getArea } from '../../src/state/store';
import { sceneRegistry } from '../fixtures/layer-registry';
import { basePayload } from '../fixtures/layers';

afterEach(() => {
  cleanup();
  releaseAreaClient();
  resetArea();
});

const outline = { type: 'Circle', coordinates: [2.5, 2.5], radius_m: 250 };
const candidate = {
  kind: 'place',
  key: 'district:INVENTED-null',
  label_en: 'INVENTED-Court',
  label_ar: 'ساحة مخترعة',
  source: 'gazetteer',
  match: 'exact',
};
const made = {
  tool: 'make_area',
  call_id: 'INVENTED-call',
  engine: 'embedded',
  status: 'OK',
  blocks: [],
  facts: [],
  caveat_keys: [],
  release_id: 'INVENTED-release',
  payload: {
    area_id: 'INVENTED-exact-area',
    outline,
    units: {},
    snap_report: null,
    point_feature_ids: { public_places: [] },
    record: { anchor_cell: null, traffic: 'free_flow', shape: 'radius' },
  },
};

it.each([
  ['en', 'dark'],
  ['en', 'light'],
  ['ar', 'dark'],
  ['ar', 'light'],
] as const)(
  'consumes a named key in %s %s with a preset and boundaries absent',
  async (language, theme) => {
    const calls: { path: string; body: unknown }[] = [];
    const client = async (path: string, init: { body: string }) => {
      calls.push({ path, body: JSON.parse(init.body) });
      return {
        status: 200,
        json: async () =>
          path === '/api/tools/resolve'
            ? {
                ...made,
                tool: 'resolve',
                payload: { candidates: [candidate] },
              }
            : made,
      };
    };
    registerFetch(client);
    const registry = sceneRegistry();
    const { container } = render(
      <AnswerShell
        language={language}
        theme={theme}
        extractUrl={null}
        registry={registry}
        sourceLayers={basePayload()}
      />,
    );
    const found = await postResolve(
      {
        text: language === 'en' ? candidate.label_en : candidate.label_ar,
        lang: language,
        kind: 'place',
      },
      client,
    );
    expect(found.kind).toBe('envelope');
    if (found.kind !== 'envelope') return;
    const selected = found.envelope.payload?.candidates[0];
    expect(selected?.kind).toBe('place');
    if (!selected) return;
    await act(async () => {
      await submitPlaceArea(selected.key, 'distance-a');
    });
    expect(calls.map((call) => call.path)).toEqual([
      '/api/tools/resolve',
      '/api/tools/make_area',
    ]);
    expect(calls[1]?.body).toEqual({
      place_key: candidate.key,
      mode: 'distance',
      cutoff: 250,
    });
    expect(getArea().presented).toMatchObject({
      namedPlace: true,
      outline,
      anchorCell: null,
      shapeKind: 'radius',
      showRefusal: false,
      showLayers: true,
    });
    expect(getArea().session.pin).toBeNull();
    expect(getArea().ownPin).toBeNull();
    expect(
      container.querySelector('[data-part="place-preset"]')?.textContent,
    ).toBe(text(language, 'draw.summary.place'));
    expect(
      container.querySelector('[data-part="boundaries"]')?.textContent,
    ).toBe(text(language, 'layers.boundaries.absent'));
    expect(container.querySelector('[data-fact-chip="input"]')).not.toBeNull();
    expect(document.documentElement.dir).toBe(
      language === 'ar' ? 'rtl' : 'ltr',
    );
    expect(document.documentElement.dataset.theme).toBe(theme);
    const summary = container
      .querySelector('[data-part="area-summary"]')
      ?.cloneNode(true) as HTMLElement;
    summary
      .querySelectorAll('[data-fact-chip]')
      .forEach((chip) => chip.remove());
    expect(summary.textContent).not.toMatch(/\p{Nd}/u);
    expect(
      container.querySelector('[data-part="official-outline"]'),
    ).toBeNull();
  },
);

it('never posts an activity key or an invented preset as an area', async () => {
  const calls: string[] = [];
  registerFetch(async (path) => {
    calls.push(path);
    return { status: 200, json: async () => made };
  });
  await submitPlaceArea('activity:INVENTED-craft', 'distance-a');
  await submitPlaceArea(candidate.key, 'INVENTED-preset');
  expect(calls).toEqual([]);
});

it('drops a pending named result after reset and refuses a failed request without guessing geometry', async () => {
  let finish:
    | ((value: { status: number; json: () => Promise<unknown> }) => void)
    | undefined;
  registerFetch(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const pending = submitPlaceArea(candidate.key, 'distance-a');
  resetArea();
  finish?.({ status: 200, json: async () => made });
  await pending;
  expect(getArea().presented).toBeNull();
  registerFetch(async () => {
    throw new Error('INVENTED');
  });
  await submitPlaceArea(candidate.key, 'distance-a');
  expect(getArea().presented).toMatchObject({
    status: 'INVALID_ARGUMENT',
    outline: null,
    showLayers: false,
  });
});
