export function foreignRequest(url: string, origin: string): string;
export function foreignBeforeCommit(url: string, pageUrl: string): string;
export function refuseForeignAfterReady(
  seen: readonly string[],
  origin: string,
): void;
