// @vitest-environment jsdom
/** Invented scenario and transport fixtures; no provider is contacted. */
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { basePayload, CHAIN_ID, NIGHT_PARENT, plain } from '../fixtures/layers';
import { layerRegistry } from '../fixtures/layer-registry';
import { Stage, MapCredits } from '../../src/stage/Stage';
import {
  completeInput,
  factId,
  registryFrom,
  makeBinding,
  makeFact,
  makeSource,
  makeLineage,
} from '../fixtures/facts';

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

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const modes = {
  open: { available: true, reason: null },
  satellite: { available: false, reason: 'offline' },
  photoreal: { available: false, reason: 'cap_reached', meter: null },
};
const registry = registryFrom({
  ...completeInput(),
  facts: [0, 1].map((index) =>
    makeBinding({
      fact: makeFact({
        fact_id: factId(index),
        value: index === 0 ? 48 : 52,
        geography: { kind: 'user_scenario', area_id: 'SYN-area' },
        input_classes: ['public', 'user_input'],
      }),
    }),
  ),
  lineages: [makeLineage({ inputClasses: ['public', 'user_input'] })],
  sources: [makeSource({ kind: 'reviewed_config' })],
});
const comparison = {
  kind: 'scenario',
  baselineFactId: factId(0),
  changedFactId: factId(1),
} as const;

it('mounts the controls, reads local availability without cache and keeps open on refusal', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue({ ok: true, json: async () => modes });
  vi.stubGlobal('fetch', fetcher);
  const view = render(
    <Stage
      language="en"
      theme="dark"
      extractUrl="/SYN-map.pmtiles"
      mapStarter={() => ({
        ...drawingMembers(),
        remove: vi.fn(),
        mountOverlay: vi.fn(),
      })}
      registry={registry}
      comparison={comparison}
    />,
  );
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      '/api/map-modes',
      expect.objectContaining({ cache: 'no-store' }),
    ),
  );
  await waitFor(() =>
    expect(
      view.getByRole('radio', { name: 'Satellite' }).hasAttribute('disabled'),
    ).toBe(true),
  );
  expect(
    view
      .getByRole('radio', { name: /Photorealistic/ })
      .hasAttribute('disabled'),
  ).toBe(true);
  fireEvent.click(view.getByRole('radio', { name: /Photorealistic/ }));
  expect(
    view.getByRole('radio', { name: 'Open map' }).getAttribute('aria-checked'),
  ).toBe('true');
  expect(view.getByRole('slider')).toBeTruthy();
  expect(view.getByRole('group', { name: 'Baseline' }).textContent).toContain(
    '48',
  );
  expect(
    view.getByRole('group', { name: 'Changed scenario' }).textContent,
  ).toContain('52');
  fireEvent.click(view.getByRole('button', { name: 'Show changed scenario' }));
  expect(view.getByRole('group', { name: 'Baseline' }).hidden).toBe(false);
  fireEvent.click(view.getByRole('button', { name: 'Reset comparison' }));
  expect(
    view
      .getByRole('button', { name: 'Show baseline' })
      .getAttribute('aria-pressed'),
  ).toBe('true');
});

it.each(['en', 'ar'] as const)(
  'contains all controls in the Stage flow in %s at narrow width',
  async (language) => {
    const { readFileSync } = await import('node:fs');
    const style = document.createElement('style');
    style.textContent = readFileSync('src/styles/answer.css', 'utf8');
    document.head.append(style);
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => modes }),
    );
    const view = render(
      <div className="shell" style={{ width: '360px' }}>
        <Stage
          language={language}
          theme="dark"
          extractUrl={null}
          registry={registry}
          comparison={comparison}
        />
        <aside data-answer>Fixture answer</aside>
      </div>,
    );
    await waitFor(() =>
      expect(view.container.querySelector('.map-controls')).not.toBeNull(),
    );
    const controls =
      view.container.querySelector<HTMLElement>('.map-controls')!;
    expect(controls.dir).toBe(language === 'ar' ? 'rtl' : 'ltr');
    expect(getComputedStyle(controls).position).toBe('relative');
    expect(getComputedStyle(controls).flexWrap).toBe('wrap');
    expect(getComputedStyle(controls).maxInlineSize).toBe('100%');
    expect(getComputedStyle(controls).overflowWrap).toBe('anywhere');
    expect(controls.closest('.stage')).not.toBeNull();
    expect(
      view.container.querySelector('[data-answer]')?.contains(controls),
    ).toBe(false);
    for (const target of controls.querySelectorAll('button, input, summary')) {
      expect(getComputedStyle(target).minBlockSize).toBe('44px');
      expect(getComputedStyle(target).minInlineSize).toBe('44px');
    }
    style.remove();
  },
);

it('routes a selected mode to the renderer and confines its runtime credit to that mode', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ...modes,
        satellite: { available: true, reason: null },
      }),
    }),
  );
  const setMode = vi.fn(async (_mode, credit) => {
    credit('SYN-runtime-credit');
  });
  const handle = {
    ...drawingMembers(),
    remove: vi.fn(),
    mountOverlay: vi.fn(),
    setMode,
  };
  const view = render(
    <Stage
      language="en"
      theme="dark"
      extractUrl="/SYN-map.pmtiles"
      mapStarter={() => handle}
    />,
  );
  await waitFor(() =>
    expect(
      view.getByRole('radio', { name: 'Satellite' }).hasAttribute('disabled'),
    ).toBe(false),
  );
  fireEvent.click(view.getByRole('radio', { name: 'Satellite' }));
  await waitFor(() =>
    expect(setMode).toHaveBeenCalledWith('satellite', expect.any(Function)),
  );
  const credit = view.getByText('SYN-runtime-credit');
  expect(credit.closest('details')?.open).toBe(false);
  expect(credit.closest('[data-part="attribution"]')).not.toBeNull();
  fireEvent.click(view.getByRole('radio', { name: 'Open map' }));
  await waitFor(() =>
    expect(view.queryByText('SYN-runtime-credit')).toBeNull(),
  );
});

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
        publisher: [
          plain('Sample Night Press'),
          {
            kind: 'reference',
            referenceKind: 'published_text',
            value: '7',
            recordId: 'night-press',
          },
        ],
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

it('scrubs light independently of stored facts and the night layer month, with no district or playback', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, json: async () => modes }),
  );
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: true })),
  );
  const payload = nightScene();
  const payloadBefore = JSON.stringify(payload);
  const facts = layerRegistry([
    { id: CHAIN_ID, metric: 'radiance_class', table: 'pub_night_lights' },
  ]);
  const setClock = vi.fn();
  const mountOverlay = vi.fn();
  const overlayFactory = vi.fn(() => ({ onAdd: vi.fn(), onRemove: vi.fn() }));
  const handle = {
    ...drawingMembers(),
    setClock,
    mountOverlay,
    remove: vi.fn(),
  };
  const view = render(
    <Stage
      language="en"
      theme="dark"
      extractUrl="/SYN-map.pmtiles"
      dayBasis="2026-06-01"
      mapStarter={() => handle}
      layerPayload={payload}
      registry={facts}
      overlayFactory={overlayFactory}
    />,
  );
  await waitFor(() => expect(mountOverlay).toHaveBeenCalledTimes(1));
  expect(setClock).toHaveBeenCalledWith(Date.parse('2026-05-31T21:00:00Z'));
  const before = view.container.querySelector(
    '[data-part="night-legend"]',
  )!.textContent;
  fireEvent.change(view.getByRole('slider'), { target: { value: '0.123' } });
  expect(setClock).toHaveBeenLastCalledWith(
    Date.parse('2026-05-31T21:00:00Z') + 0.123 * 24 * 60 * 60 * 1000,
  );
  expect(
    view.container.querySelector('[data-part="night-legend"]')!.textContent,
  ).toBe(before);
  expect(before).toContain('March 2024');
  expect(before).toContain('SYN-fixture NASA acknowledgement');
  expect(before).toContain('Night-time radiance');
  expect(JSON.stringify(payload)).toBe(payloadBefore);
  expect(overlayFactory).toHaveBeenCalledTimes(1);
  expect(overlayFactory.mock.calls[0][0]).toBe(payload);
  expect(view.queryByRole('button', { name: /play/i })).toBeNull();
  expect(view.queryByRole('combobox', { name: /district/i })).toBeNull();
  const controls = view.container
    .querySelector('.map-controls')!
    .cloneNode(true) as HTMLElement;
  controls
    .querySelectorAll('[data-fact-chip]')
    .forEach((chip) => chip.remove());
  expect(controls.textContent).not.toMatch(/\p{N}/u);
});

it('starts an available remote mode without requiring an open-map extract, then restores plain open', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ...modes,
        satellite: { available: true, reason: null },
      }),
    }),
  );
  const handle = {
    ...drawingMembers(),
    remove: vi.fn(),
    mountOverlay: vi.fn(),
    setMode: vi.fn(async () => undefined),
  };
  const start = vi.fn(() => handle);
  const view = render(
    <Stage language="en" theme="dark" extractUrl={null} mapStarter={start} />,
  );
  await waitFor(() =>
    expect(
      view.getByRole('radio', { name: 'Satellite' }).hasAttribute('disabled'),
    ).toBe(false),
  );
  expect(start).not.toHaveBeenCalled();
  fireEvent.click(view.getByRole('radio', { name: 'Satellite' }));
  await waitFor(() =>
    expect(handle.setMode).toHaveBeenCalledWith(
      'satellite',
      expect.any(Function),
    ),
  );
  fireEvent.click(view.getByRole('radio', { name: 'Open map' }));
  await waitFor(() => expect(handle.remove).toHaveBeenCalled());
  expect(
    view.container.querySelector('.stage')?.getAttribute('data-state'),
  ).toBe('asset-absent');
});

it.each(['failure', 'bad-json', 'bad-schema', 'http'] as const)(
  'keeps open when availability is %s',
  async (kind) => {
    const fetcher = vi.fn(async () => {
      if (kind === 'failure') throw new Error('SYN-failure');
      return {
        ok: kind !== 'http',
        json: async () => {
          if (kind === 'bad-json') throw new Error('SYN-json');
          return { wrong: true };
        },
      };
    });
    vi.stubGlobal('fetch', fetcher);
    const view = render(<Stage language="en" theme="dark" extractUrl={null} />);
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    expect(
      view
        .getByRole('radio', { name: 'Open map' })
        .getAttribute('aria-checked'),
    ).toBe('true');
    expect(
      view
        .getByRole('radio', { name: /Photorealistic/ })
        .hasAttribute('disabled'),
    ).toBe(true);
  },
);
it('renderer refusal returns to open and ignores late credit from the abandoned mode', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ...modes,
        satellite: { available: true, reason: null },
      }),
    }),
  );
  let late: (value: string) => void = () => undefined;
  const handle = {
    ...drawingMembers(),
    remove: vi.fn(),
    mountOverlay: vi.fn(),
    setMode: vi.fn(async (mode, credit) => {
      if (mode === 'satellite') {
        late = credit;
        throw new Error('SYN-refused');
      }
    }),
  };
  const view = render(
    <Stage
      language="en"
      theme="dark"
      extractUrl="/SYN-map.pmtiles"
      mapStarter={() => handle}
    />,
  );
  await waitFor(() =>
    expect(
      view.getByRole('radio', { name: 'Satellite' }).hasAttribute('disabled'),
    ).toBe(false),
  );
  fireEvent.click(view.getByRole('radio', { name: 'Satellite' }));
  await waitFor(() =>
    expect(
      view
        .getByRole('radio', { name: 'Open map' })
        .getAttribute('aria-checked'),
    ).toBe('true'),
  );
  expect(
    view.getByRole('radio', { name: 'Satellite' }).hasAttribute('disabled'),
  ).toBe(true);
  late('SYN-late');
  expect(view.queryByText('SYN-late')).toBeNull();
});

it('keeps the scrubbed fraction and map clock when the civil day changes', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, json: async () => modes }),
  );
  const handles = [0, 1].map(() => ({
    ...drawingMembers(),
    setClock: vi.fn(),
    mountOverlay: vi.fn(),
    remove: vi.fn(),
  }));
  const start = vi
    .fn()
    .mockReturnValueOnce(handles[0])
    .mockReturnValueOnce(handles[1]);
  const props = {
    language: 'en' as const,
    theme: 'dark' as const,
    extractUrl: '/SYN-map.pmtiles',
    mapStarter: start,
  };
  const view = render(<Stage {...props} dayBasis="2026-06-01" />);
  await waitFor(() => expect(handles[0].setClock).toHaveBeenCalled());
  fireEvent.change(view.getByRole('slider'), { target: { value: '0.25' } });
  expect(handles[0].setClock).toHaveBeenLastCalledWith(
    Date.parse('2026-06-01T03:00:00Z'),
  );
  view.rerender(<Stage {...props} dayBasis="2026-06-02" />);
  await waitFor(() => expect(handles[1].setClock).toHaveBeenCalled());
  expect((view.getByRole('slider') as HTMLInputElement).value).toBe('0.25');
  expect(handles[1].setClock).toHaveBeenLastCalledWith(
    Date.parse('2026-06-02T03:00:00Z'),
  );
  expect(start).toHaveBeenCalledTimes(2);
});

it('gives mounted Arabic Stage credits their own direction and isolates runtime text', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ...modes,
        satellite: { available: true, reason: null },
      }),
    }),
  );
  const handle = {
    ...drawingMembers(),
    remove: vi.fn(),
    mountOverlay: vi.fn(),
    setMode: vi.fn(async (_mode, credit) => credit('SYN-runtime-credit')),
  };
  const start = () => handle;
  const view = render(
    <Stage
      language="ar"
      theme="dark"
      extractUrl="/SYN-map.pmtiles"
      mapStarter={start}
    />,
  );
  expect(
    view.container
      .querySelector('[data-part="attribution"]')
      ?.getAttribute('dir'),
  ).toBe('rtl');
  await waitFor(() =>
    expect(
      view.container.querySelectorAll('[role="radio"]:not([disabled])'),
    ).toHaveLength(2),
  );
  fireEvent.click(view.getAllByRole('radio')[1]);
  await waitFor(() =>
    expect(view.queryByText('SYN-runtime-credit')).not.toBeNull(),
  );
  expect(view.getByText('SYN-runtime-credit').getAttribute('dir')).toBe('auto');
});

it('payload replacement preserves the running map and selected mode', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            open: { available: true, reason: null },
            satellite: { available: false, reason: 'no_key' },
            photoreal: { available: true, reason: null, meter: null },
          }),
        ),
    ),
  );
  const handle = {
    ...drawingMembers(),
    remove: vi.fn(),
    mountOverlay: vi.fn(),
    setMode: vi.fn(async () => undefined),
  };
  const starter = vi.fn(() => handle);
  const factory = vi.fn(() => ({ onAdd: vi.fn(), onRemove: vi.fn() }));
  const first = nightScene();
  const second = nightScene();
  const props = {
    language: 'en' as const,
    theme: 'dark' as const,
    extractUrl: '/SYN-map.pmtiles',
    mapStarter: starter,
    overlayFactory: factory,
    registry: layerRegistry([
      { id: CHAIN_ID, metric: 'radiance_class', table: 'pub_night_lights' },
    ]),
  };
  const view = render(<Stage {...props} layerPayload={first} />);
  await waitFor(() => expect(handle.mountOverlay).toHaveBeenCalledTimes(1));
  const legend = view.container.querySelector('[data-part="night-legend"]');
  expect(legend).not.toBeNull();
  const legendText = legend?.textContent;
  fireEvent.click(view.getByRole('radio', { name: /Photorealistic/ }));
  await waitFor(() =>
    expect(handle.setMode).toHaveBeenCalledWith(
      'photoreal',
      expect.any(Function),
    ),
  );
  view.rerender(<Stage {...props} layerPayload={second} />);
  await waitFor(() => expect(handle.mountOverlay).toHaveBeenCalledTimes(2));
  expect(view.container.querySelector('[data-part="night-legend"]')).toBe(
    legend,
  );
  expect(legend?.textContent).toBe(legendText);
  expect(starter).toHaveBeenCalledTimes(1);
  expect(handle.remove).not.toHaveBeenCalled();
  expect(
    view
      .getByRole('radio', { name: /Photorealistic/ })
      .getAttribute('aria-checked'),
  ).toBe('true');
});

it.each([
  ['en', 'photoreal'],
  ['ar', 'photoreal'],
  ['en', 'satellite'],
  ['ar', 'satellite'],
] as const)(
  'runtime credit numerals stay inside a reference chip in %s / %s',
  (language, mode) => {
    const credit = 'Invented credit 2026';
    const view = render(
      <MapCredits language={language} mode={mode} credit={credit} />,
    );
    const value = view.getByText(credit);
    expect(value.closest('[data-fact-chip="reference"]')).not.toBeNull();
    expect(value.closest('bdi')).not.toBeNull();
    expect(view.container.textContent).toContain(credit);
  },
);
