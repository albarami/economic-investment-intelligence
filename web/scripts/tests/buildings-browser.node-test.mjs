import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readdirSync, rmSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const WEB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

function runSpec(t, plant = '') {
  const temporary = mkdtempSync(path.join(os.tmpdir(), 'eii-buildings-run-'));
  t.after(() => rmSync(temporary, { recursive: true, force: true }));
  const result = spawnSync(
    process.execPath,
    [
      path.join(WEB, 'node_modules/playwright/cli.js'),
      'test',
      '--config',
      'playwright.buildings.config.ts',
    ],
    {
      cwd: WEB,
      encoding: 'utf8',
      timeout: 120000,
      env: {
        PATH: process.env.PATH ?? '',
        HOME: temporary,
        TMPDIR: temporary,
        LANG: 'C',
        UV_OFFLINE: '1',
        EII_DECISION_PROVIDER: 'none',
        EII_BUILDINGS_PLANT: plant,
      },
    },
  );
  assert.deepEqual(
    readdirSync(temporary).filter((name) =>
      name.startsWith('eii-buildings-scene-'),
    ),
    [],
    'buildings_fixture_cleanup',
  );
  return {
    status: result.status,
    output: `buildings_shadow_renderer_failed: ${result.error?.message ?? ''}\n${result.stdout}\n${result.stderr}`,
  };
}

test('offline buildings WebGL shadow rendering contract', (t) => {
  const result = runSpec(t);
  assert.equal(result.status, 0, result.output);
  console.log(
    result.output.split('\n').find((line) => line.startsWith('{"renderer":')),
  );
});

for (const [plant, reason] of [
  ['shadow-off', 'buildings_shadow_pass_not_drawn'],
  ['caster-removed', 'buildings_shadow_pass_not_drawn'],
  ['receiver-removed', 'buildings_receiver_missing'],
  ['second-shell', 'buildings_second_shell'],
  ['foreign-origin', 'buildings_external_request'],
  ['unknown-asset', 'buildings_unknown_asset'],
]) {
  test(`rendering plant ${plant} fails specifically with ${reason}`, (t) => {
    const result = runSpec(t, plant);
    assert.equal(result.status, 1, result.output);
    assert.match(result.output, new RegExp(`Error: ${reason}\\n`));
    console.log(`${plant}: playwright red exit ${result.status}, ${reason}`);
  });
}
