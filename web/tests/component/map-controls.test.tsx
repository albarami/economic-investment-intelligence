// @vitest-environment jsdom
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { MapModeSwitch } from '../../src/stage/MapModeSwitch';
import { parseModes, selectedMode } from '../../src/stage/map-modes';
import { MapCredits } from '../../src/stage/Stage';
import { Swipe } from '../../src/stage/Swipe';
import {
  completeInput,
  factId,
  registryFrom,
  makeBinding,
  makeFact,
  makeSource,
  makeLineage,
} from '../fixtures/facts';

afterEach(cleanup);
const modes = {
  open: { available: true, reason: null },
  satellite: { available: false, reason: 'no_key' },
  photoreal: { available: false, reason: 'cap_reached', meter: null },
} as const;

it('keeps open selected and hides satellite without its key', () => {
  const change = vi.fn();
  const view = render(
    <MapModeSwitch
      language="en"
      modes={modes}
      selected="open"
      onChange={change}
    />,
  );
  expect(view.queryByRole('radio', { name: 'Satellite' })).toBeNull();
  const open = view.getByRole('radio', { name: 'Open map' });
  expect(open.getAttribute('aria-checked')).toBe('true');
  const photo = view.getByRole('radio', {
    name: /Photorealistic/,
  }) as HTMLButtonElement;
  expect(photo.disabled).toBe(true);
  fireEvent.click(photo);
  expect(change).not.toHaveBeenCalled();
  expect(selectedMode('photoreal', modes)).toBe('open');
});

it('shows offline reasons and local-language semantic controls', () => {
  const available = {
    ...modes,
    satellite: { available: false, reason: 'offline' },
  } as const;
  const view = render(
    <MapModeSwitch
      language="ar"
      modes={available}
      selected="open"
      onChange={() => undefined}
    />,
  );
  expect(view.getByRole('radiogroup').getAttribute('dir')).toBe('rtl');
  expect(view.getAllByRole('radio')).toHaveLength(3);
  expect(view.container.textContent).toContain('غير متصل');
});

it('refuses unknown fields, reasons and contradictions in availability', () => {
  expect(parseModes(modes)).toEqual(modes);
  expect(parseModes({ ...modes, extra: true })).toBeNull();
  expect(
    parseModes({
      ...modes,
      satellite: { available: false, reason: 'invented' },
    }),
  ).toBeNull();
  expect(
    parseModes({ ...modes, open: { available: false, reason: 'offline' } }),
  ).toBeNull();
  expect(
    parseModes({ ...modes, satellite: { available: true, reason: 'no_key' } }),
  ).toBeNull();
});

it('keeps runtime satellite credit inside collapsed credits only in satellite', () => {
  const view = render(
    <MapCredits language="en" mode="satellite" credit="SYN-credit" />,
  );
  const credit = view.getByText('SYN-credit');
  const details = credit.closest('details');
  expect(details).not.toBeNull();
  expect(details?.open).toBe(false);
  view.rerender(<MapCredits language="en" mode="open" credit="SYN-credit" />);
  expect(view.queryByText('SYN-credit')).toBeNull();
  view.rerender(
    <MapCredits language="en" mode="photoreal" credit="SYN-photo-credit" />,
  );
  expect(view.getByText('SYN-photo-credit').closest('details')).toBeNull();
});

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

it('comparison keeps the baseline visible, resets immediately, and uses Fact chips', () => {
  const registry = scenarioRegistry();
  const view = render(
    <Swipe
      language="en"
      comparison={{
        kind: 'scenario',
        baselineFactId: factId(0),
        changedFactId: factId(1),
      }}
      registry={registry}
      onOpen={() => undefined}
    />,
  );
  const baseline = view.getByRole('group', { name: 'Baseline' });
  expect(baseline.querySelector('[data-fact-chip]')).not.toBeNull();
  expect(
    view
      .getByRole('group', { name: 'Changed scenario' })
      .querySelector('[data-fact-chip]'),
  ).not.toBeNull();
  fireEvent.click(view.getByRole('button', { name: 'Show changed scenario' }));
  expect(baseline.hidden).toBe(false);
  fireEvent.click(view.getByRole('button', { name: 'Reset comparison' }));
  expect(
    view
      .getByRole('button', { name: 'Show baseline' })
      .getAttribute('aria-pressed'),
  ).toBe('true');
  expect(view.container.querySelector('input[type="range"]')).toBeNull();
  const copy = view.container.cloneNode(true) as HTMLElement;
  copy.querySelectorAll('[data-fact-chip]').forEach((chip) => chip.remove());
  expect(copy.textContent).not.toMatch(/\p{N}/u);
});

it('refuses published facts presented as a user scenario', () => {
  const view = render(
    <Swipe
      language="en"
      comparison={{
        kind: 'scenario',
        baselineFactId: factId(0),
        changedFactId: factId(0),
      }}
      registry={registryFrom(completeInput())}
      onOpen={() => undefined}
    />,
  );
  expect(view.queryByRole('group', { name: 'Baseline' })).toBeNull();
});

it('controls use wrapping logical layout and pointer targets in both directions', async () => {
  const { readFileSync } = await import('node:fs');
  const css = readFileSync('src/styles/answer.css', 'utf8');
  expect(css).toContain('min-block-size: 44px');
  expect(css).toContain('min-inline-size: 44px');
  expect(css).toContain('.map-controls');
  expect(css.match(/\.map-controls\s*\{([^}]+)\}/)?.[1]).toContain(
    'overflow-wrap: anywhere',
  );
  for (const language of ['en', 'ar'] as const) {
    const view = render(
      <MapModeSwitch
        language={language}
        modes={modes}
        selected="open"
        onChange={() => undefined}
      />,
    );
    expect(view.getByRole('radiogroup').getAttribute('dir')).toBe(
      language === 'ar' ? 'rtl' : 'ltr',
    );
    cleanup();
  }
});

it('refuses identical scenario fact identifiers', () => {
  const view = render(
    <Swipe
      language="en"
      comparison={{
        kind: 'scenario',
        baselineFactId: factId(0),
        changedFactId: factId(0),
      }}
      registry={scenarioRegistry()}
      onOpen={() => undefined}
    />,
  );
  expect(view.container.childElementCount).toBe(0);
});

it('sets Arabic photoreal credits direction and isolates runtime text', () => {
  const view = render(
    <MapCredits language="ar" mode="photoreal" credit="SYN-credit" />,
  );
  expect(
    view.container
      .querySelector('[data-part="attribution"]')
      ?.getAttribute('dir'),
  ).toBe('rtl');
  expect(view.getByText('SYN-credit').getAttribute('dir')).toBe('auto');
});
