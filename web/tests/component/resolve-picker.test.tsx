// @vitest-environment jsdom
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ResolvePicker } from '../../src/journeys/ResolvePicker';
import { PublicStory } from '../../src/journeys/PublicStory';
import {
  activePort,
  registerPort,
  releasePort,
} from '../../src/state/area-actions';
import { plainPort } from '../fixtures/plain-port';

const MODES_PATH = '/api/map-modes';
const SEARCH_PATH = '/api/address-search';
const RESOLVE_PATH = '/api/tools/resolve';

const KEYED_MODES = {
  open: { available: true, reason: null },
  satellite: { available: true, reason: null },
  photoreal: { available: false, reason: 'no_key', meter: null },
};

function modesWith(satellite: { available: boolean; reason: string | null }) {
  return {
    open: { available: true, reason: null },
    satellite,
    photoreal: { available: false, reason: 'no_key', meter: null },
  };
}

const ADDRESS_RESULTS = {
  results: [
    { label: 'INVENTED-lane', point: { longitude: 1.5, latitude: 2.5 } },
  ],
};

const RESOLVE_ENVELOPE = {
  tool: 'resolve',
  status: 'OK',
  call_id: 'INVENTED-call',
  engine: 'embedded',
  release_id: 'INVENTED-release',
  blocks: [],
  facts: [],
  caveat_keys: [],
  payload: {
    candidates: [
      {
        kind: 'place',
        key: 'INVENTED-place',
        label_en: 'INVENTED Garden',
        label_ar: 'حديقة مخترعة',
        source: 'gazetteer',
        match: 'exact',
      },
    ],
  },
};

const STORY_RESOLVE_ENVELOPE = {
  tool: 'resolve',
  status: 'OK',
  call_id: 'INVENTED-call',
  engine: 'embedded',
  release_id: 'INVENTED-release',
  blocks: [],
  facts: [],
  caveat_keys: [],
  payload: {
    candidates: [
      {
        kind: 'place',
        key: 'INVENTED-place',
        label_en: 'INVENTED Garden',
        label_ar: 'حديقة مخترعة',
        source: 'gazetteer',
        match: 'exact',
      },
      {
        kind: 'activity',
        key: 'INVENTED-activity',
        label_en: 'INVENTED Craft',
        label_ar: 'حرفة مخترعة',
        source: 'activity_spine',
        match: 'exact',
        commerce_code: 'INVENTED-commerce',
        isic_class: 'INVENTED-class',
        place_category: 'INVENTED-category',
        not_mappable: false,
      },
    ],
  },
};

interface SeenCall {
  url: string;
  body: string | null;
}

function stubTransport(
  seen: SeenCall[],
  routes: Record<string, { status: number; body: unknown }>,
  planted: string[] = [],
) {
  vi.stubGlobal('fetch', async (url: string, init?: { body?: string }) => {
    seen.push({ url, body: typeof init?.body === 'string' ? init.body : null });
    if (planted.includes(url)) throw new Error(`planted call ${url}`);
    const route = routes[url];
    if (!route) {
      return {
        ok: false,
        status: 404,
        json: async () => ({ error: { code: 'NOT_FOUND' } }),
      };
    }
    return {
      ok: route.status >= 200 && route.status < 300,
      status: route.status,
      json: async () => route.body,
    };
  });
}

let portToken = 0;

afterEach(() => {
  cleanup();
  releasePort(portToken);
  portToken = 0;
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function mount(kind: 'place' | 'activity' = 'place') {
  return render(
    <ResolvePicker language="en" kind={kind} onSelect={() => undefined} />,
  );
}

function submit(view: ReturnType<typeof mount>, query: string) {
  const form = view.container.querySelector('form.resolve-picker')!;
  fireEvent.change(view.container.querySelector('input')!, {
    target: { value: query },
  });
  fireEvent.submit(form);
}

describe('the keyed place picker', () => {
  it('posts the text to the local search, shows the label and flies to it', async () => {
    const seen: SeenCall[] = [];
    stubTransport(seen, {
      [MODES_PATH]: { status: 200, body: KEYED_MODES },
      [SEARCH_PATH]: { status: 200, body: ADDRESS_RESULTS },
      [RESOLVE_PATH]: { status: 200, body: RESOLVE_ENVELOPE },
    });
    const focusPoint = vi.fn();
    portToken = registerPort({ ...plainPort(320, 320), focusPoint });
    const view = mount();
    await act(async () => undefined);
    submit(view, 'INVENTED-lane');
    await act(async () => undefined);
    const searchCalls = seen.filter((call) => call.url === SEARCH_PATH);
    expect(searchCalls.length).toBe(1);
    expect(searchCalls[0]!.body).toBe('{"text":"INVENTED-lane","lang":"en"}');
    expect(seen.some((call) => call.url === RESOLVE_PATH)).toBe(true);
    const chip = view.container.querySelector(
      '[data-part="address-result"] [data-fact-chip="reference"]',
    );
    expect(chip?.textContent).toBe('INVENTED-lane');
    expect(focusPoint).toHaveBeenCalledWith({ longitude: 1.5, latitude: 2.5 });
    expect(activePort()).not.toBeNull();
  });

  it('falls back to the gazetteer when the server reports no key', async () => {
    const seen: SeenCall[] = [];
    stubTransport(seen, {
      [MODES_PATH]: { status: 200, body: KEYED_MODES },
      [SEARCH_PATH]: { status: 404, body: { error: { code: 'NOT_FOUND' } } },
      [RESOLVE_PATH]: { status: 200, body: RESOLVE_ENVELOPE },
    });
    const view = mount();
    await act(async () => undefined);
    submit(view, 'INVENTED Garden');
    await act(async () => undefined);
    expect(seen.some((call) => call.url === SEARCH_PATH)).toBe(true);
    expect(seen.some((call) => call.url === RESOLVE_PATH)).toBe(true);
    expect(
      view.container.querySelector('[data-candidate="INVENTED-place"]'),
    ).not.toBeNull();
    expect(
      view.container.querySelector('[data-part="address-result"]'),
    ).toBeNull();
  });

  it('asks the modes on every submit and stops searching once offline', async () => {
    const seen: SeenCall[] = [];
    const routes: Record<string, { status: number; body: unknown }> = {
      [MODES_PATH]: { status: 200, body: KEYED_MODES },
      [SEARCH_PATH]: { status: 200, body: ADDRESS_RESULTS },
      [RESOLVE_PATH]: { status: 200, body: RESOLVE_ENVELOPE },
    };
    stubTransport(seen, routes);
    const view = mount();
    await act(async () => undefined);
    submit(view, 'INVENTED-lane');
    await act(async () => undefined);
    expect(seen.filter((call) => call.url === SEARCH_PATH).length).toBe(1);
    expect(
      view.container.querySelector('[data-part="address-result"]'),
    ).not.toBeNull();
    routes[MODES_PATH] = {
      status: 200,
      body: modesWith({ available: false, reason: 'offline' }),
    };
    submit(view, 'INVENTED-lane');
    await act(async () => undefined);
    expect(seen.filter((call) => call.url === SEARCH_PATH).length).toBe(1);
    expect(view.getByText('Search the offline place list')).toBeTruthy();
  });
});

describe.each([
  ['no_key', modesWith({ available: false, reason: 'no_key' })],
  ['offline', modesWith({ available: false, reason: 'offline' })],
])('the unkeyed place picker (%s)', (_name, modes) => {
  it('makes no search attempt; a planted transport call would go red', async () => {
    const seen: SeenCall[] = [];
    stubTransport(
      seen,
      {
        [MODES_PATH]: { status: 200, body: modes },
        [RESOLVE_PATH]: { status: 200, body: RESOLVE_ENVELOPE },
      },
      [SEARCH_PATH],
    );
    const focusPoint = vi.fn();
    portToken = registerPort({ ...plainPort(320, 320), focusPoint });
    const view = mount();
    await act(async () => undefined);
    submit(view, 'INVENTED Garden');
    await act(async () => undefined);
    expect(seen.filter((call) => call.url === SEARCH_PATH)).toEqual([]);
    expect(seen.some((call) => call.url === RESOLVE_PATH)).toBe(true);
    expect(
      view.container.querySelector('[data-candidate="INVENTED-place"]'),
    ).not.toBeNull();
    expect(
      view.container.querySelector('[data-part="address-result"]'),
    ).toBeNull();
    expect(focusPoint).not.toHaveBeenCalled();
    expect(view.getByText('Search the offline place list')).toBeTruthy();
  });
});

describe('the place picker', () => {
  it('stores nothing of the result in web storage, the URL or history', async () => {
    const writes: string[] = [];
    const pushState = vi.spyOn(history, 'pushState');
    const replaceState = vi.spyOn(history, 'replaceState');
    const storage = {
      setItem(key: string) {
        writes.push(`set:${key}`);
      },
      getItem() {
        return null;
      },
      removeItem(key: string) {
        writes.push(`remove:${key}`);
      },
      clear() {
        writes.push('clear');
      },
    };
    vi.stubGlobal('localStorage', storage);
    vi.stubGlobal('sessionStorage', storage);
    const seen: SeenCall[] = [];
    stubTransport(seen, {
      [MODES_PATH]: { status: 200, body: KEYED_MODES },
      [SEARCH_PATH]: { status: 200, body: ADDRESS_RESULTS },
      [RESOLVE_PATH]: { status: 200, body: RESOLVE_ENVELOPE },
    });
    const view = mount();
    await act(async () => undefined);
    submit(view, 'INVENTED-lane');
    await act(async () => undefined);
    expect(
      view.container.querySelector('[data-part="address-result"]'),
    ).not.toBeNull();
    expect(writes).toEqual([]);
    expect(pushState).not.toHaveBeenCalled();
    expect(replaceState).not.toHaveBeenCalled();
    expect(window.location.search).toBe('');
    expect(window.location.hash).toBe('');
  });

  it('clears the shown result when the query changes', async () => {
    const seen: SeenCall[] = [];
    stubTransport(seen, {
      [MODES_PATH]: { status: 200, body: KEYED_MODES },
      [SEARCH_PATH]: { status: 200, body: ADDRESS_RESULTS },
      [RESOLVE_PATH]: { status: 200, body: RESOLVE_ENVELOPE },
    });
    const view = mount();
    await act(async () => undefined);
    submit(view, 'INVENTED-lane');
    await act(async () => undefined);
    expect(
      view.container.querySelector('[data-part="address-result"]'),
    ).not.toBeNull();
    fireEvent.change(view.container.querySelector('input')!, {
      target: { value: 'INVENTED-other' },
    });
    expect(
      view.container.querySelector('[data-part="address-result"]'),
    ).toBeNull();
  });

  it('clears the address result when a gazetteer candidate is chosen', async () => {
    const seen: SeenCall[] = [];
    stubTransport(seen, {
      [MODES_PATH]: { status: 200, body: KEYED_MODES },
      [SEARCH_PATH]: { status: 200, body: ADDRESS_RESULTS },
      [RESOLVE_PATH]: { status: 200, body: RESOLVE_ENVELOPE },
    });
    const view = mount();
    await act(async () => undefined);
    submit(view, 'INVENTED-lane');
    await act(async () => undefined);
    expect(
      view.container.querySelector('[data-part="address-result"]'),
    ).not.toBeNull();
    fireEvent.click(
      view.container.querySelector('[data-candidate="INVENTED-place"]')!,
    );
    expect(
      view.container.querySelector('[data-part="address-result"]'),
    ).toBeNull();
  });

  it('drops an address response that lands after a gazetteer choice', async () => {
    const seen: SeenCall[] = [];
    let releaseSearch: (() => void) | null = null;
    const heldBody = new Promise((resolve) => {
      releaseSearch = () => resolve(ADDRESS_RESULTS);
    });
    stubTransport(seen, {
      [MODES_PATH]: { status: 200, body: KEYED_MODES },
      [SEARCH_PATH]: { status: 200, body: heldBody },
      [RESOLVE_PATH]: { status: 200, body: RESOLVE_ENVELOPE },
    });
    const focusPoint = vi.fn();
    portToken = registerPort({ ...plainPort(320, 320), focusPoint });
    const view = mount();
    await act(async () => undefined);
    submit(view, 'INVENTED-lane');
    await act(async () => undefined);
    const candidate = view.container.querySelector(
      '[data-candidate="INVENTED-place"]',
    );
    expect(candidate).not.toBeNull();
    expect(seen.some((call) => call.url === SEARCH_PATH)).toBe(true);
    fireEvent.click(candidate!);
    releaseSearch!();
    await act(async () => undefined);
    expect(focusPoint).not.toHaveBeenCalled();
    expect(
      view.container.querySelector('[data-part="address-result"]'),
    ).toBeNull();
  });
});

describe('the activity picker', () => {
  it('never probes the modes or the address search', async () => {
    const seen: SeenCall[] = [];
    stubTransport(
      seen,
      {
        [RESOLVE_PATH]: { status: 200, body: RESOLVE_ENVELOPE },
      },
      [SEARCH_PATH],
    );
    const view = mount('activity');
    await act(async () => undefined);
    submit(view, 'INVENTED craft');
    await act(async () => undefined);
    expect(seen.filter((call) => call.url === MODES_PATH)).toEqual([]);
    expect(seen.filter((call) => call.url === SEARCH_PATH)).toEqual([]);
    expect(seen.some((call) => call.url === RESOLVE_PATH)).toBe(true);
  });
});

function mountStory() {
  return render(
    <PublicStory
      language="en"
      registry={null}
      cards={[]}
      pending={false}
      failed={false}
      onRun={() => undefined}
      onOpen={() => undefined}
      onReset={() => undefined}
    />,
  );
}

function closeStoryPanel(details: Element) {
  act(() => {
    (details as HTMLDetailsElement).open = false;
    details.dispatchEvent(new Event('toggle'));
  });
}

describe('the story panel', () => {
  it('drops an address response that lands after the panel closed', async () => {
    const seen: SeenCall[] = [];
    let releaseSearch: (() => void) | null = null;
    const heldBody = new Promise((resolve) => {
      releaseSearch = () => resolve(ADDRESS_RESULTS);
    });
    stubTransport(seen, {
      [MODES_PATH]: { status: 200, body: KEYED_MODES },
      [SEARCH_PATH]: { status: 200, body: heldBody },
      [RESOLVE_PATH]: { status: 200, body: STORY_RESOLVE_ENVELOPE },
    });
    const focusPoint = vi.fn();
    portToken = registerPort({ ...plainPort(320, 320), focusPoint });
    const view = mountStory();
    await act(async () => undefined);
    const details = view.container.querySelector('details.story-selection')!;
    const placeForm = details.querySelector('form[data-picker="place"]')!;
    fireEvent.change(placeForm.querySelector('input')!, {
      target: { value: 'INVENTED-lane' },
    });
    fireEvent.submit(placeForm);
    await act(async () => undefined);
    expect(seen.some((call) => call.url === SEARCH_PATH)).toBe(true);
    closeStoryPanel(details);
    releaseSearch!();
    await act(async () => undefined);
    expect(focusPoint).not.toHaveBeenCalled();
    expect(
      view.container.querySelector('[data-part="address-result"]'),
    ).toBeNull();
  });

  it('closing the panel drops the chip but keeps the lifted selections', async () => {
    const seen: SeenCall[] = [];
    stubTransport(seen, {
      [MODES_PATH]: { status: 200, body: KEYED_MODES },
      [SEARCH_PATH]: { status: 200, body: ADDRESS_RESULTS },
      [RESOLVE_PATH]: { status: 200, body: STORY_RESOLVE_ENVELOPE },
    });
    const focusPoint = vi.fn();
    portToken = registerPort({ ...plainPort(320, 320), focusPoint });
    const view = mountStory();
    await act(async () => undefined);
    const details = view.container.querySelector('details.story-selection')!;
    const placeForm = details.querySelector('form[data-picker="place"]')!;
    const activityForm = details.querySelector('form[data-picker="activity"]')!;
    fireEvent.change(placeForm.querySelector('input')!, {
      target: { value: 'INVENTED Garden' },
    });
    fireEvent.submit(placeForm);
    await act(async () => undefined);
    fireEvent.click(
      placeForm.querySelector('[data-candidate="INVENTED-place"]')!,
    );
    await act(async () => undefined);
    expect(
      view.container.querySelector('[data-part="place-selected"]')?.textContent,
    ).toContain('INVENTED Garden');
    expect(
      view.container.querySelector('[data-part="named-presets"]'),
    ).not.toBeNull();
    fireEvent.change(placeForm.querySelector('input')!, {
      target: { value: 'INVENTED-lane' },
    });
    fireEvent.submit(placeForm);
    await act(async () => undefined);
    expect(
      view.container.querySelector('[data-part="address-result"]'),
    ).not.toBeNull();
    fireEvent.change(activityForm.querySelector('input')!, {
      target: { value: 'INVENTED craft' },
    });
    fireEvent.submit(activityForm);
    await act(async () => undefined);
    fireEvent.click(
      activityForm.querySelector('[data-candidate="INVENTED-activity"]')!,
    );
    await act(async () => undefined);
    expect(
      view.container.querySelector('[data-part="activity-selected"]')
        ?.textContent,
    ).toContain('INVENTED Craft');
    fireEvent.change(activityForm.querySelector('input')!, {
      target: { value: 'INVENTED draft' },
    });
    closeStoryPanel(details);
    await act(async () => undefined);
    expect((details as HTMLDetailsElement).open).toBe(false);
    expect(
      view.container.querySelector('[data-part="address-result"]'),
    ).toBeNull();
    expect(
      view.container.querySelector('[data-part="place-selected"]')?.textContent,
    ).toContain('INVENTED Garden');
    expect(
      view.container.querySelector('[data-part="activity-selected"]')
        ?.textContent,
    ).toContain('INVENTED Craft');
    expect(
      (activityForm.querySelector('input') as HTMLInputElement).value,
    ).toBe('INVENTED draft');
    expect(
      view.container.querySelector('[data-part="named-presets"]'),
    ).not.toBeNull();
  });
});
