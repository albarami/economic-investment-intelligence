import assert from 'node:assert/strict';
import { AsyncLocalStorage } from 'node:async_hooks';
import childProcess from 'node:child_process';
import { spawn } from 'node:child_process';
import { spawnSync } from 'node:child_process';
import { EventEmitter } from 'node:events';
import fs from 'node:fs';
import http from 'node:http';
import { syncBuiltinESMExports } from 'node:module';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { after, test as declareTest } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolveViteBin } from '../check-dev-server.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '..', '..');
const SCRIPT = path.join(WEB, 'scripts', 'check-dev-server.mjs');
const LONG_NAME_LENGTH = 300;
const MAX_PORT = 65535;
// The version the port-ownership comments cite: the startup of that vite
// probes the port it picks with a socket it closes before binding.
const PINNED_VITE = '8.3.8';
const PAGE = '<!doctype html><script type="module" src="/main.js"></script>\n';

const root = fs.mkdtempSync(
  path.join(os.tmpdir(), 'eii-test-check-dev-server-'),
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

function run(args) {
  return spawnSync(process.execPath, [SCRIPT, ...args], {
    encoding: 'utf8',
    env: cleanEnv(),
  });
}

function tempRoot() {
  return tempDir('eii-dev-');
}

function writer(root) {
  const file = path.join(root, 'writer.mjs');
  fs.writeFileSync(
    file,
    "import fs from 'node:fs';\nconst name = 'started';\nfs.writeFileSync(name, '1');\n",
  );
  return file;
}

function assertFail(result, prefix) {
  assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`);
  const hit = result.stdout.split('\n').some((line) => line.startsWith(prefix));
  assert.equal(hit, true, result.stdout);
}

function assertUsage(result) {
  assert.equal(result.status, 2, result.stdout + result.stderr);
  assert.ok(result.stdout.startsWith('USAGE: '), result.stdout);
}

// Drive the unmodified CLI with a fake dev server and a virtual clock. The
// transport models a first transform that continues after a client disconnects;
// no wall-clock sleep decides whether a request or its timeout wins. Keep the
// real httpGet, main error formatting, shared startup clock and cleanup in play.
async function timedServer(
  t,
  {
    entryDelay = 1200,
    pageDelay = 0,
    timeoutMs = 5000,
    entryStatus = 200,
    entryType = 'text/javascript',
    entryErrors = [],
  } = {},
) {
  const root = tempRoot();
  fs.writeFileSync(path.join(root, 'index.html'), PAGE);
  const bin = writer(root);
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.exitCode = null;
  child.signalCode = null;
  child.kill = (signal) => {
    child.signalCode = signal;
    child.emit('exit');
  };
  const requests = [];
  let entryReadyAt;
  let stdout = '';
  let status;
  const previousArgv = process.argv;
  const previousExit = process.exitCode;
  const write = process.stdout.write.bind(process.stdout);
  t.mock.timers.enable({ apis: ['Date', 'setTimeout'], now: 0 });
  t.mock.method(childProcess, 'spawn', () => {
    queueMicrotask(() =>
      child.stdout.emit('data', '  Local:   http://127.0.0.1:43210/\n'),
    );
    return child;
  });
  syncBuiltinESMExports();
  t.mock.method(http, 'get', (url, respond) => {
    const entry = new URL(url).pathname !== '/';
    if (entry) entryReadyAt ??= Date.now() + entryDelay;
    requests.push({ entry, at: Date.now() });
    const req = new EventEmitter();
    const errorCode = entry ? entryErrors.shift() : undefined;
    const answer = () => {
      if (errorCode !== undefined) {
        req.emit(
          'error',
          Object.assign(new Error('planted'), { code: errorCode }),
        );
        return;
      }
      const res = new EventEmitter();
      res.statusCode = entry ? entryStatus : 200;
      res.headers = {
        'content-type': entry ? entryType : 'text/html',
      };
      respond(res);
      res.emit('data', Buffer.from(entry ? 'export {};' : PAGE));
      res.emit('end');
    };
    const delay = entry ? Math.max(0, entryReadyAt - Date.now()) : pageDelay;
    const timer = Number.isFinite(delay)
      ? setTimeout(answer, errorCode ? 0 : delay)
      : null;
    req.destroy = () => clearTimeout(timer);
    return req;
  });
  t.mock.method(process.stdout, 'write', (chunk, ...args) => {
    if (/^(PASS|FAIL) /.test(String(chunk))) {
      stdout += chunk;
      return true;
    }
    return write(chunk, ...args);
  });
  t.mock.method(process, 'exit', (code) => {
    status = code;
  });
  process.argv = [
    process.execPath,
    SCRIPT,
    '--root',
    root,
    '--vite-bin',
    bin,
    '--timeout-ms',
    String(timeoutMs),
  ];
  try {
    await import(`${pathToFileURL(SCRIPT).href}?timed=${t.name}`);
    // setImmediate flushes I/O and promise continuations between clock ticks;
    // it is not a delay and makes no assertion about machine speed.
    for (
      let elapsed = 0;
      status === undefined && elapsed <= 70000;
      elapsed += 100
    ) {
      t.mock.timers.tick(100);
      await new Promise((resolve) => setImmediate(resolve));
    }
    assert.notEqual(
      status,
      undefined,
      'the CLI did not finish within the virtual bound',
    );
    return {
      status,
      stdout,
      requests,
      elapsed: Date.now(),
      signal: child.signalCode,
    };
  } finally {
    process.argv = previousArgv;
    process.exitCode = previousExit;
    t.mock.restoreAll();
    syncBuiltinESMExports();
    t.mock.timers.reset();
  }
}

test('entry transform beyond one request timeout uses the startup deadline', async (t) => {
  const result = await timedServer(t);
  assert.equal(result.status, 0, result.stdout);
  assert.match(
    result.stdout,
    /^PASS dev-server http:\/\/127\.0\.0\.1:43210\/\n$/,
  );
  assert.ok(result.elapsed < 5000);
  assert.equal(result.requests.filter((request) => request.entry).length, 2);
  assert.equal(result.signal, 'SIGTERM');
});

test('an entry that never answers times out naming its URL at the startup deadline', async (t) => {
  const result = await timedServer(t, { entryDelay: Infinity });
  assert.equal(result.status, 1, result.stdout);
  assert.equal(
    result.stdout,
    'FAIL timeout: no accepted answer from http://127.0.0.1:43210/main.js within 5000 ms\n',
  );
  assert.equal(result.elapsed, 5000);
  assert.equal(result.signal, 'SIGTERM');
});

test('entry 404 fails at once without retrying', async (t) => {
  const result = await timedServer(t, { entryDelay: 0, entryStatus: 404 });
  assert.equal(result.status, 1);
  assert.equal(result.stdout, 'FAIL bad-status: /main.js: 404\n');
  assert.equal(result.requests.filter((request) => request.entry).length, 1);
  assert.ok(result.elapsed < 1000);
});

test('entry wrong content type keeps its failure without retrying', async (t) => {
  const result = await timedServer(t, {
    entryDelay: 0,
    entryType: 'text/plain',
  });
  assert.equal(result.status, 1);
  assert.equal(result.stdout, 'FAIL bad-content-type: /main.js: text/plain\n');
  assert.equal(result.requests.filter((request) => request.entry).length, 1);
});

test('entry not-yet errors use the same retry classification as the page', async (t) => {
  for (const code of [
    'ECONNREFUSED',
    'ECONNRESET',
    'EPIPE',
    'TIMEOUT',
    'ECONNABORTED',
  ]) {
    await t.test(code, async (sub) => {
      const result = await timedServer(sub, {
        entryDelay: 0,
        entryErrors: [code],
      });
      assert.equal(result.status, 0, result.stdout);
      assert.equal(
        result.requests.filter((request) => request.entry).length,
        2,
      );
    });
  }
});

test('entry other errors retain the internal-error line without retrying', async (t) => {
  const result = await timedServer(t, {
    entryDelay: 0,
    entryErrors: ['EACCES'],
  });
  assert.equal(result.status, 1);
  assert.equal(result.stdout, 'FAIL internal-error: EACCES: planted\n');
  assert.equal(result.requests.filter((request) => request.entry).length, 1);
});

test('page polling spends the same startup budget as the entry', async (t) => {
  const result = await timedServer(t, {
    pageDelay: 700,
    entryDelay: 800,
    timeoutMs: 1500,
  });
  assert.equal(result.status, 1);
  assert.equal(
    result.stdout,
    'FAIL timeout: no accepted answer from http://127.0.0.1:43210/main.js within 1500 ms\n',
  );
  assert.equal(result.elapsed, 1500);
});

test('entry requests and pauses cannot overrun a short remaining deadline', async (t) => {
  const result = await timedServer(t, {
    entryDelay: Infinity,
    timeoutMs: 1700,
  });
  assert.equal(result.status, 1);
  assert.equal(
    result.stdout,
    'FAIL timeout: no accepted answer from http://127.0.0.1:43210/main.js within 1700 ms\n',
  );
  assert.equal(result.elapsed, 1700);
});

test('entry poll pauses stop at the remaining deadline', async (t) => {
  const result = await timedServer(t, {
    entryDelay: Infinity,
    timeoutMs: 1400,
  });
  assert.equal(result.status, 1);
  assert.equal(
    result.stdout,
    'FAIL timeout: no accepted answer from http://127.0.0.1:43210/main.js within 1400 ms\n',
  );
  assert.equal(result.elapsed, 1400);
});

test('an entry response at the deadline cannot turn expiration into success', async (t) => {
  const result = await timedServer(t, { entryDelay: 700, timeoutMs: 1000 });
  assert.equal(result.status, 1);
  assert.equal(
    result.stdout,
    'FAIL timeout: no accepted answer from http://127.0.0.1:43210/main.js within 1000 ms\n',
  );
  assert.equal(result.elapsed, 1000);
});

test('entry polling retains the outer bound even with a longer startup timeout', async (t) => {
  const result = await timedServer(t, {
    entryDelay: Infinity,
    timeoutMs: 90000,
  });
  assert.equal(result.status, 1);
  assert.equal(result.stdout, 'FAIL timeout: outer bound\n');
  assert.equal(result.elapsed, 60000);
  assert.equal(result.signal, 'SIGTERM');
});

test('real shell starts', { timeout: 60000 }, () => {
  const result = run(['--root', WEB]);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(
    result.stdout.trim().split('\n').at(-1),
    /^PASS dev-server http:\/\/127\.0\.0\.1:\d+\/$/,
  );
});

test('minimal root starts', { timeout: 60000 }, () => {
  const root = tempRoot();
  fs.writeFileSync(path.join(root, 'index.html'), PAGE);
  fs.writeFileSync(path.join(root, 'main.js'), 'export {}\n');
  const bin = resolveViteBin(WEB);
  const result = run(['--root', root, '--vite-bin', bin]);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(
    result.stdout.trim().split('\n').at(-1),
    /^PASS dev-server http:\/\/127\.0\.0\.1:\d+\/$/,
  );
});

// A stand-in for the dev server: it binds the port the check names and
// reports the port it bound; a port of zero means it picks and binds an
// ephemeral port in one listen, so this fixture models no release window
// of its own (the pinned vite 8.3.8 probes before it binds). A named port
// is announced before it is bound because, while the check hands over a
// port it has released and left unbound, any other file of the same suite
// run may take it first; the competitor in the test below takes exactly
// that window. The plant proves only the check's side: the check itself
// never holds and releases a port before the dev server binds.
const WINDOW_SERVER = [
  "import fs from 'node:fs';",
  "import http from 'node:http';",
  "import path from 'node:path';",
  'const here = path.dirname(process.argv[1]);',
  'const args = process.argv.slice(2);',
  "const named = Number(args[args.indexOf('--port') + 1]);",
  "const host = args[args.indexOf('--host') + 1];",
  "const page = fs.readFileSync(path.join(process.cwd(), 'index.html'), 'utf8');",
  "fs.writeFileSync(path.join(here, 'named'), String(named));",
  'if (named > 0) {',
  "  const taken = path.join(here, 'taken');",
  '  const deadline = Date.now() + 10000;',
  '  while (!fs.existsSync(taken) && Date.now() < deadline) {',
  '    await new Promise((resolve) => setTimeout(resolve, 10));',
  '  }',
  '}',
  'const server = http.createServer((req, res) => {',
  "  if (req.url.split('?')[0] === '/') {",
  "    res.writeHead(200, { 'Content-Type': 'text/html' });",
  '    res.end(page); return;',
  '  }',
  "  res.writeHead(200, { 'Content-Type': 'text/javascript' });",
  "  res.end('export {};');",
  '});',
  'server.listen(named, host, () => {',
  '  process.stdout.write(`  Local:   http://127.0.0.1:${server.address().port}/\\n`);',
  '});',
  "server.on('error', () => {",
  '  process.stdout.write(`Port ${named} is already in use\\n`);',
  '  process.exit(1);',
  '});',
  '',
].join('\n');

test(
  'the check itself never holds and releases a port before the dev server binds',
  { timeout: 60000 },
  async () => {
    const root = tempRoot();
    fs.writeFileSync(path.join(root, 'index.html'), PAGE);
    fs.writeFileSync(path.join(root, 'main.js'), 'export {}\n');
    const dir = tempDir('eii-window-');
    fs.writeFileSync(path.join(dir, 'server.mjs'), WINDOW_SERVER);
    const named = path.join(dir, 'named');
    const child = spawn(
      process.execPath,
      [SCRIPT, '--root', root, '--vite-bin', path.join(dir, 'server.mjs')],
      { env: cleanEnv(), stdio: ['ignore', 'pipe', 'pipe'] },
    );
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
    // Another file of the same suite run: it takes the named port while the
    // check has released it and the binder has not bound it yet.
    let squatterPort = 0;
    let squatter = null;
    while (!fs.existsSync(named)) {
      if (child.exitCode !== null || child.signalCode !== null) break;
      await new Promise((resolve) => setTimeout(resolve, 5));
    }
    if (fs.existsSync(named)) {
      const port = Number(fs.readFileSync(named, 'utf8'));
      if (port > 0) {
        squatter = net.createServer();
        await new Promise((resolve, reject) => {
          squatter.once('error', reject);
          squatter.listen(port, '127.0.0.1', resolve);
        });
        squatterPort = port;
        fs.writeFileSync(path.join(dir, 'taken'), '1');
      }
    }
    const status = await done;
    if (squatter !== null) {
      await new Promise((resolve) => squatter.close(resolve));
    }
    assert.equal(
      status,
      0,
      `${stdout}${stderr}competitor bound 127.0.0.1:${squatterPort} in the release window`,
    );
    assert.match(
      stdout.trim().split('\n').at(-1),
      /^PASS dev-server http:\/\/127\.0\.0\.1:\d+\/$/,
    );
  },
);

// The premise of the port-ownership comments: the installed vite is
// exactly the version whose startup they describe, so an upgrade of the
// installed package fails this test and the comments get re-read.
test('the installed vite is exactly the version the port comments cite', () => {
  const pkg = JSON.parse(
    fs.readFileSync(
      path.join(WEB, 'node_modules', 'vite', 'package.json'),
      'utf8',
    ),
  );
  assert.equal(
    pkg.version,
    PINNED_VITE,
    'the installed vite is no longer the version the port comments cite: re-read the comments in scripts/check-dev-server.mjs, scripts/dev-server-process.mjs and README.md',
  );
});

test('absent package.json uses the default flags', () => {
  const root = tempRoot();
  fs.writeFileSync(path.join(root, 'index.html'), PAGE);
  fs.writeFileSync(path.join(root, 'main.js'), 'export {}\n');
  const bin = path.join(root, 'server.mjs');
  fs.writeFileSync(
    bin,
    [
      "import fs from 'node:fs';",
      "import http from 'node:http';",
      "import path from 'node:path';",
      'const args = process.argv.slice(2);',
      "fs.writeFileSync(path.join(process.cwd(), 'argv.json'), JSON.stringify(args));",
      "const port = Number(args[args.indexOf('--port') + 1]);",
      "const host = args[args.indexOf('--host') + 1];",
      'const server = http.createServer((req, res) => {',
      "  if (req.url.split('?')[0] === '/') {",
      "    res.writeHead(200, { 'Content-Type': 'text/html' });",
      "    res.end(fs.readFileSync(path.join(process.cwd(), 'index.html')));",
      '    return;',
      '  }',
      "  res.writeHead(200, { 'Content-Type': 'text/javascript' });",
      "  res.end('export {};');",
      '});',
      'server.listen(port, host, () => {',
      '  process.stdout.write(`  Local:   http://127.0.0.1:${server.address().port}/\\n`);',
      '});',
      '',
    ].join('\n'),
  );
  const result = run(['--root', root, '--vite-bin', bin]);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(
    result.stdout.trim().split('\n').at(-1),
    /^PASS dev-server http:\/\/127\.0\.0\.1:\d+\/$/,
  );
  const argv = JSON.parse(
    fs.readFileSync(path.join(root, 'argv.json'), 'utf8'),
  );
  assert.deepEqual(argv.slice(0, -1), [
    '--host',
    '127.0.0.1',
    '--strictPort',
    '--port',
  ]);
  assert.match(argv.at(-1), /^\d+$/);
});

test('package.json not JSON', () => {
  const root = tempRoot();
  fs.writeFileSync(path.join(root, 'package.json'), '{');
  fs.writeFileSync(path.join(root, 'index.html'), PAGE);
  assertFail(
    run(['--root', root, '--vite-bin', writer(root)]),
    'FAIL dev-script: package.json: not valid JSON',
  );
  assert.equal(fs.existsSync(path.join(root, 'started')), false);
});

test('no scripts.dev', async (t) => {
  await t.test('scripts absent', () => {
    const root = tempRoot();
    fs.writeFileSync(path.join(root, 'package.json'), '{}\n');
    fs.writeFileSync(path.join(root, 'index.html'), PAGE);
    const result = run(['--root', root, '--vite-bin', writer(root)]);
    assertFail(result, 'FAIL dev-script: package.json: no scripts.dev string');
    assert.equal(fs.existsSync(path.join(root, 'started')), false);
  });
  await t.test('dev a number', () => {
    const root = tempRoot();
    fs.writeFileSync(
      path.join(root, 'package.json'),
      '{"scripts":{"dev":1}}\n',
    );
    fs.writeFileSync(path.join(root, 'index.html'), PAGE);
    const result = run(['--root', root, '--vite-bin', writer(root)]);
    assertFail(result, 'FAIL dev-script: package.json: no scripts.dev string');
    assert.equal(fs.existsSync(path.join(root, 'started')), false);
  });
});

test('script flags wrong', async (t) => {
  const scripts = [
    'vite',
    'vite --host 0.0.0.0 --strictPort',
    'vite --host 127.0.0.1',
    'webpack --host 127.0.0.1 --strictPort',
    'vite --host=127.0.0.1 --strictPort',
    'vite --host 127.0.0.1 --strictPort --port 4000',
    'vite --host 127.0.0.1 --strictPort --port=4000',
    'vite --strictPort --host',
  ];
  for (const dev of scripts) {
    await t.test(dev, () => {
      const root = tempRoot();
      fs.writeFileSync(
        path.join(root, 'package.json'),
        JSON.stringify({ scripts: { dev } }),
      );
      fs.writeFileSync(path.join(root, 'index.html'), PAGE);
      const result = run(['--root', root, '--vite-bin', writer(root)]);
      assertFail(result, 'FAIL dev-script: package.json');
      assert.equal(fs.existsSync(path.join(root, 'started')), false);
    });
  }
});

test('entry source faults', async (t) => {
  const pages = [
    ['no index.html', null],
    ['no module script', '<!doctype html><h1>shell</h1>\n'],
    [
      'two module scripts',
      '<script type="module" src="/a.js"></script><script type="module" src="/b.js"></script>\n',
    ],
    ['module script without src', '<script type="module"></script>\n'],
    ['only a classic script', '<script src="/main.js"></script>\n'],
  ];
  for (const [name, html] of pages) {
    await t.test(name, () => {
      const root = tempRoot();
      fs.writeFileSync(
        path.join(root, 'package.json'),
        JSON.stringify({
          scripts: { dev: 'vite --host 127.0.0.1 --strictPort' },
        }),
      );
      if (html !== null) fs.writeFileSync(path.join(root, 'index.html'), html);
      const result = run(['--root', root, '--vite-bin', writer(root)]);
      assertFail(result, 'FAIL entry-source: index.html');
      assert.equal(fs.existsSync(path.join(root, 'started')), false);
    });
  }
});

test('module script with a hosted src', () => {
  const root = tempRoot();
  fs.writeFileSync(
    path.join(root, 'index.html'),
    '<script type="module" src="https://example.com/app.js"></script>\n',
  );
  assertFail(
    run(['--root', root, '--vite-bin', writer(root)]),
    'FAIL entry-source: index.html',
  );
  assert.equal(fs.existsSync(path.join(root, 'started')), false);
});

test('bin field shape', async (t) => {
  const bodies = [
    ['object without vite', { bin: { other: 'server.mjs' } }],
    ['absent', {}],
    ['a number', { bin: 1 }],
    ['an empty string', { bin: '' }],
  ];
  for (const [name, body] of bodies) {
    await t.test(name, () => {
      const root = tempRoot();
      fs.writeFileSync(path.join(root, 'index.html'), PAGE);
      const pkg = path.join(root, 'node_modules', 'vite');
      fs.mkdirSync(pkg, { recursive: true });
      fs.writeFileSync(
        path.join(pkg, 'package.json'),
        `${JSON.stringify(body)}\n`,
      );
      assertFail(
        run(['--root', root]),
        'FAIL start-failed: node_modules/vite/package.json: bin field is absent or has no entry named vite',
      );
    });
  }
});

test('vite package.json faults', async (t) => {
  await t.test('missing', () => {
    const root = tempRoot();
    fs.writeFileSync(path.join(root, 'index.html'), PAGE);
    assertFail(
      run(['--root', root]),
      'FAIL start-failed: node_modules/vite/package.json',
    );
  });
  await t.test('not JSON', () => {
    const root = tempRoot();
    fs.writeFileSync(path.join(root, 'index.html'), PAGE);
    const pkg = path.join(root, 'node_modules', 'vite');
    fs.mkdirSync(pkg, { recursive: true });
    fs.writeFileSync(path.join(pkg, 'package.json'), '{');
    assertFail(
      run(['--root', root]),
      'FAIL start-failed: node_modules/vite/package.json',
    );
  });
  await t.test('a folder', () => {
    const root = tempRoot();
    fs.writeFileSync(path.join(root, 'index.html'), PAGE);
    fs.mkdirSync(path.join(root, 'node_modules', 'vite', 'package.json'), {
      recursive: true,
    });
    assertFail(
      run(['--root', root]),
      'FAIL start-failed: node_modules/vite/package.json',
    );
  });
});

test('bin target absent', () => {
  const root = tempRoot();
  fs.writeFileSync(path.join(root, 'index.html'), PAGE);
  const pkg = path.join(root, 'node_modules', 'vite');
  fs.mkdirSync(pkg, { recursive: true });
  fs.writeFileSync(path.join(pkg, 'package.json'), '{"bin":"missing.mjs"}\n');
  assertFail(run(['--root', root]), 'FAIL start-failed: vite binary not found');
});

test('vite-bin absent', () => {
  const root = tempRoot();
  fs.writeFileSync(path.join(root, 'index.html'), PAGE);
  const missing = path.join(root, 'missing.mjs');
  assertFail(
    run(['--root', root, '--vite-bin', missing]),
    'FAIL start-failed: vite binary not found',
  );
});

test('resolveViteBin', () => {
  const found = resolveViteBin(WEB);
  assert.equal(path.isAbsolute(found), true);
  assert.equal(fs.statSync(found).isFile(), true);
  const root = tempRoot();
  const pkg = path.join(root, 'node_modules', 'vite');
  fs.mkdirSync(pkg, { recursive: true });
  fs.writeFileSync(path.join(pkg, 'package.json'), '{"bin":1}\n');
  assert.throws(
    () => resolveViteBin(root),
    (error) => error.rule === 'start-failed',
  );
});

test('symlink run', () => {
  const root = tempRoot();
  fs.writeFileSync(
    path.join(root, 'package.json'),
    '{"scripts":{"dev":"vite"}}\n',
  );
  fs.writeFileSync(path.join(root, 'index.html'), PAGE);
  const linkParent = tempDir('eii-link-');
  const link = path.join(linkParent, 'scripts');
  fs.symlinkSync(path.join(WEB, 'scripts'), link);
  const result = spawnSync(
    process.execPath,
    [path.join(link, 'check-dev-server.mjs'), '--root', root],
    { encoding: 'utf8', env: cleanEnv() },
  );
  assertFail(result, 'FAIL dev-script: package.json');
});

test('usage', async (t) => {
  const cases = [
    ['unknown flag', ['--not-a-flag']],
    ['root without a value', ['--root']],
    ['port without a value', ['--port']],
    ['timeout without a value', ['--timeout-ms']],
    ['vite-bin without a value', ['--vite-bin']],
    ['port zero', ['--port', '0']],
    ['port above the range', ['--port', String(MAX_PORT + 4465)]],
    ['port not a number', ['--port', 'abc']],
    ['timeout zero', ['--timeout-ms', '0']],
  ];
  for (const [name, args] of cases) {
    await t.test(name, () => {
      assertUsage(run(args));
    });
  }
});

test('internal error', () => {
  const longName = path.join(root, 'n'.repeat(LONG_NAME_LENGTH));
  const result = run(['--root', longName]);
  assert.equal(result.status, 1);
  assert.equal(
    result.stdout,
    'FAIL internal-error: ENAMETOOLONG: name too long, stat\n',
  );
  assert.equal(`${result.stdout}${result.stderr}`.includes('    at '), false);
});
