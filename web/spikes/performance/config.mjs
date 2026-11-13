/** Fixed gate of the performance spike. The cap is an assumption, not a search. */

export const CONTRACT = 'eii.performance-trace';
export const CONTRACT_VERSION = 1;
export const PROVENANCE = 'Synthetic';
export const SEED = 1;
export const LAYER_SET_HEXAGONS_PARTICLES = 'hexagons-particles';
export const PROFILE_GATE = 'gate';
export const PROFILE_SMOKE = 'smoke';
export const HEXAGON_COUNT = 110000;
export const PARTICLE_COUNT = 50000;
export const HEXAGON_RESOLUTION = 8;
export const WALL_CSS_WIDTH = 1920;
export const WALL_CSS_HEIGHT = 1080;
export const CAP_VALUE = 1;
export const CAP_LABEL = 'ASSUMPTION';
export const FRAME_BUDGET_MS = 16.7;
export const SHARE_MINIMUM = 0.95;
export const ORBIT_MS = 30000;
export const SMOKE_MS = 400;
export const SCENE_CENTER = [0.02, 0.02];
export const SCENE_ZOOM = 9;

export const LAYER_SETS = {
  [LAYER_SET_HEXAGONS_PARTICLES]: {
    hexagons: HEXAGON_COUNT,
    particles: PARTICLE_COUNT,
  },
};

export function profileDuration(profile) {
  if (profile === PROFILE_GATE) return ORBIT_MS;
  if (profile === PROFILE_SMOKE) return SMOKE_MS;
  return null;
}
