import { FULL_TOKENS } from './scene-size-sites.mjs';

const MODE_NAMES = new Set(['SMALL', ...FULL_TOKENS]);

function keywordAt(source, index, word) {
  if (!source.startsWith(word, index)) return false;
  const prev = source[index - 1] ?? '';
  const next = source[index + word.length] ?? '';
  if (/[A-Za-z0-9_$]/.test(prev) || /[A-Za-z0-9_$]/.test(next)) return false;
  return prev !== '.';
}

function skipSpace(source, index) {
  let cursor = index;
  while (cursor < source.length && /\s/.test(source[cursor])) cursor += 1;
  return cursor;
}

function readIdent(source, index) {
  if (!/[A-Za-z_$]/.test(source[index] ?? '')) return '';
  let end = index + 1;
  while (/[A-Za-z0-9_$]/.test(source[end] ?? '')) end += 1;
  return source.slice(index, end);
}

function readIdentBackward(source, end) {
  if (!/[A-Za-z0-9_$]/.test(source[end] ?? '')) return '';
  let start = end;
  while (start >= 0 && /[A-Za-z0-9_$]/.test(source[start])) start -= 1;
  start += 1;
  if (!/[A-Za-z_$]/.test(source[start] ?? '')) return '';
  return source.slice(start, end + 1);
}

function prevNonSpace(source, index) {
  let cursor = index;
  while (cursor >= 0 && /\s/.test(source[cursor])) cursor -= 1;
  return cursor;
}

function matchBracket(source, openIndex) {
  const pairs = { '{': '}', '[': ']', '(': ')' };
  const open = source[openIndex];
  const close = pairs[open];
  let depth = 0;
  for (let index = openIndex; index < source.length; index += 1) {
    if (source[index] === open) depth += 1;
    else if (source[index] === close) {
      depth -= 1;
      if (depth === 0) return index;
    }
  }
  throw new Error('unbalanced pattern');
}

function matchParenBack(source, closeIndex) {
  let depth = 0;
  for (let index = closeIndex; index >= 0; index -= 1) {
    if (source[index] === ')') depth += 1;
    else if (source[index] === '(') {
      depth -= 1;
      if (depth === 0) return index;
    }
  }
  throw new Error('unbalanced parens');
}

function splitTop(text, separator) {
  const parts = [];
  let depth = 0;
  let start = 0;
  for (let index = 0; index < text.length; index += 1) {
    const current = text[index];
    if (current === '{' || current === '[' || current === '(') depth += 1;
    else if (current === '}' || current === ']' || current === ')') {
      depth -= 1;
    } else if (current === separator && depth === 0) {
      parts.push(text.slice(start, index));
      start = index + 1;
    }
  }
  parts.push(text.slice(start));
  return parts;
}

function topSeparator(text, separator) {
  let depth = 0;
  for (let index = 0; index < text.length; index += 1) {
    const current = text[index];
    if (current === '{' || current === '[' || current === '(') depth += 1;
    else if (current === '}' || current === ']' || current === ')') {
      depth -= 1;
    } else if (current === separator && depth === 0) return index;
  }
  return -1;
}

function patternNames(pattern) {
  const text = pattern.trim();
  if (text.startsWith('{')) return objectNames(text);
  if (text.startsWith('[')) return arrayNames(text);
  const match = /^(?:\.\.\.)?([A-Za-z_$][\w$]*)/.exec(text);
  return match ? [match[1]] : [];
}

function objectNames(pattern) {
  const names = [];
  for (const element of splitTop(pattern.trim().slice(1, -1), ',')) {
    const item = element.trim().replace(/^\.\.\./, '');
    if (item === '') continue;
    const colon = topSeparator(item, ':');
    if (colon === -1) {
      const ident = /^([A-Za-z_$][\w$]*)/.exec(item);
      if (ident) names.push(ident[1]);
      continue;
    }
    const right = item.slice(colon + 1).trim();
    const eq = topSeparator(right, '=');
    names.push(...patternNames(eq === -1 ? right : right.slice(0, eq)));
  }
  return names;
}

function arrayNames(pattern) {
  const names = [];
  for (const element of splitTop(pattern.trim().slice(1, -1), ',')) {
    if (element.trim() === '') continue;
    names.push(...patternNames(element));
  }
  return names;
}

function skipType(source, index) {
  let depth = 0;
  let cursor = index;
  while (cursor < source.length) {
    const current = source[cursor];
    if (
      current === '<' ||
      current === '{' ||
      current === '(' ||
      current === '['
    ) {
      depth += 1;
    } else if (
      current === '>' ||
      current === '}' ||
      current === ')' ||
      current === ']'
    ) {
      if (depth === 0) return cursor;
      depth -= 1;
    } else if (depth === 0 && current === '=' && source[cursor + 1] !== '>') {
      return cursor;
    } else if (
      depth === 0 &&
      (current === ',' || current === ';' || current === ')')
    ) {
      return cursor;
    }
    cursor += 1;
  }
  return cursor;
}

function skipInitializer(source, index) {
  let depth = 0;
  let cursor = index;
  while (cursor < source.length) {
    const current = source[cursor];
    if (current === '{' || current === '(' || current === '[') depth += 1;
    else if (current === '}' || current === ')' || current === ']') {
      if (depth === 0) return cursor;
      depth -= 1;
    } else if (depth === 0 && (current === ',' || current === ';')) {
      return cursor;
    }
    cursor += 1;
  }
  return cursor;
}

function readOneBinding(source, index) {
  const start = skipSpace(source, index);
  if (source[start] === '{' || source[start] === '[') {
    const endPattern = matchBracket(source, start);
    const names = patternNames(source.slice(start, endPattern + 1));
    let cursor = skipSpace(source, endPattern + 1);
    if (source[cursor] === ':') cursor = skipType(source, cursor + 1);
    if (source[cursor] === '=') cursor = skipInitializer(source, cursor + 1);
    return { names, end: cursor };
  }
  let cursor = start;
  if (source.startsWith('...', cursor)) cursor += 3;
  const ident = readIdent(source, cursor);
  cursor += ident.length;
  cursor = skipSpace(source, cursor);
  if (source[cursor] === '?') cursor = skipSpace(source, cursor + 1);
  if (source[cursor] === ':') cursor = skipType(source, cursor + 1);
  if (source[cursor] === '=') cursor = skipInitializer(source, cursor + 1);
  return { names: ident ? [ident] : [], end: cursor };
}

function namesInList(text) {
  const names = [];
  for (const part of splitTop(text, ',')) {
    if (part.trim() === '') continue;
    names.push(...readOneBinding(part, 0).names);
  }
  return names;
}

function collectDeclarators(source, index, names) {
  let cursor = index;
  while (cursor < source.length) {
    cursor = skipSpace(source, cursor);
    if (
      source[cursor] === ';' ||
      source[cursor] === ')' ||
      cursor >= source.length
    ) {
      return;
    }
    const binding = readOneBinding(source, cursor);
    names.push(...binding.names);
    cursor = skipSpace(source, binding.end);
    if (source[cursor] !== ',') return;
    cursor += 1;
  }
}

function collectFunctionParams(source, index, names) {
  let cursor = skipSpace(source, index);
  const ident = readIdent(source, cursor);
  if (ident) {
    const after = skipSpace(source, cursor + ident.length);
    if (source[after] === '(') cursor = after;
  }
  if (source[cursor] !== '(') return;
  const close = matchBracket(source, cursor);
  names.push(...namesInList(source.slice(cursor + 1, close)));
}

function arrowParamNames(source, arrowAt) {
  let cursor = arrowAt - 1;
  while (cursor >= 0 && /\s/.test(source[cursor])) cursor -= 1;
  if (cursor < 0) return [];
  if (source[cursor] === ')') {
    const open = matchParenBack(source, cursor);
    return namesInList(source.slice(open + 1, cursor));
  }
  const ident = readIdentBackward(source, cursor);
  if (ident) {
    const before = prevNonSpace(source, cursor - ident.length);
    if (source[before] !== ':') return [ident];
  }
  let depth = 0;
  for (let index = cursor; index >= 0; index -= 1) {
    const current = source[index];
    if (current === '>' || current === '}' || current === ']') depth += 1;
    else if (current === '<' || current === '{' || current === '[') {
      if (depth === 0) break;
      depth -= 1;
    } else if (current === ')' && depth === 0) {
      const open = matchParenBack(source, index);
      return namesInList(source.slice(open + 1, index));
    }
  }
  return [];
}

export function modeBinding(source) {
  const names = [];
  for (let index = 0; index < source.length; index += 1) {
    if (
      keywordAt(source, index, 'const') ||
      keywordAt(source, index, 'let') ||
      keywordAt(source, index, 'var')
    ) {
      const word = readIdent(source, index);
      collectDeclarators(source, index + word.length, names);
    } else if (keywordAt(source, index, 'function')) {
      collectFunctionParams(source, index + 'function'.length, names);
    } else if (keywordAt(source, index, 'catch')) {
      collectFunctionParams(source, index + 'catch'.length, names);
    } else if (source.startsWith('=>', index)) {
      names.push(...arrowParamNames(source, index));
    }
  }
  return names.find((name) => MODE_NAMES.has(name)) ?? '';
}
