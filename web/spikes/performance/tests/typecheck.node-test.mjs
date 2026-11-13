import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const web = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../..',
);

test('the performance spike typechecks', () => {
  const tsc = path.join(web, 'node_modules', 'typescript', 'lib', 'tsc.js');
  const result = spawnSync(
    process.execPath,
    [
      tsc,
      '-p',
      'spikes/performance/tsconfig.json',
      '--noEmit',
      '--pretty',
      'false',
    ],
    { cwd: web, encoding: 'utf8' },
  );
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
});
