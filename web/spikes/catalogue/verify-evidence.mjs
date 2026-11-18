import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { groups } from './count-lines.mjs';

export const sha = (value) =>
  crypto.createHash('sha256').update(value).digest('hex');
export const read = (name) => fs.readFileSync(new URL(name, import.meta.url));
export const sourceFiles = () => [
  ...new Set(Object.values(groups).flat()),
  'contract.json',
  'index.html',
  'tsconfig.json',
  '../../scripts/tests/catalogue-isolation.node-test.mjs',
  '../../../product/src/eii_product/assistant/catalogue/brief.py',
  '../../../product/src/eii_product/assistant/catalogue/slots.py',
  '../../../product/src/eii_product/assistant/catalogue/schema.py',
  '../../../product/src/eii_product/assistant/catalogue/load.py',
  '../../../product/src/eii_product/assistant/catalogue/entries.py',
  '../../../product/src/eii_product/assistant/catalogue/directives.py',
  '../../../product/src/eii_product/assistant/catalogue/scan.py',
  '../../scripts/import-tokenizer.mjs',
  '../../package.json',
  '../../package-lock.json',
];
export function verifyHashes(manifest, get) {
  for (const [name, expected] of Object.entries(manifest)) {
    let content;
    try {
      content = get(name);
    } catch {
      throw new Error(`MISSING_EVIDENCE:${name}`);
    }
    if (sha(content) !== expected) throw new Error(`HASH_MISMATCH:${name}`);
  }
}
export function evidencePlants() {
  const content = Buffer.from('invented evidence');
  const manifest = { 'fixture.json': sha(content) };
  verifyHashes(manifest, () => content);
  assert.throws(
    () =>
      verifyHashes(manifest, () => {
        throw new Error('missing');
      }),
    /MISSING_EVIDENCE/,
  );
  assert.throws(
    () => verifyHashes(manifest, () => Buffer.from('edited')),
    /HASH_MISMATCH/,
  );
}
export function verifyEvidence() {
  const fixture = JSON.parse(read('fixtures/manifest.json'));
  verifyHashes(fixture.files, read);
  const paired = JSON.parse(read('fixtures/paired-manifest.json'));
  verifyHashes(paired.files, read);
  const receipt = JSON.parse(read('evidence/checksums.json'));
  const required = [...sourceFiles(), 'evidence/results.json'];
  assert.deepEqual(Object.keys(receipt).sort(), required.sort());
  verifyHashes(receipt, read);
  const results = JSON.parse(read('evidence/results.json'));
  assert.equal(results.contract_sha256, sha(read('contract.json')));
  assert.equal(
    results.fixture_manifest_sha256,
    sha(read('fixtures/manifest.json')),
  );
  assert.deepEqual(
    results.candidates.map((item) => item.name),
    ['native', 'a2ui', 'json-render'],
  );
  const rows = [
    ...JSON.parse(read('fixtures/cases.json')),
    ...JSON.parse(read('fixtures/paired-cases.json')),
  ];
  assert.equal(
    results.paired_manifest_sha256,
    sha(read('fixtures/paired-manifest.json')),
  );
  for (const item of results.candidates)
    assert.deepEqual(
      item.cases.map((entry) => entry.id),
      rows.map((entry) => entry.id),
    );
  assert.equal(results.selection, 'native');
  for (const stream of results.streams) {
    assert.equal(stream.premature, 0);
    assert.equal(stream.stale, 0);
    assert.ok(stream.commits > 0);
  }
  return results;
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    verifyEvidence();
    console.log('catalogue evidence verified; blocked rows remain blocked');
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
