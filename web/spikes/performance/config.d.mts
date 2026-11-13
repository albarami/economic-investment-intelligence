export const CONTRACT: string;
export const CONTRACT_VERSION: number;
export const PROVENANCE: string;
export const SEED: number;
export const LAYER_SET_HEXAGONS_PARTICLES: string;
export const PROFILE_GATE: string;
export const PROFILE_SMOKE: string;
export const HEXAGON_COUNT: number;
export const PARTICLE_COUNT: number;
export const HEXAGON_RESOLUTION: number;
export const WALL_CSS_WIDTH: number;
export const WALL_CSS_HEIGHT: number;
export const CAP_VALUE: number;
export const CAP_LABEL: string;
export const FRAME_BUDGET_MS: number;
export const SHARE_MINIMUM: number;
export const ORBIT_MS: number;
export const SMOKE_MS: number;
export const EMPTY_CANVAS_PROBE_MS: number;
export const SCENE_CENTER: [number, number];
export const SCENE_ZOOM: number;
export function profileDuration(profile: string): number | null;
export const ROAD_LOADS: Record<string, number>;
export const LAYER_SETS: Record<
  string,
  { hexagons: number; particles: number; roads?: number }
>;
export const HOUR_HOLD_MS: number;
export const SCENE_MS: number;
export const VOLUME_BANDS: string[];
export const ROAD_COLORS: [number, number, number, number][];
export const ROAD_WIDTHS: Record<string, number>;
export const ROAD_EXTENT: number;
export const ROAD_SEGMENT: number;
export const ROAD_DASH: [number, number];
export function isRoadSet(name: string): boolean;
