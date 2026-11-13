import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { CSP } from './guards.mjs';

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.woff2': 'font/woff2',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
};

function fileFor(root, urlPath) {
  const decoded = decodeURIComponent(urlPath.split('?')[0]);
  const relative = decoded === '/' ? 'index.html' : decoded.replace(/^\/+/, '');
  const rootResolved = path.resolve(root);
  const full = path.resolve(rootResolved, relative);
  if (full !== rootResolved && !full.startsWith(`${rootResolved}${path.sep}`)) {
    return null;
  }
  return full;
}

function send(response, status, body, type) {
  response.writeHead(status, {
    'content-type': type,
    'content-security-policy': CSP,
    'cache-control': 'no-store',
  });
  response.end(body);
}

export function startServer(root) {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url ?? '/', 'http://127.0.0.1');
    const file = fileFor(root, url.pathname);
    if (file === null) {
      send(response, 400, 'bad path', 'text/plain; charset=utf-8');
      return;
    }
    fs.stat(file, (error, info) => {
      if (error || !info.isFile()) {
        send(response, 404, 'not found', 'text/plain; charset=utf-8');
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
        close() {
          return new Promise((done) => {
            server.close(() => done());
          });
        },
      });
    });
  });
}
