import { expect, it, vi } from 'vitest';
import { photorealSession, tilePath } from '../../src/stage/photoreal-session';

it('accepts exactly a local query-free alias and appends one view', () => {
  expect(tilePath('/api/photoreal/3dtiles/invented.glb', 'a'.repeat(32))).toBe(
    '/api/photoreal/3dtiles/invented.glb?view=' + 'a'.repeat(32),
  );
  for (const path of [
    '//foreign.invalid/a.glb',
    '/api/photoreal/3dtiles/../a.glb',
    '/api/photoreal/3dtiles/a.glb?session=bad',
    '/api/photoreal/3dtiles/a.glb?view=bad',
    '/api/photoreal/3dtiles/a%2f.glb',
  ])
    expect(() => tilePath(path, 'a'.repeat(32))).toThrow();
});
it('rejects extra view fields, performs no retry, and disposes a late view', async () => {
  const fetcher = vi.fn(
    async () =>
      new Response(JSON.stringify({ view_id: 'a'.repeat(32), extra: true })),
  );
  const session = photorealSession(fetcher);
  await expect(session.open()).rejects.toThrow('photoreal unavailable');
  session.dispose();
  await expect(session.open()).rejects.toThrow('photoreal unavailable');
  expect(
    fetcher.mock.calls.map(([path, options]) => [path, options.method]),
  ).toEqual([
    ['/api/photoreal/views', 'POST'],
    ['/api/photoreal/views/' + 'a'.repeat(32), 'DELETE'],
  ]);
  let resolve!: (r: Response) => void;
  const late = vi.fn(
    () =>
      new Promise<Response>((r) => {
        resolve = r;
      }),
  );
  const pending = photorealSession(late);
  const request = pending.open();
  pending.dispose();
  resolve(new Response(JSON.stringify({ view_id: 'a'.repeat(32) })));
  await expect(request).rejects.toThrow('photoreal unavailable');
  expect(late).toHaveBeenCalledTimes(2);
  expect(late.mock.calls[1]?.[0]).toBe(
    '/api/photoreal/views/' + 'a'.repeat(32),
  );
});
it('keeps one view and no-store for descendants and cancels on disposal', async () => {
  const fetcher = vi.fn(
    async (path: string) =>
      new Response(
        path.endsWith('/views')
          ? JSON.stringify({ view_id: 'a'.repeat(32) })
          : 'invented',
      ),
  );
  const session = photorealSession(fetcher);
  await session.open();
  await session.fetch('/api/photoreal/3dtiles/child.glb');
  session.dispose();
  const options = fetcher.mock.calls[1]?.[1] as RequestInit;
  expect(options.cache).toBe('no-store');
  expect(options.signal?.aborted).toBe(true);
  await expect(
    session.fetch('/api/photoreal/3dtiles/child.glb'),
  ).rejects.toThrow();
});

it('does not expose the application view query to loader URL inheritance', async () => {
  const fetcher = vi.fn(async (path: string) => {
    const response = new Response(
      path.endsWith('/views')
        ? JSON.stringify({ view_id: 'a'.repeat(32) })
        : 'invented',
    );
    Object.defineProperty(response, 'url', { value: path });
    return response;
  });
  const session = photorealSession(fetcher);
  await session.open();
  const response = await session.fetch('/api/photoreal/3dtiles/child.glb');
  expect(response.url).toBe('/api/photoreal/3dtiles/child.glb');
  session.dispose();
});

it.each([{}, { extra: true }])(
  'deletes a late allocated view exactly once even with body fields %j',
  async (fields) => {
    let resolve!: (value: Response) => void;
    const fetcher = vi.fn((_path, init) =>
      init.method === 'POST'
        ? new Promise<Response>((done) => {
            resolve = done;
          })
        : Promise.resolve(new Response(null, { status: 204 })),
    );
    const session = photorealSession(fetcher);
    const pending = session.open();
    session.dispose();
    resolve(
      new Response(JSON.stringify({ view_id: 'a'.repeat(32), ...fields })),
    );
    await expect(pending).rejects.toThrow(/^photoreal unavailable$/);
    session.dispose();
    expect(fetcher.mock.calls.map(([url, init]) => [url, init.method])).toEqual(
      [
        ['/api/photoreal/views', 'POST'],
        ['/api/photoreal/views/' + 'a'.repeat(32), 'DELETE'],
      ],
    );
  },
);
