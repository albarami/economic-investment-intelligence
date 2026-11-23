/*
 * Tokenizes CSS enough to find every active @font-face rule and font import.
 * Comments are skipped, at-keywords and identifiers match case-insensitively
 * with CSS escapes decoded, and rule and declaration boundaries are respected,
 * so a font cannot be hidden from or smuggled past the scanner by spelling or
 * commenting. A rule that CSS deactivates (fully commented out, or an
 * at-keyword without its block) is never reported.
 */

const WHITESPACE = new Set([' ', '\t', '\n', '\r', '\f']);
const HEX = /[0-9A-Fa-f]/;
const IDENT_START = /[A-Za-z_\u0080-\uffff-]/;
const IDENT_PART = /[A-Za-z0-9_\u0080-\uffff-]/;

function decodeEscape(text, index) {
  // text[index] is the backslash.
  const after = text[index + 1];
  if (after === undefined) return { value: '', next: index + 1 };
  if (HEX.test(after)) {
    let hex = '';
    let cursor = index + 1;
    while (cursor < text.length && hex.length < 6 && HEX.test(text[cursor])) {
      hex += text[cursor];
      cursor += 1;
    }
    let next = cursor;
    if (next < text.length && WHITESPACE.has(text[next])) next += 1;
    const code = Number.parseInt(hex, 16);
    const value =
      code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff)
        ? '\ufffd'
        : String.fromCodePoint(code);
    return { value, next };
  }
  if (after === '\n') return { value: '', next: index + 2 };
  return { value: after, next: index + 2 };
}

function isEscapeAt(text, index) {
  return text[index] === '\\' && index + 1 < text.length;
}

function readIdent(text, start) {
  let value = '';
  let cursor = start;
  while (cursor < text.length) {
    const character = text[cursor];
    if (isEscapeAt(text, cursor)) {
      const decoded = decodeEscape(text, cursor);
      value += decoded.value;
      cursor = decoded.next;
      continue;
    }
    if (
      value === '' ? IDENT_START.test(character) : IDENT_PART.test(character)
    ) {
      value += character;
      cursor += 1;
      continue;
    }
    break;
  }
  return value === '' ? null : { value, next: cursor };
}

function readString(text, start) {
  const quote = text[start];
  let value = '';
  let cursor = start + 1;
  while (cursor < text.length && text[cursor] !== quote) {
    if (text[cursor] === '\\') {
      const decoded = decodeEscape(text, cursor);
      value += decoded.value;
      cursor = decoded.next;
      continue;
    }
    value += text[cursor];
    cursor += 1;
  }
  return { value, next: cursor < text.length ? cursor + 1 : cursor };
}

function readUrl(text, openParen) {
  let cursor = openParen;
  while (cursor < text.length && WHITESPACE.has(text[cursor])) cursor += 1;
  if (text[cursor] === '"' || text[cursor] === "'") {
    const string = readString(text, cursor);
    let after = string.next;
    while (after < text.length && WHITESPACE.has(text[after])) after += 1;
    if (text[after] === ')') after += 1;
    return { value: string.value, next: after };
  }
  let value = '';
  while (cursor < text.length) {
    const character = text[cursor];
    if (character === ')') return { value, next: cursor + 1 };
    if (
      WHITESPACE.has(character) ||
      character === '(' ||
      character === '"' ||
      character === "'"
    ) {
      // A bad url token: everything up to the next ')' is part of it.
      while (cursor < text.length && text[cursor] !== ')') cursor += 1;
      return { value, next: cursor < text.length ? cursor + 1 : cursor };
    }
    if (character === '\\') {
      const decoded = decodeEscape(text, cursor);
      value += decoded.value;
      cursor = decoded.next;
      continue;
    }
    value += character;
    cursor += 1;
  }
  return { value, next: cursor };
}

function* cssTokens(text) {
  let index = 0;
  while (index < text.length) {
    const character = text[index];
    if (WHITESPACE.has(character)) {
      index += 1;
      continue;
    }
    if (character === '/' && text[index + 1] === '*') {
      const end = text.indexOf('*/', index + 2);
      index = end === -1 ? text.length : end + 2;
      continue;
    }
    if (character === '"' || character === "'") {
      const string = readString(text, index);
      yield { kind: 'string', value: string.value, index };
      index = string.next;
      continue;
    }
    if (character === '@') {
      const ident = readIdent(text, index + 1);
      if (ident) {
        yield { kind: 'at', value: ident.value.toLowerCase(), index };
        index = ident.next;
        continue;
      }
      yield { kind: 'delim', value: character, index };
      index += 1;
      continue;
    }
    const ident = readIdent(text, index);
    if (ident) {
      if (text[ident.next] === '(') {
        if (ident.value.toLowerCase() === 'url') {
          const url = readUrl(text, ident.next + 1);
          yield { kind: 'url', value: url.value, index };
          index = url.next;
          continue;
        }
        yield { kind: 'func', value: ident.value.toLowerCase(), index };
        index = ident.next + 1;
        continue;
      }
      yield { kind: 'ident', value: ident.value, index };
      index = ident.next;
      continue;
    }
    yield { kind: 'delim', value: character, index };
    index += 1;
  }
}

function isDelim(token, value) {
  return token?.kind === 'delim' && token.value === value;
}

function faceFromBlock(tokens, faceIndex) {
  const face = { family: '', urls: [], index: faceIndex };
  let index = 0;
  while (index < tokens.length) {
    const token = tokens[index];
    if (token.kind !== 'ident' || !isDelim(tokens[index + 1], ':')) {
      index += 1;
      continue;
    }
    const name = token.value.toLowerCase();
    if (name !== 'font-family' && name !== 'src') {
      index += 2;
      continue;
    }
    const value = [];
    let cursor = index + 2;
    while (
      cursor < tokens.length &&
      !isDelim(tokens[cursor], ';') &&
      !isDelim(tokens[cursor], '{') &&
      !isDelim(tokens[cursor], '}')
    ) {
      value.push(tokens[cursor]);
      cursor += 1;
    }
    if (name === 'font-family') {
      if (value[0]?.kind === 'string') {
        face.family = value[0].value;
      } else {
        face.family = value
          .filter((entry) => entry.kind === 'ident')
          .map((entry) => entry.value)
          .join(' ');
      }
    } else {
      face.urls.push(
        ...value
          .filter((entry) => entry.kind === 'url')
          .map((entry) => ({ value: entry.value, index: entry.index })),
      );
    }
    index = cursor;
  }
  return face;
}

function parseFace(tokens, atToken, next) {
  // An at-keyword without its block is invalid CSS and browsers drop it.
  if (!isDelim(tokens[next], '{')) return null;
  const block = [];
  let depth = 1;
  let cursor = next + 1;
  while (cursor < tokens.length && depth > 0) {
    if (isDelim(tokens[cursor], '{')) depth += 1;
    if (isDelim(tokens[cursor], '}')) {
      depth -= 1;
      if (depth === 0) break;
    }
    block.push(tokens[cursor]);
    cursor += 1;
  }
  const face = faceFromBlock(block, atToken.index);
  face.urls.sort((left, right) => left.index - right.index);
  return { face, next: Math.min(cursor + 1, tokens.length) };
}

function parseImport(tokens, next) {
  let target = null;
  let cursor = next;
  while (
    cursor < tokens.length &&
    !isDelim(tokens[cursor], ';') &&
    !isDelim(tokens[cursor], '{') &&
    !isDelim(tokens[cursor], '}')
  ) {
    const token = tokens[cursor];
    if (!target && (token.kind === 'url' || token.kind === 'string')) {
      target = { value: token.value, index: token.index };
    }
    cursor += 1;
  }
  if (!target) return null;
  return { import: target, next: Math.min(cursor + 1, tokens.length) };
}

export function parseFontCss(text) {
  const tokens = [...cssTokens(text)];
  const faces = [];
  const imports = [];
  let index = 0;
  while (index < tokens.length) {
    const token = tokens[index];
    if (token.kind === 'at' && token.value === 'font-face') {
      const parsed = parseFace(tokens, token, index + 1);
      if (parsed) {
        faces.push(parsed.face);
        index = parsed.next;
        continue;
      }
    } else if (token.kind === 'at' && token.value === 'import') {
      const parsed = parseImport(tokens, index + 1);
      if (parsed) {
        imports.push(parsed.import);
        index = parsed.next;
        continue;
      }
    }
    index += 1;
  }
  return { faces, imports };
}
