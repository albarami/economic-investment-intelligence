declare module '*.css';

declare module 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url' {
  const url: string;
  export default url;
}

declare module '*.woff2?url' {
  const url: string;
  export default url;
}

interface LookDiagnostics {
  ready: boolean;
  failure: string;
  lang: 'en' | 'ar';
  theme: 'dark' | 'light';
  mapTheme: 'dark' | 'light';
  reduced: boolean;
  moving: boolean;
  litMode: '' | 'staged' | 'instant';
  lit: boolean;
  flipping: boolean;
  fontsReady: boolean;
  basemap: boolean;
  bearing: number;
  pitch: number;
  zoom: number;
  units: number;
  litLevels: () => number[];
  litLayers: () => string[];
  labelFields: () => string[];
  labels: () => { name: string; kind: string; minZoom: number }[];
  labelsUnder: (
    rects: {
      name: string;
      x: number;
      y: number;
      width: number;
      height: number;
    }[],
  ) => { label: string; plate: string }[];
  brightCorners: () => { x: number; y: number }[];
  litUnder: (
    rects: { x: number; y: number; width: number; height: number }[],
  ) => number;
  districtNames: () => string[];
  planted: boolean;
  rendered: () => Promise<void>;
  showBuildings: () => Promise<void>;
  // Round 5: the screen (P2), the street camera (V9), the folded plates
  // (V7), the lit district (P1), the layers of the map and a card by key.
  screen: 'home' | 'place' | 'notyet' | 'answer';
  settled: boolean;
  fold: { brief: 'open' | 'folded'; legend: 'open' | 'folded' };
  camera: (view: {
    center: [number, number];
    zoom: number;
    pitch: number;
    bearing: number;
  }) => Promise<void>;
  district: () => { name: string; x: number; y: number } | null;
  layers: () => string[];
  // Round 5g: the map's zoom unrounded, for checks at a layer's zoom bound.
  exactZoom?: () => number;
  sourceFeatures: (source: string, layer: string) => number;
  openPoint?: (key: string) => void;
  photoreal?: {
    toggle: () => void;
    state: () => { on: boolean; loaded: boolean; held: boolean };
  };
}

interface Window {
  __look?: LookDiagnostics;
}
