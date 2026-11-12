import assert from 'node:assert/strict';
import test from 'node:test';
import { stopChild } from '../dev-server-process.mjs';

const HANG_MS = 200;

function exitingChild(field) {
  const child = {
    exitCode: null,
    signalCode: null,
    kills: [],
    listened: 0,
    kill(signal) {
      child.kills.push(signal);
      if (field === 'exitCode') child.exitCode = 0;
      if (field === 'signalCode') child.signalCode = signal;
    },
    once() {
      child.listened += 1;
    },
    removeListener() {},
  };
  return child;
}

function listeningChild() {
  const child = {
    exitCode: null,
    signalCode: null,
    kills: [],
    listened: 0,
    kill(signal) {
      child.kills.push(signal);
    },
    once(event, onExit) {
      child.listened += 1;
      queueMicrotask(() => {
        child.exitCode = 0;
        onExit();
      });
    },
    removeListener() {},
  };
  return child;
}

async function settle(child) {
  let timer;
  const hung = new Promise((resolve) => {
    timer = setTimeout(() => resolve('hung'), HANG_MS);
  });
  try {
    return await Promise.race([stopChild(child).then(() => 'done'), hung]);
  } finally {
    clearTimeout(timer);
  }
}

test('stopChild settles when kill records one exit field', async () => {
  for (const field of ['exitCode', 'signalCode']) {
    const child = exitingChild(field);
    const result = await settle(child);
    assert.equal(result, 'done', field);
    assert.deepEqual(child.kills, ['SIGTERM'], field);
    assert.equal(child.listened, 0, field);
  }
});

test('stopChild clears the wait when the child exits', async () => {
  const child = listeningChild();
  const result = await settle(child);
  assert.equal(result, 'done');
  assert.equal(child.listened, 1);
  assert.deepEqual(child.kills, ['SIGTERM']);
});
