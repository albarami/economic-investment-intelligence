// @vitest-environment jsdom
import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { PublicLayers } from '../../src/stage/layers/PublicLayers';
import { acceptPayload } from '../../src/stage/layers/refuse';
import { SYNTHETIC_COMPANY } from '../fixtures/facts';
import { fcPayload, fcRegistry } from '../fixtures/fc-firms';

afterEach(() => {
  cleanup();
});

function plant(field: Record<string, string>) {
  const payload = fcPayload();
  const company = payload.fc_firms?.companies[0];
  if (!company) throw new Error('missing row');
  Object.assign(company, field);
  return payload;
}

describe('firms by tower guards', () => {
  it('renders the checked section even if the raw section changes after validation', () => {
    const payload = fcPayload();
    const section = payload.fc_firms;
    if (!section) throw new Error('missing section');
    let reads = 0;
    Object.defineProperty(payload, 'fc_firms', {
      get: () => {
        reads += 1;
        return reads === 1 ? section : { ...section, no_data: 'yes' };
      },
    });
    const view = render(
      <PublicLayers
        language="en"
        payload={payload}
        registry={fcRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    expect(
      view.container.querySelector('[data-part="fc-firms-legend"]'),
    ).toBeTruthy();
    expect(view.container.querySelector('[data-swatch="no-data"]')).toBeNull();
  });

  it.each(['no_data', 'row_wage', 'field_wage'])(
    'refuses a planted %s before any firms chrome renders',
    (plant) => {
      const payload = fcPayload();
      const section = payload.fc_firms;
      const company = section?.companies[0];
      const field = company?.fields[0];
      if (!section || !company || !field) throw new Error('missing fixture');
      if (plant === 'no_data') Object.assign(section, { no_data: 'yes' });
      if (plant === 'row_wage') Object.assign(company, { wage: 'planted' });
      if (plant === 'field_wage') Object.assign(field, { wage: 'planted' });
      expect(acceptPayload(payload, fcRegistry()).ok).toBe(false);
      const view = render(
        <PublicLayers
          language="en"
          payload={payload}
          registry={fcRegistry()}
          onOpenChain={() => undefined}
        />,
      );
      expect(
        view.container.querySelector('[data-part="fc-firms-legend"]'),
      ).toBeNull();
      expect(
        view.container.querySelector('[data-part="fc-firms-tower-panel"]'),
      ).toBeNull();
    },
  );

  it('test_a_planted_wage_reaches_no_layer_label_legend_or_panel', () => {
    const payload = plant({ wage_key: 'wage' });
    const accepted = acceptPayload(payload, fcRegistry());
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('wage_or_synthetic_id');
    const view = render(
      <PublicLayers
        language="en"
        payload={payload}
        registry={fcRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    expect(
      view.container.querySelector('[data-part="fc-firms-legend"]'),
    ).toBeNull();
    expect(
      view.container.querySelector('[data-part="fc-firms-tower-panel"]'),
    ).toBeNull();
    expect(view.container.textContent).not.toContain('wage');
  });

  it('test_a_planted_syn_field_text_is_refused', () => {
    const payload = fcPayload();
    const company = payload.fc_firms?.companies[0];
    if (!company) throw new Error('missing row');
    company.fields = [
      { key: 'trade_name', text: 'Invented House Aleph' },
      { key: 'activity', text: 'SYN-INVENTED' },
    ];
    const accepted = acceptPayload(payload, fcRegistry());
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('wage_or_synthetic_id');
  });

  it('test_an_unknown_card_field_key_is_refused', () => {
    const payload = fcPayload();
    const company = payload.fc_firms?.companies[0];
    if (!company) throw new Error('missing row');
    company.fields = [
      { key: 'trade_name', text: 'Invented House Aleph' },
      { key: 'jobs', text: 'Sample finance activity' },
    ];
    const accepted = acceptPayload(payload, fcRegistry());
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('wage_or_synthetic_id');
  });

  it('test_a_planted_syn_segment_reaches_no_legend_panel_or_card', () => {
    const payload = fcPayload();
    const company = payload.fc_firms?.companies[0];
    if (!company) throw new Error('missing row');
    company.fields = [
      { key: 'trade_name', text: 'Invented House Aleph' },
      {
        key: 'activity',
        segments: [{ kind: 'plain', text: 'SYN-INVENTED' }],
      },
    ];
    const accepted = acceptPayload(payload, fcRegistry());
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('wage_or_synthetic_id');
    const view = render(
      <PublicLayers
        language="en"
        payload={payload}
        registry={fcRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    expect(view.container.textContent).not.toContain('SYN-INVENTED');
    expect(
      view.container.querySelector('[data-part="fc-firms-legend"]'),
    ).toBeNull();
    expect(
      view.container.querySelector('[data-part="fc-firms-tower-panel"]'),
    ).toBeNull();
    expect(
      view.container.querySelector('[data-part="company-card"]'),
    ).toBeNull();
  });

  it('test_a_planted_syn_reference_segment_is_refused', () => {
    const payload = fcPayload();
    const company = payload.fc_firms?.companies[0];
    if (!company) throw new Error('missing row');
    company.fields = [
      { key: 'trade_name', text: 'Invented House Aleph' },
      {
        key: 'activity',
        segments: [
          {
            kind: 'reference',
            referenceKind: 'published_text',
            value: 'SYN-INVENTED',
            recordId: 'rec-sample',
          },
        ],
      },
    ];
    const accepted = acceptPayload(payload, fcRegistry());
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('wage_or_synthetic_id');
  });

  it('test_a_planted_syn_reference_record_is_refused', () => {
    const payload = fcPayload();
    const company = payload.fc_firms?.companies[0];
    if (!company) throw new Error('missing row');
    company.fields = [
      { key: 'trade_name', text: 'Invented House Aleph' },
      {
        key: 'activity',
        segments: [
          {
            kind: 'reference',
            referenceKind: 'published_text',
            value: 'Sample finance activity',
            recordId: 'SYN-INVENTED',
          },
        ],
      },
    ];
    const accepted = acceptPayload(payload, fcRegistry());
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('wage_or_synthetic_id');
  });

  it('test_a_planted_syn_identifier_reaches_no_layer_label_legend_or_card', () => {
    const payload = plant({ identifier: SYNTHETIC_COMPANY });
    const accepted = acceptPayload(payload, fcRegistry());
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('wage_or_synthetic_id');
    const view = render(
      <PublicLayers
        language="en"
        payload={payload}
        registry={fcRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    expect(view.container.textContent).not.toContain(SYNTHETIC_COMPANY);
    expect(
      view.container.querySelector('[data-part="company-card"]'),
    ).toBeNull();
  });

  it('test_a_planted_labour_or_residence_detail_reaches_no_layer', () => {
    const payload = plant({ attached: 'a residence note' });
    const accepted = acceptPayload(payload, fcRegistry());
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('wage_or_synthetic_id');
    const view = render(
      <PublicLayers
        language="en"
        payload={payload}
        registry={fcRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    expect(view.container.textContent).not.toContain('residence');
  });

  it('test_every_numeral_renders_through_a_fact_chip', () => {
    const view = render(
      <PublicLayers
        language="en"
        payload={fcPayload()}
        registry={fcRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    const legend = view.container.querySelector(
      '[data-part="fc-firms-legend"]',
    );
    const chips = legend?.querySelectorAll('.chip-num') ?? [];
    expect(chips.length).toBeGreaterThan(0);
    for (const chip of chips) {
      expect(chip.closest('[data-fact-chip]')).toBeTruthy();
    }
  });

  it('test_every_legend_break_binds_to_a_count_fact_of_the_layer', () => {
    const payload = fcPayload({ count_without_fact: true });
    const accepted = acceptPayload(payload, fcRegistry());
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('legend_count_unbound');
  });

  it('test_a_count_fact_with_no_year_is_refused', () => {
    const payload = fcPayload();
    payload.count_facts = [
      { fact_id: payload.count_fact_ids?.[0] ?? '', year: '' },
    ];
    const accepted = acceptPayload(payload, fcRegistry());
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('fdi_year_missing');
  });

  it('test_no_employee_count_or_job_figure_appears_for_a_financial_centre_company', () => {
    const payload = plant({ employee_count: '4' });
    const accepted = acceptPayload(payload, fcRegistry());
    expect(accepted.ok).toBe(false);
    if (!accepted.ok) expect(accepted.code).toBe('wage_or_synthetic_id');
  });
});
