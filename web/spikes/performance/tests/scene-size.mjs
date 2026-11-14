import { modeBinding } from './scene-size-bindings.mjs';
import {
  ALIASES,
  FULL_SITES,
  FULL_TOKENS,
  LATE_SIZE,
  SMALL_SITES,
} from './scene-size-sites.mjs';

const CALL_NAMES = ['prepareCanvas', 'sharedRoadScene', 'open', 'test'];

export function stripComments(source, dropStrings = false) {
  let out = '';
  let index = 0;
  let quote = '';
  while (index < source.length) {
    const current = source[index];
    const next = source[index + 1];
    if (quote) {
      if (dropStrings) {
        if (current === '\\') {
          index += 2;
          continue;
        }
        if (current === '\n') out += '\n';
        if (current === quote) {
          quote = '';
          out += current;
        }
        index += 1;
        continue;
      }
      out += current;
      if (current === '\\') {
        out += source[index + 1] ?? '';
        index += 2;
        continue;
      }
      if (current === quote) quote = '';
      index += 1;
      continue;
    }
    if (current === "'" || current === '"' || current === '`') {
      quote = current;
      out += current;
      index += 1;
      continue;
    }
    if (current === '/' && next === '/') {
      out += ' ';
      index += 2;
      while (index < source.length && source[index] !== '\n') index += 1;
      continue;
    }
    if (current === '/' && next === '*') {
      out += ' ';
      index += 2;
      while (
        index < source.length &&
        !(source[index] === '*' && source[index + 1] === '/')
      ) {
        if (source[index] === '\n') out += '\n';
        index += 1;
      }
      index += 2;
      continue;
    }
    out += current;
    index += 1;
  }
  return out;
}

function readConst(source, name, seen = new Set()) {
  if (seen.has(name)) throw new Error(`canvas constant cycles: ${name}`);
  seen.add(name);
  const match = source.match(
    new RegExp(`export const ${name} = ([A-Z_]+|'[^']*');`),
  );
  if (!match) throw new Error(`missing canvas constant ${name}`);
  const value = match[1];
  if (value.startsWith("'")) return value.slice(1, -1);
  return readConst(source, value, seen);
}

export function assertModesDistinct(source) {
  const stripped = stripComments(source);
  const full = readConst(stripped, 'FULL');
  const small = readConst(stripped, 'SMALL');
  if (full === small) throw new Error('FULL and SMALL must differ');
  for (const name of ALIASES) {
    if (readConst(stripped, name) !== full) {
      throw new Error(`${name} must be the full canvas`);
    }
  }
}

export function assertShrinksOnlyForSmall(source) {
  const stripped = stripComments(source);
  const guard = 'if (canvas !== SMALL) return;';
  const guardAt = stripped.indexOf(guard);
  const shrinkAt = stripped.indexOf('replaceAll(WALL_WIDTH');
  const imported = stripped.includes("from './canvas-mode.mjs'");
  if (
    !imported ||
    guardAt === -1 ||
    shrinkAt === -1 ||
    shrinkAt < guardAt ||
    stripped.indexOf('replaceAll(WALL_WIDTH', shrinkAt + 1) !== -1
  ) {
    throw new Error('small map must shrink only for SMALL');
  }
}

function compact(value) {
  return value.replaceAll(/\s+/g, '');
}

function isCallSite(source, index) {
  if (index > 0 && /[A-Za-z0-9_$]/.test(source[index - 1])) return false;
  return !source.slice(0, index).trimEnd().endsWith('function');
}

function matchName(source, index) {
  for (const name of ['test.describe', ...CALL_NAMES]) {
    if (!source.startsWith(name, index)) continue;
    const gap = /^\s*\(/.exec(source.slice(index + name.length));
    if (!gap || !isCallSite(source, index)) continue;
    return { name, paren: index + name.length + gap[0].length - 1 };
  }
  return null;
}

function skipString(source, index) {
  const quote = source[index];
  let cursor = index + 1;
  while (cursor < source.length) {
    if (source[cursor] === '\\') {
      cursor += 2;
      continue;
    }
    if (source[cursor] === quote) return cursor + 1;
    cursor += 1;
  }
  return cursor;
}

function pushPart(source, parts, spans, start, end) {
  const raw = source.slice(start, end);
  const text = raw.trim();
  if (text === '') return;
  const leading = raw.length - raw.trimStart().length;
  const trailing = raw.length - raw.trimEnd().length;
  parts.push(text);
  spans.push({ start: start + leading, end: end - trailing });
}

function splitArgs(source, openParen) {
  const parts = [];
  const spans = [];
  let start = openParen + 1;
  let index = openParen + 1;
  let depth = 1;
  let quote = '';
  while (index < source.length && depth > 0) {
    const current = source[index];
    if (quote) {
      if (current === '\\') {
        index += 2;
        continue;
      }
      if (current === quote) quote = '';
      index += 1;
      continue;
    }
    if (current === "'" || current === '"' || current === '`') {
      quote = current;
      index += 1;
      continue;
    }
    if (current === '(' || current === '{' || current === '[') {
      depth += 1;
      index += 1;
      continue;
    }
    if (current === ')' || current === '}' || current === ']') {
      depth -= 1;
      if (depth === 0) {
        pushPart(source, parts, spans, start, index);
        break;
      }
      index += 1;
      continue;
    }
    if (current === ',' && depth === 1) {
      pushPart(source, parts, spans, start, index);
      index += 1;
      start = index;
      continue;
    }
    index += 1;
  }
  return { parts, spans, end: index + 1 };
}

function matchBrace(source, openIndex) {
  let depth = 0;
  let quote = '';
  for (let index = openIndex; index < source.length; index += 1) {
    const current = source[index];
    if (quote) {
      if (current === '\\') {
        index += 1;
        continue;
      }
      if (current === quote) quote = '';
      continue;
    }
    if (current === "'" || current === '"' || current === '`') {
      quote = current;
      continue;
    }
    if (current === '{') depth += 1;
    else if (current === '}') {
      depth -= 1;
      if (depth === 0) return index;
    }
  }
  throw new Error('unbalanced braces');
}

function callbackBody(source, parenIndex) {
  const parsed = splitArgs(source, parenIndex);
  const span = parsed.spans[parsed.spans.length - 1];
  if (!span) return null;
  const region = source.slice(span.start, span.end);
  const arrow = region.indexOf('=>');
  const braceRel = region.indexOf('{', arrow === -1 ? 0 : arrow);
  if (braceRel === -1) return null;
  const start = span.start + braceRel;
  return { start, end: matchBrace(source, start) };
}

function parseCalls(source) {
  const calls = [];
  const tests = [];
  let index = 0;
  while (index < source.length) {
    const current = source[index];
    if (current === "'" || current === '"' || current === '`') {
      index = skipString(source, index);
      continue;
    }
    const found = matchName(source, index);
    if (!found) {
      index += 1;
      continue;
    }
    if (found.name === 'test' || found.name === 'test.describe') {
      const body = callbackBody(source, found.paren);
      if (body) tests.push({ ...body, title: titleOf(source, found.paren) });
      // Keep scanning the body so a canvas call inside the test is found.
      index = found.paren + 1;
      continue;
    }
    const parsed = splitArgs(source, found.paren);
    calls.push({
      name: found.name,
      args: parsed.parts,
      spans: parsed.spans,
      start: index,
      paren: found.paren,
      end: parsed.end,
    });
    index = parsed.end;
  }
  return { calls, tests };
}

function pathOf(call) {
  if (call.name === 'prepareCanvas') return '';
  if (call.name === 'sharedRoadScene') {
    const raw = (call.args[0] ?? '').trim();
    if (
      (raw.startsWith("'") && raw.endsWith("'")) ||
      (raw.startsWith('"') && raw.endsWith('"'))
    ) {
      return raw.slice(1, -1);
    }
    return compact(raw);
  }
  return compact(call.args[1] ?? '');
}

function canvasOf(call) {
  if (call.name === 'open' && call.args.length < 3) return 'FULL';
  const arg = call.name === 'open' ? 2 : 1;
  return compact(call.args[arg] ?? '');
}

function siteKey(call) {
  return `${call.name}|${canvasOf(call)}|${pathOf(call)}|${call.title ?? ''}`;
}

function titleOf(source, paren) {
  const raw = (splitArgs(source, paren).parts[0] ?? '').trim();
  if (
    (raw.startsWith("'") && raw.endsWith("'")) ||
    (raw.startsWith('"') && raw.endsWith('"'))
  ) {
    return raw.slice(1, -1);
  }
  return compact(raw);
}

function enclosingTitle(blocks, position) {
  let best = null;
  for (const block of blocks) {
    if (position > block.start && position < block.end) {
      if (!best || block.end - block.start < best.end - best.start) {
        best = block;
      }
    }
  }
  return best?.title ?? '';
}

function titledCalls(source) {
  const parsed = parseCalls(source);
  for (const call of parsed.calls) {
    call.title = enclosingTitle(parsed.tests, call.start);
  }
  return parsed;
}

function assertCanvasImport(source) {
  const marked = source
    .replaceAll("from './canvas-mode.mjs'", 'from CANVAS_MODE_MODULE')
    .replaceAll('from "./canvas-mode.mjs"', 'from CANVAS_MODE_MODULE');
  const bare = stripComments(marked, true);
  const pattern = /import\s*\{([^}]*)\}\s*from\s*CANVAS_MODE_MODULE/g;
  if ([...bare.matchAll(pattern)].some((match) => /\bas\b/.test(match[1]))) {
    throw new Error('canvas import alias');
  }
}

function assertSmallMapImport(source) {
  const stripped = stripComments(source);
  const exact = "import { SMALL } from './canvas-mode.mjs';";
  const pattern = /import\s*\{([^}]*)\}\s*from\s*(['"])\.\/canvas-mode\.mjs\2/g;
  const found = [...stripped.matchAll(pattern)];
  if (
    !stripped.includes(exact) ||
    found.some((match) => /\bas\b/.test(match[1]))
  ) {
    throw new Error('small-map import');
  }
}

function assertOpenDefault(source) {
  const start = source.indexOf('async function open');
  if (start < 0) throw new Error('open defaults to FULL');
  const parsed = splitArgs(source, source.indexOf('(', start));
  if (compact(parsed.parts[2] ?? '') !== 'canvas:string=FULL') {
    throw new Error('open defaults to FULL');
  }
}

function assertNoSmallBesideFull(scenes, blocks) {
  let offender = null;
  for (const block of blocks) {
    const inside = scenes.filter(
      (call) => call.start > block.start && call.start < block.end,
    );
    const smallPrepare = inside.some(
      (call) => call.name === 'prepareCanvas' && canvasOf(call) === 'SMALL',
    );
    const fullCall = inside.some((call) => FULL_TOKENS.has(canvasOf(call)));
    if (!smallPrepare || !fullCall) continue;
    if (!offender || block.end - block.start < offender.end - offender.start) {
      offender = block;
    }
  }
  if (offender) {
    throw new Error(`small canvas beside a full mode: ${offender.title}`);
  }
}

function isHelperForward(source, call) {
  if (canvasOf(call) !== 'canvas') return false;
  const head = source.slice(0, call.start);
  const helperAt = Math.max(
    head.lastIndexOf('async function open'),
    head.lastIndexOf('function sharedRoadScene'),
  );
  if (helperAt < 0) return false;
  const brace = source.indexOf('{', helperAt);
  const end = matchBrace(source, brace);
  return call.start > brace && call.start < end;
}

function sceneCalls(source, calls) {
  const scenes = [];
  for (const call of calls) {
    if (isHelperForward(source, call)) continue;
    const token = canvasOf(call);
    if (!FULL_TOKENS.has(token) && token !== 'SMALL') {
      throw new Error(`unknown canvas ${token}`);
    }
    scenes.push(call);
  }
  return scenes;
}

function enclosingTest(tests, position) {
  let best = null;
  for (const body of tests) {
    if (position > body.start && position < body.end) {
      if (!best || body.end - body.start < best.end - best.start) best = body;
    }
  }
  return best;
}

function assertListed(found) {
  const listed = [...FULL_SITES, ...SMALL_SITES];
  for (const entry of listed) {
    const count = found.filter((key) => key === entry.key).length;
    if (count !== 1) throw new Error(`${entry.missing}: ${entry.label}`);
  }
  for (const key of found) {
    if (!listed.some((entry) => entry.key === key)) {
      throw new Error(`unexpected canvas call: ${key}`);
    }
  }
}

function assertLateSizeReadsFrom(source, scenes, tests) {
  for (const call of scenes) {
    if (FULL_TOKENS.has(canvasOf(call))) continue;
    const body =
      call.name === 'sharedRoadScene'
        ? callbackBody(source, call.paren)
        : enclosingTest(tests, call.start);
    if (!body)
      throw new Error(`canvas call is outside a test: ${siteKey(call)}`);
    const text = source.slice(body.start, body.end);
    for (const [needle, label] of LATE_SIZE) {
      if (text.includes(needle)) throw new Error(`small canvas reads ${label}`);
    }
  }
}

export function assertLateSizeReads(specSource) {
  const source = stripComments(specSource);
  const { calls, tests } = parseCalls(source);
  assertLateSizeReadsFrom(source, sceneCalls(source, calls), tests);
}

export function assertSceneSizes(specSource, modesSource, smallMapSource) {
  assertModesDistinct(modesSource);
  assertShrinksOnlyForSmall(smallMapSource);
  assertSmallMapImport(smallMapSource);
  const source = stripComments(specSource);
  assertCanvasImport(source);
  const bound = modeBinding(stripComments(specSource, true));
  if (bound) throw new Error(`canvas mode binding: ${bound}`);
  assertOpenDefault(source);
  const parsed = titledCalls(source);
  const scenes = sceneCalls(source, parsed.calls);
  assertNoSmallBesideFull(scenes, parsed.tests);
  assertListed(scenes.map(siteKey));
  assertLateSizeReadsFrom(source, scenes, parsed.tests);
}

export function shrinkSite(source, key) {
  const stripped = stripComments(source);
  const { calls } = titledCalls(stripped);
  const call = calls.find(
    (item) => !isHelperForward(stripped, item) && siteKey(item) === key,
  );
  if (!call) throw new Error(`missing canvas call ${key}`);
  if (call.name === 'open' && call.args.length < 3) {
    return (
      stripped.slice(0, call.end - 1) + ', SMALL' + stripped.slice(call.end - 1)
    );
  }
  const span = call.spans[call.name === 'open' ? 2 : 1];
  return `${stripped.slice(0, span.start)}SMALL${stripped.slice(span.end)}`;
}
