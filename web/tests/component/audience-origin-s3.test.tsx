// @vitest-environment jsdom
/** S3-C34: landed surfaces only; the full story moments remain later work. */
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { catalogue, type AnswerDraft } from '../../src/brief/catalogue';
import { text } from '../../src/i18n';
import { AnswerShell } from '../../src/shell/AnswerShell';
import { clearArea } from '../../src/state/store';
import { Swipe, swipeStates } from '../../src/stage/Swipe';
import {
  environmentPlant,
  exposedCounts,
  originLabels,
  originStyles,
  plantInto,
  sourceText,
  type Language,
  type Plant,
} from '../fixtures/audience-origin';
import {
  completeInput,
  factId,
  makeBinding,
  makeFact,
  registryFrom,
} from '../fixtures/facts';

afterEach(() => {
  cleanup();
  clearArea();
});

const HIDDEN = 7391;
const comparison = {
  kind: 'scenario',
  baselineFactId: factId(0),
  changedFactId: factId(1),
} as const;

function input(withheld: boolean, scenario: boolean) {
  const fixture = completeInput();
  fixture.facts = [0, 1].map((index) =>
    makeBinding({
      fact: makeFact({
        fact_id: factId(index),
        value: withheld ? HIDDEN : index === 0 ? 48 : 52,
        provenance: withheld ? 'suppressed' : 'public',
        ...(scenario
          ? {
              geography: { kind: 'user_scenario', area_id: 'SYN-area' },
              input_classes: ['public', 'user_input'],
            }
          : {}),
      }),
    }),
  );
  if (scenario) {
    fixture.lineages[0]!.inputClasses = ['public', 'user_input'];
    fixture.sources[0]!.kind = 'reviewed_config';
  }
  return fixture;
}

const SURFACES = ['entry', 'disclosure', 'baseline/reset component'] as const;

function mount(
  surface: (typeof SURFACES)[number],
  language: Language,
  withheld = false,
) {
  const scenario = surface === 'baseline/reset component';
  const fixture = input(withheld, scenario);
  const registry = registryFrom(fixture);
  const draft: AnswerDraft = {
    catalogueVersion: catalogue.version,
    accountingPassed: true,
    subject: 'area',
    componentKey: 'foundation_note',
    props: [],
    directive: null,
    slots: [
      {
        factId: factId(0),
        provenance: withheld ? 'suppressed' : 'public',
        metric: 'people',
      },
    ],
  };
  const view = render(
    scenario ? (
      <Swipe
        language={language}
        comparison={comparison}
        registry={registry}
        onOpen={() => undefined}
      />
    ) : (
      <AnswerShell
        language={language}
        theme="dark"
        extractUrl={null}
        registry={registry}
        draft={draft}
      />
    ),
  );
  const observed = {
    root: view.container,
    allowed: sourceText(fixture.sources, fixture.lineages),
  };
  if (scenario) {
    if (withheld) {
      expect(swipeStates(comparison, registry)).toEqual({
        kind: 'refused',
        reason: 'scenario_state_untested',
      });
      expect(view.container.innerHTML).toBe('');
    } else {
      expect(findings(observed)).toEqual([]);
      fireEvent.click(
        view.getByRole('button', {
          name: text(language, 'comparison.showChanged'),
        }),
      );
      expect(
        view
          .getByRole('button', {
            name: text(language, 'comparison.showChanged'),
          })
          .getAttribute('aria-pressed'),
      ).toBe('true');
      expect(findings(observed)).toEqual([]);
      fireEvent.click(
        view.getByRole('button', { name: text(language, 'comparison.reset') }),
      );
      expect(
        view
          .getByRole('button', {
            name: text(language, 'comparison.showBaseline'),
          })
          .getAttribute('aria-pressed'),
      ).toBe('true');
    }
  } else {
    expect(view.container.querySelector('.stage')).not.toBeNull();
    expect(
      view.container.querySelector('.brief [data-fact-chip]'),
    ).not.toBeNull();
    if (surface === 'disclosure') {
      fireEvent.click(
        view.container.querySelector<HTMLButtonElement>(
          '.brief [data-fact-chip]',
        )!,
      );
      expect(view.getByRole('dialog')).toBeTruthy();
    }
    if (withheld)
      expect(
        view.container.querySelector('[data-state="withheld"]'),
      ).not.toBeNull();
  }
  return observed;
}

function findings(view: { root: Element; allowed: ReadonlySet<string> }) {
  return [
    ...originLabels(view.root, view.allowed),
    ...originStyles(view.root),
    ...exposedCounts(view.root, HIDDEN),
  ];
}

describe.each(['en', 'ar'] as const)(
  'S3 produced surfaces (%s)',
  (language) => {
    it('one-field withheld comparison refuses for scenario_state_untested', () => {
      const fixture = input(false, true);
      fixture.facts[1]!.fact.provenance = 'suppressed';
      const registry = registryFrom(fixture);
      expect(swipeStates(comparison, registry)).toEqual({
        kind: 'refused',
        reason: 'scenario_state_untested',
      });
      const view = render(
        <Swipe
          language={language}
          comparison={comparison}
          registry={registry}
          onOpen={() => undefined}
        />,
      );
      expect(view.container.innerHTML).toBe('');
    });

    for (const surface of SURFACES) {
      it(`${surface}: origin labels and textures are absent`, () => {
        const view = mount(surface, language);
        plantInto(view.root, environmentPlant(), language, HIDDEN);
        expect(findings(view)).toEqual([]);
      });

      it(`${surface}: withheld shows neither zero nor a hidden count`, () => {
        const view = mount(surface, language, true);
        plantInto(view.root, environmentPlant(), language, HIDDEN);
        expect(findings(view)).toEqual([]);
      });

      for (const [plant, guard, where] of [
        ['visible', 'origin-label', /^span$/],
        ['accessible', 'origin-label', /@aria-label$/],
        ['texture', 'origin-style', /^span\[layer-sample\]$/],
        ['hidden-count', 'hidden-count', /@aria-label$/],
      ] as const) {
        it(`${surface}: ${plant} has the exact ${guard} reason`, () => {
          const view = mount(surface, language, plant === 'hidden-count');
          expect(findings(view)).toEqual([]);
          plantInto(view.root, plant satisfies Plant, language, HIDDEN);
          expect(findings(view)).toEqual([
            {
              guard,
              where: expect.stringMatching(where),
              text: expect.any(String),
            },
          ]);
        });
      }
    }
  },
);

describe('withheld accessible count edge classes on every produced surface', () => {
  for (const surface of SURFACES) {
    for (const value of [
      '0',
      '٠',
      '۰',
      '7391',
      '7,391',
      '7 391',
      '٧٬٣٩١',
      '۷٬۳۹۱',
    ]) {
      it(`${surface}: ${value} fails with hidden-count alone`, () => {
        const view = mount(surface, 'ar', true);
        expect(findings(view)).toEqual([]);
        view.root.setAttribute('aria-label', value);
        expect(findings(view)).toEqual([
          {
            guard: 'hidden-count',
            where: 'div@aria-label',
            text: value,
          },
        ]);
      });
    }
  }
});
