// Reads the release the server wrote into the page's data block. The page
// formats what the release carries and computes no statistic (FE-45,
// FE-55): cell geometry is drawn from cell ids, and every number on screen
// is a fact of this release.
import {
  factView,
  validateRelease,
  type FactView,
  type Release,
} from './release-shape.mjs';

export type Loaded = {
  release: Release;
  fact: (id: string) => FactView;
  facts: FactView[];
};

export function readRelease(): Loaded {
  const block = document.getElementById('eii-release');
  const text = block?.textContent ?? '';
  if (text.trim() === '') throw new Error('the page holds no release');
  const release = validateRelease(JSON.parse(text));
  const facts = release.facts.map(factView);
  const byId = new Map(facts.map((fact) => [fact.id, fact]));
  return {
    release,
    facts,
    fact: (id: string) => {
      const found = byId.get(id);
      if (found === undefined) throw new Error(`missing fact ${id}`);
      return found;
    },
  };
}

// The facts of the Brief and of the legend, by their identifiers.
export const HERO_FACT = 'densest-unit';
export const SUPPORTING_FACTS = ['areas-with-firms', 'top-classes'];
export const BREAK_FACTS = ['break-1', 'break-2', 'break-3', 'break-4'];
