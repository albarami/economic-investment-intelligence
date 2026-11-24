// @vitest-environment jsdom
/** S3-T16 boxes 8 and 16. Satellite credit stays collapsed; swipe plants fail. */
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import { pageCreditPlace } from '../credit-place/credit-place-scan.mjs';
import { text } from '../../src/i18n';
import { Stage } from '../../src/stage/Stage';
import { Swipe } from '../../src/stage/Swipe';
import {
  completeInput,
  factId,
  makeBinding,
  makeFact,
  makeLineage,
  makeSource,
  registryFrom,
} from '../fixtures/facts';

const CREDIT = 'SYN-credit';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

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
    remove: vi.fn(),
    mountOverlay: vi.fn(),
  };
}

function scenarioRegistry() {
  return registryFrom({
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
}

it('keeps the rendered satellite credit inside collapsed credits', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        open: { available: true, reason: null },
        satellite: { available: true, reason: null },
        photoreal: { available: false, reason: 'offline', meter: null },
      }),
    }),
  );
  const setMode = vi.fn(
    async (mode: string, credit: (value: string) => void) => {
      if (mode === 'satellite') credit(CREDIT);
    },
  );
  const view = render(
    <Stage
      language="en"
      theme="dark"
      extractUrl="/SYN-map.pmtiles"
      mapStarter={() => ({ ...drawingMembers(), setMode })}
    />,
  );
  await waitFor(() =>
    expect(
      view.getByRole('radio', { name: 'Satellite' }).hasAttribute('disabled'),
    ).toBe(false),
  );
  fireEvent.click(view.getByRole('radio', { name: 'Satellite' }));
  await waitFor(() =>
    expect(pageCreditPlace(view.container.innerHTML, CREDIT).inside).toBe(1),
  );
  const page = view.container.innerHTML;
  const place = pageCreditPlace(page, CREDIT);
  expect(place.outside).toBe(0);
  expect(place.inside).toBe(1);
  const credit = view.getByText(CREDIT);
  const details = credit.closest('details');
  expect(details).not.toBeNull();
  expect(details?.open).toBe(false);
  expect(credit.closest('[data-part="attribution"]')).not.toBeNull();
  const planted = pageCreditPlace(`${page}<p>${CREDIT}</p>`, CREDIT);
  expect(planted.outside).toBeGreaterThan(0);
});

function contentVisible(element: HTMLElement): boolean {
  let node: HTMLElement | null = element;
  while (node) {
    if (node.hidden) return false;
    const style = getComputedStyle(node);
    if (
      style.display === 'none' ||
      style.visibility === 'hidden' ||
      style.visibility === 'collapse'
    ) {
      return false;
    }
    node = node.parentElement;
  }
  return true;
}

function baselineHidden(root: ParentNode): boolean {
  const baseline = root.querySelector('[role="group"]');
  if (!(baseline instanceof HTMLElement)) return true;
  if (
    baseline.getAttribute('aria-label') !== text('en', 'comparison.baseline')
  ) {
    return true;
  }
  if (!contentVisible(baseline)) return true;
  const fact = baseline.querySelector('[data-fact-chip="value"]');
  if (!(fact instanceof HTMLElement)) return true;
  if ((fact.textContent ?? '').trim() === '') return true;
  return !contentVisible(fact);
}

function resetAbsent(root: ParentNode): boolean {
  const label = text('en', 'comparison.reset');
  return ![...root.querySelectorAll('button')].some(
    (button) => button.textContent === label,
  );
}

it('fails a planted hidden baseline and a planted comparison without reset', () => {
  const view = render(
    <Swipe
      language="en"
      comparison={{
        kind: 'scenario',
        baselineFactId: factId(0),
        changedFactId: factId(1),
      }}
      registry={scenarioRegistry()}
      onOpen={() => undefined}
    />,
  );
  expect(baselineHidden(view.container)).toBe(false);
  expect(resetAbsent(view.container)).toBe(false);
  fireEvent.click(view.getByRole('button', { name: 'Show changed scenario' }));
  expect(baselineHidden(view.container)).toBe(false);
  expect(view.container.querySelector('input[type="range"]')).toBeNull();
  fireEvent.click(view.getByRole('button', { name: 'Reset comparison' }));
  expect(baselineHidden(view.container)).toBe(false);
  expect(
    view
      .getByRole('button', { name: 'Show baseline' })
      .getAttribute('aria-pressed'),
  ).toBe('true');
  const hidden = view.container.cloneNode(true) as HTMLElement;
  const baseline = hidden.querySelector('[role="group"]');
  expect(baseline).not.toBeNull();
  if (baseline instanceof HTMLElement) baseline.hidden = true;
  expect(baselineHidden(hidden)).toBe(true);
  const noReset = view.container.cloneNode(true) as HTMLElement;
  const reset = [...noReset.querySelectorAll('button')].find(
    (button) => button.textContent === text('en', 'comparison.reset'),
  );
  reset?.remove();
  expect(resetAbsent(noReset)).toBe(true);
});
