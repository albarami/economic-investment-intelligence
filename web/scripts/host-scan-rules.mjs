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
      const allowed =
        builtScript &&
        (scheme.toLowerCase() === 'http' || scheme.toLowerCase() === 'https') &&
        INERT_HOSTS.includes(host);
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

function protocolHits(text) {
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
    const host = match[4];
    if (host.includes('.')) {
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
  return [...schemeHits(text, builtScript), ...protocolHits(text)];
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
