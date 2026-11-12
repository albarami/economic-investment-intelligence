import { spawn } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import net from 'node:net';
import path from 'node:path';

const PARENT_ENV_NAMES = ['PATH', 'TMPDIR', 'LANG'];
const STOP_WAIT_MS = 5000;
const ESCAPE_CHARACTER = String.fromCharCode(27);
const ANSI_ESCAPE = new RegExp(`${ESCAPE_CHARACTER}\\[[0-9;]*m`, 'g');

function ruleError(message) {
  const error = new Error(message);
  error.rule = 'start-failed';
  return error;
}

export function resolveViteBin(dir) {
  const pkgPath = path.join(dir, 'node_modules', 'vite', 'package.json');
  let text;
  try {
    const info = fs.statSync(pkgPath);
    if (!info.isFile())
      throw ruleError(
        'node_modules/vite/package.json: cannot be read (EISDIR)',
      );
    text = fs.readFileSync(pkgPath, 'utf8');
  } catch (error) {
    if (error.rule) throw error;
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') {
      throw ruleError('node_modules/vite/package.json: missing');
    }
    throw ruleError(
      `node_modules/vite/package.json: cannot be read (${error.code || error.name})`,
    );
  }
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw ruleError('node_modules/vite/package.json: not valid JSON');
  }
  let relativeBin = null;
  if (typeof data.bin === 'string' && data.bin.length > 0)
    relativeBin = data.bin;
  else if (
    data.bin &&
    typeof data.bin === 'object' &&
    typeof data.bin.vite === 'string' &&
    data.bin.vite.length > 0
  ) {
    relativeBin = data.bin.vite;
  }
  if (relativeBin === null) {
    throw ruleError(
      'node_modules/vite/package.json: bin field is absent or has no entry named vite',
    );
  }
  const target = path.join(dir, 'node_modules', 'vite', relativeBin);
  let isFile;
  try {
    isFile = fs.statSync(target).isFile();
  } catch {
    isFile = false;
  }
  if (!isFile) {
    const rel = path.relative(dir, target).split(path.sep).join('/');
    throw ruleError(`vite binary not found: ${rel}`);
  }
  return target;
}

export function childEnvironment(home) {
  const env = {};
  for (const name of PARENT_ENV_NAMES) {
    if (process.env[name] !== undefined) env[name] = process.env[name];
  }
  env.HOME = home;
  env.BROWSER = 'none';
  return env;
}

export function choosePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      server.close((error) => (error ? reject(error) : resolve(port)));
    });
  });
}

export function probePort(port) {
  return new Promise((resolve) => {
    const socket = net.connect({ host: '127.0.0.1', port });
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      socket.destroy();
      resolve(value);
    };
    const timer = setTimeout(() => finish('other'), 1000);
    socket.once('connect', () => finish('open'));
    socket.once('error', (error) =>
      finish(error.code === 'ECONNREFUSED' ? 'free' : 'other'),
    );
  });
}

export function startChild({ bin, args, cwd, env }) {
  const child = spawn(process.execPath, [bin, ...args], {
    cwd,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let output = '';
  child.stdout.on('data', (chunk) => {
    output += chunk.toString('utf8');
  });
  child.stderr.on('data', (chunk) => {
    output += chunk.toString('utf8');
  });
  return { child, text: () => output };
}

export async function stopChild(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  child.kill('SIGTERM');
  await new Promise((resolve) => {
    if (child.exitCode !== null || child.signalCode !== null) {
      resolve();
      return;
    }
    let timer;
    const onExit = () => {
      clearTimeout(timer);
      resolve();
    };
    timer = setTimeout(() => {
      child.removeListener('exit', onExit);
      resolve();
    }, STOP_WAIT_MS);
    child.once('exit', onExit);
  });
  if (child.exitCode === null && child.signalCode === null) {
    child.kill('SIGKILL');
    await new Promise((resolve) => {
      if (child.exitCode !== null || child.signalCode !== null) resolve();
      else child.once('exit', () => resolve());
    });
  }
}

export function httpGet(url, timeoutMs) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (fn, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      fn(value);
    };
    const req = http.get(url, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        finish(resolve, {
          status: res.statusCode,
          headers: res.headers,
          body: Buffer.concat(chunks).toString('utf8'),
        });
      });
    });
    const timer = setTimeout(() => {
      req.destroy();
      const error = new Error('timed out');
      error.code = 'TIMEOUT';
      finish(reject, error);
    }, timeoutMs);
    req.on('error', (error) => finish(reject, error));
  });
}

export function hasLocalLine(output, port) {
  const clean = output.replace(ANSI_ESCAPE, '');
  const expected = `http://127.0.0.1:${port}/`;
  return clean.split(/\r?\n/).some((line) => {
    const at = line.indexOf('Local:');
    if (at < 0) return false;
    const match = /^(\s+)(\S+)(\s*)$/.exec(line.slice(at + 'Local:'.length));
    return match !== null && match[2] === expected;
  });
}

export function announcesNetwork(output) {
  const clean = output.replace(ANSI_ESCAPE, '');
  return clean.split(/\r?\n/).some((line) => /Network:\s+http/.test(line));
}
