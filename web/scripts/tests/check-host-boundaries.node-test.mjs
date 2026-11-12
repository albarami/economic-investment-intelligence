import assert from 'node:assert/strict';
import test from 'node:test';
import { scanText } from '../host-scan-rules.mjs';

const HOST_STOPS = [
  ['/', '/'],
  ['\\', '\\'],
  ['?', '?'],
  ['#', '#'],
  [':', ':'],
  ['"', '"'],
  ["'", "'"],
  ['`', '`'],
  ['<', '<'],
  ['>', '>'],
  [',', ','],
  [')', ')'],
  [' ', ' '],
  ['tab', '\t'],
  ['newline', '\n'],
  ['cr', '\r'],
];

const PROTOCOL_STOPS = [
  ['whitespace', ' '],
  ['slash', '/'],
  ['backslash', '\\'],
  ['question', '?'],
  ['hash', '#'],
  ['colon', ':'],
  ['single-quote', "'"],
  ['double-quote', '"'],
  ['backtick', '`'],
  ['lt', '<'],
  ['gt', '>'],
  ['comma', ','],
  ['paren', ')'],
];

test('host scan stops at every stop character', () => {
  for (const [name, character] of HOST_STOPS) {
    const text = `https://evil.example${character}tail.example`;
    const hits = scanText(text, { builtScript: true });
    assert.equal(hits.length, 1, name);
    assert.equal(hits[0].rule, 'absolute-url-js', name);
    assert.equal(hits[0].detail, 'https URL, host evil.example', name);
  }
  const open = scanText('https://evil.example', { builtScript: true });
  assert.equal(open.length, 1);
  assert.equal(open[0].detail, 'https URL, host evil.example');

  for (const [name, character] of PROTOCOL_STOPS) {
    const text = `=//nodot${character}has.dot`;
    const hits = scanText(text);
    assert.equal(hits.length, 0, name);
  }
  const relative = scanText('=//has.dot');
  assert.equal(relative.length, 1);
  assert.equal(relative[0].rule, 'protocol-relative-url');
});
