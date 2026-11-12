import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REQUIRED_DIRECTORIES = [
  'src',
  'src/app',
  'src/state',
  'src/api',
  'src/facts',
  'src/i18n',
  'src/stage',
  'src/brief',
  'src/cards',
  'src/controls',
  'src/seats',
  'src/rooms',
  'src/story',
  'src/pack',
  'src/shell',
  'src/styles',
  'tests',
  'tests/unit',
  'tests/component',
  'tests/e2e',
  'tests/visual',
  'tests/audit',
  'tests/fixtures',
  'eslint-rules',
];
const MARKER_DIRECTORIES = [
  'src/state',
  'src/api',
  'src/facts',
  'src/i18n',
  'src/stage',
  'src/brief',
  'src/cards',
  'src/controls',
  'src/seats',
  'src/rooms',
  'src/story',
  'src/pack',
  'src/shell',
  'src/styles',
  'tests/unit',
  'tests/component',
  'tests/e2e',
  'tests/visual',
  'tests/audit',
  'tests/fixtures',
  'eslint-rules',
];
const CONTENT_DIRECTORIES = [
  'src',
  'src/app',
  'tests',
];
const REQUIRED_FILES = [
  'package.json',
  'package-lock.json',
  'vite.config.ts',
  'tsconfig.json',
  'index.html',
  'src/main.tsx',
];
const FORBIDDEN_CONFIGS = [
  'vite.config.js',
  'vite.config.mjs',
  'vite.config.cjs',
  'vite.config.mts',
  'vite.config.cts',
];
const DEFERRED = [
  ['eslint.config.js', 'S0-T04'],
  ['REFERENCE_NOTES.md', 'S0-T13'],
];
const ENTRY_COUNT = REQUIRED_DIRECTORIES.length + REQUIRED_FILES.length;

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

function parseArgs(argv) {
  let root = null;
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--root') {
      const value = argv[index + 1];
      if (value === undefined || value.startsWith('--')) throw usage('flag --root needs a value');
      root = value;
      index += 1;
      continue;
    }
    throw usage(`unknown flag ${arg}`);
  }
  return root;
}

function defaultRoot() {
  return path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
}

function statRoot(root) {
  let info;
  try {
    info = fs.statSync(root);
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') throw usage('root is not a directory');
    throw error;
  }
  if (!info.isDirectory()) throw usage('root is not a directory');
}

function directoryKind(full) {
  try {
    const info = fs.statSync(full);
    return info.isDirectory() ? 'directory' : 'other';
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') return 'absent';
    throw error;
  }
}

function hasRegularFile(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.isSymbolicLink()) continue;
    const full = path.join(dir, entry.name);
    if (entry.isFile()) return true;
    if (entry.isDirectory() && hasRegularFile(full)) return true;
  }
  return false;
}

function markerIsRegularFile(dir) {
  let info;
  try {
    info = fs.lstatSync(path.join(dir, '.gitkeep'));
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') return false;
    throw error;
  }
  return info.isFile() && info.isSymbolicLink() === false;
}

function fileKind(full) {
  try {
    const info = fs.statSync(full);
    if (!info.isFile()) return 'other';
    return info.size === 0 ? 'empty' : 'file';
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') return 'absent';
    throw error;
  }
}

function existsAny(full) {
  try {
    fs.lstatSync(full);
    return true;
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') return false;
    throw error;
  }
}

function main() {
  try {
    const requested = parseArgs(process.argv.slice(2));
    const root = path.resolve(requested ?? defaultRoot());
    statRoot(root);
    const failures = [];
    for (const dir of REQUIRED_DIRECTORIES) {
      const kind = directoryKind(path.join(root, dir));
      if (kind !== 'directory') {
        failures.push(`FAIL missing-directory: ${dir}: not a directory`);
        continue;
      }
      if (MARKER_DIRECTORIES.includes(dir) && !markerIsRegularFile(path.join(root, dir))) {
        failures.push(`FAIL empty-directory: ${dir}: no regular file named .gitkeep`);
      }
      if (CONTENT_DIRECTORIES.includes(dir) && !hasRegularFile(path.join(root, dir))) {
        failures.push(`FAIL empty-directory: ${dir}: no regular file at any depth`);
      }
    }
    for (const file of REQUIRED_FILES) {
      const kind = fileKind(path.join(root, file));
      if (kind === 'empty') failures.push(`FAIL empty-file: ${file}: empty`);
      else if (kind !== 'file') failures.push(`FAIL missing-file: ${file}: not a file`);
    }
    for (const name of FORBIDDEN_CONFIGS) {
      if (existsAny(path.join(root, name))) {
        failures.push(`FAIL unexpected-config: ${name}: only vite.config.ts may configure Vite`);
      }
    }
    const notes = [];
    for (const [name, owner] of DEFERRED) {
      if (!existsAny(path.join(root, name))) notes.push(`NOTE deferred: ${name} (${owner})`);
    }
    const tail = failures.length === 0 ? 'OK' : `${failures.length} failure(s)`;
    for (const line of failures) process.stdout.write(`${line}\n`);
    for (const line of notes) process.stdout.write(`${line}\n`);
    process.stdout.write(`checked ${ENTRY_COUNT} entries: ${tail}\n`);
    process.exitCode = failures.length === 0 ? 0 : 1;
  } catch (error) {
    if (error && error.usage) {
      process.stdout.write(`USAGE: ${error.message}\n`);
      process.exitCode = 2;
      return;
    }
    process.stdout.write(`${formatInternal(error)}\n`);
    process.exitCode = 1;
  }
}

main();
