import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '../..');
const SUITE = path.join(
  WEB,
  'eslint-rules/numerals-only-in-fact-chip.test.mjs',
);

function runSuite() {
  return spawnSync(process.execPath, [SUITE], {
    cwd: WEB,
    encoding: 'utf8',
    env: {
      PATH: process.env.PATH,
      HOME: process.env.HOME,
      TMPDIR: process.env.TMPDIR,
      TMP: process.env.TMP,
      TEMP: process.env.TEMP,
      LANG: 'C',
    },
  });
}

test('the numeral rule reports a raw numeral in JSX text', () => {
  const result = runSuite();
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
});
