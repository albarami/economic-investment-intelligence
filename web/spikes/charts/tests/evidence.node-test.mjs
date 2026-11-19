import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { checkMatrix } from '../evidence.mjs';
const identity = { contract: 'c', fixture: 'f', build: 'b', lock: 'l' };
const matrix = () => {
  const records = [];
  for (const library of ['echarts', 'plot', 'visx'])
    for (const chart of ['hourly', 'comparison', 'range'])
      for (const language of ['en', 'ar'])
        for (const device of ['laptop', 'phone'])
          for (const run of [1, 2, 3]) {
            const trace = {
              identity,
              device,
              browser: 'native',
              viewport: [640, 320],
              owner: true,
              capture: 'capture',
              active: true,
              latencies: Array(200).fill(99),
              frames: Array(1001).fill(30),
              crossfade: 800,
              heapGrowth: 49,
              storyLoops: 3,
              summary: { p95: 99 },
            };
            const raw = JSON.stringify(trace);
            records.push({
              library,
              chart,
              language,
              device,
              run,
              raw,
              capture: {
                sha256: createHash('sha256').update(raw).digest('hex'),
                ownerAttested: true,
                device,
                browser: 'native',
                viewport: [640, 320],
              },
            });
          }
  return records;
};
test('complete invented matrix is a validator control only', () =>
  assert.equal(checkMatrix(matrix(), identity).ok, true));
for (const [name, mutate] of Object.entries({
  missing: (r) => r.pop(),
  duplicate: (r) => {
    r[1] = r[0];
  },
  malformed: (r) => {
    r[0].raw = '{';
  },
  digest: (r) => {
    r[0].raw += ' ';
  },
  attestation: (r) => {
    r[0].capture.ownerAttested = false;
  },
  device: (r) => {
    r[0].capture.device = 'phone';
  },
  viewport: (r) => {
    r[0].capture.viewport = [1, 1];
  },
  extra: (r) => {
    r[0].unexpected = true;
  },
}))
  test(`matrix plant ${name}`, () => {
    const r = matrix();
    mutate(r);
    assert.equal(checkMatrix(r, identity).ok, false);
  });
