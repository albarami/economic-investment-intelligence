import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { comparisonReport, gateDetail, runChild, runSuite } from './run.mjs';
import { withHeldFiles } from './hold-files.mjs';

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
  if (had) {
    fs.cpSync(dist, held, { recursive: true });
    fs.rmSync(dist, { recursive: true, force: true });
  }
  try {
    assert.equal(fs.existsSync(dist), false);
    const status = await runSuite();
    assert.equal(status, 0);
    assert.equal(fs.existsSync(dist), false);
  } finally {
    if (had && fs.existsSync(held)) {
      fs.rmSync(dist, { recursive: true, force: true });
      fs.cpSync(held, dist, { recursive: true });
    }
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

// The destinations the glyph runner itself can write: this spike's tree,
// which contains the Playwright outputDir this spike's config names, and the
// captures folder of the hosted pixel-comparison step. The no-output
// assertion watches these and nothing else, so another browser runner
// writing its own artifacts beside this suite cannot change these listings;
// the isolation test below plants a performance artifact to prove it.
function noOutputWatchDirs() {
  return [
    SPIKE,
    path.join(SPIKE, 'test-results'),
    path.join(SPIKE, '..', '..', '..', 'data', 'glyph-captures'),
  ];
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
  const watched = noOutputWatchDirs();
  withHeldFiles(baselines, held, () => {
    const before = watched.map((dir) => listFiles(dir));
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
  });
});

test('performance artifacts cannot affect the glyph no-output watch; a glyph artifact in it fails it', () => {
  const baselines = path.join(SPIKE, 'tests', 'baselines');
  const held = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-glyphs-baselines-'));
  const command = [
    process.execPath,
    new URL('./run.mjs', import.meta.url).pathname,
  ];
  // Where a performance browser run writes its artifacts: its own spike's
  // folder, and the Playwright default at the web root that both runners
  // shared before each config named its own outputDir.
  const performanceArtifactRoots = [
    path.join(SPIKE, '..', 'performance', 'test-results'),
    path.join(SPIKE, '..', '..', 'test-results'),
  ];
  // The glyph runner's own artifact folder, the destination its Playwright
  // outputDir names; it is inside the watch.
  const glyphArtifactRoot = path.join(SPIKE, 'test-results');
  const planted = [];
  const plantArtifact = (root) => {
    if (!fs.existsSync(root)) fs.mkdirSync(root, { recursive: true });
    // Only this uniquely named folder is removed again: the root may be in
    // use by a concurrent browser run, so it is left as it is.
    const folder = fs.mkdtempSync(path.join(root, 'eii-isolation-plant-'));
    fs.writeFileSync(path.join(folder, 'error-context.md'), 'planted\n');
    planted.push(folder);
  };
  try {
    withHeldFiles(baselines, held, () => {
      // A performance run failing beside this one writes its artifacts inside
      // the window between the two listings.
      const before = noOutputWatchDirs().map((dir) => listFiles(dir));
      for (const root of performanceArtifactRoots) plantArtifact(root);
      const beside = spawnSync(command[0], command, {
        encoding: 'utf8',
        env: { ...process.env, CI: 'true' },
      });
      assert.equal(beside.status, 1, beside.stderr);
      assert.deepEqual(
        noOutputWatchDirs().map((dir) => listFiles(dir)),
        before,
      );

      // An unexpected glyph artifact in the watched destinations still fails
      // the same comparison.
      const beforeGlyph = noOutputWatchDirs().map((dir) => listFiles(dir));
      plantArtifact(glyphArtifactRoot);
      const inside = spawnSync(command[0], command, {
        encoding: 'utf8',
        env: { ...process.env, CI: 'true' },
      });
      assert.equal(inside.status, 1, inside.stderr);
      assert.notDeepEqual(
        noOutputWatchDirs().map((dir) => listFiles(dir)),
        beforeGlyph,
      );
    });
  } finally {
    for (const folder of planted) {
      fs.rmSync(folder, { recursive: true, force: true });
    }
  }
});
