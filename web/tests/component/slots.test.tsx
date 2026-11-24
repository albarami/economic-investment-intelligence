// @vitest-environment jsdom
import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { catalogue, type AnswerDraft } from '../../src/brief/catalogue';
import { AnswerShell } from '../../src/shell/AnswerShell';
import {
  completeInput,
  factId,
  makeBinding,
  makeFact,
  registryFrom,
} from '../fixtures/facts';

const SAME = {
  key: 'sample_same',
  slots: [
    {
      name: 'left',
      metric_key: 'people',
      unit: 'count',
      geography_role: 'national',
      period_rule: 'calendar_month',
      allowed_provenance: ['public'],
      breakdown: 'none',
    },
    {
      name: 'right',
      metric_key: 'people',
      unit: 'count',
      geography_role: 'national',
      period_rule: 'calendar_month',
      allowed_provenance: ['public'],
      breakdown: 'none',
    },
  ],
};

const PAIR = {
  key: 'sample_pair',
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
};

afterEach(() => {
  cleanup();
  const note = catalogue.components.find(
    (item) => item.key === 'foundation_note',
  );
  if (note) note.max_count = 1;
  catalogue.claims.splice(0, catalogue.claims.length);
});

function registry() {
  return registryFrom({
    ...completeInput(),
    facts: [
      makeBinding({ metricKey: 'people', fact: makeFact({ value: 12 }) }),
      makeBinding({
        metricKey: 'wage',
        fact: makeFact({
          fact_id: factId(1),
          value: 30,
          unit: 'qar_per_month',
        }),
      }),
    ],
  });
}

function draft(slots: AnswerDraft['slots']): AnswerDraft {
  return {
    catalogueVersion: catalogue.version,
    accountingPassed: true,
    subject: 'area',
    componentKey: 'foundation_note',
    claimKey: 'sample_pair',
    props: [],
    directive: null,
    slots,
  };
}

function shown(slots: AnswerDraft['slots']) {
  const note = catalogue.components.find(
    (item) => item.key === 'foundation_note',
  );
  if (!note) throw new Error('missing component');
  note.max_count = 2;
  catalogue.claims.push(PAIR);
  return render(
    <AnswerShell
      language="en"
      theme="dark"
      extractUrl={null}
      registry={registry()}
      draft={draft(slots)}
    />,
  );
}

describe('N1 slot plants render nothing of a withdrawn item', () => {
  it('renders no slot when two valid ids are swapped', () => {
    const view = shown([
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
    expect(view.container.querySelector('[data-part="slots"]')).toBeNull();
    expect(view.container.querySelector('.brief [data-fact-chip]')).toBeNull();
  });

  it('renders no slot when a required slot is missing', () => {
    const view = shown([
      {
        name: 'headcount',
        factId: factId(0),
        provenance: 'public',
        metric: 'people',
      },
    ]);
    expect(view.container.querySelector('[data-part="slots"]')).toBeNull();
    expect(view.container.querySelector('.brief [data-fact-chip]')).toBeNull();
  });

  it('renders no slot when a slot name is unknown', () => {
    const view = shown([
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
    expect(view.container.querySelector('[data-part="slots"]')).toBeNull();
    expect(view.container.querySelector('.brief [data-fact-chip]')).toBeNull();
  });

  it('renders both slots when each fact sits in its own slot', () => {
    const view = shown([
      {
        name: 'headcount',
        factId: factId(0),
        provenance: 'public',
        metric: 'people',
      },
      { name: 'pay', factId: factId(1), provenance: 'public', metric: 'wage' },
    ]);
    expect(
      view.container.querySelectorAll('.brief [data-fact-chip]'),
    ).toHaveLength(2);
  });
});

function people(index: number, value: number) {
  return makeBinding({
    metricKey: 'people',
    fact: makeFact({ fact_id: factId(index), value, unit: 'count' }),
  });
}

function compatible(
  slots: AnswerDraft['slots'],
  facts: ReturnType<typeof people>[],
  maxCount: number,
) {
  const note = catalogue.components.find(
    (item) => item.key === 'foundation_note',
  );
  if (!note) throw new Error('missing component');
  note.max_count = maxCount;
  catalogue.claims.push(SAME);
  return render(
    <AnswerShell
      language="en"
      theme="dark"
      extractUrl={null}
      registry={registryFrom({ ...completeInput(), facts })}
      draft={{ ...draft(slots), claimKey: SAME.key }}
    />,
  );
}

function withdrawn(view: ReturnType<typeof render>) {
  expect(view.container.querySelector('[data-part="slots"]')).toBeNull();
  expect(view.container.querySelector('.brief [data-fact-chip]')).toBeNull();
}

describe('N1 extra slot and repeated fact', () => {
  it('renders no slot when a compatible list has an extra slot', () => {
    const view = compatible(
      [
        {
          name: 'left',
          factId: factId(0),
          provenance: 'public',
          metric: 'people',
        },
        {
          name: 'right',
          factId: factId(1),
          provenance: 'public',
          metric: 'people',
        },
        {
          name: 'extra',
          factId: factId(2),
          provenance: 'public',
          metric: 'people',
        },
      ],
      [people(0, 12), people(1, 13), people(2, 14)],
      3,
    );
    withdrawn(view);
  });

  it('renders no slot when one fact fills two compatible slots', () => {
    const view = compatible(
      [
        {
          name: 'left',
          factId: factId(0),
          provenance: 'public',
          metric: 'people',
        },
        {
          name: 'right',
          factId: factId(0),
          provenance: 'public',
          metric: 'people',
        },
      ],
      [people(0, 12)],
      2,
    );
    withdrawn(view);
  });

  it('renders both compatible slots when the facts differ', () => {
    const view = compatible(
      [
        {
          name: 'left',
          factId: factId(0),
          provenance: 'public',
          metric: 'people',
        },
        {
          name: 'right',
          factId: factId(1),
          provenance: 'public',
          metric: 'people',
        },
      ],
      [people(0, 12), people(1, 13)],
      2,
    );
    expect(
      view.container.querySelectorAll('.brief [data-fact-chip]'),
    ).toHaveLength(2);
  });
});
