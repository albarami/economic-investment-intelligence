export function requestLocal(
  path: string,
  options: RequestInit,
  fetchImpl?: typeof fetch,
): Promise<Response>;
export function assertRelative(path: string, text: string): void;
export interface AddressSearchHit {
  label: string;
  point: { longitude: number; latitude: number };
}
export type AddressSearchOutcome =
  | { state: 'gazetteer_only'; results?: never }
  | { results: readonly AddressSearchHit[]; state?: never };
export function readSearchResults(
  payload: unknown,
): readonly AddressSearchHit[];
export function postAddressSearch(
  text: string,
  lang: string,
  fetchImpl?: typeof fetch,
): Promise<AddressSearchOutcome>;
