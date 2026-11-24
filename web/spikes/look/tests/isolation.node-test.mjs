import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import * as harness from './run.mjs';
import { STAND_IN } from '../register.mjs';
import { RELEASE_BLOCK, startLookServer } from '../server.mjs';

test('F5 browser harness ignores ambient register settings and live credentials', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-isolation-'));
  const previous = {
    file: process.env.EII_REGISTER_FILE,
    date: process.env.EII_REGISTER_DATE,
    key: process.env.MAPTILE_API_KEY,
  };
  const trap = path.join(root, 'invented-environment-trap.csv');
  fs.writeFileSync(trap, 'not a register');
  fs.writeFileSync(path.join(root, 'index.html'), RELEASE_BLOCK);
  // Exercise the measured-input case within this isolated repository;
  // the separate neutral-ground regression leaves this stand-in absent.
  const standIn = path.join(root, ...STAND_IN);
  fs.mkdirSync(path.dirname(standIn), { recursive: true });
  fs.copyFileSync(
    new URL('../register/establishments.csv', import.meta.url),
    standIn,
  );
  process.env.EII_REGISTER_FILE = trap;
  process.env.EII_REGISTER_DATE = '2026-11-13';
  process.env.MAPTILE_API_KEY = 'planted-unused-key';
  let server;
  try {
    // The pre-fix harness called startLookServer with unchecked options.
    const start = harness.startTestServer ?? startLookServer;
    server = await start(root, {
      repositoryRoot: root,
      env: process.env,
      apiKey: 'planted-option-key',
      fetch: () => {
        throw new Error('unchecked transport');
      },
    });
    assert.ok(server.release.establishments.length > 0);
    assert.equal(server.release.layer.provenance, 'synthetic');
    assert.equal(
      server.release.facts.some((fact) => fact.id === 'densest-unit'),
      true,
    );
    const status = JSON.parse(
      (await get(`${server.origin}/photoreal/status`)).text,
    );
    assert.equal(status.available, false);
    const childEnv = harness.browserEnvironment(server.origin, 'test-browser');
    assert.equal(childEnv.EII_REGISTER_FILE, '');
    assert.equal(childEnv.EII_REGISTER_DATE, '');
    assert.equal(childEnv.MAPTILE_API_KEY, '');
    assert.equal(
      (await get(`${server.origin}/photoreal/root.json`)).status,
      404,
    );
    assert.equal(
      (await get(`${server.origin}/photoreal/tile?path=/v1/3dtiles/example`))
        .status,
      404,
    );
  } finally {
    if (server) await server.close();
    for (const [key, value] of [
      ['EII_REGISTER_FILE', previous.file],
      ['EII_REGISTER_DATE', previous.date],
      ['MAPTILE_API_KEY', previous.key],
    ]) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
    fs.rmSync(root, { recursive: true, force: true });
  }
});

function get(url) {
  return new Promise((resolve, reject) => {
    http
      .get(url, (response) => {
        const chunks = [];
        response.on('data', (chunk) => chunks.push(chunk));
        response.on('end', () =>
          resolve({
            status: response.statusCode,
            text: Buffer.concat(chunks).toString('utf8'),
          }),
        );
      })
      .on('error', reject);
  });
}
