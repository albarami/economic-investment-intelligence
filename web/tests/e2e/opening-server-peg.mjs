/**
 * The scope peg of one opening-server process group: a live member of the
 * group owned by the test harness through ONE identity-bound connection.
 *
 * Spawned by a member of the group, so this process joins that group and
 * stays a live member until the group's teardown takes it. The harness
 * attaches while this process is alive: it connects to the socket,
 * presents the scope token it issued at spawn, and keeps that one
 * connection for the group's whole life — it never reconnects through
 * the reusable pathname. A verified connection is answered 'K' and
 * announced 'H' on this process's stdout, so the leader can start
 * descendants only after the scope is held.
 *
 * Release is the end of that held connection: on 'end' this process
 * writes 'B' — teardown intent — flushes and closes the connection,
 * then runs kill(0), member-pinned by its own membership, taking itself
 * with the group. A connection that never verifies, presents a wrong
 * token, or arrives while another is held is destroyed without effect:
 * only the held connection can release the group. If this process dies
 * on its own, the held connection closes before release and the harness
 * reports failed cleanup. An independent owner must verify completion;
 * neither 'B' nor a closed channel proves it.
 */
import net from 'node:net';
import { pathToFileURL } from 'node:url';
import { signalGroup } from './opening-server-teardown.mjs';

// Injection is test-only: exercise transport failure and repeated callbacks
// without signalling the test runner's group.
export function createScopePeg(
  token,
  signal = signalGroup,
  stdout = process.stdout,
) {
  let cleaning = false;
  function teardown() {
    if (cleaning) return;
    cleaning = true;
    signal(0, 'SIGKILL');
  }

  const TOKEN_MS = 2000;
  let held = null;
  return net.createServer((conn) => {
    conn.on('error', () => {});
    if (held !== null) {
      conn.destroy();
      return;
    }
    conn.setEncoding('utf8');
    let line = '';
    const tokenTimer = setTimeout(() => conn.destroy(), TOKEN_MS);
    conn.on('data', (chunk) => {
      if (held !== null) return;
      line += chunk;
      if (!line.includes('\n')) return;
      clearTimeout(tokenTimer);
      if (line.trim() !== token) {
        conn.destroy();
        return;
      }
      held = conn;
      conn.write('K\n');
      try {
        stdout.write('H\n');
      } catch {
        /* no reader still means the scope is held */
      }
      conn.on('end', () => {
        // Intent only. Completion must be checked by an independent owner.
        conn.write('B\n', () => conn.end(teardown));
      });
      conn.on('close', teardown);
    });
  });
}

if (
  process.argv[1] &&
  pathToFileURL(process.argv[1]).href === import.meta.url
) {
  const [sockPath, token, socketCwd] = process.argv.slice(2);
  if (sockPath === undefined || token === undefined) process.exit(1);
  if (socketCwd !== undefined) process.chdir(socketCwd);
  process.on('SIGTERM', () => {});
  process.stdout.on('error', () => {});
  const server = createScopePeg(token);
  server.on('error', () => process.exit(1));
  server.listen(sockPath);
  setInterval(() => {}, 1e9);
}
