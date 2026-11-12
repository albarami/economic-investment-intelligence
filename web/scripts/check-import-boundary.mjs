import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { collectReferences } from './import-tokenizer.mjs';

const SCRIPT_EXTENSIONS = [
  '.ts',
  '.tsx',
  '.mts',
  '.cts',
  '.js',
  '.jsx',
  '.mjs',
  '.cjs',
];
const STYLE_EXTENSIONS = [
  '.css',
  '.scss',
  '.sass',
  '.less',
  '.styl',
  '.pcss',
];
const SOURCE_DIRECTORIES = [
  'src',
  'tests',
  'eslint-rules',
];
const EXTRA_FILES = [
  'vite.config.ts',
];
const FORBIDDEN_PACKAGES = [
  'custodian',
  'core',
  'product',
  'gateway',
  'contracts',
  'evals',
  'infra',
  'data',
  'eii_core',
  'eii_custodian',
  'eii_product',
  'eii_gateway',
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
      if (value === undefined || value.startsWith('--')) throw usage('flag --root needs a value');
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
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') throw usage('root is not a directory');
    throw error;
  }
  if (!info.isDirectory()) throw usage('root is not a directory');
}

function relativePath(root, full) {
  return path.relative(root, full).split(path.sep).join('/');
}

function extensionOf(name) {
  const base = path.basename(name);
  const dot = base.lastIndexOf('.');
  if (dot <= 0) return '';
  return base.slice(dot).toLowerCase();
}

function isInside(root, target) {
  const base = fs.realpathSync(root);
  const rel = path.relative(base, path.resolve(target));
  return rel === '' || (rel !== '..' && !rel.startsWith(`..${path.sep}`) && !path.isAbsolute(rel));
}

function locate(fromDir, spec) {
  const resolved = path.resolve(fromDir, spec);
  if (fs.existsSync(resolved)) {
    try {
      return fs.realpathSync(resolved);
    } catch {
      return path.normalize(resolved);
    }
  }
  return path.normalize(resolved);
}

function hasScheme(spec) {
  return /^[A-Za-z][A-Za-z0-9+.-]*:/.test(spec);
}

function judge(spec, fromFile, root, style) {
  if (spec.includes('\\') || /^[A-Za-z]:[\\/]/.test(spec)) return 'absolute-path';
  if (spec.startsWith('//') || spec.startsWith('/@fs/') || spec.startsWith('file:')) return 'absolute-path';
  if (spec.startsWith('/')) {
    const resolved = locate(root, spec.slice(1));
    return isInside(root, resolved) ? null : 'absolute-path';
  }
  const bare = !spec.startsWith('.') && !spec.startsWith('#') && !hasScheme(spec);
  if (spec.startsWith('.') || (style && bare)) {
    const resolved = locate(path.dirname(fromFile), spec);
    return isInside(root, resolved) ? null : 'outside-web';
  }
  const first = spec.split('/')[0];
  if (FORBIDDEN_PACKAGES.includes(first)) return 'forbidden-package';
  return null;
}

function scanStyle(text) {
  const refs = [];
  let index = 0;
  let line = 1;
  const length = text.length;
  const skipSpace = () => {
    while (index < length && /\s/.test(text[index])) {
      if (text[index] === '\n') line += 1;
      index += 1;
    }
  };
  const readQuoted = () => {
    const quote = text[index];
    index += 1;
    let value = '';
    while (index < length && text[index] !== quote) {
      if (text[index] === '\n') line += 1;
      value += text[index];
      index += 1;
    }
    if (index < length && text[index] === quote) index += 1;
    return value;
  };
  const readUrl = () => {
    const startLine = line;
    index += 4;
    skipSpace();
    let value = '';
    if (text[index] === "'" || text[index] === '"') value = readQuoted();
    else {
      while (index < length && text[index] !== ')') {
        if (text[index] === '\n') line += 1;
        value += text[index];
        index += 1;
      }
    }
    skipSpace();
    if (text[index] === ')') index += 1;
    return { value: value.trim(), line: startLine };
  };
  while (index < length) {
    if (text[index] === '\n') {
      line += 1;
      index += 1;
      continue;
    }
    const importWord = `@${'imp'}${'ort'}`;
    if (text.startsWith(importWord, index) && !/[A-Za-z0-9_-]/.test(text[index + importWord.length] ?? '')) {
      const startLine = line;
      index += importWord.length;
      skipSpace();
      if (text.startsWith('url(', index)) {
        const arg = readUrl();
        if (!arg.value.startsWith('data:')) refs.push({ specifier: arg.value, line: startLine });
        continue;
      }
      if (text[index] === "'" || text[index] === '"') {
        refs.push({ specifier: readQuoted().trim(), line: startLine });
      }
      continue;
    }
    if (text.startsWith('url(', index)) {
      const arg = readUrl();
      if (!arg.value.startsWith('data:')) refs.push({ specifier: arg.value, line: arg.line });
      continue;
    }
    index += 1;
  }
  return refs;
}

function walk(dir, visit) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isSymbolicLink()) {
      let info;
      try {
        info = fs.statSync(full);
      } catch (error) {
        visit({ full, error });
        continue;
      }
      if (info.isDirectory()) continue;
      visit({ full });
      continue;
    }
    if (entry.isDirectory()) {
      walk(full, visit);
      continue;
    }
    if (entry.isFile()) visit({ full });
  }
}

function isObject(value) {
  return value !== null && typeof value === 'object' && Array.isArray(value) === false;
}

function tsconfigTypeError(config) {
  if (!isObject(config)) return 'top level is not an object';
  for (const key of ['include', 'exclude', 'files']) {
    if (config[key] !== undefined && !Array.isArray(config[key])) return `${key} is not an array`;
  }
  if (config.extends !== undefined && typeof config.extends !== 'string' && !Array.isArray(config.extends)) {
    return 'extends is not a string or an array';
  }
  if (config.references !== undefined && !Array.isArray(config.references)) return 'references is not an array';
  const options = config.compilerOptions;
  if (options !== undefined && !isObject(options)) return 'compilerOptions is not an object';
  if (options?.paths !== undefined && !isObject(options.paths)) return 'paths is not an object';
  if (options?.baseUrl !== undefined && typeof options.baseUrl !== 'string') return 'baseUrl is not a string';
  if (options?.rootDirs !== undefined && !Array.isArray(options.rootDirs)) return 'rootDirs is not an array';
  if (options?.typeRoots !== undefined && !Array.isArray(options.typeRoots)) return 'typeRoots is not an array';
  return null;
}

function entryOutside(root, entry) {
  if (typeof entry !== 'string') return false;
  const resolved = path.isAbsolute(entry) || /^[A-Za-z]:[\\/]/.test(entry)
    ? path.resolve(entry)
    : locate(root, entry);
  return !isInside(root, resolved);
}

function judgeTsconfig(root, config, failures) {
  const lists = [
    ['include', config.include],
    ['exclude', config.exclude],
    ['files', config.files],
  ];
  for (const [key, value] of lists) {
    for (const entry of value ?? []) {
      if (entryOutside(root, entry)) failures.push(`FAIL tsconfig-outside: tsconfig.json: ${key}: ${entry}`);
    }
  }
  const extended = config.extends === undefined ? [] : Array.isArray(config.extends) ? config.extends : [config.extends];
  for (const entry of extended) {
    if (entryOutside(root, entry)) failures.push(`FAIL tsconfig-outside: tsconfig.json: extends: ${entry}`);
  }
  for (const item of config.references ?? []) {
    if (item && typeof item.path === 'string' && entryOutside(root, item.path)) {
      failures.push(`FAIL tsconfig-outside: tsconfig.json: references.path: ${item.path}`);
    }
  }
  const options = config.compilerOptions ?? {};
  for (const entry of options.rootDirs ?? []) {
    if (entryOutside(root, entry)) failures.push(`FAIL tsconfig-outside: tsconfig.json: rootDirs: ${entry}`);
  }
  for (const entry of options.typeRoots ?? []) {
    if (entryOutside(root, entry)) failures.push(`FAIL tsconfig-outside: tsconfig.json: typeRoots: ${entry}`);
  }
  if (typeof options.baseUrl === 'string' && entryOutside(root, options.baseUrl)) {
    failures.push(`FAIL tsconfig-outside: tsconfig.json: baseUrl: ${options.baseUrl}`);
  }
  for (const targets of Object.values(options.paths ?? {})) {
    for (const entry of targets ?? []) {
      if (entryOutside(root, entry)) failures.push(`FAIL tsconfig-outside: tsconfig.json: paths: ${entry}`);
    }
  }
}

function readSource(root, full, failures) {
  try {
    return fs.readFileSync(full, 'utf8');
  } catch (error) {
    failures.push(`FAIL unreadable-file: ${relativePath(root, full)}: ${error.code || error.name}`);
    return null;
  }
}

function main() {
  try {
    const requested = parseArgs(process.argv.slice(2));
    const root = path.resolve(requested ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'));
    statRoot(root);
    const failures = [];
    if (!fs.existsSync(path.join(root, 'src'))) {
      failures.push('FAIL missing-source: src: absent');
      process.stdout.write(`${failures[0]}\n`);
      process.stdout.write('checked 0 references in 0 files: 1 failure(s)\n');
      process.exitCode = 1;
      return;
    }
    let references = 0;
    let files = 0;
    const consider = (full) => {
      const ext = extensionOf(full);
      const style = STYLE_EXTENSIONS.includes(ext);
      const script = SCRIPT_EXTENSIONS.includes(ext);
      if (!style && !script) return;
      const text = readSource(root, full, failures);
      if (text === null) return;
      files += 1;
      const rel = relativePath(root, full);
      if (style) {
        for (const item of scanStyle(text)) {
          references += 1;
          const rule = judge(item.specifier, full, root, true);
          if (rule) failures.push(`FAIL ${rule}: ${rel}:${item.line}: ${item.specifier}`);
        }
        return;
      }
      const found = collectReferences(text);
      for (const item of found.references) {
        references += 1;
        const rule = judge(item.specifier, full, root, false);
        if (rule) failures.push(`FAIL ${rule}: ${rel}:${item.line}: ${item.specifier}`);
      }
      for (const item of found.nonLiteral) {
        failures.push(`FAIL non-literal-import: ${rel}:${item.line}: ${item.form}`);
      }
    };
    for (const dir of SOURCE_DIRECTORIES) {
      const full = path.join(root, dir);
      if (fs.existsSync(full) && fs.statSync(full).isDirectory()) walk(full, (item) => {
        if (item.error) {
          failures.push(`FAIL unreadable-file: ${relativePath(root, item.full)}: ${item.error.code || item.error.name}`);
          return;
        }
        consider(item.full);
      });
    }
    for (const name of EXTRA_FILES) {
      const full = path.join(root, name);
      if (fs.existsSync(full) && fs.statSync(full).isFile()) consider(full);
    }
    const configPath = path.join(root, 'tsconfig.json');
    let configText = null;
    try {
      const info = fs.statSync(configPath);
      if (!info.isFile()) failures.push('FAIL tsconfig-json: tsconfig.json: missing');
      else configText = fs.readFileSync(configPath, 'utf8');
    } catch (error) {
      if (error.code === 'ENOENT' || error.code === 'ENOTDIR') {
        failures.push('FAIL tsconfig-json: tsconfig.json: missing');
      } else throw error;
    }
    if (configText !== null) {
      let config;
      try {
        config = JSON.parse(configText);
      } catch {
        config = undefined;
        failures.push('FAIL tsconfig-json: tsconfig.json: not valid JSON');
      }
      if (config !== undefined) {
        const problem = tsconfigTypeError(config);
        if (problem) failures.push(`FAIL tsconfig-json: tsconfig.json: ${problem}`);
        else judgeTsconfig(root, config, failures);
      }
    }
    const tail = failures.length === 0 ? 'OK' : `${failures.length} failure(s)`;
    for (const line of failures) process.stdout.write(`${line}\n`);
    process.stdout.write(`checked ${references} references in ${files} files: ${tail}\n`);
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
