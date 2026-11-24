import type { Page } from '@playwright/test';
import {
  auditReport,
  type AuditOrder,
  type AuditReport,
  type AuditSpec,
} from './opening-audit';

/**
 * Answer headline and body, map credits, and the inner text of Fact chips.
 * Contrast, clipping and the Arabic type rule share this set.
 */
const DRAW_TEXT =
  '.brief h1,.brief p,.stage-credits,.stage-credits p,[data-fact-chip],[data-fact-chip] span,[data-fact-chip] bdi';

/** Shorter side of a circle's in-viewport box. A few pixels is a dot. */
const MIN_CIRCLE_EXTENT_PX = 48;

/**
 * The area-drawing surfaces share one target set; only the expected DOM
 * reading order changes between screens and phases.
 */
export function drawSpec(order: readonly AuditOrder[]): AuditSpec {
  return {
    name: 'draw',
    critical: '.draw-tools,[data-part="area-summary"]',
    clipped: `.draw-tools p,.draw-tools button,[data-part="area-summary"] p,${DRAW_TEXT}`,
    contrast: `.draw-tools button,.draw-tools p,.draw-tools .chip,[data-part="area-summary"] p,[data-part="area-summary"] .chip,.sheet-toggle,${DRAW_TEXT}`,
    controls: '.draw-tools button,.draw-crosshair,.draw-knob,.sheet-toggle',
    groups:
      'html,.draw-tools,.draw-tools [role="group"],.draw-tools [data-part="presets"],.answer-sheet,.brief-column,[data-part="area-summary"],.sheet-toggle',
    inside: [
      ['.draw-tools', '.stage-column'],
      ['[data-part="area-summary"]', '.brief-column'],
    ],
    apart: [
      ['.draw-tools', '.answer-sheet'],
      ['.draw-tools', '.brief-column'],
    ],
    order,
    focus: '.draw-tools button,.draw-crosshair,.draw-knob,.sheet-toggle',
  };
}

export async function drawReport(
  page: Page,
  order: readonly AuditOrder[],
): Promise<AuditReport> {
  // Chromium applies :focus-visible only under keyboard modality: one real
  // Tab press switches it on so script-focused controls show their ring.
  await page.keyboard.press('Tab');
  return auditReport(page, drawSpec(order));
}

export async function drawProblems(
  page: Page,
  order: readonly AuditOrder[],
): Promise<string[]> {
  return (await drawReport(page, order)).problems;
}

export interface AnswerReadout {
  modeText: string;
  valueText: string;
  unitText: string;
  recordId: string;
}

/** Mode sentence and the selected cut-off chip, exact value, fully in view. */
export async function answerReadoutProblems(
  page: Page,
  readout: AnswerReadout,
): Promise<string[]> {
  return page.evaluate((readout: AnswerReadout) => {
    function fullyInView(node: HTMLElement): boolean {
      const box = node.getBoundingClientRect();
      return (
        box.width > 0 &&
        box.height > 0 &&
        box.top >= -1 &&
        box.left >= -1 &&
        box.bottom <= innerHeight + 1 &&
        box.right <= innerWidth + 1
      );
    }
    function placed(node: HTMLElement | null): node is HTMLElement {
      return (
        node !== null &&
        node.checkVisibility({
          visibilityProperty: true,
          opacityProperty: true,
        }) &&
        fullyInView(node)
      );
    }
    function sameText(node: HTMLElement, expected: string): boolean {
      return (node.textContent ?? '').trim() === expected;
    }
    function shownText(node: HTMLElement | null, expected: string): boolean {
      return placed(node) && sameText(node, expected);
    }
    const problems: string[] = [];
    const mode = document.querySelector<HTMLElement>(
      '[data-part="area-summary"] [data-part="mode-word"]',
    );
    if (!shownText(mode, readout.modeText)) problems.push('mode-missing');
    const chip = document.querySelector<HTMLElement>(
      `[data-part="area-summary"] [data-fact-chip="input"][data-record="${readout.recordId}"]`,
    );
    const numeral = chip?.querySelector<HTMLElement>('.chip-num') ?? null;
    const unit = chip?.querySelector<HTMLElement>('.chip-unit') ?? null;
    if (!placed(numeral) || !sameText(numeral, readout.valueText))
      problems.push('cutoff-missing');
    else if (!placed(unit) || !sameText(unit, readout.unitText))
      problems.push('cutoff-missing');
    return problems;
  }, readout);
}

/** In-viewport box of the circle outline's painted strokes. A stroke shape counts only when it is rendered, its
 * stroke is a colour with some alpha, and its stroke opacity and width are above zero; at least one such shape must
 * span the minimum extent on its own, so the box of an unpainted sibling or of the group never satisfies it. */
export async function circleExtentProblem(page: Page): Promise<string[]> {
  return page.evaluate((minimum: number) => {
    function painted(shape: Element): boolean {
      if (
        !shape.checkVisibility({
          visibilityProperty: true,
          opacityProperty: true,
        })
      )
        return false;
      const style = getComputedStyle(shape);
      const stroke = style.stroke;
      if (stroke === '' || stroke === 'none' || stroke === 'transparent')
        return false;
      const alpha = /^rgba\([^)]*,\s*([\d.]+)\)$/.exec(stroke);
      if (alpha !== null && Number(alpha[1]) === 0) return false;
      return (
        Number.parseFloat(style.strokeOpacity) > 0 &&
        Number.parseFloat(style.strokeWidth) > 0
      );
    }
    function spans(shape: Element): boolean {
      const box = shape.getBoundingClientRect();
      const width = Math.min(box.right, innerWidth) - Math.max(box.left, 0);
      const height = Math.min(box.bottom, innerHeight) - Math.max(box.top, 0);
      return width >= minimum && height >= minimum;
    }
    const node = document.querySelector('[data-outline="circle"]');
    if (!(node instanceof Element)) return ['outline-extent'];
    const shapes = Array.from(
      node.querySelectorAll('circle, path, polyline, polygon, line'),
    );
    return shapes.some((shape) => painted(shape) && spans(shape))
      ? []
      : ['outline-extent'];
  }, MIN_CIRCLE_EXTENT_PX);
}
