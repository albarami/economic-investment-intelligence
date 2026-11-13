import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { validateGate } from './trace.mjs';

const CAPTURE_KEYS = ['role', 'date', 'host', 'browser', 'trace', 'sha256'];
const SPIKE = path.dirname(fileURLToPath(import.meta.url));

export function parseCapture(text) {
  if (typeof text !== 'string')
    return { ok: false, failure: 'malformed-capture' };
  const record = {};
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (trimmed === '' || trimmed.startsWith('#')) continue;
    const split = trimmed.indexOf(':');
    if (split <= 0) return { ok: false, failure: 'malformed-capture' };
    const key = trimmed.slice(0, split).trim();
    const value = trimmed.slice(split + 1).trim();
    if (
      value === '' ||
      !CAPTURE_KEYS.includes(key) ||
      Object.hasOwn(record, key)
    ) {
      return { ok: false, failure: 'malformed-capture' };
    }
    record[key] = value;
  }
  for (const key of CAPTURE_KEYS) {
    if (!Object.hasOwn(record, key))
      return { ok: false, failure: 'malformed-capture' };
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(record.date)) {
    return { ok: false, failure: 'malformed-capture' };
  }
  return { ok: true, record };
}

export function gitState(root, relative) {
  const listed = spawnSync(
    'git',
    ['ls-files', '--error-unmatch', '--', relative],
    { cwd: root, encoding: 'utf8' },
  );
  if (listed.status !== 0) return 'untracked';
  const diff = spawnSync('git', ['diff', '--quiet', 'HEAD', '--', relative], {
    cwd: root,
    encoding: 'utf8',
  });
  if (diff.status !== 0) return 'changed';
  return 'clean';
}

function hashFile(file) {
  return `sha256:${createHash('sha256').update(fs.readFileSync(file)).digest('hex')}`;
}

export function verifyEvidence(options) {
  const capturePath = path.join(options.evidenceDir, 'native-capture.md');
  if (!fs.existsSync(capturePath)) {
    return { ok: false, failure: 'missing-native-trace' };
  }
  const parsed = parseCapture(fs.readFileSync(capturePath, 'utf8'));
  if (!parsed.ok) return parsed;
  const relative = parsed.record.trace;
  if (path.isAbsolute(relative) || relative.includes('..')) {
    return { ok: false, failure: 'non-native' };
  }
  const file = path.resolve(options.root, relative);
  const evidence = path.resolve(options.evidenceDir);
  if (!file.startsWith(`${evidence}${path.sep}`)) {
    return { ok: false, failure: 'non-native' };
  }
  if (!fs.existsSync(file))
    return { ok: false, failure: 'missing-native-trace' };
  const git = options.git ?? ((item) => gitState(options.root, item));
  const captureRelative = path.relative(options.root, capturePath);
  for (const item of [relative, captureRelative]) {
    const state = git(item);
    if (state === 'untracked' || state === 'missing') {
      return { ok: false, failure: 'uncommitted-trace' };
    }
    if (state !== 'clean') return { ok: false, failure: 'changed-trace' };
  }
  if (hashFile(file) !== parsed.record.sha256) {
    return { ok: false, failure: 'changed-trace' };
  }
  let trace;
  try {
    trace = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return { ok: false, failure: 'malformed-payload' };
  }
  const descriptor = options.descriptor ?? trace.layerSet;
  return validateGate(trace, descriptor, {
    role: parsed.record.role,
    host: parsed.record.host,
    browser: parsed.record.browser,
    tracePath: relative,
    sha256: parsed.record.sha256,
  });
}

function main() {
  const root = path.resolve(SPIKE, '..', '..', '..');
  const result = verifyEvidence({
    root,
    evidenceDir: path.join(SPIKE, 'evidence'),
  });
  if (!result.ok) {
    console.error(`FAIL ${result.failure}`);
    process.exitCode = 1;
    return;
  }
  console.log('native frame-rate gate passed');
}

if (
  process.argv[1] &&
  fileURLToPath(import.meta.url) === path.resolve(process.argv[1])
) {
  main();
}
