import 'maplibre-gl/dist/maplibre-gl.css';
import './style.css';
import {
  CAP_LABEL,
  CAP_VALUE,
  CONTRACT,
  CONTRACT_VERSION,
  LAYER_SET_HEXAGONS_PARTICLES,
  PROFILE_GATE,
  PROFILE_SMOKE,
  PROVENANCE,
  SEED,
  SMOKE_MS,
  WALL_CSS_HEIGHT,
  WALL_CSS_WIDTH,
  profileDuration,
} from './config.mjs';
import { generateHexagons, generateParticles } from './geometry.mjs';
import { mountScene, webglFailure } from './layers';
import notices from './notices.json' with { type: 'json' };
import { recordOrbit } from './recorder';
import { summariseFrames } from './trace.mjs';

const LOCK_PLACEHOLDER = `sha256:${'ab'.repeat(32)}`;
const ORBIT_TURN = 120;

type Spike = {
  phase: string;
  failure: string;
  hexagonInstances: number;
  particleInstances: number;
  hex: boolean;
  particle: boolean;
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
};

const spike: Spike = {
  phase: 'loading',
  failure: '',
  hexagonInstances: 0,
  particleInstances: 0,
  hex: false,
  particle: false,
  bearingStart: 0,
  bearingEnd: 0,
  positionStart: 0,
  positionEnd: 0,
  cssWidth: 0,
  cssHeight: 0,
  bufferWidth: 0,
  bufferHeight: 0,
  devicePixelRatio: 1,
  cap: CAP_VALUE,
  textPixelRatio: 1,
  profile: PROFILE_GATE,
  submitFailure: '',
  qualification: '',
  savedPath: '',
  webglRenderer: '',
  shareUnderBudget: null,
  windowWidth: 0,
  windowHeight: 0,
};

window.__spike = spike;

function show(id: string, text: string): void {
  const node = document.querySelector(id);
  if (node instanceof HTMLElement) {
    node.hidden = false;
    node.textContent = text;
  }
}

function postTrace(payload: string): Promise<{
  failure: string;
  path: string;
  qualification: string;
}> {
  return new Promise((resolve) => {
    const request = new XMLHttpRequest();
    request.open('POST', '/__perf/trace');
    request.setRequestHeader('content-type', 'application/json');
    request.onload = () => {
      try {
        const body = JSON.parse(request.responseText) as {
          ok?: boolean;
          failure?: string;
          path?: string;
          qualification?: string;
        };
        resolve({
          failure:
            body.ok === true ? '' : (body.failure ?? 'submission-failed'),
          path: body.path ?? '',
          qualification: body.qualification ?? '',
        });
      } catch {
        resolve({ failure: 'malformed-payload', path: '', qualification: '' });
      }
    };
    request.onerror = () =>
      resolve({ failure: 'submission-failed', path: '', qualification: '' });
    request.send(payload);
  });
}

function readProfile(params: URLSearchParams, plant: string): string {
  if (plant === 'rename-profile') return 'tuned';
  return params.get('profile') === PROFILE_SMOKE ? PROFILE_SMOKE : PROFILE_GATE;
}

async function start(): Promise<void> {
  const params = new URLSearchParams(window.location.search);
  const plant = params.get('plant') ?? '';
  const arabic = window.location.pathname.startsWith('/ar/');
  document.documentElement.lang = arabic ? 'ar' : 'en';
  document.documentElement.dir = arabic ? 'rtl' : 'ltr';
  show('#notice', arabic ? notices.arabic.text : notices.english);
  spike.profile = readProfile(params, plant);
  spike.textPixelRatio = window.devicePixelRatio;
  spike.devicePixelRatio = window.devicePixelRatio;
  spike.windowWidth = window.innerWidth;
  spike.windowHeight = window.innerHeight;
  if (plant === 'remote-asset') {
    const image = new Image();
    image.src = 'https://assets.invalid/spike.png';
  }
  if (plant === 'no-webgl2') {
    spike.failure = 'webgl2-unavailable';
    spike.phase = 'failed';
    show('#map-failure', spike.failure);
    return;
  }
  const container = document.querySelector('#map');
  if (!(container instanceof HTMLElement)) {
    spike.failure = 'map container is absent';
    spike.phase = 'failed';
    show('#map-failure', spike.failure);
    return;
  }
  const cap = plant === 'ignore-cap' ? window.devicePixelRatio : CAP_VALUE;
  spike.cap = cap;
  const cells = generateHexagons().slice();
  const particles = generateParticles(cells).slice();
  if (plant === 'omit-hexagon') cells.pop();
  if (plant === 'omit-particle') particles.pop();
  const isolate = params.get('isolate');
  try {
    const scene = await mountScene({
      container,
      cap,
      cells,
      particles,
      showHexagons: plant !== 'hide-hexagons' && isolate !== 'particles',
      showParticles: plant !== 'hide-particles' && isolate !== 'hexagons',
    });
    const flags = {
      visibilityLost: false,
      resized: false,
      contextLost: false,
    };
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) flags.visibilityLost = true;
    });
    window.addEventListener('resize', () => {
      if (
        scene.canvas.clientWidth !== WALL_CSS_WIDTH ||
        scene.canvas.clientHeight !== WALL_CSS_HEIGHT
      ) {
        flags.resized = true;
      }
    });
    scene.onContextLost(() => {
      flags.contextLost = true;
    });
    const colors = scene.sample();
    spike.hexagonInstances = scene.hexagonInstances;
    spike.particleInstances = scene.particleInstances;
    spike.hex = colors.hex;
    spike.particle = colors.particle;
    spike.bearingStart = scene.bearing();
    spike.positionStart = particles[0]?.position[0] ?? 0;
    spike.cssWidth = scene.canvas.clientWidth;
    spike.cssHeight = scene.canvas.clientHeight;
    spike.bufferWidth = scene.canvas.width;
    spike.bufferHeight = scene.canvas.height;
    spike.webglRenderer = plant === 'missing-renderer' ? '' : scene.renderer();
    const duration =
      plant === 'missing-renderer'
        ? SMOKE_MS
        : (profileDuration(spike.profile) ?? SMOKE_MS);
    recordOrbit({
      durationMs: duration,
      onFrame: (elapsed) => {
        scene.step(
          elapsed,
          (elapsed / duration) * ORBIT_TURN,
          plant === 'freeze',
        );
      },
      onDone: (timestamps) => {
        void finish(scene, particles, flags, plant, timestamps);
      },
    });
  } catch (error) {
    spike.failure = webglFailure(error);
    spike.phase = 'failed';
    show('#map-failure', spike.failure);
  }
}

async function finish(
  scene: {
    bearing: () => number;
    canvas: HTMLCanvasElement;
    sample: () => { hex: boolean; particle: boolean };
  },
  particles: { position: [number, number] }[],
  flags: { visibilityLost: boolean; resized: boolean; contextLost: boolean },
  plant: string,
  timestamps: number[],
): Promise<void> {
  const used = plant === 'no-samples' ? [] : timestamps;
  const summary = summariseFrames(used);
  const frameCount = summary.ok ? summary.frameCount : 0;
  const durationMs = summary.ok ? summary.durationMs : 0;
  const percentiles = summary.ok
    ? summary.percentiles
    : { p50: 0, p95: 0, p99: 0 };
  const shareUnderBudget = summary.ok ? summary.shareUnderBudget : 0;
  spike.bearingEnd = scene.bearing();
  spike.positionEnd = particles[0]?.position[0] ?? 0;
  const colors = scene.sample();
  spike.hex = spike.hex || colors.hex;
  spike.particle = spike.particle || colors.particle;
  spike.shareUnderBudget = summary.ok ? summary.shareUnderBudget : null;
  const trace = {
    contract: CONTRACT,
    version: CONTRACT_VERSION,
    provenance: PROVENANCE,
    seed: SEED,
    layerSet: LAYER_SET_HEXAGONS_PARTICLES,
    profile: spike.profile,
    codeCommit: 'page',
    lockSha256: LOCK_PLACEHOLDER,
    userAgent: navigator.userAgent,
    webglRenderer: spike.webglRenderer,
    window: { width: spike.windowWidth, height: spike.windowHeight },
    canvas: { cssWidth: spike.cssWidth, cssHeight: spike.cssHeight },
    drawingBuffer: { width: spike.bufferWidth, height: spike.bufferHeight },
    devicePixelRatio: spike.devicePixelRatio,
    cap: { value: spike.cap, label: CAP_LABEL },
    counts: {
      hexagons: spike.hexagonInstances,
      particles: spike.particleInstances,
    },
    timestamps: used,
    summary: {
      frameCount,
      durationMs,
      percentiles,
      shareUnderBudget,
    },
    camera: { completed: spike.bearingEnd !== spike.bearingStart },
    animation: { active: spike.positionEnd !== spike.positionStart },
    interruptions: flags,
  };
  if (plant === 'fail-submit') {
    Object.assign(trace, { extra: true });
  }
  const posted = await postTrace(JSON.stringify(trace));
  spike.submitFailure = posted.failure;
  spike.qualification = posted.qualification;
  spike.savedPath = posted.path;
  spike.phase = 'done';
  const share =
    spike.shareUnderBudget === null ? '' : String(spike.shareUnderBudget);
  show(
    '#result',
    `native frame-rate gate pending\nshare ${share}\nframes ${frameCount}\n${posted.path || posted.failure}`,
  );
}

void start();
