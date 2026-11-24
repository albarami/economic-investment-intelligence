// @vitest-environment jsdom
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ClockScrubber } from '../../src/stage/ClockScrubber';
import { clockTimestamp, clockDay } from '../../src/stage/clock';

afterEach(cleanup);
it('uses today or the supplied day with a continuous fraction and no district', () => {
  const today = new Date('2026-06-01T05:00:00Z');
  expect(clockDay(undefined, today)).toBe('2026-06-01');
  expect(clockDay(undefined, new Date('2026-06-01T21:30:00Z'))).toBe(
    '2026-06-02',
  );
  expect(clockDay(undefined, new Date('2026-06-01T20:30:00Z'))).toBe(
    '2026-06-01',
  );
  expect(clockDay('2026-06-02', today)).toBe('2026-06-02');
  expect(clockTimestamp('2026-06-01', 0.125)).toBe(
    Date.parse('2026-06-01T00:00:00Z'),
  );
  expect(clockTimestamp('2026-02-30', 0.5)).toBeNull();
  for (const fraction of [-1, 2, NaN, Infinity])
    expect(clockTimestamp('2026-06-01', fraction)).toBeNull();
});
it('has a non-drag input and no numeral outside the Fact family; no animation', () => {
  const change = vi.fn();
  const view = render(
    <ClockScrubber
      language="en"
      dayBasis="2026-06-01"
      fraction="0"
      onFractionChange={() => undefined}
      onChange={change}
    />,
  );
  const slider = view.getByRole('slider');
  expect(slider.getAttribute('step')).toBe('any');
  fireEvent.change(slider, { target: { value: '0.125' } });
  expect(change).toHaveBeenLastCalledWith(Date.parse('2026-06-01T00:00:00Z'));
  fireEvent.change(view.getByRole('textbox'), { target: { value: '0.25' } });
  expect(change).toHaveBeenLastCalledWith(Date.parse('2026-06-01T03:00:00Z'));
  fireEvent.change(view.getByRole('textbox'), { target: { value: 'bad' } });
  expect(change).toHaveBeenCalledTimes(2);
  const copy = view.container.cloneNode(true) as HTMLElement;
  copy.querySelectorAll('[data-fact-chip]').forEach((chip) => chip.remove());
  expect(copy.textContent).not.toMatch(/\p{N}/u);
  expect(
    view.container
      .querySelector('[data-clock]')
      ?.getAttribute('data-animation'),
  ).toBe('none');
  expect(view.queryByRole('button', { name: /play/i })).toBeNull();
});

it('refuses malformed days and fractions while accepting both day boundaries', () => {
  for (const day of ['bad', '2026-13-01', '2026-06-01T00:00:00Z'])
    expect(clockTimestamp(day, 0)).toBeNull();
  expect(clockTimestamp('2026-06-01', 0)).toBe(
    Date.parse('2026-05-31T21:00:00Z'),
  );
  expect(clockTimestamp('2026-06-01', 1)).toBe(
    Date.parse('2026-06-01T21:00:00Z'),
  );
  const change = vi.fn();
  const view = render(
    <ClockScrubber
      language="ar"
      dayBasis="2026-06-01"
      fraction="0"
      onFractionChange={() => undefined}
      onChange={change}
    />,
  );
  fireEvent.change(view.getByRole('textbox'), { target: { value: '' } });
  expect(change).not.toHaveBeenCalled();
  expect(
    view.container.querySelector('[data-clock]')?.getAttribute('dir'),
  ).toBe('rtl');
});
