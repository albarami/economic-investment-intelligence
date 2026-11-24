/**
 * The fail-closed CSS reader of the en/ar parity contract (S3-T21 box 8).
 * It reads only the forms it fully understands and refuses the rest with a
 * closed code, never skipping a declaration it cannot read:
 * - `css-escape`: any backslash outside a comment;
 * - `css-non-ascii`: any non-ASCII character outside a comment or string;
 * - `css-unsupported`: any at-rule other than `@media` and `@keyframes`, a
 *   selector outside the reviewed grammar, a malformed declaration, an
 *   unterminated comment or string, or unbalanced brackets.
 * Custom-property names keep their case (they are case-sensitive in CSS);
 * other property names fold to lower case.
 */

export type CssRefusal = 'css-escape' | 'css-non-ascii' | 'css-unsupported';

export interface Declaration {
  property: string;
  value: string;
  /** True when any enclosing rule's selector holds `:lang(...)`. */
  lang: boolean;
  /** The sorted branches of a top-level rule (inside `@media` blocks only)
   * whose list is a bare `:root` plus bare `:lang(...)` branches, for
   * example `:lang(en),:root`; `:root` alone; otherwise empty. */
  scope: string;
}

export interface CssReading {
  declarations: Declaration[];
  refusals: Set<CssRefusal>;
}

/** Comments become a space and string contents become empty quotes, so the
 * structure scan never meets a bracket or separator inside either. */
function strip(css: string, refusals: Set<CssRefusal>): string {
  let out = '';
  let at = 0;
  while (at < css.length) {
    const char = css[at]!;
    if (css.startsWith('/*', at)) {
      const end = css.indexOf('*/', at + 2);
      if (end < 0) {
        refusals.add('css-unsupported');
        return out;
      }
      out += ' ';
      at = end + 2;
    } else if (char === '"' || char === "'") {
      let end = at + 1;
      while (end < css.length && css[end] !== char && css[end] !== '\n') {
        if (css[end] === '\\') refusals.add('css-escape');
        end += 1;
      }
      if (css[end] !== char) {
        refusals.add('css-unsupported');
        return out;
      }
      out += char + char;
      at = end + 1;
    } else {
      if (char === '\\') refusals.add('css-escape');
      else if (char.charCodeAt(0) > 0x7f) refusals.add('css-non-ascii');
      out += char;
      at += 1;
    }
  }
  return out;
}

const IDENT = /^-?[A-Za-z_][A-Za-z0-9_-]*/;
const PSEUDO_CLASSES = new Set([
  'focus-visible',
  'focus',
  'hover',
  'disabled',
  'root',
]);

/** A reviewed selector list: compounds of `*`, type, `.class`, `#id`,
 * `[attr]`/`[attr=value]` and the pseudo-classes above, `:has()`, `:not()`
 * and `:lang()`, joined by descendant, `>`, `+` or `~` combinators.
 * Pseudo-elements and every other form are refused. */
function selectorList(text: string, relative = false): boolean {
  let at = 0;
  const space = () => {
    while (/\s/.test(text[at] ?? '')) at += 1;
  };
  const ident = (): boolean => {
    const match = IDENT.exec(text.slice(at));
    if (match === null) return false;
    at += match[0].length;
    return true;
  };
  const argument = (inner: (arg: string) => boolean): boolean => {
    if (text[at] !== '(') return false;
    let depth = 0;
    const start = at + 1;
    for (; at < text.length; at += 1) {
      if (text[at] === '(') depth += 1;
      if (text[at] === ')') depth -= 1;
      if (depth === 0) break;
    }
    if (text[at] !== ')') return false;
    const ok = inner(text.slice(start, at));
    at += 1;
    return ok;
  };
  const simple = (): boolean => {
    const char = text[at];
    if (char === '*') {
      at += 1;
      return true;
    }
    if (char === '.' || char === '#') {
      at += 1;
      return ident();
    }
    if (char === '[') {
      const match =
        /^\[\s*-?[A-Za-z_][A-Za-z0-9_-]*\s*(=\s*(''|""|-?[A-Za-z_][A-Za-z0-9_-]*)\s*)?\]/.exec(
          text.slice(at),
        );
      if (match === null) return false;
      at += match[0].length;
      return true;
    }
    if (char === ':') {
      at += 1;
      const start = at;
      if (!ident()) return false;
      const name = text.slice(start, at).toLowerCase();
      // A following `(` is refused by the combinator check of `complex`.
      if (PSEUDO_CLASSES.has(name)) return true;
      if (name === 'has') return argument((arg) => selectorList(arg, true));
      if (name === 'not') return argument((arg) => selectorList(arg));
      if (name === 'lang')
        return argument((arg) => /^\s*([A-Za-z-]+|''|"")\s*$/.test(arg));
      return false;
    }
    return ident();
  };
  const compound = (): boolean => {
    if (!simple()) return false;
    while (at < text.length && /[*.#[:]/.test(text[at]!))
      if (!simple()) return false;
    return true;
  };
  const complex = (): boolean => {
    space();
    if (relative && /[>+~]/.test(text[at] ?? '')) {
      at += 1;
      space();
    }
    if (!compound()) return false;
    for (;;) {
      const before = at;
      space();
      if (at >= text.length || text[at] === ',') return true;
      if (/[>+~]/.test(text[at]!)) {
        at += 1;
        space();
      } else if (at === before) return false;
      if (!compound()) return false;
    }
  };
  for (;;) {
    if (!complex()) return false;
    if (at >= text.length) return true;
    at += 1; // the comma
  }
}

const MEDIA_PRELUDE = /^@media\s+[A-Za-z0-9\s():.,-]+$/;
const KEYFRAMES_PRELUDE = /^@keyframes\s+-?[A-Za-z_][A-Za-z0-9_-]*$/;
const KEYFRAME_SELECTOR =
  /^\s*(from|to|\d+(\.\d+)?%)(\s*,\s*(from|to|\d+(\.\d+)?%))*\s*$/;
const DECLARATION =
  /^\s*(--[A-Za-z0-9_-]+|-?[A-Za-z][A-Za-z0-9-]*)\s*:([\s\S]*)$/;

type Frame = {
  kind: 'sheet' | 'inline' | 'media' | 'keyframes' | 'frame' | 'rule';
  lang: boolean;
  /** True for the sheet and for `@media` blocks not inside a rule. */
  top: boolean;
  scope: string;
};

const ROOT_BRANCH = /^:root$|^:lang\(\s*[a-z-]+\s*\)$/;

/** The root scope of a top-level rule's selector list, or empty. */
function rootScope(text: string): string {
  const branches = [
    ...new Set(
      text
        .toLowerCase()
        .split(',')
        .map((part) => part.trim()),
    ),
  ].sort();
  return branches.includes(':root') &&
    branches.every((part) => ROOT_BRANCH.test(part))
    ? branches.join(',')
    : '';
}

/** Open a block for `prelude` inside `parent`, or refuse its form. */
function open(
  prelude: string,
  parent: Frame,
  refusals: Set<CssRefusal>,
): Frame {
  const text = prelude.trim();
  const inRules = ['sheet', 'media', 'rule'].includes(parent.kind);
  const inner = { lang: parent.lang, top: false, scope: '' };
  if (parent.kind === 'keyframes') {
    if (!KEYFRAME_SELECTOR.test(text)) refusals.add('css-unsupported');
    return { ...inner, kind: 'frame' };
  }
  if (text.startsWith('@')) {
    if (inRules && MEDIA_PRELUDE.test(text))
      return { ...inner, kind: 'media', top: parent.top };
    if (inRules && parent.kind !== 'rule' && KEYFRAMES_PRELUDE.test(text))
      return { ...inner, kind: 'keyframes' };
    refusals.add('css-unsupported');
    return { ...inner, kind: 'rule' };
  }
  if (!inRules || text === '' || !selectorList(text))
    refusals.add('css-unsupported');
  return {
    kind: 'rule',
    lang: parent.lang || /:lang\s*\(/i.test(text),
    top: false,
    scope: parent.top ? rootScope(text) : '',
  };
}

/** Record the declaration `chunk` in `frame`, or refuse its form. */
function declare(
  chunk: string,
  frame: Frame,
  found: Declaration[],
  refusals: Set<CssRefusal>,
): void {
  if (chunk.trim() === '') return;
  const match = DECLARATION.exec(chunk);
  if (match === null || !['inline', 'frame', 'rule'].includes(frame.kind)) {
    refusals.add('css-unsupported');
    return;
  }
  const name = match[1]!;
  found.push({
    property: name.startsWith('--') ? name : name.toLowerCase(),
    value: match[2]!,
    lang: frame.lang,
    scope: frame.scope,
  });
}

function read(css: string, root: Frame): CssReading {
  const refusals = new Set<CssRefusal>();
  const text = strip(css, refusals) + (root.kind === 'inline' ? ';' : '');
  const declarations: Declaration[] = [];
  const stack: Frame[] = [root];
  let depth = 0;
  let start = 0;
  for (let at = 0; at < text.length; at += 1) {
    const char = text[at]!;
    if (char === '(') depth += 1;
    if (char === ')') depth -= 1;
    if (!'{};'.includes(char)) continue;
    if (depth !== 0) refusals.add('css-unsupported');
    const chunk = text.slice(start, at);
    start = at + 1;
    const frame = stack.at(-1)!;
    if (char === '{') {
      stack.push(open(chunk, frame, refusals));
      continue;
    }
    declare(chunk, frame, declarations, refusals);
    if (char === '}') {
      if (stack.length === 1) refusals.add('css-unsupported');
      else stack.pop();
    }
  }
  if (stack.length !== 1 || depth !== 0 || text.slice(start).trim() !== '')
    refusals.add('css-unsupported');
  return { declarations, refusals };
}

/** Every declaration of a stylesheet at any nesting depth. */
export function readStylesheet(css: string): CssReading {
  return read(css, { kind: 'sheet', lang: false, top: true, scope: '' });
}

/** The declarations of one inline `style` attribute. */
export function readInlineStyle(css: string): CssReading {
  return read(css, { kind: 'inline', lang: false, top: false, scope: '' });
}

/** Every custom property a value references, fallbacks included; names
 * keep their case, string contents were already emptied. */
export function references(value: string): string[] {
  return [...value.matchAll(/var\(\s*(--[A-Za-z0-9_-]+)/gi)].map(
    (use) => use[1]!,
  );
}
