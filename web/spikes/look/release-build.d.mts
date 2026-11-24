import type { Release, SourceInput } from './release-shape.mjs';

export function assemble(
  cells: Release['layer']['cells'],
  basemap: Release['basemap'],
  extra?: Partial<
    Pick<
      Release,
      | 'period'
      | 'buildings'
      | 'district'
      | 'places'
      | 'district_labels'
      | 'establishments'
    >
  > & {
    types?: Map<string, number>;
    input?: SourceInput | SourceInput[];
  },
): Release;
