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
  const answers = oracle(cases);
  const logs = [];
  for (const entry of [story, explore, assistant]) {
    const sink = [];
    const dispatch = createDispatcher((event) => sink.push(event));
    const refusals = [];
    for (const [index, row] of cases.entries()) {
      refusals.push(
        await entry(dispatch, row.raw, row.context, async () => answers[index]),
      );
    }
    logs.push({ sink, refusals });
  }
  assert.deepEqual(logs[0], logs[1]);
  assert.deepEqual(logs[0], logs[2]);
  assert.ok(logs[0].sink.length > 0);
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
