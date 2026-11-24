import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readdirSync, rmSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '../..');
const ROOT = path.resolve(WEB, '..');
const BROWSERS = path.join(ROOT, 'data', 'tools', 'playwright');

test('photoreal browser specs', (t) => {
  const temporary = mkdtempSync(path.join(os.tmpdir(), 'eii-native-run-'));
  t.after(() => rmSync(temporary, { recursive: true, force: true }));
  assert.equal(
    existsSync(path.join(WEB, 'playwright.photoreal.config.ts')),
    true,
  );
  const result = spawnSync(
    process.execPath,
    [
      path.join(WEB, 'node_modules', 'playwright', 'cli.js'),
      'test',
      '--config',
      'playwright.photoreal.config.ts',
    ],
    {
      cwd: WEB,
      encoding: 'utf8',
      env: {
        PATH: process.env.PATH ?? '',
        HOME: process.env.HOME ?? '',
        TMPDIR: temporary,
        TMP: process.env.TMP ?? '',
        TEMP: process.env.TEMP ?? '',
        LANG: process.env.LANG ?? 'C',
        PLAYWRIGHT_BROWSERS_PATH: BROWSERS,
      },
    },
  );
  assert.deepEqual(
    readdirSync(temporary).filter((name) => name.startsWith('eii-photoreal-')),
    [],
    'browser spec must remove every fixture build folder',
  );
  const output = `${result.stdout ?? ''}\n${result.stderr ?? ''}`;
  if (result.status !== 0) {
    const first = output
      .split('\n')
      .map((line) => line.trim())
      .find((line) => line.length > 0);
    const missing =
      output.includes("Executable doesn't exist") ||
      output.includes('browserType.launch') ||
      output.includes('Failed to launch');
    if (missing) assert.fail(`NOT RUN ${first ?? 'browser'}`);
    assert.equal(result.status, 0, output);
  }
});

test('fixture build refuses an unset output variable before writing', (t) => {
  const temporary = mkdtempSync(path.join(os.tmpdir(), 'eii-native-build-'));
  t.after(() => rmSync(temporary, { recursive: true, force: true }));
  const output = path.join(temporary, 'output');
  const result = spawnSync(
    process.execPath,
    [
      'node_modules/vite/bin/vite.js',
      'build',
      '--config',
      'tests/photoreal/vite.config.ts',
      '--outDir',
      output,
    ],
    {
      cwd: WEB,
      encoding: 'utf8',
      env: {
        PATH: process.env.PATH,
        HOME: process.env.HOME,
        TMPDIR: temporary,
      },
    },
  );
  // The explicit disposable output keeps the plant away from shared dist.
  assert.equal(result.status, 1, 'unset fixture output must fail closed');
  assert.match(result.stderr, /EII_PHOTOREAL_TEST_DIST is not set/);
  assert.equal(existsSync(output), false);
});
