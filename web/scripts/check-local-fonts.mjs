/*
 * Proves the font half of DES-24 and FE-97 on the built output: every
 * @font-face and font import in dist resolves to a file the application
 * serves, never a third-party host or an embedded data URL, both typefaces
 * are delivered, and the OFL licence texts sit beside the fonts with their
 * pinned SHA-256 (the pins of host-scan-rules.mjs, reused).
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { acceptedLicence } from './host-scan-rules.mjs';

const FONT_LICENCE_FILES = [
  'dist/licences/ibm-plex-sans.txt',
  'dist/licences/ibm-plex-sans-arabic.txt',
];
const REQUIRED_FAMILIES = ['IBM Plex Sans', 'IBM Plex Sans Arabic'];
const FACE_PATTERN = /@font-face\s*\{([^}]*)\}/g;
const URL_PATTERN = /url\(\s*([^)]*?)\s*\)/g;
const IMPORT_PATTERN =
  /@import\s+(?:url\(\s*([^)]*?)\s*\)|'([^']*)'|"([^"]*)")[^;]*;/g;

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
  let dist = false;
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--dist') {
      dist = true;
      continue;
    }
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
  if (!dist) throw usage('the font check needs --dist');
  return { root, dist };
}

function stripQuotes(value) {
  const trimmed = value.trim();
  if (
    (trimmed.startsWith("'") && trimmed.endsWith("'")) ||
    (trimmed.startsWith('"') && trimmed.endsWith('"'))
  ) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

function lineAt(text, index) {
  let line = 1;
  for (let cursor = 0; cursor < index; cursor += 1) {
    if (text[cursor] === '\n') line += 1;
  }
  return line;
}

function urlKind(url) {
  if (url.startsWith('//')) return 'external';
  if (/^[A-Za-z][A-Za-z0-9+.-]*:/.test(url))
    return url.startsWith('data:') ? 'embedded' : 'external';
  return 'local';
}

function urlTarget(url) {
  let target = url;
  const hash = target.indexOf('#');
  if (hash !== -1) target = target.slice(0, hash);
  const query = target.indexOf('?');
  if (query !== -1) target = target.slice(0, query);
  return target;
}

function isRegularFile(full) {
  let info;
  try {
    info = fs.statSync(full);
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') return false;
    throw error;
  }
  return info.isFile();
}

function resolvesToDistFile(root, cssFull, url) {
  const target = urlTarget(url);
  const base = target.startsWith('/')
    ? path.join(root, 'dist')
    : path.dirname(cssFull);
  return isRegularFile(path.join(base, target));
}

function scanCss(root, full, rel, text, failures) {
  const families = new Set();
  let face = FACE_PATTERN.exec(text);
  while (face) {
    const block = face[1];
    const familyMatch = block.match(/font-family\s*:\s*([^;}]+)/i);
    const family = familyMatch ? stripQuotes(familyMatch[1]) : '';
    if (family) families.add(family.toLowerCase());
    const urls = [...block.matchAll(URL_PATTERN)];
    if (urls.length === 0) {
      failures.push(
        `FAIL font-face-no-file: ${rel}:${lineAt(text, face.index)}: ${family}`,
      );
    }
    for (const match of urls) {
      const url = stripQuotes(match[1]);
      const line = lineAt(text, face.index + match.index);
      const kind = urlKind(url);
      if (kind === 'external') {
        failures.push(`FAIL font-url-external: ${rel}:${line}: ${url}`);
        continue;
      }
      if (kind === 'embedded') {
        failures.push(`FAIL font-url-embedded: ${rel}:${line}: ${url}`);
        continue;
      }
      if (!resolvesToDistFile(root, full, url)) {
        failures.push(`FAIL font-file-missing: ${rel}:${line}: ${url}`);
      }
    }
    face = FACE_PATTERN.exec(text);
  }
  for (const match of text.matchAll(IMPORT_PATTERN)) {
    const url = stripQuotes(match[1] ?? match[2] ?? match[3] ?? '');
    const line = lineAt(text, match.index);
    if (urlKind(url) !== 'local') {
      failures.push(`FAIL font-import-external: ${rel}:${line}: ${url}`);
      continue;
    }
    if (!resolvesToDistFile(root, full, url)) {
      failures.push(`FAIL font-import-missing: ${rel}:${line}: ${url}`);
    }
  }
  return families;
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

function scanDist(root, failures) {
  const dist = path.join(root, 'dist');
  let info;
  try {
    info = fs.statSync(dist);
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') {
      failures.push('FAIL dist-missing: dist: absent');
      return;
    }
    throw error;
  }
  if (!info.isDirectory()) {
    failures.push('FAIL dist-missing: dist: not a directory');
    return;
  }
  const families = new Set();
  let files = 0;
  walk(dist, (item) => {
    if (item.error) {
      failures.push(
        `FAIL unreadable-file: ${path
          .relative(root, item.full)
          .split(path.sep)
          .join('/')}: ${item.error.code || item.error.name}`,
      );
      return;
    }
    if (!item.full.endsWith('.css')) return;
    files += 1;
    const rel = path.relative(root, item.full).split(path.sep).join('/');
    let text;
    try {
      text = fs.readFileSync(item.full, 'utf8');
    } catch (error) {
      failures.push(
        `FAIL unreadable-file: ${rel}: ${error.code || error.name}`,
      );
      return;
    }
    for (const family of scanCss(root, item.full, rel, text, failures)) {
      families.add(family);
    }
  });
  if (families.size === 0) {
    failures.push('FAIL font-face-absent: dist: no @font-face rule');
  } else {
    for (const family of REQUIRED_FAMILIES) {
      if (!families.has(family.toLowerCase())) {
        failures.push(`FAIL font-family-missing: dist: ${family}`);
      }
    }
  }
  for (const rel of FONT_LICENCE_FILES) {
    const full = path.join(root, rel);
    if (!isRegularFile(full)) {
      failures.push(`FAIL font-licence-missing: ${rel}`);
      continue;
    }
    if (!acceptedLicence(rel, fs.readFileSync(full))) {
      failures.push(`FAIL font-licence-changed: ${rel}`);
    }
  }
  return files;
}

function main() {
  try {
    const args = parseArgs(process.argv.slice(2));
    const root = path.resolve(
      args.root ??
        path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'),
    );
    let info;
    try {
      info = fs.statSync(root);
    } catch (error) {
      if (error.code === 'ENOENT' || error.code === 'ENOTDIR')
        throw usage('root is not a directory');
      throw error;
    }
    if (!info.isDirectory()) throw usage('root is not a directory');
    const failures = [];
    const files = scanDist(root, failures) ?? 0;
    const tail = failures.length === 0 ? 'OK' : `${failures.length} failure(s)`;
    for (const line of failures) process.stdout.write(`${line}\n`);
    process.stdout.write(`checked ${files} css files: ${tail}\n`);
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
