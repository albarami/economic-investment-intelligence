import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { RELEASE_BLOCK, startLookServer } from '../server.mjs';
import {
  MAX_BILLABLE,
  PRICE_USD_PER_THOUSAND,
  SPEND_LIMIT_USD,
  aggregateCopyrights,
  googleHost,
  resolveRoot,
  rewriteTileset,
} from '../photoreal.mjs';

test('the billable cap stays under twenty dollars with no free use', () => {
  assert.equal(PRICE_USD_PER_THOUSAND, 6);
  assert.equal(SPEND_LIMIT_USD, 20);
  const cost = (MAX_BILLABLE * PRICE_USD_PER_THOUSAND) / 1000;
  const over = ((MAX_BILLABLE + 1) * PRICE_USD_PER_THOUSAND) / 1000;
  assert.ok(cost < SPEND_LIMIT_USD, String(cost));
  assert.ok(over >= SPEND_LIMIT_USD, String(over));
  assert.equal(MAX_BILLABLE, 3333);
});

test('with the key absent no request is made, and a Google host fails the plant', async () => {
  const seen = [];
  const result = await resolveRoot({
    reserve: async () => {},
    key: '',
    record: null,
    now: 0,
    fetchRoot: () => {
      seen.push('https://tile.googleapis.com/v1/3dtiles/root.json');
      return Promise.resolve('{}');
    },
  });
  assert.equal(result.status, 404);
  assert.deepEqual(seen, []);
  assert.equal(
    googleHost('https://tile.googleapis.com/v1/3dtiles/root.json'),
    true,
  );
  assert.equal(googleHost('http://127.0.0.1/photoreal/root.json'), false);
  assert.equal(googleHost('https://maps.googleapis.com/maps/api'), true);
});

test('one session is reused, and the next root is refused at the cap', async () => {
  let calls = 0;
  const fetchRoot = () => {
    calls += 1;
    return Promise.resolve(
      JSON.stringify({
        root: {
          content: {
            uri: '/v1/3dtiles/datasets/example/root.json?session=abc',
          },
        },
      }),
    );
  };
  const first = await resolveRoot({
    reserve: async () => {},
    key: 'not-printed',
    record: null,
    now: 1_000,
    fetchRoot,
  });
  assert.equal(first.status, 200);
  assert.equal(calls, 1);
  assert.equal(first.record.count, 1);
  assert.equal(first.body.includes('key='), false);
  assert.equal(first.body.includes('not-printed'), false);
  assert.match(first.body, /\/photoreal\/tile\?path=/);
  const second = await resolveRoot({
    reserve: async () => {},
    key: 'not-printed',
    record: first.record,
    now: 2_000,
    fetchRoot,
  });
  assert.equal(second.status, 200);
  assert.equal(calls, 1);
  assert.equal(second.record.count, 1);
  const capped = await resolveRoot({
    reserve: async () => {},
    key: 'not-printed',
    record: { count: MAX_BILLABLE, fetchedAt: 0, root: '{}' },
    now: 99_000_000,
    fetchRoot,
  });
  assert.equal(capped.status, 429);
  assert.equal(calls, 1);
});

test('a tileset body is rewritten onto the same origin', () => {
  const body = rewriteTileset(
    JSON.stringify({
      root: {
        content: { uri: '/v1/3dtiles/datasets/example/file.json?session=abc' },
        children: [
          {
            content: {
              uri: '/v1/3dtiles/datasets/example/child.glb?session=abc',
            },
          },
        ],
      },
    }),
  );
  assert.equal(body.includes('tile.googleapis.com'), false);
  assert.equal(body.includes('key='), false);
  assert.match(body, /\/photoreal\/tile\?path=%2Fv1%2F3dtiles/);
});

test('the page makes no Google request when the key is absent', async () => {
  const seen = [];
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-photo-'));
  const page = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-photo-page-'));
  fs.writeFileSync(
    path.join(page, 'index.html'),
    `<!doctype html><html><body>${RELEASE_BLOCK}</body></html>`,
  );
  const server = await startLookServer(page, {
    repositoryRoot: repo,
    apiKey: '',
    env: {},
    fetch: (url) => {
      seen.push(String(url));
      return Promise.reject(new Error('a Google host was requested'));
    },
  });
  try {
    const status = await getJson(`${server.origin}/photoreal/status`);
    assert.equal(status.status, 200);
    assert.deepEqual(status.body, {
      available: false,
      count: 0,
      remaining: MAX_BILLABLE,
      session: 0,
    });
    const root = await getText(`${server.origin}/photoreal/root.json`);
    assert.equal(root.status, 404);
    const tile = await getText(
      `${server.origin}/photoreal/tile?path=/v1/3dtiles/example`,
    );
    assert.equal(tile.status, 404);
    assert.deepEqual(seen, []);
  } finally {
    await server.close();
    fs.rmSync(repo, { recursive: true, force: true });
    fs.rmSync(page, { recursive: true, force: true });
  }
});

function getText(url) {
  return new Promise((resolve, reject) => {
    const request = http.get(url, (response) => {
      const chunks = [];
      response.on('data', (chunk) => chunks.push(chunk));
      response.on('end', () => {
        resolve({
          status: response.statusCode ?? 0,
          text: Buffer.concat(chunks).toString('utf8'),
        });
      });
    });
    request.on('error', reject);
  });
}

function getJson(url) {
  return getText(url).then((result) => ({
    status: result.status,
    body: JSON.parse(result.text),
  }));
}

const PLANTED_KEY = 'planted-map-tile-key';
const ROOT_BODY = JSON.stringify({
  root: {
    content: { uri: '/v1/3dtiles/datasets/example/root.json' },
  },
});
const TILE_PATH = '/v1/3dtiles/datasets/example/part.glb';

function sessionPath(repo) {
  return path.join(repo, 'data', 'photoreal', 'session.json');
}

function logPath(repo) {
  return path.join(repo, 'data', 'photoreal', 'sessions.log');
}

function tileUrl(origin) {
  return `${origin}/photoreal/tile?path=${encodeURIComponent(TILE_PATH)}`;
}

function upstream(status, body, type) {
  const buffer = Buffer.from(body);
  return {
    status,
    headers: {
      get(name) {
        return name.toLowerCase() === 'content-type' ? type : null;
      },
    },
    text: () => Promise.resolve(buffer.toString('utf8')),
    arrayBuffer: () =>
      Promise.resolve(
        buffer.buffer.slice(
          buffer.byteOffset,
          buffer.byteOffset + buffer.byteLength,
        ),
      ),
  };
}

function successFetch(calls) {
  return (url) => {
    calls.n += 1;
    if (String(url).includes('/v1/3dtiles/root.json')) {
      return Promise.resolve(upstream(200, ROOT_BODY, 'application/json'));
    }
    return Promise.resolve(
      upstream(200, 'tile-bytes', 'application/octet-stream'),
    );
  };
}

async function startPhotoreal(repo, fetchImpl) {
  const page = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-bill-page-'));
  fs.writeFileSync(
    path.join(page, 'index.html'),
    `<!doctype html><html><body>${RELEASE_BLOCK}</body></html>`,
  );
  const server = await startLookServer(page, {
    repositoryRoot: repo,
    apiKey: PLANTED_KEY,
    env: {},
    fetch: fetchImpl,
  });
  return { server, page };
}

function removeFixture(repo, page) {
  fs.rmSync(repo, { recursive: true, force: true });
  fs.rmSync(page, { recursive: true, force: true });
}

test('the counter counts tile requests and the root request', async () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-bill-'));
  const calls = { n: 0 };
  const { server, page } = await startPhotoreal(repo, successFetch(calls));
  try {
    const root = await getText(`${server.origin}/photoreal/root.json`);
    assert.equal(root.status, 200);
    const again = await getText(`${server.origin}/photoreal/root.json`);
    assert.equal(again.status, 200);
    assert.equal(calls.n, 1);
    const tile = await getText(tileUrl(server.origin));
    assert.equal(tile.status, 200);
    assert.equal(calls.n, 2);
    const status = await getJson(`${server.origin}/photoreal/status`);
    assert.equal(status.status, 200);
    assert.equal(status.body.available, true);
    assert.equal(status.body.count, 2);
    assert.equal(status.body.remaining, 3331);
    assert.equal(status.body.session, 2);
    assert.equal(JSON.stringify(status.body).includes(PLANTED_KEY), false);
    assert.equal(root.text.includes(PLANTED_KEY), false);
    assert.equal(tile.text.includes(PLANTED_KEY), false);
  } finally {
    await server.close();
    removeFixture(repo, page);
  }
});

test('the cap refuses at 3333 total across two sessions and a restart', async () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-bill-'));
  const calls = { n: 0 };
  const fetchImpl = successFetch(calls);
  const first = await startPhotoreal(repo, fetchImpl);
  try {
    assert.equal(
      (await getText(`${first.server.origin}/photoreal/root.json`)).status,
      200,
    );
    assert.equal((await getText(tileUrl(first.server.origin))).status, 200);
  } finally {
    await first.server.close();
    fs.rmSync(first.page, { recursive: true, force: true });
  }
  const saved = JSON.parse(fs.readFileSync(sessionPath(repo), 'utf8'));
  assert.equal(saved.count, 2);

  const second = await startPhotoreal(repo, fetchImpl);
  try {
    const opened = await getJson(`${second.server.origin}/photoreal/status`);
    assert.equal(opened.body.count, 2);
    assert.equal(opened.body.session, 0);
    assert.equal(opened.body.remaining, 3331);
    assert.equal((await getText(tileUrl(second.server.origin))).status, 200);
    let count = 3;
    while (count < 3333) {
      const result = await getText(tileUrl(second.server.origin));
      if (result.status !== 200) {
        throw new Error(`tile request status ${result.status}`);
      }
      count += 1;
    }
    const atCap = await getJson(`${second.server.origin}/photoreal/status`);
    assert.equal(atCap.body.count, 3333);
    assert.equal(atCap.body.remaining, 0);
    assert.equal(atCap.body.session, 3331);
    const callsAtCap = calls.n;
    const refused = await getText(tileUrl(second.server.origin));
    assert.equal(refused.status, 429);
    assert.equal(calls.n, callsAtCap);
    const held = JSON.parse(fs.readFileSync(sessionPath(repo), 'utf8'));
    held.fetchedAt = 0;
    fs.writeFileSync(sessionPath(repo), JSON.stringify(held));
    const root = await getText(`${second.server.origin}/photoreal/root.json`);
    assert.equal(root.status, 429);
    assert.equal(calls.n, callsAtCap);
    const still = await getJson(`${second.server.origin}/photoreal/status`);
    assert.equal(still.body.count, 3333);
    assert.equal(still.body.session, 3331);
    await second.server.close();
    const lines = fs.readFileSync(logPath(repo), 'utf8').trim().split('\n');
    assert.equal(lines.length, 2);
    assert.equal(lines[0].includes(PLANTED_KEY), false);
    assert.equal(lines[1].includes(PLANTED_KEY), false);
  } finally {
    await second.server.close();
    removeFixture(repo, second.page);
  }
});

test('an error response from the provider is counted', async () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-bill-'));
  const calls = { n: 0 };
  const fetchImpl = () => {
    calls.n += 1;
    return Promise.resolve(upstream(503, PLANTED_KEY, 'text/plain'));
  };
  const { server, page } = await startPhotoreal(repo, fetchImpl);
  try {
    const root = await getText(`${server.origin}/photoreal/root.json`);
    assert.equal(root.status, 502);
    assert.equal(root.text.includes(PLANTED_KEY), false);
    const afterRoot = await getJson(`${server.origin}/photoreal/status`);
    assert.equal(afterRoot.body.count, 1);
    assert.equal(calls.n, 1);
    const tile = await getText(tileUrl(server.origin));
    assert.equal(tile.status, 502);
    assert.equal(tile.text.includes(PLANTED_KEY), false);
    const afterTile = await getJson(`${server.origin}/photoreal/status`);
    assert.equal(afterTile.body.count, 2);
    assert.equal(afterTile.body.session, 2);
    assert.equal(calls.n, 2);
  } finally {
    await server.close();
    removeFixture(repo, page);
  }
});

test('the key never appears in a body, the status or the session log', async () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-bill-'));
  const calls = { n: 0 };
  const fetchImpl = () => {
    calls.n += 1;
    return Promise.resolve(
      upstream(200, PLANTED_KEY, 'application/octet-stream'),
    );
  };
  const { server, page } = await startPhotoreal(repo, fetchImpl);
  try {
    const root = await getText(`${server.origin}/photoreal/root.json`);
    const tile = await getText(tileUrl(server.origin));
    const status = await getJson(`${server.origin}/photoreal/status`);
    await server.close();
    assert.equal(root.text.includes(PLANTED_KEY), false);
    assert.equal(tile.text.includes(PLANTED_KEY), false);
    assert.equal(JSON.stringify(status.body).includes(PLANTED_KEY), false);
    const log = fs.readFileSync(logPath(repo), 'utf8');
    assert.equal(log.includes(PLANTED_KEY), false);
    assert.equal(log.trim().split('\n').length, 1);
    const stored = fs.readFileSync(sessionPath(repo), 'utf8');
    assert.equal(stored.includes(PLANTED_KEY), false);
    assert.equal(calls.n > 0, true);
  } finally {
    await server.close();
    removeFixture(repo, page);
  }
});

test('the per-view budget stops further tile requests', async () => {
  const photoreal = await import('../photoreal.mjs');
  assert.equal(photoreal.PER_VIEW_BUDGET, 600);
  assert.equal(photoreal.SCREEN_SPACE_ERROR, 24);
  assert.equal(photoreal.screenSpaceErrorFor(0), photoreal.SCREEN_SPACE_ERROR);
  assert.equal(
    photoreal.screenSpaceErrorFor(photoreal.PER_VIEW_BUDGET),
    Number.POSITIVE_INFINITY,
  );
  const tileset = {
    options: {
      loadTiles: true,
      maximumScreenSpaceError: photoreal.SCREEN_SPACE_ERROR,
    },
  };
  let calls = 0;
  let session = 0;
  const fetchTile = photoreal.budgetedTileFetch({
    transport: () => {
      calls += 1;
      session += 1;
      return Promise.resolve(new Response('ok'));
    },
    used: () => session,
    onHold: () => photoreal.holdView(tileset),
  });
  for (let index = 0; index < photoreal.PER_VIEW_BUDGET; index += 1) {
    const response = await fetchTile(`/photoreal/tile?n=${index}`);
    assert.equal(response.status, 200);
  }
  assert.equal(calls, photoreal.PER_VIEW_BUDGET);
  const stopped = await fetchTile('/photoreal/tile?n=over');
  assert.equal(stopped.status, 429);
  assert.equal(calls, photoreal.PER_VIEW_BUDGET);
  assert.equal(tileset.options.loadTiles, false);
  assert.equal(
    tileset.options.maximumScreenSpaceError,
    Number.POSITIVE_INFINITY,
  );
  const source = fs.readFileSync(
    new URL('../photoreal-mode.ts', import.meta.url),
    'utf8',
  );
  assert.equal(source.includes('budgetedTileFetch('), true);
  assert.equal(source.includes('SCREEN_SPACE_ERROR'), true);
  assert.equal(source.includes('holdView('), true);
});

test('copyright lines are ordered by how often they occur', () => {
  assert.deepEqual(
    aggregateCopyrights([
      'Landsat / Copernicus;Data SIO',
      'Landsat / Copernicus',
    ]),
    ['Landsat / Copernicus', 'Data SIO'],
  );
});

// F4: accounting failures never become a fresh allowance.
test('F4 corrupt, invalid and unreadable accounting state refuses every forward', async () => {
  for (const state of [
    '{',
    'null',
    '{}',
    '{"count":-1,"fetchedAt":0,"root":""}',
    '{"count":0.5,"fetchedAt":0,"root":""}',
    '{"count":1,"root":""}',
    '{"count":1,"fetchedAt":-1,"root":""}',
    '{"count":1,"fetchedAt":0,"root":5}',
    'directory',
    'missing',
  ]) {
    const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-corrupt-'));
    fs.mkdirSync(path.dirname(sessionPath(repo)), { recursive: true });
    if (state === 'directory') fs.mkdirSync(sessionPath(repo));
    else if (state !== 'missing') fs.writeFileSync(sessionPath(repo), state);
    const calls = { n: 0 };
    const { server, page } = await startPhotoreal(repo, successFetch(calls));
    try {
      assert.equal(
        (await getText(`${server.origin}/photoreal/root.json`)).status,
        503,
        state,
      );
      assert.equal((await getText(tileUrl(server.origin))).status, 503, state);
      assert.equal(calls.n, 0, state);
    } finally {
      await server.close();
      removeFixture(repo, page);
    }
  }
});

test('F4 persistence failure refuses before transport', async () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-persist-'));
  fs.mkdirSync(`${sessionPath(repo)}.tmp`, { recursive: true });
  fs.writeFileSync(
    sessionPath(repo),
    JSON.stringify({ count: 0, fetchedAt: 0, root: '' }),
  );
  const calls = { n: 0 };
  const { server, page } = await startPhotoreal(repo, successFetch(calls));
  try {
    assert.equal((await getText(tileUrl(server.origin))).status, 503);
    assert.equal(calls.n, 0);
  } finally {
    await server.close();
    removeFixture(repo, page);
  }
});

test('F4 transport rejection and interrupted responses are already durably charged', async () => {
  for (const route of ['root', 'tile']) {
    for (const interrupted of [false, true]) {
      const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-reserved-'));
      let reserved;
      const { server, page } = await startPhotoreal(repo, async () => {
        reserved = JSON.parse(fs.readFileSync(sessionPath(repo), 'utf8')).count;
        if (!interrupted) throw new Error('planted rejection');
        return {
          status: 200,
          headers: { get: () => 'application/json' },
          text: () => Promise.reject(new Error('planted interruption')),
          arrayBuffer: () => Promise.reject(new Error('planted interruption')),
        };
      });
      try {
        const url =
          route === 'root'
            ? `${server.origin}/photoreal/root.json`
            : tileUrl(server.origin);
        assert.equal((await getText(url)).status, 502);
        assert.equal(reserved, 1);
        assert.equal(
          JSON.parse(fs.readFileSync(sessionPath(repo), 'utf8')).count,
          1,
        );
        assert.equal(
          (await getJson(`${server.origin}/photoreal/status`)).body.session,
          1,
        );
      } finally {
        await server.close();
        removeFixture(repo, page);
      }
    }
  }
});

test('F4 concurrent server instances share an exclusive project reservation', async () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-exclusive-'));
  fs.mkdirSync(path.dirname(sessionPath(repo)), { recursive: true });
  fs.writeFileSync(
    sessionPath(repo),
    JSON.stringify({ count: MAX_BILLABLE - 1, fetchedAt: 0, root: '' }),
  );
  let release;
  let entered;
  const started = new Promise((done) => {
    entered = done;
  });
  const held = new Promise((done) => {
    release = done;
  });
  let calls = 0;
  let duplicated;
  const duplicate = new Promise((done) => {
    duplicated = done;
  });
  const transport = async () => {
    calls += 1;
    entered();
    if (calls > 1) duplicated({ status: 200 });
    await held;
    return upstream(200, 'bytes', 'application/octet-stream');
  };
  const first = await startPhotoreal(repo, transport);
  const second = await startPhotoreal(repo, transport);
  try {
    const pending = getText(tileUrl(first.server.origin));
    await started;
    const otherPending = getText(tileUrl(second.server.origin));
    const duringReservation = await Promise.race([otherPending, duplicate]);
    release();
    const [one, two] = await Promise.all([pending, otherPending]);
    assert.ok([429, 503].includes(duringReservation.status));
    assert.equal(one.status, 200);
    assert.ok([429, 503].includes(two.status));
    assert.equal(calls, 1);
    assert.equal(
      JSON.parse(fs.readFileSync(sessionPath(repo), 'utf8')).count,
      MAX_BILLABLE,
    );
  } finally {
    release();
    await first.server.close();
    await second.server.close();
    removeFixture(repo, first.page);
    fs.rmSync(second.page, { recursive: true, force: true });
  }
});

test('F4 missing reservation boundary and abandoned project lock refuse dispatch', async () => {
  const { resolveTile } = await import('../photoreal.mjs');
  let calls = 0;
  const transport = async () => {
    calls += 1;
    return upstream(200, ROOT_BODY, 'application/json');
  };
  assert.equal(
    (
      await resolveRoot({
        key: PLANTED_KEY,
        record: null,
        now: 1,
        fetchRoot: transport,
      })
    ).status,
    503,
  );
  assert.equal(
    (
      await resolveTile({
        key: PLANTED_KEY,
        record: null,
        pathAndQuery: TILE_PATH,
        fetchTile: transport,
      })
    ).status,
    503,
  );
  assert.equal(calls, 0);
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-abandoned-'));
  fs.mkdirSync(`${sessionPath(repo)}.lock`, { recursive: true });
  const { server, page } = await startPhotoreal(repo, transport);
  try {
    assert.equal(
      (await getText(`${server.origin}/photoreal/root.json`)).status,
      503,
    );
    assert.equal((await getText(tileUrl(server.origin))).status, 503);
    assert.equal(calls, 0);
    assert.equal(fs.existsSync(`${sessionPath(repo)}.lock`), true);
  } finally {
    await server.close();
    removeFixture(repo, page);
  }
});
