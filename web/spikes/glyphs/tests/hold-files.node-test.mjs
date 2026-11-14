import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { withHeldFiles } from './hold-files.mjs';

function fixture(action) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-held-files-'));
  const source = fs.mkdtempSync(new URL('./eii-held-source-', import.meta.url));
  const held = path.join(root, 'held');
  fs.mkdirSync(held);
  fs.writeFileSync(path.join(source, 'first.png'), 'synthetic first');
  fs.writeFileSync(path.join(source, 'second.png'), 'synthetic second');
  try {
    action(source, held);
  } finally {
    fs.rmSync(source, { recursive: true, force: true });
    fs.rmSync(root, { recursive: true, force: true });
  }
}

function restored(source) {
  assert.equal(
    fs.readFileSync(path.join(source, 'first.png'), 'utf8'),
    'synthetic first',
  );
  assert.equal(
    fs.readFileSync(path.join(source, 'second.png'), 'utf8'),
    'synthetic second',
  );
}

test('baseline holding works when rename would cross file systems', (t) => {
  fixture((source, held) => {
    t.mock.method(fs, 'renameSync', () => {
      throw Object.assign(new Error('cross-device link'), { code: 'EXDEV' });
    });
    withHeldFiles(source, held, () => {
      assert.deepEqual(fs.readdirSync(source), []);
      restored(held);
    });
    restored(source);
  });
});

test('a failed assertion always restores held baselines', () => {
  fixture((source, held) => {
    assert.throws(
      () =>
        withHeldFiles(source, held, () => {
          throw new Error('planted assertion');
        }),
      /planted assertion/,
    );
    restored(source);
  });
});

test('a failed second copy restores the first baseline', (t) => {
  fixture((source, held) => {
    const copy = fs.copyFileSync;
    t.mock.method(fs, 'copyFileSync', (from, to, ...args) => {
      if (to === path.join(held, 'second.png'))
        throw new Error('planted copy failure');
      return copy(from, to, ...args);
    });
    assert.throws(
      () => withHeldFiles(source, held, () => assert.fail('must not run')),
      /planted copy failure/,
    );
    restored(source);
  });
});

test('a corrupt copy is refused before deleting the source', (t) => {
  fixture((source, held) => {
    const copy = fs.copyFileSync;
    t.mock.method(fs, 'copyFileSync', (from, to, ...args) => {
      copy(from, to, ...args);
      if (to === path.join(held, 'second.png')) fs.writeFileSync(to, 'corrupt');
    });
    assert.throws(
      () => withHeldFiles(source, held, () => assert.fail('must not run')),
      /copy verification failed/,
    );
    restored(source);
  });
});
