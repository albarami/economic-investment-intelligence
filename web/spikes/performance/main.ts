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
  EMPTY_CANVAS_PROBE_MS,
  SMOKE_MS,
  WALL_CSS_HEIGHT,
  WALL_CSS_WIDTH,
  profileDuration,
} from './config.mjs';
import { generateHexagons, generateParticles } from './geometry.mjs';
import { mountScene, webglFailure } from './layers';
import notices from './notices.json' with { type: 'json' };
import { recordOrbit } from './recorder';
import {
  judgeEmptyCanvas,
  judgeRenderer,
  readUnmaskedRenderer,
  summariseFrames,
} from './trace.mjs';

const LOCK_PLACEHOLDER = `sha256:${'ab'.repeat(32)}`;
const ORBIT_TURN = 120;
const NONE_AVAILABLE = 'none is available';
const PLANTED_SOFTWARE_RENDERER = 'Microsoft Basic Render Driver';
const PLANTED_REMOTE_RENDERER = 'Microsoft Remote Display Adapter';
const PASSING_PLANTED_RENDERER = 'Synthetic passing adapter';
const CAPPED_INTERVAL_MS = 1000 / 30;
const SIXTY_INTERVAL_MS = 16.67;
// Above the 16.7 ms frame budget, so a planted slow scene is recorded rather than treated as the environment.
const SLOW_SCENE_INTERVAL_MS = 50;

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

function environmentGate(profile: string, plant: string): boolean {
  if (profile !== PROFILE_GATE) return false;
  return (
    plant === '' ||
    plant === 'software-renderer' ||
    plant === 'remote-renderer' ||
    plant === 'capped-frame-rate' ||
    plant === 'slow-scene'
  );
}

function plantedRenderer(real: string, plant: string): string {
  if (plant === 'software-renderer') return PLANTED_SOFTWARE_RENDERER;
  if (plant === 'remote-renderer') return PLANTED_REMOTE_RENDERER;
  if (plant === 'capped-frame-rate' || plant === 'slow-scene') {
    return PASSING_PLANTED_RENDERER;
  }
  return real;
}

function rendererLine(value: string): string {
  return value.trim() === '' ? NONE_AVAILABLE : value;
}

function refuse(name: string, rate?: number): void {
  spike.failure = name;
  spike.phase = 'failed';
  show(
    '#map-failure',
    rate === undefined ? `refused: ${name}` : `refused: ${name} ${rate}`,
  );
}

async function showRenderer(value: string): Promise<void> {
  show('#renderer', rendererLine(value));
  spike.webglRenderer = value;
  spike.phase = 'renderer';
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => resolve());
  });
}

function probeContext(container: HTMLElement): {
  renderer: string;
  close: () => void;
} {
  const canvas = document.createElement('canvas');
  canvas.width = 2;
  canvas.height = 2;
  container.append(canvas);
  const context = canvas.getContext('webgl2');
  return {
    renderer: readUnmaskedRenderer(context),
    close() {
      context?.getExtension('WEBGL_lose_context')?.loseContext();
      canvas.remove();
    },
  };
}

function plantedTimestamps(intervalMs: number, durationMs: number): number[] {
  const steps = Math.round(durationMs / intervalMs);
  const stamps: number[] = [];
  for (let index = 0; index <= steps; index += 1) {
    stamps.push(index * intervalMs);
  }
  return stamps;
}

function liveTimestamps(durationMs: number): Promise<number[]> {
  return new Promise((resolve) => {
    const stamps: number[] = [];
    let origin = -1;
    const tick = (now: number) => {
      if (origin < 0) origin = now;
      stamps.push(now);
      if (now - origin >= durationMs) {
        resolve(stamps);
        return;
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

async function emptyCanvasTimestamps(plant: string): Promise<number[]> {
  if (plant === 'capped-frame-rate') {
    return plantedTimestamps(CAPPED_INTERVAL_MS, EMPTY_CANVAS_PROBE_MS);
  }
  if (plant === 'slow-scene') {
    return plantedTimestamps(SIXTY_INTERVAL_MS, EMPTY_CANVAS_PROBE_MS);
  }
  return liveTimestamps(EMPTY_CANVAS_PROBE_MS);
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
  let environmentShown = false;
  if (environmentGate(spike.profile, plant)) {
    const probe = probeContext(container);
    const held = plantedRenderer(probe.renderer, plant);
    probe.close();
    await showRenderer(held);
    environmentShown = true;
    const rendererRefusal = judgeRenderer(held);
    if (rendererRefusal !== '') {
      refuse(rendererRefusal);
      return;
    }
    const verdict = judgeEmptyCanvas(await emptyCanvasTimestamps(plant));
    if (!verdict.ok) {
      refuse(verdict.failure, verdict.framesPerSecond);
      return;
    }
  }
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
    if (plant === 'missing-renderer') {
      await showRenderer(scene.renderer());
      spike.webglRenderer = '';
    } else if (!environmentShown) {
      await showRenderer(scene.renderer());
    }
    const duration =
      plant === 'missing-renderer' || plant === 'slow-scene'
        ? SMOKE_MS
        : (profileDuration(spike.profile) ?? SMOKE_MS);
    if (plant === 'slow-scene') {
      const timestamps = plantedTimestamps(SLOW_SCENE_INTERVAL_MS, duration);
      for (const elapsed of timestamps) {
        scene.step(elapsed, (elapsed / duration) * ORBIT_TURN, false);
      }
      void finish(scene, particles, flags, plant, timestamps);
      return;
    }
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
