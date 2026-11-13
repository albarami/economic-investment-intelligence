import type data from './road-data.json';
export type Road = {
  path: [number, number][];
  fixtureLink: string;
  roadClass: string;
  provenance: string;
  bands: Record<number, string>;
};
export type PlaybackState = {
  index: number;
  next: number;
  blend: number;
  ended: boolean;
};
export function generateRoads(input: typeof data, count: number): Road[];
export function bandAt(road: Road, hour: number): string;
export function bandsAt(roads: Road[], hour: number): string[];
export function playbackState(hours: number[], elapsed: number): PlaybackState;
export function drawnRoadCount(layer: {
  props: { visible?: boolean };
  state: {
    pathTesselator: {
      vertexStarts: number[];
      getPathSegmentIndices: (index: number) => number[];
    };
  };
}): number;
