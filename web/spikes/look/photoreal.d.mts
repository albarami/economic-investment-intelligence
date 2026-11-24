export const PER_VIEW_BUDGET: number;
export const SCREEN_SPACE_ERROR: number;

export function aggregateCopyrights(lines: string[]): string[];
export function copyrightFromTile(tile: object): string[];

export function holdView(tileset: {
  options: { loadTiles?: boolean; maximumScreenSpaceError?: number };
}): void;

export function budgetedTileFetch(options: {
  transport: (url: string, init?: RequestInit) => Promise<Response>;
  used: () => number | Promise<number>;
  budget?: number;
  onHold?: () => void;
}): (url: string, init?: RequestInit) => Promise<Response>;
