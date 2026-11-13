import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import * as config from '../config.mjs';
import data from '../road-data.json' with { type: 'json' };
import { summariseFrames, validateGate } from '../trace.mjs';
import { verifyEvidence } from '../verify-evidence.mjs';
const capture = {
  role: 'owner',
  host: 'windows-native',
  browser: 'chrome',
  tracePath: 'web/spikes/performance/evidence/synthetic.json',
  sha256: `sha256:${'ab'.repeat(32)}`,
};
function traceFor(layerSet) {
  const timestamps = Array.from({ length: 601 }, (_, index) => index * 50);
  const { frameCount, durationMs, percentiles, shareUnderBudget } =
    summariseFrames(timestamps);
  return {
    contract: config.CONTRACT,
    version: config.CONTRACT_VERSION,
    provenance: config.PROVENANCE,
    seed: config.SEED,
    layerSet,
    profile: config.PROFILE_GATE,
    codeCommit: 'fixture',
    lockSha256: capture.sha256,
    userAgent: 'Windows Chrome',
    webglRenderer: 'Synthetic hardware adapter',
    window: { width: config.WALL_CSS_WIDTH, height: config.WALL_CSS_HEIGHT },
    canvas: {
      cssWidth: config.WALL_CSS_WIDTH,
      cssHeight: config.WALL_CSS_HEIGHT,
    },
    drawingBuffer: {
      width: config.WALL_CSS_WIDTH * config.CAP_VALUE,
      height: config.WALL_CSS_HEIGHT * config.CAP_VALUE,
    },
    devicePixelRatio: config.CAP_VALUE,
    cap: { value: config.CAP_VALUE, label: config.CAP_LABEL },
    counts: { ...config.LAYER_SETS[layerSet] },
    timestamps,
    summary: { frameCount, durationMs, percentiles, shareUnderBudget },
    camera: { completed: true },
    animation: {
      active: true,
      playbackActive: true,
      reducedMotion: false,
      hoursShown: data.hours.slice(0, 2),
    },
    interruptions: {
      visibilityLost: false,
      resized: false,
      contextLost: false,
    },
  };
}
for (const layerSet of Object.keys(config.ROAD_LOADS)) {
  test(`${layerSet} records a slow native result but keeps every other gate`, () => {
    assert.equal(validateGate(traceFor(layerSet), layerSet, capture).ok, true);
    const cases = [
      [
        'road-playback-stopped',
        (trace) => {
          trace.animation.playbackActive = false;
        },
      ],
      [
        'road-reduced-motion',
        (trace) => {
          trace.animation.reducedMotion = true;
        },
      ],
      [
        'road-hours-invalid',
        (trace) => {
          trace.animation.hoursShown = [data.hours.at(-1)];
        },
      ],
      [
        'road-hours-invalid',
        (trace) => {
          trace.animation.hoursShown = [];
        },
      ],
      [
        'road-hours-invalid',
        (trace) => {
          trace.animation.hoursShown = [data.hours[0], data.hours[0]];
        },
      ],
      [
        'reduced-counts',
        (trace) => {
          trace.counts.roads--;
        },
      ],
      [
        'stopped-animation',
        (trace) => {
          trace.animation.active = false;
        },
      ],
      [
        'software-renderer',
        (trace) => {
          trace.webglRenderer = 'SwiftShader';
        },
      ],
      [
        'resized',
        (trace) => {
          trace.interruptions.resized = true;
        },
      ],
      [
        'smoke-profile',
        (trace) => {
          trace.profile = config.PROFILE_SMOKE;
        },
      ],
      [
        'missing-field',
        (trace) => {
          delete trace.animation.playbackActive;
        },
      ],
      [
        'unknown-field',
        (trace) => {
          trace.animation.extra = true;
        },
      ],
    ];
    for (const [failure, change] of cases) {
      const trace = traceFor(layerSet);
      change(trace);
      assert.equal(validateGate(trace, layerSet, capture).failure, failure);
    }
  });
  test(`${layerSet} evidence refuses a missing dedicated capture`, () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'road-evidence-'));
    try {
      fs.writeFileSync(
        path.join(root, 'native-capture.md'),
        'a capture for the original set is insufficient',
      );
      assert.equal(
        verifyEvidence({ root, evidenceDir: root, descriptor: layerSet })
          .failure,
        'missing-native-trace',
      );
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });
}

test('evidence rejects an unlisted road set before reading a capture', () => {
  assert.equal(
    verifyEvidence({ descriptor: 'unlisted', evidenceDir: '.' }).failure,
    'unknown-layer-set',
  );
});
