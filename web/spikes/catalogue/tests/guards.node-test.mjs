import assert from 'node:assert/strict';
import { test } from 'node:test';
import { cases, oracle, valid } from './helpers.mjs';

for (const row of cases) {
  test(`oracle plant/control: ${row.id}`, async () => {
    const { validate } = await import('../native-dispatch.ts');
    const [answer, control] = oracle([row, valid]);
    assert.deepEqual(answer.refusal, row.expected);
    assert.equal(control.refusal, null);
    const result = await validate(row.raw, row.context, async () => answer);
    assert.deepEqual(result.refusal, row.expected);
    assert.equal(result.severity, row.expected ? 'blocking' : null);
  });
}

for (const candidate of ['native', 'a2ui', 'json-render']) {
  test(`identical lossless corpus and sinks: ${candidate}`, async () => {
    const { adapter } = await import(`../adapters/${candidate}.ts`);
    const { createDispatcher } = await import('../native-dispatch.ts');
    const answers = oracle(cases);
    const logs = [];
    const dispatch = createDispatcher((item) => logs.push(item));
    for (const [index, row] of cases.entries()) {
      assert.equal(adapter.decode(adapter.encode(row.raw)), row.raw);
      const result = await dispatch.prepare(
        row.raw,
        row.context,
        async () => answers[index],
      );
      const before = logs.length;
      if (row.expected) {
        assert.equal(result.receipt, null);
        assert.throws(() => dispatch.commit(result.receipt), /RECEIPT/);
        assert.equal(logs.length, before);
      } else {
        assert.ok(result.receipt);
        dispatch.commit(result.receipt);
        assert.equal(logs.length, before + 1);
      }
    }
  });
}

for (const plant of [
  'forged_receipt',
  'receipt_replay',
  'severity_downgrade',
  'unknown_action',
  'unactivated',
  'forged_activation',
  'activation_replay',
  'activation_expired',
]) {
  test(`dispatcher plant/control: ${plant}`, async () => {
    const { exercisePlant } = await import('../scenarios.mjs');
    await exercisePlant(plant, oracle([valid])[0]);
  });
}

test('story, Explore and assistant share dispatch outcomes', async () => {
  const { createDispatcher, story, explore, assistant } =
    await import('../native-dispatch.ts');
  const { compareEntries } = await import('../scenarios.mjs');
  assert.deepEqual(
    await compareEntries([story, explore, assistant], cases, oracle(cases)),
    [],
  );
  const sink = [];
  const answer = oracle([valid])[0];
  assert.equal(
    await story(
      createDispatcher((event) => sink.push(event)),
      valid.raw,
      valid.context,
      async () => answer,
    ),
    null,
  );
  assert.equal(sink.length, 1);
});

for (const candidate of ['native', 'a2ui', 'json-render']) {
  test(`every byte stream cut and cancel/late chunks: ${candidate}`, async () => {
    const { streamEvidence } = await import('../scenarios.mjs');
    const evidence = await streamEvidence(candidate, cases, oracle(cases));
    assert.ok(evidence.cuts > cases.length);
    assert.equal(evidence.premature, 0);
    assert.equal(evidence.stale, 0);
    assert.ok(evidence.commits > 0);
  });
}

for (const plant of ['second_repair', 'history_edit', 'invalid_fallback']) {
  test(`repair plant/control: ${plant}`, async () => {
    const { repairEvidence } = await import('../scenarios.mjs');
    await repairEvidence(plant, oracle([valid])[0]);
  });
}
for (const outcome of [
  'invalid_repair',
  'refusal',
  'max_tokens',
  'api_error',
  'timeout',
]) {
  test(`validated same-facts fallback: ${outcome}`, async () => {
    const { fallbackEvidence } = await import('../scenarios.mjs');
    await fallbackEvidence(outcome, oracle([valid])[0]);
  });
}
for (const plant of [
  'numeral',
  'withheld_zero',
  'withheld_hidden',
  'withheld_absent',
]) {
  test(`application wording plant/control: ${plant}`, async () => {
    const { wordingEvidence } = await import('../scenarios.mjs');
    wordingEvidence(plant);
  });
}
for (const mode of [
  'normal',
  'malformed',
  'interrupted',
  'duplicate',
  'reordered',
  'late',
]) {
  test(`transport failure mode/control: ${mode}`, async () => {
    const { transportEvidence } = await import('../scenarios.mjs');
    await transportEvidence(mode, oracle([valid])[0]);
  });
}

test('evidence verifier detects missing and mismatched artifacts', async () => {
  const { evidencePlants } = await import('../verify-evidence.mjs');
  evidencePlants();
});

test('network sink guard catches a request and accepts offline work', async () => {
  const { denyNetwork } = await import('../network-guard.mjs');
  await denyNetwork(async (attempts) => {
    const get = globalThis['fet' + 'ch'];
    await assert.rejects(async () => get('https://invalid.example'), /NETWORK/);
    assert.deepEqual(attempts, ['fetch']);
  });
  await denyNetwork(async (attempts) => {
    assert.equal(await Promise.resolve('offline'), 'offline');
    assert.deepEqual(attempts, []);
  });
});

test('all accounting checks must pass before a receipt is issued', async () => {
  const { createDispatcher } = await import('../native-dispatch.ts');
  const answer = oracle([valid])[0];
  for (const omitted of answer.checks) {
    const dispatch = createDispatcher(() => assert.fail('accounting bypass'));
    const bad = await dispatch.prepare(valid.raw, valid.context, async () => ({
      refusal: null,
      checks: answer.checks.filter((item) => item !== omitted),
    }));
    assert.equal(bad.refusal.rule_code, 'ACCOUNTING');
    assert.equal(bad.receipt, null);
    const good = await dispatch.prepare(
      valid.raw,
      valid.context,
      async () => answer,
    );
    assert.ok(good.receipt);
  }
});

test('source-line counts exclude comments and retain literal content', async () => {
  const { countSource } = await import('../count-lines.mjs');
  assert.equal(
    countSource(
      '// comment\n\nconst literal = "// code";\n/* comment\n comment */\nexport { literal };\n',
      'fixture.ts',
    ),
    2,
  );
  assert.equal(
    countSource('# comment\n\ntext = "# literal"\nprint(text)\n', 'fixture.py'),
    2,
  );
  assert.equal(countSource('# comment\nkey: value\n', 'fixture.yaml'), 1);
});

for (const [source, expected] of [
  ['const a = `x${b}`;\n\n// c\nconst d = 1;\n', 2],
  ['f(`${a}`);\n\n// tail\n', 1],
]) {
  test(`template substitution line-count plant/control: ${expected}`, async () => {
    const { countSource } = await import('../count-lines.mjs');
    assert.equal(countSource('const control = 1;\n', 'f.ts'), 1);
    assert.equal(countSource(source, 'f.ts'), expected);
  });
}

test('coverage control includes every case, stream, mode and fallback', async () => {
  const { checkCoverage, read } = await import('../verify-evidence.mjs');
  checkCoverage(JSON.parse(read('evidence/results.json')), cases);
});
for (const omitted of ['candidate', 'stream', 'mode', 'fallback']) {
  test(`coverage omission plant/control: ${omitted}`, async () => {
    const { checkCoverage, read } = await import('../verify-evidence.mjs');
    const result = JSON.parse(read('evidence/results.json'));
    const incomplete = structuredClone(result);
    if (omitted === 'candidate') incomplete.candidates[1].cases.pop();
    if (omitted === 'stream') incomplete.streams[2].cases.pop();
    if (omitted === 'mode') incomplete.failureMatrix.pop();
    if (omitted === 'fallback') incomplete.fallback.pop();
    checkCoverage(result, cases);
    assert.throws(() => checkCoverage(incomplete, cases), /AssertionError/);
  });
}

test('distinct entry points delegate to shared dispatch', async () => {
  const { story, explore, assistant } = await import('../native-dispatch.ts');
  assert.notEqual(story, explore);
  assert.notEqual(story, assistant);
  assert.notEqual(explore, assistant);
});
test('entry comparison detects a divergent refusal with a clean control', async () => {
  const { story, explore, assistant } = await import('../native-dispatch.ts');
  const { compareEntries } = await import('../scenarios.mjs');
  const answers = oracle(cases);
  assert.deepEqual(
    await compareEntries([story, explore, assistant], cases, answers),
    [],
  );
  const divergent = async (dispatch, raw, context, check) => {
    await assistant(dispatch, raw, context, check);
    return null;
  };
  const differences = await compareEntries(
    [story, explore, assistant, divergent],
    cases,
    answers,
  );
  assert.deepEqual(
    differences,
    cases.filter((row) => row.expected).map((row) => row.id),
  );
});

test('recorded candidate timelines include validation before commit or refusal', async () => {
  const { read } = await import('../verify-evidence.mjs');
  for (const candidate of JSON.parse(read('evidence/results.json'))
    .candidates) {
    for (const row of candidate.cases) {
      assert.deepEqual(
        row.timeline,
        row.refusal
          ? ['complete', 'validated', 'refused']
          : ['complete', 'validated', 'commit'],
      );
    }
  }
});
