import test from 'node:test';
import assert from 'node:assert/strict';
import { judge } from '../trace.mjs';
const identity = { contract: 'c', fixture: 'f', build: 'b', lock: 'l' };
const valid = () => ({
  identity,
  device: 'laptop',
  browser: 'native',
  viewport: [1200, 800],
  owner: true,
  capture: 'digest',
  active: true,
  latencies: Array(200).fill(99),
  frames: Array(1001).fill(30),
  crossfade: 800,
  heapGrowth: 49,
  storyLoops: 3,
  summary: { p95: 99 },
});
test('valid threshold control', () =>
  assert.equal(judge(valid(), identity).ok, true));
for (const [name, patch] of Object.entries({
  missing: null,
  malformed: [],
  forged: { summary: { p95: 1 } },
  stale: { identity: { ...identity, build: 'old' } },
  headless: { browser: 'HeadlessChrome' },
  capture: { capture: '' },
  stopped: { active: false },
  latencyEqual: { latencies: Array(200).fill(100), summary: { p95: 100 } },
  latencyAbove: { latencies: Array(200).fill(101), summary: { p95: 101 } },
  playbackEqual: { frames: Array(1001).fill(1000 / 30) },
  playbackBelow: { frames: Array(1001).fill(34) },
  frame: { frames: [34, ...Array(1000).fill(30)] },
  fade: { crossfade: 801 },
  heapEqual: { heapGrowth: 50 },
  heapAbove: { heapGrowth: 51 },
  story: { storyLoops: 2 },
}))
  test(`trace plant ${name}`, () =>
    assert.equal(
      judge(
        patch === null || Array.isArray(patch)
          ? patch
          : { ...valid(), ...patch },
        identity,
      ).ok,
      false,
    ));
