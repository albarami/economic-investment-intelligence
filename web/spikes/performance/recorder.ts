export type Recorder = {
  timestamps: number[];
  visibilityLost: boolean;
  resized: boolean;
  contextLost: boolean;
  stop: () => void;
};

export function recordOrbit(input: {
  durationMs: number;
  onFrame: (elapsed: number) => void;
  onDone: (timestamps: number[]) => void;
}): Recorder {
  const timestamps: number[] = [];
  const recorder: Recorder = {
    timestamps,
    visibilityLost: false,
    resized: false,
    contextLost: false,
    stop: () => {
      stopped = true;
    },
  };
  let stopped = false;
  let start = 0;
  const tick = (now: number) => {
    if (stopped) return;
    if (start === 0) start = now;
    timestamps.push(now);
    const elapsed = now - start;
    input.onFrame(elapsed);
    if (elapsed >= input.durationMs) {
      input.onDone(timestamps);
      return;
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  return recorder;
}
