/** Closed source geometry, validated without repair, simplification or rounding. */
export type Position = readonly [number, number];
export type PolygonCoordinates = readonly (readonly Position[])[];
export type SourceGeometry =
  | { type: 'Point'; coordinates: Position }
  | { type: 'LineString'; coordinates: readonly Position[] }
  | { type: 'Polygon'; coordinates: PolygonCoordinates }
  | { type: 'MultiPolygon'; coordinates: readonly PolygonCoordinates[] };

function orientationSign(ring: readonly Position[]): -1 | 0 | 1 {
  const view = new DataView(new ArrayBuffer(8));
  function binary(value: number): readonly [bigint, number] {
    view.setFloat64(0, value);
    const bits = view.getBigUint64(0);
    const biasedExponent = Number((bits >> 52n) & 0x7ffn);
    const fraction = bits & 0xfffffffffffffn;
    const mantissa = biasedExponent === 0 ? fraction : (1n << 52n) | fraction;
    return [
      bits >> 63n === 0n ? mantissa : -mantissa,
      biasedExponent === 0 ? -1074 : biasedExponent - 1075,
    ];
  }
  const points = ring.map(([x, y]) => [binary(x), binary(y)] as const);
  let exponent = 0;
  let area = 0n;
  function addProduct(
    a: readonly [bigint, number],
    b: readonly [bigint, number],
    sign: bigint,
  ): void {
    const product = sign * a[0] * b[0];
    if (product === 0n) return;
    const productExponent = a[1] + b[1];
    // Keep every cross product at one common binary exponent, exactly.
    if (productExponent < exponent) {
      area <<= BigInt(exponent - productExponent);
      exponent = productExponent;
    }
    area += product << BigInt(productExponent - exponent);
  }
  for (let i = 1; i < points.length; i += 1) {
    const a = points[i - 1]!;
    const b = points[i]!;
    addProduct(a[0], b[1], 1n);
    addProduct(b[0], a[1], -1n);
  }
  return area > 0n ? 1 : area < 0n ? -1 : 0;
}

export function validSourceGeometry(raw: unknown): raw is SourceGeometry {
  if (
    !raw ||
    typeof raw !== 'object' ||
    Object.keys(raw).sort().join(',') !== 'coordinates,type'
  )
    return false;
  const geometry = raw as { type: unknown; coordinates: unknown };
  let count = 0;
  function position(point: unknown): point is Position {
    if (
      !Array.isArray(point) ||
      point.length !== 2 ||
      point.some((n) => typeof n !== 'number' || !Number.isFinite(n))
    )
      return false;
    count += 1;
    return (
      count <= 16384 &&
      point[0] >= -180 &&
      point[0] <= 180 &&
      point[1] >= -90 &&
      point[1] <= 90
    );
  }
  function path(points: unknown, minimum: number): points is Position[] {
    return (
      Array.isArray(points) &&
      points.length >= minimum &&
      points.length <= 4096 &&
      points.every(position)
    );
  }
  function polygon(rings: unknown): boolean {
    if (!Array.isArray(rings) || rings.length < 1 || rings.length > 64)
      return false;
    return rings.every((ring: unknown, index: number) => {
      if (!path(ring, 4)) return false;
      const start = ring[0]!;
      const end = ring[ring.length - 1]!;
      if (start[0] !== end[0] || start[1] !== end[1]) return false;
      const sign = orientationSign(ring);
      return index === 0 ? sign > 0 : sign < 0;
    });
  }
  switch (geometry.type) {
    case 'Point':
      return position(geometry.coordinates);
    case 'LineString':
      return path(geometry.coordinates, 2);
    case 'Polygon':
      return polygon(geometry.coordinates);
    case 'MultiPolygon':
      return (
        Array.isArray(geometry.coordinates) &&
        geometry.coordinates.length >= 1 &&
        geometry.coordinates.length <= 64 &&
        geometry.coordinates.every(polygon)
      );
    default:
      return false;
  }
}
