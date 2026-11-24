// The Fact chip family of the look page: the only component that renders a
// numeral (DES-155, docs/10_FRONTEND.md section "5. The Fact chip rule").
// Variants: value (large and standard), compact (legend breaks and ranges)
// and reference (identifiers). Rulings L-111 to L-114: no chip shows a class
// word or a class mark. Each chip carries its fact identifier and class in
// the page's own data, and opens the fact's source chain when pressed.
import { completeFactChain } from './lineage.mjs';
import { dateParts, formatRange, formatValue } from './facts.mjs';
import { bind, dir, lang, t } from './i18n';
import type { ClassKey, FactView } from './release-shape.mjs';

export type Fact = FactView;
export type Provenance = ClassKey;

const REALNESS: Provenance[] = ['public', 'synthetic', 'simulated'];

// FE-42: the chip recomputes the least-real class of its inputs.
function leastReal(classes: Provenance[]): Provenance | null {
  let worst = -1;
  for (const item of classes) worst = Math.max(worst, REALNESS.indexOf(item));
  return worst < 0 ? null : (REALNESS[worst] ?? null);
}

// FE-41 and FE-42: a fact without its chain, or whose class disagrees with
// its inputs, is refused rather than drawn.
export function refusal(fact: Fact): string {
  if (!completeFactChain(fact)) return 'no-chain';
  if (leastReal(fact.inputClasses) !== fact.provenance) return 'class';
  return '';
}

function isolate(text: string): HTMLElement {
  const element = document.createElement('bdi');
  element.dir = 'ltr';
  element.lang = 'en';
  element.className = 'chip-num';
  element.dataset.num = '';
  element.textContent = text;
  return element;
}

function words(className: string, read: () => string): HTMLSpanElement {
  const element = document.createElement('span');
  element.className = className;
  element.dataset.word = '';
  bind(() => {
    element.textContent = read();
    element.lang = lang();
  });
  return element;
}

function refused(): HTMLElement {
  const element = document.createElement('span');
  element.dataset.chip = 'refused';
  element.className = 'chip chip-refused';
  element.append(words('chip-unit', () => t('chip.refused')));
  return element;
}

function root(): HTMLElement {
  const element = document.createElement('bdi');
  element.className = 'chip-root';
  bind(() => {
    element.dir = dir();
  });
  return element;
}

// The page's own record of a chip's fact: identifier and class as data,
// never as a visible mark.
function record(element: HTMLElement, facts: Fact[], variant: string): void {
  element.dataset.chip = variant;
  element.dataset.fact = facts[0]?.id ?? '';
  element.dataset.facts = facts.map((fact) => fact.id).join(' ');
  element.dataset.provenance = facts[0]?.provenance ?? '';
}

function shell(
  facts: Fact[],
  variant: 'value' | 'compact',
  open: ((fact: Fact, ...additional: Fact[]) => void) | null,
): HTMLElement {
  const first = facts[0];
  if (first === undefined) throw new Error('a chip needs a fact');
  const element =
    open === null
      ? document.createElement('span')
      : document.createElement('button');
  element.className = 'chip';
  if (element instanceof HTMLButtonElement) {
    element.type = 'button';
    element.addEventListener('click', () => open?.(first, ...facts.slice(1)));
  }
  record(element, facts, variant);
  return element;
}

export type ValueSize = 'large' | 'standard';

// A `value` chip: the number with its unit, and its geography in caption
// type beneath. With `open` null it is the still copy at the head of the
// source chain.
export function valueChip(
  fact: Fact,
  size: ValueSize,
  open: ((fact: Fact, ...additional: Fact[]) => void) | null,
): HTMLElement {
  if (refusal(fact) !== '') return refused();
  const element = shell([fact], 'value', open);
  element.dataset.size = size;
  const body = root();
  const figure = document.createElement('span');
  figure.className = 'chip-figure';
  const value = () => formatValue(fact.value, fact.unit, lang());
  figure.append(isolate(value()));
  figure.append(words('chip-unit', () => t(fact.unitKey)));
  const geography = words('chip-geography', () => t(fact.geographyKey));
  body.append(figure, geography);
  element.append(body);
  if (open !== null) {
    bind(() => {
      element.setAttribute(
        'aria-label',
        `${value()} ${t(fact.unitKey)}. ${t(fact.geographyKey)}. ${t('chip.open')}.`,
      );
    });
  }
  return element;
}

// A `compact` chip: one value of the layer's scale (a legend break), at
// label size, with a hit area of the wall's target size (DES-74).
export function compactChip(fact: Fact, open: (fact: Fact) => void) {
  if (refusal(fact) !== '') return refused();
  const element = shell([fact], 'compact', open);
  const body = root();
  const value = () => formatValue(fact.value, fact.unit, lang());
  body.append(isolate(value()));
  element.append(body);
  bind(() => {
    element.setAttribute(
      'aria-label',
      `${value()} ${t(fact.unitKey)}. ${t(fact.geographyKey)}. ${t('chip.open')}.`,
    );
  });
  return element;
}

// DES-33: a range is one left-to-right run, lower bound first, en dash.
export function rangeChip(
  low: Fact,
  high: Fact,
  open: (fact: Fact, ...additional: Fact[]) => void,
) {
  if (refusal(low) !== '' || refusal(high) !== '') return refused();
  const element = shell([low, high], 'compact', open);
  const body = root();
  const value = () => formatRange(low.value, high.value, lang());
  body.append(isolate(value()));
  element.append(body);
  bind(() => {
    element.setAttribute(
      'aria-label',
      `${value()} ${t(low.unitKey)}. ${t('chip.open')}.`,
    );
  });
  return element;
}

// An identifier: rendered verbatim (DES-77).
// Round 5g, finding 22: the date of a count, a reference chip. Its day and
// year are numerals in Western digits that keep their place on a language
// flip; the month between them is a word in the page's language.
export function periodChip(iso: string): HTMLElement {
  const element = document.createElement('span');
  element.className = 'chip chip-reference';
  element.dataset.chip = 'reference';
  const { day, month, year } = dateParts(iso, lang());
  const word = document.createElement('span');
  word.textContent = month;
  element.append(isolate(day), ' ', word, ' ', isolate(year));
  return element;
}

export function referenceChip(text: string): HTMLElement {
  const element = document.createElement('span');
  element.className = 'chip chip-reference';
  element.dataset.chip = 'reference';
  element.append(isolate(text));
  return element;
}
