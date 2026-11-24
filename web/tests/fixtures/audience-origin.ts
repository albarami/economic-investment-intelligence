/**
 * Audience-origin guards for rendered surfaces (decision 0035 items 1 and 2).
 * Three separate guards, so that a planted violation fails only its own:
 * origin labels in visible or accessible text, origin-driven styles, and a
 * withheld count shown as zero or as its hidden value. Test-only; the
 * standing script of S3-T19 is separate.
 */

export type Language = 'en' | 'ar';

export interface Finding {
  guard: 'origin-label' | 'origin-style' | 'hidden-count';
  where: string;
  text: string;
}

/** Origin-class and origin words that never label audience data. */
const ORIGIN_EN = [
  'public',
  'synthetic',
  'simulated',
  'simulation',
  'generated',
  'sample',
  'demo',
  'demonstrator',
  'fictional',
  'invented',
  'fixture',
];

/** The same words in Arabic, after the normalisation of `normalise`. */
const ORIGIN_AR = [
  'علني',
  'العلني',
  'علنية',
  'العلنية',
  'اصطناعي',
  'الاصطناعي',
  'اصطناعية',
  'الاصطناعية',
  'محاكاة',
  'المحاكاة',
  'بالمحاكاة',
  'مولد',
  'المولد',
  'مولدة',
  'المولدة',
  'عينة',
  'العينة',
  'تجريبي',
  'التجريبي',
  'تجريبية',
  'التجريبية',
  'وهمي',
  'وهمية',
  'مختلق',
  'مختلقة',
];

/** Attributes whose text reaches assistive technology or a tooltip. */
export const ACCESSIBLE_ATTRIBUTES = [
  'aria-label',
  'aria-description',
  'aria-roledescription',
  'aria-valuetext',
  'aria-placeholder',
  'title',
  'alt',
  'placeholder',
] as const;

const ORIGIN_ATTRIBUTE_NAMES = [
  'data-provenance',
  'data-origin',
  'data-input-class',
  'data-class-key',
];

const ORIGIN_TOKEN =
  /(?:^|[-_\s])(?:synthetic|simulated|simulation)(?:$|[-_\s])/i;

function normalise(value: string): string {
  return value
    .normalize('NFC')
    .replace(/[\u064B-\u0652\u0670\u0640]/gu, '')
    .replace(/[\u0622\u0623\u0625]/gu, '\u0627');
}

function hasWord(term: string, value: string): boolean {
  return new RegExp(
    `(?:^|[^\\p{L}\\p{N}])${term}(?=$|[^\\p{L}\\p{N}])`,
    'iu',
  ).test(value);
}

export function originWordIn(value: string): string | null {
  const clean = normalise(value);
  for (const term of [...ORIGIN_EN, ...ORIGIN_AR]) {
    if (hasWord(term, clean)) return term;
  }
  return null;
}

/**
 * Backend class fields of a fixture: their values are markers, never words
 * a source supplies, so they never enter the allowance.
 */
const MARKER_FIELD = /provenance|class|status|kind/i;

/**
 * Every string leaf of the given fixture objects: source-supplied words
 * (publishers, datasets, names, methods). Backend marker fields are left
 * out, so a rendered class value is never allowed as a source word.
 */
export function sourceText(...values: unknown[]): Set<string> {
  const found = new Set<string>();
  const walk = (value: unknown) => {
    if (typeof value === 'string') {
      const trimmed = value.trim();
      if (trimmed) found.add(trimmed);
      return;
    }
    if (Array.isArray(value)) {
      value.forEach(walk);
      return;
    }
    if (value && typeof value === 'object')
      for (const [key, item] of Object.entries(value)) {
        if (!MARKER_FIELD.test(key)) walk(item);
      }
  };
  values.forEach(walk);
  return found;
}

function pathOf(node: Node): string {
  const element =
    node instanceof Element ? node : (node.parentElement ?? undefined);
  if (!element) return '#text';
  const part =
    element.getAttribute('data-part') ??
    element.getAttribute('data-fact-chip') ??
    element.getAttribute('class') ??
    '';
  return `${element.tagName.toLowerCase()}${part ? `[${part}]` : ''}`;
}

function textNodes(root: Element): Text[] {
  const walker = root.ownerDocument.createTreeWalker(
    root,
    NodeFilter.SHOW_TEXT,
  );
  const nodes: Text[] = [];
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const parent = node.parentElement;
    if (parent && (parent.tagName === 'SCRIPT' || parent.tagName === 'STYLE'))
      continue;
    nodes.push(node as Text);
  }
  return nodes;
}

function elementsOf(root: Element): Element[] {
  return [root, ...root.querySelectorAll('*')];
}

/**
 * Origin labels in visible text and in accessible text. A text node or an
 * accessible value whose whole text is a source-supplied value (a genuine Public credit, a
 * publisher's own words, a method or table name) is the source speaking,
 * not an origin label, and is passed over.
 */
export function originLabels(
  root: Element,
  allowed: ReadonlySet<string> = new Set(),
): Finding[] {
  const findings: Finding[] = [];
  for (const node of textNodes(root)) {
    const value = (node.textContent ?? '').trim();
    if (!value || allowed.has(value)) continue;
    const term = originWordIn(value);
    if (term)
      findings.push({
        guard: 'origin-label',
        where: pathOf(node),
        text: value,
      });
  }
  for (const element of elementsOf(root)) {
    for (const name of ACCESSIBLE_ATTRIBUTES) {
      const value = element.getAttribute(name);
      if (!value || allowed.has(value.trim())) continue;
      if (originWordIn(value))
        findings.push({
          guard: 'origin-label',
          where: `${pathOf(element)}@${name}`,
          text: value,
        });
    }
  }
  return findings;
}

/** Styles, textures, marks and hooks chosen by an origin class. */
export function originStyles(root: Element): Finding[] {
  const findings: Finding[] = [];
  for (const element of elementsOf(root)) {
    const reasons: string[] = [];
    for (const name of ORIGIN_ATTRIBUTE_NAMES) {
      if (element.hasAttribute(name)) reasons.push(name);
    }
    if (element.getAttribute('data-mark') === 'class')
      reasons.push('data-mark=class');
    for (const attribute of element.attributes) {
      const styleBearing =
        attribute.name === 'class' ||
        attribute.name === 'id' ||
        attribute.name === 'style' ||
        attribute.name === 'fill' ||
        attribute.name === 'stroke' ||
        attribute.name.startsWith('data-');
      if (!styleBearing) continue;
      const tokens = attribute.value.split(/\s+/);
      if (tokens.some((token) => ORIGIN_TOKEN.test(token)))
        reasons.push(`${attribute.name}=${attribute.value}`);
    }
    if (reasons.length > 0)
      findings.push({
        guard: 'origin-style',
        where: pathOf(element),
        text: reasons.join(' '),
      });
  }
  return findings;
}

const DIGIT_SETS = [0x0660, 0x06f0];

function asciiDigits(value: string): string {
  let out = '';
  for (const char of value) {
    const code = char.codePointAt(0) ?? 0;
    const base = DIGIT_SETS.find((start) => code >= start && code <= start + 9);
    out += base === undefined ? char : String(code - base);
  }
  return out.replace(/(?<=\d)[,'\u066C\u00A0\u202F ](?=\d)/gu, '');
}

function countsIn(value: string): number[] {
  return [...asciiDigits(value).matchAll(/\d+(?:[.\u066B]\d+)?/gu)].map(
    (match) => Number(match[0].replace('\u066B', '.')),
  );
}

/**
 * A withheld figure must show neither zero nor its hidden value, in
 * visible text or in accessible text. Reference chips (dates, hashes,
 * method versions) are references, not the withheld figure.
 */
export function exposedCounts(root: Element, hidden: number): Finding[] {
  const findings: Finding[] = [];
  const shown = (value: string) =>
    countsIn(value).some((count) => count === hidden || count === 0);
  for (const node of textNodes(root)) {
    if (node.parentElement?.closest('[data-fact-chip="reference"]')) continue;
    const value = node.textContent ?? '';
    if (shown(value))
      findings.push({
        guard: 'hidden-count',
        where: pathOf(node),
        text: value,
      });
  }
  for (const element of elementsOf(root)) {
    if (element.closest('[data-fact-chip="reference"]')) continue;
    for (const name of ACCESSIBLE_ATTRIBUTES) {
      const value = element.getAttribute(name);
      if (value && shown(value))
        findings.push({
          guard: 'hidden-count',
          where: `${pathOf(element)}@${name}`,
          text: value,
        });
    }
  }
  return findings;
}

/** The planted violations of S3-T18, one per guard. */
export type Plant = 'visible' | 'accessible' | 'texture' | 'hidden-count' | '';

export const PLANT_WORD: Record<Language, string> = {
  en: 'Simulated',
  ar: 'بالمحاكاة',
};

export function plantInto(
  root: Element,
  plant: Plant,
  language: Language,
  hidden = 7391,
): void {
  const doc = root.ownerDocument;
  if (plant === 'visible') {
    const label = doc.createElement('span');
    label.textContent = PLANT_WORD[language];
    root.append(label);
  }
  if (plant === 'accessible') {
    const label = doc.createElement('span');
    label.setAttribute('aria-label', PLANT_WORD[language]);
    root.append(label);
  }
  if (plant === 'texture') {
    const swatch = doc.createElement('span');
    swatch.className = 'layer-sample';
    swatch.setAttribute('data-pattern', 'dotted');
    swatch.setAttribute('data-provenance', 'synthetic');
    root.append(swatch);
  }
  if (plant === 'hidden-count') {
    const label = doc.createElement('span');
    label.setAttribute(
      'aria-label',
      language === 'ar'
        ? new Intl.NumberFormat('ar-QA').format(hidden)
        : String(hidden),
    );
    root.append(label);
  }
}

/** Selected by `EII_ORIGIN_PLANT` to show a guard red on a real surface. */
export function environmentPlant(): Plant {
  const value =
    typeof process === 'undefined' ? '' : (process.env.EII_ORIGIN_PLANT ?? '');
  if (
    value === 'visible' ||
    value === 'accessible' ||
    value === 'texture' ||
    value === 'hidden-count'
  )
    return value;
  return '';
}
