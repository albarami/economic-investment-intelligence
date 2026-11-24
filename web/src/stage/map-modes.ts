/** Closed server availability. No browser setting or provider address. */
import { isRecord } from '../guards';
export type MapMode = 'open' | 'satellite' | 'photoreal';
export type ModeReason =
  | 'no_key'
  | 'no_address'
  | 'offline'
  | 'cap_reached'
  | 'count_unavailable'
  | 'network'
  | 'renderer_unavailable';
export type ModeFailureReason = Extract<
  ModeReason,
  'network' | 'renderer_unavailable'
>;
export class ModeFailure extends Error {
  constructor(readonly reason: ModeFailureReason) {
    super('photoreal unavailable');
  }
}
export function modeFailureReason(error: unknown): ModeFailureReason {
  return error instanceof ModeFailure ? error.reason : 'network';
}
export type ModeAvailability =
  { available: true; reason: null } | { available: false; reason: ModeReason };
export interface SpendMeter {
  billable_requests: number;
  request_limit: number;
  spend_usd: string;
  warning: boolean;
  ceiling_usd: string;
  price_per_thousand_usd: string;
  method_version: '1';
  default_price_retrieved_on: '2026-11-13';
}
export type MapModes = Record<MapMode, ModeAvailability> & {
  photoreal: ModeAvailability & { meter: SpendMeter | null };
};
export const MODE_NAMES: readonly MapMode[] = [
  'open',
  'satellite',
  'photoreal',
];
const REASONS: readonly string[] = [
  'no_key',
  'no_address',
  'offline',
  'cap_reached',
  'count_unavailable',
  'network',
];

function validMeter(value: unknown): boolean {
  if (value === null) return true;
  return (
    isRecord(value) &&
    Object.keys(value).sort().join() ===
      'billable_requests,ceiling_usd,default_price_retrieved_on,method_version,price_per_thousand_usd,request_limit,spend_usd,warning' &&
    Number.isSafeInteger(value.billable_requests) &&
    (value.billable_requests as number) >= 0 &&
    Number.isSafeInteger(value.request_limit) &&
    (value.request_limit as number) >= 0 &&
    typeof value.spend_usd === 'string' &&
    /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(value.spend_usd) &&
    typeof value.warning === 'boolean' &&
    typeof value.ceiling_usd === 'string' &&
    /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(value.ceiling_usd) &&
    typeof value.price_per_thousand_usd === 'string' &&
    /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(value.price_per_thousand_usd) &&
    value.method_version === '1' &&
    value.default_price_retrieved_on === '2026-11-13'
  );
}

export const METER_HEADER = 'x-spend-meter';
export const ORDER_HEADER = 'x-spend-order';
/** A journal step is a canonical decimal. Sixteen digits covers every count the journal can name. */
export const JOURNAL_ORDER_MAX_CHARS = 16;
const METER_HEADER_MAX_CHARS = 1024;
const CANONICAL_ORDER = /^(?:0|[1-9][0-9]*)$/;
export type MeterHeader =
  | { state: 'absent' }
  | { state: 'malformed' }
  | { state: 'rejected' }
  | { state: 'ready'; meter: SpendMeter };

/** Closed header value. No sum, product or warning comparison. */
export function readMeterHeader(raw: string | null): MeterHeader {
  if (raw === null) return { state: 'absent' };
  if (raw.length > METER_HEADER_MAX_CHARS) return { state: 'rejected' };
  try {
    const value: unknown = JSON.parse(raw);
    if (!validMeter(value) || value === null) return { state: 'rejected' };
    return { state: 'ready', meter: value as SpendMeter };
  } catch {
    return { state: 'malformed' };
  }
}

export type JournalOrderReading =
  | { state: 'absent' }
  | { state: 'malformed' }
  | { state: 'ready'; token: string };

export type OrderDecision =
  | { state: 'accept'; token: string }
  | {
      state: 'withhold';
      reason: 'absent' | 'malformed' | 'stale' | 'duplicate';
    };

/** Closed order token. No sum or comparison of a displayed meter field. */
export function readJournalOrder(raw: string | null): JournalOrderReading {
  if (raw === null) return { state: 'absent' };
  if (raw.length > JOURNAL_ORDER_MAX_CHARS) return { state: 'malformed' };
  if (!CANONICAL_ORDER.test(raw)) return { state: 'malformed' };
  return { state: 'ready', token: raw };
}

/**
 * The server's journal step decides. A later canonical token replaces the
 * held one. Equal tokens and earlier tokens are withheld.
 */
export function decideJournalOrder(
  held: string | null,
  raw: string | null,
): OrderDecision {
  const reading = readJournalOrder(raw);
  if (reading.state === 'absent')
    return { state: 'withhold', reason: 'absent' };
  if (reading.state === 'malformed')
    return { state: 'withhold', reason: 'malformed' };
  if (held === null) return { state: 'accept', token: reading.token };
  if (reading.token === held) return { state: 'withhold', reason: 'duplicate' };
  if (!laterJournalToken(held, reading.token))
    return { state: 'withhold', reason: 'stale' };
  return { state: 'accept', token: reading.token };
}

/** More digits is later. The same length uses code-unit order. No numeric parse. */
function laterJournalToken(held: string, incoming: string): boolean {
  if (incoming.length !== held.length) return incoming.length > held.length;
  return incoming > held;
}

export function parseModes(value: unknown): MapModes | null {
  if (
    !isRecord(value) ||
    Object.keys(value).sort().join() !== [...MODE_NAMES].sort().join()
  )
    return null;
  for (const mode of MODE_NAMES) {
    const state = value[mode];
    if (
      !isRecord(state) ||
      Object.keys(state).sort().join() !==
        (mode === 'photoreal'
          ? 'available,meter,reason'
          : 'available,reason') ||
      (mode === 'photoreal' && !validMeter(state.meter))
    )
      return null;
    if (state.available === true && state.reason === null) continue;
    if (
      state.available !== false ||
      typeof state.reason !== 'string' ||
      !REASONS.includes(state.reason)
    )
      return null;
  }
  const result = value as MapModes;
  return result.open.available ? result : null;
}

export function selectedMode(requested: MapMode, modes: MapModes): MapMode {
  return modes[requested].available ? requested : 'open';
}
