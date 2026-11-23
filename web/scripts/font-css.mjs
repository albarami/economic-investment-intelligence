/*
 * Finds every active @font-face rule and font import in a stylesheet by
 * parsing it with css-tree, a CSS-parser implementation with spec error
 * recovery: comments are skipped, at-keywords match case-insensitively,
 * rule and declaration boundaries are respected, and CSS input
 * preprocessing holds, so a CRLF terminates a hexadecimal escape as one
 * whitespace. A rule that CSS deactivates (fully commented out, or an
 * at-keyword without its block) is never reported. css-tree keeps the raw
 * spelling of names (at-rule names, declaration properties, identifiers),
 * so each name is decoded here; and every Raw node it leaves — content it
 * could not structure, though a real browser may still apply it, such as
 * an escape-spelled url( written u\72l( — is handed to the hand tokenizer
 * of font-css-tokens.mjs, kept only as this cross-check (ruling L-1531).
 */
import { parse as parseCss, walk } from 'css-tree';
import {
  decodeEscape,
  parseFontCss as parseFontCssTokens,
  urlsInRaw,
} from './font-css-tokens.mjs';

export function preprocessCss(text) {
  // CSS input preprocessing: CR, LF, CRLF and FF each become one newline,
  // so a CRLF terminates a hexadecimal escape as one whitespace and every
  // downstream offset counts the same line breaks a browser would.
  return text.replace(/\r\n/g, '\n').replace(/[\r\f]/g, '\n');
}

export function decodeCssName(name) {
  // Decode the escapes of one raw CSS name the way the shared decodeEscape
  // helper does: \ followed by up to six hex digits consumes one following
  // whitespace; any other escaped character stands for itself. Names reach
  // here from text already run through preprocessCss, so a source CRLF
  // arrives as one LF and is consumed as one terminator.
  let value = '';
  let index = 0;
  while (index < name.length) {
    if (name[index] !== '\\') {
      value += name[index];
      index += 1;
      continue;
    }
    const decoded = decodeEscape(name, index);
    value += decoded.value;
    index = decoded.next;
  }
  return value;
}

function offsetOf(node) {
  return node.loc?.start.offset ?? 0;
}

function familyOf(value) {
  // A font-family value is a string or a run of identifiers joined by
  // spaces; only its first alternative matters to the delivery test.
  let first = null;
  const names = [];
  value?.children?.forEach((child) => {
    if (first === null) first = child;
    if (child.type === 'Identifier') names.push(decodeCssName(child.name));
  });
  if (first?.type === 'String') return first.value;
  return names.join(' ');
}

function rawUrls(node) {
  const urls = [];
  for (const url of urlsInRaw(node.value)) {
    urls.push({ value: url.value, index: offsetOf(node) + url.index });
  }
  return urls;
}

function functionUrl(node, text) {
  // An escape-spelled url( such as u\72l( reaches css-tree as an unknown
  // function, but a browser decodes the name at tokenization and reads a
  // URL token; its argument is the raw text between the parentheses.
  if (decodeCssName(node.name).toLowerCase() !== 'url') return null;
  if (!node.loc) return null;
  const open = text.indexOf('(', node.loc.start.offset);
  const close = node.loc.end.offset - 1;
  if (open === -1 || open >= close || text[close] !== ')') return null;
  const argument = text.slice(open + 1, close).trim();
  const quoted =
    argument.length > 1 &&
    (argument[0] === '"' || argument[0] === "'") &&
    argument[argument.length - 1] === argument[0];
  return {
    value: quoted ? argument.slice(1, -1) : argument,
    index: node.loc.start.offset,
  };
}

function urlsUnder(node, text) {
  const urls = [];
  walk(node, (inner) => {
    if (inner.type === 'Url')
      urls.push({ value: inner.value, index: offsetOf(inner) });
    else if (inner.type === 'Raw') urls.push(...rawUrls(inner));
    else if (inner.type === 'Function') {
      const url = functionUrl(inner, text);
      if (url) urls.push(url);
    }
  });
  urls.sort((left, right) => left.index - right.index);
  return urls;
}

function readFace(node, text) {
  const face = { family: '', urls: [], index: offsetOf(node) };
  node.block?.children?.forEach((child) => {
    if (child.type !== 'Declaration') return;
    const property = decodeCssName(child.property).toLowerCase();
    if (property === 'font-family') face.family = familyOf(child.value);
    if (property === 'src') face.urls.push(...urlsUnder(child.value, text));
  });
  face.urls.sort((left, right) => left.index - right.index);
  return face;
}

function readImport(node, text) {
  let target = null;
  if (node.prelude) {
    walk(node.prelude, (inner) => {
      if (inner.type === 'Raw') {
        for (const url of rawUrls(inner)) {
          if (!target) target = url;
        }
        return;
      }
      if (!target && inner.type === 'Function') {
        target = functionUrl(inner, text);
        return;
      }
      if (!target && (inner.type === 'Url' || inner.type === 'String')) {
        target = { value: inner.value, index: offsetOf(inner) };
      }
    });
  }
  return target;
}

function mergeInto(list, parsed, base) {
  for (const face of parsed.faces) {
    list.faces.push({
      ...face,
      index: face.index + base,
      urls: face.urls.map((url) => ({ ...url, index: url.index + base })),
    });
  }
  for (const ref of parsed.imports) {
    list.imports.push({ ...ref, index: ref.index + base });
  }
}

export function parseFontCss(text) {
  const source = preprocessCss(text);
  const ast = parseCss(source, { positions: true });
  const list = { faces: [], imports: [] };
  const rawNodes = [];
  walk(ast, (node) => {
    if (node.type === 'Raw') {
      rawNodes.push(node);
      return;
    }
    if (node.type !== 'Atrule') return;
    const name = decodeCssName(node.name).toLowerCase();
    if (name === 'font-face') list.faces.push(readFace(node, source));
    else if (name === 'import') {
      const target = readImport(node, source);
      if (target) list.imports.push(target);
    }
  });
  // The cross-check: the hand tokenizer reads every Raw text for at-rules
  // css-tree could not structure, so a smuggled @font-face or @import
  // inside raw content is still reported.
  for (const node of rawNodes) {
    mergeInto(list, parseFontCssTokens(node.value), offsetOf(node));
  }
  list.faces.sort((left, right) => left.index - right.index);
  list.imports.sort((left, right) => left.index - right.index);
  return list;
}
