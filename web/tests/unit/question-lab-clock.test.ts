import { expect, it } from 'vitest';
import { installLabClock } from '../question_lab/clock';

it('refuses an invalid fixture clock before changing the runtime', () => {
  const original = globalThis.Date;
  expect(() => installLabClock('INVENTED-invalid-date')).toThrow(
    'fixture_clock',
  );
  expect(globalThis.Date).toBe(original);
});

it('pins both Date.now and a new Date while preserving explicit dates', () => {
  const original = globalThis.Date;
  const originalNow = original.now;
  const stamp = original.parse('2026-03-01T12:00:00Z');
  try {
    installLabClock('2026-03-01T12:00:00Z');
    expect(Date.now()).toBe(stamp);
    expect(new Date().getTime()).toBe(stamp);
    expect(new Date('2025-01-01T00:00:00Z').toISOString()).toBe(
      '2025-01-01T00:00:00.000Z',
    );
  } finally {
    globalThis.Date = original;
    original.now = originalNow;
  }
});
