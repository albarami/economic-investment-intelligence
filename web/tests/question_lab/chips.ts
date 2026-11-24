/**
 * The reviewed Fact-chip variants of the en/ar parity contract (S3-T21 box
 * 8). A chip earns isolate exemptions only when its whole subtree matches
 * one variant below exactly: tag, exact attribute names (with pinned values
 * where given), child order and count, and where non-whitespace text may
 * sit. A class name, a `dir` or an ancestor never grants an exemption, and
 * an isolate holds fact text only, never unit or action content. Shapes
 * mirror `src/facts/FactChip.tsx`.
 */
import type { Language } from '../../src/i18n';

/** numeric: formatted value, `ltr`/`en`; opaque: published text,
 * `auto`/`en`; calendar: formatted date, `auto`/surface language. */
export type IsolateKind = 'numeric' | 'opaque' | 'calendar';

/** How the chip's accessible label is built from its own constituents. */
type LabelRule = 'value' | 'word' | 'open' | 'loading' | null;

interface Shape {
  tag: string;
  /** Exact attribute names; a list pins the allowed values. */
  attrs: Record<string, readonly string[] | null>;
  children?: readonly Shape[];
  optional?: boolean;
  /** Non-whitespace text may sit directly in this element. */
  text?: boolean;
  isolate?: IsolateKind;
  /** Label constituent role of this element's text. */
  role?: 'value' | 'unit';
}

interface Variant {
  name: string;
  shape: Shape;
  label: LabelRule;
}

const CLASS = (value: string) => ({ class: [value] });
const UNIT: Shape = { tag: 'span', attrs: CLASS('chip-unit'), text: true };
const isolate = (kind: IsolateKind, extra: Partial<Shape> = {}): Shape => ({
  tag: 'bdi',
  attrs: { class: ['chip-num'], dir: null, lang: null },
  isolate: kind,
  ...extra,
});
const BOUND = (name: string): Shape => ({
  tag: 'span',
  attrs: { 'data-bound': [name] },
  text: true,
});

const READY_BODY: Shape = {
  tag: 'bdi',
  attrs: CLASS('chip-root'),
  children: [
    {
      tag: 'span',
      attrs: CLASS('chip-figure'),
      children: [
        isolate('numeric', { role: 'value' }),
        { ...UNIT, role: 'unit', optional: true },
        { ...UNIT, role: 'unit', optional: true },
      ],
    },
    {
      tag: 'span',
      attrs: CLASS('chip-range'),
      optional: true,
      children: [
        UNIT,
        isolate('numeric', { children: [BOUND('low'), BOUND('high')] }),
      ],
    },
  ],
};

const STATE_BODIES: readonly [readonly string[], Shape, LabelRule][] = [
  [['ready'], READY_BODY, 'value'],
  [['refused', 'no_data', 'error'], { ...UNIT, role: 'unit' }, 'word'],
  [['withheld'], { tag: 'span', attrs: CLASS('chip-withheld') }, 'open'],
  [
    ['loading'],
    { tag: 'span', attrs: { class: ['chip-skeleton'], 'aria-label': null } },
    'loading',
  ],
];

const VALUE_ATTRS = {
  class: ['chip'],
  'data-fact-chip': ['value', 'compact'],
  'data-fact-id': null,
  'data-size': null,
};

const REFERENCE_ATTRS = {
  class: ['chip'],
  'data-fact-chip': ['reference'],
  'data-state': ['ready'],
  'data-record': null,
};

/** The closed table of reviewed chip variants. */
const VARIANTS: readonly Variant[] = [
  ...STATE_BODIES.flatMap(([states, body, label]): Variant[] => [
    {
      name: `value-button:${states[0]}`,
      shape: {
        tag: 'button',
        attrs: {
          ...VALUE_ATTRS,
          type: ['button'],
          'data-state': states,
          'aria-label': null,
        },
        children: [body],
      },
      label,
    },
    {
      name: `value-figure:${states[0]}`,
      shape: {
        tag: 'span',
        attrs: {
          ...VALUE_ATTRS,
          'data-state': states,
          'data-figure': ['true'],
        },
        children: [body],
      },
      label: null,
    },
  ]),
  {
    name: 'reference:published_text',
    shape: {
      tag: 'span',
      attrs: { ...REFERENCE_ATTRS, 'data-kind': ['published_text'] },
      children: [isolate('opaque')],
    },
    label: null,
  },
  {
    name: 'reference:calendar',
    shape: {
      tag: 'span',
      attrs: {
        ...REFERENCE_ATTRS,
        'data-kind': ['calendar_date', 'calendar_month', 'calendar_year'],
      },
      children: [isolate('calendar')],
    },
    label: null,
  },
  {
    name: 'reference:error',
    shape: {
      tag: 'span',
      attrs: {
        class: ['chip'],
        'data-fact-chip': ['reference'],
        'data-kind': null,
        'data-state': ['error'],
      },
      children: [UNIT],
    },
    label: null,
  },
  ...[
    ['ready', [isolate('numeric'), UNIT]],
    ['error', [UNIT]],
  ].map(([state, body]): Variant => ({
    name: `input-preset:${String(state)}`,
    shape: {
      tag: 'span',
      attrs: {
        class: ['chip chip-input'],
        'data-fact-chip': ['input'],
        'data-kind': ['preset'],
        'data-record': null,
        'data-state': [state as string],
      },
      children: [
        { tag: 'span', attrs: CLASS('chip-tag'), text: true },
        ...(body as Shape[]),
      ],
    },
    label: null,
  })),
];

/** The isolate `dir`/`lang` pair each kind must carry. */
function isolatePair(kind: IsolateKind, language: Language): [string, string] {
  if (kind === 'numeric') return ['ltr', 'en'];
  if (kind === 'opaque') return ['auto', 'en'];
  return ['auto', language];
}

interface Found {
  isolates: [Element, IsolateKind][];
  values: string[];
  units: string[];
}

function ownAttributesMatch(el: Element, shape: Shape): boolean {
  const names = el.getAttributeNames();
  if (names.length !== Object.keys(shape.attrs).length) return false;
  return names.every((name) => {
    if (!Object.hasOwn(shape.attrs, name)) return false;
    const allowed = shape.attrs[name];
    return allowed === null || allowed!.includes(el.getAttribute(name)!);
  });
}

/** The constituents of `el` when its whole subtree matches `shape`. */
function matchShape(
  el: Element,
  shape: Shape,
  language: Language,
): Found | null {
  if (el.tagName.toLowerCase() !== shape.tag) return null;
  if (!ownAttributesMatch(el, shape)) return null;
  if (shape.isolate !== undefined) {
    const [dir, lang] = isolatePair(shape.isolate, language);
    if (el.getAttribute('dir') !== dir || el.getAttribute('lang') !== lang)
      return null;
  }
  const elements: Element[] = [];
  for (const child of el.childNodes) {
    if (child.nodeType === 1) elements.push(child as Element);
    else if (child.nodeType !== 3) return null;
    else if (child.textContent!.trim() !== '' && !shape.text && !shape.isolate)
      return null;
  }
  const found: Found = { isolates: [], values: [], units: [] };
  let next = 0;
  for (const childShape of shape.children ?? []) {
    const child = elements[next];
    const inner =
      child === undefined ? null : matchShape(child, childShape, language);
    if (inner === null) {
      if (childShape.optional) continue;
      return null;
    }
    found.isolates.push(...inner.isolates);
    found.values.push(...inner.values);
    found.units.push(...inner.units);
    next += 1;
  }
  if (next !== elements.length) return null;
  if (shape.isolate !== undefined) found.isolates.unshift([el, shape.isolate]);
  if (shape.role === 'value') found.values.push(el.textContent ?? '');
  if (shape.role === 'unit') found.units.push(el.textContent ?? '');
  return found;
}

/** A chip matched to one reviewed variant. */
export interface ChipMatch {
  variant: string;
  isolates: [Element, IsolateKind][];
  /** The exact accessible label the variant's template requires, or null
   * when the variant carries no label. */
  expectedLabel: string | null;
}

/** `open`/`loading` are the surface language's `chip.open` and
 * `chip.loading` catalogue values. */
export function matchChip(
  chip: Element,
  language: Language,
  strings: { open: string; loading: string },
): ChipMatch | null {
  for (const variant of VARIANTS) {
    const found = matchShape(chip, variant.shape, language);
    if (found === null) continue;
    return {
      variant: variant.name,
      isolates: found.isolates,
      expectedLabel: expectedLabel(variant.label, found, language, strings),
    };
  }
  return null;
}

/** The label template of `FactChip.readyBody`: the formatted value, each
 * unit word in order, then the open action after the language's
 * separator. Presence, order and count are fixed by exact equality. */
function expectedLabel(
  rule: LabelRule,
  found: Found,
  language: Language,
  strings: { open: string; loading: string },
): string | null {
  if (rule === null) return null;
  if (rule === 'open') return strings.open;
  if (rule === 'loading') return strings.loading;
  if (rule === 'word') return found.units.join(' ');
  const head = [...found.values, ...found.units].join(' ');
  return language === 'ar'
    ? `${head}، ${strings.open}`
    : `${head} ${strings.open}`;
}
