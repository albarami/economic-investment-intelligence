/** Invented GPU picking proof; production never imports this harness. */
import { Deck, WebMercatorViewport } from '@deck.gl/core';
import { overlayFor } from '../../src/stage/layers/overlay';
import { routeRegistry } from '../fixtures/public-route-registry';
import responses from '../fixtures/public-layer-responses.json';
import land from '../fixtures/land-price-layer.json';
import { geometryScene, sourceGeometries } from '../fixtures/source-geometries';
import type { Fact } from '../../src/facts/types';
import type { LayerPayload } from '../../src/stage/layers/payload';
const kind = new URLSearchParams(location.search).get('kind');
const geometry = sourceGeometries.find((g) => g.type === kind)!;
const body = geometryScene(geometry);
if (kind === 'Polygon' || kind === 'MultiPolygon') {
  Object.assign(body, structuredClone(land));
  for (const feature of body.payload.layers[0]!.features) {
    delete feature.ring;
    feature.geometry = geometry;
  }
}
if (kind === 'Point' || kind === 'LineString') {
  const replacement = structuredClone(
    responses[kind === 'Point' ? 'public_places' : 'rail_plan'],
  ) as unknown as { facts: Fact[]; payload: LayerPayload };
  Object.assign(body, replacement);
  const feature = body.payload.layers[0]!.features[0]!;
  delete feature.position;
  delete feature.path;
  delete feature.ring;
  feature.geometry = geometry;
  feature.geometry_kind = kind === 'Point' ? 'point' : 'line';
}
const overlay = overlayFor(body.payload, null, routeRegistry(body));
const initialViewState = {
  longitude: 2.5,
  latitude: 1.5,
  zoom: 6,
  pitch: 0,
  bearing: 0,
};
const deck = new Deck({
  parent: document.getElementById('canvas')!,
  initialViewState,
  controller: false,
  layers: overlay._props.layers,
  onAfterRender: () => {
    document.body.dataset.ready = 'true';
  },
});
Object.assign(window, {
  pickSource(lon: number, lat: number) {
    const view = new WebMercatorViewport({
      width: innerWidth,
      height: innerHeight,
      ...initialViewState,
    });
    const [x, y] = view.project([lon, lat]);
    return deck.pickObject({ x: x!, y: y!, radius: 2 })?.object !== undefined;
  },
});
