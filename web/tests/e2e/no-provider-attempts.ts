import { existsSync } from 'node:fs';
import path from 'node:path';

/** A caught sentinel exception still invalidates the worker's entire run. */
export function assertNoProviderAttempts(work: string): void {
  if (existsSync(path.join(work, 'egress-attempts.txt')))
    throw new Error('server_provider_attempt');
}
