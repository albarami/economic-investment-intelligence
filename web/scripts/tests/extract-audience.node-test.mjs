import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test } from 'node:test';
import { fileURLToPath } from 'node:url';

import {
  ACCESSIBLE_ATTRIBUTE_NAMES,
  collectEvidence,
  decodeText,
  extractDocument,
  surfaceIds,
} from '../extract-audience.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '../..');
const ROOT = path.resolve(WEB, '..');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-audience-extract-'));
after(() => fs.rmSync(tmp, { recursive: true, force: true }));

function writeTree(name, files) {
  const root = path.join(tmp, name);
  for (const [relative, content] of Object.entries(files)) {
    const file = path.join(root, relative);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, content);
  }
  return root;
}

function itemsOf(evidence, id) {
  const surface = evidence.surfaces.find((entry) => entry.id === id);
  assert.ok(surface, `surface ${id} missing`);
  return surface.items;
}

test('evidence carries the committed surface ids', () => {
  const evidence = collectEvidence(ROOT);
  const ids = surfaceIds(evidence);
  for (const id of [
    'web.dist.document',
    'web.dist.accessible',
    'web.urls',
    'web.strings.en',
    'web.strings.ar',
    'web.accessible.en',
    'web.accessible.ar',
    'web.src.accessible',
    'web.catalogue.generated',
  ]) {
    assert.ok(ids.includes(id), `surface ${id} missing`);
  }
});

test('the string tables become screen and accessible items in both languages', () => {
  const evidence = collectEvidence(ROOT);
  for (const id of ['web.strings.en', 'web.strings.ar']) {
    const items = itemsOf(evidence, id);
    assert.ok(items.length > 0, `${id} is empty`);
    for (const entry of items) {
      const allowed =
        (entry.output_class === 'screen' &&
          (entry.field_kind === 'copy' || entry.field_kind === 'withheld')) ||
        (entry.output_class === 'url' && entry.field_kind === 'url');
      assert.ok(allowed, `unexpected item shape: ${JSON.stringify(entry)}`);
    }
  }
  const en = itemsOf(evidence, 'web.accessible.en');
  const ar = itemsOf(evidence, 'web.accessible.ar');
  assert.ok(en.length > 0 && ar.length > 0, 'accessible candidates empty');
  assert.equal(en[0].output_class, 'accessible');
  assert.equal(en[0].field_kind, 'accessible');
  assert.equal(en[0].language, 'en');
  assert.equal(ar[0].language, 'ar');
});

test('the withheld word is emitted under the withheld kind', () => {
  const evidence = collectEvidence(ROOT);
  const items = itemsOf(evidence, 'web.strings.ar');
  const withheld = items.find(
    (entry) => entry.field === 'drawer.class.suppressed',
  );
  assert.ok(withheld, 'the withheld string was not extracted');
  assert.equal(withheld.field_kind, 'withheld');
});

test('the built document emits copy, accessible and URL items', () => {
  const root = writeTree('built', {
    'web/dist/index.html': [
      '<!doctype html><html lang="en"><body>',
      '<h1>Hello area</h1>',
      '<span aria-label="Close the drawer">x</span>',
      '<a href="https://example.invalid/source?k=%61%62">credit</a>',
      '<img alt="map stage" src="/assets/stage.png">',
      '</body></html>',
    ].join(''),
    'web/src/i18n/en.json': '{"strings":{"a":"one"}}',
    'web/src/i18n/ar.json': '{"strings":{"a":"واحد"},"review":{}}',
    'web/src/brief/catalogue.generated.json':
      '{"claims":[],"components":[],"directives":[],"fragments":[],"questions":[],"version":"' +
      '0'.repeat(64) +
      '"}',
  });
  const evidence = collectEvidence(root);
  const doc = itemsOf(evidence, 'web.dist.document');
  assert.ok(
    doc.some((entry) => entry.text.includes('Hello area')),
    'no copy item',
  );
  const accessible = itemsOf(evidence, 'web.dist.accessible');
  assert.ok(
    accessible.some((entry) => entry.text === 'Close the drawer'),
    'no aria item',
  );
  assert.ok(
    accessible.some((entry) => entry.text === 'map stage'),
    'no alt item',
  );
  const urls = itemsOf(evidence, 'web.urls');
  assert.ok(
    urls.some((entry) => entry.text === '/assets/stage.png'),
    'no src item',
  );
  assert.ok(
    urls.some((entry) =>
      entry.text.includes('https://example.invalid/source?k=ab'),
    ),
    'the encoded URL was not decoded',
  );
});

test('a missing built document is reported absent, never empty', () => {
  const root = writeTree('unbuilt', {
    'web/src/i18n/en.json': '{"strings":{"a":"one"}}',
    'web/src/i18n/ar.json': '{"strings":{"a":"واحد"},"review":{}}',
    'web/src/brief/catalogue.generated.json':
      '{"claims":[],"components":[],"directives":[],"fragments":[],"questions":[],"version":"' +
      '0'.repeat(64) +
      '"}',
  });
  const evidence = collectEvidence(root);
  const surface = evidence.surfaces.find(
    (entry) => entry.id === 'web.dist.document',
  );
  assert.ok(surface, 'the built-document surface is missing');
  assert.equal(surface.status, 'absent');
  assert.deepEqual(surface.items, []);
  const accessible = evidence.surfaces.find(
    (entry) => entry.id === 'web.dist.accessible',
  );
  assert.equal(accessible.status, 'absent');
});

test('catalogue rendered fields are audience items; other fields are backend', () => {
  const evidence = collectEvidence(ROOT);
  const items = itemsOf(evidence, 'web.catalogue.generated');
  const rendered = items.filter((entry) => entry.field_kind !== 'backend');
  assert.ok(rendered.length > 0, 'no rendered catalogue text extracted');
  for (const entry of rendered) {
    assert.ok(/_(en|ar)$/.test(entry.field), `unexpected field ${entry.field}`);
    assert.equal(entry.output_class, 'catalogue');
    assert.equal(entry.language, entry.field.endsWith('_ar') ? 'ar' : 'en');
  }
  const backend = items.filter((entry) => entry.field_kind === 'backend');
  assert.ok(backend.length > 0, 'no backend fields recorded');
  for (const entry of backend) {
    assert.ok(!/_(en|ar)$/.test(entry.field), `${entry.field} is rendered`);
  }
});

test('decodeText unwraps entities and percent encodings', () => {
  assert.equal(decodeText('a &amp; b'), 'a & b');
  assert.equal(decodeText('&#x53;imulated'), 'Simulated');
  assert.equal(decodeText('%73imulated'), 'simulated');
  assert.equal(
    decodeText('%D8%A8%D8%A7%D9%84%D9%85%D8%AD%D8%A7%D9%83%D8%A7%D8%A9'),
    'بالمحاكاة',
  );
});

test('extractDocument emits each element text once, attributes and URLs', () => {
  const html =
    '<div><p>First <b>part</b> tail</p>' +
    '<a href="/x?y=1" title="the tip">go</a>' +
    '<p aria-description="described">second</p></div>';
  const found = extractDocument(html, 'fixture.html');
  const texts = found.copy.map((entry) => entry.text);
  assert.ok(
    texts.some((value) => value.includes('First') && value.includes('part')),
    `copy items: ${JSON.stringify(texts)}`,
  );
  assert.ok(
    found.accessible.some((entry) => entry.text === 'the tip'),
    'no title',
  );
  assert.ok(
    found.accessible.some((entry) => entry.text === 'described'),
    'no aria-description',
  );
  assert.ok(
    found.urls.some((entry) => entry.text === '/x?y=1'),
    'no href',
  );
  assert.deepEqual(
    found.accessible.every((entry) =>
      ACCESSIBLE_ATTRIBUTE_NAMES.some((name) =>
        entry.field.endsWith(`@${name}`),
      ),
    ),
    true,
  );
});

test('a canvas paint call and a labelled canvas element land in the evidence', () => {
  const root = writeTree('canvasplant', {
    'web/dist/index.html':
      '<!doctype html><html><body>' +
      '<canvas id="synthetic-watermark" aria-label="ماء"></canvas>' +
      '</body></html>',
    'web/src/i18n/en.json': '{"strings":{"a":"one"}}',
    'web/src/i18n/ar.json': '{"strings":{"a":"واحد"},"review":{}}',
    'web/src/paint.ts':
      'export function paint(ctx) { ctx.fillText("Simulated", 0, 0); }',
    'web/src/brief/catalogue.generated.json':
      '{"claims":[],"components":[],"directives":[],"fragments":[],"questions":[],"version":"' +
      '0'.repeat(64) +
      '"}',
  });
  const evidence = collectEvidence(root);
  const style = itemsOf(evidence, 'web.src.style');
  assert.ok(
    style.some(
      (entry) => entry.text === 'Simulated' && entry.field_kind === 'copy',
    ),
    `canvas text not extracted: ${JSON.stringify(style)}`,
  );
  const document = itemsOf(evidence, 'web.dist.document');
  assert.ok(
    document.some(
      (entry) =>
        entry.field_kind === 'style' && entry.text === 'synthetic-watermark',
    ),
    'the canvas id did not reach the style inputs',
  );
});

test('a planted label anywhere in a copied document lands in the evidence', () => {
  const root = writeTree('planted', {
    'web/dist/index.html':
      '<!doctype html><html><body><h1>Simulated workers</h1>' +
      '<span aria-label="بالمحاكاة">x</span></body></html>',
    'web/src/i18n/en.json': '{"strings":{"a":"Sample data","b":"ok"}}',
    'web/src/i18n/ar.json': '{"strings":{"a":"واحد"},"review":{}}',
    'web/src/brief/catalogue.generated.json':
      '{"claims":[],"components":[],"directives":[],"fragments":[],"questions":[],"version":"' +
      '0'.repeat(64) +
      '"}',
  });
  const evidence = collectEvidence(root);
  const all = evidence.surfaces.flatMap((surface) =>
    surface.items.map((entry) => entry.text),
  );
  assert.ok(all.includes('Simulated workers'), 'visible plant lost');
  assert.ok(all.includes('بالمحاكاة'), 'accessible plant lost');
  assert.ok(all.includes('Sample data'), 'string plant lost');
});
