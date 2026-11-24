import { expect, it } from 'vitest';
import { parseModes } from '../../src/stage/map-modes';

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

it('requires the photoreal meter field and refuses it on other modes', () => {
  expect(
    parseModes({ ...modes, photoreal: { available: true, reason: null } }),
  ).toBeNull();
  expect(parseModes({ ...modes, open: { ...modes.open, meter } })).toBeNull();
});
