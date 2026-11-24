import { expect, it } from 'vitest';
import exactFixture from '../fixtures/source-geometry-exact.json';
import type {
  Position,
  SourceGeometry,
} from '../../src/stage/layers/source-geometry';
import {
  geometryScene,
  sourceGeometries,
  outer,
  hole,
  island,
} from '../fixtures/source-geometries';
import { routeRegistry } from '../fixtures/public-route-registry';
import { acceptPayload } from '../../src/stage/layers/refuse';
import { polygonRows } from '../../src/stage/layers/overlay';
import { validSourceGeometry } from '../../src/stage/layers/source-geometry';
import orientationCases from '../fixtures/source-orientation.json';

for (const fixture of orientationCases)
  it(`matches the backend for ${fixture.name} without changing coordinates`, () => {
    const geometry = structuredClone(fixture.geometry);
    expect(validSourceGeometry(geometry)).toBe(fixture.accepted);
    const body = geometryScene(geometry);
    const verdict = acceptPayload(body.payload, routeRegistry(body));
    expect(verdict.ok).toBe(fixture.accepted);
    if (fixture.accepted) {
      expect(
        polygonRows(body.payload.layers[0]!.features)[0]!.geometry,
      ).toEqual(fixture.geometry);
    } else {
      expect(verdict).toMatchObject({ code: 'source_geometry_invalid' });
    }
    expect(geometry).toEqual(fixture.geometry);
  });
for (const geometry of sourceGeometries)
  it(`accepts the closed ${geometry.type} coordinates unchanged`, () => {
    expect(validSourceGeometry(geometry)).toBe(true);
  });
for (const geometry of sourceGeometries.slice(2))
  it(`preserves every ${geometry.type} ring and part in deck data`, () => {
    const body = geometryScene(geometry);
    expect(acceptPayload(body.payload, routeRegistry(body)).ok).toBe(true);
    expect(polygonRows(body.payload.layers[0]!.features)[0]!.geometry).toEqual(
      geometry,
    );
  });
for (const geometry of [
  { type: 'Polygon', coordinates: [outer.slice(0, -1)] },
  { type: 'Polygon', coordinates: [outer.toReversed()] },
  { type: 'Polygon', coordinates: [outer, hole.toReversed()] },
  { type: 'Polygon', coordinates: [hole, outer] },
  { type: 'Polygon', coordinates: [] },
  { type: 'Polygon', coordinates: [outer], extra: true },
  { type: 'MultiPolygon', coordinates: [[outer], [island]], extra: true },
  { type: 'GeometryCollection', coordinates: [] },
  {
    type: 'Polygon',
    coordinates: [outer, ...Array.from({ length: 64 }, () => hole)],
  },
  {
    type: 'MultiPolygon',
    coordinates: Array.from({ length: 65 }, () => [outer]),
  },
  {
    type: 'Polygon',
    coordinates: [Array.from({ length: 4097 }, () => [0, 0])],
  },
  {
    type: 'MultiPolygon',
    coordinates: Array.from({ length: 64 }, () => [
      outer,
      ...Array.from({ length: 63 }, () => hole),
    ]),
  },
  {
    type: 'LineString',
    coordinates: Array.from({ length: 4097 }, () => [0, 0]),
  },
  { type: 'Point', coordinates: [0, 0, 0] },
  { type: 'Point', coordinates: [true, 0] },
  { type: 'Point', coordinates: [NaN, 0] },
  { type: 'Point', coordinates: [181, 0] },
  { type: 'Point', coordinates: [0, 91] },
])
  it(`refuses malformed or over-bound geometry ${JSON.stringify(geometry).slice(0, 70)}`, () => {
    expect(validSourceGeometry(geometry)).toBe(false);
    const body = geometryScene(geometry);
    expect(acceptPayload(body.payload, routeRegistry(body))).toMatchObject({
      ok: false,
      code: 'source_geometry_invalid',
    });
  });
it('refuses simultaneous geometry and legacy ring rather than choosing one', () => {
  const body = geometryScene(sourceGeometries[2]);
  body.payload.layers[0]!.features[0]!.ring = outer as [number, number][];
  expect(acceptPayload(body.payload, routeRegistry(body))).toMatchObject({
    ok: false,
    code: 'source_geometry_invalid',
  });
});

it('accepts the inclusive source bounds', () => {
  expect(
    validSourceGeometry({
      type: 'LineString',
      coordinates: Array.from({ length: 4096 }, () => [0, 0]),
    }),
  ).toBe(true);
  expect(
    validSourceGeometry({
      type: 'MultiPolygon',
      coordinates: Array.from({ length: 64 }, () => [outer]),
    }),
  ).toBe(true);
  expect(
    validSourceGeometry({
      type: 'Polygon',
      coordinates: [outer, ...Array.from({ length: 63 }, () => hole)],
    }),
  ).toBe(true);
});

type ExactCase = {
  name: string;
  geometry: SourceGeometry;
  sign: number;
  accepted: boolean;
};
const sharedCases = exactFixture.cases as unknown as ExactCase[];

function fixtureRing(geometry: SourceGeometry): readonly Position[] {
  if (geometry.type === 'Polygon') return geometry.coordinates[0]!;
  if (geometry.type === 'MultiPolygon') return geometry.coordinates[0]![0]!;
  throw new Error('fixture must contain polygon rings');
}

// Independent rational oracle: radix-two strings give integer numerators over
// a fixed denominator of 2**1074, rather than decoding IEEE-754 bit fields.
function rationalSign(ring: readonly Position[]): number {
  function numerator(value: number): bigint {
    const [whole, fraction = ''] = Math.abs(value).toString(2).split('.');
    const magnitude =
      BigInt(`0b${whole}${fraction}`) << BigInt(1074 - fraction.length);
    return value < 0 ? -magnitude : magnitude;
  }
  const points = ring.map(([x, y]) => [numerator(x), numerator(y)] as const);
  let numeratorSum = 0n;
  for (let i = 1; i < points.length; i += 1) {
    const a = points[i - 1]!;
    const b = points[i]!;
    numeratorSum += a[0] * b[1] - b[0] * a[1];
  }
  return numeratorSum > 0n ? 1 : numeratorSum < 0n ? -1 : 0;
}

for (const entry of sharedCases) {
  it(`shared exact orientation: ${entry.name}`, () => {
    const before = structuredClone(entry.geometry);
    expect(rationalSign(fixtureRing(entry.geometry))).toBe(entry.sign);
    expect(validSourceGeometry(entry.geometry)).toBe(entry.accepted);
    const body = geometryScene(entry.geometry);
    const result = acceptPayload(body.payload, routeRegistry(body));
    if (entry.accepted) {
      expect(result.ok).toBe(true);
      if (!result.ok) throw new Error(result.code);
      expect(result.draw.layers[0]!.features[0]!.geometry).toEqual(before);
      expect(result.draw.layers[0]!.features[0]!.geometry).toBe(entry.geometry);
    } else {
      expect(result).toMatchObject({
        ok: false,
        code: 'source_geometry_invalid',
      });
    }
    expect(entry.geometry).toEqual(before);
  });

  it(`shared exact hole orientation: ${entry.name}`, () => {
    const geometry = {
      type: 'Polygon',
      coordinates: [outer, fixtureRing(entry.geometry)],
    };
    expect(validSourceGeometry(geometry)).toBe(entry.sign < 0);
  });
}

it('the four precision regressions disagree with naive float orientation', () => {
  for (const entry of sharedCases.slice(0, 8).filter((_, i) => i % 2 === 0)) {
    const ring = fixtureRing(entry.geometry);
    const start = ring[0]!;
    let area = 0;
    for (let i = 1; i < ring.length; i += 1) {
      const a = ring[i - 1]!;
      const b = ring[i]!;
      area +=
        (a[0] - start[0]) * (b[1] - start[1]) -
        (b[0] - start[0]) * (a[1] - start[1]);
    }
    expect(Math.sign(area)).not.toBe(entry.sign);
  }
});

it('seeded finite rings match a BigInt rational orientation reference', () => {
  let state = exactFixture.seed;
  function next(): number {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return state >>> 0;
  }
  function coordinate(maxExponent: number): number {
    const exponents = [-1074, -1073, -1022, -1000, -500, -53, 0, maxExponent];
    const exponent = exponents[next() % exponents.length]!;
    const mantissa = (next() + 1) / 2 ** 32;
    return (next() % 2 === 0 ? -1 : 1) * mantissa * 2 ** exponent;
  }
  const rings: Position[][] = [
    [
      [0, 0],
      [Number.MIN_VALUE, 0],
      [0, Number.MIN_VALUE],
      [0, 0],
    ],
  ];
  for (let i = 0; i < 512; i += 1) {
    const points: Position[] = Array.from({ length: 3 + (next() % 10) }, () => [
      coordinate(7),
      coordinate(6),
    ]);
    rings.push([...points, points[0]!]);
  }
  for (const ring of rings) {
    const sign = rationalSign(ring);
    expect(validSourceGeometry({ type: 'Polygon', coordinates: [ring] })).toBe(
      sign > 0,
    );
    expect(
      validSourceGeometry({
        type: 'Polygon',
        coordinates: [ring.toReversed()],
      }),
    ).toBe(sign < 0);
    expect(
      validSourceGeometry({ type: 'Polygon', coordinates: [outer, ring] }),
    ).toBe(sign < 0);
  }
});
