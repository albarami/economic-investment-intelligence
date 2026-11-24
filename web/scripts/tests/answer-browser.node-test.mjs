import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '../..');
const ROOT = path.resolve(WEB, '..');
const BROWSERS = path.join(ROOT, 'data', 'tools', 'playwright');

test('answer browser specs', () => {
  assert.equal(existsSync(path.join(WEB, 'playwright.answer.config.ts')), true);
  const result = spawnSync(
    process.execPath,
    [
      path.join(WEB, 'node_modules', 'playwright', 'cli.js'),
      'test',
      '--config',
      'playwright.answer.config.ts',
    ],
    {
      cwd: WEB,
      encoding: 'utf8',
      env: {
        PATH: process.env.PATH ?? '',
        HOME: process.env.HOME ?? '',
        TMPDIR: process.env.TMPDIR ?? '',
        TMP: process.env.TMP ?? '',
        TEMP: process.env.TEMP ?? '',
        LANG: process.env.LANG ?? 'C',
        PLAYWRIGHT_BROWSERS_PATH: BROWSERS,
        UV_CACHE_DIR:
          process.env.UV_CACHE_DIR ??
          path.join(ROOT, '.overnight', 'tmp', 'uv-cache'),
        UV_OFFLINE: '1',
      },
    },
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
