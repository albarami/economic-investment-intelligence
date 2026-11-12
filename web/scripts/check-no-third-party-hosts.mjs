import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { scanTags, scanText } from './host-scan-rules.mjs';

const BINARY_EXTENSIONS = [
  '.woff',
  '.woff2',
  '.ttf',
  '.otf',
  '.eot',
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.webp',
  '.avif',
  '.ico',
  '.bmp',
  '.mp3',
  '.mp4',
  '.webm',
  '.ogg',
  '.wav',
  '.pdf',
  '.wasm',
  '.zip',
  '.gz',
];
const WALK_DIRECTORIES = ['src', 'public'];
const ASSET_ATTRIBUTES = ['src', 'href', 'srcset'];
const BUILT_SCRIPT_EXTENSIONS = ['.js', '.mjs'];

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
  return { root, dist };
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

function relativePath(root, full) {
  return path.relative(root, full).split(path.sep).join('/');
}

function extensionOf(name) {
  const base = path.basename(name);
  const dot = base.lastIndexOf('.');
  if (dot <= 0) return '';
  return base.slice(dot).toLowerCase();
}

function allowedAsset(value) {
  if (value.startsWith('data:') || value.startsWith('#')) return true;
  return value.startsWith('/') && !value.startsWith('//');
}

function assetHits(html, rel) {
  const hits = [];
  for (const tag of scanTags(html)) {
    for (const attr of tag.attributes) {
      if (!ASSET_ATTRIBUTES.includes(attr.name) || attr.value === '') continue;
      const candidates =
        attr.name === 'srcset' ? attr.value.split(',') : [attr.value];
      for (const candidate of candidates) {
        const url = candidate.trim().split(/\s+/)[0] ?? '';
        if (url && !allowedAsset(url)) {
          hits.push(`FAIL asset-url-shape: ${rel}:${attr.line}: ${url}`);
        }
      }
    }
  }
  return hits;
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

function scanFile(root, full, failures, built) {
  const rel = relativePath(root, full);
  const ext = extensionOf(full);
  if (BINARY_EXTENSIONS.includes(ext)) return;
  let text;
  try {
    text = fs.readFileSync(full, 'utf8');
  } catch (error) {
    failures.push(`FAIL unreadable-file: ${rel}: ${error.code || error.name}`);
    return;
  }
  const builtScript = built && BUILT_SCRIPT_EXTENSIONS.includes(ext);
  for (const hit of scanText(text, { builtScript })) {
    failures.push(`FAIL ${hit.rule}: ${rel}:${hit.line}: ${hit.detail}`);
  }
  if (built && rel === 'dist/index.html') {
    failures.push(...assetHits(text, rel));
  }
}

function main() {
  try {
    const args = parseArgs(process.argv.slice(2));
    const root = path.resolve(
      args.root ??
        path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'),
    );
    statRoot(root);
    const failures = [];
    let files = 0;
    const addFile = (full, built) => {
      files += 1;
      scanFile(root, full, failures, built);
    };
    const indexHtml = path.join(root, 'index.html');
    let indexKind;
    try {
      fs.lstatSync(indexHtml);
      indexKind = 'present';
    } catch (error) {
      if (error.code === 'ENOENT' || error.code === 'ENOTDIR')
        indexKind = 'absent';
      else throw error;
    }
    if (indexKind === 'absent')
      failures.push('FAIL missing-file: index.html: absent');
    else addFile(indexHtml, false);
    const viteConfig = path.join(root, 'vite.config.ts');
    if (fs.existsSync(viteConfig)) addFile(viteConfig, false);
    for (const dir of WALK_DIRECTORIES) {
      const full = path.join(root, dir);
      if (!fs.existsSync(full) || !fs.statSync(full).isDirectory()) continue;
      walk(full, (item) => {
        files += 1;
        if (item.error) {
          failures.push(
            `FAIL unreadable-file: ${relativePath(root, item.full)}: ${item.error.code || item.error.name}`,
          );
          return;
        }
        scanFile(root, item.full, failures, false);
      });
    }
    if (args.dist) {
      const dist = path.join(root, 'dist');
      let distInfo;
      try {
        distInfo = fs.statSync(dist);
      } catch (error) {
        if (error.code === 'ENOENT' || error.code === 'ENOTDIR')
          distInfo = null;
        else throw error;
      }
      if (!distInfo || !distInfo.isDirectory())
        failures.push('FAIL dist-missing: dist: absent');
      else {
        const page = path.join(dist, 'index.html');
        if (!fs.existsSync(page))
          failures.push('FAIL missing-file: dist/index.html: absent');
        walk(dist, (item) => {
          files += 1;
          if (item.error) {
            failures.push(
              `FAIL unreadable-file: ${relativePath(root, item.full)}: ${item.error.code || item.error.name}`,
            );
            return;
          }
          scanFile(root, item.full, failures, true);
        });
      }
    }
    const tail = failures.length === 0 ? 'OK' : `${failures.length} failure(s)`;
    for (const line of failures) process.stdout.write(`${line}\n`);
    process.stdout.write(`checked ${files} files: ${tail}\n`);
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
