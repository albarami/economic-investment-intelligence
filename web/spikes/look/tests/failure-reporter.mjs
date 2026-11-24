// Preserve failed browser case names in the enclosing Node assertion.
export const FAILURE_PREFIX = 'EII_LOOK_FAILURE:';

export function browserFailures(output) {
  return output
    .split('\n')
    .filter((line) => line.startsWith(FAILURE_PREFIX))
    .map((line) => line.slice(FAILURE_PREFIX.length).trim());
}

export default class FailureReporter {
  constructor(write) {
    this.write =
      typeof write === 'function'
        ? write
        : (line) => process.stdout.write(line);
  }

  onTestEnd(test, result) {
    if (!['failed', 'timedOut', 'interrupted'].includes(result.status)) return;
    this.write(
      `${FAILURE_PREFIX}${test.titlePath().filter(Boolean).join(' › ')}\n`,
    );
  }
}
