/**
 * Plants for the S3-T09 fix pass. Each case names the finding it locks.
 */
import { afterEach, describe, expect, it } from 'vitest';

import {
  answerAccepted,
  catalogue,
  directiveAccepted,
  fieldValueAccepted,
  subjectAllows,
  type AnswerDraft,
  type SubjectFact,
} from '../../src/brief/catalogue';
import { formatFactValue } from '../../src/facts/formatters';
import * as formatters from '../../src/facts/formatters';
import { createRegistry } from '../../src/facts/registry';
import type { Presentation, Provenance } from '../../src/facts/types';
import {
  completeInput,
  factId,
  makeBinding,
  makeFact,
  makeLineage,
  makeSource,
} from '../fixtures/facts';
afterEach(() => {
  const note = catalogue.components.find(
    (item) => item.key === 'foundation_note',
  );
  if (note) note.max_count = 1;
  catalogue.claims.splice(0, catalogue.claims.length);
});

function factOf(
  presentation: Presentation,
  extra: Record<string, string> = {},
) {
  return makeBinding({
    presentation,
    ...extra,
    fact: makeFact({ value: 12 }),
  });
}

describe('F1 required companions', () => {
  it('refuses a forecast when any companion identifier is absent', () => {
    const registry = createRegistry({
      ...completeInput(),
      facts: [factOf('forecast')],
    });
    const resolved = registry.resolve(factId(0));
    expect(resolved.status).toBe('refused');
    if (resolved.status === 'refused')
      expect(resolved.missing).toBe('companion');
  });

  it('refuses a site estimate when a companion identifier is absent', () => {
    const registry = createRegistry({
      ...completeInput(),
      facts: [factOf('site_estimate', { estimateLowId: factId(1) })],
    });
    expect(registry.resolve(factId(0)).status).toBe('refused');
  });

  it('refuses a base rate when a companion identifier is absent', () => {
    const registry = createRegistry({
      ...completeInput(),
      facts: [factOf('base_rate')],
    });
    expect(registry.resolve(factId(0)).status).toBe('refused');
  });

  it('accepts a forecast whose three companions are ready', () => {
    const low = factId(1);
    const high = factId(2);
    const error = factId(3);
    const registry = createRegistry({
      ...completeInput(),
      facts: [
        factOf('forecast', {
          intervalLowId: low,
          intervalHighId: high,
          backtestErrorId: error,
        }),
        makeBinding({ fact: makeFact({ fact_id: low, value: 10 }) }),
        makeBinding({ fact: makeFact({ fact_id: high, value: 14 }) }),
        makeBinding({
          fact: makeFact({ fact_id: error, value: 1, unit: 'ratio' }),
        }),
      ],
    });
    const resolved = registry.resolve(factId(0));
    expect(resolved.status).toBe('ready');
  });
});

describe('F2 fact and lineage input classes', () => {
  it('refuses a fact whose input classes disagree with its lineage', () => {
    const registry = createRegistry({
      ...completeInput(),
      facts: [
        makeBinding({
          fact: makeFact({ input_classes: ['synthetic'] }),
        }),
      ],
    });
    const resolved = registry.resolve(factId(0));
    expect(resolved.status).toBe('refused');
  });

  it('accepts the same classes in another order', () => {
    const registry = createRegistry({
      ...completeInput(),
      facts: [
        makeBinding({
          fact: makeFact({
            provenance: 'synthetic',
            input_classes: ['synthetic', 'public'],
          }),
        }),
      ],
      lineages: [
        makeLineage({
          inputClasses: ['public', 'synthetic'],
          sourceIds: ['src_alpha', 'src_beta'],
        }),
      ],
      sources: [
        makeSource(),
        makeSource({
          sourceId: 'src_beta',
          kind: 'synthetic_feed',
          inputClass: 'synthetic',
        }),
      ],
    });
    expect(registry.resolve(factId(0)).status).toBe('ready');
  });

  it('refuses a duplicated input class', () => {
    const registry = createRegistry({
      ...completeInput(),
      facts: [
        makeBinding({
          fact: makeFact({ input_classes: ['public', 'public'] }),
        }),
      ],
    });
    expect(registry.resolve(factId(0)).status).toBe('refused');
  });
});

function draft(overrides: Partial<AnswerDraft> = {}): AnswerDraft {
  return {
    catalogueVersion: catalogue.version,
    accountingPassed: true,
    subject: 'area',
    componentKey: 'foundation_note',
    props: [],
    directive: null,
    slots: [{ factId: factId(0), provenance: 'public', metric: 'people' }],
    ...overrides,
  };
}

describe('F3 answer slots resolve through the registry', () => {
  it('rejects a slot whose provenance lies about the fact', () => {
    const registry = createRegistry(completeInput());
    const row = draft({
      slots: [{ factId: factId(0), provenance: 'synthetic', metric: 'people' }],
    });
    expect(answerAccepted(row, registry)).toBe(false);
  });

  it('rejects a swapped metric that names another fact', () => {
    const registry = createRegistry(completeInput());
    const row = draft({
      slots: [
        { factId: factId(0), provenance: 'public', metric: 'employee_count' },
      ],
    });
    expect(answerAccepted(row, registry)).toBe(false);
  });

  it('rejects an unknown fact and does not keep a valid sibling', () => {
    const registry = createRegistry(completeInput());
    const row = draft({
      componentKey: 'foundation_note',
      slots: [
        { factId: factId(0), provenance: 'public', metric: 'people' },
        { factId: factId(4), provenance: 'public', metric: 'people' },
      ],
    });
    expect(answerAccepted(row, registry)).toBe(false);
  });

  it('rejects a slot past max_count', () => {
    const registry = createRegistry({
      ...completeInput(),
      facts: [
        makeBinding(),
        makeBinding({ fact: makeFact({ fact_id: factId(1) }) }),
      ],
    });
    const row = draft({
      slots: [
        { factId: factId(0), provenance: 'public', metric: 'people' },
        { factId: factId(1), provenance: 'public', metric: 'people' },
      ],
    });
    expect(answerAccepted(row, registry)).toBe(false);
  });
});

describe('F4 directive field kinds', () => {
  it('rejects a string in a boolean field', () => {
    expect(
      directiveAccepted('layer', { layer: 'sample_layer', visible: 'yes' }),
    ).toBe(false);
  });

  it('rejects a list that is not a string array', () => {
    expect(directiveAccepted('highlight', { place_keys: 'one' })).toBe(false);
  });

  it('rejects a const that does not match', () => {
    expect(directiveAccepted('split', { off: false })).toBe(false);
  });

  it('rejects a list outside its cardinality', () => {
    expect(directiveAccepted('rings', { area_ids: [] })).toBe(false);
    expect(directiveAccepted('rings', { area_ids: ['a', 'b', 'c'] })).toBe(
      false,
    );
  });

  it('rejects an unknown field kind', () => {
    expect(directiveAccepted('not-a-directive', { zoom: 'city' })).toBe(false);
    expect(
      fieldValueAccepted(
        {
          name: 'shade',
          kind: 'colour',
          values: [],
          const: null,
          minimum: null,
          maximum: null,
        },
        'red',
      ),
    ).toBe(false);
  });

  it('accepts a boolean and an enumeration in their closed forms', () => {
    expect(
      directiveAccepted('layer', { layer: 'sample_layer', visible: true }),
    ).toBe(true);
    expect(
      directiveAccepted('fly', { target: 'sample-pin', zoom: 'city' }),
    ).toBe(true);
  });
});

function query(
  partial: Partial<SubjectFact> & Pick<SubjectFact, 'provenance' | 'kind'>,
): SubjectFact {
  return {
    underlyingClass: null,
    inList: false,
    stabilityPresent: false,
    ...partial,
  };
}

describe('F5 subject kinds', () => {
  it('refuses an unknown subject', () => {
    expect(
      subjectAllows(
        'synthetic_firm',
        query({ provenance: 'public', kind: 'ordinary' }),
      ),
    ).toBe(false);
  });

  it('refuses a public estimate on a named place', () => {
    expect(subjectAllows('place_public', 'public', 'estimate')).toBe(false);
  });

  it('refuses a public rank outside a list', () => {
    expect(subjectAllows('register_company', 'public', 'rank')).toBe(false);
  });

  it('admits a list rank only with its stability companion', () => {
    expect(
      subjectAllows(
        'register_company',
        query({
          provenance: 'synthetic',
          kind: 'rank',
          inList: true,
          stabilityPresent: true,
        }),
      ),
    ).toBe(true);
    expect(
      subjectAllows(
        'register_company',
        query({
          provenance: 'synthetic',
          kind: 'rank',
          inList: true,
          stabilityPresent: false,
        }),
      ),
    ).toBe(false);
  });

  it('admits a suppressed fact only when every underlying class is admitted', () => {
    expect(
      subjectAllows(
        'area',
        query({ provenance: 'suppressed', kind: 'ordinary' }),
      ),
    ).toBe(true);
    expect(
      subjectAllows(
        'place_public',
        query({ provenance: 'suppressed', kind: 'ordinary' }),
      ),
    ).toBe(false);
  });

  it('judges a suppressed fact by the class it would have', () => {
    expect(
      subjectAllows(
        'place_public',
        query({
          provenance: 'suppressed',
          kind: 'ordinary',
          underlyingClass: 'public',
        }),
      ),
    ).toBe(true);
    expect(
      subjectAllows(
        'place_public',
        query({
          provenance: 'suppressed',
          kind: 'ordinary',
          underlyingClass: 'simulated',
        }),
      ),
    ).toBe(false);
  });

  it('plants every subject and kind decision', () => {
    const rows: Array<[string, string, string, boolean]> = [
      ['area', 'public', 'people', true],
      ['area', 'synthetic', 'wage', true],
      ['area', 'simulated', 'share', true],
      ['area', 'public', 'employee_count', false],
      ['place_public', 'public', 'people', true],
      ['place_public', 'synthetic', 'people', false],
      ['place_public', 'public', 'estimate', false],
      ['place_public', 'public', 'rank', false],
      ['fdi_project', 'public', 'people', true],
      ['fdi_project', 'simulated', 'people', false],
      ['fdi_project', 'public', 'score', false],
      ['register_company', 'public', 'card', true],
      ['register_company', 'public', 'people', false],
      ['register_company', 'synthetic', 'employee_count', true],
      ['register_company', 'public', 'employee_count', false],
      ['register_company', 'public', 'estimate', false],
      ['register_company', 'synthetic', 'wage_bill', false],
    ];
    for (const [subject, provenance, metric, admitted] of rows) {
      expect(subjectAllows(subject, provenance, metric)).toBe(admitted);
    }
  });
});

describe('F6 carried precision', () => {
  it('formats four decimal places in both languages', () => {
    for (const language of ['en', 'ar'] as const) {
      const formatted = formatFactValue(1.2345, 'ratio', language);
      expect(formatted.ok).toBe(true);
      if (formatted.ok) expect(formatted.text).toContain('1.2345');
    }
  });

  it('does not add a decimal to a whole number', () => {
    for (const language of ['en', 'ar'] as const) {
      const formatted = formatFactValue(12, 'ratio', language);
      expect(formatted.ok).toBe(true);
      if (formatted.ok) expect(formatted.text).toBe('12');
    }
  });

  it('formats an exponent-form number without rescaling', () => {
    for (const language of ['en', 'ar'] as const) {
      const formatted = formatFactValue(1e-7, 'ratio', language);
      expect(formatted.ok).toBe(true);
      if (formatted.ok) expect(formatted.text).toContain('0.0000001');
    }
  });

  it('keeps a value whose number form has no trailing zero', () => {
    for (const language of ['en', 'ar'] as const) {
      const formatted = formatFactValue(1.5, 'ratio', language);
      expect(formatted.ok).toBe(true);
      if (formatted.ok) expect(formatted.text).toBe('1.5');
    }
  });
});

describe('F7 closed band and published text forms', () => {
  it('rejects a wage band outside the closed pattern', () => {
    expect(formatFactValue('B00', 'wage_band', 'en').ok).toBe(false);
    expect(formatFactValue('B01', 'wage_band', 'en').ok).toBe(true);
    expect(formatFactValue('B01..B02', 'wage_band', 'en').ok).toBe(true);
  });

  it('rejects a size band outside the closed pattern', () => {
    expect(formatFactValue('large', 'size_band', 'en').ok).toBe(false);
    expect(formatFactValue('s01_09', 'size_band', 'en').ok).toBe(true);
  });

  it('rejects a volume band outside the closed pattern', () => {
    expect(formatFactValue('high', 'volume_band', 'en').ok).toBe(false);
    expect(formatFactValue('vb1', 'volume_band', 'en').ok).toBe(true);
  });

  it('rejects published text that breaks the closed form', () => {
    expect(formatFactValue('no-digit', 'published_text', 'en').ok).toBe(false);
    expect(formatFactValue(' code-1', 'published_text', 'en').ok).toBe(false);
    expect(formatFactValue('code-1 ', 'published_text', 'en').ok).toBe(false);
    expect(formatFactValue('line\n1', 'published_text', 'en').ok).toBe(false);
    expect(formatFactValue('code-1', 'published_text', 'en').ok).toBe(true);
  });

  it('still accepts a nonnumeric reference identifier', () => {
    const formatted = formatFactValue(
      'sample_counts',
      'published_text',
      'en',
      'reference',
    );
    expect(formatted.ok).toBe(true);
  });
});

describe('B7 direction words', () => {
  it('shows the catalogue word in each language and refuses an unknown code', () => {
    const english = formatFactValue('higher', 'direction', 'en');
    const arabic = formatFactValue('lower', 'direction', 'ar');
    expect(english.ok && english.text).toBe('higher');
    expect(arabic.ok && arabic.text).toBe('أدنى');
    expect(formatFactValue('sideways', 'direction', 'en').ok).toBe(false);
  });
});

describe('unused production comparison', () => {
  it('does not export sameNumericRun from the formatter module', () => {
    expect('sameNumericRun' in formatters).toBe(false);
  });
});

const PAIR_CLAIM = {
  key: 'sample_pair',
  section: 'observed',
  subject: 'area',
  slots: [
    {
      name: 'headcount',
      metric_key: 'people',
      unit: 'count',
      geography_role: 'national',
      period_rule: 'calendar_month',
      allowed_provenance: ['public'],
      breakdown: 'none',
    },
    {
      name: 'pay',
      metric_key: 'wage',
      unit: 'qar_per_month',
      geography_role: 'national',
      period_rule: 'calendar_month',
      allowed_provenance: ['public'],
      breakdown: 'none',
    },
  ],
  required_caveat_keys: [],
  required_companions: [],
  strengths_allowed: [],
  fields: [],
};

function mountPair(): void {
  const note = catalogue.components.find(
    (item) => item.key === 'foundation_note',
  );
  if (!note) throw new Error('missing component');
  note.max_count = 2;
  catalogue.claims.push(PAIR_CLAIM);
}

function peopleAndPay() {
  return createRegistry({
    ...completeInput(),
    facts: [
      makeBinding({
        fact: makeFact({ value: 12, unit: 'count' }),
        metricKey: 'people',
      }),
      makeBinding({
        fact: makeFact({
          fact_id: factId(1),
          value: 30,
          unit: 'qar_per_month',
        }),
        metricKey: 'wage',
      }),
    ],
  });
}

function pairedDraft(slots: AnswerDraft['slots']): AnswerDraft {
  return draft({ claimKey: 'sample_pair', slots });
}

function expectWithdrawn(
  row: AnswerDraft,
  registry: ReturnType<typeof peopleAndPay>,
) {
  expect(answerAccepted(row, registry)).toBe(false);
}

describe('N1 closed slot definitions', () => {
  it('withdraws two valid facts placed in each other slots', () => {
    mountPair();
    const row = pairedDraft([
      {
        name: 'pay',
        factId: factId(0),
        provenance: 'public',
        metric: 'people',
      },
      {
        name: 'headcount',
        factId: factId(1),
        provenance: 'public',
        metric: 'wage',
      },
    ]);
    expectWithdrawn(row, peopleAndPay());
  });

  it('withdraws an answer that omits a required slot', () => {
    mountPair();
    const row = pairedDraft([
      {
        name: 'headcount',
        factId: factId(0),
        provenance: 'public',
        metric: 'people',
      },
    ]);
    expectWithdrawn(row, peopleAndPay());
  });

  it('withdraws a slot name the definition does not hold', () => {
    mountPair();
    const row = pairedDraft([
      {
        name: 'headcount',
        factId: factId(0),
        provenance: 'public',
        metric: 'people',
      },
      {
        name: 'other',
        factId: factId(1),
        provenance: 'public',
        metric: 'wage',
      },
    ]);
    expectWithdrawn(row, peopleAndPay());
  });

  it('accepts the same facts in the slots the definition names', () => {
    mountPair();
    const registry = peopleAndPay();
    const row = pairedDraft([
      {
        name: 'headcount',
        factId: factId(0),
        provenance: 'public',
        metric: 'people',
      },
      {
        name: 'pay',
        factId: factId(1),
        provenance: 'public',
        metric: 'wage',
      },
    ]);
    expect(answerAccepted(row, registry)).toBe(true);
  });

  it('withdraws a fact whose unit breaks the slot rule', () => {
    mountPair();
    const registry = createRegistry({
      ...completeInput(),
      facts: [
        makeBinding({
          fact: makeFact({ value: 12, unit: 'qar' }),
          metricKey: 'people',
        }),
      ],
    });
    const row = draft({
      claimKey: 'sample_pair',
      slots: [
        {
          name: 'headcount',
          factId: factId(0),
          provenance: 'public',
          metric: 'people',
        },
        {
          name: 'pay',
          factId: factId(0),
          provenance: 'public',
          metric: 'people',
        },
      ],
    });
    expect(answerAccepted(row, registry)).toBe(false);
  });

  it('withdraws a fact whose geography breaks the slot rule', () => {
    mountPair();
    const registry = createRegistry({
      ...completeInput(),
      facts: [
        makeBinding({
          fact: makeFact({
            value: 12,
            geography: { kind: 'release_units', unit_ids: ['u-sample'] },
          }),
          metricKey: 'people',
        }),
        makeBinding({
          fact: makeFact({
            fact_id: factId(1),
            value: 30,
            unit: 'qar_per_month',
          }),
          metricKey: 'wage',
        }),
      ],
    });
    const row = pairedDraft([
      {
        name: 'headcount',
        factId: factId(0),
        provenance: 'public',
        metric: 'people',
      },
      {
        name: 'pay',
        factId: factId(1),
        provenance: 'public',
        metric: 'wage',
      },
    ]);
    expect(answerAccepted(row, registry)).toBe(false);
  });

  it('withdraws a fact whose provenance class breaks the slot rule', () => {
    mountPair();
    const registry = createRegistry({
      ...completeInput(),
      facts: [
        makeBinding({
          fact: makeFact({
            value: 12,
            provenance: 'synthetic',
            input_classes: ['synthetic'],
            lineage_ref: 'lin_sample_synth',
          }),
          metricKey: 'people',
        }),
        makeBinding({
          fact: makeFact({
            fact_id: factId(1),
            value: 30,
            unit: 'qar_per_month',
          }),
          metricKey: 'wage',
        }),
      ],
      lineages: [
        makeLineage(),
        makeLineage({
          lineageId: 'lin_sample_synth',
          inputClasses: ['synthetic'],
          sourceIds: ['src_beta'],
        }),
      ],
      sources: [
        makeSource(),
        makeSource({
          sourceId: 'src_beta',
          kind: 'synthetic_feed',
          inputClass: 'synthetic',
        }),
      ],
    });
    const row = pairedDraft([
      {
        name: 'headcount',
        factId: factId(0),
        provenance: 'synthetic',
        metric: 'people',
      },
      {
        name: 'pay',
        factId: factId(1),
        provenance: 'public',
        metric: 'wage',
      },
    ]);
    expect(answerAccepted(row, registry)).toBe(false);
  });
});

function classKind(
  provenance: Provenance,
): 'public_dataset' | 'synthetic_feed' | 'simulation_output' {
  if (provenance === 'synthetic') return 'synthetic_feed';
  if (provenance === 'simulated') return 'simulation_output';
  return 'public_dataset';
}

function answerRegistry(
  provenance: Provenance,
  metric: string,
  stable: boolean,
) {
  const inputClass = provenance === 'suppressed' ? 'public' : provenance;
  const unit =
    metric === 'rank' || metric === 'fit'
      ? 'rank'
      : metric === 'wage' || metric === 'wage_bill'
        ? 'qar_per_month'
        : metric === 'share' || metric === 'estimate' || metric === 'score'
          ? 'percent'
          : 'count';
  const value = provenance === 'suppressed' ? null : unit === 'rank' ? 1 : 12;
  return createRegistry({
    ...completeInput(),
    facts: [
      makeBinding({
        metricKey: metric,
        stabilityId: stable ? factId(1) : undefined,
        fact: makeFact({
          provenance,
          value,
          unit,
          input_classes: [inputClass],
        }),
      }),
      makeBinding({
        metricKey: 'rank_stability',
        fact: makeFact({
          fact_id: factId(1),
          value: 1,
          unit: 'rank',
          lineage_ref: 'lin_sample_stable',
        }),
      }),
    ],
    lineages: [
      makeLineage({ inputClasses: [inputClass] }),
      makeLineage({
        lineageId: 'lin_sample_stable',
        inputClasses: ['public'],
        sourceIds: ['src_stable'],
      }),
    ],
    sources: [
      makeSource({ kind: classKind(provenance), inputClass }),
      makeSource({ sourceId: 'src_stable' }),
    ],
  });
}

describe('N2 answer gate subject combinations', () => {
  it.each([
    ['area', 'suppressed', 'people', false, false, true],
    ['place_public', 'suppressed', 'people', false, false, false],
    ['fdi_project', 'suppressed', 'people', false, false, false],
    ['register_company', 'public', 'rank', true, true, true],
    ['register_company', 'public', 'fit', true, true, true],
    ['register_company', 'synthetic', 'rank', true, true, true],
    ['register_company', 'synthetic', 'fit', true, true, true],
    ['register_company', 'synthetic', 'rank', true, false, false],
    ['register_company', 'synthetic', 'rank', false, true, false],
    ['register_company', 'public', 'rank', false, false, false],
    ['place_public', 'public', 'rank', true, true, false],
    ['area', 'public', 'rank', true, true, true],
    ['area', 'public', 'rank', false, false, false],
    ['register_company', 'suppressed', 'employee_count', false, false, false],
    ['register_company', 'synthetic', 'employee_count', false, false, true],
    ['register_company', 'public', 'employee_count', false, false, false],
    ['register_company', 'simulated', 'employee_count', false, false, false],
    ['register_company', 'synthetic', 'wage', false, false, false],
    ['register_company', 'synthetic', 'wage_bill', false, false, false],
    ['register_company', 'public', 'card', false, false, true],
    ['register_company', 'public', 'people', false, false, false],
    ['register_company', 'public', 'estimate', false, false, false],
    ['place_public', 'synthetic', 'people', false, false, false],
    ['place_public', 'public', 'estimate', false, false, false],
    ['fdi_project', 'simulated', 'people', false, false, false],
    ['fdi_project', 'public', 'score', false, false, false],
    ['area', 'public', 'people', false, false, true],
    ['area', 'synthetic', 'wage', false, false, true],
    ['area', 'simulated', 'share', false, false, true],
    ['area', 'public', 'employee_count', false, false, false],
    ['register_company', 'public', 'fit', true, false, false],
    ['register_company', 'public', 'fit', false, true, false],
    ['register_company', 'public', 'fit', false, false, false],
    ['register_company', 'synthetic', 'fit', true, false, false],
    ['register_company', 'synthetic', 'fit', false, true, false],
    ['area', 'public', 'fit', true, true, true],
    ['area', 'public', 'fit', true, false, false],
    ['area', 'public', 'fit', false, true, false],
    ['area', 'public', 'fit', false, false, false],
  ] as const)(
    '%s %s %s list %s stability %s is %s',
    (subject, provenance, metric, inList, stable, admitted) => {
      const registry = answerRegistry(provenance, metric, stable);
      const row = draft({
        subject,
        inList,
        slots: [{ factId: factId(0), provenance, metric }],
      });
      expect(answerAccepted(row, registry)).toBe(admitted);
    },
  );
});

function rankAnswer(
  stabilityId: string | undefined,
  companion: ReturnType<typeof makeBinding> | null,
) {
  const facts = [
    makeBinding({
      metricKey: 'rank',
      stabilityId,
      fact: makeFact({ value: 1, unit: 'rank' }),
    }),
  ];
  if (companion) facts.push(companion);
  const registry = createRegistry({ ...completeInput(), facts });
  const row = draft({
    subject: 'register_company',
    inList: true,
    slots: [{ factId: factId(0), provenance: 'public', metric: 'rank' }],
  });
  return answerAccepted(row, registry);
}

describe('N2 rank-stability companion attacks', () => {
  it('accepts a list rank only beside its rank-stability companion', () => {
    expect(
      rankAnswer(
        factId(1),
        makeBinding({
          metricKey: 'rank_stability',
          fact: makeFact({ fact_id: factId(1), value: 1, unit: 'rank' }),
        }),
      ),
    ).toBe(true);
  });

  it('refuses a missing stability companion', () => {
    expect(rankAnswer(undefined, null)).toBe(false);
    expect(rankAnswer(factId(1), null)).toBe(false);
  });

  it('refuses a stability companion that is not ready', () => {
    expect(
      rankAnswer(
        factId(1),
        makeBinding({
          metricKey: 'rank_stability',
          fact: makeFact({
            fact_id: factId(1),
            value: 1,
            unit: 'rank',
            lineage_ref: 'lin_absent_stable',
          }),
        }),
      ),
    ).toBe(false);
  });

  it('refuses a stability companion that is a different fact', () => {
    expect(
      rankAnswer(
        factId(1),
        makeBinding({
          metricKey: 'rank',
          fact: makeFact({ fact_id: factId(1), value: 2, unit: 'rank' }),
        }),
      ),
    ).toBe(false);
    expect(
      rankAnswer(
        factId(1),
        makeBinding({
          metricKey: 'rank_stability',
          fact: makeFact({ fact_id: factId(1), value: 12, unit: 'count' }),
        }),
      ),
    ).toBe(false);
  });

  it('refuses a self reference as the stability companion', () => {
    expect(rankAnswer(factId(0), null)).toBe(false);
  });

  it('refuses an unrelated ready fact as the stability companion', () => {
    expect(
      rankAnswer(
        factId(1),
        makeBinding({
          metricKey: 'people',
          fact: makeFact({ fact_id: factId(1), value: 12, unit: 'count' }),
        }),
      ),
    ).toBe(false);
  });
});

describe('N4 percent is one platform unit', () => {
  it('formats 12.5 as a percent in both locales without multiplying', () => {
    for (const language of ['en', 'ar'] as const) {
      const formatted = formatFactValue(12.5, 'percent', language);
      expect(formatted.ok).toBe(true);
      if (!formatted.ok) return;
      expect(formatted.text).not.toContain('1250');
      expect(formatted.text).toContain('12.5');
      expect(formatted.text).not.toMatch(/[٠-٩۰-۹]/);
      expect(formatted.text).toMatch(/%|٪/);
    }
  });
});

function joined(pieces: readonly string[]): string {
  return pieces.join('');
}

describe('N5 closed text refusals and companion positives', () => {
  it('accepts a site estimate whose companions are ready', () => {
    const low = factId(1);
    const high = factId(2);
    const registry = createRegistry({
      ...completeInput(),
      facts: [
        factOf('site_estimate', { estimateLowId: low, estimateHighId: high }),
        makeBinding({ fact: makeFact({ fact_id: low, value: 10 }) }),
        makeBinding({ fact: makeFact({ fact_id: high, value: 14 }) }),
      ],
    });
    expect(registry.resolve(factId(0)).status).toBe('ready');
  });

  it('accepts a base rate whose companions are ready', () => {
    const numerator = factId(1);
    const denominator = factId(2);
    const period = factId(3);
    const registry = createRegistry({
      ...completeInput(),
      facts: [
        factOf('base_rate', {
          numeratorId: numerator,
          denominatorId: denominator,
          periodId: period,
        }),
        makeBinding({ fact: makeFact({ fact_id: numerator, value: 2 }) }),
        makeBinding({ fact: makeFact({ fact_id: denominator, value: 8 }) }),
        makeBinding({
          fact: makeFact({ fact_id: period, value: 4, unit: 'count' }),
        }),
      ],
    });
    expect(registry.resolve(factId(0)).status).toBe('ready');
  });

  it('refuses a forecast, estimate or base rate that lacks a companion', () => {
    for (const presentation of [
      'forecast',
      'site_estimate',
      'base_rate',
    ] as const) {
      const registry = createRegistry({
        ...completeInput(),
        facts: [factOf(presentation)],
      });
      const resolved = registry.resolve(factId(0));
      expect(resolved.status).toBe('refused');
      if (resolved.status === 'refused')
        expect(resolved.missing).toBe('companion');
    }
  });

  it('refuses a fact whose input classes disagree with its lineage', () => {
    const registry = createRegistry({
      ...completeInput(),
      facts: [
        makeBinding({ fact: makeFact({ input_classes: ['synthetic'] }) }),
      ],
    });
    expect(registry.resolve(factId(0)).status).toBe('refused');
  });

  it('rejects every closed published-text form', () => {
    const eight = joined(['1357', '2468']);
    const eleven = joined(['1357', '2468', '901']);
    const rejected = [
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
      `code-${eight}`,
      `code-${eleven}`,
      'code-1\u0967',
    ];
    for (const value of rejected) {
      expect(formatFactValue(value, 'published_text', 'en').ok).toBe(false);
    }
  });
});
