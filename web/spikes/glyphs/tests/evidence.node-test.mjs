import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import {
  BASELINE_IDS,
  REMOTE_FONT,
  REVIEW_APPROVED,
  REVIEW_PENDING,
  arabicNames,
  judgeNames,
} from '../guards.mjs';
import { judgeEvidence, judgeHash, judgeReview } from '../verify-evidence.mjs';

function reviewText(state) {
  const strings = arabicNames().map((name) => `- ${name}: ${state}`);
  const images = BASELINE_IDS.map(
    (id) => `- ${id}-chromium-linux.png: ${state}`,
  );
  return [
    '# Visual review of the glyph spike',
    '',
    'Reviewer role: native reader, the project owner',
    'Review date: pending',
    `Verdict: ${state}`,
    '',
    '## Strings',
    '',
    ...strings,
    '',
    '## Images',
    '',
    ...images,
    '',
  ].join('\n');
}

test('missing evidence names the missing file', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-spike-evidence-'));
  const result = judgeEvidence(dir);
  assert.equal(result.ok, false);
  assert.match(result.detail, /arabic-labels\.png/);
});

test('a changed image whose hash does not match is refused', () => {
  const result = judgeHash({
    expected: 'sha256:abc',
    actual: 'sha256:def',
    file: 'arabic-labels.png',
  });
  assert.equal(result.ok, false);
  assert.match(result.detail, /arabic-labels\.png/);
});

test('an incomplete visual review is refused', () => {
  const result = judgeReview('Verdict: later\n');
  assert.equal(result.ok, false);
  assert.match(result.detail, /pending native review|approved/);
});

test('a missing visual review record is refused', () => {
  const result = judgeReview('');
  assert.equal(result.ok, false);
  assert.match(result.detail, /missing visual review record/);
});

test('a review that omits a string is refused', () => {
  const text = reviewText(REVIEW_PENDING).replace(
    '- منطقة الاختبار ألف: pending native review\n',
    '',
  );
  const result = judgeReview(text);
  assert.equal(result.ok, false);
  assert.match(result.detail, /منطقة الاختبار ألف/);
});

test('a pending review is reported as pending', () => {
  const result = judgeReview(reviewText(REVIEW_PENDING));
  assert.equal(result.ok, true);
  assert.equal(result.state, REVIEW_PENDING);
});

test('an approved review is reported as approved', () => {
  const result = judgeReview(reviewText(REVIEW_APPROVED));
  assert.equal(result.ok, true);
  assert.equal(result.state, REVIEW_APPROVED);
});

test('an unreviewed string mark is refused', () => {
  const places = [{ nameAr: 'منطقة الاختبار ألف', review: 'unreviewed' }];
  const result = judgeNames(places);
  assert.equal(result.ok, false);
  assert.match(result.detail, /unreviewed string/);
});

test('an evidence outcome other than recorded is refused', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-spike-evidence-'));
  for (const name of [
    'arabic-labels.png',
    'english-labels.png',
    'hexagons-below-labels.png',
  ]) {
    fs.writeFileSync(path.join(dir, name), Buffer.from(name));
  }
  fs.writeFileSync(
    path.join(dir, 'run.json'),
    JSON.stringify({ outcome: 'draft', assetHashes: {} }),
  );
  fs.writeFileSync(path.join(dir, 'network.json'), '{}\n');
  fs.writeFileSync(path.join(dir, 'asset-manifest.json'), '{}\n');
  fs.writeFileSync(
    path.join(dir, 'visual-review.md'),
    reviewText(REVIEW_PENDING),
  );
  const result = judgeEvidence(dir);
  assert.equal(result.ok, false);
  assert.match(result.detail, /recorded/);
});

test('a review state that differs from the strings is refused', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-spike-evidence-'));
  const hashes = {};
  for (const name of [
    'arabic-labels.png',
    'english-labels.png',
    'hexagons-below-labels.png',
  ]) {
    const bytes = Buffer.from(`synthetic ${name}`);
    fs.writeFileSync(path.join(dir, name), bytes);
    hashes[name] = `sha256:${createHash('sha256').update(bytes).digest('hex')}`;
  }
  fs.writeFileSync(
    path.join(dir, 'run.json'),
    JSON.stringify({ outcome: 'recorded', assetHashes: hashes }),
  );
  fs.writeFileSync(
    path.join(dir, 'network.json'),
    JSON.stringify({ requests: [{ url: REMOTE_FONT, decision: 'blocked' }] }),
  );
  fs.writeFileSync(path.join(dir, 'asset-manifest.json'), '{}\n');
  fs.writeFileSync(
    path.join(dir, 'visual-review.md'),
    reviewText(REVIEW_APPROVED),
  );
  const result = judgeEvidence(dir);
  assert.equal(result.ok, false);
  assert.match(result.detail, /pending native review|approved/);
});

test('a complete pending record passes', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-spike-evidence-'));
  const hashes = {};
  for (const name of [
    'arabic-labels.png',
    'english-labels.png',
    'hexagons-below-labels.png',
  ]) {
    const bytes = Buffer.from(`synthetic ${name}`);
    fs.writeFileSync(path.join(dir, name), bytes);
    hashes[name] = `sha256:${createHash('sha256').update(bytes).digest('hex')}`;
  }
  fs.writeFileSync(
    path.join(dir, 'run.json'),
    JSON.stringify({ outcome: 'recorded', assetHashes: hashes }),
  );
  fs.writeFileSync(
    path.join(dir, 'network.json'),
    JSON.stringify({
      requests: [{ url: REMOTE_FONT, decision: 'blocked' }],
    }),
  );
  fs.writeFileSync(path.join(dir, 'asset-manifest.json'), '{}\n');
  fs.writeFileSync(
    path.join(dir, 'visual-review.md'),
    reviewText(REVIEW_PENDING),
  );
  const result = judgeEvidence(dir);
  assert.equal(result.ok, true, result.detail);
  assert.equal(result.state, REVIEW_PENDING);
});
