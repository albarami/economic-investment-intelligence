/**
 * Interleaved deck overlay. Layers sit before the first label layer.
 * Nothing here requests a tile or a layer route.
 */
import { LightingEffect, type Layer } from '@deck.gl/core';
import { ClockLight, lightPosition, nightVisible } from '../clock-light';
import { MapLibreOverlay } from '@deck.gl/maplibre';
import { H3HexagonLayer } from '@deck.gl/geo-layers';
import { GeoJsonLayer, PathLayer, ScatterplotLayer } from '@deck.gl/layers';
import type {
  Map as LibreMap,
  LayerSpecification,
  StyleSpecification,
} from 'maplibre-gl';

import type { FactRegistry } from '../../facts/registry';
import type { SourceGeometry } from './source-geometry';
import type { LayerFeature, LayerPayload } from './payload';
import {
  boundaryColor,
  fillColor,
  OUTLINE_WIDTH_PX,
  pointRadiusPx,
} from './ramp';
import { geometryDeckType } from './checks';
import { acceptPayload, OUTLINE_LAYER_KEYS, type DrawnLayer } from './refuse';
import { publishSelection } from './selection';
import {
  activeUse,
  forUse,
  landGroupKeys,
  readUseChoice,
  subscribeUseChoice,
} from './land-use';

export interface DrawnPoint {
  position: readonly [number, number];
  featureId: string;
  classId: string;
}

export interface DrawnPath {
  path: readonly (readonly [number, number])[];
  featureId: string;
}

export interface DrawnPolygon {
  type: 'Feature';
  properties: { id: string; featureId: string; classId: string };
  geometry:
    | { type: 'Polygon'; coordinates: number[][][] }
    | { type: 'MultiPolygon'; coordinates: number[][][][] };
}

export function firstLabelLayerId(style: StyleSpecification): string | null {
  for (const layer of style.layers) {
    if (isSymbol(layer)) return layer.id;
  }
  return null;
}

function isSymbol(layer: LayerSpecification): boolean {
  return layer.type === 'symbol';
}

export function overlayFor(
  payload: LayerPayload | null,
  beforeId: string | null,
  registry?: FactRegistry,
  clockEnabled = false,
) {
  const accepted =
    payload && registry ? acceptPayload(payload, registry) : null;
  const drawn = accepted?.ok ? accepted.draw.layers : [];
  const groups = landGroupKeys(drawn);
  const buildLayers = () =>
    deckLayers(forUse(drawn, activeUse(groups, readUseChoice())), beforeId);
  const layers = buildLayers();
  const base = new MapLibreOverlay({ interleaved: true, layers });
  const overlay = clockEnabled
    ? attachClock(base, layers)
    : Object.assign(base, {
        replaceLayers(next: Layer[]) {
          base.setProps({ layers: next });
        },
      });
  const unsubscribe = groups.length
    ? subscribeUseChoice(() => overlay.replaceLayers(buildLayers()))
    : () => {};
  const remove = overlay.onRemove.bind(overlay);
  return Object.assign(overlay, {
    onRemove(target: LibreMap) {
      unsubscribe();
      remove(target);
    },
  });
}

export function pointRows(features: readonly LayerFeature[]): DrawnPoint[] {
  return features.flatMap((feature) => {
    const position =
      feature.geometry?.type === 'Point'
        ? feature.geometry.coordinates
        : feature.position;
    return position
      ? [
          {
            position,
            featureId: feature.feature_id,
            classId: feature.class_id ?? '',
          },
        ]
      : [];
  });
}
export function pathRows(features: readonly LayerFeature[]): DrawnPath[] {
  return features.flatMap((feature) => {
    const path =
      feature.geometry?.type === 'LineString'
        ? feature.geometry.coordinates
        : feature.path;
    return path ? [{ path, featureId: feature.feature_id }] : [];
  });
}
function mutablePolygon(
  geometry: Extract<SourceGeometry, { type: 'Polygon' | 'MultiPolygon' }>,
): DrawnPolygon['geometry'] {
  const polygon = (
    rings: Extract<SourceGeometry, { type: 'Polygon' }>['coordinates'],
  ) => rings.map((ring) => ring.map((point) => [point[0], point[1]]));
  return geometry.type === 'Polygon'
    ? { type: 'Polygon', coordinates: polygon(geometry.coordinates) }
    : { type: 'MultiPolygon', coordinates: geometry.coordinates.map(polygon) };
}
export function polygonRows(features: readonly LayerFeature[]): DrawnPolygon[] {
  return features.flatMap((feature) => {
    const geometry = feature.geometry;
    const polygon =
      geometry?.type === 'Polygon' || geometry?.type === 'MultiPolygon'
        ? geometry
        : feature.ring
          ? { type: 'Polygon' as const, coordinates: [feature.ring] }
          : null;
    return polygon
      ? [
          {
            type: 'Feature' as const,
            properties: {
              id: feature.feature_id,
              featureId: feature.feature_id,
              classId: feature.class_id ?? '',
            },
            geometry: mutablePolygon(polygon),
          },
        ]
      : [];
  });
}

const NO_WORKER_LOAD = { worker: false };

interface DeckRow {
  featureId?: string;
  classId?: string;
  properties?: { featureId?: string; classId?: string };
}

function pickedId(info: { object?: DeckRow }): void {
  const object = info.object;
  const id = object?.featureId ?? object?.properties?.featureId;
  if (id) publishSelection(id);
}

function partition(layer: DrawnLayer): {
  id: string;
  layerType: string;
  features: LayerFeature[];
  outline: boolean;
}[] {
  if (layer.hexes.length > 0) {
    return [
      {
        id: `${layer.key}:H3HexagonLayer`,
        layerType: 'H3HexagonLayer',
        features: layer.features,
        outline: false,
      },
    ];
  }
  const groups = new Map<string, LayerFeature[]>();
  for (const feature of layer.features) {
    const layerType = geometryDeckType(feature.geometry_kind);
    const rows = groups.get(layerType) ?? [];
    rows.push(feature);
    groups.set(layerType, rows);
  }
  return [...groups.entries()].map(([layerType, features]) => ({
    id: `${layer.key}:${layerType}`,
    layerType,
    features:
      layerType === 'ScatterplotLayer' && layer.key === 'fdi_projects'
        ? features.filter((feature) => layer.marks.includes(feature.feature_id))
        : features,
    outline:
      layerType === 'GeoJsonLayer' &&
      (OUTLINE_LAYER_KEYS.has(layer.key) ||
        features.some((feature) => feature.geometry_kind === 'outline')),
  }));
}

/** Display radius of a register establishment point; a style, never a value. */
export const COMPANY_POINT_RADIUS_PX = 4;

export function deckLayers(
  layers: readonly DrawnLayer[],
  beforeId: string | null,
) {
  return layers.flatMap((layer) => [
    ...(layer.notRanked.length
      ? [
          new GeoJsonLayer({
            id: `${layer.key}:not_ranked`,
            beforeId: beforeId ?? undefined,
            loadOptions: NO_WORKER_LOAD,
            pickable: true,
            onClick: pickedId,
            filled: false,
            stroked: true,
            getLineColor: () => boundaryColor(),
            lineWidthMinPixels: OUTLINE_WIDTH_PX,
            data: {
              type: 'FeatureCollection',
              features: layer.notRanked.map((zone) => ({
                type: 'Feature' as const,
                properties: { featureId: zone.feature_id },
                geometry: mutablePolygon(
                  zone.geometry ?? {
                    type: 'Polygon',
                    coordinates: [zone.ring!],
                  },
                ),
              })),
            },
          }),
        ]
      : []),
    ...partition(layer).map((part) => {
      const common = {
        id: part.id,
        beforeId: beforeId ?? undefined,
        loadOptions: NO_WORKER_LOAD,
        pickable: true,
        onClick: pickedId,
      };
      if (part.layerType === 'H3HexagonLayer') {
        return new H3HexagonLayer({
          ...common,
          data: layer.hexes,
          getHexagon: (row: { cell: string }) => row.cell,
          getFillColor: (row: { classId: string }) => fillColor(row.classId),
          extruded: false,
          filled: true,
          stroked: false,
        });
      }
      if (part.layerType === 'PathLayer') {
        return new PathLayer({
          ...common,
          widthMinPixels: OUTLINE_WIDTH_PX,
          data: pathRows(part.features).map((row) => ({
            path: row.path.map((pair) => [pair[0], pair[1]]),
            featureId: row.featureId,
          })),
        });
      }
      if (part.layerType === 'GeoJsonLayer') {
        return new GeoJsonLayer({
          ...common,
          data: {
            type: 'FeatureCollection',
            features: polygonRows(part.features),
          },
          filled: !part.outline,
          stroked: true,
          lineWidthMinPixels: OUTLINE_WIDTH_PX,
          ...(part.outline
            ? {
                getLineColor: () => boundaryColor(),
                getLineWidth: OUTLINE_WIDTH_PX,
                lineWidthUnits: 'pixels' as const,
              }
            : {
                getFillColor: (feature: DeckRow) =>
                  fillColor(feature.properties?.classId ?? ''),
              }),
        });
      }
      return new ScatterplotLayer({
        ...common,
        data: pointRows(part.features),
        getPosition: (row: DrawnPoint) => row.position,
        filled: true,
        stroked: false,
        ...(layer.key === 'fc_firms_per_tower'
          ? {
              getRadius: (row: DrawnPoint) => pointRadiusPx(row.classId),
              getFillColor: (row: DrawnPoint) => fillColor(row.classId),
              radiusUnits: 'pixels' as const,
            }
          : layer.key === 'company_points'
            ? {
                // One size and one neutral colour: an establishment point
                // carries no class, figure or origin meaning (S3-T12).
                getRadius: COMPANY_POINT_RADIUS_PX,
                getFillColor: () => boundaryColor(),
                radiusUnits: 'pixels' as const,
              }
            : {}),
      });
    }),
  ]);
}

/** Attach geometry clock to the existing overlay, preserving payload and facts. */
export function attachClock(overlay: MapLibreOverlay, layers: Layer[]) {
  let photoreal: Layer | null = null;
  const anchor = new ScatterplotLayer({ id: 'clock-anchor', data: [] });
  let map: LibreMap | null = null;
  let previous = '';
  let night: boolean | null = null;
  let sun: ClockLight | null = null;
  const nightLayer = (layer: Layer, visible: boolean) => {
    const duration = globalThis.matchMedia?.('(prefers-reduced-motion: reduce)')
      .matches
      ? 0
      : Number.parseFloat(
          getComputedStyle(document.documentElement).getPropertyValue(
            '--eii-dur-scene',
          ),
        ) || 0;
    return layer.clone({
      visible: true,
      opacity: visible ? 1 : 0,
      pickable: visible,
      transitions: { opacity: duration },
    });
  };
  const shownLayers = () => [
    ...layers.map((layer) => {
      const visible =
        layer.id.startsWith('night_lights:') && night !== null
          ? nightLayer(layer, night)
          : layer;
      const props = { ...visible.props, beforeId: undefined };
      return photoreal ? visible.clone(props) : visible;
    }),
    ...(photoreal ? [photoreal] : []),
    anchor,
  ];
  const applySun = (
    direction: number[],
    target: Pick<LibreMap, 'setLight' | 'setSky'>,
  ) => {
    const signature = direction.join();
    if (signature === previous) return;
    previous = signature;
    target.setLight({
      anchor: 'map',
      position: lightPosition(direction),
      'position-transition': { duration: 0, delay: 0 },
    });
    const colors = map ? getComputedStyle(map.getContainer()) : null;
    target.setSky({
      ...(colors
        ? {
            'sky-color': colors.getPropertyValue('--eii-map-water').trim(),
            'horizon-color': colors.getPropertyValue('--eii-map-land').trim(),
          }
        : {}),
      'atmosphere-blend': Math.max(0, -(direction[2] ?? 0)),
      'atmosphere-blend-transition': { duration: 0, delay: 0 },
    });
    const visible = nightVisible(direction);
    if (visible !== night) {
      night = visible;
      overlay.setProps({
        layers: shownLayers(),
      });
    }
  };
  const onAdd = overlay.onAdd.bind(overlay);
  const onRemove = overlay.onRemove.bind(overlay);
  return Object.assign(overlay, {
    applySun,
    getPayloadLayers() {
      return layers;
    },
    setPayloadLayers(next: Layer[]) {
      layers = next;
      overlay.setProps({ layers: shownLayers() });
    },
    setPhotoreal(layer: Layer | null) {
      photoreal = layer;
      overlay.setProps({ layers: shownLayers() });
    },
    replaceLayers(next: Layer[]) {
      layers = next;
      overlay.setProps({ layers: shownLayers() });
    },
    onAdd(target: LibreMap) {
      map = target;
      return onAdd(target);
    },
    onRemove(target: LibreMap) {
      map = null;
      onRemove(target);
    },
    setClock(timestamp: number) {
      previous = '';
      sun = new ClockLight(timestamp, (direction) => {
        if (map) applySun(direction, map);
      });
      overlay.setProps({
        layers: shownLayers(),
        effects: [new LightingEffect({ sun })],
        onAfterRender: () => {
          if (sun && anchor.context) sun.getProjectedLight({ layer: anchor });
        },
      });
    },
  });
}
