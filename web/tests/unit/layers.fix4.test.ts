import { describe, expect, it } from 'vitest';

import { basePayload, category, plain } from '../fixtures/layers';
import { acceptPayload } from '../../src/stage/layers/refuse';
import type { LayerPayload, TextSegment } from '../../src/stage/layers/payload';

function withNameSegment(text: string): LayerPayload {
  const payload = basePayload();
  payload.layers[0]!.features[0]!.name_segments = [plain(text)];
  return payload;
}

function sourceCategory(text: string): LayerPayload {
  return basePayload({
    sources: [
      {
        ...basePayload().sources[0]!,
        categories: [[plain(text)]],
      },
    ],
  });
}

function referenceSegment(
  referenceKind: 'published_text' | 'calendar_year',
  value: string,
  recordId: string,
): TextSegment {
  return { kind: 'reference', referenceKind, value, recordId };
}

function splitPayload(
  sourceCategories: readonly (readonly TextSegment[])[],
  chipCategories: readonly (readonly TextSegment[])[],
): LayerPayload {
  return basePayload({
    sources: [
      {
        ...basePayload().sources[0]!,
        year: '2024',
        categories: sourceCategories,
        geographyCode: 'sample_geo',
      },
    ],
    split_chip: {
      provenance: 'public',
      evidence_status: 'observed',
      source_id: 'src_places',
      year: '2024',
      categories: chipCategories,
      geography_code: 'sample_geo',
      source_geography: 'sample_geo',
    },
  });
}

const REFERENCE = {
  kind: 'reference' as const,
  referenceKind: 'published_text' as const,
  value: 'group_b',
  recordId: 'cat_b',
};

describe('fix pass 4', () => {
  it('F1 refuses a plain name segment that holds a Western digit', () => {
    const result = acceptPayload(withNameSegment('Sample 7'));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe('numeral_in_plain_segment');
  });

  it('F1 refuses a plain name segment that holds an Arabic-Indic digit', () => {
    const result = acceptPayload(withNameSegment('Sample \u0663'));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe('numeral_in_plain_segment');
  });

  it('F2 refuses a Western digit in a source category', () => {
    const result = acceptPayload(sourceCategory('group 7'));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe('numeral_in_plain_segment');
  });

  it('F2 refuses an Arabic-Indic digit in a source category', () => {
    const result = acceptPayload(sourceCategory('group \u0663'));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe('numeral_in_plain_segment');
  });

  it('F2 refuses a split category whose reference kind differs', () => {
    const source = [[REFERENCE]];
    const chip = [
      [referenceSegment('calendar_year', REFERENCE.value, REFERENCE.recordId)],
    ];
    const result = acceptPayload(splitPayload(source, chip));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe('split_incomplete');
  });

  it('F2 refuses a split category whose reference value differs', () => {
    const source = [[REFERENCE]];
    const chip = [
      [
        referenceSegment(
          REFERENCE.referenceKind,
          'group_c',
          REFERENCE.recordId,
        ),
      ],
    ];
    const result = acceptPayload(splitPayload(source, chip));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe('split_incomplete');
  });

  it('F2 refuses a split category whose reference record id differs', () => {
    const source = [[REFERENCE]];
    const chip = [
      [referenceSegment(REFERENCE.referenceKind, REFERENCE.value, 'cat_other')],
    ];
    const result = acceptPayload(splitPayload(source, chip));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe('split_incomplete');
  });

  it('F2 refuses a split category whose segment kind differs', () => {
    const result = acceptPayload(
      splitPayload([category('group_b')], [[REFERENCE]]),
    );
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe('split_incomplete');
  });
});
