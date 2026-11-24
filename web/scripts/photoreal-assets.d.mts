export function transformDependency(
  code: string,
  id: string,
  webRoot?: string,
  matched?: Set<string>,
): string | null;
export function verifyAssets(read: (relative: string) => Uint8Array): void;
export function assertQualifiedImport(
  code: string,
  id: string,
  webRoot?: string,
): void;
export function browserModules(bundle: unknown): string[];
export function verifyReplacements(matched: Set<string>): void;
