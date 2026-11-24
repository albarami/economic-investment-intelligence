// @vitest-environment jsdom
/**
 * FE-42: a Fact chip whose provenance is not the least-real class of its
 * input classes shows its refused state, no digit, and the drawer names the
 * mismatch in both languages.
 */
import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { FactChip } from '../../src/facts/FactChip';
import { SourceChainDrawer } from '../../src/facts/SourceChainDrawer';
import { text } from '../../src/i18n';
import {
  completeInput,
  factId,
  makeBinding,
  makeFact,
  registryFrom,
} from '../fixtures/facts';

afterEach(() => {
  cleanup();
});

const DIGIT = /\p{Nd}/u;

function planted() {
  return registryFrom({
    ...completeInput(),
    facts: [makeBinding({ fact: makeFact({ provenance: 'synthetic' }) })],
  });
}

describe('FE-42 chip error state', () => {
  for (const language of ['en', 'ar'] as const) {
    it(`refuses the value of a mismatched class (${language})`, () => {
      const view = render(
        <FactChip
          variant="value"
          size="standard"
          factId={factId(0)}
          registry={planted()}
          language={language}
          onOpen={() => undefined}
        />,
      );
      expect(
        view.container.querySelector('[data-state="refused"]'),
      ).toBeTruthy();
      expect(DIGIT.test(view.container.textContent ?? '')).toBe(false);
      view.unmount();
      const drawer = render(
        <SourceChainDrawer
          factId={factId(0)}
          registry={planted()}
          language={language}
          onClose={() => undefined}
        />,
      );
      expect(drawer.container.textContent).toContain(
        text(language, 'drawer.link.provenance_class'),
      );
    });
  }

  it('renders the same fact when its class follows from its inputs', () => {
    const view = render(
      <FactChip
        variant="value"
        size="standard"
        factId={factId(0)}
        registry={registryFrom(completeInput())}
        language="en"
        onOpen={() => undefined}
      />,
    );
    expect(view.container.querySelector('[data-state="ready"]')).toBeTruthy();
  });
});
