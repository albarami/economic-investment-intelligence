// Every visible word of the look page comes from catalogue.json by key
// (docs/10_FRONTEND.md section "8. Bilingual and right-to-left rules").
import catalogue from './catalogue.json' with { type: 'json' };

export type Lang = 'en' | 'ar';
type Entry = { en: string; ar: string; review: string };

const strings = catalogue.strings as Record<string, Entry>;
let current: Lang = 'en';

export function setLang(lang: Lang): void {
  current = lang;
}

export function lang(): Lang {
  return current;
}

export function dir(which: Lang = current): 'rtl' | 'ltr' {
  return which === 'ar' ? 'rtl' : 'ltr';
}

export function t(key: string, which: Lang = current): string {
  const entry = strings[key];
  if (entry === undefined) throw new Error(`missing string: ${key}`);
  return entry[which];
}

// Round 5g, finding 16: whether the catalogue holds a key (a register type
// with no key is shown as published).
export function has(key: string): boolean {
  return key in strings;
}

type Binding = () => void;
const bindings: Binding[] = [];

// Registers an element whose words change with the language. The element
// carries data-word, so that the flip fades words and never a numeral.
export function bindText(element: HTMLElement, read: () => string): void {
  element.dataset.word = '';
  const apply = () => {
    element.textContent = read();
    element.lang = current;
  };
  apply();
  bindings.push(apply);
}

export function bind(apply: Binding): void {
  apply();
  bindings.push(apply);
}

export function refresh(): void {
  for (const apply of bindings) apply();
}
