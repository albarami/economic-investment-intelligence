import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { scanTags, scanText } from './host-scan-rules.mjs';
import {
  announcesNetwork,
  childEnvironment,
  choosePort,
  hasLocalLine,
  httpGet,
  probePort,
  resolveViteBin,
  startChild,
  stopChild,
} from './dev-server-process.mjs';

export { resolveViteBin };

const MAX_PORT = 65535;
const DEFAULT_TIMEOUT_MS = 30000;
const OUTER_BOUND_MS = 60000;
const POLL_INTERVAL_MS = 200;
const REQUEST_TIMEOUT_MS = 1000;
const CONTENT_TYPES = [
  'text/javascript',
  'application/javascript',
  'text/ecmascript',
  'application/ecmascript',
];
const DEFAULT_FLAGS = ['--host', '127.0.0.1', '--strictPort'];
const DEV_DETAIL =
  'scripts.dev must start with vite and include --host 127.0.0.1 and --strictPort and no --port';

function usage(message) {
  const error = new Error(message);
  error.usage = true;
  return error;
}

function formatInternal(error) {
  const code = error.code || error.name;
  let message = String(error.message).split('\n')[0];
  const prefix = `${code}: `;
  if (message.startsWith(prefix)) message = message.slice(prefix.length);
  message = message.replace(/\s*'[^']*'/g, '');
  message = message.replace(/[\s,]+$/g, '');
  return `FAIL internal-error: ${code}: ${message}`;
}

function positiveInteger(value, max) {
  if (!/^[1-9][0-9]*$/.test(value)) return null;
  const number = Number(value);
  if (!Number.isSafeInteger(number)) return null;
  if (max !== undefined && number > max) return null;
  return number;
}

function parseArgs(argv) {
  const out = { root: null, port: null, timeoutMs: DEFAULT_TIMEOUT_MS, viteBin: null };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (!arg.startsWith('--')) throw usage(`unknown argument ${arg}`);
    const name = arg.slice(2);
    if (!['root', 'port', 'timeout-ms', 'vite-bin'].includes(name)) throw usage(`unknown flag ${arg}`);
    const value = argv[index + 1];
    if (value === undefined || value.startsWith('--')) throw usage(`flag ${arg} needs a value`);
    index += 1;
    if (name === 'root') out.root = value;
    if (name === 'port') {
      const port = positiveInteger(value, MAX_PORT);
      if (port === null) throw usage('flag --port needs a positive integer port');
      out.port = port;
    }
    if (name === 'timeout-ms') {
      const timeout = positiveInteger(value);
      if (timeout === null) throw usage('flag --timeout-ms needs a positive integer');
      out.timeoutMs = timeout;
    }
    if (name === 'vite-bin') out.viteBin = value;
  }
  return out;
}

function devFlags(root) {
  const full = path.join(root, 'package.json');
  let text;
  try {
    const info = fs.statSync(full);
    if (!info.isFile()) return { fail: 'FAIL dev-script: package.json: not valid JSON' };
    text = fs.readFileSync(full, 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') return { flags: DEFAULT_FLAGS };
    if (error.code === 'EISDIR') return { fail: 'FAIL dev-script: package.json: not valid JSON' };
    throw error;
  }
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    return { fail: 'FAIL dev-script: package.json: not valid JSON' };
  }
  const dev = data?.scripts?.dev;
  if (typeof dev !== 'string') return { fail: 'FAIL dev-script: package.json: no scripts.dev string' };
  const words = dev.split(/\s+/).filter((word) => word.length > 0);
  const flags = words.slice(1);
  let hostOk = false;
  let strict = false;
  let bad = words[0] !== 'vite';
  for (let index = 0; index < flags.length; index += 1) {
    const word = flags[index];
    if (word === '--port' || word.startsWith('--port=') || word.startsWith('--host=')) bad = true;
    if (word === '--host' && flags[index + 1] !== '127.0.0.1') bad = true;
    if (word === '--host' && flags[index + 1] === '127.0.0.1') hostOk = true;
    if (word === '--strictPort') strict = true;
  }
  if (bad || !hostOk || !strict) return { fail: `FAIL dev-script: package.json: ${DEV_DETAIL}` };
  return { flags };
}

function isModule(tag) {
  const type = tag.attributes.find((attr) => attr.name === 'type');
  return type !== undefined && type.value.toLowerCase() === 'module';
}

function srcOf(tag) {
  return tag.attributes.find((attr) => attr.name === 'src')?.value;
}

function entryFrom(root) {
  const full = path.join(root, 'index.html');
  let text;
  try {
    const info = fs.statSync(full);
    if (!info.isFile()) return { fail: 'FAIL entry-source: index.html: missing' };
    text = fs.readFileSync(full, 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') return { fail: 'FAIL entry-source: index.html: missing' };
    throw error;
  }
  const modules = scanTags(text).filter((tag) => tag.name === 'script' && isModule(tag));
  if (modules.length !== 1) {
    return { fail: `FAIL entry-source: index.html: expected exactly one module script, found ${modules.length}` };
  }
  const src = srcOf(modules[0]);
  if (src === undefined) return { fail: 'FAIL entry-source: index.html: module script has no src' };
  if (src.includes('://') || src.startsWith('//')) {
    return { fail: 'FAIL entry-source: index.html: module script src is not a local path' };
  }
  return { entry: src };
}

function childGone(child) {
  if (child.exitCode !== null) return `FAIL start-failed: child exited with ${child.exitCode}`;
  if (child.signalCode !== null) return `FAIL start-failed: child exited with signal ${child.signalCode}`;
  return null;
}

function isNotYet(error) {
  return ['ECONNREFUSED', 'ECONNRESET', 'EPIPE', 'TIMEOUT', 'ECONNABORTED'].includes(error?.code);
}

function mediaType(headers) {
  const raw = headers['content-type'] ?? '';
  const value = Array.isArray(raw) ? raw[0] : raw;
  return value.split(';')[0].trim().toLowerCase();
}

function isFile(target) {
  let isFileStat;
  try {
    isFileStat = fs.statSync(target).isFile();
  } catch {
    isFileStat = false;
  }
  return isFileStat;
}

async function poll(child, output, port, timeoutMs, outer) {
  const deadline = Date.now() + timeoutMs;
  const pageUrl = `http://127.0.0.1:${port}/`;
  while (Date.now() < deadline) {
    if (outer.fired) return { fail: 'FAIL timeout: outer bound' };
    const gone = childGone(child);
    if (gone) return { fail: gone };
    try {
      const response = await httpGet(pageUrl, REQUEST_TIMEOUT_MS);
      const goneAfter = childGone(child);
      if (goneAfter) return { fail: goneAfter };
      if (hasLocalLine(output.text(), port)) return { response };
    } catch (error) {
      if (!isNotYet(error)) throw error;
    }
    const goneLater = childGone(child);
    if (goneLater) return { fail: goneLater };
    await new Promise((resolve) => {
      setTimeout(resolve, POLL_INTERVAL_MS);
    });
  }
  return { fail: `FAIL timeout: no accepted answer from http://127.0.0.1:${port}/ within ${timeoutMs} ms` };
}

async function run() {
  const args = parseArgs(process.argv.slice(2));
  const root = path.resolve(args.root ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'));
  let info;
  try {
    info = fs.statSync(root);
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') throw usage('root is not a directory');
    throw error;
  }
  if (!info.isDirectory()) throw usage('root is not a directory');
  const dev = devFlags(root);
  if (dev.fail) {
    process.stdout.write(`${dev.fail}\n`);
    process.exitCode = 1;
    return;
  }
  const entry = entryFrom(root);
  if (entry.fail) {
    process.stdout.write(`${entry.fail}\n`);
    process.exitCode = 1;
    return;
  }
  const port = args.port ?? (await choosePort());
  if ((await probePort(port)) !== 'free') {
    process.stdout.write(`FAIL start-failed: port ${port} is already in use\n`);
    process.exitCode = 1;
    return;
  }
  let bin;
  if (args.viteBin !== null) {
    const target = path.resolve(args.viteBin);
    if (!isFile(target)) {
      const rel = path.relative(root, target).split(path.sep).join('/');
      process.stdout.write(`FAIL start-failed: vite binary not found: ${rel}\n`);
      process.exitCode = 1;
      return;
    }
    bin = target;
  } else {
    try {
      bin = resolveViteBin(root);
    } catch (error) {
      if (!error.rule) throw error;
      process.stdout.write(`FAIL ${error.rule}: ${error.message}\n`);
      process.exitCode = 1;
      return;
    }
  }
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-dev-home-'));
  const started = startChild({
    bin,
    args: [...dev.flags, '--port', String(port)],
    cwd: root,
    env: childEnvironment(home),
  });
  const outer = { fired: false };
  const outerTimer = setTimeout(() => {
    outer.fired = true;
  }, OUTER_BOUND_MS);
  try {
    const polled = await poll(started.child, started, port, args.timeoutMs, outer);
    if (polled.fail) {
      process.stdout.write(`${polled.fail}\n`);
      process.exitCode = 1;
      return;
    }
    if (polled.response.status !== 200) {
      process.stdout.write(`FAIL bad-status: /: ${polled.response.status}\n`);
      process.exitCode = 1;
      return;
    }
    const tags = scanTags(polled.response.body);
    const present = tags.some(
      (tag) => tag.name === 'script' && isModule(tag) && srcOf(tag) === entry.entry,
    );
    if (!present) {
      process.stdout.write(`FAIL missing-entry: served page has no module script with src ${entry.entry}\n`);
      process.exitCode = 1;
      return;
    }
    const entryUrl = new URL(entry.entry, `http://127.0.0.1:${port}/`).href;
    const script = await httpGet(entryUrl, REQUEST_TIMEOUT_MS);
    if (script.status !== 200) {
      process.stdout.write(`FAIL bad-status: ${entry.entry}: ${script.status}\n`);
      process.exitCode = 1;
      return;
    }
    const type = mediaType(script.headers);
    if (!CONTENT_TYPES.includes(type)) {
      process.stdout.write(`FAIL bad-content-type: ${entry.entry}: ${type}\n`);
      process.exitCode = 1;
      return;
    }
    const hits = scanText(polled.response.body, { builtScript: false });
    if (hits.length > 0) {
      for (const hit of hits) {
        process.stdout.write(`FAIL ${hit.rule}: served page:${hit.line}: ${hit.detail}\n`);
      }
      process.exitCode = 1;
      return;
    }
    if (announcesNetwork(started.text())) {
      process.stdout.write('FAIL network-announced: served output announces a network address\n');
      process.exitCode = 1;
      return;
    }
    process.stdout.write(`PASS dev-server http://127.0.0.1:${port}/\n`);
    process.exitCode = 0;
  } finally {
    clearTimeout(outerTimer);
    await stopChild(started.child);
    fs.rmSync(home, { recursive: true, force: true });
  }
}

async function main() {
  try {
    await run();
  } catch (error) {
    if (error && error.usage) {
      process.stdout.write(`USAGE: ${error.message}\n`);
      process.exitCode = 2;
    } else {
      process.stdout.write(`${formatInternal(error)}\n`);
      process.exitCode = 1;
    }
  }
  process.exit(process.exitCode ?? 0);
}

const invoked = process.argv[1] && fs.realpathSync(process.argv[1]) === fileURLToPath(import.meta.url);
if (invoked) main();
