// @vitest-environment jsdom
import { plainPort } from '../fixtures/plain-port';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { FactChip } from '../../src/facts/FactChip';
import { Stage } from '../../src/stage/Stage';
import { text } from '../../src/i18n';
import { operationalMeter as meter } from '../fixtures/operational-meter';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it.each(['en', 'ar'] as const)(
  'renders exact server money and journal explanation in %s',
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
    expect(
      chip.querySelector('[data-quantity="spend"] .chip-num')?.textContent,
    ).toBe(meter.spend_usd);
    expect(
      chip.querySelector('[data-quantity="requests"] .chip-num')?.textContent,
    ).toBe('8');
    expect(
      chip.querySelector('[data-quantity="limit"] .chip-num')?.textContent,
    ).toBe('10');
    expect(
      chip.querySelector('[data-quantity="ceiling"] .chip-num')?.textContent,
    ).toBe(meter.ceiling_usd);
    expect(
      [...chip.querySelectorAll('.chip-num')].every(
        (node) => node.tagName === 'BDI' && node.getAttribute('dir') === 'ltr',
      ),
    ).toBe(true);
    fireEvent.click(view.getByRole('button'));
    const panel = view.getByRole('region', {
      name: text(language, 'operational.title'),
    });
    expect(panel.closest('[data-fact-chip]')).toBe(chip);
    expect(panel.textContent).toContain('Budget.meter');
    expect(panel.textContent).toContain('EII_PHOTOREAL_PRICE_PER_THOUSAND');
    expect(panel.textContent).toContain('SPEND_CEILING_USD');
    expect(panel.textContent).toContain(text(language, 'operational.journal'));
    expect(panel.textContent).toContain(text(language, 'operational.toRecord'));
    expect(
      panel.querySelector('[data-quantity="price"] .chip-num')?.textContent,
    ).toBe(meter.price_per_thousand_usd);
    expect(panel.textContent).not.toMatch(
      /Public|Synthetic|Simulated|licence|release fact/i,
    );
    fireEvent.click(view.getByRole('button'));
    expect(view.queryByRole('region')).toBeNull();
  },
);

it('uses only the server warning flag even with deliberately contradictory numbers', () => {
  const view = render(
    <FactChip
      variant="operational"
      language="en"
      meter={{ ...meter, billable_requests: 0, warning: true }}
      reason={null}
    />,
  );
  expect(view.getByRole('status').textContent).toBe(
    text('en', 'operational.warning'),
  );
  view.rerender(
    <FactChip
      variant="operational"
      language="en"
      meter={{ ...meter, billable_requests: 10, warning: false }}
      reason={null}
    />,
  );
  expect(view.queryByRole('status')).toBeNull();
});

it.each(['en', 'ar'] as const)(
  'withholds null with reason and no zero in %s',
  (language) => {
    const view = render(
      <FactChip
        variant="operational"
        language={language}
        meter={null}
        reason="count_unavailable"
      />,
    );
    expect(
      view.container.querySelector('[data-state="withheld"] .chip-withheld'),
    ).not.toBeNull();
    expect(view.container.textContent).toContain(
      text(language, 'mapModes.count_unavailable'),
    );
    expect(view.container.querySelector('.chip-num')).toBeNull();
    expect(view.container.textContent).not.toMatch(/\p{Nd}/u);
  },
);

it('mounts in stage controls and refreshes on the existing mode-error response without extra fetches', async () => {
  const modes = {
    open: { available: true, reason: null },
    satellite: { available: false, reason: 'no_key' },
    photoreal: { available: true, reason: null, meter },
  };
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: async () => modes })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ...modes,
        photoreal: {
          available: false,
          reason: 'cap_reached',
          meter: { ...meter, spend_usd: '19.998' },
        },
      }),
    });
  vi.stubGlobal('fetch', fetcher);
  let fail: (() => void) | undefined;
  const view = render(
    <Stage
      language="en"
      theme="dark"
      extractUrl="/SYN-map.pmtiles"
      mapStarter={() => ({
        ...plainPort(320, 320),
        bind: vi.fn(),
        unbind: vi.fn(),
        bindView: vi.fn(),
        unbindView: vi.fn(),
        remove: vi.fn(),
        mountOverlay: vi.fn(),
        onModeError: (callback) => {
          fail = () => callback('photoreal');
          return vi.fn();
        },
      })}
    />,
  );
  await waitFor(() =>
    expect(
      view.container.querySelector(
        '.map-controls [data-quantity="spend"] .chip-num',
      )?.textContent,
    ).toBe(meter.spend_usd),
  );
  await waitFor(() => expect(fail).toBeDefined());
  fail!();
  await waitFor(() =>
    expect(
      view.container.querySelector('[data-quantity="spend"] .chip-num')
        ?.textContent,
    ).toBe('19.998'),
  );
  expect(view.container.textContent).toContain(
    text('en', 'mapModes.cap_reached'),
  );
  expect(fetcher).toHaveBeenCalledTimes(2);
});
