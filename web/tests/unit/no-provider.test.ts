// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

const send = (input: RequestInfo | URL) =>
  (Reflect.get(globalThis, 'fetch') as typeof globalThis.fetch)(input);

import { REASON, localUrl, takeRequestLog } from '../setup/no-provider';

// S3-T16: a web test never reaches the imagery or photorealistic provider.
describe('provider request log', () => {
  it('keeps same-origin, loopback, data and blob addresses local', () => {
    for (const url of [
      '/api/imagery/tiles/1/0/0',
      '/api/photoreal/views',
      'http://localhost:3000/api/map-modes',
      'http://127.0.0.1/x',
      'http://[::1]/x',
      'data:,x',
      'blob:http://localhost:3000/a',
    ])
      expect(localUrl(url), url).toBe(true);
  });

  it('refuses a provider host, with or without a key', () => {
    for (const url of [
      'https://imagery.provider.invalid/tile/1/0/0',
      'https://tiles.provider.invalid/v1/3dtiles/root.json?key=',
      '//tiles.provider.invalid/v1/3dtiles/root.json',
      'http://localhost.provider.invalid/x',
    ])
      expect(localUrl(url), url).toBe(false);
  });

  it('refuses and logs a planted fetch to a provider host', async () => {
    await expect(
      send('https://imagery.provider.invalid/tile/1/0/0'),
    ).rejects.toThrow(REASON);
    expect(takeRequestLog()).toEqual([
      'https://imagery.provider.invalid/tile/1/0/0',
    ]);
  });

  it('refuses and logs a planted request object and a planted XHR', async () => {
    await expect(
      send(new Request('https://tiles.provider.invalid/v1/3dtiles/root.json')),
    ).rejects.toThrow(REASON);
    const xhr = new XMLHttpRequest();
    expect(() =>
      xhr.open('GET', 'https://tiles.provider.invalid/v1/a.glb'),
    ).toThrow(REASON);
    expect(takeRequestLog()).toEqual([
      'https://tiles.provider.invalid/v1/3dtiles/root.json',
      'https://tiles.provider.invalid/v1/a.glb',
    ]);
  });
});
