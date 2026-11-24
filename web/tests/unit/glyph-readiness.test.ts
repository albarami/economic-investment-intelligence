/** S3-T27 box 3: readiness for the local glyph ranges before the first frame. */
import { describe, expect, it, vi } from 'vitest';

import {
  GLYPH_MIME,
  READINESS_RANGES,
  glyphReadiness,
  glyphUrl,
} from '../../src/api/glyphs';

interface StubResponse {
  ok: boolean;
  status: number;
  headers: { get(name: string): string | null };
  arrayBuffer(): Promise<ArrayBuffer>;
}

function stubResponse(
  bytes: Uint8Array,
  options: { status?: number; type?: string } = {},
): StubResponse {
  const status = options.status ?? 200;
  const type = options.type ?? GLYPH_MIME;
  return {
    ok: status === 200,
    status,
    headers: {
      get(name: string) {
        return name.toLowerCase() === 'content-type' ? type : null;
      },
    },
    arrayBuffer: async () => bytes.buffer as ArrayBuffer,
  };
}

function stubFetcher(
  responses: () => StubResponse,
): typeof fetch & { urls: string[] } {
  const urls: string[] = [];
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    urls.push(String(input));
    return responses() as unknown as Response;
  });
  return Object.assign(fetcher, { urls }) as typeof fetch & {
    urls: string[];
  };
}

const ORIGIN = 'http://127.0.0.1:8088';
const ALL_SPANS = READINESS_RANGES.map(([start, end]) => `${start}-${end}.pbf`);

describe('glyphUrl', () => {
  it('builds the same-origin URL for the closed stack and an aligned span', () => {
    expect(glyphUrl(ORIGIN, 'Noto Sans Medium', '0-255.pbf')).toBe(
      `${ORIGIN}/fonts/Noto%20Sans%20Medium/0-255.pbf`,
    );
  });

  it('refuses a stack outside the closed set and every escaped span', () => {
    expect(glyphUrl(ORIGIN, 'Noto Sans Regular', '0-255.pbf')).toBeNull();
    for (const span of [
      '',
      '0-255.pbf/../../etc/passwd',
      '../0-255.pbf',
      '0-255.pbf%2f..',
      '0-255.txt',
      '00-0255.pbf',
      '1-256.pbf',
      '0-255.pbf/extra',
      '0-255.pbf ',
      '0-255',
    ])
      expect(glyphUrl(ORIGIN, 'Noto Sans Medium', span)).toBeNull();
  });

  it('accepts exactly the aligned 256-codepoint spans by property', () => {
    // Property over the whole span domain: every aligned block name is
    // accepted, and every one-character mutation of it is refused.
    let seed = 0x2c1b3d4f;
    const random = () => {
      seed = (seed * 1664525 + 1013904223) >>> 0;
      return seed / 0x100000000;
    };
    const alphabet = '0123456789-.pbf/%\\ ';
    for (let block = 0; block * 256 <= 0xff00; block += 1) {
      const start = block * 256;
      const span = `${start}-${start + 255}.pbf`;
      expect(glyphUrl(ORIGIN, 'Noto Sans Medium', span)).toBe(
        `${ORIGIN}/fonts/Noto%20Sans%20Medium/${span}`,
      );
      const index = Math.floor(random() * span.length);
      const mutated =
        span.slice(0, index) +
        alphabet[Math.floor(random() * alphabet.length)] +
        span.slice(index + 1);
      if (mutated !== span)
        expect(glyphUrl(ORIGIN, 'Noto Sans Medium', mutated)).toBeNull();
    }
  });

  it('refuses an aligned, correctly sized span above the upper boundary', () => {
    expect(glyphUrl(ORIGIN, 'Noto Sans Medium', '65536-65791.pbf')).toBeNull();
  });
});

describe('glyphReadiness', () => {
  it('is ready when every range serves bytes with the glyph MIME type', async () => {
    const fetcher = stubFetcher(() => stubResponse(new Uint8Array([1, 2, 3])));
    await expect(glyphReadiness(ORIGIN, { fetcher })).resolves.toBeNull();
    expect(fetcher.urls).toEqual(
      ALL_SPANS.map((span) => `${ORIGIN}/fonts/Noto%20Sans%20Medium/${span}`),
    );
  });

  it('refuses a missing font with glyph_status', async () => {
    const fetcher = stubFetcher(() =>
      stubResponse(new Uint8Array([1]), {
        status: 404,
        type: 'application/json',
      }),
    );
    await expect(glyphReadiness(ORIGIN, { fetcher })).resolves.toBe(
      'glyph_status',
    );
  });

  it('refuses a 404 with the glyph MIME type and a nonempty body with glyph_status', async () => {
    const fetcher = stubFetcher(() =>
      stubResponse(new Uint8Array([1]), { status: 404 }),
    );
    await expect(glyphReadiness(ORIGIN, { fetcher })).resolves.toBe(
      'glyph_status',
    );
  });

  it('refuses a body read failure after a good status and type with glyph_network', async () => {
    const fetcher = stubFetcher(() => ({
      ...stubResponse(new Uint8Array([1])),
      arrayBuffer: () =>
        Promise.reject(new TypeError('invented body stream failure')),
    }));
    await expect(glyphReadiness(ORIGIN, { fetcher })).resolves.toBe(
      'glyph_network',
    );
  });

  it('refuses a .pbf served as text/plain with glyph_wrong_type', async () => {
    const fetcher = stubFetcher(() =>
      stubResponse(new Uint8Array([1]), { type: 'text/plain' }),
    );
    await expect(glyphReadiness(ORIGIN, { fetcher })).resolves.toBe(
      'glyph_wrong_type',
    );
  });

  it('refuses a .woff2-typed body with glyph_wrong_type', async () => {
    const fetcher = stubFetcher(() =>
      stubResponse(new Uint8Array([1]), { type: 'font/woff2' }),
    );
    await expect(glyphReadiness(ORIGIN, { fetcher })).resolves.toBe(
      'glyph_wrong_type',
    );
  });

  it('refuses an empty glyph body with glyph_empty', async () => {
    const fetcher = stubFetcher(() => stubResponse(new Uint8Array(0)));
    await expect(glyphReadiness(ORIGIN, { fetcher })).resolves.toBe(
      'glyph_empty',
    );
  });

  it('refuses a network failure with glyph_network', async () => {
    const fetcher = vi.fn(async () => {
      throw new TypeError('invented network failure');
    });
    await expect(glyphReadiness(ORIGIN, { fetcher })).resolves.toBe(
      'glyph_network',
    );
  });

  it('refuses a stack outside the closed set with glyph_stack_not_closed and fetches nothing', async () => {
    const fetcher = stubFetcher(() => stubResponse(new Uint8Array([1])));
    await expect(
      glyphReadiness(ORIGIN, { stack: 'Noto Sans Regular', fetcher }),
    ).resolves.toBe('glyph_stack_not_closed');
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('refuses an escaped span with glyph_span_invalid and fetches nothing for it', async () => {
    const fetcher = stubFetcher(() => stubResponse(new Uint8Array([1])));
    await expect(
      glyphReadiness(ORIGIN, {
        spans: ['0-255.pbf', '0-255.pbf/../../etc/passwd'],
        fetcher,
      }),
    ).resolves.toBe('glyph_span_invalid');
    expect(fetcher.urls).toEqual([
      `${ORIGIN}/fonts/Noto%20Sans%20Medium/0-255.pbf`,
    ]);
  });

  it('refuses a span above the upper boundary with glyph_span_invalid and fetches nothing', async () => {
    const fetcher = stubFetcher(() => stubResponse(new Uint8Array([1])));
    await expect(
      glyphReadiness(ORIGIN, { spans: ['65536-65791.pbf'], fetcher }),
    ).resolves.toBe('glyph_span_invalid');
    expect(fetcher).not.toHaveBeenCalled();
  });
});
