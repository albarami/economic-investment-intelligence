import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { judge } from '../trace.mjs';
test('strict policy permits inclusive frame and fade boundaries', () => {
  const identity = {};
  const trace = {
    identity,
    device: 'phone',
    browser: 'native',
    viewport: [400, 800],
    owner: true,
    capture: 'invented-unit-control',
    active: true,
    latencies: Array(200).fill(99.999),
    frames: Array(1000).fill(33),
    crossfade: 800,
    heapGrowth: 49.999,
    storyLoops: 3,
    summary: { p95: 99.999 },
  };
  assert.equal(judge(trace, identity).ok, true);
});
test('contract preserves plan budgets and fixture matrix', () => {
  const c = JSON.parse(fs.readFileSync('spikes/charts/contract.json', 'utf8'));
  assert.deepEqual(c.fixtures, ['hourly', 'comparison', 'range']);
  assert.equal(c.p95ExclusiveMs, 100);
  assert.equal(c.fpsExclusiveMinimum, 30);
  assert.equal(c.frameMaximumMs, 33);
  assert.equal(c.crossfadeMaximumMs, 800);
  assert.equal(c.fullStoryHeapExclusiveMB, 50);
});
test('each adapter validates closed workload before rendering', () => {
  for (const library of ['echarts', 'plot', 'visx']) {
    const text = fs.readFileSync(
      `spikes/charts/adapters/${library}.tsx`,
      'utf8',
    );
    assert.match(text, /workload\(input\)/);
    assert.doesNotMatch(text, /fetch\(|eval\(|new Function/);
  }
});
