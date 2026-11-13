declare module '*.css';

declare module '*.woff2?url' {
  const url: string;
  export default url;
}

declare module 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url' {
  const url: string;
  export default url;
}

declare module 'node:url' {
  export function fileURLToPath(url: URL | string): string;
}

declare module 'node:fs' {
  export function existsSync(path: URL | string): boolean;
}

declare module '../guards.mjs' {
  export const FIRST_LABEL_ID: string;
  export const LICENCE_PATHS: string[];
  export const REMOTE_FONT: string;
  export function arabicNames(): string[];
  export function loadNames(): {
    places: { id: string; nameEn: string; nameAr: string; review: string }[];
  };
  export function judgeCsp(header: string | null): {
    ok: boolean;
    detail: string;
  };
  export function judgeDigits(text: string): { ok: boolean; detail: string };
  export function judgeDirection(
    direction: string,
    bearing: number,
    mirrored: boolean,
  ): { ok: boolean; detail: string };
  export function judgeFonts(
    families: string[],
    omittedArabic: boolean,
  ): { ok: boolean; detail: string };
  export function judgeLetterSpacing(value: string): {
    ok: boolean;
    detail: string;
  };
  export function judgeLicences(texts: string[]): {
    ok: boolean;
    detail: string;
  };
  export function judgeRequests(
    urls: string[],
    origin: string,
  ): { ok: boolean; detail: string };
}

interface SpikeDiagnostics {
  ready: boolean;
  failure: string;
  labelNames: string[];
  fontFaceFamilies?: string[];
  fontFacesReady?: boolean;
  interleaved?: boolean;
  overlayCount?: number;
  webgpu?: boolean;
  firstLabelId?: string;
  beforeId?: string | null;
  layerIds?: string[];
  featureKey?: string;
  bearing?: number;
  letterSpacing?: string;
  direction?: string;
  mirrored?: boolean;
  latinFamily?: string;
  arabicFamily?: string;
}

interface Window {
  __spike?: SpikeDiagnostics;
}
