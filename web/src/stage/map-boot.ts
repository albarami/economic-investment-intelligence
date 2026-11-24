import type { Layer } from '@deck.gl/core';
/**
 * MapLibre starts only when an extract address is injected.
 * Bundled worker and RTL plugin addresses; named imports.
 */
import {
  Map,
  LngLatBounds,
  addProtocol,
  setWorkerUrl,
  setRTLTextPlugin,
  type StyleSpecification,
} from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import rtlPluginUrl from '../../node_modules/@mapbox/mapbox-gl-rtl-text/dist/mapbox-gl-rtl-text.js?url';
import { Protocol } from 'pmtiles';
import type { AreaOutline } from '../api/areas';
import { circleBoundary } from './layers/area-filter';
import type { MapMode, ModeFailureReason } from './map-modes';
import { modeRenderer } from './mode-renderer';
import { overlayFor } from './layers/overlay';

import { restoreNamed, suspendNamed, type GestureBag } from './gestures';

export interface OverlayMount {
  setClock?(timestamp: number): void;
  getPayloadLayers?(): Layer[];
  setPayloadLayers?(layers: Layer[]): void;
  setPhotoreal?(layer: Layer | null): void;
  onAdd(map: Map): HTMLElement;
  onRemove(map: Map): void;
}

export interface MapPoint {
  x: number;
  y: number;
}

export interface MapLngLat {
  longitude: number;
  latitude: number;
}

/** Primitives only. No target and no map. */
export interface DrawingEvent {
  type: string;
  x: number;
  y: number;
  longitude: number;
  latitude: number;
  key: string;
}

export interface MapHandle {
  focusArea?(outline: AreaOutline): void;
  camera?(command: CameraCommand): void;
  cameraState?(): CameraState;
  restoreCamera?(view: CameraState): void;
  onModeError?(
    listener: (mode: MapMode, reason: ModeFailureReason) => void,
  ): () => void;
  setMode?(mode: MapMode, credit: (text: string) => void): Promise<void>;
  setClock?(timestamp: number): void;
  remove(): void;
  mountOverlay(overlay: OverlayMount): void;
  bind(type: string, listener: (event: DrawingEvent) => void): void;
  unbind(type: string, listener: (event: DrawingEvent) => void): void;
  project(lngLat: MapLngLat): MapPoint;
  unproject(point: MapPoint): MapLngLat;
  suspendGestures(): void;
  restoreGestures(): void;
  centre(): MapLngLat;
  /**
   * Camera `move` and map `resize`, named in the installed
   * maplibre-gl 6.17.0 typings (`MapEventType`). The listener
   * receives no event object and no map.
   */
  bindView(listener: () => void): void;
  unbindView(listener: () => void): void;
}

export type CameraCommand =
  'north' | 'south' | 'east' | 'west' | 'zoomIn' | 'zoomOut' | 'recentre';
export interface CameraState {
  center: [number, number];
  zoom: number;
  bearing: number;
  pitch: number;
}

export interface MapSurface {
  on(type: string, listener: (event: unknown) => void): void;
  off(type: string, listener: (event: unknown) => void): void;
  project(lngLat: { lng: number; lat: number }): MapPoint;
  unproject(point: MapPoint): { lng: number; lat: number };
  getCenter(): { lng: number; lat: number };
  remove(): void;
  dragPan: { disable(): void; enable(): void };
  scrollZoom: { disable(): void; enable(): void };
  boxZoom: { disable(): void; enable(): void };
  dragRotate: { disable(): void; enable(): void };
  doubleClickZoom: { disable(): void; enable(): void };
  touchZoomRotate: { disable(): void; enable(): void };
  touchPitch: { disable(): void; enable(): void };
  keyboard: { disable(): void; enable(): void };
}

let bootReady: Promise<void> | null = null;

/** Shared with the host scan: neither attribution nor the logo control is mounted. */
export const MAP_OPTIONS = {
  attributionControl: false,
  maplibreLogo: false,
} as const;

export async function startMap(
  container: HTMLElement,
  style: StyleSpecification,
): Promise<MapHandle> {
  if (!bootReady) {
    setWorkerUrl(workerUrl);
    const protocol = new Protocol();
    addProtocol('pmtiles', protocol.tile);
    // REFERENCE_NOTES: MapLibre S25–S26; retained by decision 0042 item 7.
    bootReady = setRTLTextPlugin(rtlPluginUrl, true);
  }
  await bootReady;
  const map = new Map({
    container,
    style,
    interactive: true,
    ...MAP_OPTIONS,
  });
  (globalThis as { eiiMap?: Map }).eiiMap = map;
  const initialCenter = map.getCenter();
  const home: CameraState = {
    center: [initialCenter.lng, initialCenter.lat],
    zoom: map.getZoom(),
    bearing: map.getBearing(),
    pitch: map.getPitch(),
  };
  let modeListener:
    ((mode: MapMode, reason: ModeFailureReason) => void) | null = null;
  let photorealLayer: Layer | null = null;
  const modes = modeRenderer(
    map,
    style,
    (mode, reason) => modeListener?.(mode, reason),
    (layer) => {
      photorealLayer = layer;
      clockOverlay.setPhotoreal?.(layer);
    },
  );
  let clockOverlay: OverlayMount = overlayFor(null, null, undefined, true);
  clockOverlay.onAdd(map);
  let timestamp: number | null = null;
  return {
    ...createHandle(surfaceFrom(map), {
      mount(overlay) {
        if (overlay.getPayloadLayers && clockOverlay.setPayloadLayers) {
          clockOverlay.setPayloadLayers(overlay.getPayloadLayers());
          return;
        }
        clockOverlay.onRemove(map);
        clockOverlay = overlay;
        overlay.onAdd(map);
        overlay.setPhotoreal?.(photorealLayer);
        if (timestamp !== null) overlay.setClock?.(timestamp);
      },
      remove() {
        modes.remove();
        clockOverlay.onRemove(map);
        map.remove();
      },
    }),
    focusArea(outline) {
      const points =
        outline.type === 'Circle'
          ? circleBoundary(outline.coordinates, outline.radius_m)
          : outline.coordinates.flat();
      const bounds = new LngLatBounds();
      for (const [lon, lat] of points) bounds.extend([lon, lat]);
      if (!bounds.isEmpty())
        map.fitBounds(bounds, { duration: 0, padding: 64, maxZoom: 16 });
    },
    camera(command) {
      if (command === 'recentre') {
        map.jumpTo(home);
        return;
      }
      if (command === 'zoomIn') {
        map.zoomIn({ duration: 0 });
        return;
      }
      if (command === 'zoomOut') {
        map.zoomOut({ duration: 0 });
        return;
      }
      const offset: [number, number] =
        command === 'north'
          ? [0, -100]
          : command === 'south'
            ? [0, 100]
            : command === 'east'
              ? [100, 0]
              : [-100, 0];
      map.panBy(offset, { duration: 0 });
    },
    cameraState() {
      const center = map.getCenter();
      return {
        center: [center.lng, center.lat],
        zoom: map.getZoom(),
        bearing: map.getBearing(),
        pitch: map.getPitch(),
      };
    },
    restoreCamera(view) {
      map.jumpTo(view);
    },
    onModeError(listener) {
      modeListener = listener;
      return () => {
        modeListener = null;
      };
    },
    async setMode(mode, credit) {
      await modes.setMode(mode, credit);
      if (timestamp !== null) clockOverlay.setClock?.(timestamp);
    },
    setClock(value) {
      timestamp = value;
      clockOverlay.setClock?.(value);
    },
  };
}

export function createHandle(
  surface: MapSurface,
  life: {
    mount(overlay: OverlayMount): void;
    remove(): void;
  },
): MapHandle {
  const wrappers = new WeakMap<
    (event: DrawingEvent) => void,
    (event: unknown) => void
  >();
  const viewWrappers = new globalThis.Map<
    () => void,
    (event: unknown) => void
  >();
  return {
    mountOverlay(overlay) {
      life.mount(overlay);
    },
    remove() {
      life.remove();
    },
    bind(type, listener) {
      const wrapped = wrapperFor(wrappers, listener);
      surface.on(type, wrapped);
    },
    unbind(type, listener) {
      const wrapped = wrappers.get(listener);
      if (!wrapped) return;
      surface.off(type, wrapped);
    },
    project(lngLat) {
      return surface.project({ lng: lngLat.longitude, lat: lngLat.latitude });
    },
    unproject(point) {
      const lngLat = surface.unproject(point);
      return { longitude: lngLat.lng, latitude: lngLat.lat };
    },
    suspendGestures() {
      suspendNamed(bag(surface));
    },
    restoreGestures() {
      restoreNamed(bag(surface));
    },
    centre() {
      const lngLat = surface.getCenter();
      return { longitude: lngLat.lng, latitude: lngLat.lat };
    },
    bindView(listener) {
      const wrapped = viewWrapper(viewWrappers, listener);
      surface.on('move', wrapped);
      surface.on('resize', wrapped);
    },
    unbindView(listener) {
      const wrapped = viewWrappers.get(listener);
      if (!wrapped) return;
      surface.off('move', wrapped);
      surface.off('resize', wrapped);
      viewWrappers.delete(listener);
    },
  };
}

function viewWrapper(
  wrappers: globalThis.Map<() => void, (event: unknown) => void>,
  listener: () => void,
): (event: unknown) => void {
  const existing = wrappers.get(listener);
  if (existing) return existing;
  const wrapped = () => {
    listener();
  };
  wrappers.set(listener, wrapped);
  return wrapped;
}

function wrapperFor(
  wrappers: WeakMap<(event: DrawingEvent) => void, (event: unknown) => void>,
  listener: (event: DrawingEvent) => void,
): (event: unknown) => void {
  const existing = wrappers.get(listener);
  if (existing) return existing;
  const wrapped = (event: unknown) => {
    listener(drawingEvent(event));
  };
  wrappers.set(listener, wrapped);
  return wrapped;
}

function drawingEvent(value: unknown): DrawingEvent {
  const record = isRecord(value) ? value : {};
  const point = isRecord(record.point) ? record.point : {};
  const lngLat = isRecord(record.lngLat) ? record.lngLat : {};
  const original = isRecord(record.originalEvent) ? record.originalEvent : {};
  return {
    type: typeof record.type === 'string' ? record.type : '',
    x: finite(point.x),
    y: finite(point.y),
    longitude: finite(lngLat.lng),
    latitude: finite(lngLat.lat),
    key: typeof original.key === 'string' ? original.key : '',
  };
}

function finite(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function bag(surface: MapSurface): GestureBag {
  return {
    dragPan: surface.dragPan,
    scrollZoom: surface.scrollZoom,
    boxZoom: surface.boxZoom,
    dragRotate: surface.dragRotate,
    doubleClickZoom: surface.doubleClickZoom,
    touchZoomRotate: surface.touchZoomRotate,
    touchPitch: surface.touchPitch,
    keyboard: surface.keyboard,
  };
}

function bindMap(
  map: Map,
  type: string,
  listener: (event: unknown) => void,
  off: boolean,
): void {
  const sink = map as unknown as {
    on(name: string, handler: (event: unknown) => void): void;
    off(name: string, handler: (event: unknown) => void): void;
  };
  if (off) sink.off(type, listener);
  else sink.on(type, listener);
}

function surfaceFrom(map: Map): MapSurface {
  return {
    on(type, listener) {
      bindMap(map, type, listener, false);
    },
    off(type, listener) {
      bindMap(map, type, listener, true);
    },
    project(lngLat) {
      return map.project(lngLat);
    },
    unproject(point) {
      return map.unproject([point.x, point.y]);
    },
    getCenter() {
      return map.getCenter();
    },
    remove() {
      map.remove();
    },
    dragPan: map.dragPan,
    scrollZoom: map.scrollZoom,
    boxZoom: map.boxZoom,
    dragRotate: map.dragRotate,
    doubleClickZoom: map.doubleClickZoom,
    touchZoomRotate: map.touchZoomRotate,
    touchPitch: map.touchPitch,
    keyboard: map.keyboard,
  };
}
