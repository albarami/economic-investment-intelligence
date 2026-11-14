import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { EventEmitter } from 'node:events';
import * as trace from '../trace.mjs';
import * as config from '../config.mjs';
import { CSP } from '../../glyphs/guards.mjs';
import { loadModule } from './module-harness.mjs';
import { mutationTrace } from './mutation-fixtures.mjs';
const names = [
  'evidenceId',
  'traceNames',
  'exclusiveTrace',
  'classify',
  'send',
  'sendJson',
  'originAllowed',
  'readBody',
  'fileFor',
  'publicPath',
  'receiveTrace',
  'serveStatic',
  'tracePosts',
  'handle',
  'requestPathname',
  'tracePlugin',
  'listen',
  'repositoryStamp',
  'ownerMode',
];
function module(overrides = {}, globals = {}) {
  return loadModule(
    new URL('../server.mjs', import.meta.url),
    {
      './trace.mjs': trace,
      './config.mjs': config,
      '../glyphs/guards.mjs': { CSP },
      vite: {
        createServer() {
          throw new Error('unexpected server start');
        },
      },
      ...overrides,
    },
    names,
    globals,
  );
}
function response() {
  return {
    headers: [],
    bodies: [],
    writeHead(status, headers) {
      this.headers.push({ status, headers });
    },
    end(body) {
      this.bodies.push(body);
    },
    on() {},
  };
}
const plain = (value) => JSON.parse(JSON.stringify(value));

test('server classifiers and paths preserve closed routes and boundaries', async () => {
  const m = await module();
  for (const route of ['/en/_perf', '/ar/_perf'])
    assert.equal(m.classify(route), 'page');
  assert.equal(m.classify('/__perf/posts'), 'posts');
  assert.equal(m.classify('/__perf/trace'), 'trace');
  for (const route of [
    '/@synthetic',
    '/node_modules/synthetic',
    '/synthetic.txt',
  ])
    assert.equal(m.classify(route), 'asset');
  for (const route of ['/synthetic', '/'])
    assert.equal(m.classify(route), 'unknown');
  const root = path.resolve('synthetic-root');
  assert.equal(
    m.fileFor(root, '///synthetic.txt'),
    path.join(root, 'synthetic.txt'),
  );
  assert.equal(m.fileFor(root, ''), root);
  assert.equal(m.fileFor(root, '../synthetic.txt'), null);
  assert.equal(m.publicPath(false, 'synthetic.json'), 'synthetic.json');
  assert.equal(
    m.publicPath(true, 'synthetic.json'),
    'web/spikes/performance/evidence/synthetic.json',
  );
  assert.equal(m.sinkAllowed(root, root), false);
  assert.equal(m.sinkAllowed(path.join(root, 'child'), root), false);
  assert.equal(m.sinkAllowed(root + '-other', root), true);
  assert.equal(
    m.requestPathname({ url: '/en/_perf?synthetic=1' }),
    '/en/_perf',
  );
  assert.equal(m.requestPathname({}), '/');
  assert.equal(m.requestPathname({ url: 'http://[' }), '');
});

test('origin headers require strings and an exact same-origin value', async () => {
  const m = await module();
  assert.equal(
    m.originAllowed({
      headers: { host: 'synthetic:7', origin: 'http://synthetic:7' },
    }),
    true,
  );
  for (const headers of [
    { host: 'synthetic:7' },
    { origin: 'http://synthetic:7' },
    { host: ['synthetic:7'], origin: 'http://synthetic:7' },
    { host: 'synthetic:7', origin: ['http://synthetic:7'] },
    { host: 'synthetic:7', origin: 'https://synthetic:7' },
  ])
    assert.equal(m.originAllowed({ headers }), false);
  const r = response();
  m.send(r, 201, 'synthetic', 'text/plain');
  assert.deepEqual(plain(r.headers), [
    {
      status: 201,
      headers: {
        'content-type': 'text/plain',
        'content-security-policy': CSP,
        'cache-control': 'no-store',
      },
    },
  ]);
  assert.deepEqual(r.bodies, ['synthetic']);
  const j = response();
  m.sendJson(j, 400, { ok: false, failure: 'synthetic' });
  assert.equal(
    j.headers[0].headers['content-type'],
    'application/json; charset=utf-8',
  );
  assert.deepEqual(j.bodies, ['{"ok":false,"failure":"synthetic"}']);
});

test('body reader preserves chunk bytes and rejects stream errors', async () => {
  const m = await module();
  const request = new EventEmitter();
  const pending = m.readBody(request);
  request.emit('data', Buffer.from('synthetic '));
  request.emit('data', Buffer.from('body'));
  request.emit('end');
  assert.equal(await pending, 'synthetic body');
  const broken = new EventEmitter();
  const failure = m.readBody(broken);
  broken.emit('error', new Error('synthetic'));
  await assert.rejects(failure, /^Error: malformed-payload$/);
  const exact = new EventEmitter();
  exact.pause = () => {
    throw new Error('must accept exact limit');
  };
  const accepted = m.readBody(exact);
  exact.emit('data', Buffer.alloc(2000000, 120));
  exact.emit('end');
  assert.equal((await accepted).length, 2000000);
});

test('trace names have separated random groups and a fixed collision budget', async () => {
  const m = await module();
  assert.match(m.evidenceId(), /^r[0-9a-f]{4}x[0-9a-f]{4}$/);
  assert.match(
    m.traceNames({}, 'synthetic-layer')(),
    /^synthetic-layer\.r[0-9a-f]{4}x[0-9a-f]{4}\.json$/,
  );
  const chosen = () => 'synthetic.json';
  assert.equal(m.traceNames({ traceName: chosen }, 'unused'), chosen);
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'synthetic-exclusive-'));
  try {
    fs.writeFileSync(path.join(folder, 'kept.json'), 'kept');
    let calls = 0;
    assert.deepEqual(
      plain(
        m.exclusiveTrace(folder, { synthetic: true }, () => {
          calls++;
          return 'kept.json';
        }),
      ),
      { ok: false, failure: 'trace-name-collision' },
    );
    assert.equal(calls, 4);
    assert.equal(
      fs.readFileSync(path.join(folder, 'kept.json'), 'utf8'),
      'kept',
    );
    assert.deepEqual(
      plain(m.exclusiveTrace(folder, { synthetic: true }, chosen)),
      { ok: true, name: 'synthetic.json' },
    );
    assert.equal(
      fs.readFileSync(path.join(folder, 'synthetic.json'), 'utf8'),
      '{"synthetic":true}\n',
    );
  } finally {
    fs.rmSync(folder, { recursive: true, force: true });
  }
  const fault = new Error('synthetic-write');
  fault.code = 'EACCES';
  const injected = await module({
    'node:fs': {
      ...fs,
      mkdirSync() {},
      writeFileSync() {
        throw fault;
      },
    },
  });
  assert.throws(
    () => injected.exclusiveTrace('synthetic', {}, chosen),
    (error) => error === fault,
  );
});

test('static serving checks file types and reports filesystem failures', async () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'synthetic-static-'));
  const m = await module();
  try {
    for (const [extension, type] of Object.entries({
      html: 'text/html; charset=utf-8',
      js: 'text/javascript; charset=utf-8',
      css: 'text/css; charset=utf-8',
      json: 'application/json; charset=utf-8',
      map: 'application/json; charset=utf-8',
      txt: 'text/plain; charset=utf-8',
      woff2: 'font/woff2',
      png: 'image/png',
      svg: 'image/svg+xml',
      wasm: 'application/wasm',
      mjs: 'text/javascript; charset=utf-8',
      bin: 'application/octet-stream',
    })) {
      fs.writeFileSync(
        path.join(folder, 'synthetic.' + extension),
        'synthetic',
      );
      const r = response();
      const done = new Promise((resolve) => {
        r.end = (body) => {
          r.bodies.push(body);
          resolve();
        };
      });
      m.serveStatic(folder, '/synthetic.' + extension, r);
      await done;
      assert.equal(r.headers[0].status, 200);
      assert.equal(r.headers[0].headers['content-type'], type);
      assert.equal(String(r.bodies[0]), 'synthetic');
    }
    for (const route of ['/absent.txt', '/']) {
      const r = response();
      const done = new Promise((resolve) => {
        r.end = (body) => {
          r.bodies.push(body);
          resolve();
        };
      });
      m.serveStatic(folder, route, r);
      await done;
      assert.equal(r.headers[0].status, 404);
      assert.equal(r.bodies[0], 'unknown-route');
    }
    const escaped = response();
    m.serveStatic(folder, '../escape.txt', escaped);
    assert.equal(escaped.headers[0].status, 400);
    assert.equal(escaped.bodies[0], 'bad path');
    const injected = await module({
      'node:fs': {
        ...fs,
        stat(_file, callback) {
          callback(null, { isFile: () => true });
        },
        readFile(_file, callback) {
          callback(new Error('synthetic-read'));
        },
      },
    });
    const failure = response();
    injected.serveStatic(folder, '/synthetic.txt', failure);
    assert.equal(failure.headers[0].status, 500);
    assert.equal(failure.bodies[0], 'read failed');
  } finally {
    fs.rmSync(folder, { recursive: true, force: true });
  }
});

test('request routing retains post counts and delegates page and asset requests', async () => {
  const m = await module();
  const options = { tracePosts: 3 };
  for (const [url, method, status, body] of [
    ['/__perf/posts', 'GET', 200, '3'],
    ['/__perf/posts', 'POST', 405, 'method-not-allowed'],
    ['/__perf/trace', 'GET', 405, 'method-not-allowed'],
    ['/unknown', 'GET', 404, 'unknown-route'],
  ]) {
    const r = response();
    m.handle({ url, method }, r, options, null);
    assert.equal(r.headers[0].status, status);
    assert.equal(r.bodies[0], body);
  }
  assert.equal(m.tracePosts({}), 0);
  assert.equal(m.tracePosts({ tracePosts: '3' }), 0);
  assert.equal(m.tracePosts(options), 3);
  for (const url of [
    '/en/_perf?synthetic=1',
    '/ar/_perf?synthetic=1',
    '/synthetic.js',
  ]) {
    const r = response();
    const req = { url, method: 'GET' };
    let calls = 0;
    m.handle(req, r, options, () => calls++);
    assert.equal(calls, 1);
    assert.equal(
      req.url,
      url.includes('_perf') ? '/index.html?synthetic=1' : url,
    );
    assert.deepEqual(r.bodies, []);
  }
  const plugin = m.tracePlugin(options);
  assert.equal(plugin.name, 'eii-performance-trace');
  let middleware;
  plugin.configureServer({
    middlewares: {
      use(fn) {
        middleware = fn;
      },
    },
  });
  let next = 0;
  middleware({ url: '/main' }, response(), () => next++);
  assert.equal(next, 1);
  const r = response();
  middleware({ url: '/__perf/posts', method: 'GET' }, r, () => next++);
  assert.equal(r.bodies[0], '3');
  assert.equal(next, 1);
});

test('listening failures and Vite cleanup are observable without starting a native server', async () => {
  const m = await module();
  for (const address of [null, 'synthetic']) {
    const fake = {
      once() {},
      listen(port, host, done) {
        assert.equal(port, 0);
        assert.equal(host, '127.0.0.1');
        done();
      },
      address: () => address,
    };
    await assert.rejects(m.listen(fake), /^Error: server did not bind a port$/);
  }
  let closed = 0;
  const fake = {
    once() {},
    listen(_port, _host, done) {
      done();
    },
    address: () => ({ port: 123 }),
    close(done) {
      closed++;
      done();
    },
  };
  const listened = await m.listen(fake);
  assert.equal(listened.origin, 'http://127.0.0.1:123');
  assert.equal(listened.addressLine, 'http://127.0.0.1:123/en/_perf');
  await listened.close();
  assert.equal(closed, 1);
  for (const bound of [undefined, null, 'synthetic', { port: 123 }]) {
    let closes = 0;
    const injected = await module({
      vite: {
        async createServer(options) {
          assert.deepEqual(plain(options.server), {
            host: '127.0.0.1',
            port: 0,
            strictPort: false,
          });
          assert.equal(options.logLevel, 'silent');
          assert.ok(options.configFile.endsWith('/performance/vite.config.ts'));
          return {
            async listen() {},
            httpServer:
              bound === undefined ? undefined : { address: () => bound },
            async close() {
              closes++;
            },
          };
        },
      },
    });
    const result = await injected.startViteServer({ mode: 'development' });
    if (typeof bound === 'object' && bound !== null) {
      assert.equal(result.ok, true);
      assert.equal(result.addressLine, 'http://127.0.0.1:123/en/_perf');
      await result.close();
    } else
      assert.deepEqual(plain(result), {
        ok: false,
        failure: 'server did not bind a port',
      });
    assert.equal(closes, 1);
  }
  assert.deepEqual(plain(await m.startViteServer({ mode: 'production' })), {
    ok: false,
    failure: 'non-development',
  });
  assert.deepEqual(plain(await m.startStaticServer({ mode: 'production' })), {
    ok: false,
    failure: 'non-development',
  });
});

test('trace receipt handles malformed bodies, safe layer names, stamps and native paths', async () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'synthetic-receive-'));
  const m = await module();
  try {
    let ordinal = 0;
    async function post(body, patch = {}) {
      const request = new EventEmitter();
      request.headers = { host: 'synthetic', origin: 'http://synthetic' };
      request.pause = () => {};
      request.destroy = () => {};
      const r = response();
      const options = {
        sink: folder,
        native: false,
        traceName: () => `synthetic-${ordinal++}.json`,
        ...patch,
      };
      const result = m.receiveTrace(request, r, options);
      request.emit(
        'data',
        Buffer.from(typeof body === 'string' ? body : JSON.stringify(body)),
      );
      request.emit('end');
      await result;
      return { status: r.headers[0].status, body: JSON.parse(r.bodies[0]) };
    }
    for (const body of ['{', 'null', 'true', '[]', '1', '"synthetic"']) {
      const result = await post(body, {
        stamp: { codeCommit: 'synthetic', lockSha256: 'synthetic' },
      });
      assert.equal(result.status, 400);
      assert.equal(result.body.ok, false);
      assert.equal(
        result.body.failure,
        body === '{' ? 'malformed-payload' : 'missing-field',
      );
    }
    for (const layerSet of [
      1,
      ['synthetic'],
      '!synthetic',
      'synthetic!',
      'synthetic--layer',
      'Synthetic',
    ]) {
      const result = await post({ ...mutationTrace(), layerSet });
      assert.deepEqual(result, {
        status: 400,
        body: { ok: false, failure: 'unknown-layer-set' },
      });
    }
    const traceValue = { ...mutationTrace(), webglRenderer: 'remote' };
    const stamped = await post(traceValue, {
      native: true,
      stamp: {
        codeCommit: 'server-stamp',
        lockSha256: `sha256:${'ef'.repeat(32)}`,
      },
    });
    assert.equal(stamped.status, 200);
    assert.equal(stamped.body.ok, true);
    assert.equal(stamped.body.qualification, 'remote-renderer');
    assert.ok(stamped.body.path.startsWith('web/spikes/performance/evidence/'));
    const saved = JSON.parse(
      fs.readFileSync(
        path.join(folder, path.basename(stamped.body.path)),
        'utf8',
      ),
    );
    assert.equal(saved.codeCommit, 'server-stamp');
    assert.equal(saved.lockSha256, `sha256:${'ef'.repeat(32)}`);
    const unstamped = await post(traceValue);
    assert.equal(unstamped.body.qualification, 'remote-renderer');
    assert.equal(
      JSON.parse(
        fs.readFileSync(path.join(folder, unstamped.body.path), 'utf8'),
      ).codeCommit,
      'synthetic-commit',
    );
    const collision = await post(traceValue, {
      traceName: () => unstamped.body.path,
    });
    assert.deepEqual(collision, {
      status: 400,
      body: { ok: false, failure: 'trace-name-collision' },
    });
  } finally {
    fs.rmSync(folder, { recursive: true, force: true });
  }
});

test('owner mode and repository stamp retain explicit environment and source identity', async () => {
  for (const [mode, expected] of [
    ['production', 'production'],
    ['development', 'development'],
    [undefined, 'development'],
  ]) {
    const m = await module(
      {},
      { process: { ...process, env: { ...process.env, NODE_ENV: mode } } },
    );
    assert.equal(m.ownerMode(), expected);
  }
  for (const status of [0, 1]) {
    const m = await module({
      'node:child_process': {
        spawnSync(command, args, options) {
          assert.equal(command, 'git');
          assert.deepEqual(Array.from(args), ['rev-parse', 'HEAD']);
          assert.equal(options.encoding, 'utf8');
          return { status, stdout: ' synthetic-commit \n' };
        },
      },
      'node:fs': {
        ...fs,
        readFileSync(file) {
          assert.ok(file.endsWith('/web/package-lock.json'));
          return Buffer.from('synthetic lock');
        },
      },
    });
    const stamp = m.repositoryStamp();
    assert.equal(
      stamp.codeCommit,
      status === 0 ? 'synthetic-commit' : 'unknown',
    );
    assert.match(stamp.lockSha256, /^sha256:[0-9a-f]{64}$/);
  }
});
