/** Deferred photoreal tile responses for the spend-meter order tests. */
import { act, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { text, type Language } from '../../src/i18n';

interface MeterSnapshot {
  spend_usd: string;
}

interface OpenedOrder {
  view: { container: HTMLElement };
  load: (url: string) => Promise<Response>;
  pending: Map<string, (response: Response) => void>;
}

export function tileResponse(snapshot: object, order: string): Response {
  return new Response('{}', {
    status: 200,
    headers: {
      'x-spend-meter': JSON.stringify(snapshot),
      'x-spend-order': order,
    },
  });
}

export function deferredTiles(modes: () => Response, view: () => Response) {
  const pending = new Map<string, (response: Response) => void>();
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/map-modes') return modes();
    if (url === '/api/photoreal/views' && init?.method === 'POST')
      return view();
    if (String(url).startsWith('/api/photoreal/3dtiles/')) {
      const path = new URL(String(url), 'http://fixture.invalid').pathname;
      return new Promise<Response>((resolve) => {
        pending.set(path, resolve);
      });
    }
    return new Response(null, { status: 204 });
  });
  return { fetcher, pending };
}

export async function releaseTile(
  pending: Map<string, (response: Response) => void>,
  path: string,
  response: Response,
  done: Promise<Response>,
) {
  await act(async () => {
    pending.get(path)!(response);
    await done;
  });
}

function chip(view: { container: HTMLElement }) {
  return {
    requests: view.container.querySelector(
      '[data-quantity="requests"] .chip-num',
    )?.textContent,
    spend: view.container.querySelector('[data-quantity="spend"] .chip-num')
      ?.textContent,
    warning:
      view.container.querySelector('[role="status"]')?.textContent ?? null,
  };
}

export function registerJournalOrderTests(deps: {
  open: (language: Language) => Promise<OpenedOrder>;
  crossed: MeterSnapshot;
  stillBelow: MeterSnapshot;
}) {
  const { open, crossed, stillBelow } = deps;
  it.each(['en', 'ar'] as const)(
    'keeps the later journal snapshot when an older tile response arrives second in %s',
    async (language) => {
      const { view, load, pending } = await open(language);
      const older = load('/api/photoreal/3dtiles/older.json');
      const newer = load('/api/photoreal/3dtiles/newer.json');
      await waitFor(() => expect(pending.size).toBe(2));
      await releaseTile(
        pending,
        '/api/photoreal/3dtiles/newer.json',
        tileResponse(crossed, '8'),
        newer,
      );
      await waitFor(() => expect(chip(view).requests).toBe('8'));
      expect(chip(view).spend).toBe(crossed.spend_usd);
      expect(chip(view).warning).toBe(text(language, 'operational.warning'));
      await releaseTile(
        pending,
        '/api/photoreal/3dtiles/older.json',
        tileResponse(stillBelow, '7'),
        older,
      );
      expect(chip(view)).toEqual({
        requests: '8',
        spend: crossed.spend_usd,
        warning: text(language, 'operational.warning'),
      });
    },
  );

  it.each(['en', 'ar'] as const)(
    'keeps the later token when a higher count arrives after it in %s',
    async (language) => {
      const { view, load, pending } = await open(language);
      const laterToken = load('/api/photoreal/3dtiles/later-token.json');
      const earlierToken = load('/api/photoreal/3dtiles/earlier-token.json');
      await waitFor(() => expect(pending.size).toBe(2));
      await releaseTile(
        pending,
        '/api/photoreal/3dtiles/later-token.json',
        tileResponse(stillBelow, '8'),
        laterToken,
      );
      await waitFor(() => expect(chip(view).requests).toBe('7'));
      await releaseTile(
        pending,
        '/api/photoreal/3dtiles/earlier-token.json',
        tileResponse(crossed, '7'),
        earlierToken,
      );
      expect(chip(view)).toEqual({
        requests: '7',
        spend: stillBelow.spend_usd,
        warning: null,
      });
    },
  );
}
