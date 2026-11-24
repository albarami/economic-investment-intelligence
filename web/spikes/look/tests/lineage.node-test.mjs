import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { assemble, buildRelease, releaseFacts } from '../release-build.mjs';
import { factView, validateRelease } from '../release-shape.mjs';
import { judgeChipChains, judgeClassWords } from '../guards.mjs';

const CELL = '8943a1d8b6bffff';
const base = () =>
  assemble(
    [[CELL, 80, 2]],
    { present: false, missing: 'x' },
    { period: '2026-11-13' },
  );

test('F2 drawer source names no fixture and never renders a provenance row', () => {
  const catalogue = JSON.parse(
    fs.readFileSync(new URL('../catalogue.json', import.meta.url), 'utf8'),
  );
  for (const lang of ['en', 'ar']) {
    assert.equal(
      judgeClassWords(catalogue.strings['chain.source'][lang]).ok,
      true,
    );
  }
  const shell = fs.readFileSync(
    new URL('../shell.ts', import.meta.url),
    'utf8',
  );
  assert.equal(shell.includes("'drawer.provenance'"), false);
});

test('F3 every fact resolves a method version and producing pipeline name/version', () => {
  for (const fact of releaseFacts([[CELL, 80, 2]])) {
    assert.equal(fact.origin, 'synthetic');
    assert.equal(fact.chain.method_version, '1.0.0');
    assert.deepEqual(fact.chain.generator, {
      name: 'chain.pipeline',
      version: '1.0.0',
    });
    assert.ok(fact.chain.inputs.length > 0);
  }
});

test('F3 planted missing lineage links fail release validation and the chip guard', () => {
  const good = base();
  const mutations = [
    (fact) => {
      delete fact.chain.table;
    },
    (fact) => {
      delete fact.chain.method;
    },
    (fact) => {
      delete fact.chain.method_version;
    },
    (fact) => {
      fact.chain.method_version = 'unknown';
    },
    (fact) => {
      delete fact.chain.generator;
    },
    (fact) => {
      fact.chain.generator = { name: '', version: '1.0.0' };
    },
    (fact) => {
      fact.chain.generator = { name: 'chain.pipeline', version: '' };
    },
    (fact) => {
      fact.chain.inputs = [];
    },
    (fact) => {
      delete fact.origin;
    },
    (fact) => {
      fact.input_classes = ['public'];
    },
    (fact) => {
      delete fact.chain.inputs[0].origin;
    },
  ];
  for (const mutate of mutations) {
    const planted = structuredClone(good);
    mutate(planted.facts[0]);
    assert.throws(
      () => validateRelease(planted),
      /chain|origin/,
      String(mutate),
    );
    assert.equal(
      judgeChipChains(
        [{ variant: 'value', ids: [planted.facts[0].id] }],
        planted.facts.map(factView),
        [],
      ).ok,
      false,
    );
  }
});

test('F3 register attributes retain Public identity; attached employees retain Synthetic identity', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-lineage-'));
  try {
    const lines = fs
      .readFileSync(
        new URL('../register/establishments.csv', import.meta.url),
        'utf8',
      )
      .trim()
      .split('\n');
    const fields = lines[1].split(',');
    fields[lines[0].split(',').indexOf('branches')] = '2';
    const bytes = Buffer.from(`${lines[0]}\n${fields.join(',')}\n`);
    const file = path.join(root, 'invented.csv');
    fs.writeFileSync(file, bytes);
    const metadata = {
      publisher: 'Test publisher',
      dataset: 'Test register',
      source: 'Test register page',
      licence: 'Test licence',
      retrieved: '2026-11-13',
      sha256: createHash('sha256').update(bytes).digest('hex'),
    };
    const env = {
      EII_REGISTER_FILE: file,
      EII_REGISTER_DATE: '2026-11-13',
      EII_REGISTER_SOURCE: JSON.stringify(metadata),
    };
    const { release } = await buildRelease(root, env);
    const density = release.facts.find((fact) => fact.id === 'densest-unit');
    assert.equal(density.provenance, 'public');
    assert.deepEqual(density.chain.inputs[0], {
      provenance: 'public',
      ...metadata,
    });
    const employees = release.facts.find((fact) =>
      fact.id.endsWith('-employees'),
    );
    const branches = release.facts.find((fact) =>
      fact.id.endsWith('-branches'),
    );
    assert.equal(employees.provenance, 'synthetic');
    assert.equal(employees.origin, 'synthetic');
    assert.equal(branches.provenance, 'public');
    for (const field of Object.keys(metadata)) {
      const planted = structuredClone(release);
      delete planted.facts.find((fact) => fact.id === density.id).chain
        .inputs[0][field];
      assert.throws(() => validateRelease(planted), /chain/, field);
      assert.equal(
        judgeChipChains(
          [{ variant: 'value', ids: [density.id] }],
          planted.facts.map(factView),
          [],
        ).ok,
        false,
        field,
      );
    }
    for (const field of Object.keys(metadata)) {
      const missing = { ...metadata };
      delete missing[field];
      await assert.rejects(
        buildRelease(root, {
          ...env,
          EII_REGISTER_SOURCE: JSON.stringify(missing),
        }),
        /source|chain/,
      );
    }
    await assert.rejects(
      buildRelease(root, {
        ...env,
        EII_REGISTER_SOURCE: JSON.stringify({
          ...metadata,
          sha256: 'a'.repeat(64),
        }),
      }),
      /hash/,
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('F1 planted summary methods on empty coverage are refused', () => {
  const planted = base();
  planted.layer.cells = [];
  assert.throws(() => validateRelease(planted), /coverage/);
});

test('F2 generated and demo origin labels are caught in both languages', () => {
  for (const text of ['generated', 'demo', 'بيانات مولدة', 'بيانات مُولَّدة']) {
    assert.equal(judgeClassWords(text).ok, false, text);
  }
});

test('F3 missing release and layer backend origin markers are refused', () => {
  for (const target of ['release', 'layer']) {
    const planted = base();
    delete (target === 'release' ? planted : planted.layer).origin;
    assert.throws(() => validateRelease(planted), /origin/);
  }
});
