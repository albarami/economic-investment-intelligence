/*
 * Proves the font half of DES-24 and FE-97 on the built output: every
 * @font-face and font import in dist resolves to a file the application
 * serves, never a third-party host or an embedded data URL, both typefaces
 * are delivered, and the OFL licence texts sit beside the fonts with their
 * pinned SHA-256 (the pins of host-scan-rules.mjs, reused). Built HTML is
 * scanned with the same resolver: font preload links, stylesheet links,
 * inline styles and style attributes, and every reference resolves by
 * browser URL semantics with lexical and real-path containment inside dist,
 * so neither traversal nor an escaping symlink can satisfy the check.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { acceptedLicence, scanTags } from './host-scan-rules.mjs';
import {
  formatInternal,
  lineAt,
  relativePath,
  usage,
  walk,
} from './scan-utils.mjs';
import { parseFontCss } from './font-css-tokens.mjs';

const FONT_LICENCE_FILES = [
  'dist/licences/ibm-plex-sans.txt',
  'dist/licences/ibm-plex-sans-arabic.txt',
];
const REQUIRED_FAMILIES = ['IBM Plex Sans', 'IBM Plex Sans Arabic'];

// One refusal code per reference kind and refusal case; the url kind keeps
// the round 1 codes, including font-file-missing for an absent target.
const TRAVERSAL_CODE = {
  url: 'font-url-traversal',
  import: 'font-import-traversal',
  preload: 'font-preload-traversal',
  stylesheet: 'font-stylesheet-traversal',
};
const ESCAPE_CODE = {
  url: 'font-url-symlink-escape',
  import: 'font-import-symlink-escape',
  preload: 'font-preload-symlink-escape',
  stylesheet: 'font-stylesheet-symlink-escape',
};
const MISSING_CODE = {
  url: 'font-file-missing',
  import: 'font-import-missing',
  preload: 'font-preload-missing',
  stylesheet: 'font-stylesheet-missing',
};
const EXTERNAL_CODE = {
  url: 'font-url-external',
  import: 'font-import-external',
  preload: 'font-preload-external',
  stylesheet: 'font-stylesheet-external',
};
const EMBEDDED_CODE = {
  url: 'font-url-embedded',
  import: 'font-import-external',
  preload: 'font-preload-embedded',
  stylesheet: 'font-stylesheet-embedded',
};

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

function urlKind(url) {
  if (url.startsWith('//')) return 'external';
  if (/^[A-Za-z][A-Za-z0-9+.-]*:/.test(url))
    return url.startsWith('data:') ? 'embedded' : 'external';
  return 'local';
}

function cleanUrl(raw) {
  // Browsers strip tab, newline, carriage return and null anywhere, trim
  // leading and trailing whitespace, and read a backslash as a slash.
  let url = raw.replace(/[\t\n\r\0]/g, '');
  url = url.trim();
  url = url.replace(/\\/g, '/');
  const hash = url.indexOf('#');
  if (hash !== -1) url = url.slice(0, hash);
  const query = url.indexOf('?');
  if (query !== -1) url = url.slice(0, query);
  return url;
}

function decodeSegment(segment) {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment.replace(/%([0-9A-Fa-f]{2})/g, (_, hex) =>
      String.fromCharCode(Number.parseInt(hex, 16)),
    );
  }
}

function dotForm(segment) {
  // The URL spec reads these encoded spellings as dot segments.
  const lower = segment.toLowerCase();
  if (
    lower === '..' ||
    lower === '.%2e' ||
    lower === '%2e.' ||
    lower === '%2e%2e'
  ) {
    return '..';
  }
  if (lower === '.' || lower === '%2e') return '.';
  return null;
}

function resolveServedTarget(dist, distReal, servedRel, rawUrl) {
  const target = cleanUrl(rawUrl);
  const baseDir = servedRel.includes('/')
    ? servedRel.slice(0, servedRel.lastIndexOf('/'))
    : '';
  const stack =
    target.startsWith('/') || baseDir === '' ? [] : baseDir.split('/');
  for (const rawSegment of target.split('/')) {
    const form = dotForm(rawSegment);
    if (form === '.') continue;
    if (form === '..') {
      if (stack.length === 0) return { refusal: 'traversal' };
      stack.pop();
      continue;
    }
    if (rawSegment === '') continue;
    const segment = decodeSegment(rawSegment);
    if (segment.includes('/') || segment.includes('\0'))
      return { refusal: 'traversal' };
    stack.push(segment);
  }
  const full = path.join(dist, ...stack);
  const lexical = path.resolve(full);
  if (lexical !== dist && !lexical.startsWith(`${dist}${path.sep}`))
    return { refusal: 'traversal' };
  let real;
  try {
    real = fs.realpathSync(full);
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR')
      return { refusal: 'missing' };
    throw error;
  }
  if (real !== distReal && !real.startsWith(`${distReal}${path.sep}`))
    return { refusal: 'symlink-escape' };
  if (!fs.statSync(real).isFile()) return { refusal: 'missing' };
  return { full: real };
}

function checkReference(context, kind, url, line, cssTargets) {
  const text = `${context.rel}:${line}: ${url}`;
  const kindOfUrl = urlKind(url);
  if (kindOfUrl === 'external') {
    context.failures.push(`FAIL ${EXTERNAL_CODE[kind]}: ${text}`);
    return;
  }
  if (kindOfUrl === 'embedded') {
    context.failures.push(`FAIL ${EMBEDDED_CODE[kind]}: ${text}`);
    return;
  }
  const resolved = resolveServedTarget(
    context.dist,
    context.distReal,
    context.servedRel,
    url,
  );
  if (resolved.refusal) {
    const code =
      resolved.refusal === 'traversal'
        ? TRAVERSAL_CODE[kind]
        : resolved.refusal === 'symlink-escape'
          ? ESCAPE_CODE[kind]
          : MISSING_CODE[kind];
    context.failures.push(`FAIL ${code}: ${text}`);
    return;
  }
  if (kind === 'url') return;
  cssTargets.add(resolved.full);
}

function scanFontRules(context, text, locate, families, cssTargets) {
  const parsed = parseFontCss(text);
  for (const face of parsed.faces) {
    if (face.family && families) families.add(face.family.toLowerCase());
    if (face.urls.length === 0) {
      context.failures.push(
        `FAIL font-face-no-file: ${context.rel}:${locate(face.index)}: ${face.family}`,
      );
      continue;
    }
    for (const ref of face.urls) {
      checkReference(context, 'url', ref.value, locate(ref.index), cssTargets);
    }
  }
  for (const ref of parsed.imports) {
    checkReference(context, 'import', ref.value, locate(ref.index), cssTargets);
  }
}

function extensionOf(full) {
  const base = path.basename(full);
  const dot = base.lastIndexOf('.');
  if (dot <= 0) return '';
  return base.slice(dot).toLowerCase();
}

function attrValue(tag, name) {
  return tag.attributes.find((attribute) => attribute.name === name);
}

function rawTextStart(html, index, tagName) {
  // Returns the index just past the '>' of an opening <tagName ...> tag, or
  // null when the tag is not at index. An attribute may quote a '>'.
  const lower = html.toLowerCase();
  if (!lower.startsWith(`<${tagName}`, index)) return null;
  const after = html[index + 1 + tagName.length];
  if (!/[\s/>]/.test(after ?? '')) return null;
  let cursor = index + 1 + tagName.length;
  while (cursor < html.length && html[cursor] !== '>') {
    const quote = html[cursor];
    if (quote === '"' || quote === "'") {
      const close = html.indexOf(quote, cursor + 1);
      cursor = close === -1 ? html.length : close + 1;
      continue;
    }
    cursor += 1;
  }
  return html[cursor] === '>' ? cursor + 1 : html.length;
}

function closeTagEnd(lower, from, tagName) {
  const close = lower.indexOf(`</${tagName}`, from);
  if (close === -1) return htmlEnd(lower);
  const gt = lower.indexOf('>', close);
  return gt === -1 ? htmlEnd(lower) : gt + 1;
}

function htmlEnd(html) {
  return html.length;
}

function styleBlocks(html) {
  const blocks = [];
  const lower = html.toLowerCase();
  let index = 0;
  while (index < html.length) {
    if (html.startsWith('<!--', index)) {
      const end = html.indexOf('-->', index + 4);
      index = end === -1 ? html.length : end + 3;
      continue;
    }
    if (lower.startsWith('<script', index)) {
      const start = rawTextStart(html, index, 'script');
      if (start !== null) {
        index = closeTagEnd(lower, start, 'script');
        continue;
      }
    }
    if (lower.startsWith('<style', index)) {
      const start = rawTextStart(html, index, 'style');
      if (start !== null) {
        const close = lower.indexOf('</style', start);
        const end = close === -1 ? html.length : close;
        blocks.push({ content: html.slice(start, end), index: start });
        index = close === -1 ? html.length : closeTagEnd(lower, start, 'style');
        continue;
      }
    }
    index += 1;
  }
  return blocks;
}

function scanHtml(context, full) {
  const rel = relativePath(context.root, full);
  let text;
  try {
    text = fs.readFileSync(full, 'utf8');
  } catch (error) {
    context.failures.push(
      `FAIL unreadable-file: ${rel}: ${error.code || error.name}`,
    );
    return 1;
  }
  context.rel = rel;
  context.servedRel = relativePath(context.dist, full);
  const tags = scanTags(text);
  for (const tag of tags) {
    if (tag.name !== 'link') continue;
    const rels = (attrValue(tag, 'rel')?.value ?? '')
      .toLowerCase()
      .split(/\s+/)
      .filter(Boolean);
    const href = attrValue(tag, 'href');
    if (!href || href.value === '') continue;
    if (rels.includes('stylesheet')) {
      checkReference(
        context,
        'stylesheet',
        href.value,
        href.line,
        context.cssTargets,
      );
      continue;
    }
    if (rels.includes('preload')) {
      const as = (attrValue(tag, 'as')?.value ?? '').toLowerCase();
      if (as === 'font') {
        checkReference(
          context,
          'preload',
          href.value,
          href.line,
          context.cssTargets,
        );
      }
    }
  }
  for (const block of styleBlocks(text)) {
    scanFontRules(
      context,
      block.content,
      (index) => lineAt(text, block.index + index),
      context.families,
      context.cssTargets,
    );
  }
  for (const tag of tags) {
    const style = attrValue(tag, 'style');
    if (!style || style.value === '') continue;
    // A style attribute holds a declaration block, so an at-rule inside it
    // is invalid CSS and delivers no family; it is still scanned, so an
    // embedded or escaping target cannot hide there.
    scanFontRules(
      context,
      style.value,
      () => style.line,
      null,
      context.cssTargets,
    );
  }
  return 1;
}

function scanCss(context, full) {
  const rel = relativePath(context.root, full);
  let text;
  try {
    text = fs.readFileSync(full, 'utf8');
  } catch (error) {
    context.failures.push(
      `FAIL unreadable-file: ${rel}: ${error.code || error.name}`,
    );
    return 1;
  }
  context.rel = rel;
  context.servedRel = relativePath(context.dist, full);
  scanFontRules(
    context,
    text,
    (index) => lineAt(text, index),
    context.families,
    context.cssTargets,
  );
  return 1;
}

function scanDist(root, failures) {
  const dist = path.join(root, 'dist');
  let info;
  try {
    info = fs.statSync(dist);
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') {
      failures.push('FAIL dist-missing: dist: absent');
      return 0;
    }
    throw error;
  }
  if (!info.isDirectory()) {
    failures.push('FAIL dist-missing: dist: not a directory');
    return 0;
  }
  const distReal = fs.realpathSync(dist);
  const pending = [];
  const seen = new Set();
  const cssTargets = {
    add(full) {
      if (!seen.has(full)) {
        seen.add(full);
        pending.push(full);
      }
    },
  };
  const context = {
    root,
    dist,
    distReal,
    failures,
    families: new Set(),
    cssTargets,
    rel: 'dist',
    servedRel: '',
  };
  const htmlFiles = [];
  walk(dist, (item) => {
    if (item.error) {
      failures.push(
        `FAIL unreadable-file: ${relativePath(root, item.full)}: ${item.error.code || item.error.name}`,
      );
      return;
    }
    const extension = extensionOf(item.full);
    if (extension === '.css') cssTargets.add(item.full);
    else if (extension === '.html' || extension === '.htm')
      htmlFiles.push(item.full);
  });
  let files = 0;
  // HTML first, so stylesheet targets join the CSS worklist before it runs.
  for (const full of htmlFiles) files += scanHtml(context, full);
  while (pending.length > 0) files += scanCss(context, pending.pop());
  if (context.families.size === 0) {
    failures.push('FAIL font-face-absent: dist: no @font-face rule');
  } else {
    for (const family of REQUIRED_FAMILIES) {
      if (!context.families.has(family.toLowerCase())) {
        failures.push(`FAIL font-family-missing: dist: ${family}`);
      }
    }
  }
  for (const rel of FONT_LICENCE_FILES) {
    const full = path.join(root, rel);
    let stat;
    try {
      stat = fs.statSync(full);
    } catch (error) {
      if (error.code === 'ENOENT' || error.code === 'ENOTDIR') {
        failures.push(`FAIL font-licence-missing: ${rel}`);
        continue;
      }
      throw error;
    }
    if (!stat.isFile()) {
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
    const files = scanDist(root, failures);
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
