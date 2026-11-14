import { ROAD_LOADS } from './config.mjs';
import { createHash, randomBytes } from 'node:crypto';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import { CSP } from '../glyphs/guards.mjs';
import { judgeSubmission, validateGate } from './trace.mjs';

const SPIKE = path.dirname(fileURLToPath(import.meta.url));
export const MAX_BODY_BYTES = 2000000;
const PAGE_ROUTES = new Set(['/en/_perf', '/ar/_perf']);
const TRACE_ROUTE = '/__perf/trace';
const POSTS_ROUTE = '/__perf/posts';
const LAYER_SET_NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.woff2': 'font/woff2',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.wasm': 'application/wasm',
  '.mjs': 'text/javascript; charset=utf-8',
};

export function assertDevelopment(mode) {
  if (mode !== 'development') return { ok: false, failure: 'non-development' };
  return { ok: true };
}

export function sinkAllowed(sink, evidenceDir) {
  const resolved = path.resolve(sink);
  const evidence = path.resolve(evidenceDir);
  if (resolved === evidence) return false;
  if (resolved.startsWith(`${evidence}${path.sep}`)) return false;
  return true;
}

const TRACE_NAME_ATTEMPTS = 4;

function evidenceId() {
  const hex = randomBytes(4).toString('hex');
  return `r${hex.slice(0, 4)}x${hex.slice(4)}`;
}

function traceNames(options, layerSet) {
  if (typeof options.traceName === 'function') return options.traceName;
  return () => `${layerSet}.${evidenceId()}.json`;
}

function exclusiveTrace(sink, body, nextName) {
  const text = `${JSON.stringify(body)}\n`;
  fs.mkdirSync(sink, { recursive: true });
  for (let attempt = 0; attempt < TRACE_NAME_ATTEMPTS; attempt += 1) {
    const name = nextName();
    try {
      fs.writeFileSync(path.join(sink, name), text, { flag: 'wx' });
      return { ok: true, name };
    } catch (error) {
      if (error.code === 'EEXIST') continue;
      throw error;
    }
  }
  return { ok: false, failure: 'trace-name-collision' };
}

function classify(pathname) {
  if (PAGE_ROUTES.has(pathname)) return 'page';
  if (pathname === POSTS_ROUTE) return 'posts';
  if (pathname === TRACE_ROUTE) return 'trace';
  if (pathname.startsWith('/@') || pathname.startsWith('/node_modules/')) {
    return 'asset';
  }
  if (pathname.includes('.')) return 'asset';
  return 'unknown';
}

function send(response, status, body, type) {
  response.writeHead(status, {
    'content-type': type,
    'content-security-policy': CSP,
    'cache-control': 'no-store',
  });
  response.end(body);
}

function sendJson(response, status, payload) {
  send(
    response,
    status,
    JSON.stringify(payload),
    'application/json; charset=utf-8',
  );
}

function originAllowed(request) {
  const host = request.headers.host;
  const origin = request.headers.origin;
  if (typeof host !== 'string' || typeof origin !== 'string') return false;
  return origin === `http://${host}`;
}

function readBody(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    let rejected = false;
    request.on('data', (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY_BYTES) {
        rejected = true;
        request.pause();
        reject(new Error('malformed-payload'));
        return;
      }
      chunks.push(chunk);
    });
    request.on('end', () => {
      if (!rejected) resolve(Buffer.concat(chunks).toString('utf8'));
    });
    request.on('error', () => {
      if (!rejected) reject(new Error('malformed-payload'));
    });
  });
}

function fileFor(root, urlPath) {
  const relative = urlPath.replace(/^\/+/, '');
  const rootResolved = path.resolve(root);
  const full = path.resolve(rootResolved, relative);
  if (full !== rootResolved && !full.startsWith(`${rootResolved}${path.sep}`)) {
    return null;
  }
  return full;
}

function publicPath(native, name) {
  if (native) return `web/spikes/performance/evidence/${name}`;
  return name;
}

async function receiveTrace(request, response, options) {
  if (!originAllowed(request)) {
    sendJson(response, 403, { ok: false, failure: 'wrong-origin' });
    return;
  }
  let text;
  try {
    text = await readBody(request);
  } catch {
    sendJson(response, 400, { ok: false, failure: 'malformed-payload' });
    response.on('finish', () => {
      request.destroy();
    });
    return;
  }
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    sendJson(response, 400, { ok: false, failure: 'malformed-payload' });
    return;
  }
  if (options.stamp && body !== null && typeof body === 'object') {
    body.codeCommit = options.stamp.codeCommit;
    body.lockSha256 = options.stamp.lockSha256;
  }
  const judged = judgeSubmission(body);
  if (!judged.ok) {
    sendJson(response, 400, { ok: false, failure: judged.failure });
    return;
  }
  if (
    typeof body.layerSet !== 'string' ||
    !LAYER_SET_NAME.test(body.layerSet)
  ) {
    sendJson(response, 400, { ok: false, failure: 'unknown-layer-set' });
    return;
  }
  const stored = exclusiveTrace(
    options.sink,
    body,
    traceNames(options, body.layerSet),
  );
  if (!stored.ok) {
    sendJson(response, 400, { ok: false, failure: stored.failure });
    return;
  }
  const qualification = validateGate(body, body.layerSet, null);
  sendJson(response, 200, {
    ok: true,
    path: publicPath(options.native, stored.name),
    qualification: qualification.ok ? 'pass' : qualification.failure,
  });
}

function serveStatic(root, urlPath, response) {
  const file = fileFor(root, urlPath);
  if (file === null) {
    send(response, 400, 'bad path', 'text/plain; charset=utf-8');
    return;
  }
  fs.stat(file, (error, info) => {
    if (error || !info.isFile()) {
      send(response, 404, 'unknown-route', 'text/plain; charset=utf-8');
      return;
    }
    const type = TYPES[path.extname(file)] ?? 'application/octet-stream';
    fs.readFile(file, (readError, body) => {
      if (readError) {
        send(response, 500, 'read failed', 'text/plain; charset=utf-8');
        return;
      }
      send(response, 200, body, type);
    });
  });
}

function tracePosts(options) {
  if (typeof options.tracePosts !== 'number') options.tracePosts = 0;
  return options.tracePosts;
}

function handle(request, response, options, next) {
  const url = new URL(request.url ?? '/', 'http://127.0.0.1');
  const kind = classify(url.pathname);
  if (kind === 'unknown') {
    send(response, 404, 'unknown-route', 'text/plain; charset=utf-8');
    return;
  }
  if (kind === 'posts') {
    if (request.method !== 'GET') {
      send(response, 405, 'method-not-allowed', 'text/plain; charset=utf-8');
      return;
    }
    send(
      response,
      200,
      String(tracePosts(options)),
      'text/plain; charset=utf-8',
    );
    return;
  }
  if (kind === 'trace') {
    if (request.method !== 'POST') {
      send(response, 405, 'method-not-allowed', 'text/plain; charset=utf-8');
      return;
    }
    options.tracePosts = tracePosts(options) + 1;
    void receiveTrace(request, response, options);
    return;
  }
  if (kind === 'page') {
    if (next) {
      request.url = `/index.html${url.search}`;
      next();
      return;
    }
    serveStatic(options.root, '/index.html', response);
    return;
  }
  if (next) {
    next();
    return;
  }
  serveStatic(options.root, url.pathname, response);
}

function requestPathname(request) {
  try {
    return new URL(request.url ?? '/', 'http://127.0.0.1').pathname;
  } catch {
    return '';
  }
}

function tracePlugin(options) {
  return {
    name: 'eii-performance-trace',
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const pathname = requestPathname(request);
        if (pathname !== TRACE_ROUTE && pathname !== POSTS_ROUTE) {
          next();
          return;
        }
        handle(request, response, options, next);
      });
    },
  };
}

function listen(server) {
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      if (address === null || typeof address === 'string') {
        reject(new Error('server did not bind a port'));
        return;
      }
      const origin = `http://127.0.0.1:${address.port}`;
      resolve({
        ok: true,
        origin,
        addressLine: `${origin}/en/_perf`,
        close() {
          return new Promise((done) => {
            server.close(() => done());
          });
        },
      });
    });
  });
}

export function startStaticServer(options) {
  const mode = assertDevelopment(options.mode ?? 'development');
  if (!mode.ok) return Promise.resolve(mode);
  if (!options.native && !sinkAllowed(options.sink, options.evidenceDir)) {
    return Promise.resolve({ ok: false, failure: 'native-evidence-protected' });
  }
  const server = http.createServer((request, response) => {
    handle(request, response, options, null);
  });
  return listen(server);
}

export async function startViteServer(options) {
  const mode = assertDevelopment(options.mode ?? 'development');
  if (!mode.ok) return mode;
  const vite = await createServer({
    configFile: path.join(SPIKE, 'vite.config.ts'),
    server: { host: '127.0.0.1', port: 0, strictPort: false },
    logLevel: 'silent',
    plugins: [tracePlugin(options)],
  });
  await vite.listen();
  const bound = vite.httpServer?.address();
  if (bound === undefined || bound === null || typeof bound === 'string') {
    await vite.close();
    return { ok: false, failure: 'server did not bind a port' };
  }
  const origin = `http://127.0.0.1:${bound.port}`;
  return {
    ok: true,
    origin,
    addressLine: `${origin}/en/_perf`,
    async close() {
      await vite.close();
    },
  };
}

function repositoryStamp() {
  const root = path.resolve(SPIKE, '..', '..', '..');
  const lockPath = path.join(root, 'web', 'package-lock.json');
  const lockSha256 = `sha256:${createHash('sha256').update(fs.readFileSync(lockPath)).digest('hex')}`;
  const commit = spawnSync('git', ['rev-parse', 'HEAD'], {
    cwd: root,
    encoding: 'utf8',
  });
  return {
    codeCommit: commit.status === 0 ? commit.stdout.trim() : 'unknown',
    lockSha256,
  };
}

function ownerMode() {
  return process.env.NODE_ENV === 'production' ? 'production' : 'development';
}

async function main() {
  const evidenceDir = path.join(SPIKE, 'evidence');
  const started = await startViteServer({
    mode: ownerMode(),
    root: SPIKE,
    sink: evidenceDir,
    evidenceDir,
    native: true,
    stamp: repositoryStamp(),
  });
  if (!started.ok) {
    console.error(`FAIL ${started.failure}`);
    process.exitCode = 1;
    return;
  }
  console.log(started.addressLine);
  for (const name of Object.keys(ROAD_LOADS))
    console.log(`${started.addressLine}?layers=${name}`);
  await new Promise(() => {});
}

if (
  process.argv[1] &&
  fileURLToPath(import.meta.url) === path.resolve(process.argv[1])
) {
  await main();
}
