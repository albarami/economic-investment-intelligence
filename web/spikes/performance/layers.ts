import type { AccessorFunction, Color } from '@deck.gl/core';
import roadData from './road-data.json' with { type: 'json' };
import { roadLayer } from './road-layer';
import { drawnRoadCount, type Road } from './roads.mjs';
import { ROAD_COLORS, VOLUME_BANDS } from './config.mjs';
import type { Playback } from './road-playback';
import { H3HexagonLayer } from '@deck.gl/geo-layers';
import { ScatterplotLayer } from '@deck.gl/layers';
import { MapLibreOverlay } from '@deck.gl/maplibre';
import {
  GPUInitializationError,
  Map,
  setWorkerUrl,
  type Map as MapLibreMap,
} from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import {
  SCENE_CENTER,
  SCENE_ZOOM,
  WALL_CSS_HEIGHT,
  WALL_CSS_WIDTH,
} from './config.mjs';
import { placeParticles } from './geometry.mjs';
import { readUnmaskedRenderer } from './trace.mjs';

const LAND = '#c5d0c8';
const HEX_COLOR: [number, number, number, number] = [32, 96, 112, 230];
const PARTICLE_COLOR: [number, number, number, number] = [214, 92, 32, 240];
const EXTENT_SPAN = 1.2;
const PARTICLE_RADIUS = 4;

type Particle = {
  position: [number, number];
  originLng: number;
  originLat: number;
  destLng: number;
  destLat: number;
  phase: number;
};

export type Scene = {
  canvas: HTMLCanvasElement;
  hexagonInstances: number;
  particleInstances: number;
  roadInstances: number;
  roadDashEnabled: boolean;
  roads: Road[];
  roadSnapshot: () => {
    hour: number;
    nextHour: number;
    blend: number;
    bands: string[];
    nextBands: string[];
    trigger: number;
    stableData: boolean;
  };
  step: (elapsed: number, bearing: number, freeze: boolean) => void;
  bearing: () => number;
  renderer: () => string;
  sample: () => { hex: boolean; particle: boolean; road: boolean };
  onContextLost: (notify: () => void) => void;
};

let workerConfigured = false;

function configureWorker(): void {
  if (workerConfigured) return;
  setWorkerUrl(workerUrl);
  workerConfigured = true;
}

function extentRing(): [number, number][] {
  const [lng, lat] = SCENE_CENTER;
  const west = lng - EXTENT_SPAN;
  const east = lng + EXTENT_SPAN;
  const south = lat - EXTENT_SPAN;
  const north = lat + EXTENT_SPAN;
  return [
    [west, south],
    [east, south],
    [east, north],
    [west, north],
    [west, south],
  ];
}

function whenIdle(map: MapLibreMap): Promise<void> {
  return new Promise((resolve, reject) => {
    const fail = (event: { error?: unknown }) => {
      map.off('idle', succeed);
      const reason = event.error;
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

function countLayers(
  hexLayer: {
    props: { visible?: boolean };
    getNumInstances: () => number;
    getSubLayers?: () => { getNumInstances: () => number }[];
  },
  particleLayer: {
    props: { visible?: boolean };
    getNumInstances: () => number;
    getSubLayers?: () => { getNumInstances: () => number }[];
  },
): { hexagonInstances: number; particleInstances: number } {
  return {
    hexagonInstances: drawnCount(hexLayer, hexLayer.getSubLayers?.() ?? []),
    particleInstances: drawnCount(
      particleLayer,
      particleLayer.getSubLayers?.() ?? [],
    ),
  };
}

function drawnCount(
  layer: { props: { visible?: boolean }; getNumInstances: () => number },
  sublayers: { getNumInstances: () => number }[],
): number {
  if (layer.props.visible === false) return 0;
  if (sublayers.length === 0) return layer.getNumInstances();
  let total = 0;
  for (const sublayer of sublayers) total += sublayer.getNumInstances();
  return total;
}

function pixelKind(red: number, green: number, blue: number): string {
  // Opaque road interiors must match a stored band colour exactly.
  if (
    ROAD_COLORS.some(
      (color) => color[0] === red && color[1] === green && color[2] === blue,
    )
  )
    return 'road';
  if (red > 160 && green < 150 && blue < 120) return 'particle';
  if (blue > red + 20 && green > red && blue < 190) return 'hex';
  return 'other';
}

export async function mountScene(input: {
  container: HTMLElement;
  cap: number;
  cells: string[];
  particles: Particle[];
  showHexagons: boolean;
  showParticles: boolean;
  roads?: Road[];
  playback?: Playback;
  plant?: string;
}): Promise<Scene> {
  configureWorker();
  const map = new Map({
    container: input.container,
    style: {
      version: 8,
      name: 'Synthetic extent',
      sources: {
        extent: {
          type: 'geojson',
          data: {
            type: 'Feature',
            properties: {},
            geometry: { type: 'Polygon', coordinates: [extentRing()] },
          },
        },
      },
      layers: [
        {
          id: 'extent',
          type: 'fill',
          source: 'extent',
          paint: { 'fill-color': LAND },
        },
      ],
    },
    center: SCENE_CENTER,
    zoom: SCENE_ZOOM,
    bearing: 0,
    pitch: 0,
    interactive: false,
    attributionControl: false,
    maplibreLogo: false,
    fadeDuration: 0,
    pixelRatio: input.cap,
    canvasContextAttributes: {
      preserveDrawingBuffer: true,
      contextType: 'webgl2',
    },
  });
  const cells = input.cells;
  const particles = input.particles;
  let roadLayers: ReturnType<typeof roadLayer>[] = [];
  const build = (nextTick: number) => {
    const hexLayer = new H3HexagonLayer<string>({
      id: 'synthetic-hexagons',
      data: cells,
      highPrecision: false,
      extruded: false,
      filled: true,
      stroked: false,
      coverage: 1,
      getHexagon: (cell) => cell,
      getFillColor: HEX_COLOR,
      visible: input.showHexagons,
    });
    const particleLayer = new ScatterplotLayer<Particle>({
      id: 'synthetic-particles',
      data: particles,
      visible: input.showParticles,
      radiusUnits: 'pixels',
      getRadius: PARTICLE_RADIUS,
      getPosition: (particle) => particle.position,
      getFillColor: PARTICLE_COLOR,
      updateTriggers: { getPosition: nextTick },
    });
    if (input.roads && input.playback) {
      const state = input.playback.state;
      // Two opacity endpoints share one immutable payload and alternate slots.
      roadLayers = [
        roadLayer(
          input.roads,
          roadData.hours[state.index]!,
          1,
          state.index % 2,
          input.plant ?? '',
        ),
      ];
      roadLayers.push(
        roadLayer(
          input.roads,
          roadData.hours[state.next]!,
          state.blend,
          (state.index + 1) % 2,
          input.plant ?? '',
        ),
      );
    }
    return [hexLayer, particleLayer, ...roadLayers] as const;
  };
  let tick = 0;
  const overlay = new MapLibreOverlay({
    interleaved: true,
    layers: [...build(tick)],
  });
  map.addControl(overlay);
  await whenIdle(map);
  const current = build(tick);
  overlay.setProps({ layers: [...current] });
  await whenIdle(map);
  const canvas = map.getCanvas();
  const counts = countLayers(current[0], current[1]);
  return {
    canvas,
    hexagonInstances: counts.hexagonInstances,
    particleInstances: counts.particleInstances,
    roadInstances: roadLayers[0] ? drawnRoadCount(roadLayers[0]) : 0,
    roadDashEnabled: roadLayers[0]?.props.extensions?.length === 1,
    roads: input.roads ?? [],
    roadSnapshot: () => {
      const state = input.playback!.state;
      const hour = roadData.hours[state.index]!;
      const nextHour = roadData.hours[state.next]!;
      // Read the actual accessor and update trigger held by the layer.
      const layer = roadLayers[0]!;
      const sample = [
        ...(input.roads ?? []).slice(0, roadData.roads.links.length * 2),
        ...(input.roads ?? []).slice(-roadData.roads.links.length),
      ];
      const heldBands = (held: typeof layer) =>
        sample.map((road) => {
          const color = (held.props.getColor as AccessorFunction<Road, Color>)(
            road,
            { index: sample.indexOf(road), data: input.roads!, target: [] },
          );
          return VOLUME_BANDS[
            ROAD_COLORS.findIndex((candidate) =>
              candidate.every((value, index) => value === color[index]),
            )
          ]!;
        });
      return {
        hour,
        nextHour,
        blend: state.blend,
        bands: heldBands(layer),
        nextBands: heldBands(roadLayers[1] ?? layer),
        trigger: layer.props.updateTriggers!.getColor as number,
        stableData: roadLayers.every((held) => held.props.data === input.roads),
      };
    },
    bearing: () => map.getBearing(),
    renderer: () => readUnmaskedRenderer(canvas.getContext('webgl2')),
    step: (elapsed, bearing, freeze) => {
      if (!freeze) placeParticles(input.particles, elapsed);
      tick = elapsed;
      map.jumpTo({
        center: SCENE_CENTER,
        zoom: SCENE_ZOOM,
        bearing,
        pitch: 0,
      });
      overlay.setProps({ layers: [...build(tick)] });
    },
    sample: () => sample(canvas),
    onContextLost: (notify) => {
      canvas.addEventListener('webglcontextlost', (event) => {
        event.preventDefault();
        notify();
      });
    },
  };
}

function sample(canvas: HTMLCanvasElement): {
  hex: boolean;
  particle: boolean;
  road: boolean;
} {
  const context = canvas.getContext('webgl2');
  if (!context) return { hex: false, particle: false, road: false };
  const pixel = new Uint8Array(4);
  let hex = false;
  let particle = false;
  let road = false;
  const columns = 16;
  const rows = 16;
  for (let row = 0; row < rows; row += 1) {
    for (let column = 0; column < columns; column += 1) {
      const x = Math.floor(((column + 0.5) * canvas.width) / columns);
      const y = Math.floor(((row + 0.5) * canvas.height) / rows);
      context.readPixels(
        x,
        y,
        1,
        1,
        context.RGBA,
        context.UNSIGNED_BYTE,
        pixel,
      );
      const kind = pixelKind(pixel[0] ?? 0, pixel[1] ?? 0, pixel[2] ?? 0);
      if (kind === 'road') road = true;
      if (kind === 'hex') hex = true;
      if (kind === 'particle') particle = true;
    }
  }
  return { hex, particle, road };
}

export function webglFailure(error: unknown): string {
  if (error instanceof GPUInitializationError) return 'webgl2-unavailable';
  return error instanceof Error ? error.message : 'map failed';
}

export const WALL = { width: WALL_CSS_WIDTH, height: WALL_CSS_HEIGHT };
