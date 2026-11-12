import assert from 'node:assert/strict';
import { AsyncLocalStorage } from 'node:async_hooks';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test as declareTest } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '..', '..');
const SCRIPT = path.join(WEB, 'scripts', 'check-exact-versions.mjs');
const LONG_NAME_LENGTH = 300;
const AT = String.fromCharCode(64);

const DEPENDENCIES = { react: '19.3.1', 'react-dom': '19.3.1' };
const DEV_DEPENDENCIES = {
  vite: '8.3.8',
  typescript: '6.0.3',
  '@vitejs/plugin-react': '6.3.0',
};
const REQUIRED = [
  ['dependencies', 'react'],
  ['dependencies', 'react-dom'],
  ['devDependencies', 'vite'],
  ['devDependencies', 'typescript'],
  ['devDependencies', '@vitejs/plugin-react'],
];
const LIFECYCLE = ['preinstall', 'install', 'postinstall', 'prepare', 'prepublish'];
const SAMPLES = [
  '^19.3.1',
  '~19.3.1',
  '>=19.3.1',
  '19.x',
  '*',
  'latest',
  '19.3',
  'v19.3.1',
  '',
  '19.3.1 - 19.4.0',
  '19.3.1 || 19.4.0',
  `npm:react${AT}19.3.1`,
  'file:../core',
  'workspace:*',
  'git+ssh://example.com/repo.git',
  'github:example/repo',
  '19.3.1-rc.1',
  '19.3.1+build.5',
  '19.3.1\n',
  '\uFF11\uFF19.\uFF13.\uFF11',
  19,
  null,
];

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-test-check-exact-versions-'));
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

function run(args, env) {
  return spawnSync(process.execPath, [SCRIPT, ...args], {
    encoding: 'utf8',
    env: env ?? cleanEnv(),
  });
}

function basePackage() {
  return {
    name: 'eii-web',
    dependencies: { ...DEPENDENCIES },
    devDependencies: { ...DEV_DEPENDENCIES },
    engines: { node: '>=22.12.0 <23' },
    scripts: { build: 'vite build' },
  };
}

function lockFor(pkg, version = 3) {
  const root = {};
  const packages = { '': root };
  for (const section of [
    'dependencies',
    'devDependencies',
    'optionalDependencies',
    'peerDependencies',
  ]) {
    if (pkg[section] !== undefined) root[section] = pkg[section];
  }
  for (const section of ['dependencies', 'devDependencies', 'optionalDependencies']) {
    const block = pkg[section];
    if (block === undefined || typeof block !== 'object' || block === null) continue;
    for (const [name, spec] of Object.entries(block)) {
      const pinned = typeof spec === 'string' ? spec : '0.0.0';
      packages[`node_modules/${name}`] = { version: pinned.split('\n')[0] };
    }
  }
  return { lockfileVersion: version, packages };
}

function writeRoot(pkg, lock) {
  const root = tempDir('eii-ver-');
  fs.writeFileSync(path.join(root, 'package.json'), `${JSON.stringify(pkg, null, 2)}\n`);
  if (lock !== null) {
    const body = lock === undefined ? lockFor(pkg) : lock;
    fs.writeFileSync(path.join(root, 'package-lock.json'), `${JSON.stringify(body, null, 2)}\n`);
  }
  return root;
}

function assertFail(result, prefix) {
  assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`);
  const hit = result.stdout.split('\n').some((line) => line.startsWith(prefix));
  assert.equal(hit, true, result.stdout);
}

function snapshot(root) {
  const rows = [];
  for (const name of fs.readdirSync(root).sort()) {
    const full = path.join(root, name);
    const info = fs.lstatSync(full);
    const digest = createHash('sha256').update(fs.readFileSync(full)).digest('hex');
    rows.push(`${name} ${info.size} ${digest}`);
  }
  return rows.join('\n');
}

function hostileEnv() {
  const base = cleanEnv();
  return cleanEnv({
    npm_config_registry: 'http://127.0.0.1:9/',
    npm_config_prefix: path.join(base.HOME, 'missing-prefix'),
    npm_config_userconfig: path.join(base.HOME, 'missing.npmrc'),
    HOST: '0.0.0.0',
    PORT: '1',
    VITE_PORT: '1',
    BROWSER: 'firefox',
    NODE_ENV: 'production',
    NODE_OPTIONS: '--no-warnings',
    HTTP_PROXY: 'http://127.0.0.1:9/',
    HTTPS_PROXY: 'http://127.0.0.1:9/',
  });
}

test('clean package and lock', () => {
  const root = writeRoot(basePackage());
  const result = run(['--root', root]);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
});

test('real web passes', () => {
  const result = run(['--root', WEB]);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout.trim().split('\n').at(-1), /^checked \d+ specifiers: OK$/);
});

test('sample specifiers are not exact', async (t) => {
  for (const section of ['dependencies', 'devDependencies']) {
    for (const sample of SAMPLES) {
      const label = `${section} ${JSON.stringify(sample)}`;
      await t.test(label, () => {
        const pkg = basePackage();
        const name = section === 'dependencies' ? 'react' : 'vite';
        pkg[section][name] = sample;
        const root = writeRoot(pkg);
        assertFail(run(['--root', root]), `FAIL not-exact: ${section}.${name}`);
      });
    }
  }
});

test('bad value in overrides, optional and peer sections', async (t) => {
  await t.test('overrides nested', () => {
    const pkg = basePackage();
    pkg.overrides = { react: { '.': '^1.0.0' } };
    const root = writeRoot(pkg);
    assertFail(run(['--root', root]), 'FAIL not-exact: overrides.react.');
  });
  await t.test('optionalDependencies', () => {
    const pkg = basePackage();
    pkg.optionalDependencies = { sample: '^1.0.0' };
    const root = writeRoot(pkg);
    assertFail(run(['--root', root]), 'FAIL not-exact: optionalDependencies.sample');
  });
  await t.test('peerDependencies', () => {
    const pkg = basePackage();
    pkg.peerDependencies = { sample: '^1.0.0' };
    const root = writeRoot(pkg);
    assertFail(run(['--root', root]), 'FAIL not-exact: peerDependencies.sample');
  });
});

test('engines', async (t) => {
  await t.test('removed', () => {
    const pkg = basePackage();
    delete pkg.engines;
    assertFail(run(['--root', writeRoot(pkg)]), 'FAIL engines-missing: engines.node');
  });
  await t.test('string', () => {
    const pkg = basePackage();
    pkg.engines = '>=22.12.0 <23';
    assertFail(run(['--root', writeRoot(pkg)]), 'FAIL engines-missing: engines.node');
  });
  await t.test('node is a number', () => {
    const pkg = basePackage();
    pkg.engines = { node: 22 };
    assertFail(run(['--root', writeRoot(pkg)]), 'FAIL engines-missing: engines.node');
  });
  await t.test('node is empty', () => {
    const pkg = basePackage();
    pkg.engines = { node: '' };
    assertFail(run(['--root', writeRoot(pkg)]), 'FAIL engines-missing: engines.node');
  });
});

test('required packages', async (t) => {
  for (const [section, name] of REQUIRED) {
    await t.test(`${section}.${name}`, () => {
      const pkg = basePackage();
      delete pkg[section][name];
      assertFail(run(['--root', writeRoot(pkg)]), `FAIL required-package: ${section}.${name}`);
    });
  }
});

test('lifecycle keys', async (t) => {
  for (const key of LIFECYCLE) {
    await t.test(key, () => {
      const pkg = basePackage();
      pkg.scripts[key] = 'node -e 0';
      assertFail(run(['--root', writeRoot(pkg)]), `FAIL lifecycle-script: scripts.${key}`);
    });
  }
});

test('other script keys pass', () => {
  const pkg = basePackage();
  pkg.scripts = { prepack: 'node -e 0', build: 'vite build' };
  const result = run(['--root', writeRoot(pkg)]);
  assert.equal(result.status, 0, result.stdout);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
});

test('package.json shape', async (t) => {
  await t.test('missing', () => {
    const root = tempDir('eii-ver-');
    fs.writeFileSync(path.join(root, 'package-lock.json'), '{}\n');
    assertFail(run(['--root', root]), 'FAIL package-json: package.json');
  });
  await t.test('not JSON', () => {
    const root = writeRoot(basePackage());
    fs.writeFileSync(path.join(root, 'package.json'), '{');
    assertFail(run(['--root', root]), 'FAIL package-json: package.json');
  });
  await t.test('top level an array', () => {
    const root = writeRoot(basePackage());
    fs.writeFileSync(path.join(root, 'package.json'), '[]\n');
    assertFail(run(['--root', root]), 'FAIL package-json: package.json');
  });
  await t.test('dependencies a string', () => {
    const pkg = basePackage();
    pkg.dependencies = 'react';
    assertFail(run(['--root', writeRoot(pkg)]), 'FAIL package-json: package.json');
  });
  await t.test('overrides a string', () => {
    const pkg = basePackage();
    pkg.overrides = 'react';
    const result = run(['--root', writeRoot(pkg)]);
    assertFail(result, 'FAIL package-json: package.json');
    assert.ok(result.stdout.includes('overrides is not an object'));
  });
  await t.test('scripts a string', () => {
    const pkg = basePackage();
    pkg.scripts = 'build';
    assertFail(run(['--root', writeRoot(pkg)]), 'FAIL package-json: package.json');
  });
  for (const section of ['devDependencies', 'optionalDependencies', 'peerDependencies']) {
    await t.test(`${section} a string`, () => {
      const pkg = basePackage();
      pkg[section] = 'sample';
      assertFail(run(['--root', writeRoot(pkg)]), 'FAIL package-json: package.json');
    });
  }
});

test('usage', async (t) => {
  await t.test('unknown flag', () => {
    const result = run(['--not-a-flag']);
    assert.equal(result.status, 2, result.stdout);
    assert.ok(result.stdout.startsWith('USAGE: '));
  });
  await t.test('root without a value', () => {
    const result = run(['--root']);
    assert.equal(result.status, 2, result.stdout);
    assert.ok(result.stdout.startsWith('USAGE: '));
  });
});

test('internal error', () => {
  const longName = path.join(root, 'n'.repeat(LONG_NAME_LENGTH));
  const result = run(['--root', longName]);
  assert.equal(result.status, 1);
  assert.equal(result.stdout, 'FAIL internal-error: ENAMETOOLONG: name too long, stat\n');
  assert.equal(`${result.stdout}${result.stderr}`.includes('    at '), false);
});

test('hostile surroundings', () => {
  const clean = run(['--root', WEB], cleanEnv());
  const hostile = run(['--root', WEB], hostileEnv());
  assert.equal(clean.status, 0, clean.stdout + clean.stderr);
  assert.match(clean.stdout.trim().split('\n').at(-1), /OK$/);
  assert.equal(hostile.status, clean.status);
  assert.equal(hostile.stdout, clean.stdout);
});

test('reads only', () => {
  const root = writeRoot(basePackage());
  const before = snapshot(root);
  const result = run(['--root', root]);
  assert.equal(result.status, 0, result.stdout);
  assert.equal(snapshot(root), before);
});
