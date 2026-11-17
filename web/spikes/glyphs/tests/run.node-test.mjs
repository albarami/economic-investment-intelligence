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
// the isolation test below maps the same destinations onto a disposable
// tree and plants an artifact at the performance runner's configured
// destinations to prove it. The root is injectable for that mapping and
// defaults to the real spike.
function noOutputWatchDirs(root = SPIKE) {
  return [
    root,
    path.join(root, 'test-results'),
    path.join(root, '..', '..', '..', 'data', 'glyph-captures'),
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

// Each browser config's own configured destinations, as written in the
// config file: its outputDir and the files its reporters name, resolved
// against the config's directory the way Playwright resolves them.
function configDestinations(spike) {
  const text = fs.readFileSync(
    path.join(spike, 'playwright.config.ts'),
    'utf8',
  );
  const outputDir = /outputDir:\s*'([^']+)'/.exec(text);
  if (outputDir === null) {
    throw new Error(
      `${path.join(spike, 'playwright.config.ts')} names no outputDir`,
    );
  }
  const reportFiles = [...text.matchAll(/outputFile:\s*'([^']+)'/g)].map(
    (match) => match[1],
  );
  return { outputDir: outputDir[1], reportFiles };
}

test('performance artifacts cannot affect the glyph no-output watch; a glyph artifact in it fails it', () => {
  const baselines = path.join(SPIKE, 'tests', 'baselines');
  const command = [
    process.execPath,
    new URL('./run.mjs', import.meta.url).pathname,
  ];
  const glyphConfig = configDestinations(SPIKE);
  const performanceSpike = path.join(SPIKE, '..', 'performance');
  const performanceConfig = configDestinations(performanceSpike);
  const runCommand = () =>
    spawnSync(command[0], command.slice(1), {
      encoding: 'utf8',
      env: { ...process.env, CI: 'true' },
    });
  const missingBaselineDiagnostic =
    /missing baseline: spikes\/glyphs\/tests\/baselines\/arabic-labels-chromium-linux\.png/;
  // Every temporary folder is registered here the moment it is made and the
  // whole tree is removed in the finally below; no plant ever lands in a
  // live runner's output folder.
  const temporary = [];
  try {
    // A disposable mirror of the artifact layout: the web root, the two
    // browser spikes and the captures folder at the same relative depth the
    // watch helper resolves them from the glyph spike.
    const mirror = fs.mkdtempSync(
      path.join(os.tmpdir(), 'eii-isolation-mirror-'),
    );
    temporary.push(mirror);
    const glyphSpike = path.join(mirror, 'web', 'spikes', 'glyphs');
    const mirrorPerformanceSpike = path.join(
      mirror,
      'web',
      'spikes',
      'performance',
    );
    const watched = noOutputWatchDirs(glyphSpike);
    for (const dir of [...watched, mirrorPerformanceSpike]) {
      fs.mkdirSync(dir, { recursive: true });
    }
    // Pin the configured destinations to this mapping: the glyph runner's
    // own destinations are watched, and the performance runner's
    // configured destinations never are. That is the isolation this test
    // plants; a config change that moves a destination across the mapping
    // fails here.
    const insideWatch = (target) =>
      watched.some(
        (dir) => target === dir || target.startsWith(`${dir}${path.sep}`),
      );
    const mappedGlyphOutputDir = path.join(glyphSpike, glyphConfig.outputDir);
    assert.equal(insideWatch(mappedGlyphOutputDir), true);
    const performanceDestinations = [
      path.join(mirrorPerformanceSpike, performanceConfig.outputDir),
      ...performanceConfig.reportFiles.map((file) =>
        path.join(mirrorPerformanceSpike, file),
      ),
    ];
    for (const destination of performanceDestinations) {
      assert.equal(insideWatch(destination), false, destination);
    }
    const plant = (file) => {
      fs.mkdirSync(path.dirname(file), { recursive: true });
      fs.writeFileSync(file, 'planted\n');
    };
    const held = fs.mkdtempSync(
      path.join(os.tmpdir(), 'eii-glyphs-baselines-'),
    );
    temporary.push(held);
    withHeldFiles(baselines, held, () => {
      // A performance run failing beside this one writes its artifacts at
      // its configured destinations, mapped here into the disposable tree:
      // a failure context in its outputDir and each file its reporters name.
      const before = watched.map((dir) => listFiles(dir));
      plant(
        path.join(
          mirrorPerformanceSpike,
          performanceConfig.outputDir,
          'error-context.md',
        ),
      );
      for (const file of performanceConfig.reportFiles) {
        plant(path.join(mirrorPerformanceSpike, file));
      }
      const beside = runCommand();
      assert.equal(beside.status, 1, beside.stderr);
      assert.equal(beside.stdout, '');
      assert.match(beside.stderr, missingBaselineDiagnostic);
      assert.deepEqual(
        watched.map((dir) => listFiles(dir)),
        before,
      );

      // An unexpected glyph artifact inside the watched destinations still
      // fails the same comparison.
      const beforeGlyph = watched.map((dir) => listFiles(dir));
      plant(path.join(mappedGlyphOutputDir, 'unexpected.md'));
      const inside = runCommand();
      assert.equal(inside.status, 1, inside.stderr);
      assert.equal(inside.stdout, '');
      assert.match(inside.stderr, missingBaselineDiagnostic);
      assert.notDeepEqual(
        watched.map((dir) => listFiles(dir)),
        beforeGlyph,
      );
    });
  } finally {
    for (const dir of temporary) {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  }
});
