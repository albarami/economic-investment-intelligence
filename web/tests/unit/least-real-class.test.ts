/**
 * FE-42 (DAT-91): the registry recomputes the least-real class from the
 * fact's own input classes and refuses the value when `provenance` differs.
 * Public is more real than Synthetic, which is more real than Simulated;
 * a user's typed input takes no part in the ordering.
 */
import { describe, expect, it } from 'vitest';

import {
  createRegistry,
  leastRealClass,
  type InputClass,
  type Provenance,
  type SourceRow,
} from '../../src/facts/registry';
import {
  completeInput,
  factId,
  hashId,
  makeBinding,
  makeFact,
  makeLineage,
  makeSource,
} from '../fixtures/facts';

const RELEASE_CLASSES = ['public', 'synthetic', 'simulated'] as const;
const ORDER: Record<(typeof RELEASE_CLASSES)[number], number> = {
  public: 0,
  synthetic: 1,
  simulated: 2,
};

const SOURCE_FOR: Record<(typeof RELEASE_CLASSES)[number], SourceRow> = {
  public: makeSource({ sourceId: 'src_pub', kind: 'public_dataset' }),
  synthetic: makeSource({
    sourceId: 'src_syn',
    kind: 'synthetic_feed',
    inputClass: 'synthetic',
    sha256: hashId(1),
  }),
  simulated: makeSource({
    sourceId: 'src_sim',
    kind: 'simulation_output',
    inputClass: 'simulated',
    sha256: hashId(2),
  }),
};

/** Every non-empty set of release classes, with and without user input. */
function classSets(): InputClass[][] {
  const sets: InputClass[][] = [];
  for (let mask = 1; mask < 1 << RELEASE_CLASSES.length; mask += 1) {
    const chosen = RELEASE_CLASSES.filter((_, bit) => mask & (1 << bit));
    sets.push([...chosen]);
    sets.push([...chosen, 'user_input']);
  }
  return sets;
}

/** Test-side oracle written apart from the registry code. */
function expected(classes: readonly InputClass[]): Provenance {
  let worst: (typeof RELEASE_CLASSES)[number] = 'public';
  for (const item of classes) {
    if (item === 'user_input') continue;
    if (ORDER[item] > ORDER[worst]) worst = item;
  }
  return worst;
}

function inputFor(classes: InputClass[], provenance: Provenance) {
  const releaseClasses = classes.filter(
    (item): item is (typeof RELEASE_CLASSES)[number] => item !== 'user_input',
  );
  const sources = releaseClasses.map((item) => SOURCE_FOR[item]);
  return {
    ...completeInput(),
    facts: [
      makeBinding({
        fact: makeFact({ provenance, input_classes: classes }),
      }),
    ],
    lineages: [
      makeLineage({
        sourceIds: sources.map((row) => row.sourceId),
        inputClasses: classes,
      }),
    ],
    sources,
  };
}

describe('FE-42 least-real class recomputed against provenance', () => {
  it('readies a fact exactly when provenance is the least-real class', () => {
    let checked = 0;
    for (const classes of classSets()) {
      for (const provenance of RELEASE_CLASSES) {
        const registry = createRegistry(inputFor(classes, provenance));
        const resolution = registry.resolve(factId(0));
        if (provenance === expected(classes)) {
          expect(resolution.status, `${provenance} ${classes.join(',')}`).toBe(
            'ready',
          );
        } else {
          expect(resolution, `${provenance} ${classes.join(',')}`).toEqual({
            status: 'refused',
            missing: 'provenance_class',
          });
        }
        checked += 1;
      }
    }
    expect(checked).toBe(42);
  });

  it('refuses a planted mismatch: a synthetic input under a public mark', () => {
    const planted = inputFor(['public', 'synthetic'], 'public');
    expect(createRegistry(planted).resolve(factId(0))).toEqual({
      status: 'refused',
      missing: 'provenance_class',
    });
    const repaired = inputFor(['public', 'synthetic'], 'synthetic');
    expect(createRegistry(repaired).resolve(factId(0)).status).toBe('ready');
  });

  it('refuses a fact whose only input is the user, which has no class', () => {
    const input = {
      ...completeInput(),
      facts: [
        makeBinding({
          fact: makeFact({
            provenance: 'public',
            input_classes: ['user_input'],
          }),
        }),
      ],
      lineages: [makeLineage({ sourceIds: [], inputClasses: ['user_input'] })],
      sources: [],
    };
    expect(createRegistry(input).resolve(factId(0)).status).toBe('refused');
  });

  it('keeps a withheld fact withheld without a least-real comparison', () => {
    const input = inputFor(['public', 'synthetic'], 'suppressed');
    const resolution = createRegistry(input).resolve(factId(0));
    expect(resolution.status).toBe('ready');
    if (resolution.status === 'ready')
      expect(resolution.display).toBe('withheld');
  });

  it('computes the least-real class with user input taking no part', () => {
    expect(leastRealClass(['public'])).toBe('public');
    expect(leastRealClass(['simulated', 'public'])).toBe('simulated');
    expect(leastRealClass(['public', 'synthetic', 'user_input'])).toBe(
      'synthetic',
    );
    expect(leastRealClass(['user_input'])).toBeNull();
    expect(leastRealClass([])).toBeNull();
  });
});
