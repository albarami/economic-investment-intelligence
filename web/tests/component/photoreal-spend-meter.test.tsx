// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { FactChip } from '../../src/facts/FactChip';
import { Stage } from '../../src/stage/Stage';
import { text } from '../../src/i18n';
import { MapModeSwitch } from '../../src/stage/MapModeSwitch';
import { selectedMode } from '../../src/stage/map-modes';
import { operationalMeter as meter } from '../fixtures/operational-meter';
import {
  deferredTiles,
  registerJournalOrderTests,
} from '../fixtures/spend-order';

const state = vi.hoisted(() => ({
  maps: [] as object[],
  overlays: [] as { props: { layers?: PhotorealLayer[] } }[],
}));

interface PhotorealLayer {
  id: string;
  props: { loadOptions: { fetch: (input: string) => Promise<Response> } };
}

vi.mock('maplibre-gl', async () => {
  const { mapLibreDouble } = await import('../fixtures/renderer-doubles');
  return mapLibreDouble(state);
});

vi.mock('@deck.gl/maplibre', async () => {
  const { overlayDouble } = await import('../fixtures/renderer-doubles');
  return overlayDouble(state);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  state.maps.length = 0;
  state.overlays.length = 0;
});

const capped = {
  open: { available: true, reason: null },
  satellite: { available: false, reason: 'no_key' as const },
  photoreal: {
    available: false,
    reason: 'cap_reached' as const,
    meter,
  },
};

it.each(['en', 'ar'] as const)(
  'disables photoreal at the hard stop, shows the reason, and keeps the open map in %s',
  (language) => {
    const view = render(
      <MapModeSwitch
        language={language}
        modes={capped}
        selected="photoreal"
        onChange={() => undefined}
      />,
    );
    expect(view.getByRole('radiogroup').getAttribute('dir')).toBe(
      language === 'ar' ? 'rtl' : 'ltr',
    );
    const open = view.getByRole('radio', {
      name: text(language, 'mapModes.open'),
    });
    expect(open.getAttribute('aria-checked')).toBe('true');
    const photo = view.getByRole('radio', {
      name: text(language, 'mapModes.photoreal'),
    }) as HTMLButtonElement;
    expect(photo.disabled).toBe(true);
    expect(view.container.textContent).toContain(
      text(language, 'mapModes.cap_reached'),
    );
    expect(selectedMode('photoreal', capped)).toBe('open');
  },
);

it.each(['en', 'ar'] as const)(
  'keeps the spend warning on and every numeral inside a fact chip in %s',
  (language) => {
    const view = render(
      <FactChip
        variant="operational"
        language={language}
        meter={meter}
        reason={null}
      />,
    );
    const chip = view.container.querySelector(
      '[data-fact-chip="operational"]',
    )!;
    expect(chip.getAttribute('dir')).toBe(language === 'ar' ? 'rtl' : 'ltr');
    expect(view.getByRole('status').textContent).toBe(
      text(language, 'operational.warning'),
    );
    fireEvent.click(view.getByRole('button'));
    expect(view.getByRole('status').textContent).toBe(
      text(language, 'operational.warning'),
    );
    const withoutNumerals = chip.cloneNode(true) as HTMLElement;
    withoutNumerals
      .querySelectorAll('.chip-num')
      .forEach((node) => node.remove());
    expect(withoutNumerals.textContent ?? '').not.toMatch(/\p{Nd}/u);
    expect(
      chip.querySelector('[data-quantity="requests"] .chip-num')?.textContent,
    ).toBe(String(meter.billable_requests));
    expect(
      chip.querySelector('[data-quantity="spend"] .chip-num')?.textContent,
    ).toBe(meter.spend_usd);
  },
);

const below = {
  ...meter,
  billable_requests: 6,
  spend_usd: '0.04275',
  warning: false,
};
const stillBelow = {
  ...meter,
  billable_requests: 7,
  spend_usd: '0.049875',
  warning: false,
};
const crossed = {
  ...meter,
  billable_requests: 8,
  spend_usd: '0.057',
  warning: true,
};
const later = {
  ...meter,
  billable_requests: 9,
  spend_usd: '0.064125',
  warning: true,
};
/** Canonical journal step. Accepted when the loader holds no token yet. */
const laterOrder = '9';

function quantity(view: { container: HTMLElement }, name: string) {
  return view.container.querySelector(`[data-quantity="${name}"] .chip-num`)
    ?.textContent;
}

function expectMountMeter(
  view: { container: HTMLElement },
  language: 'en' | 'ar',
) {
  expect(quantity(view, 'requests')).toBe(String(below.billable_requests));
  expect(quantity(view, 'spend')).toBe(below.spend_usd);
  expect(view.container.querySelector('[role="status"]')).toBeNull();
  expect(
    view.container
      .querySelector('[data-fact-chip="operational"]')
      ?.getAttribute('dir'),
  ).toBe(language === 'ar' ? 'rtl' : 'ltr');
}

function mountModes() {
  return JSON.stringify({
    open: { available: true, reason: null },
    satellite: { available: false, reason: 'no_key' },
    photoreal: { available: true, reason: null, meter: below },
  });
}

function viewCreated() {
  return new Response(JSON.stringify({ view_id: 'a'.repeat(32) }));
}

function refusalFetch() {
  const leaked = JSON.stringify(meter);
  const rejected = JSON.stringify({ ...meter, extra: true });
  return vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/map-modes') return new Response(mountModes());
    if (url === '/api/photoreal/views' && init?.method === 'POST') {
      return viewCreated();
    }
    const path = new URL(url, 'http://fixture.invalid').pathname;
    if (path === '/api/photoreal/3dtiles/rejected.json') {
      return new Response('{}', {
        status: 200,
        headers: {
          'x-spend-meter': rejected,
          'x-spend-order': laterOrder,
        },
      });
    }
    if (path === '/api/photoreal/3dtiles/error.json') {
      return new Response('{}', {
        status: 500,
        headers: {
          'x-spend-meter': leaked,
          'x-spend-order': laterOrder,
        },
      });
    }
    if (path === '/api/photoreal/3dtiles/absent-order.json') {
      return new Response('{}', {
        status: 200,
        headers: { 'x-spend-meter': leaked },
      });
    }
    if (path.startsWith('/api/imagery/')) {
      return new Response('{}', {
        status: 200,
        headers: {
          'x-attribution': 'SYN-credit',
          'x-spend-meter': leaked,
          'x-spend-order': laterOrder,
        },
      });
    }
    return new Response('{}', { status: 200 });
  });
}

async function openPhotoreal(
  language: 'en' | 'ar',
  fetcher: (
    url: string,
    init?: RequestInit,
  ) => Promise<Response> = refusalFetch(),
) {
  vi.stubGlobal('fetch', fetcher);
  const { startMap } = await import('../../src/stage/map-boot');
  const view = render(
    <Stage
      language={language}
      theme="dark"
      extractUrl="/SYN-map.pmtiles"
      mapStarter={startMap}
    />,
  );
  await waitFor(() =>
    expect(quantity(view, 'requests')).toBe(String(below.billable_requests)),
  );
  const control = view.getByRole('radio', {
    name: text(language, 'mapModes.photoreal'),
  });
  await waitFor(() => expect(control.hasAttribute('disabled')).toBe(false));
  fireEvent.click(control);
  let layer: PhotorealLayer | undefined;
  await waitFor(() => {
    layer = state.overlays
      .at(-1)
      ?.props.layers?.find((item) => item.id.startsWith('photoreal:'));
    expect(layer).toBeTruthy();
  });
  return { view, load: layer!.props.loadOptions.fetch, fetcher };
}

function liveFetcher() {
  const tiles = [
    { meter: 'not-json', order: '' },
    { meter: JSON.stringify(stillBelow), order: '7' },
    { meter: JSON.stringify(crossed), order: '8' },
    { meter: JSON.stringify(later), order: '9' },
  ];
  let tile = 0;
  return vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/map-modes') return new Response(mountModes());
    if (url === '/api/photoreal/views' && init?.method === 'POST') {
      return viewCreated();
    }
    if (url.startsWith('/api/photoreal/3dtiles/')) {
      const issued = tiles[tile++] ?? { meter: '', order: '' };
      const headers: Record<string, string> = {
        'x-spend-meter': issued.meter,
      };
      if (issued.order !== '') headers['x-spend-order'] = issued.order;
      return new Response('{}', { status: 200, headers });
    }
    return new Response(null, { status: 204 });
  });
}

function assertAdvisoryTiles(fetcher: { mock: { calls: unknown[][] } }) {
  const tileCalls = fetcher.mock.calls.filter(([url]) =>
    String(url).startsWith('/api/photoreal/3dtiles/'),
  );
  expect(tileCalls).toHaveLength(4);
  for (const [url] of tileCalls) {
    const parsed = new URL(String(url), 'http://fixture.invalid');
    expect([...parsed.searchParams.keys()]).toEqual(['view']);
    expect(parsed.searchParams.get('maximumScreenSpaceError')).toBeNull();
  }
  expect(
    fetcher.mock.calls.filter(([url]) => url === '/api/map-modes'),
  ).toHaveLength(1);
}

it.each(['en', 'ar'] as const)(
  'shows the server count, USD and warning after successful tiles cross 80 percent in %s',
  async (language) => {
    const fetcher = liveFetcher();
    vi.stubGlobal('fetch', fetcher);
    const { startMap } = await import('../../src/stage/map-boot');
    const view = render(
      <Stage
        language={language}
        theme="dark"
        extractUrl="/SYN-map.pmtiles"
        mapStarter={startMap}
      />,
    );
    await waitFor(() => expect(quantity(view, 'requests')).toBe('6'));
    expect(quantity(view, 'spend')).toBe(below.spend_usd);
    expect(view.container.querySelector('[role="status"]')).toBeNull();
    const control = view.getByRole('radio', {
      name: text(language, 'mapModes.photoreal'),
    });
    await waitFor(() => expect(control.hasAttribute('disabled')).toBe(false));
    fireEvent.click(control);
    let layer: PhotorealLayer | undefined;
    await waitFor(() => {
      layer = state.overlays
        .at(-1)
        ?.props.layers?.find((item) => item.id.startsWith('photoreal:'));
      expect(layer).toBeTruthy();
    });
    const load = layer!.props.loadOptions.fetch;
    await act(async () => {
      await load('/api/photoreal/3dtiles/malformed.json');
    });
    expect(quantity(view, 'requests')).toBe('6');
    expect(quantity(view, 'spend')).toBe(below.spend_usd);
    expect(view.container.querySelector('[role="status"]')).toBeNull();
    await act(async () => {
      await load('/api/photoreal/3dtiles/below.json');
    });
    await waitFor(() => expect(quantity(view, 'requests')).toBe('7'));
    expect(quantity(view, 'spend')).toBe(stillBelow.spend_usd);
    expect(view.container.querySelector('[role="status"]')).toBeNull();
    await act(async () => {
      await load('/api/photoreal/3dtiles/crossed.json');
    });
    await waitFor(() =>
      expect(view.container.querySelector('[role="status"]')?.textContent).toBe(
        text(language, 'operational.warning'),
      ),
    );
    expect(quantity(view, 'requests')).toBe('8');
    expect(quantity(view, 'spend')).toBe(crossed.spend_usd);
    const chip = view.container.querySelector(
      '[data-fact-chip="operational"]',
    )!;
    expect(chip.getAttribute('dir')).toBe(language === 'ar' ? 'rtl' : 'ltr');
    const withoutNumerals = chip.cloneNode(true) as HTMLElement;
    withoutNumerals
      .querySelectorAll('.chip-num')
      .forEach((node) => node.remove());
    expect(withoutNumerals.textContent ?? '').not.toMatch(/\p{Nd}/u);
    await act(async () => {
      await load('/api/photoreal/3dtiles/later.json');
    });
    await waitFor(() => expect(quantity(view, 'requests')).toBe('9'));
    expect(quantity(view, 'spend')).toBe(later.spend_usd);
    expect(control.hasAttribute('disabled')).toBe(false);
    assertAdvisoryTiles(fetcher);
  },
);

it.each(['en', 'ar'] as const)(
  'an absent spend header leaves the displayed meter in %s',
  async (language) => {
    const { view, load } = await openPhotoreal(language);
    await act(async () => {
      await load('/api/photoreal/3dtiles/absent.json');
    });
    expectMountMeter(view, language);
  },
);

it.each(['en', 'ar'] as const)(
  'a schema-rejected spend header leaves the displayed meter in %s',
  async (language) => {
    const { view, load } = await openPhotoreal(language);
    await act(async () => {
      await load('/api/photoreal/3dtiles/rejected.json');
    });
    expectMountMeter(view, language);
  },
);

it.each(['en', 'ar'] as const)(
  'a ready meter with an absent order token leaves the displayed meter in %s',
  async (language) => {
    const { view, load } = await openPhotoreal(language);
    await act(async () => {
      await load('/api/photoreal/3dtiles/absent-order.json');
    });
    expectMountMeter(view, language);
  },
);

function shown(view: { container: HTMLElement }, refusal: string | null) {
  return {
    refusal,
    requests: quantity(view, 'requests'),
    spend: quantity(view, 'spend'),
    warning:
      view.container.querySelector('[role="status"]')?.textContent ?? null,
  };
}

const untouched = {
  refusal: 'photoreal unavailable',
  requests: String(below.billable_requests),
  spend: below.spend_usd,
  warning: null,
};

async function refusedLoad(language: 'en' | 'ar', url: string) {
  const opened = await openPhotoreal(language);
  let refusal: string | null = null;
  await act(async () => {
    try {
      await opened.load(url);
    } catch (error) {
      refusal = error instanceof Error ? error.message : 'unknown';
    }
  });
  return { ...opened, refusal };
}

it.each(['en', 'ar'] as const)(
  'a spend header on an error response never reaches the meter in %s',
  async (language) => {
    const { view, fetcher, refusal } = await refusedLoad(
      language,
      '/api/photoreal/3dtiles/error.json',
    );
    expect({
      ...shown(view, refusal),
      fetched: fetcher.mock.calls.some(([url]) =>
        String(url).includes('/error.json'),
      ),
    }).toEqual({ ...untouched, fetched: true });
    expectMountMeter(view, language);
  },
);

async function openDeferred(language: 'en' | 'ar') {
  const deferred = deferredTiles(() => new Response(mountModes()), viewCreated);
  const opened = await openPhotoreal(language, deferred.fetcher);
  return { ...opened, pending: deferred.pending };
}

registerJournalOrderTests({ open: openDeferred, crossed, stillBelow });

it.each(['en', 'ar'] as const)(
  'a spend header on a satellite response never reaches the meter in %s',
  async (language) => {
    const { view, fetcher, refusal } = await refusedLoad(
      language,
      '/api/imagery/tiles/0/0/0',
    );
    expect({
      ...shown(view, refusal),
      imagery: fetcher.mock.calls.some(([url]) =>
        String(url).startsWith('/api/imagery/'),
      ),
    }).toEqual({ ...untouched, imagery: false });
    expectMountMeter(view, language);
  },
);
