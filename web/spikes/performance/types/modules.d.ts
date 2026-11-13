declare module '*.css';

declare module 'maplibre-gl/dist/maplibre-gl.css';

declare module 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url' {
  const url: string;
  export default url;
}

interface SpikeDiagnostics {
  phase: string;
  roadInstances: number;
  roadDashEnabled: boolean;
  layerSet: string;
  hoursShown: number[];
  paused: boolean;
  reducedMotion: boolean;
  motionElapsed: number;
  motionFrames: number;
  currentPosition: number;
  roadStates: {
    hour: number;
    nextHour: number;
    blend: number;
    bands: string[];
    nextBands: string[];
    trigger: number;
    stableData: boolean;
  }[];
  hourStepsMs: number[];
  failure: string;
  hexagonInstances: number;
  particleInstances: number;
  hex: boolean;
  particle: boolean;
  road: boolean;
  bearingStart: number;
  bearingEnd: number;
  positionStart: number;
  positionEnd: number;
  cssWidth: number;
  cssHeight: number;
  bufferWidth: number;
  bufferHeight: number;
  devicePixelRatio: number;
  cap: number;
  textPixelRatio: number;
  profile: string;
  submitFailure: string;
  qualification: string;
  savedPath: string;
  webglRenderer: string;
  shareUnderBudget: number | null;
  windowWidth: number;
  windowHeight: number;
}

interface Window {
  __spike?: SpikeDiagnostics;
  __rendererSeenBeforeOrbit?: boolean;
}
