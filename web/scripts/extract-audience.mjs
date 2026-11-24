#!/usr/bin/env node
// Web extractor of the standing audience-origin check (decision 0035 item 5;
// S3-T19). Emits typed surface evidence (audience-evidence.v1) for the
// audience-visible text of the built app and the source tree:
//
//   web.dist.document        copy and style inputs of dist/index.html
//   web.dist.accessible      accessible names/descriptions of the built page
//   web.urls                 audience URLs, percent- and entity-decoded
//   web.strings.en / .ar     the i18n string tables (screen copy)
//   web.accessible.en / .ar  strings used in accessible positions, resolved
//   web.src.accessible       literal accessible attributes of the source
//   web.src.style            literal class/id/style inputs of the source
//   web.catalogue.generated  rendered fields of the generated catalogue
//
// An input that is absent reports status "absent" with no items, so a missing
// or opaque artifact can never pass as an empty scan. The Python checker
// (scripts/check_audience_origin.py) consumes this document and fails on any
// absent required surface, empty extraction or planted origin label.
//
// Usage: node web/scripts/extract-audience.mjs [--root REPO_ROOT]

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SCHEMA = 'audience-evidence.v1';

export const ACCESSIBLE_ATTRIBUTE_NAMES = [
  'aria-label',
  'aria-labelledby',
  'aria-description',
  'aria-describedby',
  'aria-roledescription',
  'alt',
  'title',
  'placeholder',
];

const URL_ATTRIBUTE_NAMES = [
  'href',
  'src',
  'action',
  'formaction',
  'poster',
  'xlink:href',
];

const STYLE_ATTRIBUTE_NAMES = ['class', 'id', 'style'];

const VOID_ELEMENTS = new Set([
  'area',
  'base',
  'br',
  'col',
  'embed',
  'hr',
  'img',
  'input',
  'link',
  'meta',
  'param',
  'source',
  'track',
  'wbr',
]);

const OPAQUE_ELEMENTS = new Set(['script', 'style']);

const ENTITIES = {
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  nbsp: ' ',
};

const WITHHELD_KEY = /suppress|withheld|hidden/i;
const URL_KEY = /(?:^|[._-])(?:url|href|uri)$/i;

function decodeEntities(text) {
  return text.replace(
    /&(#[xX][0-9a-fA-F]+|#[0-9]+|[a-zA-Z]+);/g,
    (whole, group) => {
      if (group.startsWith('#')) {
        const code =
          group[1] === 'x' || group[1] === 'X'
            ? parseInt(group.slice(2), 16)
            : parseInt(group.slice(1), 10);
        return Number.isFinite(code) ? String.fromCodePoint(code) : whole;
      }
      return Object.prototype.hasOwnProperty.call(ENTITIES, group)
        ? ENTITIES[group]
        : whole;
    },
  );
}

export function decodeText(text) {
  const entities = decodeEntities(text);
  try {
    return decodeURIComponent(entities);
  } catch {
    return entities;
  }
}

function* tagsOf(html) {
  let index = 0;
  while (true) {
    const start = html.indexOf('<', index);
    if (start < 0) {
      if (index < html.length) yield { text: html.slice(index) };
      return;
    }
    if (start > index) yield { text: html.slice(index, start) };
    let cursor = start + 1;
    let quote = null;
    while (cursor < html.length) {
      const char = html[cursor];
      if (quote) {
        if (char === quote) quote = null;
      } else if (char === '"' || char === "'") {
        quote = char;
      } else if (char === '>') {
        break;
      }
      cursor += 1;
    }
    yield { raw: html.slice(start, cursor + 1), start, end: cursor + 1 };
    index = cursor + 1;
  }
}

const ATTRIBUTE_PATTERN =
  /([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?/g;

function attributesOf(inner) {
  const found = [];
  for (const match of inner.matchAll(ATTRIBUTE_PATTERN)) {
    const [, name, doubleQuoted, singleQuoted, bare] = match;
    if (name.startsWith('<') || name.startsWith('/')) continue;
    found.push({
      name: name.toLowerCase(),
      value: doubleQuoted ?? singleQuoted ?? bare ?? '',
    });
  }
  return found;
}

function item(field, fieldKind, outputClass, language, text) {
  return {
    field,
    field_kind: fieldKind,
    output_class: outputClass,
    language,
    text,
  };
}

export function extractDocument(html, name) {
  const copy = [];
  const accessible = [];
  const urls = [];
  const styles = [];
  const seenCopy = new Set();
  const stack = [];
  let elementIndex = 0;
  const opaque = () => stack.some((entry) => OPAQUE_ELEMENTS.has(entry.tag));
  for (const part of tagsOf(html)) {
    if (part.text !== undefined) {
      if (!opaque() && part.text.trim() !== '') {
        for (const entry of stack) entry.buffer += part.text;
      }
      continue;
    }
    const raw = part.raw;
    if (raw.startsWith('<!--') || raw.startsWith('<!') || raw.startsWith('<?'))
      continue;
    const closing = /^<\s*\/\s*([a-zA-Z][\w:-]*)/.exec(raw);
    if (closing) {
      const tag = closing[1].toLowerCase();
      while (stack.length) {
        const entry = stack.pop();
        const text = decodeText(entry.buffer.replace(/\s+/g, ' ').trim());
        if (text !== '' && !seenCopy.has(text)) {
          seenCopy.add(text);
          copy.push(
            item(`${name}:${entry.tag}`, 'copy', 'screen', 'und', text),
          );
        }
        if (entry.tag === tag) break;
      }
      continue;
    }
    const opened = /^<\s*([a-zA-Z][\w:-]*)([\s\S]*?)\/?>$/.exec(raw);
    if (!opened) continue;
    const tag = opened[1].toLowerCase();
    elementIndex += 1;
    const where = `${name}:${tag}[${elementIndex}]`;
    for (const attribute of attributesOf(opened[2])) {
      if (ACCESSIBLE_ATTRIBUTE_NAMES.includes(attribute.name)) {
        accessible.push(
          item(
            `${where}@${attribute.name}`,
            'accessible',
            'accessible',
            'und',
            decodeText(attribute.value),
          ),
        );
      } else if (URL_ATTRIBUTE_NAMES.includes(attribute.name)) {
        urls.push(
          item(
            `${where}@${attribute.name}`,
            'url',
            'url',
            'und',
            decodeText(attribute.value),
          ),
        );
      } else if (STYLE_ATTRIBUTE_NAMES.includes(attribute.name)) {
        styles.push(
          item(
            `${where}@${attribute.name}`,
            'style',
            'screen',
            'und',
            attribute.value,
          ),
        );
      }
    }
    if (!VOID_ELEMENTS.has(tag) && !raw.endsWith('/>')) {
      stack.push({ tag, buffer: '' });
    }
  }
  return { copy, accessible, urls, styles };
}

function walkFiles(dir, predicate) {
  const found = [];
  if (!fs.existsSync(dir)) return found;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name.startsWith('.')) continue;
      found.push(...walkFiles(full, predicate));
    } else if (entry.isFile() && predicate(entry.name)) {
      found.push(full);
    }
  }
  return found.sort();
}

const SOURCE_LIKE = /\.(tsx?|jsx?|html)$/;

const LITERAL_ACCESSIBLE = new RegExp(
  `\\b(${ACCESSIBLE_ATTRIBUTE_NAMES.join('|')})\\s*=\\s*(["'\`])([^"'\`]+)\\2`,
  'g',
);
const LITERAL_URL = new RegExp(
  `\\b(${URL_ATTRIBUTE_NAMES.join('|')})\\s*=\\s*(["'\`])([^"'\`]+)\\2`,
  'g',
);
const LITERAL_STYLE = /\b(?:className|class)\s*=\s*(["'`])([^"'`]+)\1/g;
const CANVAS_TEXT = /\b(?:fillText|strokeText)\s*\(\s*(["'`])([^"'`]+)\1/g;
const ACCESSIBLE_REF = new RegExp(
  `\\b(${ACCESSIBLE_ATTRIBUTE_NAMES.join('|')})\\s*=\\s*\\{[^}]*?text\\(\\s*language\\s*,\\s*'([^']+)'\\s*\\)`,
  'g',
);

function sourceItems(web, fileName) {
  const text = fs.readFileSync(fileName, 'utf8');
  const origin = path.relative(web, fileName).split(path.sep).join('/');
  const accessible = [];
  const urls = [];
  const styles = [];
  const keys = new Set();
  for (const match of text.matchAll(LITERAL_ACCESSIBLE)) {
    if (match[3].startsWith('{')) continue;
    accessible.push(
      item(
        `${origin}@${match[1]}`,
        'accessible',
        'accessible',
        'und',
        decodeText(match[3]),
      ),
    );
  }
  for (const match of text.matchAll(ACCESSIBLE_REF)) {
    keys.add(match[2]);
  }
  for (const match of text.matchAll(LITERAL_URL)) {
    const value = match[3];
    if (!/^https?:|^\/|^data:|^#|^\./.test(value)) continue;
    urls.push(
      item(`${origin}@${match[1]}`, 'url', 'url', 'und', decodeText(value)),
    );
  }
  for (const match of text.matchAll(LITERAL_STYLE)) {
    styles.push(item(`${origin}@class`, 'style', 'screen', 'und', match[2]));
  }
  for (const match of text.matchAll(CANVAS_TEXT)) {
    // Canvas pixels are opaque to the DOM; the paint call's text is the
    // only extraction evidence a canvas watermark leaves.
    styles.push(
      item(`${origin}@canvas-text`, 'copy', 'screen', 'und', match[2]),
    );
  }
  return { accessible, urls, styles, keys };
}

function surface(id, origin, status, items) {
  return { id, origin, status, items };
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function stringsItems(table, language) {
  const strings =
    table && typeof table === 'object' && table.strings ? table.strings : {};
  const items = [];
  for (const [key, value] of Object.entries(strings)) {
    if (typeof value !== 'string') continue;
    if (WITHHELD_KEY.test(key)) {
      items.push(item(key, 'withheld', 'screen', language, value));
    } else if (URL_KEY.test(key)) {
      items.push(item(key, 'url', 'url', language, decodeText(value)));
    } else {
      items.push(item(key, 'copy', 'screen', language, value));
    }
  }
  return items;
}

function catalogueItems(node, prefix, items) {
  if (Array.isArray(node)) {
    if (node.length === 2 && typeof node[0] === 'string') {
      catalogueItems(node[1], `${prefix}.${node[0]}`, items);
      return;
    }
    node.forEach((value, index) =>
      catalogueItems(value, `${prefix}[${index}]`, items),
    );
    return;
  }
  if (node && typeof node === 'object') {
    for (const [key, value] of Object.entries(node)) {
      const dotted = prefix ? `${prefix}.${key}` : key;
      catalogueItems(value, dotted, items);
    }
    return;
  }
  if (typeof node !== 'string') return;
  const leaf = prefix.split('.').pop() ?? '';
  if (leaf.endsWith('_en')) {
    items.push(item(prefix, 'copy', 'catalogue', 'en', node));
  } else if (leaf.endsWith('_ar')) {
    items.push(item(prefix, 'copy', 'catalogue', 'ar', node));
  } else {
    items.push(item(prefix, 'backend', 'catalogue', 'und', node));
  }
}

export function surfaceIds(evidence) {
  return evidence.surfaces.map((entry) => entry.id);
}

export function collectEvidence(root) {
  const web = path.join(root, 'web');
  const surfaces = [];

  const documentPath = path.join(web, 'dist', 'index.html');
  const built = fs.existsSync(documentPath)
    ? extractDocument(
        fs.readFileSync(documentPath, 'utf8'),
        'web/dist/index.html',
      )
    : null;
  surfaces.push(
    surface(
      'web.dist.document',
      'web/dist/index.html',
      built ? 'ok' : 'absent',
      built ? [...built.copy, ...built.styles] : [],
    ),
  );
  surfaces.push(
    surface(
      'web.dist.accessible',
      'web/dist/index.html',
      built ? 'ok' : 'absent',
      built ? built.accessible : [],
    ),
  );

  const sourceFiles = [
    ...(fs.existsSync(path.join(web, 'index.html'))
      ? [path.join(web, 'index.html')]
      : []),
    ...walkFiles(path.join(web, 'src'), (name) => SOURCE_LIKE.test(name)),
  ];
  const srcAccessible = [];
  const srcStyles = [];
  const srcUrls = [];
  const accessibleKeys = new Set();
  for (const fileName of sourceFiles) {
    const found = sourceItems(web, fileName);
    srcAccessible.push(...found.accessible);
    srcStyles.push(...found.styles);
    srcUrls.push(...found.urls);
    for (const key of found.keys) accessibleKeys.add(key);
  }

  const urlStatus = built || srcUrls.length ? 'ok' : 'absent';
  surfaces.push(
    surface('web.urls', 'web/dist + web/src', urlStatus, [
      ...(built ? built.urls : []),
      ...srcUrls,
    ]),
  );

  for (const language of ['en', 'ar']) {
    const file = path.join(web, 'src', 'i18n', `${language}.json`);
    const table = fs.existsSync(file) ? readJson(file) : null;
    surfaces.push(
      surface(
        `web.strings.${language}`,
        `web/src/i18n/${language}.json`,
        table ? 'ok' : 'absent',
        table ? stringsItems(table, language) : [],
      ),
    );
    const resolved = [];
    if (table) {
      const strings = table.strings ?? {};
      for (const key of [...accessibleKeys].sort()) {
        if (typeof strings[key] !== 'string') continue;
        resolved.push(
          item(
            `${key}@accessible`,
            'accessible',
            'accessible',
            language,
            strings[key],
          ),
        );
      }
    }
    surfaces.push(
      surface(
        `web.accessible.${language}`,
        `web/src/i18n/${language}.json + web/src`,
        table ? 'ok' : 'absent',
        resolved,
      ),
    );
  }

  surfaces.push(
    surface(
      'web.src.accessible',
      'web/src + web/index.html',
      sourceFiles.length ? 'ok' : 'absent',
      srcAccessible,
    ),
  );
  surfaces.push(
    surface(
      'web.src.style',
      'web/src + web/index.html',
      sourceFiles.length ? 'ok' : 'absent',
      srcStyles,
    ),
  );

  const catalogueFile = path.join(
    web,
    'src',
    'brief',
    'catalogue.generated.json',
  );
  const catalogue = fs.existsSync(catalogueFile)
    ? readJson(catalogueFile)
    : null;
  const catalogueEntries = [];
  if (catalogue) catalogueItems(catalogue, '', catalogueEntries);
  surfaces.push(
    surface(
      'web.catalogue.generated',
      'web/src/brief/catalogue.generated.json',
      catalogue ? 'ok' : 'absent',
      catalogueEntries,
    ),
  );

  return {
    schema: SCHEMA,
    extractor: 'extract-audience.mjs',
    surfaces,
    generated_outputs: [],
    source_chains: [],
  };
}

function main(argv) {
  let root = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    '..',
    '..',
  );
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === '--root' && argv[index + 1]) {
      root = path.resolve(argv[index + 1]);
      index += 1;
    }
  }
  process.stdout.write(`${JSON.stringify(collectEvidence(root), null, 2)}\n`);
}

if (
  process.argv[1] &&
  fileURLToPath(import.meta.url) === path.resolve(process.argv[1])
) {
  main(process.argv.slice(2));
}
