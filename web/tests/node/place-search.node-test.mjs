import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';

import {
  ADDRESS_SEARCH_PATH,
  assertRelative,
  postAddressSearch,
  readSearchResults,
} from '../../src/api/address-search.mjs';
import { createPlaceSearch } from '../../src/controls/place-search.mjs';

const WEB = path.resolve(import.meta.dirname, '../..');

test('the poster uses the relative path and puts the text in the body only', async () => {
  const seen = [];
  const fetchImpl = async (url, options) => {
    seen.push({ url, options });
    return {
      status: 200,
      async json() {
        return { results: [] };
      },
    };
  };
  await postAddressSearch('SYN-lane', 'en', fetchImpl);
  assert.equal(seen.length, 1);
  assert.equal(seen[0].url, '/api/address-search');
  assert.equal(seen[0].url, ADDRESS_SEARCH_PATH);
  assert.equal(seen[0].url.includes('://'), false);
  assert.equal(seen[0].url.includes('SYN-lane'), false);
  assert.equal(seen[0].options.method, 'POST');
  assert.equal(seen[0].options.body.includes('SYN-lane'), true);
  assert.equal(seen[0].options.body.includes('"lang":"en"'), true);
});

test('a malformed results payload is refused', async () => {
  const fetchImpl = async () => ({
    status: 200,
    async json() {
      return { results: [{ label: 'SYN-lane' }] };
    },
  });
  await assert.rejects(
    () => postAddressSearch('SYN-lane', 'en', fetchImpl),
    /address_search_malformed/,
  );
  assert.throws(() => readSearchResults({ results: 'SYN-lane' }), /malformed/);
  assert.throws(
    () =>
      readSearchResults({
        results: [{ label: 'SYN-lane', point: { longitude: 1.5 } }],
      }),
    /malformed/,
  );
  const refused = [
    { results: [], extra: true },
    {
      results: [
        {
          label: 'SYN-lane',
          point: { longitude: 1.5, latitude: 2.5, altitude: 0 },
        },
      ],
    },
    {
      results: [{ label: 42, point: { longitude: 1.5, latitude: 2.5 } }],
    },
    {
      results: [
        {
          label: 'SYN-lane',
          point: { longitude: Number.NaN, latitude: 2.5 },
        },
      ],
    },
    {
      results: [
        {
          label: 'SYN-lane',
          point: { longitude: Infinity, latitude: 2.5 },
        },
      ],
    },
    {
      results: [
        { label: 'SYN-lane', point: { longitude: 181, latitude: 2.5 } },
      ],
    },
    {
      results: [
        { label: 'SYN-lane', point: { longitude: 1.5, latitude: -91 } },
      ],
    },
  ];
  for (const payload of refused) {
    assert.throws(() => readSearchResults(payload), /address_search_malformed/);
  }
});

test('an absolute url and text in the url are refused', () => {
  assert.throws(
    () => assertRelative('https://example.test/api/address-search', 'SYN-lane'),
    /absolute URL/,
  );
  assert.throws(
    () => assertRelative('/api/address-search?text=SYN-lane', 'SYN-lane'),
    /text in URL/,
  );
});

test('the control shows the label and sets the camera target', async () => {
  const calls = [];
  const poster = async (text, lang) => {
    calls.push({ text, lang });
    return {
      results: [
        {
          label: 'SYN-lane',
          point: { longitude: 1.5, latitude: 2.5 },
        },
      ],
    };
  };
  const search = createPlaceSearch(poster);
  const shown = await search.search('SYN-lane', 'ar');
  assert.deepEqual(calls, [{ text: 'SYN-lane', lang: 'ar' }]);
  assert.equal(shown.state, 'shown');
  assert.equal(shown.label, 'SYN-lane');
  assert.deepEqual(shown.camera, { longitude: 1.5, latitude: 2.5 });
  assert.equal(search.results.length, 1);
});

test('not found returns gazetteer_only and close clears the results', async () => {
  const search = createPlaceSearch(async () => ({ state: 'gazetteer_only' }));
  const outcome = await search.search('SYN-lane', 'en');
  assert.equal(outcome.state, 'gazetteer_only');
  assert.deepEqual(search.results, []);
  const shown = createPlaceSearch(async () => ({
    results: [{ label: 'SYN-lane', point: { longitude: 1.5, latitude: 2.5 } }],
  }));
  await shown.search('SYN-lane', 'en');
  shown.close();
  assert.deepEqual(shown.results, []);
  assert.equal(shown.camera, null);
});

test('a search and close write nothing to browser local storage', async () => {
  const writes = [];
  const storage = {
    setItem(key, value) {
      writes.push(`${key}=${value}`);
    },
    getItem() {
      return null;
    },
    removeItem(key) {
      writes.push(`remove:${key}`);
    },
    clear() {
      writes.push('clear');
    },
  };
  const previousStorage = globalThis.localStorage;
  const previousWindow = globalThis.window;
  globalThis.localStorage = storage;
  globalThis.window = { localStorage: storage };
  try {
    const search = createPlaceSearch(async () => ({
      results: [
        { label: 'SYN-lane', point: { longitude: 1.5, latitude: 2.5 } },
      ],
    }));
    await search.search('SYN-lane', 'en');
    search.close();
    assert.deepEqual(writes, []);
  } finally {
    globalThis.localStorage = previousStorage;
    globalThis.window = previousWindow;
  }
});

test('the control source does not call fetch and the markers stay', () => {
  const control = fs.readFileSync(
    path.join(WEB, 'src/controls/place-search.mjs'),
    'utf8',
  );
  assert.equal(/\bfetch\b/.test(control), false);
  assert.equal(fs.existsSync(path.join(WEB, 'src/api/.gitkeep')), true);
  assert.equal(fs.existsSync(path.join(WEB, 'src/controls/.gitkeep')), true);
});
