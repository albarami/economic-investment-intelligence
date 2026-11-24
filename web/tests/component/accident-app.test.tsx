// @vitest-environment jsdom
/**
 * S3-T12, design amendments 1 and 2: the live mounted accident and rail
 * routes (spawned from `product/tests/test_accident_mounted_http.py` over an
 * invented release) rendered through `App` in both languages. No network.
 */
import { spawnSync } from 'node:child_process';
import {
  act,
  cleanup,
  fireEvent,
  render,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';

import { App } from '../../src/app/App';
import { text, type Language } from '../../src/i18n';
import { resetArea } from '../../src/state/area-actions';
import { clearArea } from '../../src/state/store';
import type { LayerPayload } from '../../src/stage/layers/payload';

/** The two mounted counts, and the unit each must read in each language. */
const MOUNTED_COUNTS = [5, 0];
const ACCIDENT_UNIT = {
  en: ['road accidents', 'road accidents'],
  ar: ['حوادث مرورية', 'حادث مروري'],
} as const;

type Body = {
  status: string;
  reason?: string;
  facts: { fact_id: string; period: string; value?: unknown }[];
  payload: LayerPayload;
};
let http: Record<
  'accidents' | 'rail_plan' | 'geography_missing' | 'source_missing',
  Body
> & { release: unknown; chains: Record<string, unknown> };

beforeAll(() => {
  const run = spawnSync(
    'uv',
    [
      'run',
      '--locked',
      'python',
      '-P',
      '-s',
      '-m',
      'pytest',
      '-c',
      'pyproject.toml',
      '--rootdir',
      '.',
      '-p',
      'no:cacheprovider',
      'product/tests/test_accident_mounted_http.py::test_mounted_accident_bodies_are_the_web_fixture',
      '-q',
      '-s',
    ],
    { cwd: '..', encoding: 'utf8', env: { ...process.env, UV_OFFLINE: '1' } },
  );
  expect(run.status, run.stderr + run.stdout).toBe(0);
  const line = run.stdout
    .split('\n')
    .find((row) => row.startsWith('ACCIDENT_PROJECTION='));
  expect(line).toBeTruthy();
  http = JSON.parse(line!.slice('ACCIDENT_PROJECTION='.length));
}, 120_000);

afterEach(() => {
  cleanup();
  resetArea();
  clearArea();
  vi.unstubAllGlobals();
  window.history.replaceState(null, '', '/');
});

function serve(accidents: Body) {
  vi.stubGlobal('fetch', async (path: string) => {
    const body =
      path === '/api/release'
        ? http.release
        : path === '/api/layers/accidents'
          ? accidents
          : path === '/api/layers/rail_plan'
            ? http.rail_plan
            : path.startsWith('/api/facts/')
              ? http.chains[path.split('/')[3]!]
              : {};
    return { ok: true, status: 200, json: async () => structuredClone(body) };
  });
}

async function chooseAccidents(language: Language) {
  window.history.replaceState(null, '', language === 'ar' ? '/?lang=ar' : '/');
  const view = render(<App />);
  const guided = [...view.container.querySelectorAll('button')].find(
    (button) => button.textContent === text(language, 'opening.guided'),
  )!;
  fireEvent.click(guided);
  const chooser = view.container.querySelector('.layer-chooser select')!;
  expect(
    [...chooser.querySelectorAll('option')].find(
      (option) => option.value === 'accidents',
    )?.textContent,
  ).toBe(text(language, 'layers.name.accidents'));
  fireEvent.change(chooser, { target: { value: 'accidents' } });
  await waitFor(() =>
    expect(
      view.container.querySelector('[data-part="access-pending"]'),
    ).not.toBeNull(),
  );
  return view.container;
}

function shared(plate: Element, language: Language) {
  const access = plate.querySelector('[data-part="access-pending"]')!;
  expect(access.textContent).toBe(text(language, 'layers.access.pending'));
  expect(access.querySelector('[data-fact-chip]')).toBeNull();
  expect(plate.querySelector('[data-legend="station"]')).not.toBeNull();
  const station = http.rail_plan.payload.layers[0]!.features[0]!;
  expect(
    plate.querySelector(`[data-feature="${station.feature_id}"]`),
  ).not.toBeNull();
  expect(plate.querySelector('[data-part="layer-refusal"]')).toBeNull();
  const clone = plate.cloneNode(true) as HTMLElement;
  clone.querySelectorAll('[data-fact-chip]').forEach((node) => node.remove());
  expect(clone.textContent).not.toMatch(/\p{Nd}/u);
  expect(plate.outerHTML).not.toContain('pending-native-review');
}

for (const language of ['en', 'ar'] as const) {
  it(`shows accident outlines and count beside planned rail and pending access in ${language}`, async () => {
    serve(http.accidents);
    const container = await chooseAccidents(language);
    const plate = container.querySelector('[data-part="public-layers"]')!;
    expect(plate.getAttribute('dir')).toBe(language === 'ar' ? 'rtl' : 'ltr');
    shared(plate, language);
    expect(plate.querySelector('[data-part="layer-no-data"]')).toBeNull();
    expect(plate.querySelector('[data-credit="accidents"]')).not.toBeNull();
    const features = http.accidents.payload.layers[0]!.features;
    expect(features.map((f) => f.geometry_kind)).toEqual([
      'outline',
      'outline',
    ]);
    for (const feature of features)
      expect(
        plate.querySelector(`[data-feature="${feature.feature_id}"]`),
      ).not.toBeNull();
    const first = features[0]!;
    act(() =>
      fireEvent.click(
        plate.querySelector(`[data-feature="${first.feature_id}"]`)!,
      ),
    );
    const panel = plate.querySelector(
      '[data-part="feature-panel"][data-layer="accidents"]',
    )!;
    const count = panel.querySelector(
      `[data-fact-chip="value"][data-fact-id="${first.fact_id}"]`,
    )!;
    expect(count.getAttribute('data-state')).toBe('ready');
    const context = panel.querySelector('[data-part="accident-context"]')!;
    expect(context.getAttribute('data-zone')).toBe(first.source_zone);
    // RV1 finding 2: shown from the zone fact of the count's own row.
    const zone = http.accidents.facts.find(
      (f) => f.fact_id === first.source_zone_fact_id,
    )!;
    expect(zone.value).toBe(first.source_zone);
    expect(
      context.querySelector(`[data-record="${zone.fact_id}"]`)!.textContent,
    ).toContain(String(zone.value));
    expect(context.getAttribute('data-period')).toBe(
      http.accidents.facts.find((f) => f.fact_id === first.fact_id)!.period,
    );
    expect(
      context.querySelector('[data-caveat="accidents"]')!.textContent,
    ).toBe(text(language, 'layers.accidents.caveat'));
    shared(plate, language);
  });

  // CF1 finding 1: each mounted count (five and zero) reads as road
  // accidents in the form its count takes, never as people.
  it(`labels each mounted accident count as road accidents in ${language}`, async () => {
    serve(http.accidents);
    const container = await chooseAccidents(language);
    const plate = container.querySelector('[data-part="public-layers"]')!;
    const words = ACCIDENT_UNIT[language];
    const features = http.accidents.payload.layers[0]!.features;
    expect(features).toHaveLength(2);
    for (const [index, feature] of features.entries()) {
      act(() =>
        fireEvent.click(
          plate.querySelector(`[data-feature="${feature.feature_id}"]`)!,
        ),
      );
      const count = http.accidents.facts.find(
        (f) => f.fact_id === feature.fact_id,
      )!;
      expect(count.value).toBe(MOUNTED_COUNTS[index]);
      const chip = plate.querySelector(
        `[data-part="feature-panel"] [data-fact-chip="value"][data-fact-id="${feature.fact_id}"]`,
      )!;
      expect(chip.getAttribute('data-state')).toBe('ready');
      const unit = chip.querySelector('.chip-unit')!.textContent;
      expect(unit).toBe(words[index]);
      expect(unit).not.toBe(text(language, 'unit.count'));
      expect(chip.getAttribute('aria-label')).toContain(words[index]);
      expect(chip.textContent).not.toContain(text(language, 'unit.count'));
    }
    shared(plate, language);
  });

  for (const key of ['geography_missing', 'source_missing'] as const)
    it(`labels ${key} with its closed reason beside the rail in ${language}`, async () => {
      serve(http[key]);
      const container = await chooseAccidents(language);
      const plate = container.querySelector('[data-part="public-layers"]')!;
      const absent = plate.querySelector('[data-part="layer-no-data"]')!;
      expect(absent.getAttribute('data-reason')).toBe(http[key].reason);
      expect(absent.textContent).toBe(
        text(language, `layers.accidents.no_data.accident_${key}`),
      );
      expect(plate.querySelector('[data-feature^="accidents:"]')).toBeNull();
      expect(plate.querySelector('[data-credit="accidents"]')).toBeNull();
      shared(plate, language);
    });
}
