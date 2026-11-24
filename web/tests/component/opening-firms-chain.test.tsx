// @vitest-environment jsdom
/**
 * S3-T10: the opening screen reads an invented, successful firms-per-tower
 * chain through its existing API client (`loadPublicLayer`, then
 * `loadRegistryInput`), offline, in English and Arabic. Each plant changes one
 * input of the fixture and asserts its own refusal reason.
 */
import {
  act,
  cleanup,
  fireEvent,
  render,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { loadPublicLayer } from '../../src/api/public-layer';
import { MountedPublicShell } from '../../src/app/MountedPublicShell';
import { createRegistry } from '../../src/facts/registry';
import { text } from '../../src/i18n';
import { digitInPlain, plainHoldsDigit } from '../../src/stage/layers/checks';
import type { LayerPayload } from '../../src/stage/layers/payload';
import { acceptPayload } from '../../src/stage/layers/refuse';
import { resetArea, releaseAreaClient } from '../../src/state/area-actions';
import {
  FC_ALEPH,
  FC_GIMEL,
  fcPayload,
  fcRegistry,
} from '../fixtures/fc-firms';
import { plain } from '../fixtures/layers';
import { numeralsOutsideChips } from '../fixtures/numerals';
import {
  chainFetch,
  firmsChain,
  type FirmsChain,
} from '../fixtures/opening-firms-chain';

// The real registry factory, counted, so a refusal before it is provable.
vi.mock('../../src/facts/registry', async (original) => {
  const actual = await original<typeof import('../../src/facts/registry')>();
  return { ...actual, createRegistry: vi.fn(actual.createRegistry) };
});
beforeEach(() => {
  vi.mocked(createRegistry).mockClear();
});

afterEach(() => {
  cleanup();
  resetArea();
  releaseAreaClient();
  vi.unstubAllGlobals();
  history.replaceState(null, '', '/');
});

const LANGUAGES = ['en', 'ar'] as const;
type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const payload = (chain: FirmsChain) => chain.layer.payload as Json;

/** The opening screen, its guided-story action, then the firms layer. */
async function openFirms(chain: FirmsChain, language: 'en' | 'ar') {
  history.replaceState(null, '', '/?lang=' + language);
  const seen: string[] = [];
  vi.stubGlobal('fetch', chainFetch(chain, seen));
  const view = render(
    <MountedPublicShell extractUrl="/tiles/basemap.pmtiles" />,
  );
  await act(async () => undefined);
  expect(view.container.querySelector('[data-scene="opening"]')).not.toBeNull();
  fireEvent.click(
    view.container.querySelector('[data-action="guided-story"]')!,
  );
  await act(async () =>
    fireEvent.change(view.container.querySelector('.layer-chooser select')!, {
      target: { value: 'fc_firms_per_tower' },
    }),
  );
  await waitFor(() =>
    expect(
      view.container.querySelector(
        '[data-part="public-layers"], [role="alert"]',
      ),
    ).not.toBeNull(),
  );
  return { view, seen };
}

for (const language of LANGUAGES)
  it(`reads the successful firms chain on the opening screen (${language})`, async () => {
    const chain = firmsChain();
    const { view, seen } = await openFirms(chain, language);
    expect(document.documentElement.lang).toBe(language);
    expect(view.queryByRole('alert')).toBeNull();
    expect(
      view.container.querySelector('[data-part="layer-refusal"]'),
    ).toBeNull();
    // Each fact resolved through its own lineage route; nothing left the origin.
    for (const fact of chain.layer.facts)
      expect(seen).toContain('/api/facts/' + fact.fact_id + '/lineage');
    expect(seen.every((path) => path.startsWith('/api/'))).toBe(true);
    const legend = view.container.querySelector(
      '[data-part="fc-firms-legend"]',
    );
    expect(
      [...(legend?.querySelectorAll('[data-fact-chip]') ?? [])].map((chip) =>
        chip.getAttribute('data-state'),
      ),
    ).toEqual(['ready', 'ready', 'ready', 'ready', 'ready']);
    expect(legend?.querySelector('[data-legend="name"]')?.textContent).toBe(
      text(language, 'layers.name.fc_firms_per_tower'),
    );
    fireEvent.click(view.getByRole('button', { name: 'Invented Tower Aleph' }));
    const panel = view.container.querySelector(
      '[data-part="fc-firms-tower-panel"]',
    );
    const count = panel?.querySelector(`[data-fact-id="${FC_ALEPH}"]`);
    expect(count?.getAttribute('data-fact-chip')).toBe('value');
    expect(count?.querySelector('.chip-num')?.textContent).toBe('4');
    expect(
      view.getByRole('button', { name: 'Invented House Aleph' }),
    ).toBeTruthy();
    expect(numeralsOutsideChips(view.container)).toEqual([]);
  });

/**
 * Plant 1: one chain link is missing. Each changes one input only and names
 * how often the registry factory runs before the refusal: a refusal of the
 * HTTP status, the lineage or the table comes before any registry.
 */
const MISSING_LINK: Record<string, [number, (chain: FirmsChain) => void]> = {
  'the lineage of one fact': [
    0,
    (chain) => {
      delete chain.lineages[FC_GIMEL];
    },
  ],
  // The body stays valid; only the HTTP status refuses it.
  'an OK status on the lineage of one fact': [
    0,
    (chain) => {
      chain.status['/api/facts/' + FC_GIMEL + '/lineage'] = 404;
    },
  ],
  'the table in the release': [
    0,
    (chain) => {
      chain.release.tables = [];
    },
  ],
  // Every fact shares one lineage, so the source row is removed from the chain.
  'the source of the lineage': [
    1,
    (chain) => {
      for (const row of Object.values(chain.lineages)) row!.sources = [];
    },
  ],
};

for (const [link, [registryCalls, plant]] of Object.entries(MISSING_LINK)) {
  it(`a chain missing ${link} is refused by the client with chain_refused`, async () => {
    const chain = firmsChain();
    plant(chain);
    vi.stubGlobal('fetch', chainFetch(chain));
    await expect(loadPublicLayer('fc_firms_per_tower')).rejects.toThrow(
      /^chain_refused$/,
    );
    expect(createRegistry).toHaveBeenCalledTimes(registryCalls);
  });
  for (const language of LANGUAGES)
    it(`a chain missing ${link} shows the unavailable alert and no firm (${language})`, async () => {
      const chain = firmsChain();
      plant(chain);
      const { view } = await openFirms(chain, language);
      expect(view.getByRole('alert').textContent).toBe(
        text(language, 'layers.unavailable'),
      );
      expect(
        view.container.querySelector('[data-part="fc-firms-legend"]'),
      ).toBeNull();
      expect(
        view.queryByRole('button', { name: 'Invented Tower Aleph' }),
      ).toBeNull();
    });
}

/** Plants 2 and 3: a value outside its closed type, and a numeral outside a chip. */
const REFUSED: Record<string, [string, (chain: FirmsChain) => void]> = {
  'a tower class outside the closed bands': [
    'night_class_missing',
    (chain) => {
      payload(chain).layers[0].features[0].class_id = 'band_extreme';
    },
  ],
  'a direction outside the closed directions': [
    'legend_count_unbound',
    (chain) => {
      payload(chain).fc_firms.direction = 'sideways';
    },
  ],
  'a numeral in a company field': [
    'numeral_in_plain_segment',
    (chain) => {
      payload(chain).fc_firms.companies[0].fields[0].text = 'Invented House 7';
    },
  ],
  'a numeral in a tower name': [
    'numeral_in_plain_segment',
    (chain) => {
      payload(chain).layers[0].features[0].words.name = 'Invented Tower 12';
    },
  ],
};

for (const [name, [reason, plant]] of Object.entries(REFUSED))
  for (const language of LANGUAGES)
    it(`${name} is refused with ${reason} (${language})`, async () => {
      const chain = firmsChain();
      plant(chain);
      const { view } = await openFirms(chain, language);
      expect(
        view.container
          .querySelector('[data-part="layer-refusal"]')
          ?.getAttribute('data-refusal'),
      ).toBe(reason);
      expect(
        view.container.querySelector('[data-part="fc-firms-legend"]'),
      ).toBeNull();
      expect(numeralsOutsideChips(view.container)).toEqual([]);
    });

/** Every decimal digit script, at each position and fused or split, is refused. */
const DIGITS = ['7', '٧', '۷', '७', '７', '๗'];
const PLACES = [
  (d: string) => d + ' Invented House',
  (d: string) => 'Invented ' + d + ' House',
  (d: string) => 'Invented House ' + d,
  (d: string) => 'Invented House' + d,
  (d: string) => d,
];
it('a numeral of any script and place in a company field is refused', async () => {
  for (const digit of DIGITS)
    for (const place of PLACES) {
      const chain = firmsChain();
      payload(chain).fc_firms.companies[0].fields[0].text = place(digit);
      const { view } = await openFirms(chain, 'en');
      expect(
        view.container
          .querySelector('[data-part="layer-refusal"]')
          ?.getAttribute('data-refusal'),
        place(digit),
      ).toBe('numeral_in_plain_segment');
      expect(numeralsOutsideChips(view.container)).toEqual([]);
      cleanup();
    }
});

/**
 * The whole decimal-digit domain. The oracle is every Unicode `Nd` code point,
 * scanned here from `\p{Nd}` into ranges and pinned by independent anchors.
 */
const ND = /\p{Nd}/u;
const ND_POINTS: number[] = [];
for (let point = 0; point <= 0x10ffff; point++)
  if (ND.test(String.fromCodePoint(point))) ND_POINTS.push(point);
const ND_SET = new Set(ND_POINTS);
const ND_RANGES = ND_POINTS.reduce<[number, number][]>((ranges, point) => {
  const last = ranges.at(-1);
  if (last && last[1] === point - 1) last[1] = point;
  else ranges.push([point, point]);
  return ranges;
}, []);
/** First digits of scripts, two of them beyond the Basic Multilingual Plane. */
const ND_ANCHORS = [
  0x30, 0x660, 0x6f0, 0x966, 0xe50, 0xff10, 0x104a0, 0x1d7ce, 0x1e950,
];

/** mulberry32: a small seeded generator, so every run draws the same cases. */
const SEED = 0x20261123;
function generator(seed: number) {
  let state = seed;
  return (bound: number) => {
    state = (state + 0x6d2b79f5) | 0;
    let mixed = Math.imul(state ^ (state >>> 15), 1 | state);
    mixed = (mixed + Math.imul(mixed ^ (mixed >>> 7), 61 | mixed)) ^ mixed;
    return (((mixed ^ (mixed >>> 14)) >>> 0) / 4294967296) * bound;
  };
}
/** Text without any Unicode number (`\p{N}`), lone surrogates included. */
function numberFree(draw: (bound: number) => number): string {
  let out = '';
  for (let left = Math.floor(draw(8)); left > 0;) {
    const char = String.fromCodePoint(Math.floor(draw(0x110000)));
    if (/\p{N}/u.test(char)) continue;
    out += draw(2) < 1 ? char : ' Invented';
    left--;
  }
  return out;
}
/** Number-free text with one digit drawn from every `Nd` code point. */
function withDigit(draw: (bound: number) => number): string {
  const digit = ND_POINTS[Math.floor(draw(ND_POINTS.length))]!;
  return numberFree(draw) + String.fromCodePoint(digit) + numberFree(draw);
}
const CASES = 400;

/** The refusal code of a payload on the layer guard, or null when accepted. */
function refusal(layer: LayerPayload): string | null {
  const accepted = acceptPayload(layer, fcRegistry());
  return accepted.ok ? null : accepted.code;
}
function fieldRefusal(field: object): string | null {
  const layer = fcPayload();
  (layer.fc_firms!.companies[0]!.fields as object[])[0] = field;
  return refusal(layer);
}

it('the Nd oracle holds every decimal-digit range, beyond the BMP too', () => {
  for (const anchor of ND_ANCHORS)
    expect(
      ND_RANGES.some(([low]) => low === anchor),
      anchor.toString(16),
    ).toBe(true);
  // Unicode encodes decimal digits in contiguous runs of ten.
  expect(ND_RANGES.every(([low, high]) => (high - low + 1) % 10 === 0)).toBe(
    true,
  );
  expect(ND_RANGES.some(([low]) => low > 0xffff)).toBe(true);
});

it('the digit guard matches the Nd oracle at every code point', () => {
  const wrong: string[] = [];
  for (let point = 0; point <= 0x10ffff; point++) {
    const char = String.fromCodePoint(point);
    const expected = ND_SET.has(point);
    if (
      plainHoldsDigit(char) !== expected ||
      digitInPlain([plain(char)]) !== expected
    )
      wrong.push(point.toString(16));
  }
  expect(wrong).toEqual([]);
});

it('every Nd digit, at each place, in a company field or tower name is refused with numeral_in_plain_segment', () => {
  const wrong: string[] = [];
  for (const point of ND_POINTS)
    for (const place of PLACES) {
      const words = place(String.fromCodePoint(point));
      const tower = fcPayload();
      tower.layers[0]!.features[0]!.words = { name: words };
      const codes = [
        fieldRefusal({ key: 'trade_name', text: words }),
        fieldRefusal({ key: 'trade_name', segments: [plain(words)] }),
        refusal(tower),
      ];
      if (codes.some((code) => code !== 'numeral_in_plain_segment'))
        wrong.push(point.toString(16) + ':' + codes.join());
    }
  expect(wrong).toEqual([]);
});

it(`generated text (seed ${SEED}, ${CASES} cases each) is refused only when it holds a digit`, () => {
  const draw = generator(SEED);
  const wrong: string[] = [];
  let beyondPlane = 0;
  for (let index = 0; index < CASES; index++) {
    const digit = withDigit(draw);
    const free = numberFree(draw);
    if ([...digit].some((char) => ND.test(char) && char.length === 2))
      beyondPlane++;
    if (
      fieldRefusal({ key: 'trade_name', text: digit }) !==
      'numeral_in_plain_segment'
    )
      wrong.push('digit:' + JSON.stringify(digit));
    if (
      fieldRefusal({
        key: 'trade_name',
        segments: [plain(free), plain(digit)],
      }) !== 'numeral_in_plain_segment'
    )
      wrong.push('segments:' + JSON.stringify(digit));
    if (fieldRefusal({ key: 'trade_name', text: free }) !== null)
      wrong.push('free:' + JSON.stringify(free));
  }
  // Empty and blank controls carry no digit and are not refused for one.
  for (const blank of ['', ' ', '\u00a0\u2003'])
    if (fieldRefusal({ key: 'trade_name', text: blank }) !== null)
      wrong.push('blank:' + JSON.stringify(blank));
  expect(wrong).toEqual([]);
  expect(beyondPlane).toBeGreaterThan(0);
});

it(`generated text on the opening screen (seed ${SEED}) is refused only when it holds a digit`, async () => {
  const draw = generator(SEED + 1);
  for (let index = 0; index < 8; index++) {
    const language = LANGUAGES[index % 2]!;
    const words = index < 6 ? withDigit(draw) : numberFree(draw);
    const chain = firmsChain();
    payload(chain).fc_firms.companies[0].fields[0].text = words;
    const { view } = await openFirms(chain, language);
    expect(
      view.container
        .querySelector('[data-part="layer-refusal"]')
        ?.getAttribute('data-refusal') ?? null,
      JSON.stringify(words),
    ).toBe(index < 6 ? 'numeral_in_plain_segment' : null);
    if (index >= 6) {
      // A digit-free control must be accepted on screen, not merely unrefused:
      // a failed load shows the unavailable alert and no refusal either.
      expect(view.queryByRole('alert'), JSON.stringify(words)).toBeNull();
      expect(
        view.container.querySelector('[data-part="fc-firms-legend"]'),
      ).not.toBeNull();
      expect(
        view.getByRole('button', { name: 'Invented Tower Aleph' }),
      ).toBeTruthy();
    }
    expect(numeralsOutsideChips(view.container)).toEqual([]);
    cleanup();
  }
});
