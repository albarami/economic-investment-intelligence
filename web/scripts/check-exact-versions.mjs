import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const EXACT_VERSION = /^\d+\.\d+\.\d+$/;
const DEPENDENCY_SECTIONS = [
  'dependencies',
  'devDependencies',
  'optionalDependencies',
  'peerDependencies',
];
const LOCKED_SECTIONS = [
  'dependencies',
  'devDependencies',
  'optionalDependencies',
];
const REQUIRED_PACKAGES = [
  ['dependencies', 'react'],
  ['dependencies', 'react-dom'],
  ['devDependencies', 'vite'],
  ['devDependencies', 'typescript'],
  ['devDependencies', '@vitejs/plugin-react'],
];
const LIFECYCLE_KEYS = [
  'preinstall',
  'install',
  'postinstall',
  'prepare',
  'prepublish',
];
const ACCEPTED_LOCK_VERSIONS = [2, 3];
const JUDGED_OBJECTS = [
  'dependencies',
  'devDependencies',
  'optionalDependencies',
  'peerDependencies',
  'overrides',
  'scripts',
];

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
      if (value === undefined || value.startsWith('--'))
        throw usage('flag --root needs a value');
      root = value;
      index += 1;
      continue;
    }
    throw usage(`unknown flag ${arg}`);
  }
  return root;
}

function statRoot(root) {
  let info;
  try {
    info = fs.statSync(root);
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR')
      throw usage('root is not a directory');
    throw error;
  }
  if (!info.isDirectory()) throw usage('root is not a directory');
}

function isObject(value) {
  return (
    value !== null &&
    typeof value === 'object' &&
    Array.isArray(value) === false
  );
}

function readPackage(root, failures) {
  const full = path.join(root, 'package.json');
  let text;
  try {
    const info = fs.statSync(full);
    if (!info.isFile()) {
      failures.push('FAIL package-json: package.json: missing');
      return null;
    }
    text = fs.readFileSync(full, 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') {
      failures.push('FAIL package-json: package.json: missing');
      return null;
    }
    throw error;
  }
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    failures.push('FAIL package-json: package.json: not valid JSON');
    return null;
  }
  if (!isObject(data)) {
    failures.push(
      'FAIL package-json: package.json: top level is not an object',
    );
    return null;
  }
  for (const key of JUDGED_OBJECTS) {
    if (data[key] !== undefined && !isObject(data[key])) {
      const detail =
        key === 'overrides'
          ? 'overrides is not an object'
          : `${key} is not an object`;
      failures.push(`FAIL package-json: package.json: ${detail}`);
      return null;
    }
  }
  return data;
}

function sectionOf(pkg, name) {
  return pkg[name] === undefined ? {} : pkg[name];
}

function walkOverrides(value, prefix, leaves) {
  if (isObject(value)) {
    for (const [key, child] of Object.entries(value)) {
      const next = prefix ? `${prefix}.${key}` : key;
      walkOverrides(child, next, leaves);
    }
    return;
  }
  leaves.push({ name: prefix, value });
}

function canonical(section) {
  const keys = Object.keys(section).sort();
  const ordered = {};
  for (const key of keys) ordered[key] = section[key];
  return JSON.stringify(ordered);
}

function checkLock(root, pkg, failures) {
  const full = path.join(root, 'package-lock.json');
  let text;
  try {
    const info = fs.statSync(full);
    if (!info.isFile()) {
      failures.push('FAIL missing-lock: package-lock.json: missing');
      return;
    }
    text = fs.readFileSync(full, 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') {
      failures.push('FAIL missing-lock: package-lock.json: missing');
      return;
    }
    throw error;
  }
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    failures.push('FAIL lock-parse: package-lock.json: not valid JSON');
    return;
  }
  if (!isObject(data) || !isObject(data.packages)) {
    failures.push('FAIL lock-parse: package-lock.json: no packages object');
    return;
  }
  if (!ACCEPTED_LOCK_VERSIONS.includes(data.lockfileVersion)) {
    failures.push(
      'FAIL lock-version: package-lock.json: lockfileVersion is not 2 or 3',
    );
    return;
  }
  const rootEntry = data.packages[''];
  if (!isObject(rootEntry)) {
    failures.push(
      'FAIL lock-root-mismatch: package-lock.json: root entry absent',
    );
    return;
  }
  for (const section of [...DEPENDENCY_SECTIONS]) {
    const left = sectionOf(pkg, section);
    const right = rootEntry[section] === undefined ? {} : rootEntry[section];
    if (!isObject(right) || canonical(left) !== canonical(right)) {
      failures.push(
        `FAIL lock-root-mismatch: package-lock.json: ${section} differs`,
      );
    }
  }
  for (const section of LOCKED_SECTIONS) {
    for (const [name, spec] of Object.entries(sectionOf(pkg, section))) {
      const entry = data.packages[`node_modules/${name}`];
      if (!isObject(entry)) {
        failures.push(
          `FAIL lock-version-mismatch: package-lock.json: ${name} absent`,
        );
        continue;
      }
      if (entry.version !== spec) {
        failures.push(
          `FAIL lock-version-mismatch: package-lock.json: ${name} version ${entry.version}`,
        );
      }
    }
  }
}

function main() {
  try {
    const requested = parseArgs(process.argv.slice(2));
    const root = path.resolve(
      requested ??
        path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'),
    );
    statRoot(root);
    const failures = [];
    const pkg = readPackage(root, failures);
    let count = 0;
    if (pkg) {
      for (const section of DEPENDENCY_SECTIONS) {
        for (const [name, spec] of Object.entries(sectionOf(pkg, section))) {
          count += 1;
          if (typeof spec !== 'string' || EXACT_VERSION.test(spec) === false) {
            failures.push(
              `FAIL not-exact: ${section}.${name}: ${JSON.stringify(spec)}: not an exact version`,
            );
          }
        }
      }
      const leaves = [];
      if (pkg.overrides) walkOverrides(pkg.overrides, '', leaves);
      for (const leaf of leaves) {
        count += 1;
        if (
          typeof leaf.value !== 'string' ||
          EXACT_VERSION.test(leaf.value) === false
        ) {
          failures.push(
            `FAIL not-exact: overrides.${leaf.name}: ${JSON.stringify(leaf.value)}: not an exact version`,
          );
        }
      }
      for (const [section, name] of REQUIRED_PACKAGES) {
        if (!Object.hasOwn(sectionOf(pkg, section), name)) {
          failures.push(`FAIL required-package: ${section}.${name}: absent`);
        }
      }
      const engines = pkg.engines;
      if (
        !isObject(engines) ||
        typeof engines.node !== 'string' ||
        engines.node.length === 0
      ) {
        failures.push('FAIL engines-missing: engines.node: missing or empty');
      }
      const scripts = sectionOf(pkg, 'scripts');
      for (const key of LIFECYCLE_KEYS) {
        if (Object.hasOwn(scripts, key)) {
          failures.push(
            `FAIL lifecycle-script: scripts.${key}: runs when the package is installed`,
          );
        }
      }
      checkLock(root, pkg, failures);
      process.stdout.write(
        'NOTE scripts are not judged beyond the five lifecycle keys\n',
      );
    }
    for (const line of failures) process.stdout.write(`${line}\n`);
    const tail = failures.length === 0 ? 'OK' : `${failures.length} failure(s)`;
    process.stdout.write(`checked ${count} specifiers: ${tail}\n`);
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
