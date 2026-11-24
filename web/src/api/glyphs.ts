/**
 * Map-glyph readiness. The closed sets mirror the server's: one stack,
 * its aligned 256-codepoint ranges and the glyph MIME type. The bundled
 * interface fonts stay the only copy of each face; readiness only proves
 * the served ranges before the first story frame.
 */
import { refusalState, type RefusalState } from './refusal';

export const GLYPH_STACKS = ['Noto Sans Medium'] as const;

export type GlyphStack = (typeof GLYPH_STACKS)[number];
export const READINESS_STACK: GlyphStack = GLYPH_STACKS[0];
export const GLYPH_MIME = 'application/x-protobuf';

/** Closed set of ranges the mounted font stack holds (start, end). */
export const READINESS_RANGES: readonly (readonly [number, number])[] = [
  [0, 255],
  [1536, 1791],
  [1792, 2047],
  [8192, 8447],
  [64256, 64511],
  [64512, 64767],
  [65024, 65279],
  [65280, 65535],
];

export type GlyphRefusal =
  | 'glyph_stack_not_closed'
  | 'glyph_span_invalid'
  | 'glyph_status'
  | 'glyph_wrong_type'
  | 'glyph_empty'
  | 'glyph_network';

const SPAN = /^(0|[1-9][0-9]*)-(0|[1-9][0-9]*)\.pbf$/;

export function glyphUrl(
  origin: string,
  stack: string,
  span: string,
): string | null {
  if (!(GLYPH_STACKS as readonly string[]).includes(stack)) return null;
  const match = SPAN.exec(span);
  if (match === null) return null;
  const start = Number(match[1]);
  const end = Number(match[2]);
  if (start % 256 !== 0 || end !== start + 255 || start > 0xff00) return null;
  return `${origin}/fonts/${encodeURIComponent(stack)}/${span}`;
}

export interface GlyphReadinessOptions {
  stack?: string;
  spans?: string[];
  fetcher?: typeof fetch;
}

export async function glyphReadiness(
  origin: string,
  options: GlyphReadinessOptions = {},
): Promise<GlyphRefusal | null> {
  const {
    stack = READINESS_STACK,
    spans = defaultSpans(),
    fetcher = fetch,
  } = options;
  if (!(GLYPH_STACKS as readonly string[]).includes(stack))
    return 'glyph_stack_not_closed';
  for (const span of spans) {
    const url = glyphUrl(origin, stack, span);
    if (url === null) return 'glyph_span_invalid';
    let response: Response;
    try {
      response = await fetcher(url);
    } catch (error) {
      return networkRefusal(refusalState(error, 'stage.error'));
    }
    if (!response.ok) return 'glyph_status';
    const type = response.headers.get('content-type');
    if (type === null || type.split(';')[0]?.trim() !== GLYPH_MIME)
      return 'glyph_wrong_type';
    let body: ArrayBuffer;
    try {
      body = await response.arrayBuffer();
    } catch (error) {
      return networkRefusal(refusalState(error, 'stage.error'));
    }
    if (body.byteLength === 0) return 'glyph_empty';
  }
  return null;
}

/** A caught fault passes the closed projection; readiness keeps its closed code. */
function networkRefusal(state: RefusalState): GlyphRefusal {
  void state;
  return 'glyph_network';
}

function defaultSpans(): string[] {
  return READINESS_RANGES.map(([start, end]) => `${start}-${end}.pbf`);
}
