import { describe, expect, it } from 'vitest';

import { createRegistry } from '../../src/facts/registry';
import {
  completeInput,
  factId,
  makeBinding,
  makeFact,
} from '../fixtures/facts';

describe('direction referencers', () => {
  it('returns the parent fact ids that name an id as directionId, in registry order', () => {
    const direction = factId(3);
    const registry = createRegistry({
      ...completeInput(),
      facts: [
        makeBinding({
          fact: makeFact({ value: -6 }),
          presentation: 'change',
          directionId: direction,
        }),
        makeBinding({
          fact: makeFact({ fact_id: factId(1), value: 12 }),
          rangeLowId: direction,
        }),
        makeBinding({
          fact: makeFact({ fact_id: factId(2), value: 4 }),
          presentation: 'change',
          directionId: direction,
        }),
        makeBinding({
          fact: makeFact({
            fact_id: direction,
            value: 'higher',
            unit: 'direction',
          }),
        }),
      ],
    });
    expect(registry.directionReferencers(direction)).toEqual([
      factId(0),
      factId(2),
    ]);
    expect(registry.directionReferencers(factId(0))).toEqual([]);
  });
});
