import roadData from './road-data.json' with { type: 'json' };
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
/** Empty-canvas frame count, about two seconds, before the map and its layers load. */
export const EMPTY_CANVAS_PROBE_MS = 2000;
export const SCENE_CENTER = [0.02, 0.02];
export const SCENE_ZOOM = 9;

// W4 owner ruling, 2026-11-13: OpenStreetMap contributors, counted by the
// owner through the Overpass service: 24,367 ways motorway to tertiary,
// 76,703 with residential, 122,720 with service. Ways are not links.
// These invented load sizes represent the first load and full street network;
// they are not a place statistic and never appear on the page.
export const ROAD_LOADS = {
  'hexagons-particles-roads': 100000,
  'hexagons-particles-roads-250k': 250000,
};
// docs/11_DESIGN_DIRECTION.md, Motion: --eii-hour-hold, --eii-dur-scene.
export const HOUR_HOLD_MS = 2500;
export const SCENE_MS = 800;
// Closed keys of parameters_v1.json band_count; no assignment calculation here.
export const VOLUME_BANDS = ['vb1', 'vb2', 'vb3', 'vb4'];
export const ROAD_COLORS = [
  [184, 177, 210, 255],
  [151, 137, 191, 255],
  [117, 96, 166, 255],
  [78, 55, 132, 255],
];
// ASSUMPTION: widths and invented segment length are spike presentation settings.
export const ROAD_WIDTHS = { residential: 2, secondary: 4 };
export const ROAD_EXTENT = 1.2;
export const ROAD_SEGMENT = 0.012;
export const ROAD_DASH = [3, 2];
export const LAYER_SETS = {
  [LAYER_SET_HEXAGONS_PARTICLES]: {
    hexagons: HEXAGON_COUNT,
    particles: PARTICLE_COUNT,
  },
};

for (const [name, count] of Object.entries(ROAD_LOADS)) {
  LAYER_SETS[name] = {
    hexagons: HEXAGON_COUNT,
    particles: PARTICLE_COUNT,
    roads: count + roadData.roads.links.length,
  };
}
export function isRoadSet(name) {
  return Object.hasOwn(ROAD_LOADS, name);
}

export function profileDuration(profile) {
  if (profile === PROFILE_GATE) return ORBIT_MS;
  if (profile === PROFILE_SMOKE) return SMOKE_MS;
  return null;
}
