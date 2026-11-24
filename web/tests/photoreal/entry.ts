import { Map, setWorkerUrl } from 'maplibre-gl';
import worker from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import { MapLibreOverlay } from '@deck.gl/maplibre';
import { ScatterplotLayer, PathLayer } from '@deck.gl/layers';
import { attachClock } from '../../src/stage/layers/overlay';
import { modeRenderer } from '../../src/stage/mode-renderer';
setWorkerUrl(worker);
const open = {
  version: 8 as const,
  sources: {
    'invented-building': {
      type: 'geojson',
      data: {
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            properties: {},
            geometry: {
              type: 'Polygon',
              coordinates: [
                [
                  [0, 0],
                  [0.001, 0],
                  [0.001, 0.001],
                  [0, 0],
                ],
              ],
            },
          },
        ],
      },
    },
  },
  layers: [
    {
      id: 'open-buildings',
      type: 'fill-extrusion',
      source: 'invented-building',
      paint: { 'fill-extrusion-height': 10 },
    },
    {
      id: 'open-base',
      type: 'background' as const,
      paint: { 'background-color': '#111111' },
    },
  ],
};
const map = new Map({
  container: 'map',
  style: open,
  center: [0, 0],
  zoom: 17,
  pitch: 45,
  attributionControl: false,
  maplibreLogo: false,
});
const layers = [
  new ScatterplotLayer({
    id: 'invented-context',
    data: [{ position: [-0.001, 0.001] }],
    getPosition: (d) => d.position,
    getRadius: 10,
  }),
  new ScatterplotLayer({
    id: 'invented-hero',
    data: [{ position: [0.001, 0.001] }],
    getPosition: (d) => d.position,
    getRadius: 10,
  }),
  new PathLayer({
    id: 'invented-area',
    data: [
      {
        path: [
          [0, 0],
          [0.001, 0],
          [0.001, 0.001],
        ],
      },
    ],
    getPath: (d) => d.path,
    getWidth: 2,
  }),
];
const overlay = attachClock(
  new MapLibreOverlay({ interleaved: true, layers }),
  layers,
);
map.addControl(overlay);
const failures: string[] = [];
// A held page does not return to the open mode after a failure, so that a
// test can see what the failed mode removes by itself.
let held = false;
const renderer = modeRenderer(
  map,
  open,
  () => {
    failures.push('fixed failure');
    if (!held) void renderer.setMode('open', () => {});
  },
  (layer) => overlay.setPhotoreal(layer),
);
const credit = (text: string) => {
  document.getElementById('credit')!.textContent = text;
};
const ready = new Promise<void>((resolve) => map.on('load', () => resolve()));
Object.assign(globalThis, {
  inventedNative: {
    map,
    overlay,
    ready,
    failures,
    hold: () => {
      held = true;
    },
    setMode: (mode: 'open' | 'photoreal' | 'satellite') =>
      renderer.setMode(mode, credit),
    clock: () => overlay.setClock(0),
    payload: () => overlay.setPayloadLayers([...layers]),
    remove: () => {
      renderer.remove();
      map.remove();
    },
  },
});
