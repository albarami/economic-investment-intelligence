import test from 'node:test';
import assert from 'node:assert/strict';
import { validateInput, validateView, isolated } from '../guards.mjs';
const input = { fixture: 'hourly', selection: 'first' };
test('closed valid input invokes renderer once', () => {
  let calls = 0;
  validateInput(input, () => calls++);
  assert.equal(calls, 1);
});
for (const property of ['specification', 'expression', 'address']) {
  test(`reject ${property} before rendering`, () => {
    let calls = 0;
    assert.throws(() =>
      validateInput({ ...input, [property]: 'forbidden' }, () => calls++),
    );
    assert.equal(calls, 0);
  });
}
const view = {
  description: 'Profile',
  table: ['fact:a'],
  marks: ['fact:a'],
  text: 'Profile',
  digits: '12',
  arabicDigits: '12',
  lineage: true,
  texture: 'series',
};
test('valid governance control', () =>
  assert.doesNotThrow(() => validateView(view)));
for (const [name, patch] of Object.entries({
  table: { table: null },
  description: { description: '' },
  equality: { table: ['fact:b'] },
  numeral: { text: 'Profile 2' },
  arabicIndic: { digits: '١٢' },
  extendedArabicIndic: { digits: '۱۲' },
  parity: { arabicDigits: '13' },
  lineage: { lineage: false },
  origin: { texture: 'origin' },
}))
  test(`plant ${name}`, () =>
    assert.throws(() => validateView({ ...view, ...patch })));
test('production graph positive and planted transitive import', () => {
  assert.equal(
    isolated({ 'src/main.tsx': ['src/app.tsx'], 'src/app.tsx': [] }),
    true,
  );
  assert.equal(
    isolated({
      'src/main.tsx': ['src/app.tsx'],
      'src/app.tsx': ['spikes/charts/main.tsx'],
    }),
    false,
  );
});
