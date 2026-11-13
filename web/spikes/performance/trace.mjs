import roadData from './road-data.json' with { type: 'json' };
/**
 * Closed performance-trace contract.
 * Percentiles and the share under the frame budget are computed here and nowhere else.
 */
import {
  isRoadSet,
  CAP_LABEL,
  CAP_VALUE,
  CONTRACT,
  CONTRACT_VERSION,
  FRAME_BUDGET_MS,
  LAYER_SETS,
  ORBIT_MS,
  PROFILE_GATE,
  PROFILE_SMOKE,
  PROVENANCE,
  SEED,
  SHARE_MINIMUM,
  WALL_CSS_HEIGHT,
  WALL_CSS_WIDTH,
} from './config.mjs';

export {
  CAP_LABEL,
  CAP_VALUE,
  CONTRACT,
  FRAME_BUDGET_MS,
  HEXAGON_COUNT,
  LAYER_SET_HEXAGONS_PARTICLES,
  ORBIT_MS,
  PARTICLE_COUNT,
  PROFILE_GATE,
  SHARE_MINIMUM,
  WALL_CSS_HEIGHT,
  WALL_CSS_WIDTH,
} from './config.mjs';

const TRACE_KEYS = [
  'contract',
  'version',
  'provenance',
  'seed',
  'layerSet',
  'profile',
  'codeCommit',
  'lockSha256',
  'userAgent',
  'webglRenderer',
  'window',
  'canvas',
  'drawingBuffer',
  'devicePixelRatio',
  'cap',
  'counts',
  'timestamps',
  'summary',
  'camera',
  'animation',
  'interruptions',
];

const SUMMARY_KEYS = [
  'frameCount',
  'durationMs',
  'percentiles',
  'shareUnderBudget',
];

const PERCENTILE_KEYS = ['p50', 'p95', 'p99'];

const CAPTURE_KEYS = ['role', 'host', 'browser', 'tracePath', 'sha256'];

const SOFTWARE_RENDERERS = [
  'swiftshader',
  'llvmpipe',
  'software',
  'microsoft basic render driver',
];
const WARP_WORD = /(?:^|[^a-z0-9])warp(?:[^a-z0-9]|$)/;
const REMOTE_WORD = /(?:^|[^a-z0-9])remote(?:[^a-z0-9]|$)/;
// Reaches 60 when the median frame interval is at most 17.5 ms.
// A 60 Hz interval is 16.67 ms and a 59.94 Hz interval is 16.68 ms, so both pass.
// A 50 Hz interval is 20 ms and a 30 Hz interval is 33.33 ms, so both are refused.
// Chosen once as the tolerance for "reaches 60", not fitted to a measured trace.
export const EMPTY_CANVAS_MAX_MEDIAN_MS = 17.5;
const RATE_HUNDREDTHS = 100;

function fail(failure) {
  return { ok: false, failure };
}

function ownKeys(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return Object.keys(value);
}

function closed(value, allowed) {
  const keys = ownKeys(value);
  if (keys === null) return 'missing-field';
  for (const key of keys) {
    if (!allowed.includes(key)) return 'unknown-field';
  }
  for (const key of allowed) {
    if (!Object.hasOwn(value, key)) return 'missing-field';
  }
  return '';
}

function nearestRank(sorted, percentile) {
  const rank = Math.ceil((percentile / 100) * sorted.length);
  return sorted[rank - 1];
}

export function summariseFrames(timestamps) {
  if (!Array.isArray(timestamps)) return fail('invalid-timestamps');
  if (timestamps.length < 2) return fail('empty-timestamps');
  const intervals = [];
  for (let index = 1; index < timestamps.length; index += 1) {
    const previous = timestamps[index - 1];
    const current = timestamps[index];
    if (
      typeof previous !== 'number' ||
      typeof current !== 'number' ||
      !Number.isFinite(previous) ||
      !Number.isFinite(current)
    ) {
      return fail('non-finite-timestamp');
    }
    if (!(current > previous)) return fail('non-increasing-timestamps');
    intervals.push(current - previous);
  }
  const sorted = [...intervals].sort((left, right) => left - right);
  let under = 0;
  for (const interval of intervals) {
    if (interval < FRAME_BUDGET_MS) under += 1;
  }
  return {
    ok: true,
    frameCount: intervals.length,
    durationMs: timestamps[timestamps.length - 1] - timestamps[0],
    intervals,
    percentiles: {
      p50: nearestRank(sorted, 50),
      p95: nearestRank(sorted, 95),
      p99: nearestRank(sorted, 99),
    },
    shareUnderBudget: under / intervals.length,
  };
}

function sameSummary(stored, fresh) {
  const shape = closed(stored, SUMMARY_KEYS);
  if (shape) return shape;
  const percentiles = closed(stored.percentiles, PERCENTILE_KEYS);
  if (percentiles) return percentiles;
  if (
    stored.frameCount !== fresh.frameCount ||
    stored.durationMs !== fresh.durationMs ||
    stored.shareUnderBudget !== fresh.shareUnderBudget ||
    stored.percentiles.p50 !== fresh.percentiles.p50 ||
    stored.percentiles.p95 !== fresh.percentiles.p95 ||
    stored.percentiles.p99 !== fresh.percentiles.p99
  ) {
    return 'forged-summary';
  }
  return '';
}

function shapeOf(value) {
  if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
    if (Object.hasOwn(value, 'path') || Object.hasOwn(value, 'outputPath')) {
      return fail('client-path');
    }
  }
  const root = closed(value, TRACE_KEYS);
  if (root) return fail(root);
  const nested = [
    closed(value.window, ['width', 'height']),
    closed(value.canvas, ['cssWidth', 'cssHeight']),
    closed(value.drawingBuffer, ['width', 'height']),
    closed(value.cap, ['value', 'label']),
    closed(
      value.counts,
      isRoadSet(value.layerSet)
        ? ['hexagons', 'particles', 'roads']
        : ['hexagons', 'particles'],
    ),
    closed(value.camera, ['completed']),
    closed(
      value.animation,
      isRoadSet(value.layerSet)
        ? ['active', 'playbackActive', 'reducedMotion', 'hoursShown']
        : ['active'],
    ),
    closed(value.interruptions, ['visibilityLost', 'resized', 'contextLost']),
  ];
  for (const item of nested) {
    if (item) return fail(item);
  }
  const fresh = summariseFrames(value.timestamps);
  if (!fresh.ok) return fresh;
  const summary = sameSummary(value.summary, fresh);
  if (summary) return fail(summary);
  return { ok: true, fresh };
}

export function judgeSubmission(value) {
  const shaped = shapeOf(value);
  if (!shaped.ok) return shaped;
  return { ok: true };
}

function positive(value) {
  return typeof value === 'number' && Number.isFinite(value) && value > 0;
}

export function readUnmaskedRenderer(context) {
  if (
    context === null ||
    typeof context !== 'object' ||
    typeof context.getExtension !== 'function' ||
    typeof context.getParameter !== 'function'
  ) {
    return '';
  }
  const extension = context.getExtension('WEBGL_debug_renderer_info');
  if (extension === null || typeof extension !== 'object') return '';
  const token = extension.UNMASKED_RENDERER_WEBGL;
  if (typeof token !== 'number') return '';
  const value = context.getParameter(token);
  if (typeof value !== 'string' || value.trim() === '') return '';
  return value;
}

export function judgeRenderer(renderer) {
  if (typeof renderer !== 'string' || renderer.trim() === '') {
    return 'missing-renderer';
  }
  const folded = renderer.toLowerCase();
  for (const needle of SOFTWARE_RENDERERS) {
    if (folded.includes(needle)) return 'software-renderer';
  }
  if (WARP_WORD.test(folded)) return 'software-renderer';
  if (REMOTE_WORD.test(folded)) return 'remote-renderer';
  return '';
}

function medianInterval(intervals) {
  const sorted = [...intervals].sort((left, right) => left - right);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) return sorted[mid];
  return (sorted[mid - 1] + sorted[mid]) / 2;
}

function measuredFramesPerSecond(medianMs) {
  return Math.round((1000 / medianMs) * RATE_HUNDREDTHS) / RATE_HUNDREDTHS;
}

export function judgeEmptyCanvas(timestamps) {
  if (!Array.isArray(timestamps) || timestamps.length < 2) {
    return { ok: false, failure: 'capped-frame-rate', framesPerSecond: 0 };
  }
  const intervals = [];
  for (let index = 1; index < timestamps.length; index += 1) {
    const previous = timestamps[index - 1];
    const current = timestamps[index];
    if (
      typeof previous !== 'number' ||
      typeof current !== 'number' ||
      !Number.isFinite(previous) ||
      !Number.isFinite(current) ||
      !(current > previous)
    ) {
      return { ok: false, failure: 'capped-frame-rate', framesPerSecond: 0 };
    }
    intervals.push(current - previous);
  }
  const medianMs = medianInterval(intervals);
  const framesPerSecond = measuredFramesPerSecond(medianMs);
  if (medianMs <= EMPTY_CANVAS_MAX_MEDIAN_MS) {
    return { ok: true, failure: '', framesPerSecond };
  }
  return { ok: false, failure: 'capped-frame-rate', framesPerSecond };
}

function judgeNative(capture, userAgent) {
  const shape = closed(capture, CAPTURE_KEYS);
  if (shape) return shape;
  if (capture.role !== 'owner' || capture.host !== 'windows-native') {
    return 'non-native';
  }
  if (capture.browser !== 'chrome' && capture.browser !== 'edge') {
    return 'non-native';
  }
  if (
    typeof capture.tracePath !== 'string' ||
    capture.tracePath.includes('..') ||
    !capture.tracePath.startsWith('web/spikes/performance/evidence/')
  ) {
    return 'non-native';
  }
  if (
    typeof capture.sha256 !== 'string' ||
    !/^sha256:[0-9a-f]{64}$/.test(capture.sha256)
  ) {
    return 'non-native';
  }
  if (
    typeof userAgent !== 'string' ||
    !userAgent.includes('Windows') ||
    userAgent.includes('Headless')
  ) {
    return 'non-native';
  }
  if (capture.browser === 'edge') {
    return userAgent.includes('Edg') ? '' : 'non-native';
  }
  if (!userAgent.includes('Chrome') || userAgent.includes('Edg')) {
    return 'non-native';
  }
  return '';
}

function qualify(trace, fresh, descriptor, capture) {
  if (!Object.hasOwn(LAYER_SETS, descriptor)) return 'unknown-layer-set';
  if (trace.layerSet !== descriptor) return 'layer-set-mismatch';
  if (trace.contract !== CONTRACT) return 'wrong-contract';
  if (trace.version !== CONTRACT_VERSION) return 'wrong-version';
  if (trace.provenance !== PROVENANCE) return 'wrong-provenance';
  if (trace.seed !== SEED) return 'wrong-seed';
  if (typeof trace.codeCommit !== 'string' || trace.codeCommit === '') {
    return 'missing-commit';
  }
  if (
    typeof trace.lockSha256 !== 'string' ||
    !/^sha256:[0-9a-f]{64}$/.test(trace.lockSha256)
  ) {
    return 'missing-lock';
  }
  const spec = LAYER_SETS[descriptor];
  if (
    trace.counts.hexagons !== spec.hexagons ||
    trace.counts.particles !== spec.particles ||
    (isRoadSet(descriptor) && trace.counts.roads !== spec.roads)
  ) {
    return 'reduced-counts';
  }
  if (!positive(trace.window.width) || !positive(trace.window.height)) {
    return 'missing-window';
  }
  if (!positive(trace.devicePixelRatio)) return 'missing-ratio';
  if (
    trace.canvas.cssWidth !== WALL_CSS_WIDTH ||
    trace.canvas.cssHeight !== WALL_CSS_HEIGHT
  ) {
    return 'wrong-viewport';
  }
  if (trace.cap.value !== CAP_VALUE || trace.cap.label !== CAP_LABEL) {
    return 'wrong-cap';
  }
  if (
    trace.drawingBuffer.width !== WALL_CSS_WIDTH * CAP_VALUE ||
    trace.drawingBuffer.height !== WALL_CSS_HEIGHT * CAP_VALUE
  ) {
    return 'dimension-mismatch';
  }
  if (isRoadSet(descriptor)) {
    if (trace.animation.playbackActive !== true) return 'road-playback-stopped';
    if (trace.animation.reducedMotion !== false) return 'road-reduced-motion';
    const hours = trace.animation.hoursShown;
    if (
      !Array.isArray(hours) ||
      hours.length === 0 ||
      hours.length > roadData.hours.length ||
      hours.some((hour, index) => hour !== roadData.hours[index])
    )
      return 'road-hours-invalid';
  }
  if (trace.profile === PROFILE_SMOKE) return 'smoke-profile';
  if (trace.profile !== PROFILE_GATE) return 'unknown-profile';
  if (trace.camera.completed !== true) return 'incomplete-orbit';
  if (trace.animation.active !== true) return 'stopped-animation';
  if (trace.interruptions.visibilityLost !== false) return 'visibility-lost';
  if (trace.interruptions.resized !== false) return 'resized';
  if (trace.interruptions.contextLost !== false) return 'context-lost';
  const renderer = judgeRenderer(trace.webglRenderer);
  if (renderer) return renderer;
  const native = judgeNative(capture, trace.userAgent);
  if (native) return native;
  if (fresh.durationMs < ORBIT_MS) return 'short-orbit';
  if (!isRoadSet(descriptor) && fresh.shareUnderBudget < SHARE_MINIMUM)
    return 'frame-rate';
  return '';
}

export function validateGate(trace, descriptor, capture) {
  const shaped = shapeOf(trace);
  if (!shaped.ok) return shaped;
  const failure = qualify(trace, shaped.fresh, descriptor, capture);
  if (failure) return fail(failure);
  return { ok: true };
}
