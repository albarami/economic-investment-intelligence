// @vitest-environment jsdom
import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { CompanyCard } from '../../src/views/CompanyCard';
import { acceptPayload } from '../../src/stage/layers/refuse';
import { fcPayload, fcRegistry } from '../fixtures/fc-firms';
import type { FcCompanyRow } from '../../src/stage/layers/payload';

afterEach(() => {
  cleanup();
});

const row: FcCompanyRow = {
  feature_id: 'feat-invented-tower-aleph',
  row_id: 'row-aleph-one',
  fields: [
    { key: 'trade_name', text: 'Invented House Aleph' },
    { key: 'activity', text: 'Sample finance activity' },
    { key: 'wage', text: 'a planted wage' },
  ],
};

describe('company card', () => {
  it('test_the_card_shows_only_the_published_card_fields', () => {
    const view = render(<CompanyCard row={row} language="en" />);
    expect(view.getByText('Invented House Aleph')).toBeTruthy();
    expect(view.getByText('Sample finance activity')).toBeTruthy();
    expect(view.queryByText('a planted wage')).toBeNull();
    expect(view.container.querySelector('[data-field="wage"]')).toBeNull();
  });

  it('test_a_digit_card_field_renders_only_through_a_chip', () => {
    const planted = fcPayload();
    const company = planted.fc_firms?.companies[0];
    if (!company) throw new Error('missing row');
    company.fields = [
      ...company.fields,
      { key: 'trade_name', text: 'House 4' },
    ];
    const refused = acceptPayload(planted, fcRegistry());
    expect(refused.ok).toBe(false);
    if (!refused.ok) expect(refused.code).toBe('numeral_in_plain_segment');
    const view = render(
      <CompanyCard
        language="en"
        row={{
          feature_id: 'feat-invented-tower-aleph',
          row_id: 'row-aleph-one',
          fields: [
            {
              key: 'trade_name',
              segments: [
                {
                  kind: 'reference',
                  referenceKind: 'published_text',
                  value: 'House 4',
                  recordId: 'row-aleph-one-name',
                },
              ],
            },
          ],
        }}
      />,
    );
    expect(
      view.container.querySelector('[data-fact-chip="reference"]'),
    ).toBeTruthy();
    expect(view.container.textContent).toContain('House 4');
  });
});
