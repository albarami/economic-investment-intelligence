import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SCRIPT = path.join(HERE, '..', 'check-import-boundary.mjs');
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-test-tsconfig-types-'));
after(() => fs.rmSync(root, { recursive: true, force: true }));

function cleanEnv() {
  const home = fs.mkdtempSync(path.join(root, 'home-'));
  const tmp = path.join(home, 'tmp');
  fs.mkdirSync(tmp);
  return {
    PATH: process.env.PATH,
    HOME: home,
    TMPDIR: tmp,
    TMP: tmp,
    TEMP: tmp,
    LANG: 'C',
  };
}

function assertProblem(body, problem) {
  const dir = fs.mkdtempSync(path.join(root, 'case-'));
  fs.mkdirSync(path.join(dir, 'src'));
  const text = `${JSON.stringify(body)}\n`;
  fs.writeFileSync(path.join(dir, 'tsconfig.json'), text);
  const result = spawnSync(process.execPath, [SCRIPT, '--root', dir], {
    encoding: 'utf8',
    env: cleanEnv(),
  });
  const line = `FAIL tsconfig-json: tsconfig.json: ${problem}`;
  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.equal(result.stdout.includes(line), true, result.stdout);
}

test('tsconfig type errors name the bad field', () => {
  const reference =
    'references has an element that is not an object with a string path';
  const cases = [
    [{ extends: ['src', 1] }, 'extends has a non-string element'],
    [{ references: [null] }, reference],
    [{ references: [{ path: 1 }] }, reference],
    [
      { compilerOptions: { paths: { a: ['src', 1] } } },
      'paths has a value that is not an array of strings',
    ],
    [
      { compilerOptions: { rootDirs: ['src', 1] } },
      'rootDirs has a non-string element',
    ],
    [
      { compilerOptions: { typeRoots: ['src', 1] } },
      'typeRoots has a non-string element',
    ],
  ];
  for (const [body, problem] of cases) assertProblem(body, problem);
});
