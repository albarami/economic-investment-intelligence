// @vitest-environment jsdom
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { PublicContextCard } from '../../src/cards/PublicContextCard';
import { contextPayloads, contextRegistry } from '../fixtures/public-context';
import {
  candidateProperties,
  cardParity,
  cardSnapshot,
  catalogueTextProblems,
} from '../question_lab/parity';
import { answerAccepted, catalogue } from '../../src/brief/catalogue';

afterEach(cleanup);

for (const payload of contextPayloads) {
  it(`S3-T21 exact bilingual card and evidence-depth parity: ${payload.family}`, () => {
    const registry = contextRegistry();
    const views = (['en', 'ar'] as const).map((language) => {
      const view = render(
        <PublicContextCard
          payload={payload}
          registry={registry}
          language={language}
          onOpen={() => undefined}
        />,
      );
      for (const level of ['comparison', 'evidence'])
        fireEvent.click(
          view.container.querySelector(
            `[data-context-level="${level}"] > button`,
          )!,
        );
      expect(catalogueTextProblems(view.container, language)).toEqual([]);
      return view;
    });
    const en = cardSnapshot(views[0]!.container);
    const ar = cardSnapshot(views[1]!.container);
    expect(cardParity(en, ar)).toEqual([]);
    const caveat = views[1]!.container.querySelector('[data-caveat] bdi')!;
    caveat.textContent =
      views[0]!.container.querySelector('[data-caveat] bdi')!.textContent;
    expect(catalogueTextProblems(views[1]!.container, 'ar')).toContain(
      'uncatalogued-text',
    );
    caveat.textContent = 'نص مخترع غير مسجل';
    expect(catalogueTextProblems(views[1]!.container, 'ar')).toContain(
      'uncatalogued-text',
    );
    const digit = views[1]!.container.querySelector('.chip-num')!;
    digit.textContent =
      '-' + views[0]!.container.querySelector('.chip-num')!.textContent;
    expect(cardParity(en, cardSnapshot(views[1]!.container))).toContain(
      'digits',
    );
    digit.textContent = '999';
    expect(cardParity(en, cardSnapshot(views[1]!.container))).toContain(
      'digits',
    );
    digit.textContent = '\u0669';
    expect(cardParity(en, cardSnapshot(views[1]!.container))).toContain(
      'westernDigits',
    );
    views[1]!.container
      .querySelector('[data-context-level="comparison"] > div')!
      .setAttribute('data-fact-id', 'INVENTED-other');
    expect(cardParity(en, cardSnapshot(views[1]!.container))).toContain(
      'factIds',
    );
    views[1]!.container
      .querySelector('[data-context-level="evidence"]')!
      .remove();
    expect(cardParity(en, cardSnapshot(views[1]!.container))).toContain(
      'depth',
    );
  });
}

it('S3-T21 lab rejects model text, raw numerals and a model-only candidate property', () => {
  const view = render(
    <PublicContextCard
      payload={contextPayloads[0]!}
      registry={contextRegistry()}
      language="en"
      onOpen={() => undefined}
    />,
  );
  const extra = document.createElement('p');
  extra.textContent = 'INVENTED model-written display sentence';
  view.container.append(extra);
  expect(catalogueTextProblems(view.container, 'en')).toContain(
    'uncatalogued-text',
  );
  extra.textContent = '123';
  expect(catalogueTextProblems(view.container, 'en')).toContain(
    'loose-numeral',
  );
  expect(candidateProperties({ componentKey: 'foundation_note' })).toEqual([]);
  expect(
    candidateProperties({ componentKey: 'foundation_note', prose: 'INVENTED' }),
  ).toEqual(['prose']);
  const control = {
    catalogueVersion: catalogue.version,
    accountingPassed: true,
    subject: 'area' as const,
    componentKey: 'foundation_note',
    props: [],
    directive: null,
    slots: [],
  };
  expect(answerAccepted(control, contextRegistry())).toBe(true);
  for (const property of ['prose', 'text', 'html', 'INVENTED-extra']) {
    const planted = { ...control, [property]: 'INVENTED uncatalogued text' };
    expect(answerAccepted(planted, contextRegistry())).toBe(false);
  }
  expect(
    answerAccepted(
      { ...control, claimKey: 'INVENTED-unknown' },
      contextRegistry(),
    ),
  ).toBe(false);
});
