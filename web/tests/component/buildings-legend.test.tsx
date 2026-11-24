// @vitest-environment jsdom
/** Invented buildings SYN-B-*; the read is the route's own fixture body. */
import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { text, type Language } from '../../src/i18n';
import { BuildingsLegend } from '../../src/stage/BuildingsLegend';
import {
  readBuildingHeights,
  verifyBuildingWords,
  type BuildingHeightsRead,
  type BuildingRow,
  type ShadowSelection,
} from '../../src/stage/buildings3d';
import { heightsBody } from '../fixtures/building-heights';
import { numeralsOutsideChips } from '../fixtures/numerals';

afterEach(() => {
  cleanup();
});

function verified(): BuildingHeightsRead {
  const result = readBuildingHeights(heightsBody());
  if (!result.ok) throw new Error(result.reason);
  return result.read;
}

const BUILDING: BuildingRow = verified().buildings.find(
  (row) => row.height_source === 'floor_count',
)!;

function legend(
  language: Language,
  selection: ShadowSelection,
  picked?: BuildingRow,
) {
  return render(
    <BuildingsLegend
      language={language}
      heights={verified()}
      selection={selection}
      picked={picked}
      onOpenChain={() => undefined}
    />,
  );
}

const LIMITED: ShadowSelection = { casting: [BUILDING], limited: true };

describe('BuildingsLegend', () => {
  it.each(['en', 'ar'] as const)(
    'says in words, in %s, heights are estimates, shadows use estimated heights and are limited',
    (language) => {
      const view = legend(language, LIMITED);
      const root = view.container;
      expect(
        root.querySelector('[data-words="heights-estimates"]')?.textContent,
      ).toBe(text(language, 'buildings.estimates'));
      expect(
        root.querySelector('[data-words="shadow-estimated"]')?.textContent,
      ).toBe(text(language, 'buildings.shadowEstimated'));
      expect(
        root.querySelector('[data-words="shadow-limited"]')?.textContent,
      ).toBe(text(language, 'buildings.shadowLimited'));
      expect(
        root
          .querySelector('[data-part="buildings-legend"]')
          ?.getAttribute('dir'),
      ).toBe(language === 'ar' ? 'rtl' : 'ltr');
      expect(() => verifyBuildingWords(root, LIMITED)).not.toThrow();
    },
  );
  it('the English words name estimated heights', () => {
    expect(text('en', 'buildings.shadowEstimated')).toContain(
      'estimated heights',
    );
    expect(text('en', 'buildings.estimates')).toBe('Heights are estimates.');
  });
  it('omits the limit words under the cap and the shadow words with no shadow', () => {
    const view = legend('en', { casting: [], limited: false });
    expect(
      view.container.querySelector('[data-words="shadow-limited"]'),
    ).toBeNull();
    expect(
      view.container.querySelector('[data-words="shadow-estimated"]'),
    ).toBeNull();
  });
  it('puts every fallback error behind More evidence, as Fact chips, with no loose numeral', () => {
    const view = legend('en', LIMITED, BUILDING);
    const details = view.container.querySelector(
      'details[data-part="more-evidence"]',
    );
    expect(details).not.toBeNull();
    expect(details?.hasAttribute('open')).toBe(false);
    expect(details?.querySelector('summary')?.textContent).toBe(
      'More evidence',
    );
    const panel = details?.querySelector('[data-part="fallback-panel"]');
    expect(panel?.querySelectorAll('[data-fallback]')).toHaveLength(3);
    expect(panel?.querySelectorAll('[data-fact-chip="compact"]')).toHaveLength(
      8,
    );
    expect(
      panel?.querySelector(
        '[data-fallback="3dglobfp"] [data-reason="no_pairs"]',
      ),
    ).not.toBeNull();
    const evidence = details?.querySelector('[data-part="building-evidence"]');
    expect(
      evidence?.querySelector('[data-height-source="floor_count"]')
        ?.textContent,
    ).toBe(text('en', 'buildings.source.floor_count'));
    expect(
      evidence?.querySelectorAll('[data-fact-chip="compact"]'),
    ).toHaveLength(4);
    expect(numeralsOutsideChips(view.container)).toEqual([]);
    // No error value sits outside "More evidence".
    expect(
      [...view.container.querySelectorAll('[data-fact-chip]')].every((chip) =>
        details?.contains(chip),
      ),
    ).toBe(true);
  });
  it.each([
    ['en', 'buildings'],
    ['ar', 'مبانٍ'],
  ] as const)(
    'names the pair count in buildings, never people, in %s',
    (language, unit) => {
      const view = legend(language, LIMITED);
      const pairs = view.container.querySelector(
        '[data-fallback="floor_count"] dd [data-fact-chip="compact"]',
      );
      expect(pairs?.textContent).toContain(unit);
      expect(pairs?.textContent).not.toContain(text(language, 'unit.count'));
      expect(text(language, 'unit.buildings')).toBe(unit);
    },
  );
  it('plant: a numeral outside a Fact chip is found', () => {
    const view = legend('en', LIMITED);
    const loose = document.createElement('p');
    loose.textContent = 'error 4 m';
    view.container
      .querySelector('[data-part="fallback-panel"]')
      ?.appendChild(loose);
    expect(numeralsOutsideChips(view.container)).toEqual(['error 4 m']);
  });
  it('plant: a view over the cap that omits the words fails', () => {
    const view = legend('en', LIMITED);
    view.container.querySelector('[data-words="shadow-limited"]')?.remove();
    expect(() => verifyBuildingWords(view.container, LIMITED)).toThrow(
      'shadow_limit_words_missing',
    );
  });
  it('plant: a shadow layer without the "estimated heights" words fails', () => {
    const view = legend('en', LIMITED);
    view.container.querySelector('[data-words="shadow-estimated"]')?.remove();
    expect(() => verifyBuildingWords(view.container, LIMITED)).toThrow(
      'estimated_heights_words_missing',
    );
  });
  it('plant: a legend without "heights are estimates" fails', () => {
    const view = legend('en', LIMITED);
    view.container.querySelector('[data-words="heights-estimates"]')?.remove();
    expect(() => verifyBuildingWords(view.container, LIMITED)).toThrow(
      'heights_words_missing',
    );
  });
});
