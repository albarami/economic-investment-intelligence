export type FrameSummary =
  | {
      ok: true;
      frameCount: number;
      durationMs: number;
      intervals: number[];
      percentiles: { p50: number; p95: number; p99: number };
      shareUnderBudget: number;
    }
  | { ok: false; failure: string };

export function readUnmaskedRenderer(context: unknown): string;

export function judgeRenderer(renderer: string): string;

export const EMPTY_CANVAS_MAX_MEDIAN_MS: number;

export type EmptyCanvasVerdict = {
  ok: boolean;
  failure: string;
  framesPerSecond: number;
};

export function judgeEmptyCanvas(timestamps: number[]): EmptyCanvasVerdict;

export function summariseFrames(timestamps: number[]): FrameSummary;
