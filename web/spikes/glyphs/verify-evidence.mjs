import { createHash } from 'node:crypto';
import { readFileSync, existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  EVIDENCE_FILES,
  IMAGE_FILES,
  judgeHash,
  judgeNames,
  judgeNetwork,
  judgeReview,
  loadNames,
} from './guards.mjs';

export { judgeHash, judgeReview };

const EVIDENCE_DIR = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  'evidence',
);

function hashFile(file) {
  const bytes = readFileSync(file);
  return `sha256:${createHash('sha256').update(bytes).digest('hex')}`;
}

export function judgeEvidence(dir) {
  for (const name of EVIDENCE_FILES) {
    if (!existsSync(path.join(dir, name))) {
      return { ok: false, detail: `missing evidence file: ${name}`, state: '' };
    }
  }
  const run = JSON.parse(readFileSync(path.join(dir, 'run.json'), 'utf8'));
  if (run.outcome !== 'recorded') {
    return { ok: false, detail: 'evidence outcome is not recorded', state: '' };
  }
  const hashes = run.assetHashes ?? {};
  for (const name of IMAGE_FILES) {
    const actual = hashFile(path.join(dir, name));
    const compared = judgeHash({
      expected: hashes[name],
      actual,
      file: name,
    });
    if (!compared.ok) return compared;
  }
  const names = judgeNames(loadNames().places);
  if (!names.ok) return names;
  const review = judgeReview(
    readFileSync(path.join(dir, 'visual-review.md'), 'utf8'),
  );
  if (!review.ok) return review;
  if (review.state !== names.state) {
    return {
      ok: false,
      detail: 'visual review must be pending native review or approved',
      state: '',
    };
  }
  const network = JSON.parse(
    readFileSync(path.join(dir, 'network.json'), 'utf8'),
  );
  const requests = judgeNetwork(network.requests);
  if (!requests.ok) return requests;
  return { ok: true, detail: '', state: review.state };
}

function main() {
  const result = judgeEvidence(EVIDENCE_DIR);
  if (!result.ok) {
    console.error(`FAIL ${result.detail}`);
    process.exitCode = 1;
    return;
  }
  console.log(`visual review: ${result.state}`);
}

if (
  process.argv[1] &&
  fileURLToPath(import.meta.url) === path.resolve(process.argv[1])
) {
  main();
}
