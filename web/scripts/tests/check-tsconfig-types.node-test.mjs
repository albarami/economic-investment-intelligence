import assert from 'node:assert/strict';
import { AsyncLocalStorage } from 'node:async_hooks';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test as declareTest } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SCRIPT = path.join(HERE, '..', 'check-import-boundary.mjs');
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-test-tsconfig-types-'));
const currentTest = new AsyncLocalStorage();
after(() => fs.rmSync(root, { recursive: true, force: true }));

function bindTest(t) {
  const own = t.test.bind(t);
  t.test = (name, options, fn) => {
    if (typeof options === 'function') {
      fn = options;
      options = undefined;
    }
    const wrapped = (sub) =>
      currentTest.run(sub, () => {
        bindTest(sub);
        return fn(sub);
      });
    if (options === undefined) return own(name, wrapped);
    return own(name, options, wrapped);
  };
}

function test(name, options, fn) {
  if (typeof options === 'function') {
    fn = options;
    options = undefined;
  }
  const wrapped = (t) =>
    currentTest.run(t, () => {
      bindTest(t);
      return fn(t);
    });
  if (options === undefined) return declareTest(name, wrapped);
  return declareTest(name, options, wrapped);
}

function tempDir(prefix) {
  const dir = fs.mkdtempSync(path.join(root, prefix));
  currentTest
    .getStore()
    .after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}

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

function run(args, env, cwd) {
  return spawnSync(process.execPath, [SCRIPT, ...args], {
    encoding: 'utf8',
    env: env ?? cleanEnv(),
    cwd,
  });
}

function makeRoot() {
  const root = tempDir('eii-bound-');
  fs.mkdirSync(path.join(root, 'src', 'app'), { recursive: true });
  fs.writeFileSync(
    path.join(root, 'tsconfig.json'),
    `${JSON.stringify({ compilerOptions: { strict: true }, include: ['src'] })}\n`,
  );
  return root;
}

function assertFail(result, prefix) {
  assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`);
  const hit = result.stdout.split('\n').some((line) => line.startsWith(prefix));
  assert.equal(hit, true, result.stdout);
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

test('tsconfig windows paths on this platform', async (t) => {
  for (const entry of ['..\\..\\core', 'C:/core']) {
    await t.test(JSON.stringify(entry), () => {
      const root = makeRoot();
      fs.writeFileSync(
        path.join(root, 'tsconfig.json'),
        `${JSON.stringify({ include: [entry] })}\n`,
      );
      assertFail(
        run(['--root', root], cleanEnv(), root),
        'FAIL tsconfig-outside',
      );
    });
  }
});

test('tsconfig entries with the wrong element type', async (t) => {
  const cases = [
    ['paths number', { compilerOptions: { paths: { a: 1 } } }],
    ['paths string', { compilerOptions: { paths: { a: '..' } } }],
    ['references string', { references: ['../core'] }],
    ['include number', { include: [1] }],
  ];
  for (const [name, body] of cases) {
    await t.test(name, () => {
      const root = makeRoot();
      fs.writeFileSync(
        path.join(root, 'tsconfig.json'),
        `${JSON.stringify(body)}\n`,
      );
      assertFail(run(['--root', root]), 'FAIL tsconfig-json: tsconfig.json');
    });
  }
});
