import assert from 'node:assert/strict';
import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
  symlinkSync,
} from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { test } from 'node:test';
import { baselineProblems } from '../../tests/question_lab/baselines.mjs';

test('S3-T21 pixel gate fails missing, local, unapproved, changed and escaping baselines', () => {
  const tmp = path.resolve('../.overnight/tmp');
  mkdirSync(tmp, { recursive: true });
  const root = mkdtempSync(path.join(tmp, 'lab-baseline-fixture-'));
  try {
    const bytes = Buffer.from('INVENTED-image-fixture-not-a-baseline');
    writeFileSync(path.join(root, 'INVENTED.png'), bytes);
    const manifest = {
      origin: 'CI',
      review: 'APPROVED',
      entries: [
        {
          path: 'INVENTED.png',
          sha256: createHash('sha256').update(bytes).digest('hex'),
        },
      ],
    };
    assert.deepEqual(baselineProblems(root, manifest), []);
    for (const plant of [
      null,
      { ...manifest, origin: 'local' },
      { ...manifest, review: 'waiting' },
      { ...manifest, entries: [] },
    ])
      assert.ok(
        baselineProblems(root, plant).includes(
          'pixel:approved_CI_baselines_required',
        ),
      );
    writeFileSync(path.join(root, 'INVENTED.png'), 'INVENTED-corrupted-image');
    assert.deepEqual(baselineProblems(root, manifest), ['pixel:hash']);
    writeFileSync(
      path.join(root, 'INVENTED-target.png'),
      'INVENTED-different-target',
    );
    symlinkSync(
      path.join(root, 'INVENTED-target.png'),
      path.join(root, 'INVENTED-link.png'),
    );
    assert.deepEqual(
      baselineProblems(root, {
        ...manifest,
        entries: [{ ...manifest.entries[0], path: 'INVENTED-link.png' }],
      }),
      ['pixel:missing_or_link'],
    );
    assert.deepEqual(
      baselineProblems(root, {
        ...manifest,
        entries: [{ path: '../INVENTED.png', sha256: 'ab'.repeat(32) }],
      }),
      ['pixel:manifest'],
    );
    rmSync(path.join(root, 'INVENTED.png'));
    assert.deepEqual(baselineProblems(root, manifest), [
      'pixel:missing_or_link',
    ]);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('S3-T21 sampler counts identities and complete language pairs, with no repetition credit', () => {
  const manifest = JSON.parse(
    readFileSync('../evals/question_lab/cases.v1.json', 'utf8'),
  );
  assert.equal(manifest.cases.length, 100);
  assert.equal(new Set(manifest.cases.map((row) => row.identity)).size, 100);
  assert.equal(new Set(manifest.cases.map((row) => row.pin)).size, 100);
  assert.ok(
    manifest.cases.every(
      (row) => Object.keys(row.questions).sort().join() === 'ar,en',
    ),
  );
});
