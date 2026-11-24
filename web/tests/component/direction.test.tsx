// @vitest-environment jsdom
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { FactChip } from '../../src/facts/FactChip';
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

const WORDS = ['higher', 'lower', 'equal', 'أعلى', 'أدنى', 'مساوٍ'];

function changeRegistry(
  value: number,
  direction: 'higher' | 'lower' | 'equal' | null,
) {
  const facts = [
    makeBinding({
      fact: makeFact({ value }),
      presentation: 'change' as const,
      directionId: direction ? factId(1) : undefined,
    }),
  ];
  if (direction) {
    facts.push(
      makeBinding({
        fact: makeFact({
          fact_id: factId(1),
          value: direction,
          unit: 'direction',
        }),
      }),
    );
  }
  return registryFrom({ ...completeInput(), facts });
}

function chipText(
  value: number,
  direction: 'higher' | 'lower' | 'equal' | null,
  language: 'en' | 'ar',
) {
  const view = render(
    <FactChip
      variant="value"
      size="standard"
      factId={factId(0)}
      registry={changeRegistry(value, direction)}
      language={language}
      onOpen={() => undefined}
    />,
  );
  const shown = view.container.textContent ?? '';
  view.unmount();
  return shown;
}

describe('N3 supplied direction', () => {
  it('shows the supplied word for a positive, negative and zero change', () => {
    expect(chipText(6, 'higher', 'en')).toContain(
      text('en', 'direction.higher'),
    );
    expect(chipText(-6, 'lower', 'en')).toContain(
      text('en', 'direction.lower'),
    );
    expect(chipText(0, 'equal', 'en')).toContain(text('en', 'direction.equal'));
    expect(chipText(6, 'higher', 'ar')).toContain(
      text('ar', 'direction.higher'),
    );
  });

  it('shows no direction word when none was supplied', () => {
    for (const value of [6, -6, 0]) {
      const shown = chipText(value, null, 'en');
      expect(shown).toContain(value === 0 ? '0' : '6');
      for (const word of WORDS) expect(shown).not.toContain(word);
    }
  });

  it('shows a supplied direction that disagrees with the sign', () => {
    const shown = chipText(-6, 'higher', 'en');
    expect(shown).toContain(text('en', 'direction.higher'));
    expect(shown).not.toContain(text('en', 'direction.lower'));
  });

  function signedChange(companion: ReturnType<typeof makeBinding> | null) {
    const facts = [
      makeBinding({
        fact: makeFact({ value: -6 }),
        presentation: 'change' as const,
        directionId: companion ? factId(1) : undefined,
      }),
    ];
    if (companion) facts.push(companion);
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
    const shown = view.container.textContent ?? '';
    view.unmount();
    return shown;
  }

  function expectSignedNumber(shown: string) {
    expect(shown).toMatch(/[+\u2212-]6/);
    for (const word of WORDS) expect(shown).not.toContain(word);
  }

  function chipOf(
    registry: ReturnType<typeof registryFrom>,
    id: string,
  ): string {
    const view = render(
      <FactChip
        variant="value"
        size="standard"
        factId={id}
        registry={registry}
        language="en"
        onOpen={() => undefined}
      />,
    );
    const shown = view.container.textContent ?? '';
    view.unmount();
    return shown;
  }

  it('shows the signed number and no direction word on both parents that share one direction', () => {
    const direction = factId(2);
    const registry = registryFrom({
      ...completeInput(),
      facts: [
        makeBinding({
          fact: makeFact({ value: -6 }),
          presentation: 'change',
          directionId: direction,
        }),
        makeBinding({
          fact: makeFact({ fact_id: factId(1), value: 4 }),
          presentation: 'change',
          directionId: direction,
        }),
        makeBinding({
          fact: makeFact({
            fact_id: direction,
            value: 'higher',
            unit: 'direction',
          }),
        }),
      ],
    });
    expectSignedNumber(chipOf(registry, factId(0)));
    const other = chipOf(registry, factId(1));
    expect(other).toMatch(/[+\u2212-]4/);
    for (const word of WORDS) expect(other).not.toContain(word);
  });

  it("shows no direction word when parent A names parent B's direction and shows the word when B owns it", () => {
    const direction = factId(2);
    const companion = makeBinding({
      fact: makeFact({
        fact_id: direction,
        value: 'higher',
        unit: 'direction',
      }),
    });
    const parentB = makeBinding({
      fact: makeFact({ fact_id: factId(1), value: 4 }),
      presentation: 'change',
      directionId: direction,
    });
    const parentA = makeBinding({
      fact: makeFact({ value: -6 }),
      presentation: 'change',
      directionId: direction,
    });
    const named = registryFrom({
      ...completeInput(),
      facts: [parentA, parentB, companion],
    });
    expectSignedNumber(chipOf(named, factId(0)));
    const owned = registryFrom({
      ...completeInput(),
      facts: [parentB, companion],
    });
    const shownB = chipOf(owned, factId(1));
    expect(shownB).toContain(text('en', 'direction.higher'));
    expect(shownB).toMatch(/[+\u2212-]4/);
  });

  it('shows the signed number and no direction word for a null direction value', () => {
    expectSignedNumber(
      signedChange(
        makeBinding({
          fact: makeFact({
            fact_id: factId(1),
            value: null,
            unit: 'direction',
          }),
        }),
      ),
    );
  });

  it('shows the signed number and no direction word for an unknown direction value', () => {
    expectSignedNumber(
      signedChange(
        makeBinding({
          fact: makeFact({
            fact_id: factId(1),
            value: 'sideways',
            unit: 'direction',
          }),
        }),
      ),
    );
  });

  it('shows the signed number and no direction word when the direction companion is not ready', () => {
    expectSignedNumber(
      signedChange(
        makeBinding({
          fact: makeFact({
            fact_id: factId(1),
            value: 'higher',
            unit: 'direction',
            lineage_ref: 'lin_absent_direction',
          }),
        }),
      ),
    );
  });

  it('shows the signed number and no direction word when the reference is another fact', () => {
    const facts = [
      makeBinding({
        fact: makeFact({ value: -6 }),
        presentation: 'change' as const,
        directionId: factId(1),
      }),
      makeBinding({
        fact: makeFact({
          fact_id: factId(1),
          value: 'higher',
          unit: 'direction',
        }),
      }),
      makeBinding({
        fact: makeFact({ fact_id: factId(2), value: 4 }),
        presentation: 'change' as const,
        directionId: factId(1),
      }),
    ];
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
    expectSignedNumber(view.container.textContent ?? '');
    view.unmount();
  });

  it('shows the signed number and no direction word when the reference is not a direction', () => {
    expectSignedNumber(
      signedChange(
        makeBinding({
          fact: makeFact({
            fact_id: factId(1),
            value: 'higher',
            unit: 'count',
          }),
        }),
      ),
    );
  });

  it('shows the signed number and no direction word when the reference is a numeric change fact', () => {
    expectSignedNumber(
      signedChange(
        makeBinding({
          fact: makeFact({ fact_id: factId(1), value: 4 }),
          presentation: 'change' as const,
        }),
      ),
    );
  });

  it('shows the signed number and no direction word when the direction companion is withheld', () => {
    expectSignedNumber(
      signedChange(
        makeBinding({
          fact: makeFact({
            fact_id: factId(1),
            value: 'higher',
            unit: 'direction',
            provenance: 'suppressed',
            input_classes: ['public'],
          }),
        }),
      ),
    );
  });

  it('opens the same fact from each range bound by click and Enter', () => {
    const low = factId(1);
    const high = factId(2);
    const registry = registryFrom({
      ...completeInput(),
      facts: [
        makeBinding({
          fact: makeFact({ value: 48 }),
          presentation: 'estimated_count',
          rangeLowId: low,
          rangeHighId: high,
        }),
        makeBinding({ fact: makeFact({ fact_id: low, value: 40 }) }),
        makeBinding({ fact: makeFact({ fact_id: high, value: 50 }) }),
      ],
    });
    const onOpen = vi.fn();
    const view = render(
      <FactChip
        variant="value"
        size="large"
        factId={factId(0)}
        registry={registry}
        language="en"
        onOpen={onOpen}
      />,
    );
    for (const name of ['low', 'high']) {
      const bound = view.container.querySelector(`[data-bound="${name}"]`);
      expect(bound).toBeTruthy();
      if (!bound) continue;
      fireEvent.click(bound);
      fireEvent.keyDown(bound, { key: 'Enter' });
    }
    expect(onOpen.mock.calls).toEqual([
      [factId(0)],
      [factId(0)],
      [factId(0)],
      [factId(0)],
    ]);
  });
});
