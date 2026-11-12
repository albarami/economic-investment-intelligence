import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { after, test } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SCRIPT = path.join(HERE, '..', 'check-dev-server.mjs');
const SQUAT_WAIT_MS = 600;
const POLL_MS = 20;
const SHORT_TIMEOUT_MS = 1500;
const ELAPSED_LIMIT_MS = 15000;
const pids = [];

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
  "    if (mode === 'page-500' && req.url.split('?')[0] === '/') {",
  "      res.writeHead(500); res.end('no'); return;",
  '    }',
  "    if (req.url.split('?')[0] === '/') {",
  '      let body = page;',
  '      if (mode === \'no-entry\') body = \'<script type="module" src="/other.js"></script>\';',
  "      if (mode === 'no-module') body = '<html></html>';",
  "      res.writeHead(200, { 'Content-Type': 'text/html' });",
  '      res.end(body); return;',
  '    }',
  "    if (mode === 'entry-404') { res.writeHead(404); res.end('missing'); return; }",
  "    let type = 'text/javascript';",
  "    if (mode.startsWith('ctype:')) type = mode.slice('ctype:'.length);",
  "    if (mode === 'plain') type = 'text/plain';",
  "    if (mode === 'html') type = 'text/html';",
  "    res.writeHead(200, { 'Content-Type': type });",
  "    res.end('export {};');",
  '  });',
  '  server.listen(port, host, () => {',
  "    if (mode !== 'no-local') {",
  "      const shown = mode === 'wrong-port' ? port + 1 : port;",
  '      process.stdout.write(`  Local:   http://127.0.0.1:${shown}/\\n`);',
  '    }',
  "    if (mode === 'network') {",
  '      process.stdout.write(`  Network: http://192.0.2.5:${port}/\\n`);',
  '    }',
  '  });',
  '}',
  '',
].join('\n');

function cleanEnv(extra) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-env-'));
  const base = { PATH: process.env.PATH, HOME: home, TMPDIR: home, LANG: 'C' };
  return { ...base, ...extra };
}

function run(args) {
  return spawnSync(process.execPath, [SCRIPT, ...args], {
    encoding: 'utf8',
    env: cleanEnv(),
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
  if (!fs.existsSync(file)) return;
  const pid = Number(fs.readFileSync(file, 'utf8'));
  if (Number.isInteger(pid)) pids.push(pid);
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

function prepare(mode, html) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-fake-'));
  const dir = path.join(root, 'fake');
  fs.mkdirSync(dir);
  fs.writeFileSync(path.join(dir, 'server.mjs'), FAKE_SERVER);
  fs.writeFileSync(path.join(dir, 'mode.txt'), `${mode}\n`);
  fs.writeFileSync(
    path.join(root, 'package.json'),
    '{"scripts":{"dev":"vite --host 127.0.0.1 --strictPort --clearScreen false"}}\n',
  );
  fs.writeFileSync(
    path.join(root, 'index.html'),
    html ?? '<!doctype html><script type="module" src="/main.js"></script>\n',
  );
  fs.writeFileSync(path.join(root, 'main.js'), 'export {}\n');
  return { root, dir, bin: path.join(dir, 'server.mjs') };
}

function assertFail(result, prefix) {
  assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`);
  const hit = result.stdout.split('\n').some((line) => line.startsWith(prefix));
  assert.equal(hit, true, result.stdout);
}

test('fake server, good', () => {
  const { root, dir, bin } = prepare('good');
  const result = run(['--root', root, '--vite-bin', bin]);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /^PASS dev-server http:\/\/127\.0\.0\.1:/m);
  const argv = JSON.parse(fs.readFileSync(path.join(dir, 'argv.json'), 'utf8'));
  assert.deepEqual(argv.slice(0, -1), [
    '--host',
    '127.0.0.1',
    '--strictPort',
    '--clearScreen',
    'false',
    '--port',
  ]);
  assert.match(argv.at(-1), /^\d+$/);
  const pid = Number(fs.readFileSync(path.join(dir, 'pid'), 'utf8'));
  pids.push(pid);
  assert.equal(alive(pid), false);
});

test('bin field, string form', () => {
  const { root, dir } = prepare('good');
  const pkg = path.join(root, 'node_modules', 'vite');
  fs.mkdirSync(pkg, { recursive: true });
  fs.writeFileSync(path.join(pkg, 'package.json'), '{"bin":"../../fake/server.mjs"}\n');
  const result = run(['--root', root]);
  remember(dir);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test('bin field, object form', () => {
  const { root, dir } = prepare('good');
  const pkg = path.join(root, 'node_modules', 'vite');
  fs.mkdirSync(pkg, { recursive: true });
  fs.writeFileSync(
    path.join(pkg, 'package.json'),
    '{"bin":{"vite":"../../fake/server.mjs"}}\n',
  );
  const result = run(['--root', root]);
  remember(dir);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test('terminate signal ignored', { timeout: 20000 }, () => {
  const { root, dir, bin } = prepare('ignore-term');
  const result = run(['--root', root, '--vite-bin', bin]);
  const pid = Number(fs.readFileSync(path.join(dir, 'pid'), 'utf8'));
  pids.push(pid);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.equal(alive(pid), false);
});

test('server that never answers', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-sleep-'));
  const dir = path.join(root, 'fake');
  fs.mkdirSync(dir);
  fs.writeFileSync(
    path.join(dir, 'sleep.mjs'),
    "import fs from 'node:fs';\nimport path from 'node:path';\nfs.writeFileSync(path.join(path.dirname(process.argv[1]), 'pid'), String(process.pid));\nsetInterval(() => {}, 1000);\n",
  );
  fs.writeFileSync(path.join(root, 'index.html'), '<script type="module" src="/main.js"></script>\n');
  const started = Date.now();
  const result = run([
    '--root',
    root,
    '--vite-bin',
    path.join(dir, 'sleep.mjs'),
    '--timeout-ms',
    String(SHORT_TIMEOUT_MS),
  ]);
  remember(dir);
  assert.ok(Date.now() - started < ELAPSED_LIMIT_MS);
  assertFail(result, 'FAIL timeout');
  const pid = Number(fs.readFileSync(path.join(dir, 'pid'), 'utf8'));
  assert.equal(alive(pid), false);
});

test('answers but prints no Local line', () => {
  const { root, dir, bin } = prepare('no-local');
  const result = run(['--root', root, '--vite-bin', bin, '--timeout-ms', String(SHORT_TIMEOUT_MS)]);
  remember(dir);
  assertFail(result, 'FAIL timeout: no accepted answer');
});

test('prints a Local line for another port', () => {
  const { root, dir, bin } = prepare('wrong-port');
  const result = run(['--root', root, '--vite-bin', bin, '--timeout-ms', String(SHORT_TIMEOUT_MS)]);
  remember(dir);
  assertFail(result, 'FAIL timeout: no accepted answer');
});

test('network announced', () => {
  const { root, dir, bin } = prepare('network');
  const result = run(['--root', root, '--vite-bin', bin]);
  remember(dir);
  assertFail(result, 'FAIL network-announced');
});

test('entry omitted but another module script served', () => {
  const { root, dir, bin } = prepare('no-entry');
  const result = run(['--root', root, '--vite-bin', bin]);
  remember(dir);
  assertFail(result, 'FAIL missing-entry');
});

test('page without any module script', () => {
  const { root, dir, bin } = prepare('no-module');
  const result = run(['--root', root, '--vite-bin', bin]);
  remember(dir);
  assertFail(result, 'FAIL missing-entry');
});

test('content types', async (t) => {
  for (const type of ['text/javascript', 'application/javascript', 'text/ecmascript', 'application/ecmascript']) {
    await t.test(type, () => {
      const { root, dir, bin } = prepare(`ctype:${type}`);
      const result = run(['--root', root, '--vite-bin', bin]);
      remember(dir);
      assert.equal(result.status, 0, result.stdout + result.stderr);
    });
  }
});

test('bad content type', async (t) => {
  for (const mode of ['plain', 'html']) {
    await t.test(mode, () => {
      const { root, dir, bin } = prepare(mode);
      const result = run(['--root', root, '--vite-bin', bin]);
      remember(dir);
      assertFail(result, 'FAIL bad-content-type');
    });
  }
});

test('entry 404', () => {
  const { root, dir, bin } = prepare('entry-404');
  const result = run(['--root', root, '--vite-bin', bin]);
  remember(dir);
  assertFail(result, 'FAIL bad-status');
});

test('page not 200', () => {
  const { root, dir, bin } = prepare('page-500');
  const result = run(['--root', root, '--vite-bin', bin]);
  remember(dir);
  assertFail(result, 'FAIL bad-status: /');
});

test('hosted script in the page', () => {
  const html = [
    '<script type="module" src="/main.js"></script>',
    '<script src="https://example.com/a.js"></script>',
    '',
  ].join('\n');
  const { root, dir, bin } = prepare('good', html);
  const result = run(['--root', root, '--vite-bin', bin]);
  remember(dir);
  assertFail(result, 'FAIL absolute-url');
});

test('child exits at once', () => {
  const { root, dir, bin } = prepare('exit-at-once');
  const result = run(['--root', root, '--vite-bin', bin]);
  remember(dir);
  assertFail(result, 'FAIL start-failed: child exited with 3');
});

test('squatter answers while the child exits', async () => {
  const { root, dir, bin } = prepare('squat-exit');
  const probe = spawnSync(process.execPath, [
    '-e',
    "const n=require('node:net');const s=n.createServer();s.listen(0,'127.0.0.1',()=>{process.stdout.write(String(s.address().port));s.close();});",
  ], { encoding: 'utf8', env: cleanEnv() });
  const port = probe.stdout.trim();
  assert.match(port, /^\d+$/);
  const child = spawn(process.execPath, [SCRIPT, '--root', root, '--port', port, '--vite-bin', bin], {
    env: cleanEnv(),
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let stdout = '';
  let stderr = '';
  child.stdout.on('data', (chunk) => {
    stdout += chunk;
  });
  child.stderr.on('data', (chunk) => {
    stderr += chunk;
  });
  const done = new Promise((resolve) => {
    child.on('close', (status) => resolve(status));
  });
  let server;
  const timer = setInterval(() => {
    if (server || !fs.existsSync(path.join(dir, 'started'))) return;
    server = http.createServer((req, res) => {
      if (req.url.split('?')[0] === '/') {
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(fs.readFileSync(path.join(root, 'index.html')));
        return;
      }
      res.writeHead(200, { 'Content-Type': 'text/javascript' });
      res.end('export {}');
    });
    server.listen(Number(port), '127.0.0.1');
  }, POLL_MS);
  try {
    const status = await done;
    assertFail({ status, stdout, stderr }, 'FAIL start-failed: child exited');
  } finally {
    clearInterval(timer);
    remember(dir);
    if (server) await new Promise((resolve) => server.close(resolve));
  }
});
