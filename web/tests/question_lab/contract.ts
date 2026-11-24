/**
 * Cross-surface en/ar parity contract (S3-T21 box 8; decision 0044 item
 * 8(iv)). One contract for speech, cards, ranking explanations and layout:
 * every catalogue string present in both languages with the same keys, no
 * English text in the Arabic output, the same Fact-chip slots, and one
 * layout mirrored by logical properties, never a separate layout. Slice S3
 * executes it for cards and layout; S8-T10 calls speechParity and S6-T11
 * calls rankingParity with their own surface lines.
 */
import { JSDOM } from 'jsdom';
import { physicalAxis } from '../../scripts/check-answer.mjs';
import { LOOSE_NUMERAL } from './parity';
import { matchChip, type IsolateKind } from './chips';
import {
  readInlineStyle,
  readStylesheet,
  references,
  type Declaration,
} from './css';
import { formatFactValue } from '../../src/facts/formatters';
import { catalogue } from '../../src/brief/catalogue';
import enJson from '../../src/i18n/en.json' with { type: 'json' };
import arJson from '../../src/i18n/ar.json' with { type: 'json' };
import type { Language } from '../../src/i18n';

/** Catalogue collections that carry bilingual text fields. */
const COLLECTIONS = [
  ['fragment', catalogue.fragments],
  ['question', catalogue.questions],
  ['claim', catalogue.claims],
] as const;

type Collection = (typeof COLLECTIONS)[number][0];

/** The sanctioned identical bilingual values, pinned to their exact shipped
 * strings; every other i18n entry with en === ar — and any change to a
 * pinned value — is untranslated English-only source text. */
const IDENTICAL_BILINGUAL = new Map([
  ['i18n:drawer.title', 'Source chain'],
  ['i18n:stage.attribution', '© OpenStreetMap © Protomaps'],
  ['i18n:unit.percent', '%'],
]);

/** Translated attributes captured as keyed language slots. */
const TRANSLATED_ATTRIBUTES = ['aria-label', 'title', 'placeholder', 'value'];

/** One bilingual catalogue string: `i18n:key` or `kind:key#fieldStem`. */
export interface ParityEntry {
  key: string;
  en: string;
  ar: string;
  /** 'i18n' values may be sanctioned identical; catalogue kinds never may. */
  kind: 'i18n' | Collection;
}

/** A captured surface string with its resolved or declared key. */
export interface SurfaceString {
  key: string | null;
  text: string;
  /** True when the producer names the catalogue key itself. */
  declared: boolean;
  /** The translated attribute this slot came from, when not a text node. */
  attr?: string;
  /** Attribute slots are bound to `elementPath@attr`; moving one value to
   * another attribute or element is a different slot. */
  slotId?: string;
  /** Resolved attribute constituents in order: `keys` parts are required
   * catalogue values (each a set of alternative identities), `fact` parts
   * are the non-letter residual of an identified Fact slot. */
  parts?: AttrPart[];
  /** True only for a matched chip's accessible label that equals its
   * variant's exact template; the one place a numeral may sit in an
   * attribute. */
  templated?: boolean;
}

/** One constituent of a composite attribute value: either a required
 * catalogue value with its alternative identities, or a non-letter
 * residual carrying the associated Fact content. */
type AttrPart = { keys: string[] } | { fact: string };

/** One surface line for the speech and ranking entry points. */
export interface SurfaceLine {
  /** Catalogue key (`kind:key#stem` or `i18n:key`); omit to resolve the
   * key from the text. */
  key?: string | null;
  text: string;
  /** Fact-chip slots this line carries, in order. */
  factIds?: readonly string[];
}

/** The reference-chip kinds whose isolate text is bound to a record. */
export type ReferenceKind =
  'published_text' | 'calendar_date' | 'calendar_month' | 'calendar_year';

/** One trusted reference value from the fixture record, never from the
 * rendered surface. The n-th reference chip carrying `data-record=record`
 * binds to the n-th record of that id, in the order given. */
export interface ReferenceRecord {
  record: string;
  kind: ReferenceKind;
  value: string;
}

/** The normalized output of one surface in one language. */
export interface SurfaceCapture {
  /** True for a DOM capture, which must hold exactly one surface root;
   * typed-line captures (speech, ranking) carry none. */
  dom: boolean;
  /** Non-empty rendered strings in document order. */
  strings: SurfaceString[];
  /** Ordered Fact-chip slots as `lineIndex|variant:record:state:kind:size`;
   * the prefix is the index of the containing line's first string. */
  factSlots: string[];
  /** Ordered element signatures prefixed by their ancestor chain. */
  components: string[];
  /** Ordered [elementPath, tag, dir, lang, isolate] of direction-bearing
   * elements; the flag marks isolates of a matched reviewed chip variant. */
  directions: [string, string, string, string, boolean][];
  /** Every element matching a reviewed surface-root selector, with its
   * OWN `lang` and `dir`; a DOM capture must hold exactly one. */
  roots: { path: string; lang: string; dir: string }[];
  /** Each Fact chip's matched variant (null when none matches) and, for a
   * labelled variant, its actual and exactly required accessible label. */
  chips: {
    variant: string | null;
    label: string | null;
    expected: string | null;
  }[];
  /** Each exempt isolate's kind and text, in document order; `bound` when
   * the text equals its trusted reference record's expected text. */
  isolates: { kind: IsolateKind; text: string; bound: boolean }[];
  /** Each reference chip's isolate text with the exact text its trusted
   * record requires in this language (null when no record binds it). */
  references: { text: string; expected: string | null }[];
  /** Trusted reference records that no rendered chip consumed. */
  unrendered: number;
  /** The element path of each captured string's owner, in string order. */
  ownerPaths: string[];
  /** Inline style attribute values, in document order. */
  styles: string[];
}

function fieldsOf(item: unknown): readonly [string, string][] {
  if (!item || typeof item !== 'object') return [];
  const fields = (item as { fields?: unknown }).fields;
  if (!Array.isArray(fields)) return [];
  return fields.filter(
    (row): row is [string, string] =>
      Array.isArray(row) &&
      typeof row[0] === 'string' &&
      typeof row[1] === 'string',
  );
}

function keyOf(item: unknown): string {
  const key = (item as { key?: unknown } | null)?.key;
  return typeof key === 'string' ? key : '';
}

/** The contract's source: every string the application may render. */
export function catalogueSource(): ParityEntry[] {
  const enStrings: Record<string, string> = enJson.strings;
  const arStrings: Record<string, string> = arJson.strings;
  const entries: ParityEntry[] = [];
  const keys = new Set([...Object.keys(enStrings), ...Object.keys(arStrings)]);
  for (const key of keys)
    entries.push({
      key: `i18n:${key}`,
      en: enStrings[key] ?? '',
      ar: arStrings[key] ?? '',
      kind: 'i18n',
    });
  for (const [kind, items] of COLLECTIONS)
    for (const item of items as readonly unknown[]) {
      const stems = new Map<string, { en?: string; ar?: string }>();
      for (const [name, value] of fieldsOf(item)) {
        const stem =
          name.endsWith('_en') || name.endsWith('_ar')
            ? name.slice(0, -3)
            : name;
        const pair = stems.get(stem) ?? {};
        if (name.endsWith('_en')) pair.en = value;
        if (name.endsWith('_ar')) pair.ar = value;
        stems.set(stem, pair);
      }
      for (const [stem, pair] of stems)
        entries.push({
          key: `${kind}:${keyOf(item)}#${stem}`,
          en: pair.en ?? '',
          ar: pair.ar ?? '',
          kind,
        });
    }
  return entries;
}

type Side = 'en' | 'ar';

function textIndex(
  entries: readonly ParityEntry[],
  side: Side,
): Map<string, Set<string>> {
  const index = new Map<string, Set<string>>();
  for (const entry of entries) {
    const text = entry[side];
    if (!text) continue;
    const keys = index.get(text) ?? new Set<string>();
    keys.add(entry.key);
    index.set(text, keys);
  }
  return index;
}

function resolveKey(
  text: string,
  index: Map<string, Set<string>>,
): string | null {
  const keys = index.get(text);
  return keys ? [...keys].sort().join('|') : null;
}

interface Containment {
  hits: { value: string; keys: string[] }[];
  /** True when the text outside the matched values holds letters. */
  letters: boolean;
}

/** Longest-first catalogue substrings a composite attribute value carries;
 * the leftover may hold numerals and punctuation (fact content), never
 * letters. */
function contained(text: string, index: Map<string, Set<string>>): Containment {
  const hits: { value: string; keys: string[] }[] = [];
  let remainder = text;
  const values = [...index.keys()].sort((a, b) => b.length - a.length);
  for (const value of values) {
    if (value.length < 2 || !remainder.includes(value)) continue;
    hits.push({ value, keys: [...index.get(value)!] });
    remainder = remainder.split(value).join(' ');
  }
  return { hits, letters: /\p{L}/u.test(remainder) };
}

/** Locale separators are the only residual characters free to differ:
 * whitespace and the en/ar list and thousands marks drop out, and the
 * Arabic decimal mark folds to its Latin counterpart. Every other
 * character — digits, signs, unit symbols — is formatted Fact content
 * preserved verbatim. */
function normalizeResidual(text: string): string {
  return text.replace(/[\s,،٬]/gu, '').replaceAll('٫', '.');
}

/** The reviewed surface roots: a capture records the card's own root
 * element by this selector, never by ancestry. */
const SURFACE_ROOT = 'article.public-context-card[data-context-family]';

/** A translated attribute resolves exactly, or positionally as a composite:
 * every catalogue value found in order is a required constituent (each with
 * its own alternative identities), and each leftover run is a fact residual
 * that may hold numerals and punctuation, never letters. */
function resolveAttr(
  text: string,
  index: Map<string, Set<string>>,
): { key: string; parts: AttrPart[] } | null {
  const exact = index.get(text);
  if (exact !== undefined)
    return {
      key: [...exact].sort().join('|'),
      parts: [{ keys: [...exact].sort() }],
    };
  const values = [...index.keys()]
    .filter((value) => value.length >= 2)
    .sort((a, b) => b.length - a.length);
  const parts: AttrPart[] = [];
  let residual = '';
  let position = 0;
  while (position < text.length) {
    const hit = values.find((value) => text.startsWith(value, position));
    if (hit === undefined) {
      residual += text[position];
      position += 1;
    } else {
      if (residual !== '') {
        parts.push({ fact: residual });
        residual = '';
      }
      parts.push({ keys: [...index.get(hit)!].sort() });
      position += hit.length;
    }
  }
  if (residual !== '') parts.push({ fact: residual });
  if (parts.every((part) => 'fact' in part)) return null;
  if (parts.some((part) => 'fact' in part && /\p{L}/u.test(part.fact)))
    return null;
  return {
    key: [
      ...new Set(parts.flatMap((part) => ('keys' in part ? part.keys : []))),
    ]
      .sort()
      .join('|'),
    parts,
  };
}

const SKIP_ATTRIBUTES = new Set([
  'id',
  'for',
  'dir',
  'lang',
  'title',
  'placeholder',
  'value',
  'aria-controls',
  'aria-labelledby',
  'aria-describedby',
  'aria-details',
  'aria-activedescendant',
  'aria-owns',
  'aria-label',
]);

function signature(node: Element): string {
  const attrs = node
    .getAttributeNames()
    .filter((name) => !SKIP_ATTRIBUTES.has(name))
    .sort()
    .map((name) => `${name}=${node.getAttribute(name) ?? ''}`);
  return `${node.tagName.toLowerCase()}(${attrs.join(',')})`;
}

function elementIndex(node: Element): number {
  let index = 0;
  for (
    let sibling = node.previousElementSibling;
    sibling;
    sibling = sibling.previousElementSibling
  )
    index += 1;
  return index;
}

function slotIdentity(node: Element): string {
  return [
    node.getAttribute('data-fact-chip'),
    node.getAttribute('data-fact-id') ?? node.getAttribute('data-record'),
    node.getAttribute('data-state'),
    node.getAttribute('data-kind'),
    node.getAttribute('data-size'),
  ].join(':');
}

interface CaptureState {
  language: Language;
  labels: { open: string; loading: string };
  index: Map<string, Set<string>>;
  /** Isolate elements of matched chips; their text is fact content. */
  exempt: Set<Element>;
  /** Trusted reference records still to bind, per record id, in order. */
  pending: Map<string, ReferenceRecord[]>;
  references: SurfaceCapture['references'];
  roots: SurfaceCapture['roots'];
  chipRecords: SurfaceCapture['chips'];
  isolates: SurfaceCapture['isolates'];
  strings: SurfaceString[];
  owners: Element[];
  ownerPaths: string[];
  chips: { node: Element; slot: string }[];
  components: string[];
  directions: [string, string, string, string, boolean][];
  styles: string[];
}

function captureNode(
  node: Node,
  path: readonly string[],
  state: CaptureState,
): void {
  if (node.nodeType === 3) {
    // Only text inside an isolate of a matched chip variant is exempt.
    for (let el = node.parentElement; el; el = el.parentElement)
      if (state.exempt.has(el)) return;
    const text = node.textContent?.trim() ?? '';
    if (!text) return;
    state.strings.push({
      key: resolveKey(text, state.index),
      text,
      declared: false,
    });
    state.owners.push(node.parentElement as Element);
    state.ownerPaths.push(path.join('>'));
    return;
  }
  if (node.nodeType === 9 || node.nodeType === 11) {
    for (const child of node.childNodes) captureNode(child, path, state);
    return;
  }
  if (node.nodeType !== 1) return;
  const el = node as Element;
  const tag = el.tagName.toLowerCase();
  // The capture root's own position among siblings outside the surface is
  // not part of the surface.
  const own = [...path, path.length === 0 ? tag : `${tag}#${elementIndex(el)}`];
  state.components.push(
    `${path.length > 0 ? `${path.join('>')}>` : ''}${signature(el)}`,
  );
  let label: string | null = null;
  if (el.hasAttribute('data-fact-chip')) {
    const match = matchChip(el, state.language, state.labels);
    const reference = match?.variant.startsWith('reference:') === true;
    const expected = reference ? bindReference(el, state) : null;
    for (const [isolate, kind] of match?.isolates ?? []) {
      const text = isolate.textContent ?? '';
      state.exempt.add(isolate);
      state.isolates.push({ kind, text, bound: text === expected });
      if (reference) state.references.push({ text, expected });
    }
    label = match?.expectedLabel ?? null;
    state.chipRecords.push({
      variant: match?.variant ?? null,
      label: el.getAttribute('aria-label'),
      expected: label,
    });
  }
  const isolateElement = state.exempt.has(el);
  if (el.matches(SURFACE_ROOT))
    state.roots.push({
      path: own.join('>'),
      lang: el.getAttribute('lang') ?? '',
      dir: el.getAttribute('dir') ?? '',
    });
  if (el.hasAttribute('dir') || el.hasAttribute('lang'))
    state.directions.push([
      own.join('>'),
      tag,
      el.getAttribute('dir') ?? '',
      el.getAttribute('lang') ?? '',
      isolateElement,
    ]);
  const style = el.getAttribute('style');
  if (style !== null && style.trim() !== '') state.styles.push(style);
  for (const name of TRANSLATED_ATTRIBUTES) {
    const value = el.getAttribute(name);
    if (value === null || value === '') continue;
    const resolved = resolveAttr(value, state.index);
    state.strings.push({
      key: resolved?.key ?? null,
      text: value,
      declared: false,
      attr: name,
      slotId: `${own.join('>')}@${name}`,
      parts: resolved?.parts,
      templated: name === 'aria-label' && label !== null && value === label,
    });
    state.owners.push(el);
    state.ownerPaths.push(own.join('>'));
  }
  if (el.hasAttribute('data-fact-chip'))
    state.chips.push({ node: el, slot: slotIdentity(el) });
  for (const child of el.childNodes) captureNode(child, own, state);
}

/** The exact text the chip's next trusted record of its `data-record`
 * requires in this language: the record's kind must equal the chip's
 * `data-kind`, and its value must format; otherwise nothing binds. */
function bindReference(chip: Element, state: CaptureState): string | null {
  const queue = state.pending.get(chip.getAttribute('data-record') ?? '');
  const record = queue?.shift();
  if (record === undefined || record.kind !== chip.getAttribute('data-kind'))
    return null;
  const formatted = formatFactValue(
    record.value,
    record.kind,
    state.language,
    'reference',
  );
  return formatted.ok ? formatted.text : null;
}

/** Each Fact-chip slot keeps the index of its containing line's first
 * string, so a slot moved between catalogue lines still differs. */
function factLineSlots(state: CaptureState): string[] {
  const firstInside = new Map<Element, number>();
  state.owners.forEach((owner, index) => {
    for (
      let el: Element | null = owner;
      el && !firstInside.has(el);
      el = el.parentElement
    )
      firstInside.set(el, index);
  });
  return state.chips.map((chip) => {
    let line = -1;
    for (let el: Element | null = chip.node; el; el = el.parentElement) {
      const found = firstInside.get(el);
      if (found !== undefined) {
        line = found;
        break;
      }
    }
    return `${line}|${chip.slot}`;
  });
}

/** Normalize a rendered surface for the contract. */
export function domCapture(
  root: Element | Document | DocumentFragment,
  language: Language,
  trusted: readonly ReferenceRecord[],
  entries: readonly ParityEntry[] = catalogueSource(),
): SurfaceCapture {
  const pending = new Map<string, ReferenceRecord[]>();
  for (const record of trusted)
    pending.set(record.record, [...(pending.get(record.record) ?? []), record]);
  const catalogueValue = (key: string) =>
    entries.find((entry) => entry.key === key)?.[language] ?? '';
  const state: CaptureState = {
    language,
    labels: {
      open: catalogueValue('i18n:chip.open'),
      loading: catalogueValue('i18n:chip.loading'),
    },
    index: textIndex(entries, language),
    exempt: new Set(),
    pending,
    references: [],
    roots: [],
    chipRecords: [],
    isolates: [],
    strings: [],
    owners: [],
    ownerPaths: [],
    chips: [],
    components: [],
    directions: [],
    styles: [],
  };
  captureNode(root as unknown as Node, [], state);
  return {
    dom: true,
    strings: state.strings,
    factSlots: factLineSlots(state),
    components: state.components,
    directions: state.directions,
    roots: state.roots,
    chips: state.chipRecords,
    isolates: state.isolates,
    references: state.references,
    unrendered: [...pending.values()].reduce((sum, q) => sum + q.length, 0),
    ownerPaths: state.ownerPaths,
    styles: state.styles,
  };
}

/** Normalize typed surface lines for the contract. */
export function linesCapture(
  lines: readonly SurfaceLine[],
  language: Language,
  entries: readonly ParityEntry[] = catalogueSource(),
): SurfaceCapture {
  const index = textIndex(entries, language);
  return {
    dom: false,
    strings: lines.map((line) => ({
      key: line.key === undefined ? resolveKey(line.text, index) : line.key,
      text: line.text,
      declared: line.key !== undefined && line.key !== null,
    })),
    factSlots: lines.flatMap((line, lineIndex) =>
      (line.factIds ?? []).map((fact) => `${lineIndex}|${fact}`),
    ),
    components: [],
    directions: [],
    roots: [],
    chips: [],
    isolates: [],
    references: [],
    unrendered: 0,
    ownerPaths: [],
    styles: [],
  };
}

function guardMissingLanguage(
  entries: readonly ParityEntry[],
  problems: Set<string>,
): void {
  for (const entry of entries)
    if (!entry.en || !entry.ar) problems.add('missing-language');
}

function guardEnglishOnly(
  entries: readonly ParityEntry[],
  problems: Set<string>,
): void {
  for (const entry of entries)
    if (
      entry.en !== '' &&
      entry.en === entry.ar &&
      IDENTICAL_BILINGUAL.get(entry.key) !== entry.en
    )
      problems.add('english-only');
}

function guardDuplicateKeys(
  entries: readonly ParityEntry[],
  problems: Set<string>,
): void {
  const seen = new Set<string>();
  for (const entry of entries) {
    if (seen.has(entry.key)) problems.add('duplicate-key');
    seen.add(entry.key);
  }
}

/** Source-level contract: both languages present, no English-only string. */
export function sourceProblems(entries: readonly ParityEntry[]): string[] {
  const problems = new Set<string>();
  guardMissingLanguage(entries, problems);
  guardEnglishOnly(entries, problems);
  guardDuplicateKeys(entries, problems);
  return [...problems].sort();
}

function guardEnglishInArabic(
  ar: SurfaceCapture,
  enIndex: Map<string, Set<string>>,
  byKey: Map<string, ParityEntry>,
  problems: Set<string>,
): void {
  for (const slot of ar.strings) {
    if (slot.attr !== undefined) {
      for (const hit of contained(slot.text, enIndex).hits)
        for (const key of hit.keys) {
          const entry = byKey.get(key);
          if (entry && entry.ar !== hit.value)
            problems.add('english-in-arabic');
        }
      continue;
    }
    for (const key of enIndex.get(slot.text) ?? []) {
      const entry = byKey.get(key);
      if (entry && entry.ar !== slot.text) problems.add('english-in-arabic');
    }
  }
}

function guardDeclaredTemplates(
  en: SurfaceCapture,
  ar: SurfaceCapture,
  byKey: Map<string, ParityEntry>,
  problems: Set<string>,
): void {
  for (const [side, language] of [
    [en, 'en'],
    [ar, 'ar'],
  ] as const)
    for (const slot of side.strings) {
      if (!slot.declared || slot.key === null) continue;
      const entry = byKey.get(slot.key);
      if (!entry) problems.add('unknown-key');
      else if (entry[language] !== slot.text) problems.add('template-mismatch');
    }
}

interface KeyAlignment {
  enFree: string[][];
  arFree: string[][];
  enUnion: Set<string>;
  arUnion: Set<string>;
  enContains: Map<string, number>;
  arContains: Map<string, number>;
}

/** Pair keyed slots by order. Position pairs sharing a key are matched;
 * every other keyed slot is "free" and is checked against the other
 * surface's key union and per-key containment counts. A key that several
 * keys' texts share (a legitimately ambiguous resolution) never counts
 * unless it is the only interpretation of its slot. */
function alignKeys(en: SurfaceCapture, ar: SurfaceCapture): KeyAlignment {
  const enSlots = en.strings
    .filter((slot) => slot.key !== null)
    .map((slot) => slot.key!.split('|'));
  const arSlots = ar.strings
    .filter((slot) => slot.key !== null)
    .map((slot) => slot.key!.split('|'));
  const union = (slots: string[][]) => new Set(slots.flatMap((slot) => slot));
  const contains = (slots: string[][]) => {
    const counts = new Map<string, number>();
    for (const slot of slots)
      for (const key of new Set(slot))
        counts.set(key, (counts.get(key) ?? 0) + 1);
    return counts;
  };
  const shared = Math.min(enSlots.length, arSlots.length);
  const enFree: string[][] = [];
  const arFree: string[][] = [];
  for (let index = 0; index < shared; index += 1) {
    const left = enSlots[index]!;
    const right = arSlots[index]!;
    if (left.some((key) => right.includes(key))) continue;
    enFree.push(left);
    arFree.push(right);
  }
  enFree.push(...enSlots.slice(shared));
  arFree.push(...arSlots.slice(shared));
  return {
    enFree,
    arFree,
    enUnion: union(enSlots),
    arUnion: union(arSlots),
    enContains: contains(enSlots),
    arContains: contains(arSlots),
  };
}

/** A free slot is missing/extra when none of its keys appear on the other
 * surface, or when every shared interpretation is rendered more times on
 * this side than the other. Otherwise the slot corresponds to a key that
 * merely sits elsewhere — a reorder, handled by guardKeyOrder. */
function freeSlotProblems(
  free: readonly string[][],
  otherUnion: ReadonlySet<string>,
  ownContains: ReadonlyMap<string, number>,
  otherContains: ReadonlyMap<string, number>,
): { hasOrder: boolean; hasAbsent: boolean } {
  let hasOrder = false;
  let hasAbsent = false;
  for (const slot of free) {
    const hits = slot.filter((key) => otherUnion.has(key));
    const excess = hits.some(
      (key) => (ownContains.get(key) ?? 0) > (otherContains.get(key) ?? 0),
    );
    if (hits.length === 0 || excess) hasAbsent = true;
    else hasOrder = true;
  }
  return { hasOrder, hasAbsent };
}

function guardKeyParity(
  en: SurfaceCapture,
  ar: SurfaceCapture,
  problems: Set<string>,
): void {
  const aligned = alignKeys(en, ar);
  if (
    freeSlotProblems(
      aligned.enFree,
      aligned.arUnion,
      aligned.enContains,
      aligned.arContains,
    ).hasAbsent
  )
    problems.add('missing-key');
  if (
    freeSlotProblems(
      aligned.arFree,
      aligned.enUnion,
      aligned.arContains,
      aligned.enContains,
    ).hasAbsent
  )
    problems.add('extra-key');
}

function guardKeyOrder(
  en: SurfaceCapture,
  ar: SurfaceCapture,
  problems: Set<string>,
): void {
  const aligned = alignKeys(en, ar);
  const enSide = freeSlotProblems(
    aligned.enFree,
    aligned.arUnion,
    aligned.enContains,
    aligned.arContains,
  );
  const arSide = freeSlotProblems(
    aligned.arFree,
    aligned.enUnion,
    aligned.arContains,
    aligned.enContains,
  );
  if (enSide.hasOrder || arSide.hasOrder) problems.add('key-order');
}

/** Every rendered string must resolve to the catalogue; a numeral is
 * permitted only in a chip label that equals its variant's template. */
function guardStrings(
  en: SurfaceCapture,
  ar: SurfaceCapture,
  problems: Set<string>,
): void {
  for (const slot of [...en.strings, ...ar.strings]) {
    if (slot.key === null) problems.add('uncatalogued-text');
    if (LOOSE_NUMERAL.test(slot.text) && slot.templated !== true)
      problems.add('loose-numeral');
  }
}

/** Attribute slots are bound to `elementPath@attr`: the same resolved
 * content must sit in the same attribute on the same element. Composites
 * compare constituent-by-constituent — every catalogue part is required
 * (an alternatives set for that one string) and each residual carries its
 * fact numerals. */
function guardAttrSlots(
  en: SurfaceCapture,
  ar: SurfaceCapture,
  problems: Set<string>,
): void {
  const slotsOf = (capture: SurfaceCapture) => {
    const map = new Map<string, SurfaceString>();
    for (const slot of capture.strings)
      if (slot.attr !== undefined) map.set(slot.slotId!, slot);
    return map;
  };
  const equal = (left: SurfaceString, right: SurfaceString): boolean => {
    if (left.key === null || right.key === null) return left.key === right.key;
    const a = left.parts ?? [];
    const b = right.parts ?? [];
    if (a.length !== b.length) return false;
    return a.every((part, index) => {
      const other = b[index]!;
      if ('keys' in part && 'keys' in other)
        return part.keys.some((key) => other.keys.includes(key));
      if ('fact' in part && 'fact' in other)
        return normalizeResidual(part.fact) === normalizeResidual(other.fact);
      return false;
    });
  };
  const enSlots = slotsOf(en);
  const arSlots = slotsOf(ar);
  for (const [id, left] of enSlots) {
    const right = arSlots.get(id);
    if (right === undefined || !equal(left, right)) problems.add('attr-slot');
  }
  for (const id of arSlots.keys())
    if (!enSlots.has(id)) problems.add('attr-slot');
  // A matched chip's accessible label must equal its variant's template
  // exactly: value, units and action, each present once and in order.
  for (const chip of [...en.chips, ...ar.chips])
    if (chip.label !== chip.expected) problems.add('attr-slot');
}

function guardFactSlots(
  en: SurfaceCapture,
  ar: SurfaceCapture,
  problems: Set<string>,
): void {
  if (en.factSlots.join() !== ar.factSlots.join()) problems.add('fact-slot');
}

/** Every Fact chip must match a reviewed variant; an unmatched chip earns
 * no exemption and is itself refused. */
function guardChipVariants(
  en: SurfaceCapture,
  ar: SurfaceCapture,
  problems: Set<string>,
): void {
  for (const chip of [...en.chips, ...ar.chips])
    if (chip.variant === null) problems.add('chip-variant');
}

const LATIN = /\p{Script=Latin}/u;
const ARABIC = /\p{Script=Arabic}/u;

/** Isolate text is fact content, positively shaped by kind: a numeric
 * isolate holds a digit and no letter; numeric and opaque isolates carry
 * the same fact on both sides. An isolate not bound to its trusted record
 * is also checked for script (calendar) and for a multi-word catalogue
 * value; a bound isolate is authenticated by its record, so a legitimate
 * published value that collides with catalogue words still passes. */
function guardIsolates(
  en: SurfaceCapture,
  ar: SurfaceCapture,
  entries: readonly ParityEntry[],
  problems: Set<string>,
): void {
  // Whole multi-word catalogue values; a single word may be opaque data.
  const sentences = entries.flatMap((entry) =>
    [entry.en, entry.ar]
      .map((text) => text.trim())
      .filter((text) => /\s/u.test(text))
      .map((text) => ({ text, entry })),
  );
  for (const [capture, own, other] of [
    [en, 'en', ARABIC],
    [ar, 'ar', LATIN],
  ] as const)
    for (const { kind, text, bound } of capture.isolates) {
      const value = text.trim();
      if (
        kind === 'numeric' &&
        (!LOOSE_NUMERAL.test(value) || /\p{L}/u.test(value))
      )
        problems.add('isolate-content');
      if (bound) continue;
      if (kind === 'calendar' && other.test(value))
        problems.add(own === 'ar' ? 'english-in-arabic' : 'isolate-content');
      for (const { text: sentence, entry } of sentences) {
        if (!value.includes(sentence)) continue;
        problems.add('isolate-content');
        if (own === 'ar' && entry.en === sentence && entry.ar !== sentence)
          problems.add('english-in-arabic');
      }
    }
  const shared = (capture: SurfaceCapture) =>
    capture.isolates.map(({ kind, text }) =>
      kind === 'calendar' ? kind : `${kind}:${normalizeResidual(text)}`,
    );
  if (shared(en).join('\n') !== shared(ar).join('\n'))
    problems.add('fact-slot');
}

/** Every reference chip's isolate text must equal the exact text its
 * trusted record requires: an unbound chip is `reference-unbound`, an
 * empty isolate `isolate-content`, any other text `fact-slot`; a trusted
 * record no chip rendered is `reference-missing`. */
function guardReferences(
  en: SurfaceCapture,
  ar: SurfaceCapture,
  problems: Set<string>,
): void {
  for (const capture of [en, ar]) {
    for (const { text, expected } of capture.references)
      if (expected === null) problems.add('reference-unbound');
      else if (text.trim() === '') problems.add('isolate-content');
      else if (text !== expected) problems.add('fact-slot');
    if (capture.unrendered > 0) problems.add('reference-missing');
  }
}

function guardComponents(
  en: SurfaceCapture,
  ar: SurfaceCapture,
  problems: Set<string>,
): void {
  if (en.components.join() !== ar.components.join()) problems.add('component');
}

/** Direction values must mirror (`ltr`→`rtl`, `en`→`ar`); isolates of a
 * matched chip variant carry the pair their variant pins and are only
 * checked for position here. A DOM capture holds exactly one reviewed
 * surface root whose OWN `lang`/`dir` are `en`/`ltr` or `ar`/`rtl`; every
 * other direction entry and every captured string sits inside it. */
const MIRRORED_DIRECTIONS = new Set(['ltr>rtl', '>']);
const MIRRORED_LANGUAGES = new Set(['en>ar', '>']);

function rootProblems(
  capture: SurfaceCapture,
  dir: string,
  lang: string,
): boolean {
  if (capture.roots.length !== 1) return true;
  const root = capture.roots[0]!;
  const inside = (path: string) => path.startsWith(`${root.path}>`);
  return (
    root.dir !== dir ||
    root.lang !== lang ||
    !capture.directions.every(
      (entry) => entry[0] === root.path || inside(entry[0]),
    ) ||
    !capture.ownerPaths.every((owner) => owner === root.path || inside(owner))
  );
}

function guardDirection(
  en: SurfaceCapture,
  ar: SurfaceCapture,
  problems: Set<string>,
): void {
  // Typed-line captures carry no DOM surface and no root; a DOM capture
  // always needs exactly one, even when it holds no element at all.
  if (!en.dom && !ar.dom) return;
  if (rootProblems(en, 'ltr', 'en') || rootProblems(ar, 'rtl', 'ar'))
    problems.add('direction');
  if (en.directions.length !== ar.directions.length) problems.add('direction');
  const rootPath = en.roots[0]?.path;
  const shared = Math.min(en.directions.length, ar.directions.length);
  for (let index = 0; index < shared; index += 1) {
    const [enPath, enTag, enDir, enLang, enIsolate] = en.directions[index]!;
    const [arPath, arTag, arDir, arLang, arIsolate] = ar.directions[index]!;
    if (enPath !== arPath || enTag !== arTag || enIsolate !== arIsolate)
      problems.add('direction');
    if (enIsolate || enPath === rootPath) continue;
    if (!MIRRORED_DIRECTIONS.has(`${enDir}>${arDir}`))
      problems.add('direction');
    if (!MIRRORED_LANGUAGES.has(`${enLang}>${arLang}`))
      problems.add('direction');
  }
}

/** Inline layout declarations obey the same physical-axis rule as the
 * stylesheets a surface relies on; `layoutParity` also reads them into
 * the shared dependency graph. */
function guardInlineStyles(
  en: SurfaceCapture,
  ar: SurfaceCapture,
  problems: Set<string>,
): void {
  for (const css of [...en.styles, ...ar.styles])
    for (const problem of physicalAxis(css)) problems.add(problem);
}

/** The shared contract: en/ar parity of one surface's captured output. */
export function surfaceParity(
  en: SurfaceCapture,
  ar: SurfaceCapture,
  entries: readonly ParityEntry[] = catalogueSource(),
): string[] {
  const problems = new Set<string>();
  const byKey = new Map(entries.map((entry) => [entry.key, entry]));
  if (byKey.size !== entries.length) problems.add('duplicate-key');
  guardEnglishInArabic(ar, textIndex(entries, 'en'), byKey, problems);
  guardDeclaredTemplates(en, ar, byKey, problems);
  guardKeyParity(en, ar, problems);
  guardKeyOrder(en, ar, problems);
  guardStrings(en, ar, problems);
  guardAttrSlots(en, ar, problems);
  guardFactSlots(en, ar, problems);
  guardChipVariants(en, ar, problems);
  guardIsolates(en, ar, entries, problems);
  guardReferences(en, ar, problems);
  guardComponents(en, ar, problems);
  guardDirection(en, ar, problems);
  guardInlineStyles(en, ar, problems);
  return [...problems].sort();
}

/** A direction-conditioned selector is a separate layout, even when it is
 * written with logical properties. */
const SEPARATE_LAYOUT = /\[dir\b|\[lang\b|:dir\s*\(/i;

/** The exact reviewed typography tokens a `:lang` rule may redeclare. */
const SCRIPT_TYPOGRAPHY_TOKENS = new Set([
  '--eii-font-latin',
  '--eii-font-arabic',
  '--eii-type-display',
  '--eii-type-title',
  '--eii-type-body',
  '--eii-type-label',
  '--eii-type-caption',
  '--eii-type-tracking',
  '--eii-num-hero',
  '--eii-num-large',
  '--eii-num-standard',
  '--eii-num-compact',
]);

/** The reviewed letter-level properties a `:lang` rule may declare. */
const SCRIPT_TYPOGRAPHY_PROPERTIES = new Set([
  'font',
  'font-family',
  'font-size',
  'font-style',
  'font-weight',
  'font-stretch',
  'font-variant',
  'font-variant-caps',
  'font-kerning',
  'font-feature-settings',
  'font-variation-settings',
  'font-size-adjust',
  'font-synthesis',
  'letter-spacing',
  'word-spacing',
  'line-height',
  'text-decoration',
  'text-decoration-line',
  'text-decoration-style',
  'text-decoration-color',
  'text-decoration-thickness',
  'text-underline-offset',
  'text-underline-position',
  'quotes',
  'hyphens',
]);

/** An integer pixel length, the only context-independent form the shipped
 * root-paired tokens use: `--eii-brief-width` (`706px`, `448px`),
 * `--eii-focus-ring` (`4px`, `3px`) and `--eii-focus-offset` (`4px`,
 * `3px`). It computes to the same length on the root and on every element.
 * Any other value stays language-varied. */
const PAIRED_LITERAL = /^\d+px$/;

function pairedLiteral(value: string): boolean {
  return PAIRED_LITERAL.test(value.trim());
}

/** Custom properties whose every declaration is an integer pixel length,
 * all in bare `:root` rules followed by rules of one root scope that also
 * holds `:lang(...)` branches (see `Declaration.scope`). Such a token has
 * the same value at the root and at every element of those languages, so
 * its `:lang` branch varies nothing. */
function rootPaired(all: readonly Declaration[]): Set<string> {
  const paired = new Set<string>();
  const tokens = new Set(
    all.map((item) => item.property).filter((name) => name.startsWith('--')),
  );
  for (const token of tokens) {
    const items = all.filter((item) => item.property === token);
    const first = items.findIndex((item) => item.scope.includes(':lang('));
    if (first < 0) continue;
    const scope = items[first]!.scope;
    if (
      items.every(
        (item, index) =>
          pairedLiteral(item.value) &&
          (item.scope === scope || (item.scope === ':root' && index < first)),
      )
    )
      paired.add(token);
  }
  return paired;
}

/** Custom properties a `:lang` rule varies, closed transitively over the
 * custom-property dependency graph of every supplied stylesheet. */
function languageVaried(
  all: readonly Declaration[],
  paired: ReadonlySet<string>,
): Set<string> {
  const varied = new Set(
    all
      .filter(
        (item) =>
          item.lang &&
          item.property.startsWith('--') &&
          !paired.has(item.property),
      )
      .map((item) => item.property),
  );
  for (let grew = true; grew;) {
    grew = false;
    for (const item of all)
      if (
        item.property.startsWith('--') &&
        !varied.has(item.property) &&
        references(item.value).some((name) => varied.has(name))
      ) {
        varied.add(item.property);
        grew = true;
      }
  }
  return varied;
}

/** A `:lang` rule may declare only the reviewed typography tokens and
 * letter-level properties, and only a letter-level property may consume
 * a language-varied token, directly or through any alias chain. The graph
 * spans every supplied stylesheet and every captured inline `style`; CSS
 * the reader cannot fully read is refused with its closed code. */
function guardLogicalStyles(
  styles: readonly string[],
  inline: readonly string[],
  problems: Set<string>,
): void {
  const clean = styles.map((css) => css.replace(/\/\*[\s\S]*?\*\//g, ''));
  for (const css of clean) {
    for (const problem of physicalAxis(css)) problems.add(problem);
    if (SEPARATE_LAYOUT.test(css)) problems.add('separate-layout');
  }
  const readings = [
    ...styles.map(readStylesheet),
    ...inline.map(readInlineStyle),
  ];
  for (const reading of readings)
    for (const refusal of reading.refusals) problems.add(refusal);
  const all = readings.flatMap((reading) => reading.declarations);
  const typography = (property: string) =>
    property.startsWith('--')
      ? SCRIPT_TYPOGRAPHY_TOKENS.has(property)
      : SCRIPT_TYPOGRAPHY_PROPERTIES.has(property);
  const paired = rootPaired(all);
  for (const item of all)
    if (item.lang && !typography(item.property) && !paired.has(item.property))
      problems.add('separate-layout');
  const varied = languageVaried(all, paired);
  for (const item of all)
    if (
      !item.property.startsWith('--') &&
      !SCRIPT_TYPOGRAPHY_PROPERTIES.has(item.property) &&
      references(item.value).some((name) => varied.has(name))
    )
      problems.add('separate-layout');
}

type DomRoot = Element | Document | DocumentFragment;

/** Contract execution for the cards surface. `trusted` holds the fixture
 * record's reference values every reference chip must bind to. */
export function cardsParity(
  enRoot: DomRoot,
  arRoot: DomRoot,
  trusted: readonly ReferenceRecord[],
  entries: readonly ParityEntry[] = catalogueSource(),
): string[] {
  return surfaceParity(
    domCapture(enRoot, 'en', trusted, entries),
    domCapture(arRoot, 'ar', trusted, entries),
    entries,
  );
}

/** Contract execution for the layout surface: the same components and slots
 * in both languages, mirrored by logical properties, never a separate
 * layout. `styles` are the stylesheets the surface relies on; the captured
 * inline styles join them in one dependency graph. */
export function layoutParity(
  enRoot: DomRoot,
  arRoot: DomRoot,
  trusted: readonly ReferenceRecord[],
  styles: readonly string[],
  entries: readonly ParityEntry[] = catalogueSource(),
): string[] {
  const en = domCapture(enRoot, 'en', trusted, entries);
  const ar = domCapture(arRoot, 'ar', trusted, entries);
  const problems = new Set(surfaceParity(en, ar, entries));
  guardLogicalStyles(styles, [...en.styles, ...ar.styles], problems);
  return [...problems].sort();
}

/** The lab capture path's parity check: the stored en/ar card markup
 * parsed through JSDOM and run through the shared contract, exactly as
 * `answers.spec.ts` records it as `parity_problems` per capture. */
export function capturedCardsParity(
  enHtml: string,
  arHtml: string,
  trusted: readonly ReferenceRecord[],
  styles: readonly string[],
  entries: readonly ParityEntry[] = catalogueSource(),
): string[] {
  const enDoc = new JSDOM(enHtml).window.document;
  const arDoc = new JSDOM(arHtml).window.document;
  return [
    ...new Set([
      ...cardsParity(enDoc, arDoc, trusted, entries),
      ...layoutParity(enDoc, arDoc, trusted, styles, entries),
    ]),
  ].sort();
}

/** One lab capture state's record step: the en card stores its markup for
 * pairing; the ar card pairs against it and runs the shared contract. */
interface CaptureStep {
  pairedCards: Map<string, string>;
  pairKey: string;
  language: Language;
  cardHtml: string | null;
  trusted: readonly ReferenceRecord[];
  styles: readonly string[];
  fields: Record<string, unknown>;
}

/** The `parity_problems` diagnostic of one step; an en step records
 * nothing. An ar step with no card fails closed whether or not its pair
 * was stored: no card-less state is declared in the lab's cases
 * (`evals/question_lab/cases.v1.json`), so every state must show a card
 * in both languages, and the pair's presence only decides whether the
 * missing pair is reported beside the missing card. */
function parityCapture(
  step: CaptureStep,
): { parity_problems: string[] } | null {
  const { pairedCards, pairKey, cardHtml } = step;
  if (step.language === 'en') {
    if (cardHtml !== null) pairedCards.set(pairKey, cardHtml);
    return null;
  }
  if (cardHtml === null)
    return {
      parity_problems: pairedCards.has(pairKey)
        ? ['parity:card-missing']
        : ['parity:card-missing', 'parity:pair-missing'],
    };
  const enHtml = pairedCards.get(pairKey);
  if (enHtml === undefined) return { parity_problems: ['parity:pair-missing'] };
  return {
    parity_problems: capturedCardsParity(
      enHtml,
      cardHtml,
      step.trusted,
      step.styles,
    ),
  };
}

/** The capture's failure enforcement: a recorded parity problem fails
 * the spec, naming every recorded code. */
function enforceParity(record: { parity_problems: string[] } | null): void {
  if (record !== null && record.parity_problems.length > 0)
    throw new Error(`parity_problems: ${record.parity_problems.join(', ')}`);
}

/** One lab capture state's shared record step: pair or compare the card,
 * write the capture JSON with its `parity_problems` diagnostic through
 * `sink`, then fail on any recorded problem. */
export function recordCapture(
  step: CaptureStep,
  sink: (json: string) => void,
): void {
  const record = parityCapture(step);
  sink(
    JSON.stringify(
      {
        ...step.fields,
        ...(record === null ? {} : { parity_problems: record.parity_problems }),
      },
      null,
      2,
    ) + '\n',
  );
  enforceParity(record);
}

/** One lab question as the capture matrix reads it. */
export interface LabCase {
  identity: string;
  refusal: string | null;
}

/** One registered test of the matrix: its coordinates and the capture
 * step the driver calls at each state. */
export interface LabRun<C extends LabCase> {
  question: C;
  width: number;
  height: number;
  language: Language;
  theme: string;
  stem: string;
  capture: (state: string) => Promise<void>;
}

/** What one state's snapshot hands to the record step. */
export interface LabShot {
  cardHtml: string | null;
  trusted: readonly ReferenceRecord[];
  fields: Record<string, unknown>;
}

/** The injected dependencies of the browser capture matrix. */
export interface LabMatrix<C extends LabCase, F> {
  cases: readonly C[];
  sizes: readonly (readonly [number, number])[];
  themes: readonly string[];
  styles: readonly string[];
  /** Registers one test (Playwright's `test` in the browser spec). */
  register: (title: string, body: (fixtures: F) => Promise<void>) => void;
  /** Drives one test, calling `run.capture` at each state in order. */
  drive: (fixtures: F, run: LabRun<C>) => Promise<void>;
  /** The current state's report, screenshot and card markup. */
  snapshot: (fixtures: F, run: LabRun<C>, state: string) => Promise<LabShot>;
  /** Writes one capture JSON under its file name. */
  sink: (name: string, json: string) => void;
  /** The visual comparison after a state is recorded. */
  compare: (fixtures: F, name: string) => Promise<void>;
}

/** The capture states every test must record, in order. */
function requiredStates(question: LabCase): string[] {
  return [
    'answer',
    'comparison',
    'evidence',
    'drawer',
    ...(question.refusal ? ['refusal'] : []),
  ];
}

/** The browser capture matrix, the only caller of `recordCapture` in the
 * lab spec: one test per question, size, language and theme. Each state's
 * record runs in both languages; its rejection propagates; and a test
 * whose driver skipped a state or absorbed a failed record fails with
 * `capture_states`. */
export function registerLabCaptures<C extends LabCase, F>(
  matrix: LabMatrix<C, F>,
): void {
  const pairedCards = new Map<string, string>();
  for (const question of matrix.cases)
    for (const [width, height] of matrix.sizes)
      for (const language of ['en', 'ar'] as const)
        for (const theme of matrix.themes) {
          const size = `${width}x${height}`;
          const stem = `${question.identity}-${size}-${language}-${theme}`;
          const pairStem = `${question.identity}-${size}-${theme}`;
          matrix.register(
            `${question.identity} ${size} ${language} ${theme}`,
            async (fixtures) => {
              const recorded: string[] = [];
              const run: LabRun<C> = {
                question,
                width,
                height,
                language,
                theme,
                stem,
                capture: async (state) => {
                  const shot = await matrix.snapshot(fixtures, run, state);
                  recordCapture(
                    {
                      pairedCards,
                      pairKey: `${pairStem}-${state}`,
                      language,
                      cardHtml: shot.cardHtml,
                      trusted: shot.trusted,
                      styles: matrix.styles,
                      fields: shot.fields,
                    },
                    (json) => matrix.sink(`${stem}-${state}.json`, json),
                  );
                  recorded.push(state);
                  await matrix.compare(fixtures, `${stem}-${state}.png`);
                },
              };
              await matrix.drive(fixtures, run);
              const required = requiredStates(question);
              if (recorded.join() !== required.join())
                throw new Error(`capture_states: ${recorded.join(',')}`);
            },
          );
        }
}

/** S8-T10 entry point: spoken lines in both languages, one call. */
export function speechParity(
  enLines: readonly SurfaceLine[],
  arLines: readonly SurfaceLine[],
  entries: readonly ParityEntry[] = catalogueSource(),
): string[] {
  return surfaceParity(
    linesCapture(enLines, 'en', entries),
    linesCapture(arLines, 'ar', entries),
    entries,
  );
}

/** S6-T11 entry point: ranking-explanation lines, one call. */
export function rankingParity(
  enLines: readonly SurfaceLine[],
  arLines: readonly SurfaceLine[],
  entries: readonly ParityEntry[] = catalogueSource(),
): string[] {
  return surfaceParity(
    linesCapture(enLines, 'en', entries),
    linesCapture(arLines, 'ar', entries),
    entries,
  );
}
