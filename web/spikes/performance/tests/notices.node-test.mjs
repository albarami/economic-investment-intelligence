import assert from 'node:assert/strict';
import fs from 'node:fs';
import { test } from 'node:test';

const REVIEW = 'pending native review';
const NOTICES = new URL('../notices.json', import.meta.url);
const PAGE = new URL('../main.ts', import.meta.url);

function pageArabic(source, notices) {
  const shown = source.match(/show\(\s*'#notice',\s*arabic \? ([^:]+?) :/);
  if (shown === null) return '';
  const expression = shown[1].trim();
  if (expression === 'notices.arabic.text') return notices.arabic.text;
  const literal = expression.match(/^'([^']*)'$/);
  return literal === null ? '' : literal[1];
}

test('the Arabic notice is marked pending native review and the page shows it', () => {
  let review = '';
  let marked = '';
  let shown = '';
  if (fs.existsSync(NOTICES)) {
    const notices = JSON.parse(fs.readFileSync(NOTICES, 'utf8'));
    review = notices.arabic?.review ?? '';
    marked = notices.arabic?.text ?? '';
    shown = pageArabic(fs.readFileSync(PAGE, 'utf8'), notices);
  }
  assert.equal(review, REVIEW);
  assert.equal(shown, marked);
});
