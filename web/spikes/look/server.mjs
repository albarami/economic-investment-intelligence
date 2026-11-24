import fs from 'node:fs';
import http from 'node:http';
import https from 'node:https';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { browserHome } from '../glyphs/browser-home.mjs';
import { buildPage, removePage } from './build-page.mjs';
import { CSP, ROUTES } from './guards.mjs';
import {
  billableView,
  formatSessionLog,
  googleOrigin,
  resolveRoot,
  resolveTile,
  validSession,
} from './photoreal.mjs';
import {
  BASEMAP_ROUTE,
  BUILDINGS_ROUTE,
  buildRelease,
  locateBuildings,
} from './release-build.mjs';
import { serialiseRelease } from './release-shape.mjs';

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
};

// The empty data block of index.html that the release is written into.
export const RELEASE_BLOCK =
  '<script type="application/json" id="eii-release"></script>';

export function repositoryRoot(moduleUrl = import.meta.url) {
  return path.resolve(browserHome(moduleUrl), '..', '..', '..');
}

function headers(type, extra = {}) {
  return {
    'content-type': type,
    'content-security-policy': CSP,
    'cache-control': 'no-store',
    ...extra,
  };
}

function send(response, status, body, type) {
  response.writeHead(status, headers(type));
  response.end(body);
}

// One byte range of the form "bytes=a-b", "bytes=a-" or "bytes=-n".
export function parseRange(header, size) {
  if (header === undefined) return null;
  const match = /^bytes=(\d*)-(\d*)$/.exec(header.trim());
  if (match === null || (match[1] === '' && match[2] === '')) return 'bad';
  let start;
  let end;
  if (match[1] === '') {
    const tail = Number(match[2]);
    start = Math.max(0, size - tail);
    end = size - 1;
  } else {
    start = Number(match[1]);
    end = match[2] === '' ? size - 1 : Math.min(Number(match[2]), size - 1);
  }
  if (start > end || start >= size) return 'bad';
  return { start, end };
}

function sendFileRange(request, response, file) {
  fs.stat(file, (error, stat) => {
    if (error || !stat.isFile()) {
      send(response, 404, 'not found', 'text/plain; charset=utf-8');
      return;
    }
    const range = parseRange(request.headers.range, stat.size);
    if (range === 'bad') {
      response.writeHead(
        416,
        headers('text/plain; charset=utf-8', {
          'content-range': `bytes */${stat.size}`,
        }),
      );
      response.end('range not satisfiable');
      return;
    }
    const type = 'application/octet-stream';
    if (range === null) {
      response.writeHead(
        200,
        headers(type, {
          'accept-ranges': 'bytes',
          'content-length': String(stat.size),
        }),
      );
      fs.createReadStream(file).pipe(response);
      return;
    }
    response.writeHead(
      206,
      headers(type, {
        'accept-ranges': 'bytes',
        'content-range': `bytes ${range.start}-${range.end}/${stat.size}`,
        'content-length': String(range.end - range.start + 1),
      }),
    );
    fs.createReadStream(file, { start: range.start, end: range.end }).pipe(
      response,
    );
  });
}

function fileFor(root, pathname) {
  if (!pathname.includes('.')) return null;
  const rootResolved = path.resolve(root);
  const full = path.resolve(rootResolved, pathname.replace(/^\/+/, ''));
  if (!full.startsWith(`${rootResolved}${path.sep}`)) return null;
  return full;
}

// Serves a built look page on a loopback port: the two routes /en/_look and
// /ar/_look with the release written into their data block, the basemap
// extract with HTTP range requests, the built assets, and nothing else.
// Every response carries the same-origin content security policy of the
// glyph spike.
function upstream(url) {
  return new Promise((resolve, reject) => {
    const request = https.request(url, { method: 'GET' }, (incoming) => {
      const chunks = [];
      incoming.on('aborted', () => reject(new Error('upstream interrupted')));
      incoming.on('error', reject);
      incoming.on('data', (chunk) => chunks.push(chunk));
      incoming.on('end', () => {
        const body = Buffer.concat(chunks);
        resolve({
          status: incoming.statusCode ?? 0,
          headers: {
            get: (name) => {
              const value = incoming.headers[name.toLowerCase()];
              if (Array.isArray(value)) return value.join(', ');
              return value ?? null;
            },
          },
          text: () => Promise.resolve(body.toString('utf8')),
          arrayBuffer: () =>
            Promise.resolve(
              body.buffer.slice(
                body.byteOffset,
                body.byteOffset + body.byteLength,
              ),
            ),
        });
      });
    });
    request.on('error', reject);
    request.end();
  });
}

function sessionFile(repository) {
  return path.join(repository, 'data', 'photoreal', 'session.json');
}

function usageLog(file) {
  return path.join(path.dirname(file), 'sessions.log');
}

function readSession(file) {
  try {
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    if (!validSession(parsed)) throw new Error('invalid accounting state');
    return parsed;
  } catch (error) {
    if (error?.code === 'ENOENT' && !fs.existsSync(path.dirname(file)))
      return null;
    throw new Error('accounting unavailable', { cause: error });
  }
}

function writeSession(file, record) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temporary = `${file}.tmp`;
  // An exclusive temporary file also refuses stale interrupted writes.
  const fd = fs.openSync(temporary, 'wx', 0o600);
  try {
    fs.writeFileSync(fd, JSON.stringify(record));
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
  fs.renameSync(temporary, file);
  const directory = fs.openSync(path.dirname(file), 'r');
  try {
    fs.fsyncSync(directory);
  } finally {
    fs.closeSync(directory);
  }
}

function remember(file, before, resolved) {
  const previous = before?.count ?? 0;
  if (
    resolved.record &&
    (resolved.status === 200 || resolved.record.count !== previous)
  ) {
    writeSession(file, resolved.record);
  }
}

export async function startLookServer(root, options = {}) {
  const repository = options.repositoryRoot ?? repositoryRoot();
  const built = await buildRelease(
    repository,
    options.env,
    options.standInFile,
  );
  const buildings = locateBuildings(repository);
  const apiKey =
    typeof options.apiKey === 'string'
      ? options.apiKey
      : (process.env.MAPTILE_API_KEY ?? '');
  const fetchImpl = options.fetch ?? upstream;
  const sessionPath = options.sessionFile ?? sessionFile(repository);
  const exclusive = async (task) => {
    const created = fs.mkdirSync(path.dirname(sessionPath), {
      recursive: true,
    });
    const canonical = path.join(
      fs.realpathSync(path.dirname(sessionPath)),
      path.basename(sessionPath),
    );
    const lock = `${canonical}.lock`;
    // Shared across processes. Busy or abandoned locks refuse; never steal.
    fs.mkdirSync(lock);
    try {
      if (created !== undefined)
        writeSession(sessionPath, { count: 0, fetchedAt: 0, root: '' });
      return await task();
    } finally {
      fs.rmdirSync(lock);
    }
  };
  let sessionCount = 0;
  let logged = false;
  let gate = Promise.resolve();
  const enqueue = (task) => {
    const run = gate.then(task, task);
    gate = run.then(
      () => undefined,
      () => undefined,
    );
    return run;
  };
  const reserve = async (next) => {
    writeSession(sessionPath, next.record);
    sessionCount = next.session;
  };
  const writeUsage = () => {
    if (logged) return;
    logged = true;
    const view = billableView(readSession(sessionPath), sessionCount);
    fs.mkdirSync(path.dirname(sessionPath), { recursive: true });
    fs.appendFileSync(usageLog(sessionPath), `${formatSessionLog(view)}\n`);
  };
  const page = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  if (!page.includes(RELEASE_BLOCK)) {
    throw new Error('the built page has no release data block');
  }
  const filled = RELEASE_BLOCK.replace(
    '></',
    `>${serialiseRelease(built.release)}</`,
  );
  const html = page.replace(RELEASE_BLOCK, () => filled);
  const server = http.createServer((request, response) => {
    let pathname;
    try {
      pathname = decodeURIComponent(
        new URL(request.url ?? '/', 'http://127.0.0.1').pathname,
      );
    } catch {
      send(response, 400, 'bad path', 'text/plain; charset=utf-8');
      return;
    }
    if (ROUTES.includes(pathname)) {
      send(response, 200, html, TYPES['.html']);
      return;
    }
    if (pathname === BASEMAP_ROUTE) {
      if (built.file === null) {
        send(response, 404, 'no basemap extract', 'text/plain; charset=utf-8');
        return;
      }
      sendFileRange(request, response, built.file);
      return;
    }
    if (pathname === BUILDINGS_ROUTE) {
      if (!buildings.ok) {
        send(response, 404, 'no building archive', 'text/plain; charset=utf-8');
        return;
      }
      sendFileRange(request, response, buildings.file);
      return;
    }
    if (pathname === '/photoreal/status') {
      let view;
      try {
        view = billableView(readSession(sessionPath), sessionCount);
      } catch {
        send(
          response,
          503,
          'accounting unavailable',
          'text/plain; charset=utf-8',
        );
        return;
      }
      send(
        response,
        200,
        JSON.stringify({ available: apiKey !== '', ...view }),
        TYPES['.json'],
      );
      return;
    }
    if (
      (pathname === '/photoreal/root.json' || pathname === '/photoreal/tile') &&
      apiKey === ''
    ) {
      send(response, 404, 'photoreal unavailable', 'text/plain; charset=utf-8');
      return;
    }
    if (pathname === '/photoreal/root.json') {
      enqueue(() =>
        exclusive(async () => {
          const current = readSession(sessionPath);
          const resolved = await resolveRoot({
            key: apiKey,
            record: current,
            session: sessionCount,
            now: Date.now(),
            reserve,
            fetchRoot: async () => {
              const target = googleOrigin('/v1/3dtiles/root.json');
              target.searchParams.set('key', apiKey);
              const upstreamResponse = await fetchImpl(target, {
                redirect: 'manual',
              });
              return {
                status: upstreamResponse.status,
                body: await upstreamResponse.text(),
              };
            },
          });
          sessionCount = resolved.session;
          remember(sessionPath, current, resolved);
          const type =
            resolved.status === 200
              ? TYPES['.json']
              : 'text/plain; charset=utf-8';
          const body =
            resolved.status === 200 ? resolved.body : 'photoreal unavailable';
          send(response, resolved.status, body, type);
        }),
      ).catch(() => {
        send(
          response,
          503,
          'photoreal unavailable',
          'text/plain; charset=utf-8',
        );
      });
      return;
    }
    if (pathname === '/photoreal/tile') {
      const query = new URL(request.url ?? '/', 'http://127.0.0.1');
      const pathAndQuery = query.searchParams.get('path') ?? '';
      enqueue(() =>
        exclusive(async () => {
          const current = readSession(sessionPath);
          const resolved = await resolveTile({
            key: apiKey,
            record: current,
            session: sessionCount,
            pathAndQuery,
            reserve,
            fetchTile: (target) => fetchImpl(target, { redirect: 'manual' }),
          });
          sessionCount = resolved.session;
          remember(sessionPath, current, resolved);
          send(response, resolved.status, resolved.body, resolved.type);
        }),
      ).catch(() => {
        send(response, 503, 'tile failed', 'text/plain; charset=utf-8');
      });
      return;
    }
    const file = fileFor(root, pathname);
    if (file === null) {
      send(response, 404, 'unknown route', 'text/plain; charset=utf-8');
      return;
    }
    fs.readFile(file, (error, body) => {
      if (error) {
        send(response, 404, 'not found', 'text/plain; charset=utf-8');
        return;
      }
      const type = TYPES[path.extname(file)] ?? 'application/octet-stream';
      send(response, 200, body, type);
    });
  });
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      if (address === null || typeof address === 'string') {
        reject(new Error('server did not bind a port'));
        return;
      }
      resolve({
        origin: `http://127.0.0.1:${address.port}`,
        release: built.release,
        basemap: built.file !== null,
        close() {
          return new Promise((done) => {
            if (logged) {
              done();
              return;
            }
            try {
              if (apiKey !== '') writeUsage();
            } catch {
              // Refuse to invent usage on corrupt state; still close sockets.
            }
            logged = true;
            server.closeAllConnections();
            server.close(() => done());
          });
        },
      });
    });
  });
}

async function main() {
  const outDir = await buildPage();
  const server = await startLookServer(outDir);
  if (!server.basemap) {
    console.log(`basemap extract absent: ${server.release.basemap.missing}`);
  }
  console.log(`${server.origin}/en/_look`);
  console.log(`${server.origin}/ar/_look`);
  const stop = async () => {
    await server.close();
    removePage(outDir);
    process.exit(0);
  };
  process.once('SIGINT', stop);
  process.once('SIGTERM', stop);
}

if (
  process.argv[1] &&
  fileURLToPath(import.meta.url) === path.resolve(process.argv[1])
) {
  await main();
}
