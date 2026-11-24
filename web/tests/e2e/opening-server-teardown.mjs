/**
 * Shared member-pinned group teardown for the opening-server lifecycle
 * actors (supervisor, sentinel, scope peg).
 *
 * `signalGroup` signals the group `pgid` by number; it is safe only while
 * the caller is a live member of that group, because the caller's own
 * membership pins the id against reuse. `pgid` 0 means the caller's own
 * process group (POSIX kill(0)), which needs no remembered value at all.
 * ESRCH is the only tolerated error: an empty group is already done.
 *
 * `groupCleanup` returns an idempotent teardown: SIGTERM, one bounded
 * grace, then SIGKILL — which takes the caller with the group, so nothing
 * of the group outlives the actor that owns its cleanup.
 */
export function signalGroup(pgid, signal) {
  try {
    process.kill(-pgid, signal);
  } catch (error) {
    if (error.code !== 'ESRCH') throw error;
  }
}

export function groupCleanup(pgid, graceMs) {
  let cleaning = false;
  return function cleanup() {
    if (cleaning) return;
    cleaning = true;
    signalGroup(pgid, 'SIGTERM');
    // One bounded grace, then SIGKILL the whole group, this process included.
    setTimeout(() => signalGroup(pgid, 'SIGKILL'), graceMs);
  };
}
