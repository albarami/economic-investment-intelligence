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

export function summariseFrames(timestamps: number[]): FrameSummary;
