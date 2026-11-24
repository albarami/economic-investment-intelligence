// @vitest-environment jsdom
/** S3-T16 boxes 3 and 4. Invented fixtures; the scrubber never moves an hourly figure. */
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { Layer } from '@deck.gl/core';

import { formatFactValue } from '../../src/facts/formatters';
import { text, type Language } from '../../src/i18n';
import { Stage } from '../../src/stage/Stage';
import { PublicLayers } from '../../src/stage/layers/PublicLayers';
import { acceptPayload } from '../../src/stage/layers/refuse';
import { deckLayers, overlayFor } from '../../src/stage/layers/overlay';
import { basePayload, CHAIN_ID, NIGHT_PARENT, plain } from '../fixtures/layers';
import { layerRegistry } from '../fixtures/layer-registry';

/** FE-106 stored hours of this fixture. The clock is not that hour control. */
const STORED_HOURS = ['0', '6', '12', '18'];

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

type HourlyFigure = { hour: string; text: string };

function outsideStoredChange(
  storedHours: readonly string[],
  before: readonly HourlyFigure[],
  after: readonly HourlyFigure[],
): HourlyFigure | null {
  for (const next of after) {
    if (storedHours.includes(next.hour)) continue;
    const previous = before.find((item) => item.hour === next.hour);
    if (previous && previous.text !== next.text) return next;
  }
  return null;
}

function readHourlyFigures(root: ParentNode): HourlyFigure[] {
  return [...root.querySelectorAll('[data-hour]')].map((node) => ({
    hour: node.getAttribute('data-hour') ?? '',
    text: node.textContent ?? '',
  }));
}

function drawingMembers() {
  return {
    bind: vi.fn(),
    unbind: vi.fn(),
    project: vi.fn(() => ({ x: 0, y: 0 })),
    unproject: vi.fn(() => ({ longitude: 0, latitude: 0 })),
    suspendGestures: vi.fn(),
    restoreGestures: vi.fn(),
    centre: vi.fn(() => ({ longitude: 0, latitude: 0 })),
    bindView: vi.fn(),
    unbindView: vi.fn(),
  };
}

const modes = {
  open: { available: true, reason: null },
  satellite: { available: false, reason: 'offline' },
  photoreal: { available: false, reason: 'cap_reached', meter: null },
};

function nightScene() {
  return basePayload({
    layers: [
      {
        key: 'night_lights',
        visible: true,
        source_chain_fact_id: CHAIN_ID,
        source_id: 'src_night',
        features: [
          {
            feature_id: 'feat_night',
            metric_key: 'radiance_class',
            provenance: 'public',
            subject: 'statistic',
            geometry_kind: 'hex',
            cell: NIGHT_PARENT,
            resolution: 8,
            fact_id: CHAIN_ID,
            class_id: 'band_high',
          },
        ],
      },
    ],
    sources: [
      {
        sourceId: 'src_night',
        attribution: [plain('SYN-fixture NASA acknowledgement')],
        retrievalDate: '2024-03-14',
        publisher: [plain('Sample Night Press')],
        datasetOrPage: 'Sample night page',
        licenceOrTerms: 'Terms recorded for this sample',
      },
    ],
    night: {
      month: '2024-03',
      direction: 'higher',
      class_id: 'band_high',
      unit: 'radiance_nw_cm2_sr',
      caveat_key: 'night_lights_not_activity',
    },
  });
}

function calendarMonthText(month: string, language: Language): string {
  const formatted = formatFactValue(month, 'calendar_month', language);
  if (!formatted.ok) throw new Error(formatted.reason);
  return formatted.text;
}

function shownCalendarMonth(root: ParentNode): string {
  return root.querySelector('[data-kind="calendar_month"]')?.textContent ?? '';
}

it('keeps hourly figures outside stored hours still when the scrubber moves', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, json: async () => modes }),
  );
  const setClock = vi.fn();
  const payload = nightScene();
  const month = payload.night?.month ?? '';
  const registry = layerRegistry([
    { id: CHAIN_ID, metric: 'radiance_class', table: 'pub_night_lights' },
  ]);
  const view = render(
    <Stage
      language="en"
      theme="dark"
      extractUrl="/SYN-map.pmtiles"
      dayBasis="2026-06-01"
      layerPayload={payload}
      registry={registry}
      onOpenChain={() => undefined}
      overlayFactory={() => ({ onAdd: vi.fn(), onRemove: vi.fn() })}
      mapStarter={() => ({
        ...drawingMembers(),
        setClock,
        mountOverlay: vi.fn(),
        remove: vi.fn(),
      })}
    />,
  );
  await waitFor(() => expect(view.getByRole('slider')).toBeTruthy());
  const legend = view.container.querySelector('[data-part="night-legend"]');
  expect(legend).not.toBeNull();
  const expectedMonth = calendarMonthText(month, 'en');
  expect(shownCalendarMonth(view.container)).toBe(expectedMonth);
  expect(expectedMonth).not.toBe('');
  const before = readHourlyFigures(view.container);
  const chipsBefore = [
    ...view.container.querySelectorAll('[data-fact-chip="value"]'),
  ].map((node) => node.textContent);
  const legendBefore = legend?.textContent;
  fireEvent.change(view.getByRole('slider'), { target: { value: '0.125' } });
  expect(setClock).toHaveBeenCalled();
  expect(payload.night?.month).toBe(month);
  expect(shownCalendarMonth(view.container)).toBe(expectedMonth);
  expect(
    view.container.querySelector('[data-part="night-legend"]')?.textContent,
  ).toBe(legendBefore);
  expect(
    outsideStoredChange(
      STORED_HOURS,
      before,
      readHourlyFigures(view.container),
    ),
  ).toBeNull();
  expect(
    [...view.container.querySelectorAll('[data-fact-chip="value"]')].map(
      (node) => node.textContent,
    ),
  ).toEqual(chipsBefore);
  const plant = outsideStoredChange(
    STORED_HOURS,
    [{ hour: '3', text: '10' }],
    [{ hour: '3', text: '11' }],
  );
  expect(plant?.hour).toBe('3');
  expect(
    outsideStoredChange(
      STORED_HOURS,
      [{ hour: '6', text: '10' }],
      [{ hour: '6', text: '11' }],
    ),
  ).toBeNull();
});

function duskTiedToChip(input: {
  producedIds: readonly string[];
  shownIds: readonly string[];
  chipMonth: string | null;
  payloadMonth: string;
}): boolean {
  if (input.chipMonth !== input.payloadMonth) return false;
  if (input.shownIds.length === 0) return false;
  return input.shownIds.every(
    (id) => id.startsWith('night_lights:') && input.producedIds.includes(id),
  );
}

function activityWording(legend: ParentNode): boolean {
  const unit = legend.querySelector('[data-legend="unit"]')?.textContent ?? '';
  const caveat = legend.querySelector('[data-caveat]')?.textContent ?? '';
  if (/activity/i.test(unit) || unit.includes('نشاط')) return true;
  const mentions = /activity/i.test(caveat) || caveat.includes('نشاط');
  if (!mentions) return false;
  const denial =
    caveat.includes('not a measure of business activity') ||
    caveat.includes('وليس مقياساً لنشاط');
  return !denial;
}

function shownNightIds(layers: readonly Layer[]): string[] {
  return layers
    .filter(
      (layer) =>
        layer.id.startsWith('night_lights:') && layer.props.opacity === 1,
    )
    .map((layer) => layer.id);
}

it.each(['en', 'ar'] as const)(
  'ties the dusk switch to the layer month chip and refuses activity wording in %s',
  (language) => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    const payload = nightScene();
    const month = payload.night?.month ?? '';
    const registry = layerRegistry([
      { id: CHAIN_ID, metric: 'radiance_class', table: 'pub_night_lights' },
    ]);
    const view = render(
      <PublicLayers
        payload={payload}
        language={language}
        registry={registry}
        onOpenChain={() => undefined}
      />,
    );
    const legend = view.container.querySelector('[data-part="night-legend"]');
    expect(legend).not.toBeNull();
    const chipMonth = legend
      ?.querySelector('[data-kind="calendar_month"]')
      ?.getAttribute('data-record');
    expect(chipMonth).toBe(month);
    expect(shownCalendarMonth(view.container)).toBe(
      calendarMonthText(month, language),
    );
    const replacement = '2023-11';
    const replaced = nightScene();
    if (!replaced.night) throw new Error('night fixture');
    replaced.night = { ...replaced.night, month: replacement };
    view.rerender(
      <PublicLayers
        payload={replaced}
        language={language}
        registry={registry}
        onOpenChain={() => undefined}
      />,
    );
    const replacedLegend = view.container.querySelector(
      '[data-part="night-legend"]',
    );
    expect(
      replacedLegend
        ?.querySelector('[data-kind="calendar_month"]')
        ?.getAttribute('data-record'),
    ).toBe(replacement);
    expect(shownCalendarMonth(view.container)).toBe(
      calendarMonthText(replacement, language),
    );
    expect(
      replacedLegend?.querySelector('[data-legend="unit"]')?.textContent,
    ).toBe(text(language, 'unit.radiance_nw_cm2_sr'));
    expect(activityWording(replacedLegend as ParentNode)).toBe(false);
    const accepted = acceptPayload(replaced, registry);
    expect(accepted.ok).toBe(true);
    if (!accepted.ok) return;
    expect(accepted.draw.night?.month).toBe(replacement);
    expect(shownCalendarMonth(view.container)).toBe(
      calendarMonthText(accepted.draw.night?.month ?? '', language),
    );
    const producedIds = deckLayers(accepted.draw.layers, null)
      .filter((layer) => layer.id.startsWith('night_lights:'))
      .map((layer) => layer.id);
    const clock = overlayFor(replaced, null, registry, true) as {
      applySun: (
        direction: readonly number[],
        target: { setLight: () => void; setSky: () => void },
      ) => void;
      setProps: (props: { layers?: Layer[] }) => void;
    };
    const setProps = vi.spyOn(clock, 'setProps');
    const sky = { setLight: vi.fn(), setSky: vi.fn() };
    clock.applySun([0, 0, -1], sky);
    clock.applySun([0, 0, 1], sky);
    expect(
      duskTiedToChip({
        producedIds,
        shownIds: shownNightIds(setProps.mock.lastCall?.[0].layers ?? []),
        chipMonth: replacement,
        payloadMonth: replacement,
      }),
    ).toBe(true);
    expect(
      duskTiedToChip({
        producedIds,
        shownIds: ['night_lights:2019-01'],
        chipMonth: replacement,
        payloadMonth: replacement,
      }),
    ).toBe(false);
    const planted = (replacedLegend as HTMLElement).cloneNode(
      true,
    ) as HTMLElement;
    const unit = planted.querySelector('[data-legend="unit"]');
    expect(unit).not.toBeNull();
    if (unit) unit.textContent = 'Night-time activity';
    expect(activityWording(planted)).toBe(true);
  },
);
