import fs from 'node:fs';
import path from 'node:path';

function verifiedCopy(from, to) {
  fs.copyFileSync(from, to);
  if (!fs.readFileSync(from).equals(fs.readFileSync(to))) {
    throw new Error('copy verification failed');
  }
}

// Baselines are files. Keep verified backups until every original is restored.
export function withHeldFiles(source, held, action) {
  const copied = [];
  try {
    for (const name of fs.readdirSync(source)) {
      const from = path.join(source, name);
      const to = path.join(held, name);
      verifiedCopy(from, to);
      copied.push([from, to]);
    }
    for (const [from] of copied) fs.unlinkSync(from);
    return action();
  } finally {
    for (const [from, to] of copied) verifiedCopy(to, from);
    fs.rmSync(held, { recursive: true, force: true });
  }
}
