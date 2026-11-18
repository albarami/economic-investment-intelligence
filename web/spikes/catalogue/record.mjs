import fs from 'node:fs';
import { renderToStaticMarkup } from 'react-dom/server';
import { cases, oracle, valid } from './tests/helpers.mjs';
import { createDispatcher } from './native-dispatch.ts';
import {
  streamEvidence,
  transportEvidence,
  fallbackEvidence,
  exercisePlant,
  repairEvidence,
  wordingEvidence,
} from './scenarios.mjs';
import { countLines } from './count-lines.mjs';
import { read, sha, sourceFiles, verifyHashes } from './verify-evidence.mjs';
import { denyNetwork } from './network-guard.mjs';
import assert from 'node:assert/strict';

const manifest = JSON.parse(read('fixtures/manifest.json'));
verifyHashes(manifest.files, read);
verifyHashes(JSON.parse(read('fixtures/paired-manifest.json')).files, read);
const result = await denyNetwork(async (attempts) => {
  const answers = oracle(cases);
  for (const [index, row] of cases.entries())
    assert.deepEqual(answers[index].refusal, row.expected);
  const candidates = [];
  const streams = [];
  for (const name of ['native', 'a2ui', 'json-render']) {
    const { adapter } = await import(`./adapters/${name}.ts`);
    const rows = [];
    for (const [index, row] of cases.entries()) {
      const log = [];
      const trace = [];
      assert.equal(adapter.decode(adapter.encode(row.raw)), row.raw);
      const dispatch = createDispatcher((selection) => {
        log.push(selection);
        trace.push('commit');
      });
      trace.push('complete');
      const prepared = await dispatch.prepare(
        row.raw,
        row.context,
        async (raw, ctx) => {
          assert.equal(raw, row.raw);
          assert.deepEqual(ctx, row.context);
          const a = answers[index];
          trace.push('validated');
          return a;
        },
      );
      let markup = null;
      if (prepared.receipt) {
        dispatch.commit(prepared.receipt);
        if (adapter.render)
          markup = renderToStaticMarkup(adapter.render(log[0]));
      }
      if (!prepared.receipt) trace.push('refused');
      assert.deepEqual(
        trace,
        prepared.receipt
          ? ['complete', 'validated', 'commit']
          : ['complete', 'validated', 'refused'],
      );
      rows.push({
        id: row.id,
        refusal: prepared.refusal,
        severity: prepared.severity,
        sinkCommits: log.length,
        markup,
        timeline: trace,
      });
    }
    candidates.push({
      name,
      cases: rows,
      renderer:
        name === 'a2ui'
          ? 'BLOCKED: requires browser HTMLElement and surface construction'
          : 'server markup only; live DOM BLOCKED',
    });
    streams.push(await streamEvidence(name, cases, answers));
  }
  const failureMatrix = [];
  for (const mode of [
    'normal',
    'malformed',
    'interrupted',
    'duplicate',
    'reordered',
    'late',
  ])
    failureMatrix.push(...(await transportEvidence(mode, answers[0])));
  const fallback = [];
  for (const mode of [
    'invalid_repair',
    'refusal',
    'max_tokens',
    'api_error',
    'timeout',
  ])
    fallback.push(await fallbackEvidence(mode, answers[0]));
  const plants = [
    'forged_receipt',
    'receipt_replay',
    'severity_downgrade',
    'unknown_action',
    'unactivated',
    'forged_activation',
    'activation_replay',
    'activation_expired',
  ];
  for (const plant of plants) await exercisePlant(plant, answers[0]);
  for (const plant of ['second_repair', 'history_edit', 'invalid_fallback'])
    await repairEvidence(plant, answers[0]);
  for (const plant of [
    'numeral',
    'withheld_zero',
    'withheld_hidden',
    'withheld_absent',
  ])
    wordingEvidence(plant);
  assert.deepEqual(attempts, []);
  const counts = countLines();
  return {
    schema: 1,
    contract_sha256: sha(read('contract.json')),
    fixture_manifest_sha256: sha(read('fixtures/manifest.json')),
    paired_manifest_sha256: sha(read('fixtures/paired-manifest.json')),
    environment: {
      node: process.version,
      platform: process.platform,
      architecture: process.arch,
      randomness: 'none',
      provider: 'none',
      affinity: 'launcher cores 20,21',
    },
    candidates,
    streams,
    failureMatrix,
    fallback,
    dispatcherPlants: plants,
    counts,
    networkAttempts: attempts.length,
    activation: 'host seam tested; real browser user-event activation BLOCKED',
    selection: 'native',
    selectionReason:
      'L-974 requires every criterion PASS and less code. Browser, Fact chips, official-page reading and independent review remain BLOCKED; every adapter adds maintained lines.',
    acceptance: [
      {
        criterion: 'predeclare_identical_fixtures',
        status: 'PASS',
        evidence:
          'contract and fixture hashes; all candidates have every canonical envelope case',
      },
      {
        criterion: 'zero_unauthorized_output',
        status: 'BLOCKED',
        evidence:
          'oracle and dispatch sinks pass plants; native/json-render server markup only, A2UI and live DOM/accessibility/render commits need browser',
      },
      {
        criterion: 'interrupted_streams',
        status: 'BLOCKED',
        evidence:
          'every-byte harness commits and cancellation pass; transient browser observation pending',
      },
      {
        criterion: 'shared_dispatcher',
        status: 'PASS',
        evidence:
          'distinct story, explore, assistant entries call shared dispatch; corpus parity and divergent-entry plant; forged receipt rejected',
      },
      {
        criterion: 'versions_severity_activation',
        status: 'BLOCKED',
        evidence:
          'version/severity/host activation seam plants pass; real same-turn user event proof pending',
      },
      {
        criterion: 'closed_schema_slots',
        status: 'PASS',
        evidence:
          'existing check_brief bridge; each invalid case has exact rule/path and valid control',
      },
      {
        criterion: 'repair_fallback',
        status: 'PASS',
        evidence:
          'append-only recorded turns, one repair, invalid repair and terminal statuses use validated same-facts template',
      },
      {
        criterion: 'withheld_unchanged_controls',
        status: 'BLOCKED',
        evidence:
          'withheld wording, full source-chain and companion plants pass; numeric Fact chip display absent, production accounting gate not claimed',
      },
      {
        criterion: 'transport_comparison',
        status: 'PASS',
        evidence:
          'frozen line lists plus both transports over every failure mode; these are CUSTOM-envelope harness events only',
      },
      {
        criterion: 'decision_isolation',
        status: 'BLOCKED',
        evidence:
          'native retained and import/evidence guards pass; lead confirms Proposed decision number and different-maker review',
      },
    ],
  };
});
fs.writeFileSync(
  new URL('evidence/results.json', import.meta.url),
  JSON.stringify(result, null, 2) + '\n',
);
const checksums = Object.fromEntries(
  [...sourceFiles(), 'evidence/results.json'].map((name) => [
    name,
    sha(read(name)),
  ]),
);
fs.writeFileSync(
  new URL('evidence/checksums.json', import.meta.url),
  JSON.stringify(checksums, null, 2) + '\n',
);
console.log(
  `recorded ${cases.length} invented cases for every candidate; selection native; blocked criteria preserved`,
);
assert.ok(valid);
