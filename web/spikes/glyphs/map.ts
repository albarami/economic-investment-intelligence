import { MapLibreOverlay } from '@deck.gl/maplibre';
import { PolygonLayer } from '@deck.gl/layers';
import {
  Map,
  setWorkerUrl,
  type Map as MapLibreMap,
  type MapOptions,
} from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import {
  LABEL_LAYER_ID,
  SCENE_CENTER,
  SCENE_ZOOM,
  OVERLAP_ZOOM,
  firstLabelCenter,
  fixture,
  hexagonRing,
  type Fixture,
  type Lang,
} from './fixtures';
import { ARABIC_FACE, LATIN_FACE, fontFaces, type FontFaceMap } from './fonts';

const LAND_COLOR = '#c5d0c8';
const BUILDING_COLOR = '#7e8c96';
const LABEL_COLOR = '#1c2430';
const HALO_COLOR = '#f7f4ee';
const HALO_WIDTH = 2;
const LABEL_SIZE = 16;
const HEX_FILL: [number, number, number, number] = [32, 96, 112, 210];
const DECK_GROUP_PREFIX = 'deck-maplibre-layer-group';

type HexDatum = { polygon: [number, number][] };
type HexExtra = { beforeId: string };

let workerConfigured = false;

function configureWorker(): void {
  if (workerConfigured) return;
  setWorkerUrl(workerUrl);
  workerConfigured = true;
}

type StyleObject = Exclude<NonNullable<MapOptions['style']>, string>;

function textFont(lang: Lang): [string, string] {
  return lang === 'ar' ? [ARABIC_FACE, LATIN_FACE] : [LATIN_FACE, ARABIC_FACE];
}

function kindFilter(kind: string): ['==', string, string] {
  return ['==', 'kind', kind];
}

function styleFor(data: Fixture, faces: FontFaceMap, lang: Lang): StyleObject {
  const layers: StyleObject['layers'] = [
    {
      id: 'land',
      type: 'fill',
      source: 'fixture',
      filter: kindFilter('land'),
      paint: { 'fill-color': LAND_COLOR },
    },
    {
      id: 'buildings',
      type: 'fill',
      source: 'fixture',
      filter: kindFilter('building'),
      paint: { 'fill-color': BUILDING_COLOR },
    },
    {
      id: LABEL_LAYER_ID,
      type: 'symbol',
      source: 'fixture',
      filter: kindFilter('label'),
      layout: {
        'text-field': ['get', 'label'],
        'text-font': textFont(lang),
        'text-size': LABEL_SIZE,
        'text-letter-spacing': 0,
        'text-anchor': 'center',
        'text-allow-overlap': true,
        'text-ignore-placement': true,
      },
      paint: {
        'text-color': LABEL_COLOR,
        'text-halo-color': HALO_COLOR,
        'text-halo-width': HALO_WIDTH,
        'text-halo-blur': 0,
      },
    },
  ];
  return {
    version: 8,
    name: 'Synthetic fixture',
    'font-faces': faces,
    sources: {
      fixture: { type: 'geojson', data: data.collection },
    },
    layers,
  };
}

function whenIdle(map: MapLibreMap): Promise<void> {
  return new Promise((resolve, reject) => {
    const fail = (event: { error?: unknown }) => {
      const reason = event.error;
      map.off('idle', succeed);
      reject(reason instanceof Error ? reason : new Error('map failed'));
    };
    const succeed = () => {
      map.off('error', fail);
      resolve();
    };
    map.once('error', fail);
    map.once('idle', succeed);
  });
}

export type MountResult = {
  labelNames: string[];
  fontFaceFamilies: string[];
  fontFacesReady: boolean;
  interleaved: boolean;
  overlayCount: number;
  webgpu: boolean;
  firstLabelId: string;
  beforeId: string | null;
  layerIds: string[];
  featureKey: string;
  bearing: number;
};

export async function mountMap(input: {
  container: HTMLElement;
  lang: Lang;
  omitArabic: boolean;
  overlap: boolean;
}): Promise<MountResult> {
  configureWorker();
  const faces = fontFaces(input.omitArabic);
  const data = fixture(input.lang);
  const center = input.overlap ? firstLabelCenter() : SCENE_CENTER;
  const map = new Map({
    container: input.container,
    style: styleFor(data, faces, input.lang),
    center,
    zoom: input.overlap ? OVERLAP_ZOOM : SCENE_ZOOM,
    bearing: 0,
    pitch: 0,
    interactive: false,
    attributionControl: false,
    maplibreLogo: false,
    fadeDuration: 0,
    pixelRatio: 1,
    canvasContextAttributes: {
      preserveDrawingBuffer: true,
      contextType: 'webgl2',
    },
    localIdeographFontFamily: false,
  });
  const hexagon = new PolygonLayer<HexDatum, HexExtra>({
    id: 'synthetic-hexagons',
    data: [{ polygon: hexagonRing(firstLabelCenter()) }],
    filled: true,
    stroked: false,
    extruded: false,
    getPolygon: (datum) => datum.polygon,
    getFillColor: HEX_FILL,
    beforeId: LABEL_LAYER_ID,
  });
  const overlay = new MapLibreOverlay({ interleaved: true, layers: [hexagon] });
  map.addControl(overlay);
  await whenIdle(map);
  overlay.setProps({ layers: [hexagon] });
  await whenIdle(map);
  const layerIds = map.getLayersOrder();
  const labelIndex = layerIds.indexOf(LABEL_LAYER_ID);
  const deckIndexes = layerIds
    .map((id, index) => (id.startsWith(DECK_GROUP_PREFIX) ? index : -1))
    .filter((index) => index >= 0);
  const declared = map.getFontFaces() ?? {};
  const interleaved =
    deckIndexes.length === 1 && labelIndex > (deckIndexes[0] ?? -1);
  if (!interleaved) {
    throw new Error(
      `hexagons are not under the labels: ${layerIds.join(',')} styleLoaded=${String(map.isStyleLoaded())}`,
    );
  }
  return {
    labelNames: data.labelNames,
    fontFaceFamilies: Object.keys(declared),
    fontFacesReady: ARABIC_FACE in declared && LATIN_FACE in declared,
    interleaved,
    overlayCount: deckIndexes.length,
    webgpu: false,
    firstLabelId: LABEL_LAYER_ID,
    beforeId: hexagon.props.beforeId ?? null,
    layerIds,
    featureKey: data.featureKey,
    bearing: map.getBearing(),
  };
}
