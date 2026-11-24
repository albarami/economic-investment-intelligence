// @vitest-environment jsdom
/**
 * S3-T16 boxes 5 and 15: the swipe shows two scenario states from tested code
 * or two fixed imagery-history views, every numeral in a Fact chip, and the GIS
 * centre's source line while a history view is on. The history views are an
 * invented fixture: S2-T19's views are not on this base.
 */
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { HeightCredits } from '../../src/stage/HeightCredits';
import {
  Swipe,
  swipeStates,
  type HistoryComparison,
} from '../../src/stage/Swipe';
import type { Fact } from '../../src/facts/types';
import type { TextSegment } from '../../src/stage/layers/payload';
import {
  completeInput,
  factId,
  makeBinding,
  makeFact,
  makeLineage,
  makeSource,
  registryFrom,
} from '../fixtures/facts';

afterEach(cleanup);

const DIGIT = /\p{Nd}/u;

function scenarioRegistry(
  classes: readonly ('public' | 'user_input')[] = ['public', 'user_input'],
  second: Partial<Fact> = {},
) {
  return registryFrom({
    ...completeInput(),
    facts: [0, 1].map((index) =>
      makeBinding({
        fact: makeFact({
          fact_id: factId(index),
          value: index === 0 ? 48 : 52,
          geography: { kind: 'user_scenario', area_id: 'SYN-area' },
          input_classes: [...classes],
          ...(index === 1 ? second : {}),
        }),
      }),
    ),
    lineages: [makeLineage({ inputClasses: [...classes] })],
    sources: [makeSource({ kind: 'reviewed_config' })],
  });
}

const plain = (value: string): TextSegment[] => [
  { kind: 'plain', text: value },
];

function history(): HistoryComparison {
  return {
    kind: 'imagery-history',
    beforeViewId: 'SYN-view-a',
    afterViewId: 'SYN-view-b',
    views: [
      {
        viewId: 'SYN-view-a',
        capturedOn: '2019-03-01',
        image: '/imagery-history/SYN-view-a.webp',
      },
      {
        viewId: 'SYN-view-b',
        capturedOn: '2025-03-01',
        image: '/imagery-history/SYN-view-b.webp',
      },
    ],
    source: {
      attribution: plain('Source: SYN publisher, SYN imagery service.'),
      retrievalDate: '2026-11-15',
      recordId: 'SYN-rec-gis',
    },
  };
}

/** Planted-violation detector: a numeral in a text node outside a chip. */
function numeralOutsideChip(root: HTMLElement): boolean {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (!DIGIT.test(node.textContent ?? '')) continue;
    if (!node.parentElement?.closest('[data-fact-chip]')) return true;
  }
  return false;
}

function gisLineAbsent(root: HTMLElement): boolean {
  const line = root.querySelector('[data-credit="gis_imagery_history"]');
  return !line || !(line.textContent ?? '').startsWith('Source: SYN publisher');
}

describe('imagery-history swipe', () => {
  it('shows two fixed views with the GIS source line and no loose numeral', () => {
    const view = render(
      <Swipe
        language="en"
        comparison={history()}
        registry={scenarioRegistry()}
        onOpen={() => undefined}
      />,
    );
    expect(view.getByRole('group', { name: 'Earlier view' })).toBeTruthy();
    expect(view.getByRole('group', { name: 'Later view' })).toBeTruthy();
    expect(gisLineAbsent(view.container)).toBe(false);
    expect(numeralOutsideChip(view.container)).toBe(false);
    const images = [...view.container.querySelectorAll('img')].map((img) => [
      img.getAttribute('data-history-image'),
      img.getAttribute('src'),
      img.getAttribute('alt'),
    ]);
    expect(images).toEqual([
      ['SYN-view-a', '/imagery-history/SYN-view-a.webp', 'Earlier view'],
      ['SYN-view-b', '/imagery-history/SYN-view-b.webp', 'Later view'],
    ]);
    for (const name of ['Earlier view', 'Later view']) {
      const group = view.getByRole('group', { name });
      expect(group.querySelector('img')).toBeTruthy();
      expect(group.querySelector('[data-fact-chip]')).toBeTruthy();
    }
    fireEvent.click(view.getByRole('button', { name: 'Show later view' }));
    expect(
      view
        .getByRole('button', { name: 'Show later view' })
        .getAttribute('aria-pressed'),
    ).toBe('true');
    fireEvent.click(view.getByRole('button', { name: 'Reset comparison' }));
    expect(
      view
        .getByRole('button', { name: 'Show earlier view' })
        .getAttribute('aria-pressed'),
    ).toBe('true');
  });

  it('renders in Arabic right to left with no loose numeral', () => {
    const view = render(
      <Swipe
        language="ar"
        comparison={history()}
        registry={scenarioRegistry()}
        onOpen={() => undefined}
      />,
    );
    const section = view.container.querySelector('section');
    expect(section?.getAttribute('dir')).toBe('rtl');
    expect(numeralOutsideChip(view.container)).toBe(false);
  });

  it('fails a planted numeral outside a chip', () => {
    const view = render(
      <Swipe
        language="en"
        comparison={history()}
        registry={scenarioRegistry()}
        onOpen={() => undefined}
      />,
    );
    const planted = view.container.cloneNode(true) as HTMLElement;
    planted.querySelector('p')?.append(document.createTextNode(' 7'));
    expect(numeralOutsideChip(planted)).toBe(true);
  });

  it('fails a planted view without the GIS source line', () => {
    const view = render(
      <Swipe
        language="en"
        comparison={history()}
        registry={scenarioRegistry()}
        onOpen={() => undefined}
      />,
    );
    const planted = view.container.cloneNode(true) as HTMLElement;
    planted.querySelector('[data-credit="gis_imagery_history"]')?.remove();
    expect(gisLineAbsent(planted)).toBe(true);
  });

  it('draws nothing when the GIS source line is refused', () => {
    const changed = history();
    changed.source = { ...changed.source, attribution: [] };
    const view = render(
      <Swipe
        language="en"
        comparison={changed}
        registry={scenarioRegistry()}
        onOpen={() => undefined}
      />,
    );
    expect(view.container.querySelector('section')).toBeNull();
  });
});

describe('swipe states come only from tested code', () => {
  it('accepts the scenario pair and the fixed history pair', () => {
    const registry = scenarioRegistry();
    expect(
      swipeStates(
        {
          kind: 'scenario',
          baselineFactId: factId(0),
          changedFactId: factId(1),
        },
        registry,
      ).kind,
    ).toBe('scenario');
    expect(swipeStates(history(), registry).kind).toBe('imagery-history');
  });

  const pair = {
    kind: 'scenario',
    baselineFactId: factId(0),
    changedFactId: factId(1),
  } as const;

  it('refuses a ready scenario state that is not a user input', () => {
    const registry = scenarioRegistry(['public']);
    const resolved = registry.resolve(factId(1));
    expect(resolved.status).toBe('ready');
    if (resolved.status !== 'ready') return;
    expect(resolved.display).toBe('value');
    expect(resolved.binding.fact.geography.kind).toBe('user_scenario');
    expect(swipeStates(pair, registry)).toEqual({
      kind: 'refused',
      reason: 'scenario_state_untested',
    });
  });

  it('refuses a scenario state that does not resolve', () => {
    expect(
      swipeStates(
        { ...pair, changedFactId: 'SYN-fact-absent' },
        scenarioRegistry(),
      ),
    ).toEqual({ kind: 'refused', reason: 'scenario_state_untested' });
  });

  it('refuses a ready scenario state whose value is withheld', () => {
    const registry = scenarioRegistry(undefined, { provenance: 'suppressed' });
    const resolved = registry.resolve(factId(1));
    expect(resolved.status === 'ready' && resolved.display).toBe('withheld');
    expect(swipeStates(pair, registry)).toEqual({
      kind: 'refused',
      reason: 'scenario_state_untested',
    });
  });

  it('refuses a ready scenario state outside the user scenario geography', () => {
    const registry = scenarioRegistry(undefined, {
      geography: { kind: 'national' },
    });
    const resolved = registry.resolve(factId(1));
    expect(resolved.status === 'ready' && resolved.display).toBe('value');
    expect(swipeStates(pair, registry)).toEqual({
      kind: 'refused',
      reason: 'scenario_state_untested',
    });
  });

  it('refuses one scenario state shown twice', () => {
    expect(
      swipeStates(
        {
          kind: 'scenario',
          baselineFactId: factId(0),
          changedFactId: factId(0),
        },
        scenarioRegistry(),
      ),
    ).toEqual({ kind: 'refused', reason: 'swipe_states_same' });
  });

  it('refuses a history view outside the fixed list', () => {
    expect(
      swipeStates(
        { ...history(), afterViewId: 'SYN-view-z' },
        scenarioRegistry(),
      ),
    ).toEqual({ kind: 'refused', reason: 'history_view_unknown' });
  });

  it('refuses one history view shown twice', () => {
    expect(
      swipeStates(
        { ...history(), afterViewId: 'SYN-view-a' },
        scenarioRegistry(),
      ),
    ).toEqual({ kind: 'refused', reason: 'swipe_states_same' });
  });

  it('refuses a history view with a malformed capture date', () => {
    const changed = history();
    changed.views = [
      changed.views[0],
      { viewId: 'SYN-view-b', capturedOn: 'spring' },
    ];
    expect(swipeStates(changed, scenarioRegistry())).toEqual({
      kind: 'refused',
      reason: 'history_view_date_invalid',
    });
  });

  it('refuses an impossible capture date that the pattern alone accepts', () => {
    const changed = history();
    changed.views = [
      changed.views[0],
      { ...changed.views[1], capturedOn: '2025-02-29' },
    ];
    expect(swipeStates(changed, scenarioRegistry())).toEqual({
      kind: 'refused',
      reason: 'history_view_date_invalid',
    });
  });

  it('accepts a valid leap-day capture date', () => {
    const changed = history();
    changed.views = [
      changed.views[0],
      { ...changed.views[1], capturedOn: '2024-02-29' },
    ];
    expect(swipeStates(changed, scenarioRegistry()).kind).toBe(
      'imagery-history',
    );
  });

  it.each([
    ['a remote address', 'https://imagery.invalid/SYN-view-b.webp'],
    ['a protocol-relative address', '//imagery.invalid/SYN-view-b.webp'],
    ['a parent-folder step', '/imagery-history/../SYN-view-b.webp'],
    ['a relative path', 'imagery-history/SYN-view-b.webp'],
    ['a non-picture file', '/imagery-history/SYN-view-b.svg'],
    ['an empty reference', ''],
  ])('refuses a history view image with %s', (_name, image) => {
    const changed = history();
    changed.views = [changed.views[0], { ...changed.views[1], image }];
    expect(swipeStates(changed, scenarioRegistry())).toEqual({
      kind: 'refused',
      reason: 'history_view_image_invalid',
    });
  });

  it('refuses two history views that show the same picture', () => {
    const changed = history();
    changed.views = [
      changed.views[0],
      { ...changed.views[1], image: changed.views[0].image },
    ];
    expect(swipeStates(changed, scenarioRegistry())).toEqual({
      kind: 'refused',
      reason: 'swipe_states_same',
    });
  });

  it('refuses a history pair whose GIS source line is refused', () => {
    const changed = history();
    changed.source = { ...changed.source, retrievalDate: 'later' };
    expect(swipeStates(changed, scenarioRegistry())).toEqual({
      kind: 'refused',
      reason: 'gis_retrieval_date_invalid',
    });
  });
});

describe('height credits on the map', () => {
  function creditMissing(root: HTMLElement, sourceId: string, words: string) {
    const line = root.querySelector(`[data-credit="${sourceId}"]`);
    return !line || !(line.textContent ?? '').includes(words);
  }

  it('shows both credits while fallback heights are drawn, chips holding numerals', () => {
    const view = render(
      <HeightCredits
        language="en"
        drawn={['bldg_3dglobfp', 'bldg_wsf3d']}
        inputs={{
          bldg_3dglobfp: { retrievalDate: '2026-11-15', recordId: 'SYN-g' },
          bldg_wsf3d: {
            retrievalDate: '2026-11-15',
            recordId: 'SYN-w',
            productionYear: '2023',
            landingPage: 'https://wsf3d-landing.invalid/',
          },
        }}
      />,
    );
    expect(
      creditMissing(view.container, 'bldg_3dglobfp', 'Che et al. 2024'),
    ).toBe(false);
    expect(
      creditMissing(
        view.container,
        'bldg_wsf3d',
        'WSF 3D, German Aerospace Center (DLR), CC BY 4.0',
      ),
    ).toBe(false);
    expect(numeralOutsideChip(view.container)).toBe(false);
    const links = view.getAllByRole('link', { name: 'Landing page' });
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      'https://wsf3d-landing.invalid/',
    ]);
    expect(links[0].closest('[data-credit="bldg_wsf3d"]')).toBeTruthy();
    const noGlobfp = view.container.cloneNode(true) as HTMLElement;
    noGlobfp.querySelector('[data-credit="bldg_3dglobfp"]')?.remove();
    expect(creditMissing(noGlobfp, 'bldg_3dglobfp', 'Che et al. 2024')).toBe(
      true,
    );
    const noWsf = view.container.cloneNode(true) as HTMLElement;
    noWsf.querySelector('[data-credit="bldg_wsf3d"]')?.remove();
    expect(
      creditMissing(
        noWsf,
        'bldg_wsf3d',
        'WSF 3D, German Aerospace Center (DLR), CC BY 4.0',
      ),
    ).toBe(true);
  });

  it('names the refusal when a drawn fallback has no credit input', () => {
    const view = render(
      <HeightCredits language="en" drawn={['bldg_wsf3d']} inputs={{}} />,
    );
    expect(
      view.container
        .querySelector('[data-height-credit-refused]')
        ?.getAttribute('data-height-credit-refused'),
    ).toBe('wsf3d_credit_absent');
  });
});
