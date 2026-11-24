/** DOM rendering for the credit-place scan; test tooling only. */
import vm from 'node:vm';

import { JSDOM } from 'jsdom';

const CREDIT_GLOBAL = '__EII_CREDIT_PLACE__';
const ROOT_ID = 'credit-place-root';
const RENDER_WAIT_MS = 5000;
const RENDER_POLL_MS = 20;
const SATELLITE_LABEL = 'Satellite';

/**
 * @param {ParentNode} root
 * @param {string} credit
 * @returns {{ inside: number, outside: number }}
 */
export function placeCredit(root, credit) {
  const hits = { inside: 0, outside: 0 };
  if (credit.length === 0) return hits;
  const view = root.ownerDocument?.defaultView;
  if (!view) return hits;
  const walker = root.ownerDocument.createTreeWalker(
    root,
    view.NodeFilter.SHOW_TEXT,
  );
  /** @type {{ text: string, allowed: boolean }[]} */
  const parts = [];
  let current = walker.nextNode();
  while (current) {
    parts.push({
      text: current.nodeValue ?? '',
      allowed: allowedText(current),
    });
    current = walker.nextNode();
  }
  let combined = '';
  /** @type {{ start: number, end: number, allowed: boolean }[]} */
  const ranges = [];
  for (const part of parts) {
    const start = combined.length;
    combined += part.text;
    ranges.push({ start, end: combined.length, allowed: part.allowed });
  }
  let from = 0;
  while (from < combined.length) {
    const at = combined.indexOf(credit, from);
    if (at < 0) break;
    const end = at + credit.length;
    const allowed = ranges.every((range) => {
      const overlaps =
        range.end > range.start && range.end > at && range.start < end;
      return !overlaps || range.allowed;
    });
    if (allowed) hits.inside += 1;
    else hits.outside += 1;
    from = end;
  }
  return hits;
}

/**
 * @param {string} html
 * @param {string} credit
 * @returns {{ inside: number, outside: number }}
 */
export function pageCreditPlace(html, credit) {
  const dom = new JSDOM(`<!doctype html><html><body>${html}</body></html>`);
  try {
    return placeCredit(dom.window.document.body, credit);
  } finally {
    dom.window.close();
  }
}

/**
 * @param {Node} node
 */
function allowedText(node) {
  const parent = node.parentElement;
  if (!parent) return false;
  const details = parent.closest('details');
  if (!details || details.open || details.hasAttribute('open')) return false;
  let cursor = details.parentElement;
  while (cursor) {
    if (
      cursor.getAttribute('data-part') === 'attribution' ||
      cursor.classList.contains('stage-credits')
    ) {
      return true;
    }
    cursor = cursor.parentElement;
  }
  return false;
}

/**
 * @param {string} script
 * @param {string} credit
 */
export async function renderBuiltStage(script, credit) {
  const dom = new JSDOM(
    `<!doctype html><html><body><div id="${ROOT_ID}"></div></body></html>`,
    {
      pretendToBeVisual: true,
      runScripts: 'dangerously',
      url: 'http://127.0.0.1/',
    },
  );
  const { window } = dom;
  try {
    window[CREDIT_GLOBAL] = credit;
    window.fetch = mapModesFetch();
    vm.runInContext(script, dom.getInternalVMContext());
    const button = await waitFor(RENDER_WAIT_MS, () => {
      const found = [
        ...window.document.querySelectorAll('[role="radio"]'),
      ].find((node) => node.textContent === SATELLITE_LABEL && !node.disabled);
      return found ?? null;
    });
    button.click();
    await waitFor(RENDER_WAIT_MS, () => {
      const place = placeCredit(window.document.body, credit);
      return place.inside > 0 || place.outside > 0 ? place : null;
    });
    const place = placeCredit(window.document.body, credit);
    if (place.outside > 0) return 'credit-outside-collapsed';
    if (place.inside === 0) return 'credit-place-missing';
    return 'credit-place-ok';
  } finally {
    window.close();
  }
}

function mapModesFetch() {
  const body = {
    open: { available: true, reason: null },
    satellite: { available: true, reason: null },
    photoreal: { available: false, reason: 'offline', meter: null },
  };
  return async (input) => {
    const url = String(input);
    if (url === '/api/map-modes') {
      return { ok: true, json: async () => body };
    }
    return { ok: false, status: 404, json: async () => null };
  };
}

/**
 * @template T
 * @param {number} timeoutMs
 * @param {() => T | null} read
 * @returns {Promise<T>}
 */
function waitFor(timeoutMs, read) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      try {
        const value = read();
        if (value) {
          resolve(value);
          return;
        }
      } catch (error) {
        reject(error instanceof Error ? error : new Error('credit-place-wait'));
        return;
      }
      if (Date.now() - started >= timeoutMs) {
        reject(new Error('credit-place-timeout'));
        return;
      }
      setTimeout(tick, RENDER_POLL_MS);
    };
    tick();
  });
}
