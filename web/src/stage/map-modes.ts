/** Closed server availability. No browser setting or provider address. */
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

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function validMeter(value: unknown): boolean {
  if (value === null) return true;
  return (
    record(value) &&
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

export function parseModes(value: unknown): MapModes | null {
  if (
    !record(value) ||
    Object.keys(value).sort().join() !== [...MODE_NAMES].sort().join()
  )
    return null;
  for (const mode of MODE_NAMES) {
    const state = value[mode];
    if (
      !record(state) ||
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
