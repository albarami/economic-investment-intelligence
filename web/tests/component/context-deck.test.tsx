// @vitest-environment jsdom
import { cleanup, fireEvent, render, within } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { ContextCards } from '../../src/journeys/ContextCards';
import { createRegistry } from '../../src/facts/registry';
import { contextInput, contextPayloads } from '../fixtures/public-context';
import { factId } from '../fixtures/facts';

afterEach(cleanup);
for (const language of ['en', 'ar'] as const) {
  it(`a withheld selected observation keeps its reason and lock, never its hidden value (${language})`, () => {
    const input = contextInput();
    input.facts[0]!.fact.provenance = 'suppressed';
    input.facts[0]!.fact.value = 987;
    const view = render(
      <ContextCards
        cards={contextPayloads}
        registry={createRegistry(input)}
        language={language}
        onOpen={() => undefined}
      />,
    );
    const card = view.container.querySelector(
      '[data-context-family="night_lights"]',
    )!;
    expect(card.querySelector('[data-mark="withheld"]')).not.toBeNull();
    expect(card.querySelector('.context-withheld p')?.textContent).toBeTruthy();
    expect(card.textContent).not.toMatch(/987|(?<![0-9])0(?![0-9])/);
    expect(card.querySelector('[data-fact-chip="value"] .chip-num')).toBeNull();
    expect(card.querySelector('[data-fact-chip="value"]')).toBeNull();
    expect(
      card.querySelector(
        '.context-withheld .chip-withheld [data-shape="lock"]',
      ),
    ).not.toBeNull();
  });
}

it('selection and a language flip preserve the same returned observation identity', () => {
  const input = contextInput();
  const original = input.facts[2]!;
  input.facts.push({
    ...original,
    fact: { ...original.fact, fact_id: factId(3), value: 35 },
  });
  const registry = createRegistry(input);
  const existing = contextPayloads[2]!;
  if (existing.state !== 'ready' || existing.family !== 'population_age_sex')
    throw new Error('ready fixture');
  const cards = [existing, { ...existing, factId: factId(3) }];
  const view = render(
    <ContextCards
      cards={cards}
      registry={registry}
      language="en"
      onOpen={() => undefined}
    />,
  );
  const details = view.container.querySelector('details')!;
  fireEvent.click(within(details).getByText('Population by age and sex'));
  details.open = true;
  fireEvent.click(
    view.container.querySelector(`[data-observation="${factId(3)}"]`)!,
  );
  expect(
    view.container
      .querySelector('article [data-fact-chip="value"]')
      ?.getAttribute('data-fact-id'),
  ).toBe(factId(3));
  view.rerender(
    <ContextCards
      cards={cards}
      registry={registry}
      language="ar"
      onOpen={() => undefined}
    />,
  );
  expect(
    view.container
      .querySelector('article [data-fact-chip="value"]')
      ?.getAttribute('data-fact-id'),
  ).toBe(factId(3));
  const selected = registry.resolve(factId(3));
  if (selected.status !== 'ready') throw new Error('chain fixture');
  expect(selected.binding).toBe(input.facts[3]);
});

// S3-T26 A5 round 2 (F4): the chosen-area caption covers the area cards only.
for (const language of ['en', 'ar'] as const) {
  it(`the chosen-area caption sits on each area card and never on the named-place card (${language})`, () => {
    const view = render(
      <ContextCards
        cards={contextPayloads}
        registry={createRegistry(contextInput())}
        language={language}
        onOpen={() => undefined}
        chosenArea
      />,
    );
    const caption = (family: string) =>
      view.container.querySelectorAll(
        `[data-context-deck="${family}"] [data-part="chosen-area"]`,
      );
    expect(caption('night_lights')).toHaveLength(1);
    expect(caption('population_age_sex')).toHaveLength(1);
    expect(caption('venue_busyness')).toHaveLength(0);
    expect(caption('night_lights')[0]!.textContent).toBe(
      language === 'en'
        ? 'This card is for the area you chose.'
        : 'هذه البطاقة تخص المنطقة التي اخترتها.',
    );
  });
}
// S3-T26 A5 round 3 (R2-F1): a no-data area card keeps a state-neutral caption.
for (const language of ['en', 'ar'] as const) {
  it(`a no-data area card carries the state-neutral chosen-area caption after its card (${language})`, () => {
    const view = render(
      <ContextCards
        cards={[
          {
            family: 'population_age_sex',
            state: 'no_data',
            reason: 'missing_input',
          },
        ]}
        registry={createRegistry(contextInput())}
        language={language}
        onOpen={() => undefined}
        chosenArea
      />,
    );
    const deck = view.container.querySelector(
      '[data-context-deck="population_age_sex"]',
    )!;
    const article = deck.querySelector(
      '[data-context-family="population_age_sex"]',
    )!;
    expect(article.querySelector('[data-state="NO_DATA"]')).not.toBeNull();
    const caption = deck.querySelectorAll('[data-part="chosen-area"]');
    expect(caption).toHaveLength(1);
    expect(caption[0]!.textContent).toBe(
      language === 'en'
        ? 'This card is for the area you chose.'
        : 'هذه البطاقة تخص المنطقة التي اخترتها.',
    );
    expect(
      article.compareDocumentPosition(caption[0]!) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(article.contains(caption[0]!)).toBe(false);
  });
}
it('shows no chosen-area caption unless the story marks its cards', () => {
  const view = render(
    <ContextCards
      cards={contextPayloads}
      registry={createRegistry(contextInput())}
      language="en"
      onOpen={() => undefined}
    />,
  );
  expect(view.container.querySelector('[data-part="chosen-area"]')).toBeNull();
});
