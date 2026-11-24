import { createHash } from 'node:crypto';

const INERT_HOSTS = [
  // XML namespace identifiers in react-dom
  'www.w3.org',
  // error and warning message text
  'react.dev',
  // error and warning message text
  'reactjs.org',
  // issue links in messages
  'github.com',
];

// One exact scheme and one exact host, as the scanner reads them.
// Each counts only in a built script.
const INERT_SCHEME_HOSTS = [
  // maplibre-gl: placeholder base used only to read a URL protocol
  ['https', 'maplibre.invalid'],
  // maplibre-gl: text of the WebGL error message
  ['https', 'wiki.openstreetmap.org'],
  // maplibre-gl: attribution and logo text; this page mounts neither control
  ['https', 'maplibre.org'],
  // maplibre-gl: Android origin token, compared and never fetched
  ['resource', 'android'],
  // pmtiles: regular expression that parses a tile address
  ['pmtiles', '(.+'],
  // luma.gl: text of a shader source comment, never fetched
  ['https', 'en.wikipedia.org'],
  // loaders.gl: default worker CDN; unreachable: overlayFor sets worker false (test overlayFor sets worker false and sets no CDN) and gives every layer in-memory rows (test overlayFor gives every layer in-memory rows)
  ['https', 'unpkg.com'],
];

// Exact slashes and host text, as protocolHits captures groups 3 and 4.
// Each counts only in a built script.
const INERT_PROTOCOL_RELATIVE = [
  // luma.gl: regular-expression source of a shader deprecation pattern
  ['\\\\', 'b${e.old}'],
  // luma.gl: regular-expression source that strips a line comment
  ['/\\/\\/', '.*$'],
  // luma.gl: regular-expression source that cuts a hook signature
  ['/\\', '(.+'],
  // luma.gl: regular-expression source of a fragment-input pattern
  ['\\\\', 'b${U(l.name'],
  // loaders.gl: regular-expression source of a file-extension pattern
  ['/\\', '.([^.]+'],
  // loaders.gl: regular-expression source of an svg-address pattern
  ['/\\', '.svg(('],
];

// Licence texts, accepted by path and SHA-256 only.
const LICENCE_TEXTS = [
  // Pinned decoder notices; identity, never a host allowance.
  [
    'dist/licences/photoreal-loaders.txt',
    '092a0a3ad1bc93e3667f666257cadb82b9a2acac483d6c798df3aed156c876e3',
  ],
  // Pinned RTL plugin and its bundled ICU notice; identity, never a host allowance.
  [
    'dist/licences/mapbox-gl-rtl-text.txt',
    '7dca3646879aae2fa04f9d77f98ddeeabe4898be6a592a59985c112fd817300b',
  ],
  // @fontsource/ibm-plex-sans: the licence, including its own address
  [
    'dist/licences/ibm-plex-sans.txt',
    'd0283623ef57e722fd0eb688a8041589670c608ab780cd3612d06ba6f153d3fd',
  ],
  // @fontsource/ibm-plex-sans-arabic: the licence, including its own address
  [
    'dist/licences/ibm-plex-sans-arabic.txt',
    '1c32ddc3fc6efd167cdcbe475195287f2dc26ed1a4c92fbe31c87ceaffe44f98',
  ],
];

function inertProtocolRelative(slashes, host) {
  return INERT_PROTOCOL_RELATIVE.some(
    ([listedSlashes, listedHost]) =>
      listedSlashes === slashes && listedHost === host,
  );
}

function inertBuilt(scheme, host) {
  const name = scheme.toLowerCase();
  if ((name === 'http' || name === 'https') && INERT_HOSTS.includes(host)) {
    return true;
  }
  return INERT_SCHEME_HOSTS.some(
    ([listedScheme, listedHost]) =>
      listedScheme === name && listedHost === host,
  );
}

export function acceptedLicence(rel, bytes) {
  const row = LICENCE_TEXTS.find(([file]) => file === rel);
  if (!row) return false;
  const digest = createHash('sha256').update(bytes).digest('hex');
  return digest === row[1];
}

const PROTOCOL_PRECEDING = ['"', "'", '`', '(', '=', ','];

const HOST_STOP = new Set([
  '/',
  '\\',
  '?',
  '#',
  ':',
  '"',
  "'",
  '`',
  '<',
  '>',
  ',',
  ')',
  ' ',
  '\t',
  '\n',
  '\r',
]);

function lineAt(text, index) {
  let line = 1;
  for (let cursor = 0; cursor < index; cursor += 1) {
    if (text[cursor] === '\n') line += 1;
  }
  return line;
}

function readHost(text, start) {
  let end = start;
  while (end < text.length && !HOST_STOP.has(text[end])) end += 1;
  return text.slice(start, end);
}

function schemeHits(text, builtScript) {
  const hits = [];
  const pattern = /([A-Za-z][A-Za-z0-9+.-]*):([/\\]{2,})/g;
  let match = pattern.exec(text);
  while (match) {
    const after = match.index + match[0].length;
    const next = text[after];
    if (next !== undefined && !/[\s'"`]/.test(next)) {
      const host = readHost(text, after).toLowerCase();
      const scheme = match[1];
      const allowed = builtScript && inertBuilt(scheme, host);
      if (!allowed) {
        const rule = builtScript ? 'absolute-url-js' : 'absolute-url';
        const detail = builtScript
          ? `${scheme} URL, host ${host}`
          : `${scheme} URL`;
        hits.push({ rule, line: lineAt(text, match.index), detail });
      }
    }
    match = pattern.exec(text);
  }
  return hits;
}

function protocolHits(text, builtScript) {
  const hits = [];
  const escaped = PROTOCOL_PRECEDING.map((character) =>
    character.replace(/[\\^\]-]/g, '\\$&'),
  ).join('');
  const pattern = new RegExp(
    `([${escaped}])(\\s*)([/\\\\]{2,})([^\\s/\\\\?#:'"\`<>,)]+)`,
    'g',
  );
  let match = pattern.exec(text);
  while (match) {
    const slashes = match[3];
    const host = match[4];
    const allowed = builtScript && inertProtocolRelative(slashes, host);
    if (host.includes('.') && !allowed) {
      hits.push({
        rule: 'protocol-relative-url',
        line: lineAt(text, match.index),
        detail: 'protocol-relative URL',
      });
    }
    match = pattern.exec(text);
  }
  return hits;
}

export function scanText(text, options = {}) {
  const builtScript = options.builtScript === true;
  return [...schemeHits(text, builtScript), ...protocolHits(text, builtScript)];
}

export function scanTags(html) {
  const tags = [];
  let index = 0;
  let line = 1;
  while (index < html.length) {
    if (html[index] === '\n') {
      line += 1;
      index += 1;
      continue;
    }
    if (html[index] === '<' && /[A-Za-z]/.test(html[index + 1] ?? '')) {
      const tagLine = line;
      index += 1;
      let name = '';
      while (index < html.length && /[A-Za-z0-9]/.test(html[index])) {
        name += html[index].toLowerCase();
        index += 1;
      }
      const attributes = [];
      while (index < html.length && html[index] !== '>') {
        if (html[index] === '\n') {
          line += 1;
          index += 1;
          continue;
        }
        if (/\s/.test(html[index])) {
          index += 1;
          continue;
        }
        if (html[index] === '/') {
          index += 1;
          continue;
        }
        const attrLine = line;
        let attr = '';
        while (index < html.length && /[^\s=/<>]/.test(html[index])) {
          attr += html[index].toLowerCase();
          index += 1;
        }
        while (index < html.length && /\s/.test(html[index])) {
          if (html[index] === '\n') line += 1;
          index += 1;
        }
        if (html[index] !== '=') {
          if (attr) attributes.push({ name: attr, value: '', line: attrLine });
          continue;
        }
        index += 1;
        while (index < html.length && /\s/.test(html[index])) {
          if (html[index] === '\n') line += 1;
          index += 1;
        }
        let value = '';
        if (html[index] === '"' || html[index] === "'") {
          const quote = html[index];
          index += 1;
          while (index < html.length && html[index] !== quote) {
            if (html[index] === '\n') line += 1;
            value += html[index];
            index += 1;
          }
          if (index < html.length && html[index] === quote) index += 1;
        } else {
          while (index < html.length && !/[\s>]/.test(html[index])) {
            value += html[index];
            index += 1;
          }
        }
        attributes.push({ name: attr, value, line: attrLine });
      }
      if (html[index] === '>') index += 1;
      tags.push({ name, line: tagLine, attributes });
      continue;
    }
    index += 1;
  }
  return tags;
}
