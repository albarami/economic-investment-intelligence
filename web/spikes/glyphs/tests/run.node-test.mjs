import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { comparisonReport, gateDetail, runChild, runSuite } from './run.mjs';

const SPIKE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

test('a non-zero child status propagates', () => {
  const status = runChild(process.execPath, ['-e', 'process.exit(2)']);
  assert.equal(status, 2);
});

test('a missing browser is refused', () => {
  const result = gateDetail({
    capture: false,
    ci: undefined,
    browserPresent: false,
  });
  assert.equal(result.status, 1);
  assert.match(result.detail, /spike:glyphs:install-browser/);
});

test('the suite passes with no dist folder', async () => {
  const dist = path.join(SPIKE, 'dist');
  const heldParent = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-glyphs-held-'));
  const held = path.join(heldParent, 'dist');
  const had = fs.existsSync(dist);
  if (had) fs.renameSync(dist, held);
  try {
    assert.equal(fs.existsSync(dist), false);
    const status = await runSuite();
    assert.equal(status, 0);
    assert.equal(fs.existsSync(dist), false);
  } finally {
    if (had && fs.existsSync(held)) fs.renameSync(held, dist);
    fs.rmSync(heldParent, { recursive: true, force: true });
  }
});

test('the capture command refuses outside CI', () => {
  const result = spawnSync(
    process.execPath,
    [new URL('./run.mjs', import.meta.url).pathname, '--capture'],
    {
      encoding: 'utf8',
      env: { ...process.env, CI: '' },
    },
  );
  assert.equal(result.status, 2);
  assert.match(result.stderr, /CI environment/);
});

test('the browser suite reports its real status', async () => {
  const status = await runSuite();
  assert.equal(status, 0);
});

function listFiles(root) {
  if (!fs.existsSync(root)) return [];
  const found = [];
  const pending = [root];
  while (pending.length > 0) {
    const current = pending.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) pending.push(full);
      else found.push(full);
    }
  }
  found.sort();
  return found;
}

test('stripped CI reports no pixel comparison and a direct run names a missing baseline', () => {
  const stripped = {};
  for (const name of [
    'PATH',
    'HOME',
    'TMPDIR',
    'LANG',
    'NO_COLOR',
    'EII_DECISION_PROVIDER',
  ]) {
    if (process.env[name] !== undefined) stripped[name] = process.env[name];
  }
  assert.equal(Object.hasOwn(stripped, 'CI'), false);
  const runModule = new URL('./run.mjs', import.meta.url).href;
  const reported = spawnSync(
    process.execPath,
    [
      '--input-type=module',
      '-e',
      [
        `import { comparisonReport } from ${JSON.stringify(runModule)};`,
        'const report = comparisonReport(process.env.CI);',
        'if (report.compared) process.exit(3);',
        'process.stdout.write(report.line);',
      ].join('\n'),
    ],
    { encoding: 'utf8', env: stripped },
  );
  assert.equal(reported.status, 0, reported.stderr);
  assert.equal(comparisonReport(undefined).compared, false);
  assert.equal(comparisonReport('').compared, false);
  assert.match(reported.stdout, /no pixel was compared/);
  assert.match(reported.stdout, /hosted job's own step/);
  assert.match(reported.stdout, /direct run of the command with CI=true/);
  assert.match(reported.stdout, /\.\/eii test, anywhere/);

  const baselines = path.join(SPIKE, 'tests', 'baselines');
  const held = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-glyphs-baselines-'));
  const moved = [];
  if (fs.existsSync(baselines)) {
    for (const name of fs.readdirSync(baselines)) {
      const from = path.join(baselines, name);
      const to = path.join(held, name);
      fs.renameSync(from, to);
      moved.push([from, to]);
    }
  }
  const watched = [
    SPIKE,
    path.join(SPIKE, '..', '..', 'test-results'),
    path.join(SPIKE, '..', '..', 'playwright-report'),
    path.join(SPIKE, '..', '..', '..', 'data', 'glyph-captures'),
  ];
  const before = watched.map((dir) => listFiles(dir));
  try {
    const result = spawnSync(
      process.execPath,
      [new URL('./run.mjs', import.meta.url).pathname],
      { encoding: 'utf8', env: { ...process.env, CI: 'true' } },
    );
    assert.equal(result.status, 1, result.stderr);
    assert.equal(result.stdout, '');
    assert.match(
      result.stderr,
      /missing baseline: spikes\/glyphs\/tests\/baselines\/arabic-labels-chromium-linux\.png/,
    );
    assert.deepEqual(
      watched.map((dir) => listFiles(dir)),
      before,
    );
  } finally {
    for (const [from, to] of moved) fs.renameSync(to, from);
    fs.rmSync(held, { recursive: true, force: true });
  }
});
