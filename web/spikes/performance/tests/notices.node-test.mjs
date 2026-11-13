import assert from 'node:assert/strict';
import { test } from 'node:test';
import { pageHarness } from './page-harness.mjs';
import notices from '../notices.json' with { type: 'json' };

test('the Arabic notice is marked pending native review and the page shows it', async () => {
  const h = await pageHarness('', false, true);
  assert.equal(notices.arabic.review, 'pending native review');
  assert.equal(h.nodes.get('#notice').textContent, notices.arabic.text);
  assert.equal(h.nodes.get('#notice').hidden, false);
  assert.equal(notices.simulated.arabic.review, 'pending native review');
  assert.equal(notices.pause.arabic.review, 'pending native review');
});
