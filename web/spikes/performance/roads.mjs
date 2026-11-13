import { random } from './geometry.mjs';
import {
  SEED,
  SCENE_CENTER,
  ROAD_EXTENT,
  ROAD_SEGMENT,
  VOLUME_BANDS,
  HOUR_HOLD_MS,
  SCENE_MS,
} from './config.mjs';

export function generateRoads(data, count) {
  const nodes = new Map(
    data.roads.nodes.map((node) => [
      node.id,
      [Number(node.lon), Number(node.lat)],
    ]),
  );
  const fixture = data.roads.links.map((link) => ({
    path: [nodes.get(link.source), nodes.get(link.target)],
    fixtureLink: link.link_id,
    roadClass: link.road_class,
    provenance: data.header.provenance,
    bands: Object.fromEntries(
      data.rows
        .filter((row) => row.link_id === link.link_id)
        .map((row) => [row.hour, row.volume_band]),
    ),
  }));
  const result = [...fixture];
  const next = random(SEED);
  for (let index = 0; index < count; index++) {
    const link = fixture[index % fixture.length];
    const lng =
      SCENE_CENTER[0] + (next() * 2 - 1) * (ROAD_EXTENT - ROAD_SEGMENT);
    const lat =
      SCENE_CENTER[1] + (next() * 2 - 1) * (ROAD_EXTENT - ROAD_SEGMENT);
    const angle = next() * Math.PI * 2;
    result.push({
      ...link,
      path: [
        [lng, lat],
        [
          lng + Math.cos(angle) * ROAD_SEGMENT,
          lat + Math.sin(angle) * ROAD_SEGMENT,
        ],
      ],
    });
  }
  return result;
}
export function bandAt(road, hour) {
  return road.bands[hour] ?? VOLUME_BANDS[0];
}
export function bandsAt(roads, hour) {
  return roads.map((road) => bandAt(road, hour));
}

/** Opacity alone blends two stored states; no band, width or colour tween. */
export function playbackState(hours, elapsed) {
  const index = Math.min(
    Math.floor(elapsed / (HOUR_HOLD_MS + SCENE_MS)),
    hours.length - 1,
  );
  if (index === hours.length - 1)
    return { index, next: index, blend: 0, ended: true };
  const phase = elapsed % (HOUR_HOLD_MS + SCENE_MS);
  if (phase <= HOUR_HOLD_MS)
    return { index, next: index, blend: 0, ended: false };
  return {
    index,
    next: index + 1,
    blend: (phase - HOUR_HOLD_MS) / SCENE_MS,
    ended: false,
  };
}

/** Count rendered links, excluding PathLayer's invalid terminal padding. */
export function drawnRoadCount(layer) {
  if (layer.props.visible === false) return 0;
  const tessellator = layer.state.pathTesselator;
  let count = 0;
  for (let index = 0; index < tessellator.vertexStarts.length - 1; index++) {
    if (tessellator.getPathSegmentIndices(index).length > 0) count++;
  }
  return count;
}
