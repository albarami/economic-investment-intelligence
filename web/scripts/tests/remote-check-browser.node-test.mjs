import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { test } from 'node:test';

test('S3-T20 remote-check runner: control, planted cases and result file', () => {
  const run = spawnSync(
    process.execPath,
    [
      path.resolve('node_modules/playwright/cli.js'),
      'test',
      '--config',
      'playwright.remote-check-plants.config.ts',
    ],
    {
      cwd: process.cwd(),
      encoding: 'utf8',
      env: {
        PATH: process.env.PATH ?? '',
        HOME: process.env.HOME ?? '',
        TMPDIR: process.env.TMPDIR ?? '',
        TMP: process.env.TMP ?? '',
        TEMP: process.env.TEMP ?? '',
        LANG: process.env.LANG ?? 'C',
        PLAYWRIGHT_BROWSERS_PATH: path.resolve('../data/tools/playwright'),
        UV_CACHE_DIR:
          process.env.UV_CACHE_DIR ??
          path.resolve('../.overnight/tmp/uv-cache'),
        EII_DECISION_PROVIDER: 'none',
        UV_OFFLINE: '1',
      },
    },
  );
  assert.equal(run.status, 0, run.stdout + run.stderr);
});
