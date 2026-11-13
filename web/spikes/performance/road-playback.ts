import { HOUR_HOLD_MS, SCENE_MS } from './config.mjs';
import data from './road-data.json' with { type: 'json' };
import { playbackState, type PlaybackState } from './roads.mjs';

export type Playback = {
  state: PlaybackState;
  hoursShown: number[];
  paused: boolean;
  reduced: boolean;
  interrupted: boolean;
  elapsed: number;
  toggle: () => void;
  tick: (now: number) => void;
};
export function createPlayback(reduced: boolean): Playback {
  let previous: number | null = null;
  const playback: Playback = {
    state: playbackState(data.hours, 0),
    hoursShown: [data.hours[0]!],
    paused: false,
    reduced,
    interrupted: reduced,
    elapsed: 0,
    toggle() {
      playback.paused = !playback.paused;
      playback.interrupted = true;
      previous = null;
    },
    tick(now) {
      if (previous !== null && !playback.paused && !playback.reduced) {
        const elapsed = playback.elapsed + now - previous;
        // The hour selection stops at the last stored hour. Particle motion
        // keeps its clock, so Pause motion can still stop and resume it.
        playback.elapsed = playback.state.ended
          ? elapsed
          : Math.min(
              elapsed,
              (playback.state.index + 1) * (HOUR_HOLD_MS + SCENE_MS),
            );
      }
      previous = now;
      const state = playbackState(data.hours, playback.elapsed);
      // Retain every displayed stored state; do not fill gaps with invented visits.
      for (const index of [state.index, state.next]) {
        const hour = data.hours[index]!;
        if (playback.hoursShown.at(-1)! < hour) playback.hoursShown.push(hour);
      }
      playback.state = state;
    },
  };
  return playback;
}
