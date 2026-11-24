/** Render the server's exact-shape Public point membership; no browser selection geometry. */
import type { AreaOutline, PublicPointIds } from '../../api/areas';
import type { LayerPayload } from './payload';
import { layerEntry } from './registry';

const POINT_LAYERS = new Set([
  'public_places',
  'commercial_points',
  'address_points',
  'landmarks',
  'fdi_projects',
]);

export function filterPublicToOutline(
  payload: LayerPayload,
  _outline: AreaOutline,
  membership: PublicPointIds | null,
): LayerPayload {
  return {
    ...payload,
    layers: payload.layers.map((layer) => {
      const entry = layerEntry(layer.key);
      if (
        entry?.className !== 'Public' &&
        entry?.className !== 'Frame (Public)'
      )
        return layer;
      if (!POINT_LAYERS.has(layer.key)) return layer;
      const ids = new Set(membership?.[layer.key] ?? []);
      return {
        ...layer,
        // Lines, polygons and statistics keep their supplied geography (DAT-147).
        features: layer.features.filter(
          (feature) =>
            feature.geometry_kind !== 'point' || ids.has(feature.feature_id),
        ),
      };
    }),
  };
}

/** Screen ring for a circle make_area returned. Coordinates are not shown. */
export function circleBoundary(
  centre: readonly [number, number],
  radiusM: number,
): readonly (readonly [number, number])[] {
  const lat1 = toRad(centre[1]);
  const lon1 = toRad(centre[0]);
  const delta = radiusM / EARTH_RADIUS_M;
  const points: [number, number][] = [];
  for (let index = 0; index <= CIRCLE_EDGE_COUNT; index += 1) {
    const bearing = (2 * Math.PI * index) / CIRCLE_EDGE_COUNT;
    const lat2 = Math.asin(
      Math.sin(lat1) * Math.cos(delta) +
        Math.cos(lat1) * Math.sin(delta) * Math.cos(bearing),
    );
    const lon2 =
      lon1 +
      Math.atan2(
        Math.sin(bearing) * Math.sin(delta) * Math.cos(lat1),
        Math.cos(delta) - Math.sin(lat1) * Math.sin(lat2),
      );
    points.push([toDeg(lon2), toDeg(lat2)]);
  }
  return points;
}

/** Mean radius used by `eii_core.shapes.great_circle_m`. Not displayed. */
const EARTH_RADIUS_M = 6371008.8;
const CIRCLE_EDGE_COUNT = 48;

function toRad(degrees: number): number {
  return (degrees * Math.PI) / 180;
}

function toDeg(radians: number): number {
  return (radians * 180) / Math.PI;
}
