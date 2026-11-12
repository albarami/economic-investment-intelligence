import assert from 'node:assert/strict';
import { AsyncLocalStorage } from 'node:async_hooks';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test as declareTest } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '..', '..');
const SCRIPT = path.join(WEB, 'scripts', 'check-import-boundary.mjs');
const IMP = 'imp' + 'ort';
const FROM = 'fr' + 'om';

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-test-check-import-boundary-'));
const currentTest = new AsyncLocalStorage();
after(() => fs.rmSync(root, { recursive: true, force: true }));

function bindTest(t) {
  const own = t.test.bind(t);
  t.test = (name, options, fn) => {
    if (typeof options === 'function') {
      fn = options;
      options = undefined;
    }
    const wrapped = (sub) => currentTest.run(sub, () => {
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
  const wrapped = (t) => currentTest.run(t, () => {
    bindTest(t);
    return fn(t);
  });
  if (options === undefined) return declareTest(name, wrapped);
  return declareTest(name, options, wrapped);
}

function tempDir(prefix) {
  const dir = fs.mkdtempSync(path.join(root, prefix));
  currentTest.getStore().after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}

function childTemp(home) {
  const dir = path.join(home, 'tmp');
  fs.mkdirSync(dir);
  return dir;
}

function cleanEnv(extra) {
  const home = tempDir('eii-env-');
  const tmp = childTemp(home);
  const base = { PATH: process.env.PATH, HOME: home, TMPDIR: tmp, TMP: tmp, TEMP: tmp, LANG: 'C' };
  return { ...base, ...extra };
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

function plant(root, rel, text) {
  const full = path.join(root, rel);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, text);
}

function fromLine(spec) {
  return `${IMP} x ${FROM} '${spec}';\n`;
}

function assertFail(result, prefix) {
  assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`);
  const hit = result.stdout.split('\n').some((line) => line.startsWith(prefix));
  assert.equal(hit, true, result.stdout);
}

test('extensionless import through a directory symlink', () => {
  const root = makeRoot();
  const outside = tempDir('eii-out-');
  fs.writeFileSync(path.join(outside, 'secret.ts'), 'export const value = 1;\n');
  fs.symlinkSync(outside, path.join(root, 'src', 'linked'));
  plant(root, 'src/app/use.ts', fromLine('../linked/secret'));
  assertFail(run(['--root', root]), 'FAIL outside-web');
});

test('tsconfig paths through a directory symlink', () => {
  const root = makeRoot();
  const outside = tempDir('eii-out-');
  fs.writeFileSync(path.join(outside, 'secret.ts'), 'export const value = 1;\n');
  fs.symlinkSync(outside, path.join(root, 'src', 'linked'));
  fs.writeFileSync(
    path.join(root, 'tsconfig.json'),
    `${JSON.stringify({ include: ['src'], compilerOptions: { paths: { a: ['./src/linked/*'] } } })}\n`,
  );
  assertFail(run(['--root', root]), 'FAIL tsconfig-outside');
});

test('root is a symbolic link to the shell', () => {
  const dir = tempDir('eii-link-');
  const target = path.join(dir, 'web');
  fs.symlinkSync(WEB, target);
  try {
    const result = run(['--root', target]);
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
  } finally {
    fs.unlinkSync(target);
  }
});
