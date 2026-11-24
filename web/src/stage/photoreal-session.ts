/** One application view, with opaque aliases; never a browser native session. */
import { requestLocal } from '../api/address-search.mjs';

const unavailable = () => new Error('photoreal unavailable');
export function tilePath(path: string, view: string): string {
  if (
    !/^\/api\/photoreal\/3dtiles\/(?:[A-Za-z0-9_-]+\/)*[A-Za-z0-9_-]+\.(?:json|glb)$/.test(
      path,
    ) ||
    !/^[a-f0-9]{32}$/.test(view)
  )
    throw unavailable();
  return `${path}?view=${view}`;
}
export function photorealSession(fetcher?: typeof fetch) {
  const abort = new AbortController();
  let view: string | null = null;
  let opened = false;
  const remove = (id: string) => {
    void requestLocal(
      `/api/photoreal/views/${id}`,
      { method: 'DELETE', cache: 'no-store' },
      fetcher,
    ).catch(() => undefined);
  };
  return {
    signal: abort.signal,
    async open() {
      if (opened || abort.signal.aborted) throw unavailable();
      opened = true;
      try {
        const response = await requestLocal(
          '/api/photoreal/views',
          { method: 'POST', cache: 'no-store', signal: abort.signal },
          fetcher,
        );
        if (!response.ok) throw unavailable();
        const body: unknown = await response.json();
        // Keep an allocated identifier even when the remaining schema is refused.
        if (
          body &&
          typeof body === 'object' &&
          !Array.isArray(body) &&
          'view_id' in body &&
          typeof body.view_id === 'string' &&
          /^[a-f0-9]{32}$/.test(body.view_id)
        )
          view = body.view_id;
        if (
          !body ||
          typeof body !== 'object' ||
          Array.isArray(body) ||
          Object.keys(body).join() !== 'view_id' ||
          !('view_id' in body) ||
          typeof body.view_id !== 'string' ||
          !/^[a-f0-9]{32}$/.test(body.view_id)
        )
          throw unavailable();
        if (abort.signal.aborted) {
          throw unavailable();
        }
        view = body.view_id;
        return '/api/photoreal/3dtiles/root.json';
      } catch {
        if (view) remove(view);
        view = null;
        throw unavailable();
      }
    },
    async fetch(input: RequestInfo | URL, init?: RequestInit) {
      if (!view || abort.signal.aborted || typeof input !== 'string')
        throw unavailable();
      let path = input;
      if (
        typeof location !== 'undefined' &&
        path.startsWith(location.origin + '/')
      )
        path = path.slice(location.origin.length);
      try {
        const response = await requestLocal(
          tilePath(path, view),
          {
            cache: 'no-store',
            redirect: 'error',
            signal: init?.signal
              ? AbortSignal.any([abort.signal, init.signal])
              : abort.signal,
          },
          fetcher,
        );
        if (!response.ok || abort.signal.aborted) throw unavailable();
        // Keep the application query inside transport: Tileset3D inherits Response.url.
        const local = new Response(response.body, {
          status: response.status,
          headers: response.headers,
        });
        Object.defineProperty(local, 'url', { value: path });
        return local;
      } catch {
        throw unavailable();
      }
    },
    dispose() {
      abort.abort();
      if (view) remove(view);
      view = null;
    },
  };
}
