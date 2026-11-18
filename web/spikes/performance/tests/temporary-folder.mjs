import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';

// EOF survives SIGKILL: the cleanup process owns only this newly made folder.
// Existing finally blocks still remove it promptly on normal completion.
export function temporaryFolder(prefix) {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  const cleanup = spawn(
    process.execPath,
    [
      '-e',
      "process.stdin.resume(); process.stdin.on('end', () => require('node:fs').rmSync(process.argv[1], {recursive:true, force:true}));",
      folder,
    ],
    { detached: true, stdio: ['pipe', 'ignore', 'inherit'] },
  );
  cleanup.on('error', (error) => {
    fs.rmSync(folder, { recursive: true, force: true });
    throw error;
  });
  cleanup.unref();
  cleanup.stdin.unref();
  return folder;
}
