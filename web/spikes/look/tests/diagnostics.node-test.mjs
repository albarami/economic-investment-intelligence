import assert from 'node:assert/strict';
import { test } from 'node:test';
import FailureReporter, { browserFailures } from './failure-reporter.mjs';

test('a failed browser case is named even when child output is hidden', () => {
  const lines = [];
  const reporter = new FailureReporter((line) => lines.push(line));
  reporter.onTestEnd(
    { titlePath: () => ['', 'look.spec.ts', 'planted broken range'] },
    { status: 'failed' },
  );
  assert.deepEqual(lines, [
    'EII_LOOK_FAILURE:look.spec.ts › planted broken range\n',
  ]);
});

test('a passing browser case emits no failure diagnostic', () => {
  const lines = [];
  const reporter = new FailureReporter((line) => lines.push(line));
  reporter.onTestEnd(
    { titlePath: () => ['look.spec.ts', 'working range'] },
    { status: 'passed' },
  );
  assert.deepEqual(lines, []);
});

test('failure names survive noisy child output and include every failed case', () => {
  const lines = [];
  const reporter = new FailureReporter((line) => lines.push(line));
  for (const status of ['failed', 'timedOut', 'interrupted']) {
    reporter.onTestEnd(
      { titlePath: () => ['look.spec.ts', status] },
      { status },
    );
  }
  assert.deepEqual(
    browserFailures(`normal progress\n${lines.join('')}summary\n`),
    [
      'look.spec.ts › failed',
      'look.spec.ts › timedOut',
      'look.spec.ts › interrupted',
    ],
  );
});
