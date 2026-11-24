import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { EventEmitter, once } from 'node:events';
import {
  chmodSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import { afterEach, test } from 'node:test';
import { pathToFileURL } from 'node:url';
import { createScopePeg } from '../e2e/opening-server-peg.mjs';
import { startServerGroup, stopServerGroup } from '../e2e/opening-server.mjs';

const WEB = path.resolve(import.meta.dirname, '../..');
const TMP = path.resolve(WEB, '../.overnight/tmp');
const HELPER_URL = pathToFileURL(
  path.join(WEB, 'tests', 'e2e', 'opening-server.mjs'),
).href;
const SOCKET_CWD = process.cwd();
const ownedLeaders = new Map();
const PEG = path.resolve(import.meta.dirname, '../e2e/opening-server-peg.mjs');
const BOUND_MS = 15_000;
const POLL_MS = 50;
const REAP_MS = 5_000;
// How long the harness waits for a peg to accept while a group is still
// starting, and how long a token handshake may take once connected.
const PEG_READY_MS = 5_000;
const HANDSHAKE_MS = 2_000;
const SLEEPER = 'setInterval(() => {}, 1e9)';
const newToken = () => randomBytes(8).toString('hex');

// A second cleanup boundary survives assertions and guard-deletion plants in
// reap itself. It uses only owned ChildProcess handles, never numeric IDs.
afterEach(async () => {
  for (const owner of ownedLeaders.values()) await settleOwner(owner);
  ownedLeaders.clear();
});

// Seeded PRNG: generated registration domains stay reproducible.
function mulberry32(seed) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Eval'd children: a leader that sleeps, spawns a scope peg and — only
// after the peg announces a held harness connection ('H' on the peg's
// stdout) — a grandchild sleeper inside its own process group. The peg
// listens on `pegSock` and verifies the scope `token`; the held
// connection is the live scope handle the harness's cleanup attaches to,
// held for the group's whole life and never recreated from the pathname.
// The grandchild's pid is recorded in `pidFile` so a test can prove the
// teardown reached more than the leader — and prove no descendant starts
// before the scope is held. `pegPidFile`, when given, records the peg's
// own pid so a test can kill the peg alone.
const pegSpawn = (pegArgv) =>
  `const __peg = require('node:child_process').spawn(` +
  `process.execPath, ${pegArgv}, { stdio: ['ignore', 'pipe', 'ignore'] });` +
  `__peg.on('error', () => {});` +
  `__peg.stdout.on('error', () => {});` +
  `__peg.stdout.once('data', () => {`;
const pegArgv = (pegSock, token, peg = PEG) =>
  `[${JSON.stringify(peg)}, ${JSON.stringify(pegSock)}, ` +
  `${JSON.stringify(token)}, ${JSON.stringify(SOCKET_CWD)}]`;
const spawnGrandchild = (pidFile) =>
  `const c = require('node:child_process').spawn(` +
  `process.execPath, ['-e', '${SLEEPER}'], { stdio: 'ignore' });` +
  `require('node:fs').writeFileSync(${JSON.stringify(pidFile)}, String(c.pid));`;
const recordPegPid = (pegPidFile) =>
  pegPidFile === undefined
    ? ''
    : `require('node:fs').writeFileSync(` +
      `${JSON.stringify(pegPidFile)}, String(__peg.pid));`;
const leaderScript = (pidFile, pegSock, token, pegPidFile, peg = PEG) =>
  pegSpawn(pegArgv(pegSock, token, peg)) +
  spawnGrandchild(pidFile) +
  '});' +
  recordPegPid(pegPidFile) +
  SLEEPER;
const exitingLeaderScript = (pidFile, pegSock, token) =>
  pegSpawn(pegArgv(pegSock, token)) +
  `const c = require('node:child_process').spawn(` +
  `process.execPath, ['-e', '${SLEEPER}'], { stdio: 'ignore' });` +
  `c.unref();` +
  `require('node:fs').writeFileSync(${JSON.stringify(pidFile)}, String(c.pid));` +
  '});';
// A leader whose grandchild ignores SIGTERM: only the SIGKILL step reaps it.
const deafLeaderScript = (pidFile, pegSock, token) =>
  pegSpawn(pegArgv(pegSock, token)) +
  `const c = require('node:child_process').spawn(` +
  `process.execPath, ['-e', 'process.on("SIGTERM", () => {});' + '${SLEEPER}'],` +
  `{ stdio: 'ignore' });` +
  `require('node:fs').writeFileSync(${JSON.stringify(pidFile)}, String(c.pid));` +
  '});' +
  SLEEPER;
// A leader whose "peg" never binds and never announces 'H': the scope is
// never attachable and no descendant may start.
const hungLeaderScript = (pidFile) =>
  pegSpawn(`['-e', '${SLEEPER}']`) + spawnGrandchild(pidFile) + '});' + SLEEPER;
// Records 'R' once the SIGTERM handler is installed, then 'T' if it fires.
const termSpyScript = (marker) =>
  `const fs = require('node:fs');` +
  `process.on('SIGTERM', () => {` +
  `fs.writeFileSync(${JSON.stringify(marker)}, 'T');` +
  `process.exit(0);` +
  `});` +
  `fs.writeFileSync(${JSON.stringify(marker)}, 'R');` +
  SLEEPER;
// Ignores SIGTERM and records 'R' once that handler is installed.
const termDeafScript = (marker) =>
  `process.on('SIGTERM', () => {});` +
  `require('node:fs').writeFileSync(${JSON.stringify(marker)}, 'R');` +
  SLEEPER;

// A simulated worker: starts a group through the helper, registers the
// group's scope handle — the socket path and the issued scope token, as
// one JSON line — into `scopeFile` synchronously at spawn (before any
// reporting can fail), then reports the group id on stdout and dies by
// process.exit without calling stop. `commandScript` is the server
// command; `killLog` makes the worker first wrap process.kill so every
// signal lands in the log.
const workerScript = (
  pidFile,
  scopeFile,
  killLog,
  commandScript,
  pegSock,
  token,
) =>
  `import fs from 'node:fs';` +
  (killLog === undefined
    ? ''
    : `const realKill = process.kill;` +
      `process.kill = (pid, sig) => {` +
      `fs.appendFileSync(${JSON.stringify(killLog)},` +
      `JSON.stringify([pid, sig === undefined ? null : sig]) + '\\n');` +
      `return realKill(pid, sig);` +
      `};`) +
  `const { startServerGroup } = await import(${JSON.stringify(HELPER_URL)});` +
  `const proc = startServerGroup(` +
  `process.execPath,` +
  `['-e', ${JSON.stringify(commandScript ?? leaderScript(pidFile, pegSock, token))}],` +
  `{ register: () =>` +
  `fs.appendFileSync(${JSON.stringify(scopeFile)},` +
  `JSON.stringify([${JSON.stringify(pegSock)}, ${JSON.stringify(token)}]) + '\\n') });` +
  `process.stdout.write(String(proc.pid) + '\\n');` +
  `process.stdin.once('data', () => process.exit(0));`;

function alive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function groupAlive(pgid) {
  return alive(-pgid);
}

async function poll(fn, ms = BOUND_MS) {
  const deadline = Date.now() + ms;
  while (Date.now() < deadline) {
    // Awaited: an async probe (socketRefused) must resolve, never pass by
    // returning a truthy pending promise.
    if (await fn()) return true;
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  }
  return fn();
}

function tmpdir() {
  mkdirSync(TMP, { recursive: true });
  return mkdtempSync(path.join(TMP, 'opening-server-'));
}

// Bind every actor to the captured creation-time cwd: the relative path
// fits sun_path even in a long worktree, and a command may use another cwd.
function pegsock(dir) {
  return path.relative(SOCKET_CWD, path.join(dir, 'peg.sock'));
}

// Reuse the supervisor/sentinel pair as an independent cleanup owner.
// Register synchronously, before any wait or assertion can lose the handle.
function ownedLeader(script, sock, token, options = {}) {
  return startServerGroup(process.execPath, ['-e', script], {
    ...options,
    register: (proc) => ownedLeaders.set(scopeKey(sock, token), proc),
  });
}

// Bounded read of the first reported line: a silent worker fails inside
// `ms` instead of hanging, and the stream is destroyed so its writer can go.
async function readLine(stream, ms = BOUND_MS) {
  const reading = (async () => {
    let text = '';
    for await (const chunk of stream) {
      text += chunk;
      if (text.includes('\n')) return text;
    }
    return text;
  })();
  let timer;
  try {
    return await Promise.race([
      reading,
      new Promise((_, reject) => {
        timer = setTimeout(() => {
          stream.destroy();
          reject(new Error(`readLine timed out after ${ms} ms`));
        }, ms);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

// Bounded wait for a child's exit: resolves [code, signal] like 'exit',
// rejects inside `ms` for a child that never dies.
async function waitExit(proc, ms = BOUND_MS) {
  if (proc.exitCode !== null || proc.signalCode !== null) {
    return [proc.exitCode, proc.signalCode];
  }
  let timer;
  try {
    return await Promise.race([
      once(proc, 'exit'),
      new Promise((_, reject) => {
        timer = setTimeout(
          () =>
            reject(
              new Error(`process ${proc.pid} did not exit within ${ms} ms`),
            ),
          ms,
        );
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

// Bounded single write: resolves the callback's error (or undefined for
// a callback without one), rejects inside `ms` for a callback that never
// fires — a stream that withholds its callback cannot hang the caller.
async function boundedWrite(stream, chunk, ms) {
  return await new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error(`write timed out after ${ms} ms`)),
      ms,
    );
    stream.write(chunk, (error) => {
      clearTimeout(timer);
      resolve(error ?? undefined);
    });
  });
}

// One-shot liveness probe of a socket path: true when a connection is
// refused (a bound file with no listener — the stale-socket state), false
// when a listener answers or the file is absent. A probe is not a release
// channel; a live peg just ignores it.
function socketRefused(sockPath) {
  return new Promise((resolve) => {
    const conn = net.createConnection(sockPath);
    conn.on('error', () => {});
    conn.once('connect', () => {
      conn.destroy();
      resolve(false);
    });
    conn.once('error', (error) => resolve(error.code === 'ECONNREFUSED'));
  });
}

// server.close() waits on accepted connections and its callback can
// outlive the event loop: the server's tracked conns are destroyed and
// the close itself is bounded.
async function closeServer(server) {
  for (const conn of server.conns ?? []) conn.destroy();
  await Promise.race([
    new Promise((resolve) => server.close(resolve)),
    new Promise((resolve) => setTimeout(resolve, 1_000)),
  ]);
}

// Every scope the harness has touched, keyed by path+token. A scope's
// outcome is the cleanup verdict for that key and is terminal once set:
// 'held' (live owner connection), 'released' (ended by the harness and
// confirmed by intent plus the independent owner's exit), 'lost' (closed
// before release, without intent, or without the witness — channel loss is
// never a teardown), 'failed' (never held, with its reason). There is no
// clean outcome other than 'released'.
const heldScopes = new Map();
const scopeKey = (sockPath, token) => `${sockPath}\n${token}`;

function recordScope(scope) {
  heldScopes.set(scopeKey(scope.path, scope.token), scope);
  return scope;
}

// Wait for the peg's 'K' after the scope token was sent: 'K' verifies
// ownership of this exact peg; a close, an error or the bound fails the
// handshake — a foreign listener is never treated as the peg.
async function raceHandshake(conn, deadline) {
  let buf = '';
  return await Promise.race([
    new Promise((resolve) => {
      conn.on('data', (chunk) => {
        buf += chunk;
        if (buf.includes('K')) resolve('K');
      });
      conn.once('close', () => resolve('peer closed the handshake'));
      conn.once('error', (error) => resolve(`socket error ${error.code}`));
    }),
    new Promise((resolve) =>
      setTimeout(
        () => resolve('no handshake reply'),
        Math.max(1, Math.min(HANDSHAKE_MS, deadline - Date.now())),
      ),
    ),
  ]);
}

// Attach ONE identity-bound connection to the peg at `sockPath`: connect
// while the peg is still starting (ENOENT or a bound-but-not-listening
// file), present the token and wait for 'K'. The held connection is the
// only release channel for the group's whole life. Anything else is
// failed cleanup with its reason recorded — never "clean": a path that
// stayed ENOENT is "not ready", a persistently refused one is a stale
// socket, an answering listener that cannot complete the handshake is an
// identity mismatch, and an unexpected error is propagated, not retried.
async function holdScope(sockPath, token, ms = PEG_READY_MS) {
  const existing = heldScopes.get(scopeKey(sockPath, token));
  // A scope is never re-attached: a recorded verdict stands, and a lost
  // channel is never recreated through the reusable pathname.
  if (existing) return existing;
  const scope = {
    path: sockPath,
    token,
    conn: null,
    buf: '',
    outcome: 'failed',
    reason: 'attach never ran',
  };
  const deadline = Date.now() + ms;
  let lastCode = 'ENOENT';
  for (;;) {
    let conn;
    try {
      conn = net.createConnection(sockPath);
    } catch (error) {
      scope.reason = `attach threw: ${error.code ?? error.message}`;
      return recordScope(scope);
    }
    conn.on('error', () => {});
    // `once` rejects if 'error' fires first: fold that into the state so
    // ENOENT/ECONNREFUSED and unexpected codes are handled, not thrown.
    const state = await Promise.race([
      once(conn, 'connect').then(
        () => 'connect',
        (error) => error,
      ),
      new Promise((resolve) =>
        setTimeout(
          () => resolve('retry'),
          Math.max(1, Math.min(POLL_MS, deadline - Date.now())),
        ),
      ),
    ]);
    if (state === 'connect') {
      conn.write(`${token}\n`);
      const reply = await raceHandshake(conn, deadline);
      if (reply === 'K') {
        scope.conn = conn;
        scope.outcome = 'held';
        scope.reason = '';
        conn.on('data', (chunk) => {
          scope.buf += chunk;
        });
        conn.once('close', () => {
          if (scope.outcome === 'held') {
            scope.outcome = 'lost';
            scope.reason = 'held connection closed before release';
          }
        });
        return recordScope(scope);
      }
      conn.destroy();
      scope.reason = `identity mismatch: ${reply}`;
      return recordScope(scope);
    }
    conn.destroy();
    if (state instanceof Error) {
      lastCode = state.code ?? lastCode;
      if (state.code !== 'ENOENT' && state.code !== 'ECONNREFUSED') {
        scope.reason = `unexpected socket error: ${state.code}`;
        return recordScope(scope);
      }
    }
    if (Date.now() >= deadline) {
      scope.reason =
        lastCode === 'ECONNREFUSED'
          ? 'stale socket: a bound path with no listener'
          : 'peg not ready by its deadline';
      return recordScope(scope);
    }
  }
}

// 'B' means intent only. A real scope also has an independently owned
// supervisor: its SIGKILL exit and EOF from the pipe held by BOTH
// supervisor and sentinel witness the group's member-pinned teardown. A peg that flushes B
// and dies alone cannot satisfy that witness. Missing intent, closure or
// witness remains lost; reap still invokes the independent owner's cleanup.
async function releaseScope(scope, deadline) {
  if (scope.outcome !== 'held') return;
  scope.outcome = 'releasing';
  scope.conn.end();
  const closed =
    scope.conn.destroyed ||
    (await Promise.race([
      once(scope.conn, 'close').then(
        () => true,
        () => true,
      ),
      new Promise((resolve) =>
        setTimeout(() => resolve(false), Math.max(1, deadline - Date.now())),
      ),
    ]));
  const owner = ownedLeaders.get(scopeKey(scope.path, scope.token));
  const completed =
    owner &&
    (await poll(
      () => owner.signalCode === 'SIGKILL' && owner.stdio[3].readableEnded,
      Math.max(1, Math.min(500, deadline - Date.now())),
    ));
  if (closed && scope.buf.includes('B') && completed) {
    scope.outcome = 'released';
    scope.reason = '';
  } else {
    scope.outcome = 'lost';
    scope.reason = !closed
      ? 'held connection did not close inside its bound'
      : !scope.buf.includes('B')
        ? 'held connection closed without the peg teardown intent'
        : 'peg teardown intent without independent completion';
    scope.conn.destroy();
  }
}

// stopServerGroup may return after a supervisor killed from outside;
// the sentinel still owns its grace. Await its independently held pipe.
async function settleOwner(owner) {
  await stopServerGroup(owner);
  assert.equal(
    await poll(() => owner.stdio[3].readableEnded, REAP_MS + 1000),
    true,
    'independent owner completion was not verified',
  );
}

// Bounded finally cleanup: end the held identity-bound channel, then stop
// the independent supervisor through its owned pipe even for a lost or
// unattached peg. Never probe or signal a numeric group ID, nor retry a
// terminal scope through its reusable pathname. Reports distinguish the
// peg protocol's outcome from the fallback owner's cleanup.
async function reap(entries) {
  const refs = new Map();
  const malformed = [];
  const addRef = (sockPath, token) => {
    if (
      typeof sockPath !== 'string' ||
      typeof token !== 'string' ||
      sockPath.length === 0 ||
      token.length === 0
    ) {
      malformed.push(String(sockPath));
      return;
    }
    const key = scopeKey(sockPath, token);
    if (!refs.has(key)) refs.set(key, { path: sockPath, token });
  };
  for (const { proc, scope, peg, token } of entries) {
    if (
      proc &&
      ![...ownedLeaders.values()].includes(proc) &&
      proc.exitCode === null &&
      proc.signalCode === null
    ) {
      try {
        proc.kill('SIGKILL');
      } catch (error) {
        if (error.code !== 'ESRCH') throw error;
      }
    }
    if (peg !== undefined) addRef(peg, token);
    if (scope !== undefined && existsSync(scope)) {
      for (const line of readFileSync(scope, 'utf8').split('\n')) {
        if (line === '') continue;
        try {
          const entry = JSON.parse(line);
          if (!Array.isArray(entry) || entry.length !== 2) {
            malformed.push(line);
          } else {
            addRef(...entry);
          }
        } catch {
          malformed.push(line);
        }
      }
    }
  }
  const deadline = Date.now() + REAP_MS;
  const touched = new Set();
  for (const ref of refs.values()) {
    // One token-verified attach at most; a recorded verdict is returned
    // as-is — 'lost' and 'failed' are never retried through the pathname.
    const scope = await holdScope(
      ref.path,
      ref.token,
      Math.max(1, Math.min(1500, deadline - Date.now())),
    );
    await releaseScope(scope, deadline);
    touched.add(scope);
  }
  // A held scope its caller forgot to list is still released, and
  // reported.
  for (const scope of heldScopes.values()) {
    if (scope.outcome === 'held' && !touched.has(scope)) {
      await releaseScope(scope, deadline);
      touched.add(scope);
    }
  }
  const owners = new Set(entries.map(({ proc }) => proc));
  for (const ref of refs.values()) {
    owners.add(ownedLeaders.get(scopeKey(ref.path, ref.token)));
  }
  for (const owner of owners) {
    if (owner && [...ownedLeaders.values()].includes(owner)) {
      await settleOwner(owner);
    }
  }
  for (const { proc } of entries) {
    while (
      proc &&
      proc.exitCode === null &&
      proc.signalCode === null &&
      Date.now() < deadline
    ) {
      await new Promise((resolve) => setTimeout(resolve, POLL_MS));
    }
  }
  const report = [...touched].map(({ path: p, token: t, outcome, reason }) => ({
    path: p,
    token: t,
    outcome,
    reason,
  }));
  for (const line of malformed) {
    report.push({
      path: line,
      token: '',
      outcome: 'failed',
      reason: 'malformed scope registration',
    });
  }
  return { scopes: report };
}

// Assert a reap report carries exactly the expected scopes: the same set
// of path+token keys, each with its expected outcome and — when given —
// a reason the recorded failure must match. Nothing less is clean.
function expectScopes(report, expected) {
  const actual = new Map(
    report.scopes.map((s) => [scopeKey(s.path, s.token), s]),
  );
  assert.equal(
    actual.size,
    expected.length,
    `scope report: ${JSON.stringify(report.scopes)}`,
  );
  for (const want of expected) {
    const got = actual.get(scopeKey(want.path, want.token));
    assert.ok(got, `scope ${want.path} not in report`);
    assert.equal(
      got.outcome,
      want.outcome,
      `scope ${want.path}: ${got.reason}`,
    );
    if (want.reason !== undefined) {
      assert.match(got.reason, want.reason, `scope ${want.path}`);
    }
  }
}

test('a worker exit without stop reaps the whole detached group', async () => {
  const dir = tmpdir();
  let worker;
  let pgid;
  const pegSock = pegsock(dir);
  const token = newToken();
  try {
    const pidFile = path.join(dir, 'grandchild.pid');
    const scopeFile = path.join(dir, 'scopes.txt');
    worker = spawn(
      process.execPath,
      [
        '--input-type=module',
        '--eval',
        workerScript(pidFile, scopeFile, undefined, undefined, pegSock, token),
      ],
      { stdio: ['pipe', 'pipe', 'inherit'] },
    );
    pgid = Number(await readLine(worker.stdout));
    assert.ok(Number.isInteger(pgid) && pgid > 0, `leader pid: ${pgid}`);
    // The scope is held before any descendant starts: the peg's 'H' gates
    // the grandchild on this one identity-bound connection.
    const scope = await holdScope(pegSock, token);
    assert.equal(scope.outcome, 'held', scope.reason);
    assert.equal(
      await poll(() => groupAlive(pgid)),
      true,
      'group did not form',
    );
    assert.equal(await poll(() => existsSync(pidFile)), true, 'no grandchild');
    const grandchild = Number(readFileSync(pidFile, 'utf8'));
    assert.notEqual(grandchild, pgid);
    worker.stdin.write('\n');
    const [code, signal] = await waitExit(worker);
    assert.equal(code, 0);
    assert.equal(signal, null);
    assert.equal(
      await poll(() => !groupAlive(pgid)),
      true,
      'a group member survived the worker exit',
    );
    assert.equal(
      await poll(() => scope.outcome === 'lost'),
      true,
      'the peg survived its own group',
    );
    assert.equal(alive(grandchild), false, 'grandchild survived');
  } finally {
    // The supervisor tore the group down; the peg died inside it, so the
    // held channel is lost — reported failed, never clean. The teardown
    // itself is verified by the assertion above, not by the channel.
    const report = await reap([
      { proc: worker, scope: path.join(dir, 'scopes.txt') },
      { peg: pegSock, token },
    ]);
    expectScopes(report, [
      { path: pegSock, token, outcome: 'lost', reason: /closed/ },
    ]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a SIGKILLed worker still reaps the whole detached group', async () => {
  const dir = tmpdir();
  let worker;
  let pgid;
  const pegSock = pegsock(dir);
  const token = newToken();
  try {
    const pidFile = path.join(dir, 'grandchild.pid');
    const scopeFile = path.join(dir, 'scopes.txt');
    worker = spawn(
      process.execPath,
      [
        '--input-type=module',
        '--eval',
        workerScript(
          pidFile,
          scopeFile,
          undefined,
          deafLeaderScript(pidFile, pegSock, token),
          pegSock,
          token,
        ),
      ],
      { stdio: ['pipe', 'pipe', 'inherit'] },
    );
    pgid = Number(await readLine(worker.stdout));
    assert.ok(Number.isInteger(pgid) && pgid > 0, `leader pid: ${pgid}`);
    const scope = await holdScope(pegSock, token);
    assert.equal(scope.outcome, 'held', scope.reason);
    assert.equal(
      await poll(() => groupAlive(pgid)),
      true,
      'group did not form',
    );
    assert.equal(await poll(() => existsSync(pidFile)), true, 'no grandchild');
    const grandchild = Number(readFileSync(pidFile, 'utf8'));
    assert.notEqual(grandchild, pgid);
    worker.kill('SIGKILL');
    const [, signal] = await waitExit(worker);
    assert.equal(signal, 'SIGKILL');
    assert.equal(
      await poll(() => !groupAlive(pgid)),
      true,
      'a group member survived the SIGKILLed worker',
    );
    assert.equal(
      await poll(() => scope.outcome === 'lost'),
      true,
      'the peg survived its own group',
    );
    assert.equal(alive(grandchild), false, 'grandchild survived');
  } finally {
    const report = await reap([
      { proc: worker, scope: path.join(dir, 'scopes.txt') },
      { peg: pegSock, token },
    ]);
    expectScopes(report, [
      { path: pegSock, token, outcome: 'lost', reason: /closed/ },
    ]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a retired owner never signals a freed group id', async () => {
  const dir = tmpdir();
  let worker;
  let pgid;
  let replacement;
  const pegSock = pegsock(dir);
  const token = newToken();
  try {
    const pidFile = path.join(dir, 'grandchild.pid');
    const scopeFile = path.join(dir, 'scopes.txt');
    const killLog = path.join(dir, 'kills.ndjson');
    writeFileSync(killLog, '');
    worker = spawn(
      process.execPath,
      [
        '--input-type=module',
        '--eval',
        workerScript(pidFile, scopeFile, killLog, undefined, pegSock, token),
      ],
      { stdio: ['pipe', 'pipe', 'inherit'] },
    );
    pgid = Number(await readLine(worker.stdout));
    assert.ok(Number.isInteger(pgid) && pgid > 0, `leader pid: ${pgid}`);
    const scope = await holdScope(pegSock, token);
    assert.equal(scope.outcome, 'held', scope.reason);
    assert.equal(
      await poll(() => groupAlive(pgid)),
      true,
      'group did not form',
    );
    // The group disappears out from under the worker's ownership record.
    process.kill(-pgid, 'SIGKILL');
    assert.equal(
      await poll(() => !groupAlive(pgid)),
      true,
      'group did not die',
    );
    assert.equal(
      await poll(() => scope.outcome === 'lost'),
      true,
      'the dead peg left the channel reported held',
    );
    // A replacement group formed after the id was freed must stay untouched.
    replacement = spawn(process.execPath, ['-e', SLEEPER], {
      detached: true,
      stdio: 'ignore',
    });
    replacement.unref();
    worker.stdin.write('\n');
    await waitExit(worker);
    const kills = readFileSync(killLog, 'utf8')
      .split('\n')
      .filter(Boolean)
      .map((line) => JSON.parse(line));
    assert.deepEqual(
      kills.filter(([target]) => target === pgid || target === -pgid),
      [],
      'stale ownership signalled the freed group id',
    );
    assert.equal(
      await poll(() => alive(replacement.pid)),
      true,
      'a replacement group was signalled',
    );
  } finally {
    const report = await reap([
      { proc: worker, scope: path.join(dir, 'scopes.txt') },
      { peg: pegSock, token },
      { proc: replacement },
    ]);
    expectScopes(report, [
      {
        path: pegSock,
        token,
        outcome: 'lost',
        reason: /closed before release/,
      },
    ]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('stop reaps the leader and its grandchild and retires ownership', async () => {
  const dir = tmpdir();
  let proc;
  let pgid;
  const pegSock = pegsock(dir);
  const token = newToken();
  try {
    const pidFile = path.join(dir, 'grandchild.pid');
    const listenersBefore = process.listenerCount('exit');
    proc = startServerGroup(process.execPath, [
      '-e',
      leaderScript(pidFile, pegSock, token),
    ]);
    pgid = proc.pid;
    assert.ok(typeof pgid === 'number' && pgid > 0);
    const scope = await holdScope(pegSock, token);
    assert.equal(scope.outcome, 'held', scope.reason);
    assert.equal(
      await poll(() => groupAlive(pgid)),
      true,
      'group did not form',
    );
    assert.equal(await poll(() => existsSync(pidFile)), true, 'no grandchild');
    const grandchild = Number(readFileSync(pidFile, 'utf8'));
    await stopServerGroup(proc);
    assert.equal(alive(pgid), false, 'leader survived');
    assert.equal(
      await poll(() => !alive(grandchild)),
      true,
      'grandchild survived',
    );
    assert.equal(
      await poll(() => !groupAlive(pgid)),
      true,
      'a group member survived',
    );
    assert.equal(
      await poll(() => scope.outcome === 'lost'),
      true,
      'the peg survived its own group',
    );
    // A repeated stop is harmless and emits no signal at all: the retired
    // owner can never reach a group id freed for reuse.
    const calls = [];
    const realKill = process.kill;
    process.kill = (pid, sig) => {
      calls.push([pid, sig]);
      return realKill.call(process, pid, sig);
    };
    try {
      await stopServerGroup(proc);
    } finally {
      process.kill = realKill;
    }
    assert.deepEqual(calls, [], 'a repeated stop emitted a signal');
    assert.equal(
      process.listenerCount('exit'),
      listenersBefore,
      'exit guard left behind',
    );
  } finally {
    const report = await reap([{ proc }, { peg: pegSock, token }]);
    expectScopes(report, [
      { path: pegSock, token, outcome: 'lost', reason: /closed/ },
    ]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('stop signals the group with SIGTERM before it escalates', async () => {
  const dir = tmpdir();
  let proc;
  let pgid;
  try {
    const marker = path.join(dir, 'term.txt');
    proc = startServerGroup(process.execPath, ['-e', termSpyScript(marker)]);
    pgid = proc.pid;
    assert.equal(
      await poll(
        () => existsSync(marker) && readFileSync(marker, 'utf8') === 'R',
      ),
      true,
      'handler not installed',
    );
    await stopServerGroup(proc);
    assert.equal(readFileSync(marker, 'utf8'), 'T');
    assert.equal(await poll(() => !groupAlive(pgid)), true);
  } finally {
    await reap([{ proc }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('stop escalates to SIGKILL when the server ignores SIGTERM', async () => {
  const dir = tmpdir();
  let proc;
  let pgid;
  try {
    const marker = path.join(dir, 'ready.txt');
    proc = startServerGroup(process.execPath, ['-e', termDeafScript(marker)]);
    pgid = proc.pid;
    assert.equal(
      await poll(() => existsSync(marker)),
      true,
      'handler not installed',
    );
    await stopServerGroup(proc);
    assert.equal(
      await poll(() => !groupAlive(pgid)),
      true,
      'a group member survived the escalation',
    );
  } finally {
    await reap([{ proc }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('stop reaps a grandchild after the command already exited', async () => {
  const dir = tmpdir();
  let proc;
  let pgid;
  const pegSock = pegsock(dir);
  const token = newToken();
  try {
    const pidFile = path.join(dir, 'grandchild.pid');
    proc = startServerGroup(process.execPath, [
      '-e',
      exitingLeaderScript(pidFile, pegSock, token),
    ]);
    pgid = proc.pid;
    const scope = await holdScope(pegSock, token);
    assert.equal(scope.outcome, 'held', scope.reason);
    assert.equal(await poll(() => existsSync(pidFile)), true, 'no grandchild');
    const grandchild = Number(readFileSync(pidFile, 'utf8'));
    assert.equal(
      await poll(() => groupAlive(pgid)),
      true,
      'grandchild is not in the group',
    );
    await stopServerGroup(proc);
    assert.equal(
      await poll(() => !groupAlive(pgid)),
      true,
      'grandchild survived',
    );
    assert.equal(
      await poll(() => scope.outcome === 'lost'),
      true,
      'the peg survived its own group',
    );
    assert.equal(await poll(() => !alive(grandchild)), true);
  } finally {
    const report = await reap([{ proc }, { peg: pegSock, token }]);
    expectScopes(report, [
      { path: pegSock, token, outcome: 'lost', reason: /closed/ },
    ]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('stop settles on a command that never spawned', async () => {
  let proc;
  try {
    proc = startServerGroup('eii-invented-missing-command', []);
    proc.on('error', () => {});
    await stopServerGroup(proc);
  } finally {
    await reap([{ proc }]);
  }
});

test('stop reaps orphaned members when the supervisor died first', async () => {
  const dir = tmpdir();
  let proc;
  let pgid;
  const pegSock = pegsock(dir);
  const token = newToken();
  try {
    const pidFile = path.join(dir, 'grandchild.pid');
    proc = startServerGroup(process.execPath, [
      '-e',
      leaderScript(pidFile, pegSock, token),
    ]);
    pgid = proc.pid;
    const scope = await holdScope(pegSock, token);
    assert.equal(scope.outcome, 'held', scope.reason);
    assert.equal(
      await poll(() => groupAlive(pgid)),
      true,
      'group did not form',
    );
    assert.equal(await poll(() => existsSync(pidFile)), true, 'no grandchild');
    const grandchild = Number(readFileSync(pidFile, 'utf8'));
    // Only the supervisor dies; the orphaned members keep the group id and
    // the sentinel — a live member of the group — reaps them, never the
    // worker's remembered id.
    proc.kill('SIGKILL');
    await waitExit(proc);
    assert.equal(
      await poll(() => groupAlive(pgid)),
      true,
      'orphans are not in the group',
    );
    await stopServerGroup(proc);
    assert.equal(
      await poll(() => !groupAlive(pgid)),
      true,
      'an orphaned member survived',
    );
    assert.equal(
      await poll(() => scope.outcome === 'lost'),
      true,
      'the peg survived its own group',
    );
    assert.equal(await poll(() => !alive(grandchild)), true);
  } finally {
    const report = await reap([{ proc }, { peg: pegSock, token }]);
    expectScopes(report, [
      { path: pegSock, token, outcome: 'lost', reason: /closed/ },
    ]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('stop settles on a supervisor that already exited', async () => {
  let proc;
  try {
    proc = startServerGroup('eii-invented-missing-command', []);
    proc.on('error', () => {});
    proc.kill('SIGKILL');
    await waitExit(proc);
    await stopServerGroup(proc);
  } finally {
    await reap([{ proc }]);
  }
});

test('a first stop never signals a group id that was freed and reused', async () => {
  const dir = tmpdir();
  let proc;
  let pgid;
  let replacement;
  const pegSock = pegsock(dir);
  const token = newToken();
  try {
    const pidFile = path.join(dir, 'grandchild.pid');
    proc = startServerGroup(process.execPath, [
      '-e',
      leaderScript(pidFile, pegSock, token),
    ]);
    pgid = proc.pid;
    const scope = await holdScope(pegSock, token);
    assert.equal(scope.outcome, 'held', scope.reason);
    assert.equal(
      await poll(() => groupAlive(pgid)),
      true,
      'group did not form',
    );
    // The whole original group dies and the supervisor exits: the group id
    // is freed for reuse before the first stopServerGroup call.
    process.kill(-pgid, 'SIGKILL');
    assert.equal(
      await poll(() => !groupAlive(pgid)),
      true,
      'group did not die',
    );
    assert.equal(
      await poll(() => scope.outcome === 'lost'),
      true,
      'the dead peg left its channel reported held',
    );
    await waitExit(proc);
    // A real replacement group formed after the id was freed.
    replacement = spawn(process.execPath, ['-e', SLEEPER], {
      detached: true,
      stdio: 'ignore',
    });
    replacement.unref();
    // Deterministic reuse: an unrelated group now answers every probe of
    // -pgid. Any remembered-id probe or signal lands in `calls` — the seam
    // stays installed through the finally cleanup, so reap itself is
    // covered: a retired numeric id is not a scope handle and must never
    // be signalled or probed.
    const calls = [];
    const realKill = process.kill;
    process.kill = (pid, sig) => {
      calls.push([pid, sig === undefined ? 0 : sig]);
      if (pid === -pgid) return true;
      return realKill.call(process, pid, sig);
    };
    try {
      await stopServerGroup(proc);
      assert.equal(
        alive(replacement.pid),
        true,
        'a replacement group was signalled',
      );
      const report = await reap([
        { proc },
        { pgid },
        { peg: pegSock, token },
        { proc: replacement },
      ]);
      expectScopes(report, [
        {
          path: pegSock,
          token,
          outcome: 'lost',
          reason: /closed before release/,
        },
      ]);
    } finally {
      process.kill = realKill;
    }
    // A positive-pid call is an owned signal to a live child; only a
    // negative target can reach a group, so a stale group id shows up as
    // -pgid — and it must never be signalled or probed.
    assert.deepEqual(
      calls.filter(([target]) => target === -pgid),
      [],
      'stale ownership probed or signalled the reused group id',
    );
  } finally {
    await reap([{ proc }, { peg: pegSock, token }, { proc: replacement }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('an unreported group is still reaped from its registered scope', async () => {
  const dir = tmpdir();
  const pidFile = path.join(dir, 'grandchild.pid');
  const scopeFile = path.join(dir, 'scopes.txt');
  const pegSock = pegsock(dir);
  const token = newToken();
  let worker;
  try {
    worker = spawn(
      process.execPath,
      [
        '--input-type=module',
        '--eval',
        workerScript(pidFile, scopeFile, undefined, undefined, pegSock, token),
      ],
      { stdio: ['pipe', 'pipe', 'inherit'] },
    );
    // stdout is never consumed: the registration written at spawn, before
    // reporting or assertions can fail, is the only ownership record the
    // harness holds.
    assert.equal(
      await poll(() => {
        if (!existsSync(scopeFile)) return false;
        const [p, t] = JSON.parse(readFileSync(scopeFile, 'utf8'));
        return p === pegSock && t === token;
      }),
      true,
      'the group was not registered at creation',
    );
    // The live handle itself is the evidence the peg came up: it holds
    // its socket only while it lives, as a member of the group.
    assert.equal(
      await poll(() => existsSync(pegSock)),
      true,
      'the scope peg did not come up',
    );
    worker.kill('SIGKILL');
    await waitExit(worker);
    // finally's reap must settle the scope with no reported group id and
    // no held connection: the group already died through the ownership
    // pipe, the peg with it, so the dead socket reports failed — never
    // clean, and never reattached to whatever bound the path.
    assert.equal(
      await poll(() => socketRefused(pegSock)),
      true,
      'the dead peg still answers connections',
    );
  } finally {
    const report = await reap([{ proc: worker, scope: scopeFile }]);
    expectScopes(report, [
      {
        path: pegSock,
        token,
        outcome: 'failed',
        reason: /stale socket/,
      },
    ]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('reap releases a registered scope through its held peg connection', async () => {
  const dir = tmpdir();
  const pidFile = path.join(dir, 'grandchild.pid');
  const scopeFile = path.join(dir, 'scopes.txt');
  const pegSock = pegsock(dir);
  const token = newToken();
  let stray;
  try {
    stray = ownedLeader(leaderScript(pidFile, pegSock, token), pegSock, token);
    stray.unref();
    writeFileSync(scopeFile, `${JSON.stringify([pegSock, token])}\n`);
    const scope = await holdScope(pegSock, token);
    assert.equal(scope.outcome, 'held', scope.reason);
    assert.equal(
      await poll(() => groupAlive(stray.pid)),
      true,
      'stray group did not form',
    );
    assert.equal(await poll(() => existsSync(pidFile)), true, 'no grandchild');
    const grandchild = Number(readFileSync(pidFile, 'utf8'));
    const report = await reap([{ proc: stray }, { scope: scopeFile }]);
    expectScopes(report, [{ path: pegSock, token, outcome: 'released' }]);
    assert.equal(
      await poll(() => !groupAlive(stray.pid)),
      true,
      'stray group survived the scope release',
    );
    assert.equal(
      await poll(() => !alive(grandchild)),
      true,
      'grandchild survived',
    );
  } finally {
    await reap([{ proc: stray }, { scope: scopeFile }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a rebound socket path never reaches the replacement group through cleanup', async () => {
  const dir = tmpdir();
  const pidFileA = path.join(dir, 'grandchild-a.pid');
  const pidFileB = path.join(dir, 'grandchild-b.pid');
  const pegPidFile = path.join(dir, 'peg-a.pid');
  const pegSock = pegsock(dir);
  const tokenA = newToken();
  const tokenB = newToken();
  let strayA;
  let strayB;
  try {
    strayA = ownedLeader(
      leaderScript(pidFileA, pegSock, tokenA, pegPidFile),
      pegSock,
      tokenA,
    );
    strayA.unref();
    const scopeA = await holdScope(pegSock, tokenA);
    assert.equal(scopeA.outcome, 'held', scopeA.reason);
    assert.equal(
      await poll(() => existsSync(pegPidFile)),
      true,
      'the original peg did not come up',
    );
    // The original peg dies; its stale pathname is unlinked and rebound
    // by another group's peg — the exact reuse CF3 found.
    process.kill(Number(readFileSync(pegPidFile, 'utf8')), 'SIGKILL');
    assert.equal(
      await poll(() => scopeA.outcome === 'lost'),
      true,
      'the dead peg left its channel reported held',
    );
    rmSync(pegSock, { force: true });
    strayB = ownedLeader(
      leaderScript(pidFileB, pegSock, tokenB),
      pegSock,
      tokenB,
    );
    strayB.unref();
    assert.equal(
      await poll(() => existsSync(pegSock) && groupAlive(strayB.pid)),
      true,
      'the replacement group did not form on the rebound path',
    );
    // Cleanup over the recorded scope — the same pathname a live
    // replacement now answers — must never reach it.
    const report = await reap([
      { proc: strayA },
      { peg: pegSock, token: tokenA },
    ]);
    expectScopes(report, [
      {
        path: pegSock,
        token: tokenA,
        outcome: 'lost',
        reason: /closed before release/,
      },
    ]);
    assert.equal(
      groupAlive(strayB.pid),
      true,
      'the replacement group received a release',
    );
    // Its members prove its own group exists; they never prove ownership.
    assert.equal(
      existsSync(pidFileB),
      false,
      'the replacement received a held connection it never earned',
    );
  } finally {
    // Both groups retain separate supervisor handles through finally.
    const report = await reap([
      { proc: strayA },
      { proc: strayB },
      { peg: pegSock, token: tokenB },
    ]);
    expectScopes(report, [
      { path: pegSock, token: tokenB, outcome: 'released' },
    ]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a peg killed alone reports failed cleanup and its owner removes siblings', async () => {
  const dir = tmpdir();
  const pidFile = path.join(dir, 'grandchild.pid');
  const pegPidFile = path.join(dir, 'peg.pid');
  const pegSock = pegsock(dir);
  const token = newToken();
  let stray;
  try {
    stray = ownedLeader(
      leaderScript(pidFile, pegSock, token, pegPidFile),
      pegSock,
      token,
    );
    stray.unref();
    const scope = await holdScope(pegSock, token);
    assert.equal(scope.outcome, 'held', scope.reason);
    assert.equal(
      await poll(() => existsSync(pegPidFile) && existsSync(pidFile)),
      true,
      'the group did not form',
    );
    const grandchild = Number(readFileSync(pidFile, 'utf8'));
    // Only the peg dies: the channel closes while every sibling lives.
    process.kill(Number(readFileSync(pegPidFile, 'utf8')), 'SIGKILL');
    assert.equal(
      await poll(() => scope.outcome === 'lost'),
      true,
      'the dead peg left its channel reported held',
    );
    assert.equal(alive(grandchild), true, 'grandchild died with the peg');
    const report = await reap([{ proc: stray }, { peg: pegSock, token }]);
    // The lost peg stays lost even though the independent owner reaps
    // its siblings; fallback cleanup cannot retroactively certify the peg.
    expectScopes(report, [
      {
        path: pegSock,
        token,
        outcome: 'lost',
        reason: /closed before release/,
      },
    ]);
    assert.equal(
      alive(grandchild),
      false,
      'independent cleanup left a descendant',
    );
    assert.equal(
      groupAlive(stray.pid),
      false,
      'the independent owner left its group alive',
    );
    assert.equal(
      await poll(() => !groupAlive(stray.pid)),
      true,
      'owned teardown did not empty the group',
    );
  } finally {
    await reap([{ proc: stray }, { peg: pegSock, token }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a stale socket file fails the scope as stale, never clean', async () => {
  const dir = tmpdir();
  const pegSock = pegsock(dir);
  const token = newToken();
  let holder;
  try {
    // A killed holder leaves its bound socket file with no listener.
    holder = spawn(
      process.execPath,
      [
        '-e',
        `require('node:net').createServer().listen(${JSON.stringify(pegSock)})`,
      ],
      { stdio: 'ignore' },
    );
    assert.equal(
      await poll(() => existsSync(pegSock)),
      true,
      'the holder did not bind',
    );
    holder.kill('SIGKILL');
    await waitExit(holder);
    assert.equal(
      existsSync(pegSock),
      true,
      'a killed listener did not leave a stale file',
    );
    const scope = await holdScope(pegSock, token, 1_500);
    assert.equal(scope.outcome, 'failed');
    assert.match(scope.reason, /stale socket/);
    const report = await reap([{ peg: pegSock, token }]);
    expectScopes(report, [
      { path: pegSock, token, outcome: 'failed', reason: /stale socket/ },
    ]);
  } finally {
    await reap([{ proc: holder }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a taken socket path fails the scope, never the foreign listener', async () => {
  const dir = tmpdir();
  const pegSock = pegsock(dir);
  const token = newToken();
  // server.close() waits on accepted connections and its callback can
  // outlive the event loop: the foreign listener's conns are tracked and
  // destroyed, and the close is bounded.
  const blocker = net.createServer((conn) => {
    conn.on('error', () => {});
    blocker.conns.add(conn);
    conn.once('close', () => blocker.conns.delete(conn));
  });
  blocker.conns = new Set();
  let stray;
  try {
    await new Promise((resolve) => blocker.listen(pegSock, resolve));
    stray = ownedLeader(
      leaderScript(path.join(dir, 'grandchild.pid'), pegSock, token),
      pegSock,
      token,
    );
    stray.unref();
    // The peg cannot bind and exits; the listener answering the path is
    // not ours — the handshake must refuse it, never hold or release it.
    const scope = await holdScope(pegSock, token, 3_000);
    assert.equal(scope.outcome, 'failed');
    assert.match(scope.reason, /identity mismatch: no handshake reply/);
    const report = await reap([{ proc: stray }, { peg: pegSock, token }]);
    expectScopes(report, [
      {
        path: pegSock,
        token,
        outcome: 'failed',
        reason: /identity mismatch/,
      },
    ]);
    assert.equal(
      blocker.listening,
      true,
      'the foreign listener was treated as the peg',
    );
  } finally {
    await closeServer(blocker);
    await reap([{ proc: stray }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a peg that never listens fails its scope by the readiness deadline', async () => {
  const dir = tmpdir();
  const pidFile = path.join(dir, 'grandchild.pid');
  const pegSock = pegsock(dir);
  const token = newToken();
  let stray;
  try {
    stray = ownedLeader(hungLeaderScript(pidFile), pegSock, token);
    stray.unref();
    const scope = await holdScope(pegSock, token, 1_500);
    assert.equal(scope.outcome, 'failed');
    assert.match(scope.reason, /peg not ready by its deadline/);
    // No held connection ever formed, so no descendant may start.
    assert.equal(
      await poll(() => existsSync(pidFile), 1_000),
      false,
      'a descendant started before the scope was held',
    );
    assert.equal(groupAlive(stray.pid), true, 'the group leader is not alive');
  } finally {
    await reap([{ proc: stray }, { peg: pegSock, token }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a wrong scope token is refused, never held', async () => {
  const dir = tmpdir();
  const pidFile = path.join(dir, 'grandchild.pid');
  const pegSock = pegsock(dir);
  const token = newToken();
  let stray;
  try {
    stray = ownedLeader(leaderScript(pidFile, pegSock, token), pegSock, token);
    stray.unref();
    const scope = await holdScope(pegSock, newToken(), 3_000);
    assert.equal(scope.outcome, 'failed');
    assert.match(scope.reason, /identity mismatch: peer closed the handshake/);
    assert.equal(
      existsSync(pidFile),
      false,
      'a descendant started on an unheld scope',
    );
    const report = await reap([{ proc: stray }, { peg: pegSock, token }]);
    expectScopes(report, [{ path: pegSock, token, outcome: 'released' }]);
    assert.equal(
      await poll(() => !groupAlive(stray.pid)),
      true,
      'the group survived its rightful release',
    );
  } finally {
    await reap([{ proc: stray }, { peg: pegSock, token }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('unverified and duplicate connections never release the group', async () => {
  const dir = tmpdir();
  const pidFile = path.join(dir, 'grandchild.pid');
  const pegSock = pegsock(dir);
  const token = newToken();
  let stray;
  try {
    stray = ownedLeader(leaderScript(pidFile, pegSock, token), pegSock, token);
    stray.unref();
    assert.equal(await poll(() => existsSync(pegSock)), true);
    // No owner exists yet: this connection must exercise the token timer,
    // not the immediate duplicate refusal.
    const raw = net.createConnection(pegSock);
    raw.on('error', () => {});
    await once(raw, 'connect');
    assert.equal(
      await poll(() => raw.destroyed, 4_000),
      true,
      'an unverified connection was left open',
    );
    const scope = await holdScope(pegSock, token);
    assert.equal(scope.outcome, 'held', scope.reason);
    // A second verified connection is refused too: one owner per peg.
    const dup = net.createConnection(pegSock);
    dup.on('error', () => {});
    await once(dup, 'connect');
    dup.write(`${token}\n`);
    assert.equal(
      await poll(() => dup.destroyed, 500),
      true,
      'a duplicate connection was held',
    );
    scope.conn.write('ignored post-handshake bytes\n');
    assert.equal(
      await poll(() => scope.outcome !== 'held', 300),
      false,
      'post-handshake bytes changed ownership',
    );
    assert.equal(scope.outcome, 'held');
    assert.equal(
      groupAlive(stray.pid),
      true,
      'an unowned connection released the group',
    );
    const report = await reap([{ proc: stray }, { peg: pegSock, token }]);
    expectScopes(report, [{ path: pegSock, token, outcome: 'released' }]);
    assert.equal(
      await poll(() => !groupAlive(stray.pid)),
      true,
      'the held connection did not release',
    );
  } finally {
    await reap([{ proc: stray }, { peg: pegSock, token }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a destroyed held connection makes the peg take its own group', async () => {
  const dir = tmpdir();
  const pidFile = path.join(dir, 'grandchild.pid');
  const pegSock = pegsock(dir);
  const token = newToken();
  let stray;
  try {
    stray = ownedLeader(leaderScript(pidFile, pegSock, token), pegSock, token);
    stray.unref();
    const scope = await holdScope(pegSock, token);
    assert.equal(scope.outcome, 'held', scope.reason);
    // Losing the owner channel is itself a teardown trigger for the peg:
    // no sibling outlives a lost channel, and the loss is reported, never
    // reported clean.
    scope.conn.destroy();
    assert.equal(await poll(() => scope.outcome === 'lost'), true);
    assert.equal(
      await poll(() => !groupAlive(stray.pid)),
      true,
      'the group survived a lost owner channel',
    );
  } finally {
    const report = await reap([{ proc: stray }, { peg: pegSock, token }]);
    expectScopes(report, [
      { path: pegSock, token, outcome: 'lost', reason: /closed/ },
    ]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('an unexpected socket error is propagated, never classified clean', async () => {
  const dir = tmpdir();
  const sealed = path.join(dir, 'sealed');
  mkdirSync(sealed);
  const pegSock = pegsock(sealed);
  const token = newToken();
  // No search permission on a path component: EACCES is neither ENOENT
  // nor ECONNREFUSED, so it is propagated, not retried until 'not ready'.
  chmodSync(sealed, 0o000);
  try {
    const scope = await holdScope(pegSock, token, 1_000);
    assert.equal(scope.outcome, 'failed');
    assert.match(scope.reason, /unexpected socket error: EACCES/);
  } finally {
    chmodSync(sealed, 0o700);
    rmSync(dir, { recursive: true, force: true });
  }
});

// A listener that answers 'K' but is not a peg: its 'end' handling never
// writes the 'B' commit (or never closes), so a release through it can
// never be reported clean.
const fakePeg = (pegSock, token, onEnd) => {
  const conns = new Set();
  // allowHalfOpen: 'end' alone must not answer the release — only the
  // case's own onEnd decides whether the connection closes.
  const server = net.createServer({ allowHalfOpen: true }, (conn) => {
    conn.on('error', () => {});
    conns.add(conn);
    conn.once('close', () => conns.delete(conn));
    conn.setEncoding('utf8');
    let line = '';
    conn.on('data', (chunk) => {
      line += chunk;
      if (line.includes('\n') && line.trim() === token) conn.write('K\n');
    });
    conn.on('end', onEnd);
  });
  server.conns = conns;
  return server;
};

// A completed independent owner isolates intent/closure guards from the
// completion guard. It is already exited, so it owns no live process.
const completedOwner = () => ({
  exitCode: null,
  signalCode: 'SIGKILL',
  stdio: [null, null, null, { readableEnded: true }],
});

test('a release without the peg teardown commit is lost, never clean', async () => {
  const dir = tmpdir();
  const pegSock = pegsock(dir);
  const token = newToken();
  const fake = fakePeg(pegSock, token, function () {
    this.end(); // closes without writing 'B'
  });
  try {
    await new Promise((resolve) => fake.listen(pegSock, resolve));
    ownedLeaders.set(scopeKey(pegSock, token), completedOwner());
    const scope = await holdScope(pegSock, token);
    assert.equal(scope.outcome, 'held', scope.reason);
    const report = await reap([{ peg: pegSock, token }]);
    expectScopes(report, [
      {
        path: pegSock,
        token,
        outcome: 'lost',
        reason: /closed without the peg teardown intent/,
      },
    ]);
  } finally {
    ownedLeaders.delete(scopeKey(pegSock, token));
    await closeServer(fake);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a release the peg never closes is lost inside its bound', async () => {
  const dir = tmpdir();
  const pegSock = pegsock(dir);
  const token = newToken();
  const fake = fakePeg(pegSock, token, function () {
    this.write('B\n'); // intent without closure; the owner is completed
  });
  try {
    await new Promise((resolve) => fake.listen(pegSock, resolve));
    ownedLeaders.set(scopeKey(pegSock, token), completedOwner());
    const scope = await holdScope(pegSock, token);
    assert.equal(scope.outcome, 'held', scope.reason);
    await releaseScope(scope, Date.now() + 800);
    assert.equal(scope.outcome, 'lost');
    assert.match(scope.reason, /did not close inside its bound/);
  } finally {
    ownedLeaders.delete(scopeKey(pegSock, token));
    await closeServer(fake);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a registration without a token is malformed, never attached', async () => {
  const dir = tmpdir();
  const pegSock = pegsock(dir);
  try {
    const report = await reap([{ peg: pegSock }]);
    expectScopes(report, [
      {
        path: pegSock,
        token: '',
        outcome: 'failed',
        reason: /malformed scope registration/,
      },
    ]);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// Oracle over the registration-file input domain of reap: for every
// generated file — empty or holding any mix of fresh keys, duplicates,
// blank lines and malformed shapes — the report is exactly one terminal
// entry per unique (path, token) key plus one 'malformed scope
// registration' per bad line. Paths never answer, so every valid key is
// 'failed'. Dedup, blank-skip and malformed-catch are the guards under
// test; the generator covers the domain the named cases sample.
test('reap settles any registration file: an oracle over the scope domain', async () => {
  const rng = mulberry32(0xb17);
  const tokenPool = ['t0', 't1'];
  for (let round = 0; round < 10; round++) {
    const dir = tmpdir();
    const scopeFile = path.join(dir, 'scopes.txt');
    const valid = [];
    const seen = new Set();
    let malformed = 0;
    const lines = [];
    const n = 1 + Math.floor(rng() * 6);
    for (let i = 0; i < n; i++) {
      const shape = Math.floor(rng() * 8);
      if (shape <= 2) {
        // A fresh key while slots last, then duplicates of earlier keys.
        const dup = valid.length === 2 || (valid.length > 0 && rng() < 0.5);
        const entry = dup
          ? valid[Math.floor(rng() * valid.length)]
          : [`${pegsock(dir)}-${valid.length}`, tokenPool[valid.length]];
        if (!dup) valid.push(entry);
        seen.add(scopeKey(entry[0], entry[1]));
        lines.push(JSON.stringify(entry));
      } else if (shape === 3) {
        lines.push('');
      } else if (shape === 4) {
        lines.push('{"not":"an array"}');
        malformed++;
      } else if (shape === 5) {
        lines.push('["only-a-path"]');
        malformed++;
      } else if (shape === 7) {
        const invalid = [
          [{ path: 'invented.sock' }, 't'],
          ['sock', {}],
          ['', 't'],
          ['sock', ''],
          ['sock', 't', 'extra'],
          [null, 't'],
        ];
        lines.push(JSON.stringify(invalid[Math.floor(rng() * invalid.length)]));
        malformed++;
      } else {
        lines.push(`junk-${i}`);
        malformed++;
      }
    }
    writeFileSync(scopeFile, lines.join('\n'));
    const report = await reap([{ scope: scopeFile }]);
    assert.equal(
      report.scopes.length,
      seen.size + malformed,
      `round ${round}: wrong report size`,
    );
    const keys = new Set(report.scopes.map((s) => scopeKey(s.path, s.token)));
    for (const key of seen) {
      assert.ok(keys.has(key), `round ${round}: missing ${key}`);
    }
    assert.equal(
      report.scopes.filter((s) => s.reason === 'malformed scope registration')
        .length,
      malformed,
      `round ${round}: malformed count`,
    );
    for (const s of report.scopes) {
      assert.match(
        s.outcome,
        /^(failed|lost|released)$/,
        `round ${round}: non-terminal ${s.outcome}`,
      );
    }
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a broken ownership pipe surfaces only accepted shutdown errors', async () => {
  const dir = tmpdir();
  let proc;
  let pgid;
  try {
    proc = startServerGroup(process.execPath, ['-e', SLEEPER]);
    pgid = proc.pid;
    assert.equal(
      await poll(() => groupAlive(pgid)),
      true,
      'group did not form',
    );
    proc.kill('SIGKILL');
    await waitExit(proc);
    // A real dead reader: a write reports a shutdown-class pipe error.
    // Each write is bounded on its own; a withheld callback cannot hang
    // the loop.
    let saw;
    const deadline = Date.now() + BOUND_MS;
    while (saw === undefined && Date.now() < deadline) {
      saw = await boundedWrite(
        proc.stdin,
        'x',
        Math.max(1, deadline - Date.now()),
      );
      if (saw === undefined)
        await new Promise((resolve) => setTimeout(resolve, POLL_MS));
    }
    assert.ok(
      saw !== undefined &&
        (saw.code === 'EPIPE' || saw.code === 'ERR_STREAM_DESTROYED'),
      `expected a shutdown-class pipe error, saw ${saw?.code ?? saw}`,
    );
    // The listener swallows only those codes: an injected EPIPE is a
    // shutdown, an injected EPERM must surface.
    const epipe = new Error('injected');
    epipe.code = 'EPIPE';
    proc.stdin.emit('error', epipe);
    const eperm = new Error('injected');
    eperm.code = 'EPERM';
    assert.throws(
      () => proc.stdin.emit('error', eperm),
      (error) => error.code === 'EPERM',
    );
  } finally {
    await reap([{ proc }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('reap tolerates ESRCH but propagates an unexpected kill error', async () => {
  const gone = {
    exitCode: null,
    signalCode: null,
    kill() {
      this.exitCode = 0;
      const error = new Error('gone');
      error.code = 'ESRCH';
      throw error;
    },
  };
  await reap([{ proc: gone }]);
  const denied = {
    exitCode: null,
    signalCode: null,
    kill() {
      this.exitCode = 0;
      const error = new Error('denied');
      error.code = 'EPERM';
      throw error;
    },
  };
  await assert.rejects(
    () => reap([{ proc: denied }]),
    (error) => error.code === 'EPERM',
  );
});

test('a sentinel started without a valid group id exits', async () => {
  let sentinel;
  try {
    sentinel = spawn(process.execPath, [
      path.resolve(import.meta.dirname, '../e2e/opening-server-sentinel.mjs'),
      'bogus',
    ]);
    const [code] = await waitExit(sentinel);
    assert.equal(code, 1);
  } finally {
    await reap([{ proc: sentinel }]);
  }
});

test('readLine, waitExit and write waits fail inside their bound', async () => {
  const dir = tmpdir();
  let sleeper;
  try {
    sleeper = spawn(process.execPath, ['-e', SLEEPER], {
      stdio: ['pipe', 'pipe', 'inherit'],
    });
    await assert.rejects(() => readLine(sleeper.stdout, 300), /timed out/);
    await assert.rejects(() => waitExit(sleeper, 300), /did not exit/);
    // A stream whose callback never comes fails inside the bound.
    const withheld = { write() {} };
    await assert.rejects(() => boundedWrite(withheld, 'x', 300), /timed out/);
  } finally {
    await reap([{ proc: sleeper }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

// One parameterized startup-refusal case: a sentinel that cannot report
// ready makes the supervisor refuse startup — exit 4, no command, no
// surviving group member. `sentinel` is the injected sentinel argv.
async function refusedStartup(dir, sentinel, ms = BOUND_MS, register) {
  const marker = path.join(dir, 'command-started');
  const proc = startServerGroup(
    process.execPath,
    [
      '-e',
      `require('node:fs').writeFileSync(${JSON.stringify(marker)}, 'x');` +
        SLEEPER,
    ],
    { sentinel, register },
  );
  try {
    const [code, signal] = await waitExit(proc, ms);
    assert.equal(code, 4, 'startup was not refused');
    assert.equal(signal, null);
    assert.equal(
      existsSync(marker),
      false,
      'the command ran without a sentinel',
    );
    assert.equal(
      await poll(() => !groupAlive(proc.pid)),
      true,
      'a group member survived the refused startup',
    );
    return proc;
  } catch (error) {
    await settleOwner(proc);
    throw error;
  }
}

test('a sentinel that cannot spawn keeps the command from starting', async () => {
  const dir = tmpdir();
  let proc;
  try {
    proc = await refusedStartup(dir, [
      path.join(dir, 'missing-sentinel-binary'),
      'x',
    ]);
  } finally {
    await reap([{ proc }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a sentinel that exits before reporting keeps the command from starting', async () => {
  const dir = tmpdir();
  let proc;
  try {
    const badSentinel = path.join(dir, 'early-exit-sentinel.mjs');
    writeFileSync(badSentinel, 'process.exit(0);\n');
    proc = await refusedStartup(dir, [process.execPath, badSentinel]);
  } finally {
    await reap([{ proc }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a sentinel that never reports fails startup inside the bound', async () => {
  const dir = tmpdir();
  let proc;
  try {
    const hungSentinel = path.join(dir, 'hung-sentinel.mjs');
    writeFileSync(hungSentinel, 'setInterval(() => {}, 1e9);\n');
    proc = await refusedStartup(dir, [process.execPath, hungSentinel]);
  } finally {
    await reap([{ proc }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a scope peg started without a socket path exits', async () => {
  let peg;
  try {
    peg = spawn(process.execPath, [PEG]);
    const [code] = await waitExit(peg);
    assert.equal(code, 1);
  } finally {
    await reap([{ proc: peg }]);
  }
});

test('a scope peg exits when its socket path is taken', async () => {
  const dir = tmpdir();
  const pegSock = pegsock(dir);
  const blocker = net.createServer();
  let peg;
  try {
    await new Promise((resolve) => blocker.listen(pegSock, resolve));
    peg = spawn(process.execPath, [PEG, pegSock, newToken()]);
    const [code] = await waitExit(peg);
    assert.equal(code, 1);
  } finally {
    await closeServer(blocker);
    await reap([{ proc: peg }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('S3-B18 malformed registrations never reach a socket operation', async () => {
  const dir = tmpdir();
  const file = path.join(dir, 'scopes.txt');
  const invalid = [
    null,
    {},
    'text',
    'ab',
    [],
    ['sock'],
    ['sock', 't', 'extra'],
    [{ path: 'invented.sock' }, 't'],
    ['sock', {}],
    ['', 't'],
    ['sock', ''],
    [null, 't'],
    ['sock', null],
    [3, 't'],
    ['sock', false],
  ];
  const realConnect = net.createConnection;
  const calls = [];
  net.createConnection = (...args) => {
    calls.push(args);
    throw new Error('socket operation reached');
  };
  try {
    for (const entry of invalid) {
      writeFileSync(file, JSON.stringify(entry));
      const report = await reap([{ scope: file }]);
      assert.equal(report.scopes.length, 1);
      assert.equal(report.scopes[0].reason, 'malformed scope registration');
      assert.deepEqual(calls, [], JSON.stringify(entry));
    }
  } finally {
    net.createConnection = realConnect;
    rmSync(dir, { recursive: true, force: true });
  }
});

test('S3-B18 peg-only death and an early assertion retain independent cleanup', async () => {
  const dir = tmpdir();
  const sock = pegsock(dir);
  const token = newToken();
  const pidFile = path.join(dir, 'grandchild.pid');
  const pegFile = path.join(dir, 'peg.pid');
  let proc;
  let grandchild;
  try {
    await assert.rejects(async () => {
      try {
        proc = ownedLeader(
          leaderScript(pidFile, sock, token, pegFile),
          sock,
          token,
        );
        const scope = await holdScope(sock, token);
        assert.equal(scope.outcome, 'held', scope.reason);
        assert.equal(await poll(() => existsSync(pidFile)), true);
        grandchild = Number(readFileSync(pidFile, 'utf8'));
        process.kill(Number(readFileSync(pegFile, 'utf8')), 'SIGKILL');
        assert.equal(await poll(() => scope.outcome === 'lost'), true);
        throw new Error('injected early assertion');
      } finally {
        await reap([{ proc }, { peg: sock, token }]);
      }
    }, /injected early assertion/);
    assert.equal(
      await poll(() => !alive(grandchild)),
      true,
      'descendant survived finally',
    );
  } finally {
    await reap([{ proc }, { peg: sock, token }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('S3-B18 teardown intent followed by peg death is unverified and reaped', async () => {
  const dir = tmpdir();
  const sock = pegsock(dir);
  const token = newToken();
  const pidFile = path.join(dir, 'grandchild.pid');
  const faultPeg = path.join(dir, 'fault-peg.mjs');
  let proc;
  try {
    writeFileSync(
      faultPeg,
      `import { createScopePeg } from ${JSON.stringify(pathToFileURL(PEG).href)};` +
        `process.chdir(${JSON.stringify(SOCKET_CWD)});` +
        `createScopePeg(process.argv[3], () => process.exit(3)).listen(process.argv[2]);`,
    );
    proc = ownedLeader(
      leaderScript(pidFile, sock, token, undefined, faultPeg),
      sock,
      token,
    );
    const scope = await holdScope(sock, token);
    assert.equal(scope.outcome, 'held', scope.reason);
    assert.equal(await poll(() => existsSync(pidFile)), true);
    const child = Number(readFileSync(pidFile, 'utf8'));
    const report = await reap([{ proc }, { peg: sock, token }]);
    expectScopes(report, [
      {
        path: sock,
        token,
        outcome: 'lost',
        reason: /peg teardown intent without independent completion/,
      },
    ]);
    assert.equal(
      await poll(() => !alive(child)),
      true,
      'intent failure leaked descendant',
    );
  } finally {
    await reap([{ proc }, { peg: sock, token }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('S3-B18 a different actor cwd still resolves the creation-time socket', async () => {
  const dir = tmpdir();
  const sock = pegsock(dir);
  const token = newToken();
  let proc;
  try {
    proc = ownedLeader(
      leaderScript(path.join(dir, 'child.pid'), sock, token),
      sock,
      token,
      { cwd: dir },
    );
    const scope = await holdScope(sock, token);
    assert.equal(scope.outcome, 'held', scope.reason);
    const report = await reap([{ proc }, { peg: sock, token }]);
    expectScopes(report, [{ path: sock, token, outcome: 'released' }]);
  } finally {
    await reap([{ proc }, { peg: sock, token }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('S3-B18 attach expiry owns cleanup even when peg readiness arrives late', async () => {
  const dir = tmpdir();
  const sock = pegsock(dir);
  const token = newToken();
  const pegFile = path.join(dir, 'peg.pid');
  const childFile = path.join(dir, 'child.pid');
  let proc;
  try {
    proc = ownedLeader(
      "process.on('SIGTERM', () => {});setTimeout(() => {" +
        leaderScript(childFile, sock, token, pegFile) +
        '}, 1800);' +
        SLEEPER,
      sock,
      token,
    );
    // Reap's attach expires first. The command ignores TERM and starts
    // the peg during the independent owner's grace, before group KILL.
    const report = await reap([{ proc }, { peg: sock, token }]);
    expectScopes(report, [
      {
        path: sock,
        token,
        outcome: 'failed',
        reason: /peg not ready by its deadline/,
      },
    ]);
    assert.equal(existsSync(pegFile), true, 'late peg never started');
    const peg = Number(readFileSync(pegFile, 'utf8'));
    assert.equal(await poll(() => !alive(peg)), true, 'late peg survived');
    assert.equal(
      existsSync(childFile),
      false,
      'unheld scope started a descendant',
    );
  } finally {
    await reap([{ proc }, { peg: sock, token }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('S3-B18 refusedStartup cleans its own handle when readiness is withheld', async () => {
  const dir = tmpdir();
  let proc;
  try {
    await assert.rejects(
      () =>
        refusedStartup(dir, [process.execPath, '-e', SLEEPER], 200, (child) => {
          proc = child;
        }),
      /did not exit within 200 ms/,
    );
    assert.notEqual(
      proc.signalCode ?? proc.exitCode,
      null,
      'helper lost its process handle',
    );
  } finally {
    await stopServerGroup(proc);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('S3-B18 verified socket error-close without EOF tears down exactly once', async () => {
  const calls = [];
  const server = createScopePeg('token', (...args) => calls.push(args), {
    write() {},
  });
  const conn = new EventEmitter();
  conn.setEncoding = () => {};
  conn.write = (_text, done) => done?.();
  conn.end = (done) => done?.();
  conn.destroy = () => conn.emit('close');
  try {
    server.emit('connection', conn);
    conn.emit('data', 'token\n');
    conn.emit('error', new Error('injected verified socket error'));
    conn.emit('close');
    assert.deepEqual(
      calls,
      [[0, 'SIGKILL']],
      'error-close did not trigger teardown',
    );
    conn.emit('close');
    conn.emit('end');
    conn.emit('end');
    assert.deepEqual(
      calls,
      [[0, 'SIGKILL']],
      'repeated callbacks repeated teardown',
    );
  } finally {
    conn.emit('close');
    await closeServer(server);
  }
});

test('S3-B18 ownership is registered synchronously before a helper returns', async () => {
  const dir = tmpdir();
  const sock = pegsock(dir);
  const token = newToken();
  let proc;
  try {
    proc = ownedLeader(SLEEPER, sock, token);
    assert.equal(
      ownedLeaders.get(scopeKey(sock, token)),
      proc,
      'owned handle not registered',
    );
  } finally {
    if (proc) await stopServerGroup(proc);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('S3-B18 reap preserves the live owner until its ownership pipe closes', async () => {
  const dir = tmpdir();
  const sock = pegsock(dir);
  const token = newToken();
  let proc;
  try {
    const marker = path.join(dir, 'ready');
    proc = ownedLeader(termSpyScript(marker), sock, token);
    assert.equal(await poll(() => existsSync(marker)), true);
    const calls = [];
    const kill = proc.kill.bind(proc);
    proc.kill = (...args) => {
      calls.push(args);
      return kill(...args);
    };
    await reap([{ proc }]);
    assert.deepEqual(calls, [], 'reap killed its independent owner directly');
    assert.equal(readFileSync(marker, 'utf8'), 'T');
  } finally {
    if (proc) await stopServerGroup(proc);
    rmSync(dir, { recursive: true, force: true });
  }
});

let hookOwner;
test('S3-B18 emergency hook owns a handle omitted by a caller', () => {
  hookOwner = ownedLeader(SLEEPER, 'hook-owned.sock', newToken());
});
test('S3-B18 emergency hook has settled the omitted handle', async () => {
  try {
    assert.notEqual(
      hookOwner.signalCode ?? hookOwner.exitCode,
      null,
      'emergency owner cleanup did not run',
    );
  } finally {
    await stopServerGroup(hookOwner);
  }
});

test('S3-B18 supervisor death alone cannot certify intent while its sentinel lives', async () => {
  const dir = tmpdir();
  const sock = pegsock(dir);
  const token = newToken();
  const marker = path.join(dir, 'ready');
  const fake = fakePeg(sock, token, function () {
    this.end('B\n');
  });
  let proc;
  try {
    await new Promise((resolve) => fake.listen(sock, resolve));
    proc = ownedLeader(termDeafScript(marker), sock, token);
    assert.equal(await poll(() => existsSync(marker)), true);
    const scope = await holdScope(sock, token);
    assert.equal(scope.outcome, 'held', scope.reason);
    proc.kill('SIGKILL');
    await waitExit(proc);
    assert.equal(
      proc.stdio[3].readableEnded,
      false,
      'sentinel witness closed prematurely',
    );
    const report = await reap([{ proc }, { peg: sock, token }]);
    expectScopes(report, [
      {
        path: sock,
        token,
        outcome: 'lost',
        reason: /peg teardown intent without independent completion/,
      },
    ]);
    assert.equal(proc.stdio[3].readableEnded, true, 'sentinel did not finish');
  } finally {
    await closeServer(fake);
    await reap([{ proc }, { peg: sock, token }]);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('S3-B18 a withheld completion witness has a specific refusal', async () => {
  const dir = tmpdir();
  let proc;
  let witness;
  try {
    proc = ownedLeader(SLEEPER, pegsock(dir), newToken());
    witness = proc.stdio[3];
    proc.stdio[3] = { readableEnded: false };
    await assert.rejects(
      () => settleOwner(proc),
      /independent owner completion was not verified/,
    );
  } finally {
    if (witness) proc.stdio[3] = witness;
    if (proc) await settleOwner(proc);
    rmSync(dir, { recursive: true, force: true });
  }
});

test('S3-B18 intent without an owner or with an unexpected owner exit is unverified', async () => {
  for (const owner of [
    undefined,
    {
      signalCode: 'SIGTERM',
      stdio: [null, null, null, { readableEnded: true }],
    },
  ]) {
    const dir = tmpdir();
    const sock = pegsock(dir);
    const token = newToken();
    const fake = fakePeg(sock, token, function () {
      this.end('B\n');
    });
    try {
      await new Promise((resolve) => fake.listen(sock, resolve));
      if (owner) ownedLeaders.set(scopeKey(sock, token), owner);
      const scope = await holdScope(sock, token);
      assert.equal(scope.outcome, 'held', scope.reason);
      await releaseScope(scope, Date.now() + REAP_MS);
      assert.equal(scope.outcome, 'lost');
      assert.equal(
        scope.reason,
        'peg teardown intent without independent completion',
      );
    } finally {
      ownedLeaders.delete(scopeKey(sock, token));
      await closeServer(fake);
      rmSync(dir, { recursive: true, force: true });
    }
  }
});
