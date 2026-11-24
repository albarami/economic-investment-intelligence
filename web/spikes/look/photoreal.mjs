// The photoreal mode's spend guard and same-origin rewrite. The page's
// server adds the key on the way to Google; this module never reads a key
// from a file and never writes one. Tile bytes are not stored.

export const PRICE_USD_PER_THOUSAND = 6;
export const SPEND_LIMIT_USD = 20;
// Every forwarded root or tile is priced at the first paid tier.
// Free use is ignored. 3,333 requests cost 19.998 dollars; 3,334 would
// reach 20.004.
export const MAX_BILLABLE = Math.floor(
  (SPEND_LIMIT_USD * 1000 - 1) / PRICE_USD_PER_THOUSAND,
);
// The loader's own default screen-space error is 8. 24 is three times
// coarser, which the README estimates at about 400 tiles for one wall view.
export const SCREEN_SPACE_ERROR = 24;
export const PER_VIEW_BUDGET = 600;
// Google's root tileset covers three hours of renderer requests.
export const SESSION_MS = 3 * 60 * 60 * 1000;
export const PROXY_PREFIX = '/photoreal/tile?path=';
const TILE_HOST = 'tile.googleapis.com';

export function googleHost(url) {
  let host;
  try {
    host = new URL(url).hostname.toLowerCase();
  } catch {
    return false;
  }
  return (
    host === 'google.com' ||
    host.endsWith('.google.com') ||
    host === 'googleapis.com' ||
    host.endsWith('.googleapis.com')
  );
}

export function validSession(record) {
  return (
    record !== null &&
    typeof record === 'object' &&
    Number.isSafeInteger(record.count) &&
    record.count >= 0 &&
    Number.isSafeInteger(record.fetchedAt) &&
    record.fetchedAt >= 0 &&
    typeof record.root === 'string'
  );
}

function fresh(record, now) {
  return (
    record !== null &&
    typeof record.root === 'string' &&
    record.root !== '' &&
    typeof record.fetchedAt === 'number' &&
    now - record.fetchedAt < SESSION_MS
  );
}

const PLAIN = 'text/plain; charset=utf-8';

export function billableView(record, session) {
  const count = record?.count ?? 0;
  return {
    count,
    remaining: Math.max(0, MAX_BILLABLE - count),
    session: session ?? 0,
  };
}

export function formatSessionLog(view) {
  return `photoreal billable=${view.count} remaining=${view.remaining} session=${view.session}`;
}

function charged(record, session) {
  return {
    record: {
      count: (record?.count ?? 0) + 1,
      fetchedAt: typeof record?.fetchedAt === 'number' ? record.fetchedAt : 0,
      root: typeof record?.root === 'string' ? record.root : '',
    },
    session: (session ?? 0) + 1,
  };
}

function atCap(record) {
  return (record?.count ?? 0) >= MAX_BILLABLE;
}

// Rewrites tileset URIs onto the page's own origin. The key is not added
// here; the tile route adds it when it calls Google.
export function rewriteTileset(text) {
  return text.replace(/\/v1\/3dtiles\/[^"\\\s]*/g, (uri) => {
    return `${PROXY_PREFIX}${encodeURIComponent(uri)}`;
  });
}

export async function resolveRoot({
  key,
  record,
  session = 0,
  now,
  fetchRoot,
  reserve,
}) {
  if (typeof key !== 'string' || key.trim() === '') {
    return { status: 404, record, session, body: '' };
  }
  if (record !== null && !validSession(record))
    return { status: 503, record, session, body: '' };
  if (fresh(record, now)) {
    return { status: 200, record, session, body: record.root };
  }
  if (atCap(record)) {
    return { status: 429, record, session, body: '' };
  }
  const next = charged(record, session);
  try {
    await reserve(next);
  } catch {
    return { status: 503, record, session, body: '' };
  }
  let raw;
  try {
    raw = await fetchRoot();
  } catch {
    return { status: 502, ...next, body: '' };
  }
  const payload = typeof raw === 'string' ? { status: 200, body: raw } : raw;
  if (payload.status !== 200) {
    return {
      status: 502,
      record: next.record,
      session: next.session,
      body: '',
    };
  }
  const body = rewriteTileset(String(payload.body ?? ''));
  if (body.includes('key=') || body.includes(key)) {
    return {
      status: 502,
      record: next.record,
      session: next.session,
      body: '',
    };
  }
  return {
    status: 200,
    body,
    session: next.session,
    record: { count: next.record.count, fetchedAt: now, root: body },
  };
}

function hidden(body, key) {
  const buffer = Buffer.isBuffer(body) ? body : Buffer.from(body);
  return buffer.includes(key);
}

export async function resolveTile({
  key,
  record,
  session = 0,
  pathAndQuery,
  fetchTile,
  reserve,
}) {
  if (typeof key !== 'string' || key.trim() === '') {
    return {
      status: 404,
      record,
      session,
      body: 'not available',
      type: PLAIN,
    };
  }
  if (record !== null && !validSession(record))
    return {
      status: 503,
      record,
      session,
      body: 'photoreal unavailable',
      type: PLAIN,
    };
  const tile = tilePath(pathAndQuery);
  if (tile === null) {
    return { status: 400, record, session, body: 'bad tile', type: PLAIN };
  }
  if (atCap(record)) {
    return {
      status: 429,
      record,
      session,
      body: 'photoreal unavailable',
      type: PLAIN,
    };
  }
  const target = googleOrigin(tile);
  target.searchParams.set('key', key);
  if (googleHost(target.href) !== true) {
    return { status: 400, record, session, body: 'bad tile', type: PLAIN };
  }
  const next = charged(record, session);
  try {
    await reserve(next);
  } catch {
    return {
      status: 503,
      record,
      session,
      body: 'photoreal unavailable',
      type: PLAIN,
    };
  }
  let response;
  try {
    response = await fetchTile(target);
  } catch {
    return { status: 502, ...next, body: 'tile failed', type: PLAIN };
  }
  if (response.status !== 200) {
    return {
      status: 502,
      record: next.record,
      session: next.session,
      body: 'tile failed',
      type: PLAIN,
    };
  }
  let bytes;
  try {
    bytes = Buffer.from(await response.arrayBuffer());
  } catch {
    return {
      status: 502,
      record: next.record,
      session: next.session,
      body: 'tile failed',
      type: PLAIN,
    };
  }
  const type =
    response.headers.get('content-type') ?? 'application/octet-stream';
  if (tile.includes('.json') || type.includes('json')) {
    const text = rewriteTileset(bytes.toString('utf8'));
    if (text.includes('key=') || text.includes(key)) {
      return {
        status: 502,
        record: next.record,
        session: next.session,
        body: 'tile failed',
        type: PLAIN,
      };
    }
    return {
      status: 200,
      record: next.record,
      session: next.session,
      body: text,
      type: 'application/json; charset=utf-8',
    };
  }
  if (hidden(bytes, key)) {
    return {
      status: 502,
      record: next.record,
      session: next.session,
      body: 'tile failed',
      type: PLAIN,
    };
  }
  return {
    status: 200,
    record: next.record,
    session: next.session,
    body: bytes,
    type,
  };
}

export function screenSpaceErrorFor(sessionCount) {
  if (sessionCount >= PER_VIEW_BUDGET) return Number.POSITIVE_INFINITY;
  return SCREEN_SPACE_ERROR;
}

export function holdView(tileset) {
  tileset.options.loadTiles = false;
  tileset.options.maximumScreenSpaceError =
    screenSpaceErrorFor(PER_VIEW_BUDGET);
}

export function budgetedTileFetch({
  transport,
  used,
  budget = PER_VIEW_BUDGET,
  onHold,
}) {
  return async function fetchWithinBudget(url, init) {
    const session = await used();
    if (session >= budget) {
      if (typeof onHold === 'function') onHold();
      return new Response('', { status: 429 });
    }
    return transport(url, init);
  };
}

export function googleOrigin(pathAndQuery) {
  const url = new URL(pathAndQuery, 'http://127.0.0.1');
  url.protocol = 'https:';
  url.hostname = TILE_HOST;
  url.port = '';
  return url;
}

// A tile path from a rewritten tileset. Returns null when the path is not
// a Google 3D tile path. The caller adds the key and does not log the URL.
export function tilePath(pathAndQuery) {
  if (typeof pathAndQuery !== 'string') return null;
  if (!pathAndQuery.startsWith('/v1/3dtiles/')) return null;
  if (
    pathAndQuery.includes('..') ||
    pathAndQuery.includes('\\') ||
    pathAndQuery.includes('://') ||
    pathAndQuery.includes('key=')
  ) {
    return null;
  }
  let url;
  try {
    url = googleOrigin(pathAndQuery);
  } catch {
    return null;
  }
  if (url.hostname !== TILE_HOST) return null;
  return `${url.pathname}${url.search}`;
}

export function aggregateCopyrights(lines) {
  const counts = new Map();
  for (const line of lines) {
    for (const part of String(line).split(';')) {
      const name = part.trim();
      if (name === '') continue;
      counts.set(name, (counts.get(name) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || (left[0] < right[0] ? -1 : 1))
    .map(([name]) => name);
}

export function copyrightFromTile(tile) {
  const piles = [
    tile?.content?.gltf?.asset?.copyright,
    tile?.content?.asset?.copyright,
    tile?.header?.gltf?.asset?.copyright,
  ];
  const lines = [];
  for (const value of piles) {
    if (typeof value === 'string' && value.trim() !== '') lines.push(value);
  }
  return lines;
}
