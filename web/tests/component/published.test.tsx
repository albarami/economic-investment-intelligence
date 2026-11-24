// @vitest-environment jsdom
import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { FactChip } from '../../src/facts/FactChip';
import { text } from '../../src/i18n';
import {
  completeInput,
  factId,
  makeBinding,
  makeFact,
  registryFrom,
} from '../fixtures/facts';

const DIGIT = /\p{Nd}/u;

function joined(parts: readonly string[]): string {
  return parts.join('');
}

function shown(value: string) {
  const registry = registryFrom({
    ...completeInput(),
    facts: [
      makeBinding({
        fact: makeFact({ value, unit: 'published_text' }),
      }),
    ],
  });
  return render(
    <FactChip
      variant="value"
      size="inline"
      factId={factId(0)}
      registry={registry}
      language="en"
      onOpen={() => undefined}
    />,
  );
}

describe('N5 published text stays an error with no digit', () => {
  afterEach(() => {
    cleanup();
  });

  it.each([
    'no-digit',
    '',
    ' code-1',
    'code-1 ',
    'code-1\n',
    'code-\u0665',
    'code-\u06F5',
    'code-1\u0001',
    'code-1\u200e',
    'code-1\u200b',
    'code-1\ufeff',
    'code-1\u2028',
    'code-1\u2029',
    `${'a'.repeat(200)}1`,
    `code-${joined(['1357', '2468'])}`,
    `code-${joined(['1357', '2468', '901'])}`,
    'code-1\u0967',
  ])('refuses %j on the chip', (value) => {
    const view = shown(value);
    const chip = view.container.querySelector('[data-fact-chip]');
    expect(chip?.getAttribute('data-state')).toBe('error');
    expect(chip?.textContent).toBe(text('en', 'chip.error'));
    expect(chip?.textContent ?? '').not.toMatch(DIGIT);
  });
});

function refusedFigure(facts: Parameters<typeof registryFrom>[0]['facts']) {
  const view = render(
    <FactChip
      variant="value"
      size="standard"
      factId={factId(0)}
      registry={registryFrom({ ...completeInput(), facts })}
      language="en"
      onOpen={() => undefined}
    />,
  );
  const chip = view.container.querySelector('[data-fact-chip]');
  expect(chip?.getAttribute('data-state')).toBe('refused');
  expect(chip?.textContent ?? '').not.toMatch(DIGIT);
  expect(chip?.textContent).toBe(text('en', 'chip.refused'));
  view.unmount();
}

describe('N5 refused chips show no digit', () => {
  afterEach(() => {
    cleanup();
  });

  it.each(['forecast', 'site_estimate', 'base_rate'] as const)(
    'shows no digit when a %s chip is refused',
    (presentation) => {
      refusedFigure([
        makeBinding({
          presentation,
          fact: makeFact({ value: 12 }),
        }),
      ]);
    },
  );

  it('shows no digit when a class-mismatch chip is refused', () => {
    refusedFigure([
      makeBinding({
        fact: makeFact({ value: 12, input_classes: ['synthetic'] }),
      }),
    ]);
  });
});
