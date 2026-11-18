import fs from 'node:fs';
import { createHash } from 'node:crypto';
import { checkMatrix } from './evidence.mjs';
const hash = (file) =>
  createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const matrixPath = 'spikes/charts/evidence/native-matrix.json';
if (!fs.existsSync(matrixPath)) {
  console.error('BLOCKED: missing native capture matrix');
  process.exitCode = 1;
} else {
  try {
    const bundle = JSON.parse(
      fs.readFileSync('spikes/charts/evidence/bundle.json', 'utf8'),
    );
    const identity = {
      contract: hash('spikes/charts/contract.json'),
      fixture: hash('spikes/charts/fixtures/profiles.json'),
      build: createHash('sha256')
        .update(JSON.stringify(bundle.sources))
        .digest('hex'),
      lock: hash('package-lock.json'),
    };
    const result = checkMatrix(
      JSON.parse(fs.readFileSync(matrixPath, 'utf8')),
      identity,
    );
    if (!result.ok) {
      console.error(`FAIL: ${result.failure}`);
      process.exitCode = 1;
    } else {
      // The proposed instrumentation and unavailable shared Fact chips still
      // prevent native qualification, even if structural matrix checks pass.
      console.error(
        'BLOCKED: native instrumentation and shared Fact-chip acceptance pending',
      );
      process.exitCode = 1;
    }
  } catch {
    console.error('FAIL: malformed evidence');
    process.exitCode = 1;
  }
}
