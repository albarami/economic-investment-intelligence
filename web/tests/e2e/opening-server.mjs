/**
 * Start and stop the public opening server as one owned process group.
 *
 * `startServerGroup` spawns a detached supervisor (see
 * opening-server-supervisor.mjs) that leads a new process group, runs the
 * command inside it and stays alive as the peg, so the group id cannot be
 * freed for reuse while the group is owned. The supervisor's stdin is the
 * ownership pipe: a normal stop closes it, and the kernel closes it on the
 * worker's death by any path including SIGKILL. Either way the supervisor,
 * not the worker, kills the group — SIGTERM, one bounded grace, SIGKILL —
 * and dies with it. A sentinel inside the group holds the supervisor's
 * other pipe end and runs the same teardown if the supervisor dies first.
 *
 * The worker never probes or signals a numeric group id. The only signal
 * it owns is `proc.kill` on its live, unreaped child: a child pid cannot
 * be recycled while it is still ours, and killing the supervisor hands
 * the group's teardown to the sentinel. Every group signal is sent by a
 * live member of that group — the supervisor or the sentinel — for which
 * the id is pinned by its own membership, never a remembered value.
 */
import { spawn } from 'node:child_process';
import path from 'node:path';

const SUPERVISOR = path.join(
  import.meta.dirname,
  'opening-server-supervisor.mjs',
);

// One bounded grace step between SIGTERM and SIGKILL; never unbounded.
const STOP_WAIT_MS = 5000;
// The supervisor's own teardown is SIGTERM + one grace + SIGKILL; the
// worker waits two graces plus slack before it kills the supervisor and
// hands teardown to the sentinel.
const SUPERVISOR_BOUND_MS = 2 * STOP_WAIT_MS + 1000;

// Procs whose supervision is done; a repeated stop does nothing.
const retired = new Set();

// Pipe failures expected while a dying supervisor's read end closes the
// stream down. Any other code is a real stream failure and must surface,
// never be swallowed.
const SHUTDOWN_CODES = new Set(['EPIPE', 'ERR_STREAM_DESTROYED']);
function shutdownPipeError(error) {
  if (!SHUTDOWN_CODES.has(error.code)) throw error;
}

function waitForExit(proc, ms) {
  return new Promise((resolve) => {
    if (proc.exitCode !== null || proc.signalCode !== null) {
      resolve();
      return;
    }
    const done = () => {
      clearTimeout(timer);
      proc.removeListener('exit', done);
      proc.removeListener('error', done);
      resolve();
    };
    const timer = setTimeout(done, ms);
    proc.once('exit', done);
    proc.once('error', done);
  });
}

/**
 * Spawn `command` inside a new process group owned by a detached
 * supervisor. `options` may carry `cwd` and `env`; `options.register`, if
 * given, is called synchronously with the spawned proc before return, so
 * an owner can register the group id (proc.pid === pgid) at creation —
 * before an asynchronous report, an assertion or a helper return can
 * lose it. `options.sentinel`, if given, replaces the sentinel spawn
 * argv (the supervisor appends its own pid) so a test can inject a
 * sentinel that cannot report ready. Stdio is fixed: the command's
 * stdout and stderr are forwarded to `proc.stdout`/`proc.stderr`. The
 * returned proc is the supervisor.
 */
export function startServerGroup(command, args, options) {
  const cfg = { command, args: args ?? [] };
  if (options?.cwd !== undefined) cfg.cwd = options.cwd;
  if (options?.env !== undefined) cfg.env = options.env;
  if (options?.sentinel !== undefined) cfg.sentinel = options.sentinel;
  const proc = spawn(process.execPath, [SUPERVISOR, JSON.stringify(cfg)], {
    detached: true,
    stdio: ['pipe', 'pipe', 'pipe', 'pipe'],
  });
  // The group never holds the worker's event loop open; the ownership pipe
  // is the only owner of its teardown. A dead supervisor leaves a dead
  // read end: shutdown-class stream errors are swallowed, nothing else.
  proc.unref();
  proc.stdin.unref();
  proc.stdout.unref();
  proc.stderr.unref();
  // Completion witness: supervisor and sentinel both inherit this pipe.
  // EOF is possible only after both have closed their copies on exit.
  proc.stdio[3].unref();
  proc.stdio[3].resume();
  proc.stdin.on('error', shutdownPipeError);
  options?.register?.(proc);
  return proc;
}

/**
 * Close the ownership pipe and let the supervisor kill the group, bounded.
 * If the supervisor is still running past its own bound it is killed
 * directly — our own live child, whose pid cannot have been recycled —
 * and the sentinel inside the group runs the teardown. If the supervisor
 * already died, the sentinel already owns the orphans: nothing here ever
 * probes or signals a remembered group id. Always settles inside the two
 * bounds.
 */
export async function stopServerGroup(proc) {
  if (retired.has(proc)) return;
  try {
    try {
      proc.stdin.end();
    } catch {
      /* supervisor already gone */
    }
    await waitForExit(proc, SUPERVISOR_BOUND_MS);
    if (proc.exitCode === null && proc.signalCode === null) {
      proc.kill('SIGKILL');
      await waitForExit(proc, STOP_WAIT_MS);
    }
  } finally {
    retired.add(proc);
  }
}
