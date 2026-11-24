// @vitest-environment jsdom
import { cleanup, fireEvent, render, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { catalogue } from '../../src/brief/catalogue';
import { AnswerShell } from '../../src/shell/AnswerShell';
import { completeRegistry, factId } from '../fixtures/facts';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const draft = {
  catalogueVersion: catalogue.version,
  accountingPassed: true,
  subject: 'area' as const,
  componentKey: 'foundation_note',
  props: [],
  directive: null,
  slots: [
    { factId: factId(0), provenance: 'public' as const, metric: 'people' },
  ],
};

for (const language of ['en', 'ar'] as const) {
  for (const theme of ['dark', 'light'] as const) {
    describe(`phone sheet ${language} ${theme}`, () => {
      function mount() {
        return render(
          <AnswerShell
            language={language}
            theme={theme}
            extractUrl={null}
            registry={completeRegistry()}
            draft={draft}
          />,
        );
      }

      it('keeps focus when hiding the control blurs it before the media event', () => {
        let matches = true;
        const phone = new EventTarget();
        Object.defineProperty(phone, 'matches', { get: () => matches });
        vi.stubGlobal('matchMedia', () => phone);
        const view = mount();
        const button = within(view.container).getByRole('button', {
          name: language === 'ar' ? 'توسيع الموجز' : 'Expand Brief',
        });
        button.focus();
        matches = false;
        button.blur();
        expect(document.activeElement).toBe(document.body);
        phone.dispatchEvent(new Event('change'));
        expect(document.activeElement).toBe(
          view.container.querySelector('.brief'),
        );
      });

      it('does not move focus when the user left the control before resizing', () => {
        let matches = true;
        const phone = new EventTarget();
        Object.defineProperty(phone, 'matches', { get: () => matches });
        vi.stubGlobal('matchMedia', () => phone);
        const view = mount();
        const button = within(view.container).getByRole('button', {
          name: language === 'ar' ? 'توسيع الموجز' : 'Expand Brief',
        });
        const chip = view.container.querySelector<HTMLElement>(
          '.brief [data-fact-chip]',
        );
        if (!chip) throw new Error('missing chip');
        button.focus();
        chip.focus();
        matches = false;
        phone.dispatchEvent(new Event('change'));
        expect(document.activeElement).toBe(chip);
      });

      it('keeps the answer in a named, controlled sheet in both states', () => {
        const view = mount();
        const button = within(view.container).getByRole('button', {
          name: language === 'ar' ? 'توسيع الموجز' : 'Expand Brief',
        });
        const sheet = view.container.querySelector('.answer-sheet');
        expect(sheet?.contains(view.container.querySelector('.brief'))).toBe(
          true,
        );
        expect(sheet?.getAttribute('data-expanded')).toBe('false');
        expect(button.getAttribute('aria-expanded')).toBe('false');
        const region = document.getElementById(
          button.getAttribute('aria-controls') ?? '',
        );
        expect(region).toBe(view.container.querySelector('.brief'));
        expect(region?.querySelector('[data-fact-chip]')).toBeTruthy();
        fireEvent.click(button);
        expect(button.getAttribute('aria-expanded')).toBe('true');
        expect(button.textContent).toBe(
          language === 'ar' ? 'طي الموجز' : 'Collapse Brief',
        );
        expect(sheet?.getAttribute('data-expanded')).toBe('true');
        expect(region?.querySelector('[data-fact-chip]')).toBeTruthy();
        fireEvent.click(button);
        expect(button.getAttribute('aria-expanded')).toBe('false');
        expect(/\p{Nd}/u.test(button.textContent ?? '')).toBe(false);
      });

      it('Escape collapses the sheet and returns focus to its control', () => {
        const view = mount();
        const button = within(view.container).getByRole('button', {
          name: language === 'ar' ? 'توسيع الموجز' : 'Expand Brief',
        });
        fireEvent.click(button);
        const chip = view.container.querySelector<HTMLElement>(
          '.brief [data-fact-chip]',
        );
        if (!chip) throw new Error('missing chip');
        chip.focus();
        fireEvent.keyDown(chip, { key: 'Escape' });
        expect(button.getAttribute('aria-expanded')).toBe('false');
        expect(document.activeElement).toBe(button);
        expect(
          view.container.querySelector('.stage')?.hasAttribute('inert'),
        ).toBe(false);
      });

      it('drawer closure restores its chip without collapsing or trapping the sheet', () => {
        const view = mount();
        const button = within(view.container).getByRole('button', {
          name: language === 'ar' ? 'توسيع الموجز' : 'Expand Brief',
        });
        fireEvent.click(button);
        const chip = view.container.querySelector<HTMLElement>(
          '.brief [data-fact-chip]',
        );
        if (!chip) throw new Error('missing chip');
        for (const method of ['escape', 'button'] as const) {
          chip.focus();
          fireEvent.click(chip);
          const close = within(view.container).getByRole('button', {
            name: language === 'ar' ? 'إغلاق' : 'Close',
          });
          expect(document.activeElement).toBe(close);
          expect(
            view.container
              .querySelector('.answer-sheet')
              ?.hasAttribute('inert'),
          ).toBe(true);
          if (method === 'escape') fireEvent.keyDown(close, { key: 'Escape' });
          else fireEvent.click(close);
          expect(document.activeElement).toBe(chip);
          expect(view.container.querySelector('[role="dialog"]')).toBeNull();
          expect(button.getAttribute('aria-expanded')).toBe('true');
          expect(
            view.container
              .querySelector('.answer-sheet')
              ?.hasAttribute('inert'),
          ).toBe(false);
        }
      });
    });
  }
}
