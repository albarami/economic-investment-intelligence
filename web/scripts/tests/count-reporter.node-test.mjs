import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '..', '..');
const REPORTER = path.join(WEB, 'scripts', 'count-reporter.mjs');
const SKIP = 's' + 'kip';
const TODO = 'to' + 'do';
const KIND_SKIP = SKIP;

function childEnv(home) {
  return {
    PATH: process.env.PATH,
    HOME: home,
    TMPDIR: home,
    LANG: 'C',
  };
}

function runCase(files) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-count-'));
  try {
    const written = [];
    for (const [name, text] of Object.entries(files)) {
      const full = path.join(home, name);
      fs.mkdirSync(path.dirname(full), { recursive: true });
      fs.writeFileSync(full, text);
      written.push(full);
    }
    const destination = path.join(home, 'records.jsonl');
    const child = spawnSync(
      process.execPath,
      [
        '--test',
        '--test-reporter=spec',
        '--test-reporter-destination=stdout',
        `--test-reporter=${pathToFileURL(REPORTER).href}`,
        `--test-reporter-destination=${destination}`,
        ...written,
      ],
      { encoding: 'utf8', cwd: home, env: childEnv(home) },
    );
    const raw = fs.existsSync(destination)
      ? fs.readFileSync(destination, 'utf8')
      : '';
    const records = raw
      .split('\n')
      .filter((item) => item.length > 0)
      .map((item) => JSON.parse(item));
    return { child, records };
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
}

function expectRecords(result, expected, status) {
  const message = result.child.stderr || result.child.stdout || '';
  if (status !== undefined) {
    assert.equal(result.child.status, status, message);
  }
  const end = result.records.filter((item) => item.end === true);
  const tests = result.records.filter((item) => item.end !== true);
  tests.sort((left, right) => String(left.n).localeCompare(String(right.n)));
  const wanted = [...expected].sort((left, right) =>
    String(left.n).localeCompare(String(right.n)),
  );
  assert.deepEqual(end, [{ end: true }], message);
  assert.deepEqual(tests, wanted, message);
}

test('counts each test once and not the suites', () => {
  const source = `
import test from 'node:test';
test.describe('group', () => {
  test('a', () => {});
  test('b', () => {});
});
test('top', () => {});
`;
  const result = runCase({ 'case.node-test.mjs': source });
  expectRecords(
    result,
    [
      { s: 'pass', n: 'a', r: '' },
      { s: 'pass', n: 'b', r: '' },
      { s: 'pass', n: 'top', r: '' },
    ],
    0,
  );
});

test('fail', () => {
  const source = `
import test from 'node:test';
import assert from 'node:assert/strict';
test('bad', () => { assert.equal(1, 2); });
test('good', () => { assert.equal(1, 1); });
`;
  const result = runCase({ 'case.node-test.mjs': source });
  expectRecords(
    result,
    [
      { s: 'fail', n: 'bad', r: '' },
      { s: 'pass', n: 'good', r: '' },
    ],
    1,
  );
});

test('reasons', () => {
  const source = `
import test from 'node:test';
test('later case', { ${SKIP}: 'later' }, () => {});
test('flag case', { ${SKIP}: true }, () => {});
test('standing case', { ${SKIP}: 'OI-10 no database' }, () => {});
`;
  const result = runCase({ 'case.node-test.mjs': source });
  expectRecords(result, [
    { s: KIND_SKIP, n: 'later case', r: 'later' },
    { s: KIND_SKIP, n: 'flag case', r: '' },
    { s: KIND_SKIP, n: 'standing case', r: 'OI-10 no database' },
  ]);
});

test('deferred', () => {
  const source = `
import test from 'node:test';
test('passes', { ${TODO}: 'later' }, () => {});
test('fails', { ${TODO}: 'later' }, () => { throw new Error('no'); });
`;
  const result = runCase({ 'case.node-test.mjs': source });
  expectRecords(result, [
    { s: KIND_SKIP, n: 'fails', r: 'later' },
    { s: KIND_SKIP, n: 'passes', r: 'later' },
  ]);
});

test('subtests', () => {
  const passing = `
import test from 'node:test';
test('parent', async (t) => {
  await t.test('one', () => {});
  await t.test('two', () => {});
});
`;
  const failing = `
import test from 'node:test';
test('parent', async (t) => {
  await t.test('bad', () => { throw new Error('x'); });
});
`;
  const first = runCase({ 'pass.node-test.mjs': passing });
  expectRecords(
    first,
    [
      { s: 'pass', n: 'one', r: '' },
      { s: 'pass', n: 'parent', r: '' },
      { s: 'pass', n: 'two', r: '' },
    ],
    0,
  );
  const second = runCase({ 'fail.node-test.mjs': failing });
  expectRecords(second, [{ s: 'fail', n: 'bad', r: '' }], 1);
});

test('import error', () => {
  const homeName = 'missing.node-test.mjs';
  const result = runCase({
    [homeName]: "import './no-such-module.mjs';\n",
  });
  const fails = result.records.filter((item) => item.s === 'fail');
  assert.equal(fails.length, 1, result.child.stderr);
  assert.equal(fails[0].n.endsWith(homeName), true, fails[0].n);
  assert.deepEqual(
    result.records.filter((item) => item.end === true),
    [{ end: true }],
    result.child.stderr,
  );
});

test('unsettled test', () => {
  const source = `
import test from 'node:test';
test('hangs', { timeout: 30 }, () => new Promise(() => {}));
`;
  const result = runCase({ 'hang.node-test.mjs': source });
  expectRecords(result, [{ s: 'fail', n: 'hangs', r: '' }]);
});

test('no tests', () => {
  const source = `
import test from 'node:test';
test.describe('empty', () => {});
`;
  const result = runCase({ 'empty.node-test.mjs': source });
  expectRecords(result, [], 0);
});

test('suites set aside', () => {
  const source = `
import test from 'node:test';
test.describe('alpha', { ${SKIP}: 'suite reason' }, () => {
  test('a', () => {});
  test('b', () => {});
});
test.describe('beta', { ${SKIP}: true }, () => {
  test('c', () => {});
});
test.describe.${SKIP}('gamma', () => {
  test('d', () => {});
});
test('passes', () => {});
`;
  const result = runCase({ 'suites.node-test.mjs': source });
  expectRecords(result, [
    { s: KIND_SKIP, n: 'alpha', r: 'suite reason' },
    { s: KIND_SKIP, n: 'beta', r: '' },
    { s: KIND_SKIP, n: 'gamma', r: '' },
    { s: 'pass', n: 'passes', r: '' },
  ]);
});

test('file without a test', () => {
  const result = runCase({ 'blank.node-test.mjs': '' });
  const skips = result.records.filter((item) => item.s === KIND_SKIP);
  assert.equal(skips.length, 1, result.child.stderr);
  assert.equal(skips[0].r, 'the file registers no test');
  assert.equal(skips[0].n.endsWith('blank.node-test.mjs'), true, skips[0].n);
  assert.deepEqual(
    result.records.filter((item) => item.end === true),
    [{ end: true }],
    result.child.stderr,
  );
});

test('failing hook', () => {
  const source = `
import test from 'node:test';
test.describe('group', () => {
  test.before(() => { throw new Error('boom'); });
  test('a', () => {});
  test('b', () => {});
});
`;
  const result = runCase({ 'hook.node-test.mjs': source });
  expectRecords(result, [
    { s: 'fail', n: 'a', r: '' },
    { s: 'fail', n: 'b', r: '' },
  ]);
});
