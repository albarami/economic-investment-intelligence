import type { Page } from '@playwright/test';

/** Selector sets a screen audit measures. `name` prefixes its own codes. */
export interface AuditSpec {
  name: string;
  /** Elements that must sit fully inside the viewport. */
  critical: string;
  /** Copy checked for clipping and the Arabic type rule. */
  clipped: string;
  /** Elements measured for a 4.5:1 contrast ratio. */
  contrast: string;
  /** Targets checked for size and viewport overflow. */
  controls: string;
  /** Elements that must carry the interface direction. */
  groups?: string;
  /** (inner, outer) pairs whose inner box stays inside the outer box. */
  inside?: readonly (readonly [string, string])[];
  /** Pairs whose boxes never overlap. */
  apart?: readonly (readonly [string, string])[];
  /** Control groups whose DOM order is their reading order. */
  order?: readonly AuditOrder[];
  /** Interactive elements that must show a focus ring. */
  focus?: string;
}

export interface AuditOrder {
  scope: string;
  /** Reads this attribute; unset derives tool, preset, part then index. */
  attribute?: string;
  expected: readonly string[];
}

export interface ContrastRow {
  selector: string;
  foreground: string;
  background: string;
  ratio: number;
}

export interface AuditReport {
  problems: string[];
  contrast: ContrastRow[];
}

const OPENING_SPEC: AuditSpec = {
  name: 'opening',
  critical:
    '[data-scene="opening"] h1,[data-action="guided-story"],[data-journey="site"]',
  clipped:
    '.public-opening h1,.public-story h1,.resolve-picker label,.public-context-card p',
  contrast:
    '.public-opening button,.public-opening h1,.public-opening p,.opening-language button,.camera-controls button,.map-control-panel > summary,.layer-inspector > summary,.stage-credits,.context-legend',
  controls:
    '.public-opening button,.opening-language button,.camera-controls button,.map-control-panel > summary,.layer-inspector > summary',
};

/** Audits actual layout and accessible copy. It is also used on planted defects. */
export async function auditReport(
  page: Page,
  spec: AuditSpec,
): Promise<AuditReport> {
  return page.evaluate((spec: AuditSpec) => {
    const problems: string[] = [];
    const contrast: ContrastRow[] = [];
    if (document.documentElement.scrollWidth > innerWidth)
      problems.push('page-overflow');
    const critical = document.querySelectorAll<HTMLElement>(spec.critical);
    for (const node of critical) {
      const rect = node.getBoundingClientRect();
      if (
        rect.top < 0 ||
        rect.bottom > innerHeight ||
        rect.left < 0 ||
        rect.right > innerWidth
      )
        problems.push(`${spec.name}-outside-viewport`);
    }
    const stage = document.querySelector<HTMLElement>('.stage');
    const sheet = document.querySelector<HTMLElement>('.answer-sheet');
    if (
      stage &&
      document.querySelector('.stage-host canvas') &&
      !document.querySelector(
        '[role="dialog"],.map-control-panel[open],.layer-inspector[open]',
      )
    ) {
      const rect = stage.getBoundingClientRect();
      const sheetBox = sheet?.getBoundingClientRect();
      const bottom =
        sheetBox && sheetBox.width > 0
          ? Math.min(rect.bottom, sheetBox.top)
          : Math.min(rect.bottom, innerHeight);
      const hit = document.elementFromPoint(
        rect.x + rect.width / 2,
        rect.y + (bottom - rect.y) / 2,
      );
      if (!hit?.closest('.stage-host,.area-overlay'))
        problems.push('map-hidden-by-controls');
    }
    const html = document.documentElement;
    const expected = html.lang === 'ar' ? 'rtl' : 'ltr';
    const shell = document.querySelector<HTMLElement>('.shell');
    if (shell?.dir !== expected) problems.push('wrong-reading-direction');
    if (document.querySelector('.stage')?.getAttribute('dir') !== 'ltr')
      problems.push('mirrored-map');
    if (spec.groups)
      for (const element of document.querySelectorAll<HTMLElement>(
        spec.groups,
      )) {
        if (!element.checkVisibility()) continue;
        if (getComputedStyle(element).direction !== expected)
          problems.push('wrong-group-direction');
      }
    for (const [inner, outer] of spec.inside ?? []) {
      const innerNode = document.querySelector(inner);
      const outerNode = document.querySelector(outer);
      if (!innerNode || !outerNode) continue;
      const innerRect = innerNode.getBoundingClientRect();
      const outerRect = outerNode.getBoundingClientRect();
      if (innerRect.width === 0 || innerRect.height === 0) continue;
      if (
        innerRect.top < outerRect.top - 1 ||
        innerRect.bottom > outerRect.bottom + 1 ||
        innerRect.left < outerRect.left - 1 ||
        innerRect.right > outerRect.right + 1
      )
        problems.push(`${spec.name}-outside-container`);
    }
    for (const [a, b] of spec.apart ?? []) {
      const aNode = document.querySelector(a);
      const bNode = document.querySelector(b);
      if (!aNode || !bNode) continue;
      const aRect = aNode.getBoundingClientRect();
      const bRect = bNode.getBoundingClientRect();
      if (
        aRect.width === 0 ||
        aRect.height === 0 ||
        bRect.width === 0 ||
        bRect.height === 0
      )
        continue;
      const overlap =
        Math.min(aRect.right, bRect.right) - Math.max(aRect.left, bRect.left) >
          1 &&
        Math.min(aRect.bottom, bRect.bottom) - Math.max(aRect.top, bRect.top) >
          1;
      if (overlap) problems.push(`${spec.name}-overlap`);
    }
    for (const group of spec.order ?? []) {
      const keys = [...document.querySelectorAll<HTMLElement>(group.scope)].map(
        (element) =>
          (group.attribute
            ? element.getAttribute(group.attribute)
            : (element.dataset.tool ??
              element.dataset.preset ??
              element.dataset.part ??
              element.dataset.index)) ?? '',
      );
      if (
        keys.length !== group.expected.length ||
        keys.some((key, index) => key !== group.expected[index])
      )
        problems.push(`${spec.name}-reading-order`);
    }
    const prior =
      spec.focus && document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    if (spec.focus)
      for (const element of document.querySelectorAll<HTMLElement>(
        spec.focus,
      )) {
        if (!element.checkVisibility()) continue;
        element.focus();
        const style = getComputedStyle(element);
        if (style.outlineStyle === 'none' || style.outlineWidth === '0px')
          problems.push('focus-hidden');
      }
    if (prior?.isConnected) prior.focus();
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
    );
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const parent = node.parentElement;
      if (
        !parent ||
        !parent.checkVisibility() ||
        parent.closest('script,style,option,[data-fact-chip]')
      )
        continue;
      if (/\p{Nd}/u.test(node.textContent ?? ''))
        problems.push('loose-numeral');
      if (originWord(node.textContent ?? '')) problems.push('origin-word');
    }
    for (const node of document.querySelectorAll<HTMLElement>(
      '[aria-label],[aria-description],[title],[alt]',
    )) {
      const inChip = Boolean(node.closest('[data-fact-chip]'));
      for (const name of ['aria-label', 'aria-description', 'title', 'alt']) {
        const value = node.getAttribute(name);
        if (!value) continue;
        if (!inChip && /\p{Nd}/u.test(value))
          problems.push('accessible-numeral');
        if (originWord(value)) problems.push('accessible-origin');
      }
    }
    for (const element of document.querySelectorAll<HTMLElement>(
      spec.clipped,
    )) {
      if (!element.checkVisibility()) continue;
      const style = getComputedStyle(element);
      if (
        element.scrollWidth > element.clientWidth + 1 ||
        element.scrollHeight > element.clientHeight + 1
      )
        problems.push('clipped-copy');
      if (
        html.lang === 'ar' &&
        (parseFloat(style.lineHeight) / parseFloat(style.fontSize) < 1.5 ||
          parseFloat(style.letterSpacing || '0') > 0)
      )
        problems.push('arabic-type');
    }
    for (const caveat of document.querySelectorAll<HTMLElement>(
      '[data-caveat="night_lights_not_activity"] bdi',
    )) {
      if (
        caveat.checkVisibility() &&
        getComputedStyle(caveat).direction !== expected
      )
        problems.push('wrong-caveat-direction');
    }
    function originWord(value: string): boolean {
      return /(?:^|\W)(?:Public|Synthetic|Simulated)(?:$|\W)|علني|اصطناعي|بالمحاكاة/iu.test(
        value,
      );
    }
    function luminance(color: string): number {
      const channels = (color.match(/[\d.]+/g) ?? [])
        .slice(0, 3)
        .map(Number)
        .map((value) => {
          const channel = value / 255;
          return channel <= 0.04045
            ? channel / 12.92
            : ((channel + 0.055) / 1.055) ** 2.4;
        });
      return (
        channels[0]! * 0.2126 + channels[1]! * 0.7152 + channels[2]! * 0.0722
      );
    }
    for (const element of document.querySelectorAll<HTMLElement>(
      spec.contrast,
    )) {
      if (!element.checkVisibility()) continue;
      // A map canvas is not a DOM background. Credits need an opaque plate;
      // an inherited colour cannot establish contrast against its pixels.
      if (
        element.matches('.stage-credits') &&
        ['transparent', 'rgba(0, 0, 0, 0)'].includes(
          getComputedStyle(element).backgroundColor,
        )
      )
        problems.push('attribution-plate');
      const foreground = luminance(getComputedStyle(element).color);
      let ancestor: HTMLElement | null = element;
      while (
        ancestor &&
        ['transparent', 'rgba(0, 0, 0, 0)'].includes(
          getComputedStyle(ancestor).backgroundColor,
        )
      )
        ancestor = ancestor.parentElement;
      const background = luminance(
        ancestor
          ? getComputedStyle(ancestor).backgroundColor
          : 'rgb(255,255,255)',
      );
      const ratio =
        (Math.max(foreground, background) + 0.05) /
        (Math.min(foreground, background) + 0.05);
      contrast.push({
        selector: element.matches('.stage-credits')
          ? '.stage-credits'
          : element.tagName.toLowerCase(),
        foreground: getComputedStyle(element).color,
        background: ancestor
          ? getComputedStyle(ancestor).backgroundColor
          : 'rgb(255,255,255)',
        ratio,
      });
      if (ratio < 4.5) problems.push('contrast');
    }
    for (const element of document.querySelectorAll<HTMLElement>(
      spec.controls,
    )) {
      if (!element.checkVisibility()) continue;
      const rect = element.getBoundingClientRect();
      if (rect.width < 44 || rect.height < 44) problems.push('small-target');
      if (rect.left < 0 || rect.right > innerWidth + 1)
        problems.push('control-overflow');
    }
    return { problems: [...new Set(problems)], contrast };
  }, spec);
}

export async function openingReport(page: Page): Promise<AuditReport> {
  return auditReport(page, OPENING_SPEC);
}

export async function openingProblems(page: Page): Promise<string[]> {
  return (await openingReport(page)).problems;
}
