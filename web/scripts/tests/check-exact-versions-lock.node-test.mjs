import assert from 'node:assert/strict';
import { AsyncLocalStorage } from 'node:async_hooks';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test as declareTest } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SCRIPT = path.join(HERE, '..', 'check-exact-versions.mjs');

const root = fs.mkdtempSync(
  path.join(os.tmpdir(), 'eii-test-check-exact-versions-lock-'),
);
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

function childTemp(home) {
  const dir = path.join(home, 'tmp');
  fs.mkdirSync(dir);
  return dir;
}

function cleanEnv(extra) {
  const home = tempDir('eii-env-');
  const tmp = childTemp(home);
  const base = {
    PATH: process.env.PATH,
    HOME: home,
    TMPDIR: tmp,
    TMP: tmp,
    TEMP: tmp,
    LANG: 'C',
  };
  return { ...base, ...extra };
}

function run(root) {
  return spawnSync(process.execPath, [SCRIPT, '--root', root], {
    encoding: 'utf8',
    env: cleanEnv(),
  });
}

function basePackage() {
  return {
    dependencies: { react: '19.3.1', 'react-dom': '19.3.1' },
    devDependencies: {
      vite: '8.3.8',
      typescript: '6.0.3',
      '@vitejs/plugin-react': '6.3.0',
    },
    engines: { node: '>=22.12.0 <23' },
    scripts: { build: 'vite build' },
  };
}

function lockFor(pkg, version = 3) {
  const rootEntry = {};
  const packages = { '': rootEntry };
  for (const section of [
    'dependencies',
    'devDependencies',
    'optionalDependencies',
    'peerDependencies',
  ]) {
    if (pkg[section] !== undefined) rootEntry[section] = pkg[section];
  }
  for (const section of [
    'dependencies',
    'devDependencies',
    'optionalDependencies',
  ]) {
    for (const [name, spec] of Object.entries(pkg[section] ?? {})) {
      packages[`node_modules/${name}`] = { version: spec };
    }
  }
  return { lockfileVersion: version, packages };
}

function writeRoot(pkg, lock) {
  const root = tempDir('eii-lock-');
  fs.writeFileSync(path.join(root, 'package.json'), `${JSON.stringify(pkg)}\n`);
  if (lock !== null) {
    fs.writeFileSync(
      path.join(root, 'package-lock.json'),
      `${JSON.stringify(lock === undefined ? lockFor(pkg) : lock)}\n`,
    );
  }
  return root;
}

function assertFail(result, prefix) {
  assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`);
  const hit = result.stdout.split('\n').some((line) => line.startsWith(prefix));
  assert.equal(hit, true, result.stdout);
}

test('clean lock with lockfileVersion 2', () => {
  const pkg = basePackage();
  const result = run(writeRoot(pkg, lockFor(pkg, 2)));
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
});

test('lock missing', () => {
  assertFail(
    run(writeRoot(basePackage(), null)),
    'FAIL missing-lock: package-lock.json',
  );
});

test('lock parse failures', async (t) => {
  await t.test('unparsable', () => {
    const root = writeRoot(basePackage());
    fs.writeFileSync(path.join(root, 'package-lock.json'), '{');
    assertFail(run(root), 'FAIL lock-parse: package-lock.json');
  });
  await t.test('top level an array', () => {
    const root = writeRoot(basePackage());
    fs.writeFileSync(path.join(root, 'package-lock.json'), '[]\n');
    assertFail(run(root), 'FAIL lock-parse: package-lock.json');
  });
  await t.test('without packages', () => {
    const root = writeRoot(basePackage());
    fs.writeFileSync(
      path.join(root, 'package-lock.json'),
      '{"lockfileVersion":3}\n',
    );
    assertFail(run(root), 'FAIL lock-parse: package-lock.json');
  });
});

test('lockfileVersion rejected', async (t) => {
  await t.test('version 1', () => {
    const pkg = basePackage();
    assertFail(
      run(writeRoot(pkg, lockFor(pkg, 1))),
      'FAIL lock-version: package-lock.json',
    );
  });
  await t.test('string 3', () => {
    const pkg = basePackage();
    const lock = lockFor(pkg, 3);
    lock.lockfileVersion = '3';
    assertFail(
      run(writeRoot(pkg, lock)),
      'FAIL lock-version: package-lock.json',
    );
  });
});

test('lock root mismatch', async (t) => {
  for (const section of [
    'dependencies',
    'devDependencies',
    'optionalDependencies',
    'peerDependencies',
  ]) {
    await t.test(section, () => {
      const pkg = basePackage();
      if (
        section === 'optionalDependencies' ||
        section === 'peerDependencies'
      ) {
        pkg[section] = { sample: '1.2.3' };
      }
      const lock = lockFor(pkg);
      lock.packages[''][section] = {
        ...(lock.packages[''][section] ?? {}),
        extra: '1.2.3',
      };
      if (section === 'optionalDependencies') {
        lock.packages['node_modules/sample'] = { version: '1.2.3' };
      }
      assertFail(run(writeRoot(pkg, lock)), 'FAIL lock-root-mismatch');
    });
  }
  await t.test('root entry absent', () => {
    const pkg = basePackage();
    const lock = lockFor(pkg);
    delete lock.packages[''];
    assertFail(run(writeRoot(pkg, lock)), 'FAIL lock-root-mismatch');
  });
});

test('locked version mismatch', async (t) => {
  const sections = [
    ['dependencies', 'react'],
    ['devDependencies', 'vite'],
    ['optionalDependencies', 'sample'],
  ];
  for (const [section, name] of sections) {
    await t.test(`${section} version differs`, () => {
      const pkg = basePackage();
      if (section === 'optionalDependencies')
        pkg.optionalDependencies = { sample: '1.2.3' };
      const lock = lockFor(pkg);
      lock.packages[`node_modules/${name}`].version = '9.9.9';
      assertFail(run(writeRoot(pkg, lock)), 'FAIL lock-version-mismatch');
    });
    await t.test(`${section} entry absent`, () => {
      const pkg = basePackage();
      if (section === 'optionalDependencies')
        pkg.optionalDependencies = { sample: '1.2.3' };
      const lock = lockFor(pkg);
      delete lock.packages[`node_modules/${name}`];
      assertFail(run(writeRoot(pkg, lock)), 'FAIL lock-version-mismatch');
    });
  }
});

test('a peer dependency has no locked entry', () => {
  const pkg = basePackage();
  pkg.peerDependencies = { sample: '1.2.3' };
  const lock = lockFor(pkg);
  delete lock.packages['node_modules/sample'];
  const result = run(writeRoot(pkg, lock));
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
});
