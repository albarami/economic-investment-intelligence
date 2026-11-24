import { expect, it } from 'vitest';
import {
  JOURNAL_ORDER_MAX_CHARS,
  decideJournalOrder,
  parseModes,
  readMeterHeader,
} from '../../src/stage/map-modes';

import { operationalMeter as meter } from '../fixtures/operational-meter';
const modes = {
  open: { available: true, reason: null },
  satellite: { available: false, reason: 'no_key' },
  photoreal: { available: true, reason: null, meter },
};

it('accepts the server meter without browser money or warning calculations', () => {
  expect(parseModes(modes)).toEqual(modes);
  expect(
    parseModes({
      ...modes,
      photoreal: { available: false, reason: 'cap_reached', meter },
    }),
  ).not.toBeNull();
  expect(
    parseModes({
      ...modes,
      photoreal: { available: false, reason: 'count_unavailable', meter: null },
    }),
  ).not.toBeNull();
});

it.each([
  { ...meter, billable_requests: -1 },
  { ...meter, billable_requests: 1.5 },
  { ...meter, billable_requests: Number.MAX_SAFE_INTEGER + 1 },
  { ...meter, request_limit: -1 },
  { ...meter, request_limit: '10' },
  { ...meter, spend_usd: 0.057 },
  { ...meter, spend_usd: '-0.057' },
  { ...meter, spend_usd: 'NaN' },
  { ...meter, warning: 'true' },
  { ...meter, extra: true },
  { ...meter, ceiling_usd: 20 },
  { ...meter, price_per_thousand_usd: 'NaN' },
  { ...meter, method_version: 'unknown' },
  { ...meter, default_price_retrieved_on: 'tomorrow' },
  { billable_requests: 8, request_limit: 10, warning: true },
])('rejects malformed operational meter %j', (invalid) => {
  expect(
    parseModes({ ...modes, photoreal: { ...modes.photoreal, meter: invalid } }),
  ).toBeNull();
});

it('names an absent spend header', () => {
  expect(readMeterHeader(null)).toEqual({ state: 'absent' });
});

it('names a malformed spend header', () => {
  expect(readMeterHeader('not-json')).toEqual({ state: 'malformed' });
});

it('names an empty spend header as malformed', () => {
  expect(readMeterHeader('')).toEqual({ state: 'malformed' });
});

it('names a rejected spend header when one field is extra', () => {
  expect(readMeterHeader(JSON.stringify({ ...meter, extra: true }))).toEqual({
    state: 'rejected',
  });
});

it('names a rejected spend header when the value is null', () => {
  expect(readMeterHeader('null')).toEqual({ state: 'rejected' });
});

it('names a rejected spend header when the value exceeds the closed length', () => {
  const huge = { ...meter, spend_usd: `1.${'0'.repeat(1100)}` };
  expect(readMeterHeader(JSON.stringify(huge))).toEqual({ state: 'rejected' });
});

it('keeps a false warning that the count alone would not decide', () => {
  const silent = { ...meter, billable_requests: 8, warning: false };
  expect(readMeterHeader(JSON.stringify(silent))).toEqual({
    state: 'ready',
    meter: silent,
  });
});

it('names an absent order token', () => {
  expect(decideJournalOrder(null, null)).toEqual({
    state: 'withhold',
    reason: 'absent',
  });
});

it.each([
  '',
  '08',
  '8 ',
  '8a',
  '+8',
  '-1',
  '1'.repeat(JOURNAL_ORDER_MAX_CHARS + 1),
])('names order token %j as malformed', (raw) => {
  expect(decideJournalOrder(null, raw)).toEqual({
    state: 'withhold',
    reason: 'malformed',
  });
});

it('withholds a duplicate order token', () => {
  expect(decideJournalOrder('8', '8')).toEqual({
    state: 'withhold',
    reason: 'duplicate',
  });
});

it('withholds an earlier order token', () => {
  expect(decideJournalOrder('8', '7')).toEqual({
    state: 'withhold',
    reason: 'stale',
  });
});

it('withholds a shorter earlier order token', () => {
  expect(decideJournalOrder('10', '9')).toEqual({
    state: 'withhold',
    reason: 'stale',
  });
});

it('accepts the first canonical order token', () => {
  expect(decideJournalOrder(null, '0')).toEqual({
    state: 'accept',
    token: '0',
  });
});

it('accepts a longer later order token', () => {
  expect(decideJournalOrder('9', '10')).toEqual({
    state: 'accept',
    token: '10',
  });
});

it('orders every journal token from 0 through 40 by the integer oracle', () => {
  const later = (held: number, incoming: number) => incoming > held;
  for (let held = 0; held <= 40; held += 1) {
    for (let incoming = 0; incoming <= 40; incoming += 1) {
      const decision = decideJournalOrder(String(held), String(incoming));
      if (later(held, incoming)) {
        expect(decision).toEqual({ state: 'accept', token: String(incoming) });
      } else if (held === incoming) {
        expect(decision).toEqual({ state: 'withhold', reason: 'duplicate' });
      } else {
        expect(decision).toEqual({ state: 'withhold', reason: 'stale' });
      }
    }
  }
});

it('requires the photoreal meter field and refuses it on other modes', () => {
  expect(
    parseModes({ ...modes, photoreal: { available: true, reason: null } }),
  ).toBeNull();
  expect(parseModes({ ...modes, open: { ...modes.open, meter } })).toBeNull();
});
