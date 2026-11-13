import assert from 'node:assert/strict';
import { test } from 'node:test';
import { EMPTY_CANVAS_MAX_MEDIAN_MS, judgeEmptyCanvas } from '../trace.mjs';

function regular(intervalMs, intervals) {
  const stamps = [];
  for (let index = 0; index <= intervals; index += 1) {
    stamps.push(index * intervalMs);
  }
  return stamps;
}

test('the empty-canvas threshold is a median interval of 17.5 ms', () => {
  assert.equal(EMPTY_CANVAS_MAX_MEDIAN_MS, 17.5);
});

test('a 60 Hz empty canvas passes the environment judgement', () => {
  const result = judgeEmptyCanvas(regular(16.67, 120));
  assert.equal(result.ok, true, result.failure);
  assert.equal(result.failure, '');
  assert.equal(result.framesPerSecond, 59.99);
});

test('a 59.94 Hz empty canvas passes the environment judgement', () => {
  const result = judgeEmptyCanvas(regular(1000 / 59.94, 120));
  assert.equal(result.ok, true, result.failure);
  assert.equal(result.framesPerSecond, 59.94);
});

test('a 50 Hz empty canvas is refused as a capped frame rate', () => {
  const result = judgeEmptyCanvas(regular(20, 120));
  assert.equal(result.ok, false);
  assert.equal(result.failure, 'capped-frame-rate');
  assert.equal(result.framesPerSecond, 50);
});

test('a 30 Hz empty canvas is refused as a capped frame rate', () => {
  const result = judgeEmptyCanvas(regular(1000 / 30, 120));
  assert.equal(result.ok, false);
  assert.equal(result.failure, 'capped-frame-rate');
  assert.equal(result.framesPerSecond, 30);
});

test('fewer than two empty-canvas timestamps are refused', () => {
  const result = judgeEmptyCanvas([0]);
  assert.equal(result.ok, false);
  assert.equal(result.failure, 'capped-frame-rate');
  assert.equal(result.framesPerSecond, 0);
});
