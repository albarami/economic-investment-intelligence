import assert from 'node:assert/strict';
import { AsyncLocalStorage } from 'node:async_hooks';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { after, test as declareTest } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '..', '..');
const SCRIPT = path.join(HERE, '..', 'check-dev-server.mjs');
const SQUAT_WAIT_MS = 600;
const pids = [];
const ALLOWED = ['BROWSER', 'HOME', 'LANG', 'PATH', 'TMPDIR'];
const LEAKED = [
  'npm_config_registry',
  'npm_config_prefix',
  'npm_config_userconfig',
  'HOST',
  'PORT',
  'VITE_PORT',
  'NODE_ENV',
  'NODE_OPTIONS',
  'HTTP_PROXY',
  'HTTPS_PROXY',
];

const FAKE_SERVER = [
  "import http from 'node:http';",
  "import fs from 'node:fs';",
  "import path from 'node:path';",
  'const here = path.dirname(process.argv[1]);',
  "const mode = fs.readFileSync(path.join(here, 'mode.txt'), 'utf8').trim();",
  "fs.writeFileSync(path.join(here, 'pid'), String(process.pid));",
  "fs.writeFileSync(path.join(here, 'env.json'), JSON.stringify(process.env));",
  "fs.writeFileSync(path.join(here, 'argv.json'), JSON.stringify(process.argv.slice(2)));",
  "if (mode === 'ignore-term') process.on('SIGTERM', () => {});",
  "if (mode === 'exit-at-once') process.exit(3);",
  "if (mode === 'squat-exit') {",
  "  fs.writeFileSync(path.join(here, 'started'), '1');",
  `  setTimeout(() => process.exit(1), ${SQUAT_WAIT_MS});`,
  '} else {',
  '  const args = process.argv.slice(2);',
  "  const port = Number(args[args.indexOf('--port') + 1]);",
  "  const host = args[args.indexOf('--host') + 1];",
  "  const page = fs.readFileSync(path.join(process.cwd(), 'index.html'), 'utf8');",
  '  const server = http.createServer((req, res) => {',
  "    if (req.url.split('?')[0] === '/') {",
  "      res.writeHead(200, { 'Content-Type': 'text/html' });",
  '      res.end(page); return;',
  '    }',
  "    res.writeHead(200, { 'Content-Type': 'text/javascript' });",
  "    res.end('export {};');",
  '  });',
  '  server.listen(port, host, () => {',
  '    process.stdout.write(`  Local:   http://127.0.0.1:${port}/\\n`);',
  '  });',
  '}',
  '',
].join('\n');

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-test-check-dev-server-surroundings-'));
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

function hostileVars(home) {
  return {
    npm_config_registry: 'http://127.0.0.1:9/',
    npm_config_prefix: path.join(home, 'missing-prefix'),
    npm_config_userconfig: path.join(home, 'missing.npmrc'),
    HOST: '0.0.0.0',
    PORT: '1',
    VITE_PORT: '1',
    BROWSER: 'firefox',
    NODE_ENV: 'production',
    NODE_OPTIONS: '--no-warnings',
    HTTP_PROXY: 'http://127.0.0.1:9/',
    HTTPS_PROXY: 'http://127.0.0.1:9/',
  };
}

function run(args, env) {
  return spawnSync(process.execPath, [SCRIPT, ...args], {
    encoding: 'utf8',
    env: env ?? cleanEnv(),
  });
}

function alive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function remember(dir) {
  const file = path.join(dir, 'pid');
  if (!fs.existsSync(file)) return null;
  const pid = Number(fs.readFileSync(file, 'utf8'));
  if (Number.isInteger(pid)) pids.push(pid);
  return pid;
}

after(() => {
  let leaked = false;
  for (const pid of pids) {
    if (!alive(pid)) continue;
    leaked = true;
    try {
      process.kill(pid, 'SIGKILL');
    } catch {
      /* already gone */
    }
  }
  if (leaked) throw new Error('a child was still running');
});

function prepare() {
  const root = tempDir('eii-surr-');
  const dir = path.join(root, 'fake');
  fs.mkdirSync(dir);
  fs.writeFileSync(path.join(dir, 'server.mjs'), FAKE_SERVER);
  fs.writeFileSync(path.join(dir, 'mode.txt'), 'good\n');
  fs.writeFileSync(
    path.join(root, 'package.json'),
    '{"scripts":{"dev":"vite --host 127.0.0.1 --strictPort --clearScreen false"}}\n',
  );
  fs.writeFileSync(path.join(root, 'index.html'), '<script type="module" src="/main.js"></script>\n');
  fs.writeFileSync(path.join(root, 'main.js'), 'export {}\n');
  return { root, dir, bin: path.join(dir, 'server.mjs') };
}

function recordedEnv(dir) {
  return JSON.parse(fs.readFileSync(path.join(dir, 'env.json'), 'utf8'));
}

function assertFail(result, prefix) {
  assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`);
  const hit = result.stdout.split('\n').some((line) => line.startsWith(prefix));
  assert.equal(hit, true, result.stdout);
}

test('child environment', () => {
  const { root, dir, bin } = prepare();
  const parent = cleanEnv();
  const env = cleanEnv({ ...hostileVars(parent.HOME), HOME: parent.HOME, TMPDIR: parent.TMPDIR });
  const result = run(['--root', root, '--vite-bin', bin], env);
  remember(dir);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const childEnv = recordedEnv(dir);
  assert.deepEqual(Object.keys(childEnv).sort(), ALLOWED);
  assert.equal(childEnv.BROWSER, 'none');
  assert.notEqual(childEnv.HOME, parent.HOME);
});

test('child environment, a name absent in the parent', () => {
  const { root, dir, bin } = prepare();
  const env = cleanEnv();
  delete env.LANG;
  const result = run(['--root', root, '--vite-bin', bin], env);
  remember(dir);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.deepEqual(Object.keys(recordedEnv(dir)).sort(), ['BROWSER', 'HOME', 'PATH', 'TMPDIR']);
});

test('hostile surroundings', { timeout: 180000 }, () => {
  const clean = run(['--root', WEB], cleanEnv());
  assert.equal(clean.status, 0, clean.stdout + clean.stderr);
  assert.match(clean.stdout, /^PASS dev-server http:\/\/127\.0\.0\.1:/m);
  const parent = cleanEnv();
  const hostile = cleanEnv(hostileVars(parent.HOME));
  const again = run(['--root', WEB], hostile);
  assert.equal(again.status, 0, again.stdout + again.stderr);
  assert.match(again.stdout, /^PASS dev-server http:\/\/127\.0\.0\.1:/m);
  const { root, dir, bin } = prepare();
  const fake = run(['--root', root, '--vite-bin', bin], hostile);
  remember(dir);
  assert.equal(fake.status, 0, fake.stdout + fake.stderr);
  const names = Object.keys(recordedEnv(dir));
  for (const name of LEAKED) assert.equal(names.includes(name), false, name);
});

test('port busy by a bare listener', { timeout: 30000 }, async () => {
  const server = net.createServer();
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  try {
    const result = run(['--root', WEB, '--port', String(port)]);
    assertFail(result, `FAIL start-failed: port ${port} is already in use`);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test('port busy by an HTTP server', { timeout: 30000 }, async () => {
  const page = fs.readFileSync(path.join(WEB, 'index.html'));
  const server = http.createServer((req, res) => {
    if (req.url.split('?')[0] === '/') {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(page);
      return;
    }
    res.writeHead(200, { 'Content-Type': 'text/javascript' });
    res.end('export {}');
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  try {
    const result = run(['--root', WEB, '--port', String(port)]);
    assertFail(result, `FAIL start-failed: port ${port} is already in use`);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test('port busy, nothing started', { timeout: 30000 }, async () => {
  const root = tempDir('eii-busy-');
  fs.writeFileSync(path.join(root, 'index.html'), '<script type="module" src="/main.js"></script>\n');
  const writer = path.join(root, 'writer.mjs');
  fs.writeFileSync(writer, "import fs from 'node:fs';\nfs.writeFileSync('started', '1');\n");
  const server = http.createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('busy');
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  try {
    const result = run(['--root', root, '--port', String(port), '--vite-bin', writer]);
    assertFail(result, 'FAIL start-failed: port');
    assert.equal(fs.existsSync(path.join(root, 'started')), false);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test('process hygiene', () => {
  for (const pid of pids) assert.equal(alive(pid), false);
});
