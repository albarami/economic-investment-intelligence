/** BE-91: diagnostics are data; only an existing bilingual key reaches text. */
import codes from './reason-codes.generated.json';
import type { StringKey } from '../i18n';

const CLOSED = new Set<string>(codes);
const HTTP_CODES = new Set([
  'INVALID_ARGUMENT',
  'SEAT_FORBIDDEN',
  'NOT_FOUND',
  'NOT_IMPLEMENTED',
  'PROVIDER_CAP_REACHED',
  'BRIEF_STORE_PAUSED',
  'STORE_UNAVAILABLE',
  'QUERY_TIMEOUT',
  'RELEASE_MISMATCH',
  'RATE_LIMITED',
  'INTERNAL',
]);
const DEFAULT_KEYS = new Set(
  [...HTTP_CODES].map((code) => 'errors.' + code.toLowerCase()),
);
const REASON_KEYS: Readonly<Record<string, StringKey>> = {
  missing_input: 'layers.not_ranked.missing_input',
  chain_refused: 'layers.refused.registry',
  source_missing: 'layers.refused.registry',
  no_key: 'mapModes.no_key',
  offline: 'mapModes.offline',
  operation_timeout: 'mapModes.network',
};
export type RefusalState = {
  http_status: number | null;
  code: string;
  message_key: string;
  catalogue_key: StringKey;
};
export class ApiRefusal extends Error {
  constructor(
    readonly state: RefusalState,
    message = 'request_refused',
  ) {
    super(message);
  }
}
function row(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
function closed(value: unknown): string | null {
  return typeof value === 'string' &&
    (CLOSED.has(value) || DEFAULT_KEYS.has(value))
    ? value
    : null;
}
function state(
  http_status: number | null,
  code: string,
  message_key: string,
  fallback: StringKey,
): RefusalState {
  return {
    http_status,
    code,
    message_key,
    catalogue_key: REASON_KEYS[message_key] ?? fallback,
  };
}
export function refusalState(
  error: unknown,
  fallback: StringKey,
): RefusalState {
  return error instanceof ApiRefusal
    ? error.state
    : state(
        null,
        'INTERNAL',
        error instanceof Error
          ? (closed(error.message) ?? 'operation_failed')
          : 'operation_failed',
        fallback,
      );
}

/** JSON faults contain no server diagnostic; never copy SyntaxError prose. */
export async function readApiBody(
  response: Response,
  fallback: StringKey,
  message: string,
): Promise<unknown> {
  let body: unknown;
  try {
    body = await response.json();
  } catch (error) {
    throw new ApiRefusal(
      { ...refusalState(error, fallback), http_status: response.status },
      message,
    );
  }
  if (!response.ok) {
    const error = row(row(body).error);
    const code =
      typeof error.code === 'string' && HTTP_CODES.has(error.code)
        ? error.code
        : 'INTERNAL';
    const key =
      closed(error.message_key) ?? closed(error.reason) ?? 'operation_failed';
    throw new ApiRefusal(state(response.status, code, key, fallback), message);
  }
  if (body === null || typeof body !== 'object' || Array.isArray(body))
    throw new ApiRefusal(
      state(response.status, 'INTERNAL', 'operation_failed', fallback),
      message,
    );
  return body;
}

/** Governed bodies remain withheld; the FC layer's short NO_DATA is valid. */
export function outcomeRefusal(
  body: unknown,
  httpStatus: number,
  fallback: StringKey,
): RefusalState | null {
  const value = row(body);
  if (value.status !== 'NO_DATA' && value.status !== 'SUPPRESSED') return null;
  const caveats = Array.isArray(value.caveat_keys) ? value.caveat_keys : [];
  const withheld = row(value.payload).withheld;
  const first = Array.isArray(withheld)
    ? row(withheld[0]).reason_key
    : undefined;
  const key =
    closed(value.reason) ??
    closed(value.reason_key) ??
    closed(first) ??
    caveats.map(closed).find((key) => key !== null) ??
    'missing_input';
  return state(httpStatus, value.status, key, fallback);
}

export function bodyRefusal(
  message: string,
  httpStatus: number,
  fallback: StringKey,
): ApiRefusal {
  return new ApiRefusal(
    state(
      httpStatus,
      'INTERNAL',
      closed(message) ?? 'operation_failed',
      fallback,
    ),
    message,
  );
}
