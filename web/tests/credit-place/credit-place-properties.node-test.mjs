import assert from 'node:assert/strict';
import { test } from 'node:test';

import { pageCreditPlace } from './credit-place-scan.mjs';

// Exhaust the partition domain: each boundary either splits the credit into
// another text node or keeps it fused. Entities must decode before matching.
test('credit placement is invariant over every text-node partition', () => {
  const credit = 'SYN-<&>';
  for (let mask = 0; mask < 2 ** (credit.length - 1); mask += 1) {
    let text = '<span>';
    for (let index = 0; index < credit.length; index += 1) {
      text += `&#${credit.charCodeAt(index)};`;
      if ((mask & (1 << index)) !== 0) text += '</span><span>';
    }
    text += '</span>';
    const page = `<div data-part="attribution"><details>${text}</details></div>`;
    assert.deepEqual(pageCreditPlace(page, credit), { inside: 1, outside: 0 });
    assert.deepEqual(pageCreditPlace(`${page}<p>${text}</p>`, credit), {
      inside: 1,
      outside: 1,
    });
    assert.deepEqual(
      pageCreditPlace(
        page.replace('<details>', '<details open="false">'),
        credit,
      ),
      { inside: 0, outside: 1 },
    );
    assert.deepEqual(
      pageCreditPlace(page.replace('data-part="attribution"', ''), credit),
      { inside: 0, outside: 1 },
    );
  }
});

test('empty, partial and repeated credits retain exact occurrence counts', () => {
  const credit = 'SYN-credit';
  const page = `<div class="stage-credits"><details>${credit}${credit}</details></div>`;
  assert.deepEqual(pageCreditPlace(page, ''), { inside: 0, outside: 0 });
  assert.deepEqual(pageCreditPlace('', credit), { inside: 0, outside: 0 });
  assert.deepEqual(pageCreditPlace('<p>SYN-credi</p>', credit), {
    inside: 0,
    outside: 0,
  });
  assert.deepEqual(pageCreditPlace(page, credit), { inside: 2, outside: 0 });
  assert.deepEqual(pageCreditPlace(`${page}<p>${credit}</p>`, credit), {
    inside: 2,
    outside: 1,
  });
});
