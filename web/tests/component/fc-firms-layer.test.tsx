// @vitest-environment jsdom
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import ar from '../../src/i18n/ar.json';
import en from '../../src/i18n/en.json';
import { FactChip } from '../../src/facts/FactChip';
import { PublicLayers } from '../../src/stage/layers/PublicLayers';
import { rampToken } from '../../src/stage/layers/ramp';
import { factId } from '../fixtures/facts';
import { fcPayload, fcRegistry } from '../fixtures/fc-firms';
import { layerRegistry } from '../fixtures/layer-registry';

afterEach(() => {
  cleanup();
});

function plate(payload = fcPayload(), value = 4) {
  return render(
    <PublicLayers
      language="en"
      payload={payload}
      registry={fcRegistry(value)}
      onOpenChain={() => undefined}
    />,
  );
}

describe('firms by tower layer', () => {
  it('test_selecting_a_tower_lists_its_register_companies', () => {
    const view = plate();
    fireEvent.click(view.getByRole('button', { name: 'Invented Tower Aleph' }));
    expect(
      view.getByRole('button', { name: 'Invented House Aleph' }),
    ).toBeTruthy();
    expect(
      view.getByRole('button', { name: 'Invented House Aleph Two' }),
    ).toBeTruthy();
  });

  it('test_a_row_opens_the_company_card', () => {
    const view = plate();
    fireEvent.click(view.getByRole('button', { name: 'Invented Tower Aleph' }));
    fireEvent.click(view.getByRole('button', { name: 'Invented House Aleph' }));
    expect(
      view.container
        .querySelector('[data-part="company-card"]')
        ?.getAttribute('data-row'),
    ).toBe('row-aleph-one');
  });

  it('test_selecting_a_tower_shows_exactly_one_panel', () => {
    const view = plate();
    fireEvent.click(view.getByRole('button', { name: 'Invented Tower Aleph' }));
    expect(
      view.container.querySelectorAll('[data-part="fc-firms-tower-panel"]')
        .length,
    ).toBe(1);
    expect(
      view.container.querySelector('[data-part="feature-panel"]'),
    ).toBeNull();
  });

  it('test_selecting_a_district_fill_shows_its_count_and_no_company_rows', () => {
    const view = plate();
    fireEvent.click(
      view.getByRole('button', { name: 'Invented North District' }),
    );
    const panel = view.container.querySelector(
      '[data-part="fc-firms-tower-panel"]',
    );
    expect(panel?.getAttribute('data-form')).toBe('district');
    expect(panel?.querySelector('[data-company]')).toBeNull();
    expect(panel?.textContent).toContain(
      'These firms are placed at district level.',
    );
    expect(panel?.querySelector('[data-fact-chip]')).toBeTruthy();
  });

  it('test_a_tower_feature_without_a_position_draws_no_mark_but_stays_listed', () => {
    const view = plate();
    expect(
      view.getByRole('button', { name: 'Invented Tower Gimel' }),
    ).toBeTruthy();
  });

  it('test_every_legend_break_binds_to_a_count_fact_of_the_layer', () => {
    const view = plate();
    const legend = view.container.querySelector(
      '[data-part="fc-firms-legend"]',
    );
    const chips = legend?.querySelectorAll('[data-fact-id]') ?? [];
    const ids = [...chips].map((chip) => chip.getAttribute('data-fact-id'));
    const bound = new Set(
      (fcPayload().count_facts ?? []).map((row) => row.fact_id),
    );
    expect(ids.length).toBe(5);
    for (const id of ids) expect(bound.has(id ?? '')).toBe(true);
  });

  it('gives each swatch a size and its ramp colour and no origin word', () => {
    const view = plate();
    const legend = view.container.querySelector(
      '[data-part="fc-firms-legend"]',
    );
    const swatches = [...(legend?.querySelectorAll('li [data-swatch]') ?? [])];
    expect(swatches).toHaveLength(5);
    for (const swatch of swatches) {
      const token = rampToken(swatch.getAttribute('data-swatch') ?? '');
      const style = swatch.getAttribute('style') ?? '';
      const element = swatch as HTMLElement;
      expect(token).toBeTruthy();
      expect(style).toContain(`var(${token})`);
      expect(element.style.width).not.toBe('');
      expect(element.style.height).not.toBe('');
      expect(Number.parseFloat(element.style.width)).toBeGreaterThan(0);
      expect(Number.parseFloat(element.style.height)).toBeGreaterThan(0);
    }
    expect(legend?.textContent).not.toContain('Public');
    expect(legend?.textContent).not.toContain('Synthetic');
    expect(legend?.textContent).not.toContain('Simulated');
    expect(legend?.querySelector('.mark-glyph')).toBeNull();
  });

  it('names a firm count as firms in both languages', () => {
    const english = plate();
    const legend = english.container.querySelector(
      '[data-part="fc-firms-legend"]',
    );
    const chip = legend?.querySelector('[data-fact-chip]');
    expect(chip?.querySelector('.chip-unit')?.textContent).toBe('firms');
    expect(chip?.getAttribute('aria-label')).toContain('firms');
    expect(chip?.querySelector('.chip-unit')?.textContent).not.toBe('people');
    fireEvent.click(
      english.getByRole('button', { name: 'Invented Tower Aleph' }),
    );
    const tower = english.container.querySelector(
      '[data-part="fc-firms-tower-panel"] [data-fact-chip] .chip-unit',
    );
    expect(tower?.textContent).toBe('firms');
    fireEvent.click(
      english.getByRole('button', { name: 'Invented North District' }),
    );
    const district = english.container.querySelector(
      '[data-form="district"] [data-fact-chip] .chip-unit',
    );
    expect(district?.textContent).toBe('firms');
    cleanup();
    const arabic = render(
      <PublicLayers
        language="ar"
        payload={fcPayload()}
        registry={fcRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    const arabicChip = arabic.container.querySelector(
      '[data-part="fc-firms-legend"] [data-fact-chip]',
    );
    expect(arabicChip?.querySelector('.chip-unit')?.textContent).toBe('شركات');
    expect(arabicChip?.getAttribute('aria-label')).toContain('شركات');
    expect(arabicChip?.textContent).not.toContain('أشخاص');
    expect(ar.review['unit.firms']).toBe('pending-native-review');
  });

  it('keeps a people count labelled as people', () => {
    const registry = layerRegistry([
      { id: factId(0), metric: 'people', table: 'pub_place', value: 12 },
    ]);
    const view = render(
      <FactChip
        variant="compact"
        factId={factId(0)}
        registry={registry}
        language="en"
        onOpen={() => undefined}
      />,
    );
    expect(view.container.querySelector('.chip-unit')?.textContent).toBe(
      'people',
    );
    expect(view.container.querySelector('.chip-num')?.textContent).toBe('12');
  });

  it('shows five swatches, the zone sentence and no origin sample', () => {
    const view = plate();
    const legend = view.container.querySelector(
      '[data-part="fc-firms-legend"]',
    );
    expect(legend?.querySelectorAll('[data-swatch]').length).toBe(5);
    expect(legend?.textContent).toContain('lowest');
    expect(legend?.textContent).toContain('highest');
    expect(legend?.textContent).toContain('Show as table');
    expect(legend?.textContent).toContain('Method and source');
    expect(
      legend?.querySelector('[data-note="zone-without-district"]'),
    ).toBeTruthy();
    expect(legend?.querySelector('.mark-glyph')).toBeNull();
    expect(legend?.textContent).not.toContain('Public');
  });

  it('test_no_count_or_break_is_computed_in_the_browser', () => {
    const view = plate(fcPayload(), 4);
    const legend = view.container.querySelector(
      '[data-part="fc-firms-legend"]',
    );
    const chip = legend?.querySelector('.chip-num');
    expect(chip?.textContent).toBe('1');
    expect(fcPayload().fc_firms?.companies.length).toBe(2);
  });

  it('test_no_employee_count_or_job_figure_appears_for_a_financial_centre_company', () => {
    const view = plate();
    fireEvent.click(view.getByRole('button', { name: 'Invented Tower Aleph' }));
    fireEvent.click(view.getByRole('button', { name: 'Invented House Aleph' }));
    const card = view.container.querySelector('[data-part="company-card"]');
    expect(card?.querySelector('[data-field="employee_count"]')).toBeNull();
    expect(card?.textContent).not.toContain('jobs');
  });

  it('keeps the new strings in both languages and pending review', () => {
    const keys = [
      'layers.fc.name',
      'layers.fc.unit',
      'layers.fc.table',
      'layers.fc.nodata',
      'layers.fc.zone',
      'layers.fc.district',
      'layers.fc.method',
    ] as const;
    expect(Object.keys(ar.review).sort()).toEqual(
      Object.keys(en.strings).sort(),
    );
    for (const key of keys) {
      expect(en.strings[key].length).toBeGreaterThan(0);
      expect(ar.strings[key].length).toBeGreaterThan(0);
      expect(ar.review[key]).toBe('pending-native-review');
    }
  });
});
