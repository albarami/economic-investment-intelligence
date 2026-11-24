// S3-T26 A5 fix round 2 (F1): decodeAreaOutline returns null for every
// unreadable outline. Each negative changes one input of a valid outline; the
// body is sent as raw text so that 1e999 parses to a non-finite number.
import { describe, expect, it } from 'vitest';
import {
  decodeAreaOutline,
  readableOutline,
  type AreaOutline,
} from '../../src/api/areas';

const square = [
  [0, 0],
  [0, 1],
  [1, 1],
  [0, 0],
];
const polygon = { type: 'Polygon', coordinates: [square] };
const circle = { type: 'Circle', coordinates: [51.5, 25.3], radius_m: 500 };

function answer(outline: string, areaId = 'INVENTED-wider') {
  const body =
    '{"tool":"make_area","call_id":"INVENTED-call","release_id":"INVENTED-release",' +
    '"engine":"embedded","status":"OK","blocks":[],"facts":[],"caveat_keys":[],' +
    `"payload":{"area_id":"${areaId}","outline":${outline},"record":{"anchor_cell":null,` +
    '"traffic":"free_flow","shape":"walk"},"units":{},"snap_report":null,' +
    '"point_feature_ids":null}}';
  return () => Promise.resolve(new Response(body));
}

const decode = (outline: string) =>
  decodeAreaOutline('INVENTED-wider', answer(outline));

describe('decodeAreaOutline readable outlines', () => {
  it.each([
    ['a closed polygon ring', polygon],
    ['a polygon with a hole', { ...polygon, coordinates: [square, square] }],
    ['a circle', circle],
  ])('accepts %s', async (_name, outline) => {
    expect(await decode(JSON.stringify(outline))).toEqual(outline);
  });
});

describe('decodeAreaOutline unreadable outlines', () => {
  const ring = (points: string) =>
    `{"type":"Polygon","coordinates":[${points}]}`;
  const closed = (first: string) => `[${first},[0,1],[1,1],${first}]`;
  it.each([
    ['an empty polygon', '{"type":"Polygon","coordinates":[]}'],
    ['an empty ring', ring('[]')],
    ['a short ring of three positions', ring('[[0,0],[0,1],[0,0]]')],
    ['an open ring', ring('[[0,0],[0,1],[1,1],[1,0]]')],
    [
      'a closed ring of one repeated position',
      ring('[[0,0],[0,0],[0,0],[0,0]]'),
    ],
    ['a closed ring on one line', ring('[[0,0],[0,1],[0,2],[0,0]]')],
    ['a ring that is not a list', ring('"INVENTED"')],
    ['a position that is not a list', ring('[[0,0],7,[1,1],[0,0]]')],
    ['a position of three numbers', ring(closed('[0,0,0]'))],
    ['a position of one number', ring(closed('[0]'))],
    ['a text coordinate', ring(closed('["0",0]'))],
    ['a non-finite longitude', ring(closed('[1e999,0]'))],
    ['a non-finite latitude', ring(closed('[0,-1e999]'))],
    ['a longitude off the globe', ring(closed('[181,0]'))],
    ['a latitude off the globe', ring(closed('[0,91]'))],
    [
      'a second ring that is short',
      `{"type":"Polygon","coordinates":[${JSON.stringify(square)},[[0,0]]]}`,
    ],
    [
      'a non-finite circle longitude',
      '{"type":"Circle","coordinates":[1e999,25.3],"radius_m":500}',
    ],
    [
      'a non-finite circle latitude',
      '{"type":"Circle","coordinates":[51.5,1e999],"radius_m":500}',
    ],
    [
      'a circle centre off the globe',
      '{"type":"Circle","coordinates":[51.5,95],"radius_m":500}',
    ],
    [
      'a circle centre of three numbers',
      '{"type":"Circle","coordinates":[51.5,25.3,0],"radius_m":500}',
    ],
    [
      'a non-finite circle radius',
      '{"type":"Circle","coordinates":[51.5,25.3],"radius_m":1e999}',
    ],
    [
      'a zero circle radius',
      '{"type":"Circle","coordinates":[51.5,25.3],"radius_m":0}',
    ],
    [
      'a negative circle radius',
      '{"type":"Circle","coordinates":[51.5,25.3],"radius_m":-500}',
    ],
  ])('returns null for %s', async (_name, outline) => {
    expect(await decode(outline)).toBeNull();
  });
});

// Exhaustive oracle over a small closed domain: every ring of zero to five
// positions drawn from valid, non-finite and off-globe positions, open or
// closed, enclosing some area or none. The oracle is written apart from the
// decoder; it measures area by the trapezoid sum, not the decoder's shoelace.
function trapezoidArea(items: string[]): number {
  const points = items.map((item) => JSON.parse(item) as number[]);
  let sum = 0;
  for (let i = 0; i + 1 < points.length; i += 1)
    sum +=
      (points[i + 1][0] - points[i][0]) * (points[i + 1][1] + points[i][1]);
  return sum;
}
describe('decodeAreaOutline ring oracle', () => {
  const positions = ['[0,0]', '[0,1]', '[1,1]', '[1e999,0]', '[0,91]', '[0]'];
  const valid = new Set(['[0,0]', '[0,1]', '[1,1]']);
  const rings: string[][] = [[]];
  for (let length = 1; length <= 5; length += 1)
    for (const prefix of rings.filter((item) => item.length === length - 1))
      for (const position of positions) rings.push([...prefix, position]);
  it('agrees with the oracle on every ring of the domain', async () => {
    let readable = 0;
    for (const items of rings) {
      const expected =
        items.length >= 4 &&
        items.every((item) => valid.has(item)) &&
        items[0] === items.at(-1) &&
        trapezoidArea(items) !== 0;
      const got = await decode(
        `{"type":"Polygon","coordinates":[[${items.join(',')}]]}`,
      );
      expect([items.join(','), got !== null]).toEqual([
        items.join(','),
        expected,
      ]);
      if (expected) readable += 1;
    }
    expect(readable).toBeGreaterThan(0);
    expect(rings.length).toBe(1 + 6 + 36 + 216 + 1296 + 7776);
  });
});

// readableOutline is also called outside the decoder's catch (the Stage's
// drawable-ring gate), so it must refuse without throwing.
describe('readableOutline outside the decoder', () => {
  it.each([
    ['a ring that is text', ['INVENTEDRING']],
    ['a null position', [[null, [0, 1], [1, 1], null]]],
  ])('refuses %s without throwing', (_name, coordinates) => {
    const outline = { type: 'Polygon', coordinates } as unknown as AreaOutline;
    expect(readableOutline(outline)).toBe(false);
  });
});
