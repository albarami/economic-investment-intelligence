import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { expect, it } from 'vitest';
import { assertNoProviderAttempts } from '../e2e/no-provider-attempts';

it('the worker refuses a recorded provider attempt even after its exception was caught', () => {
  const tmp = path.resolve('../.overnight/tmp');
  mkdirSync(tmp, { recursive: true });
  const work = mkdtempSync(path.join(tmp, 'opening-sentinel-'));
  try {
    expect(() => assertNoProviderAttempts(work)).not.toThrow();
    writeFileSync(path.join(work, 'egress-attempts.txt'), 'provider_attempt\n');
    expect(() => assertNoProviderAttempts(work)).toThrow(
      'server_provider_attempt',
    );
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
});
