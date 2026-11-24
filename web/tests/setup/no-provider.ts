/**
 * Request log: a web test never reaches a map provider (S3-T16, TST-248,
 * TST-255). Every fetch or XHR outside the page's own origin and loopback is
 * refused and logged; the test fails after it runs while the log is not
 * empty, so code that swallows the refusal still cannot pass.
 */
import { afterEach } from 'vitest';

export const REASON = 'provider_request_refused';
const LOOPBACK = new Set(['localhost', '127.0.0.1', '[::1]']);
const log: string[] = [];

function base(): string {
  return globalThis.location?.href ?? 'http://localhost/';
}

export function localUrl(input: string | URL): boolean {
  const url = new URL(String(input), base());
  if (url.protocol === 'data:' || url.protocol === 'blob:') return true;
  return (
    LOOPBACK.has(url.hostname) || url.hostname === globalThis.location?.hostname
  );
}

function refuse(input: string | URL): Error | null {
  if (localUrl(input)) return null;
  const href = new URL(String(input), base()).href;
  log.push(href);
  return new TypeError(`${REASON}: ${href}`);
}

export function takeRequestLog(): string[] {
  return log.splice(0, log.length);
}

const FETCH = 'fetch';
const originalFetch = Reflect.get(globalThis, FETCH) as typeof globalThis.fetch;
Reflect.set(
  globalThis,
  FETCH,
  (input: RequestInfo | URL, init?: RequestInit) => {
    const error = refuse(input instanceof Request ? input.url : input);
    return error ? Promise.reject(error) : originalFetch(input, init);
  },
);

const xhr = globalThis.XMLHttpRequest?.prototype;
if (xhr) {
  const originalOpen = xhr.open as (...args: unknown[]) => void;
  xhr.open = function open(this: XMLHttpRequest, ...args: unknown[]) {
    const error = refuse(args[1] as string | URL);
    if (error) throw error;
    originalOpen.apply(this, args);
  } as XMLHttpRequest['open'];
}

afterEach(() => {
  const refused = takeRequestLog();
  if (refused.length > 0) throw new Error(`${REASON}: ${refused.join(', ')}`);
});
