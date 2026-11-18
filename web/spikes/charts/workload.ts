import profiles from './fixtures/profiles.json';
import { validateInput } from './guards.mjs';
export type Point = number[];
export type Panel = { lower: Point[]; upper: Point[] | null };
export function workload(input: unknown): Panel[] {
  return validateInput(
    input,
    (key: {
      fixture: 'hourly' | 'comparison' | 'range';
      selection: string;
    }) => {
      const selected =
        key.selection === 'first' ? profiles.hourly : profiles.comparison;
      if (key.fixture === 'comparison')
        return [profiles.hourly, profiles.comparison].map((lower) => ({
          lower,
          upper: null,
        }));
      if (key.fixture === 'range')
        return [
          {
            lower: profiles.range.map(([x, lo]) => [x ?? 0, lo ?? 0]),
            upper: profiles.range.map(([x, , hi]) => [x ?? 0, hi ?? 0]),
          },
        ];
      return [{ lower: selected, upper: null }];
    },
  );
}
