/**
 * The detached supervisor of one opening-server process group.
 *
 * Spawned by `startServerGroup`: this process leads a new process group
 * (detached, so the group id is its own pid), spawns the sentinel
 * (opening-server-sentinel.mjs) and then the real command inside that
 * group, and stays alive as the peg — it ignores SIGTERM and holds its
 * event loop — so the group exists for as long as this process owns it
 * and its id can never be recycled into an unrelated group. Its stdin is
 * the ownership pipe: the worker's normal stop closes it, and the kernel
 * closes it on the worker's death by any path including SIGKILL. Either
 * way this process, not the worker, runs the teardown: group SIGTERM,
 * one bounded grace, then group SIGKILL — which takes this process with
 * it, so nothing of the group outlives the ownership record.
 *
 * The command starts only after the sentinel reports ready on stdout:
 * a group without its orphan reaper is never left running a command. A
 * sentinel that fails to spawn, exits or never reports inside READY_MS
 * is handled — startup is refused while this process is the only member,
 * or owned cleanup runs once members exist. If this process dies first,
 * its held write end of the sentinel's stdin closes by the same kernel
 * rule, and the sentinel — a live member of the group — runs the same
 * teardown from inside. Orphan cleanup never falls back on a remembered
 * numeric id probed from outside the group.
 */
import { spawn } from 'node:child_process';
import path from 'node:path';
import { groupCleanup } from './opening-server-teardown.mjs';

const SENTINEL = path.join(import.meta.dirname, 'opening-server-sentinel.mjs');

// Same bound as STOP_WAIT_MS in opening-server.mjs: the grace between the
// group's SIGTERM and its SIGKILL; never unbounded.
const GRACE_MS = 5000;
// Bounded wait for the sentinel's readiness byte; a sentinel that never
// reports fails startup instead of leaving the group without its reaper.
const READY_MS = 2000;
// Startup refusal: the worker sees this exit code when no command could
// be started under supervision.
const REFUSED = 4;

const {
  command,
  args = [],
  cwd,
  env,
  sentinel: sentinelArgv = [process.execPath, SENTINEL],
} = JSON.parse(process.argv[2]);

process.on('SIGTERM', () => {}); // the peg: survives the grace signal

const baseCleanup = groupCleanup(process.pid, GRACE_MS);
let tearingDown = false;
const cleanup = () => {
  tearingDown = true;
  baseCleanup();
};

// The orphan reaper joins this group before the command does. Its stdin's
// only write end is `sentinel.stdin` below, so this process's death by
// any path — including SIGKILL — delivers EOF there and hands teardown
// to a live member of the group. The module-scope binding keeps that
// write end open for this process's whole life.
const sentinel = spawn(
  sentinelArgv[0],
  [...sentinelArgv.slice(1), String(process.pid)],
  {
    // Keep the inherited completion pipe open in both cleanup owners;
    // the harness must observe both deaths, even when this owner dies first.
    stdio: ['pipe', 'pipe', 'ignore', 3],
  },
);

let started = false;
// A sentinel that fails to spawn or dies before or after reporting
// leaves the group without its orphan reaper. While no command has
// started the group holds only this process, so refusing startup leaves
// nothing behind; once members exist the failure runs owned cleanup.
const fail = () => {
  if (tearingDown) return;
  if (started) {
    cleanup();
    return;
  }
  // Refusal: the group holds only this process and the sentinel. The
  // sentinel is this process's own live child — killing it empties the
  // group, so no member outlives the refused startup.
  try {
    sentinel.kill('SIGKILL');
  } catch (error) {
    if (error.code !== 'ESRCH') throw error;
  }
  process.exit(REFUSED);
};
sentinel.on('error', fail);
sentinel.on('exit', fail);
sentinel.stdout.on('error', () => {});
sentinel.stdin.on('error', (error) => {
  if (error.code !== 'EPIPE' && error.code !== 'ERR_STREAM_DESTROYED') {
    throw error;
  }
});

// The command joins this process group (not detached); its output goes to
// this process's own pipes, which the worker reads. It starts only after
// the sentinel reports ready, inside READY_MS.
const startCommand = () => {
  if (started) return;
  started = true;
  spawn(command, args, {
    cwd,
    env,
    stdio: ['ignore', 'inherit', 'inherit'],
  }).on('error', () => {});
};
const readyDeadline = setTimeout(fail, READY_MS);
sentinel.stdout.once('data', () => {
  clearTimeout(readyDeadline);
  startCommand();
});

// The ownership pipe: a normal stop closes it; a worker death closes it.
process.stdin.on('data', cleanup);
process.stdin.on('end', cleanup);
process.stdin.resume();
setInterval(() => {}, 1e9); // the peg's loop: ends only by SIGKILL
