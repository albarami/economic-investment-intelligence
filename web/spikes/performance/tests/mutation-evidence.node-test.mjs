import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { parseCapture, verifyEvidence } from '../verify-evidence.mjs';
import * as config from '../config.mjs';
import * as trace from '../trace.mjs';
import { loadModule } from './module-harness.mjs';
import { mutationTrace } from './mutation-fixtures.mjs';
const plain = (x) => JSON.parse(JSON.stringify(x));
const digest = (bytes) =>
  `sha256:${createHash('sha256').update(bytes).digest('hex')}`;
function captureText(relative, sha) {
  return `role: owner\ndate: 2026-11-13\nhost: windows-native\nbrowser: chrome\ntrace: ${relative}\nsha256: ${sha}\n`;
}

test('capture parsing accepts whitespace and comments but rejects every malformed field', () => {
  const text = captureText('synthetic.json', `sha256:${'ab'.repeat(32)}`);
  const parsed = parseCapture(text);
  assert.equal(parsed.ok, true);
  assert.equal(parsed.record.trace, 'synthetic.json');
  assert.deepEqual(
    parseCapture(
      '\n# synthetic\n' +
        text
          .split('\n')
          .map((line) => (line ? '  ' + line + '  ' : line))
          .join('\n'),
    ),
    parsed,
  );
  for (const bad of [
    null,
    1,
    {},
    '',
    ': bad\n' + text,
    'broken\n' + text,
    'unknown: value\n' + text,
    'role: owner\n' + text,
    text.replace('role: owner', 'role: '),
    text.replace('role: owner\n', ''),
    text.replace('2026-11-13', 'x2026-11-13'),
    text.replace('2026-11-13', '2026-11-13x'),
    text.replace('2026-11-13', '26-1-3'),
  ])
    assert.deepEqual(parseCapture(bad), {
      ok: false,
      failure: 'malformed-capture',
    });
});

test('evidence verification checks both tracked files, containment, bytes and JSON', () => {
  const root = fs.mkdtempSync(
    path.join(os.tmpdir(), 'synthetic-verification-'),
  );
  const relative = 'web/spikes/performance/evidence/synthetic.json';
  const file = path.join(root, relative);
  const evidenceDir = path.dirname(file);
  const capture = path.join(evidenceDir, 'native-capture.md');
  fs.mkdirSync(evidenceDir, { recursive: true });
  const options = { root, evidenceDir, git: () => 'clean' };
  const reset = () => {
    const bytes = JSON.stringify(mutationTrace());
    fs.writeFileSync(file, bytes);
    fs.writeFileSync(capture, captureText(relative, digest(bytes)));
  };
  try {
    assert.deepEqual(verifyEvidence({ ...options, descriptor: 'unknown' }), {
      ok: false,
      failure: 'unknown-layer-set',
    });
    assert.deepEqual(verifyEvidence(options), {
      ok: false,
      failure: 'missing-native-trace',
    });
    reset();
    assert.deepEqual(verifyEvidence(options), { ok: true });
    for (const value of ['malformed', 'role: owner\n']) {
      fs.writeFileSync(capture, value);
      assert.deepEqual(verifyEvidence(options), {
        ok: false,
        failure: 'malformed-capture',
      });
    }
    reset();
    for (const destination of [
      path.resolve(root, 'absolute.json'),
      '../synthetic.json',
      'outside.json',
    ]) {
      fs.writeFileSync(capture, captureText(destination, digest('synthetic')));
      assert.deepEqual(verifyEvidence(options), {
        ok: false,
        failure: 'non-native',
      });
    }
    reset();
    fs.unlinkSync(file);
    assert.deepEqual(verifyEvidence(options), {
      ok: false,
      failure: 'missing-native-trace',
    });
    reset();
    for (const faulty of [
      relative,
      'web/spikes/performance/evidence/native-capture.md',
    ]) {
      for (const state of ['untracked', 'missing', 'changed', 'unexpected']) {
        const seen = [];
        const result = verifyEvidence({
          ...options,
          git: (item) => {
            seen.push(item);
            return item === faulty ? state : 'clean';
          },
        });
        assert.deepEqual(result, {
          ok: false,
          failure:
            state === 'missing' || state === 'untracked'
              ? 'uncommitted-trace'
              : 'changed-trace',
        });
        assert.ok(seen.includes(faulty));
      }
    }
    fs.writeFileSync(file, 'changed');
    assert.deepEqual(verifyEvidence(options), {
      ok: false,
      failure: 'changed-trace',
    });
    fs.writeFileSync(file, '{');
    fs.writeFileSync(capture, captureText(relative, digest('{')));
    assert.deepEqual(verifyEvidence(options), {
      ok: false,
      failure: 'malformed-payload',
    });
    reset();
    const bytes = JSON.stringify({ ...mutationTrace(), codeCommit: '' });
    fs.writeFileSync(file, bytes);
    fs.writeFileSync(capture, captureText(relative, digest(bytes)));
    assert.deepEqual(verifyEvidence(options), {
      ok: false,
      failure: 'missing-commit',
    });
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('git-state probes retain command arguments and failure distinctions', async () => {
  for (const [listed, diff, expected] of [
    [1, 0, 'untracked'],
    [0, 1, 'changed'],
    [0, 0, 'clean'],
  ]) {
    const calls = [];
    const m = await loadModule(
      new URL('../verify-evidence.mjs', import.meta.url),
      {
        './config.mjs': config,
        './trace.mjs': trace,
        'node:child_process': {
          spawnSync(command, args, options) {
            calls.push({
              command,
              args: Array.from(args),
              options: plain(options),
            });
            return { status: calls.length === 1 ? listed : diff };
          },
        },
      },
      [],
    );
    assert.equal(m.gitState('synthetic-root', 'synthetic.json'), expected);
    assert.deepEqual(calls[0], {
      command: 'git',
      args: ['ls-files', '--error-unmatch', '--', 'synthetic.json'],
      options: { cwd: 'synthetic-root', encoding: 'utf8' },
    });
    if (listed === 0)
      assert.deepEqual(calls[1], {
        command: 'git',
        args: ['diff', '--quiet', 'HEAD', '--', 'synthetic.json'],
        options: { cwd: 'synthetic-root', encoding: 'utf8' },
      });
    assert.equal(calls.length, listed === 0 ? 2 : 1);
  }
});
