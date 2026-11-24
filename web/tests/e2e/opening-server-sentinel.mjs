/**
 * The orphan reaper inside one opening-server process group.
 *
 * Spawned by the supervisor (opening-server-supervisor.mjs) into its own
 * process group, before the command, so this process is a live member of
 * the group for as long as it runs. Its stdin's only write end is the
 * supervisor's: the supervisor's death by any path, including SIGKILL,
 * delivers EOF here, and this process then runs the teardown the dead
 * supervisor could not — group SIGTERM, one bounded grace, group SIGKILL,
 * which takes this process with it.
 *
 * Signalling -pgid from inside a live member can never reach a recycled
 * id: a process group exists for as long as one member does, and this
 * process is that member. The id here is never a remembered value from
 * outside the group; the supervisor passes its own pid, which is this
 * process's own group id for as long as this process lives.
 *
 * Once the watch is armed it reports one readiness byte on stdout: the
 * supervisor starts the command only after this process can already reap.
 */
import { groupCleanup } from './opening-server-teardown.mjs';

// Same bound as GRACE_MS in opening-server-supervisor.mjs: the grace
// between the group's SIGTERM and its SIGKILL; never unbounded.
const GRACE_MS = 5000;
// This process's own group id: the supervisor's pid, passed at spawn.
const PGID = Number(process.argv[2]);
if (!Number.isInteger(PGID) || PGID <= 0) process.exit(1);

process.on('SIGTERM', () => {}); // survive this group's grace signal

const cleanup = groupCleanup(PGID, GRACE_MS);

// The supervisor's write end: its death by any path delivers EOF here.
process.stdin.on('data', cleanup);
process.stdin.on('end', cleanup);
process.stdin.resume();
// Readiness: the watch above is armed before this byte is written.
process.stdout.write('R\n');
setInterval(() => {}, 1e9); // stay a live member until killed
