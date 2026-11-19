import assert from 'node:assert/strict';
import { isDeepStrictEqual } from 'node:util';
import { createDispatcher, negotiate, severity } from './native-dispatch.ts';
import { bufferedStream } from './stream.ts';
import { conversation, fallback, resolveAnswer } from './repair.ts';
import { checkWording, wording } from './wording.ts';
import { eventMachine } from './transport.ts';
import { valid } from './tests/helpers.mjs';

export async function compareEntries(entries, cases, answers) {
  let baseline;
  const differences = new Set();
  for (const entry of entries) {
    const sink = [];
    const dispatch = createDispatcher((selection) => sink.push(selection));
    const outcomes = [];
    for (const [index, row] of cases.entries()) {
      const before = sink.length;
      const refusal = await entry(
        dispatch,
        row.raw,
        row.context,
        async () => answers[index],
      );
      const outcome = { sink: sink.slice(before), refusal };
      outcomes.push(outcome);
      if (baseline && !isDeepStrictEqual(outcome, baseline[index]))
        differences.add(row.id);
    }
    baseline ??= outcomes;
  }
  return cases.filter((row) => differences.has(row.id)).map((row) => row.id);
}

export async function exercisePlant(plant, answer) {
  const logs = [];
  let active = true;
  const dispatch = createDispatcher(
    (value) => logs.push(value),
    () => active,
  );
  const result = await dispatch.prepare(
    valid.raw,
    valid.context,
    async () => answer,
  );
  assert.ok(result.receipt);
  if (plant === 'forged_receipt')
    assert.throws(() => dispatch.commit({}), /RECEIPT/);
  dispatch.commit(result.receipt);
  assert.equal(logs.length, 1);
  if (plant === 'receipt_replay')
    assert.throws(() => dispatch.commit(result.receipt), /RECEIPT/);
  if (plant === 'severity_downgrade') {
    assert.throws(
      () => severity({ rule_code: 'SCHEMA', item_path: 'brief' }, 'warning'),
      /SEVERITY/,
    );
    assert.equal(
      severity({ rule_code: 'SCHEMA', item_path: 'brief' }, 'blocking'),
      'blocking',
    );
  }
  const action = { key: 'save_view', side_effect: true };
  if (plant === 'unknown_action')
    assert.throws(
      () =>
        dispatch.action(result.receipt, { key: 'execute', side_effect: true }),
      /ACTION/,
    );
  if (plant === 'unactivated')
    assert.throws(() => dispatch.action(result.receipt, action), /ACTIVATION/);
  if (plant === 'forged_activation')
    assert.throws(
      () => dispatch.action(result.receipt, action, { active: true }),
      /ACTIVATION/,
    );
  if (plant === 'activation_expired') {
    const token = dispatch.activate();
    await Promise.resolve();
    assert.throws(
      () => dispatch.action(result.receipt, action, token),
      /ACTIVATION/,
    );
  }
  const token = dispatch.activate();
  assert.equal(dispatch.action(result.receipt, action, token), 'saved_view');
  if (plant === 'activation_replay')
    assert.throws(
      () => dispatch.action(result.receipt, action, token),
      /ACTIVATION/,
    );
  active = false;
  assert.throws(() => dispatch.activate(), /ACTIVATION/);
  const version = JSON.parse(valid.raw).catalogue_version;
  assert.equal(negotiate(version, new Set([version])), version);
  assert.throws(
    () => negotiate('unsupported', new Set([version])),
    /CATALOGUE_VERSION/,
  );
}

export async function streamEvidence(candidate, rows, answers) {
  const { adapter } = await import(`./adapters/${candidate}.ts`);
  const evidence = {
    candidate,
    cuts: 0,
    premature: 0,
    stale: 0,
    commits: 0,
    cases: [],
  };
  for (const [index, row] of rows.entries()) {
    const bytes = new TextEncoder().encode(adapter.encode(row.raw));
    const result = answers[index];
    const check = async (raw) =>
      raw === row.raw
        ? result
        : { refusal: { rule_code: 'JSON', item_path: 'brief' }, checks: [] };
    let successful = 0;
    for (let cut = 0; cut <= bytes.length; cut += 1) {
      const logs = [];
      const timeline = [];
      const dispatch = createDispatcher((selection) => logs.push(selection));
      const stream = bufferedStream(
        dispatch,
        row.context,
        check,
        timeline,
        adapter.decode,
      );
      stream.push(bytes.slice(0, cut));
      evidence.premature += logs.length;
      assert.equal(logs.length, 0);
      evidence.cuts += 1;
      stream.push(bytes.slice(cut));
      assert.equal(logs.length, 0);
      const complete = await stream.finish();
      assert.equal(complete, !row.expected);
      assert.deepEqual(
        timeline,
        row.expected
          ? ['complete', 'validated']
          : ['complete', 'validated', 'committed'],
      );
      assert.equal(logs.length, row.expected ? 0 : 1);
      successful += logs.length;
      // Cancellation before completion plus late chunks and repeated finish.
      const cancelled = bufferedStream(
        dispatch,
        row.context,
        check,
        [],
        adapter.decode,
      );
      cancelled.push(bytes.slice(0, cut));
      cancelled.cancel();
      assert.equal(cancelled.push(bytes.slice(cut)), false);
      assert.equal(await cancelled.finish(), false);
      assert.equal(logs.length, row.expected ? 0 : 1);
    }
    // Cancellation while accounting is pending, then a late validator answer.
    let release;
    const gate = new Promise((resolve) => {
      release = resolve;
    });
    const logs = [];
    const pending = bufferedStream(
      createDispatcher((selection) => logs.push(selection)),
      row.context,
      () => gate,
      [],
      adapter.decode,
    );
    pending.push(bytes);
    const finishing = pending.finish();
    pending.cancel();
    release(result);
    assert.equal(await finishing, false);
    evidence.stale += logs.length;
    assert.equal(logs.length, 0);
    // An interrupted prefix is completed explicitly: it must never commit.
    for (let cut = 0; cut < bytes.length; cut += 1) {
      const partial = bufferedStream(
        createDispatcher((selection) => logs.push(selection)),
        row.context,
        check,
        [],
        adapter.decode,
      );
      partial.push(bytes.slice(0, cut));
      assert.equal(await partial.finish(), false);
      assert.equal(logs.length, 0);
    }
    evidence.commits += successful;
    evidence.cases.push({
      id: row.id,
      cuts: bytes.length + 1,
      commits: successful,
      timeline: row.expected
        ? ['complete', 'validated']
        : ['complete', 'validated', 'committed'],
    });
  }
  return evidence;
}

export async function repairEvidence(plant, answer) {
  const history = ['application-owned system turn', 'invented question'];
  const session = conversation(history);
  const issue = { rule_code: 'UNKNOWN_COMPONENT', item_path: 'layout[0]' };
  if (plant === 'history_edit')
    assert.throws(
      () => session.repair(['edited', history[1]], issue),
      /HISTORY/,
    );
  const next = session.repair(history, issue);
  assert.deepEqual(next.slice(0, history.length), history);
  assert.deepEqual(JSON.parse(next.at(-1)), {
    role: 'user',
    request: 'Correct structured data',
    rule: issue.rule_code,
    path: issue.item_path,
  });
  if (plant === 'second_repair')
    assert.throws(() => session.repair(next, issue), /REPAIR_LIMIT/);
  if (plant === 'invalid_fallback')
    await assert.rejects(
      fallback(
        createDispatcher(() => assert.fail('invalid fallback reached sink')),
        '{',
        valid.context,
        async () => ({ refusal: issue, checks: [] }),
      ),
      /FALLBACK/,
    );
  const logs = [];
  await fallback(
    createDispatcher((value) => logs.push(value)),
    valid.raw,
    valid.context,
    async () => answer,
  );
  assert.equal(logs.length, 1);
}
export async function fallbackEvidence(outcome, answer) {
  assert.ok(
    [
      'invalid_repair',
      'refusal',
      'max_tokens',
      'api_error',
      'timeout',
    ].includes(outcome),
  );
  const logs = [];
  const context = structuredClone(valid.context);
  const before = JSON.stringify(context);
  const history = ['original system turn', 'invented user turn'];
  const result = await resolveAnswer(
    outcome === 'invalid_repair' ? 'answer' : outcome,
    '{',
    '{',
    valid.raw,
    context,
    async (raw, supplied) => {
      assert.deepEqual(supplied, context);
      return raw === valid.raw
        ? answer
        : { refusal: { rule_code: 'JSON', item_path: 'brief' }, checks: [] };
    },
    createDispatcher((value) => logs.push(value)),
    history,
  );
  assert.deepEqual(result.history.slice(0, history.length), history);
  assert.equal(
    result.history.length,
    outcome === 'invalid_repair' ? history.length + 1 : history.length,
  );
  assert.equal(JSON.stringify(context), before);
  assert.equal(result.writer, 'template');
  assert.equal(logs.length, 1);
  return {
    outcome,
    writer: result.writer,
    sameFacts: true,
    history: result.history,
  };
}
export function wordingEvidence(plant) {
  const bad = {
    numeral: 'A reading 7',
    withheld_zero: '0',
    withheld_hidden: 'Hidden count seven',
    withheld_absent: '',
  }[plant];
  assert.throws(() => checkWording(bad, plant !== 'numeral'), /TEMPLATE/);
  assert.equal(checkWording(wording.valid, false), wording.valid);
  assert.equal(checkWording(wording.withheld, true), wording.withheld);
}
export async function transportEvidence(mode, answer) {
  const outcomes = [];
  for (const name of ['plain-events', 'ag-ui']) {
    const { transport } = await import(`./adapters/${name}.ts`);
    const logs = [];
    const stream = bufferedStream(
      createDispatcher((selection) => logs.push(selection)),
      valid.context,
      async () => answer,
      [],
    );
    const machine = eventMachine(stream);
    const events = [
      { run: 'fixture', seq: 0, kind: 'start' },
      { run: 'fixture', seq: 1, kind: 'chunk', data: valid.raw },
      { run: 'fixture', seq: 2, kind: 'finish' },
    ];
    const send = (event) => machine(transport.decode(transport.encode(event)));
    if (mode === 'normal') for (const event of events) await send(event);
    if (mode === 'malformed')
      await assert.rejects(
        send({ run: 'fixture', seq: 0, kind: 'unknown' }),
        /EVENT/,
      );
    if (mode === 'reordered') await assert.rejects(send(events[1]), /EVENT/);
    if (mode === 'duplicate') {
      await send(events[0]);
      await assert.rejects(send(events[0]), /EVENT/);
    }
    if (mode === 'interrupted' || mode === 'late') {
      await send(events[0]);
      await send(events[1]);
      await send({ run: 'fixture', seq: 2, kind: 'cancel' });
      if (mode === 'late')
        await assert.rejects(
          send({ run: 'fixture', seq: 3, kind: 'chunk', data: valid.raw }),
          /EVENT/,
        );
    }
    assert.equal(logs.length, mode === 'normal' ? 1 : 0);
    outcomes.push({
      name,
      mode,
      commits: logs.length,
      outcome:
        mode === 'normal'
          ? 'accepted'
          : mode === 'interrupted'
            ? 'cancelled'
            : 'rejected',
    });
  }
  assert.equal(outcomes[0].commits, outcomes[1].commits);
  return outcomes;
}
