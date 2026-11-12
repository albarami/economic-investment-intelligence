const REFERENCE_PREFIX = '///';

function lineBreak(text, index) {
  return text[index] === '\n';
}

export function tokenize(text) {
  const tokens = [];
  let index = 0;
  let line = 1;
  const length = text.length;

  function bump(count) {
    for (let step = 0; step < count; step += 1) {
      if (text[index + step] === '\n') line += 1;
    }
    index += count;
  }

  function skipLineComment(start) {
    let cursor = start + 2;
    while (cursor < length && text[cursor] !== '\n') cursor += 1;
    if (text.startsWith(REFERENCE_PREFIX, start)) {
      const body = text.slice(start + REFERENCE_PREFIX.length, cursor);
      const match = /^\s*<reference\s+(path|types)\s*=\s*(['"])([\s\S]*?)\2/.exec(body);
      if (match) {
        tokens.push({ type: 'reference', value: match[3], kind: match[1], line });
      }
    }
    index = cursor;
  }

  function skipBlockComment() {
    index += 2;
    while (index < length && !(text[index] === '*' && text[index + 1] === '/')) {
      if (lineBreak(text, index)) line += 1;
      index += 1;
    }
    if (index < length) index += 2;
  }

  function readString(quote) {
    const startLine = line;
    index += 1;
    let value = '';
    while (index < length && text[index] !== '\n' && text[index] !== quote) {
      if (text[index] === '\\' && index + 1 < length) {
        value += text[index] + text[index + 1];
        if (text[index + 1] === '\n') line += 1;
        index += 2;
        continue;
      }
      value += text[index];
      index += 1;
    }
    if (index < length && text[index] === quote) index += 1;
    return { type: 'string', value, line: startLine };
  }

  function skipString(quote) {
    index += 1;
    while (index < length && text[index] !== '\n' && text[index] !== quote) {
      if (text[index] === '\\' && index + 1 < length) {
        if (text[index + 1] === '\n') line += 1;
        index += 2;
        continue;
      }
      index += 1;
    }
    if (index < length && text[index] === quote) index += 1;
  }

  function skipCode() {
    let depth = 0;
    while (index < length) {
      const current = text[index];
      if (current === '\n') {
        line += 1;
        index += 1;
        continue;
      }
      if (current === '/' && text[index + 1] === '/') {
        while (index < length && text[index] !== '\n') index += 1;
        continue;
      }
      if (current === '/' && text[index + 1] === '*') {
        skipBlockComment();
        continue;
      }
      if (current === "'" || current === '"') {
        skipString(current);
        continue;
      }
      if (current === '`') {
        skipTemplate();
        continue;
      }
      if (current === '{') {
        depth += 1;
        index += 1;
        continue;
      }
      if (current === '}') {
        if (depth === 0) {
          index += 1;
          return;
        }
        depth -= 1;
        index += 1;
        continue;
      }
      index += 1;
    }
  }

  function skipTemplate() {
    index += 1;
    while (index < length) {
      if (text[index] === '\\' && index + 1 < length) {
        if (text[index + 1] === '\n') line += 1;
        index += 2;
        continue;
      }
      if (text[index] === '`') {
        index += 1;
        return;
      }
      if (text[index] === '$' && text[index + 1] === '{') {
        index += 2;
        skipCode();
        continue;
      }
      if (text[index] === '\n') line += 1;
      index += 1;
    }
  }

  function readTemplate() {
    const startLine = line;
    index += 1;
    let value = '';
    let hasSubstitution = false;
    while (index < length) {
      if (text[index] === '\\' && index + 1 < length) {
        value += text[index] + text[index + 1];
        if (text[index + 1] === '\n') line += 1;
        index += 2;
        continue;
      }
      if (text[index] === '`') {
        index += 1;
        return { type: 'template', value, hasSubstitution, line: startLine };
      }
      if (text[index] === '$' && text[index + 1] === '{') {
        hasSubstitution = true;
        value += '${';
        index += 2;
        const before = index;
        skipCode();
        value += text.slice(before, index);
        continue;
      }
      if (text[index] === '\n') line += 1;
      value += text[index];
      index += 1;
    }
    return { type: 'template', value, hasSubstitution, line: startLine };
  }

  while (index < length) {
    const current = text[index];
    if (current === '\n') {
      line += 1;
      index += 1;
      continue;
    }
    if (current === ' ' || current === '\t' || current === '\r' || current === '\f') {
      index += 1;
      continue;
    }
    if (current === '/' && text[index + 1] === '/') {
      skipLineComment(index);
      continue;
    }
    if (current === '/' && text[index + 1] === '*') {
      skipBlockComment();
      continue;
    }
    if (current === "'" || current === '"') {
      tokens.push(readString(current));
      continue;
    }
    if (current === '`') {
      tokens.push(readTemplate());
      continue;
    }
    if (/[A-Za-z0-9_$]/.test(current)) {
      const startLine = line;
      const start = index;
      while (index < length && /[A-Za-z0-9_$]/.test(text[index])) index += 1;
      tokens.push({ type: 'word', value: text.slice(start, index), line: startLine });
      continue;
    }
    tokens.push({ type: 'punct', value: current, line });
    bump(1);
  }
  return tokens;
}

function isLiteral(token) {
  if (!token) return false;
  if (token.type === 'string') return true;
  return token.type === 'template' && token.hasSubstitution === false;
}

function at(tokens, index) {
  return tokens[index];
}

export function collectReferences(text) {
  const tokens = tokenize(text);
  const references = [];
  const nonLiteral = [];
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (token.type === 'reference') {
      references.push({
        form: token.kind === 'path' ? 'reference-path' : 'reference-types',
        specifier: token.value,
        line: token.line,
      });
      continue;
    }
    if (token.type !== 'word') continue;
    if (token.value === 'from' && isLiteral(at(tokens, index + 1))) {
      const next = tokens[index + 1];
      references.push({ form: 'from', specifier: next.value, line: next.line });
      continue;
    }
    if (token.value === 'import' && at(tokens, index + 1)?.value === '.') {
      const sequence = ['meta', '.', 'glob', '('];
      const matched = sequence.every((part, offset) => at(tokens, index + 2 + offset)?.value === part);
      if (matched) {
        const arg = at(tokens, index + 6);
        if (isLiteral(arg)) {
          references.push({ form: 'glob', specifier: arg.value, line: arg.line });
        } else if (arg && arg.value === '[') {
          let depth = 1;
          for (let cursor = index + 7; cursor < tokens.length; cursor += 1) {
            const item = tokens[cursor];
            if (item.value === '[') depth += 1;
            else if (item.value === ']') {
              depth -= 1;
              if (depth === 0) break;
            } else if (isLiteral(item)) {
              references.push({ form: 'glob', specifier: item.value, line: item.line });
            }
          }
        }
      }
      continue;
    }
    if (token.value === 'import' && at(tokens, index + 1)?.value === '(') {
      const arg = at(tokens, index + 2);
      if (isLiteral(arg)) references.push({ form: 'import()', specifier: arg.value, line: arg.line });
      else nonLiteral.push({ form: 'import()', line: token.line });
      continue;
    }
    if (token.value === 'import' && isLiteral(at(tokens, index + 1))) {
      const next = tokens[index + 1];
      references.push({ form: 'import', specifier: next.value, line: next.line });
      continue;
    }
    if (token.value === 'require' && at(tokens, index + 1)?.value === '(') {
      const arg = at(tokens, index + 2);
      if (isLiteral(arg)) references.push({ form: 'require()', specifier: arg.value, line: arg.line });
      else nonLiteral.push({ form: 'require()', line: token.line });
      continue;
    }
    if (
      token.value === 'new' &&
      at(tokens, index + 1)?.value === 'URL' &&
      at(tokens, index + 2)?.value === '('
    ) {
      const arg = at(tokens, index + 3);
      if (isLiteral(arg)) references.push({ form: 'new URL()', specifier: arg.value, line: arg.line });
      else if (arg && arg.type === 'template' && arg.hasSubstitution) {
        nonLiteral.push({ form: 'new URL()', line: token.line });
      }
    }
  }
  return { references, nonLiteral };
}
