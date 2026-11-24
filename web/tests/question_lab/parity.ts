/** Deterministic card oracle: application strings by exact locale and slot. */
import { catalogue, fragmentField } from '../../src/brief/catalogue';
import en from '../../src/i18n/en.json' with { type: 'json' };
import ar from '../../src/i18n/ar.json' with { type: 'json' };

/** A digit outside a Fact chip is a loose numeral, never permitted text. */
export const LOOSE_NUMERAL = /\p{Nd}/u;

/** True when a node sits strictly inside a Fact chip (permitted content). */
export function insideFactChip(node: Node): boolean {
  return !!node.parentElement?.closest('[data-fact-chip]');
}

export function catalogueTextProblems(
  root: HTMLElement,
  language: 'en' | 'ar',
): string[] {
  const problems = new Set<string>();
  const allowed = new Set([
    ...Object.values((language === 'en' ? en : ar).strings),
    ...catalogue.fragments.flatMap((entry) =>
      entry.fields
        .filter(([key]) => key === `template_${language}`)
        .map(([, text]) => text),
    ),
  ]);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (insideFactChip(node)) continue;
    const text = node.textContent?.trim() ?? '';
    if (!text) continue;
    if (LOOSE_NUMERAL.test(text)) problems.add('loose-numeral');
    if (!allowed.has(text)) problems.add('uncatalogued-text');
  }
  for (const card of root.querySelectorAll<HTMLElement>(
    '[data-context-family]',
  )) {
    const family = card.dataset.contextFamily!;
    if (
      card.lang !== language ||
      card.dir !== (language === 'ar' ? 'rtl' : 'ltr')
    )
      problems.add('card-direction');
    const slots: [string, string][] = [['h2 bdi', family]];
    for (const level of ['answer', 'comparison', 'evidence'])
      slots.push([
        `[data-context-level="${level}"] > button`,
        `context_level_${level}`,
      ]);
    for (const caveat of card.querySelectorAll<HTMLElement>('[data-caveat]'))
      slots.push([
        `[data-caveat="${caveat.dataset.caveat}"] bdi`,
        caveat.dataset.caveat!,
      ]);
    if (
      card
        .querySelector('[data-context-level="comparison"] > div')
        ?.hasAttribute('hidden') === false
    )
      slots.push([
        '[data-context-level="comparison"] p',
        `context_compare_${family}`,
      ]);
    for (const [selector, key] of slots) {
      const node = card.querySelector(selector);
      if (
        !node ||
        node.textContent !== fragmentField(key, `template_${language}`)
      )
        problems.add('uncatalogued-text');
    }
  }
  return [...problems].sort();
}

export function cardSnapshot(root: HTMLElement) {
  return {
    factIds: [...root.querySelectorAll('[data-fact-id]')].map((node) =>
      node.getAttribute('data-fact-id'),
    ),
    // Calendar month names and opaque citation words use their exact locale
    // templates; compare their Western numeric runs, retaining numeric separators.
    digits: [...root.querySelectorAll('.chip-num')].map((node) =>
      (node.textContent?.match(/[-+\u2212]?[0-9]+(?:[.,][0-9]+)*/g) ?? []).join(
        '|',
      ),
    ),
    status: [...root.querySelectorAll('[data-state]')].map((node) =>
      node.getAttribute('data-state'),
    ),
    kinds: [...root.querySelectorAll('[data-kind]')].map((node) =>
      node.getAttribute('data-kind'),
    ),
    depth: [...root.querySelectorAll('[data-context-level]')].map((node) => [
      node.getAttribute('data-context-level'),
      node.querySelector('button')?.getAttribute('aria-expanded'),
    ]),
    caveats: [...root.querySelectorAll('[data-caveat]')].map((node) =>
      node.getAttribute('data-caveat'),
    ),
    westernDigits: [...root.querySelectorAll('.chip-num')].every(
      (node) => !/[\u0660-\u0669\u06f0-\u06f9]/u.test(node.textContent ?? ''),
    ),
  };
}

/** Lab oracle, separate from the production reader, for model-only properties. */
export function candidateProperties(candidate: object): string[] {
  const allowed = [
    'catalogueVersion',
    'accountingPassed',
    'subject',
    'componentKey',
    'claimKey',
    'inList',
    'props',
    'directive',
    'slots',
  ];
  return Object.keys(candidate).filter((key) => !allowed.includes(key));
}

export function cardParity(
  left: ReturnType<typeof cardSnapshot>,
  right: ReturnType<typeof cardSnapshot>,
): string[] {
  const problems = (Object.keys(left) as (keyof typeof left)[]).filter(
    (key) => JSON.stringify(left[key]) !== JSON.stringify(right[key]),
  );
  if (
    right.digits.some((value) =>
      /[\u0660-\u0669\u06f0-\u06f9]/u.test(value ?? ''),
    )
  )
    problems.push('digits');
  return [...new Set(problems)];
}
