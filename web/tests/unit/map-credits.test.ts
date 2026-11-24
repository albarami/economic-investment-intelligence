/** S3-T16 box 15: building-height credits and the GIS centre's source line (PUB-110). */
import { describe, expect, it } from 'vitest';

import {
  calendarAccepted,
  gisSourceLine,
  heightCredits,
  type HeightCreditInputs,
  type HeightSource,
} from '../../src/stage/map-credits';
import type { TextSegment } from '../../src/stage/layers/payload';

const DATE = '2026-11-15';
/** An invented host: no lookup ever leaves the machine. */
const LANDING = 'https://wsf3d-landing.invalid/';

function inputs(): HeightCreditInputs {
  return {
    bldg_3dglobfp: { retrievalDate: DATE, recordId: 'SYN-rec-globfp' },
    bldg_wsf3d: {
      retrievalDate: DATE,
      recordId: 'SYN-rec-wsf3d',
      productionYear: '2023',
      landingPage: LANDING,
    },
  };
}

function joined(segments: readonly TextSegment[]): string {
  return segments
    .map((segment) => (segment.kind === 'plain' ? segment.text : segment.value))
    .join('');
}

/** Document 04, attribution table rows `bldg_3dglobfp` and `bldg_wsf3d`, with {date} filled. */
const GLOBFP_EN =
  'Building heights: 3D-GloBFP, Che et al. 2024, CC BY 4.0, retrieved 2026-11-15. Heights are estimates.';
const WSF_EN =
  'Building heights: WSF 3D, German Aerospace Center (DLR), CC BY 4.0, retrieved 2026-11-15. Heights are estimates. Copyright DLR 2023';

const PLAIN_DIGIT = /\p{Nd}/u;

describe('height credits', () => {
  it('shows no credit when only recorded or floor-count heights are drawn', () => {
    expect(heightCredits('en', ['recorded', 'floor_count'], {})).toEqual({
      kind: 'credits',
      lines: [],
    });
  });

  it('renders the GloBFP and WSF 3D wording verbatim from document 04', () => {
    const result = heightCredits(
      'en',
      ['bldg_wsf3d', 'recorded', 'bldg_3dglobfp', 'bldg_3dglobfp'],
      inputs(),
    );
    expect(result.kind).toBe('credits');
    if (result.kind !== 'credits') return;
    expect(result.lines.map((line) => line.sourceId)).toEqual([
      'bldg_3dglobfp',
      'bldg_wsf3d',
    ]);
    expect(joined(result.lines[0].segments)).toBe(GLOBFP_EN);
    expect(joined(result.lines[1].segments)).toBe(WSF_EN);
    expect(joined(result.lines[0].segments)).toContain('Che et al. 2024');
    expect(result.lines[0].link).toBeUndefined();
    expect(result.lines[1].link).toBe(LANDING);
  });

  it('keeps every numeral in a chip segment, in en and ar', () => {
    for (const language of ['en', 'ar'] as const) {
      const result = heightCredits(
        language,
        ['bldg_3dglobfp', 'bldg_wsf3d'],
        inputs(),
      );
      if (result.kind !== 'credits') throw new Error('refused');
      for (const line of result.lines) {
        for (const segment of line.segments) {
          if (segment.kind === 'plain') {
            expect(segment.text).not.toMatch(PLAIN_DIGIT);
          }
        }
      }
    }
  });

  it('refuses a drawn GloBFP height without its credit input', () => {
    const { bldg_wsf3d } = inputs();
    expect(heightCredits('en', ['bldg_3dglobfp'], { bldg_wsf3d })).toEqual({
      kind: 'refused',
      reason: 'globfp_credit_absent',
    });
  });

  it('refuses a drawn WSF 3D height without its credit input', () => {
    const { bldg_3dglobfp } = inputs();
    expect(heightCredits('en', ['bldg_wsf3d'], { bldg_3dglobfp })).toEqual({
      kind: 'refused',
      reason: 'wsf3d_credit_absent',
    });
  });

  it('refuses a malformed retrieval date', () => {
    const changed = inputs();
    changed.bldg_3dglobfp = {
      ...changed.bldg_3dglobfp!,
      retrievalDate: '15/11',
    };
    expect(heightCredits('en', ['bldg_3dglobfp'], changed)).toEqual({
      kind: 'refused',
      reason: 'height_retrieval_date_invalid',
    });
  });

  it('refuses a WSF 3D credit without its year of production', () => {
    const changed = inputs();
    changed.bldg_wsf3d = { ...changed.bldg_wsf3d!, productionYear: 'soon' };
    expect(heightCredits('en', ['bldg_wsf3d'], changed)).toEqual({
      kind: 'refused',
      reason: 'wsf3d_production_year_invalid',
    });
  });

  it('refuses an impossible retrieval date that the pattern alone accepts', () => {
    const changed = inputs();
    changed.bldg_3dglobfp = {
      ...changed.bldg_3dglobfp!,
      retrievalDate: '2026-02-30',
    };
    expect(heightCredits('en', ['bldg_3dglobfp'], changed)).toEqual({
      kind: 'refused',
      reason: 'height_retrieval_date_invalid',
    });
  });

  it('accepts a valid leap-day retrieval date', () => {
    const changed = inputs();
    changed.bldg_3dglobfp = {
      ...changed.bldg_3dglobfp!,
      retrievalDate: '2024-02-29',
    };
    expect(heightCredits('en', ['bldg_3dglobfp'], changed).kind).toBe(
      'credits',
    );
  });

  it('refuses the year of production 0000', () => {
    const changed = inputs();
    changed.bldg_wsf3d = { ...changed.bldg_wsf3d!, productionYear: '0000' };
    expect(heightCredits('en', ['bldg_wsf3d'], changed)).toEqual({
      kind: 'refused',
      reason: 'wsf3d_production_year_invalid',
    });
  });

  it.each([
    ['absent', undefined],
    ['plain http', 'http://wsf3d-landing.invalid/'],
    ['script scheme', 'javascript:void(0)'],
    ['not a URL', 'landing page'],
  ])('refuses a WSF 3D credit with a %s landing page', (_name, landingPage) => {
    const changed = inputs();
    changed.bldg_wsf3d = { ...changed.bldg_wsf3d!, landingPage };
    expect(heightCredits('en', ['bldg_wsf3d'], changed)).toEqual({
      kind: 'refused',
      reason: 'wsf3d_landing_page_invalid',
    });
  });
});

function gisInput() {
  return {
    attribution: [
      { kind: 'plain', text: 'Source: SYN publisher, SYN imagery service.' },
    ] as TextSegment[],
    retrievalDate: DATE,
    recordId: 'SYN-rec-gis',
  };
}

describe('GIS centre source line', () => {
  it('renders the recorded attribution and its retrieval-date chip', () => {
    const result = gisSourceLine(gisInput());
    expect(result).toEqual({
      kind: 'line',
      segments: [
        ...gisInput().attribution,
        {
          kind: 'reference',
          referenceKind: 'calendar_date',
          value: DATE,
          recordId: 'SYN-rec-gis',
        },
      ],
    });
  });

  it('refuses a blank attribution', () => {
    expect(
      gisSourceLine({
        ...gisInput(),
        attribution: [{ kind: 'plain', text: ' ' }],
      }),
    ).toEqual({ kind: 'refused', reason: 'gis_source_line_absent' });
  });

  it('refuses a malformed retrieval date', () => {
    expect(
      gisSourceLine({ ...gisInput(), retrievalDate: 'yesterday' }),
    ).toEqual({ kind: 'refused', reason: 'gis_retrieval_date_invalid' });
  });

  it('refuses a numeral in a plain segment', () => {
    expect(
      gisSourceLine({
        ...gisInput(),
        attribution: [{ kind: 'plain', text: 'Source: SYN service 7' }],
      }),
    ).toEqual({ kind: 'refused', reason: 'gis_numeral_outside_chip' });
  });

  it('refuses an impossible retrieval date that the pattern alone accepts', () => {
    expect(
      gisSourceLine({ ...gisInput(), retrievalDate: '2026-02-30' }),
    ).toEqual({ kind: 'refused', reason: 'gis_retrieval_date_invalid' });
  });

  it('accepts a valid leap-day retrieval date', () => {
    expect(
      gisSourceLine({ ...gisInput(), retrievalDate: '2024-02-29' }).kind,
    ).toBe('line');
  });

  const reference = (value: string): TextSegment => ({
    kind: 'reference',
    referenceKind: 'calendar_date',
    value,
    recordId: 'SYN-rec-gis',
  });

  it('refuses a recorded attribution chip that would render as an error', () => {
    expect(
      gisSourceLine({
        ...gisInput(),
        attribution: [...gisInput().attribution, reference('2026-02-30')],
      }),
    ).toEqual({ kind: 'refused', reason: 'gis_reference_invalid' });
  });

  it('keeps a valid recorded attribution chip', () => {
    expect(
      gisSourceLine({
        ...gisInput(),
        attribution: [...gisInput().attribution, reference('2024-02-29')],
      }).kind,
    ).toBe('line');
  });
});

describe('calendar acceptance against an independent oracle', () => {
  /** Exact oracle: a four-digit year from 1000 and a real Gregorian day. */
  function oracleDay(year: number, month: number, day: number): boolean {
    if (year < 1000 || month < 1 || month > 12 || day < 1) return false;
    const stamp = new Date(Date.UTC(2000, month - 1, day));
    stamp.setUTCFullYear(year);
    return stamp.getUTCMonth() === month - 1 && stamp.getUTCDate() === day;
  }
  const pad = (value: number, size: number) =>
    String(value).padStart(size, '0');
  const YEARS = [0, 999, 1000, 1900, 1999, 2000, 2023, 2024, 2100, 9999];

  it('accepts exactly the real dates over years x months 0-13 x days 0-32', () => {
    for (const year of YEARS) {
      for (let month = 0; month <= 13; month += 1) {
        for (let day = 0; day <= 32; day += 1) {
          const value = `${pad(year, 4)}-${pad(month, 2)}-${pad(day, 2)}`;
          expect(calendarAccepted(value, 'calendar_date'), value).toBe(
            oracleDay(year, month, day),
          );
        }
      }
    }
  });

  it('accepts exactly the four-digit years from 1000', () => {
    for (const year of YEARS) {
      expect(calendarAccepted(pad(year, 4), 'calendar_year')).toBe(
        year >= 1000,
      );
    }
    for (const value of ['', '2024 ', '+2024', '20245', '2O24']) {
      expect(calendarAccepted(value, 'calendar_year'), value).toBe(false);
    }
  });
});

describe('height credits over the whole drawn-list domain (length up to four)', () => {
  const ALL: HeightSource[] = [
    'recorded',
    'floor_count',
    'bldg_3dglobfp',
    'bldg_wsf3d',
  ];
  function lists(length: number): HeightSource[][] {
    if (length === 0) return [[]];
    return lists(length - 1).flatMap((head) =>
      ALL.map((item) => [...head, item]),
    );
  }
  const domain = [0, 1, 2, 3, 4].flatMap(lists);
  const presence = [
    {},
    { bldg_3dglobfp: inputs().bldg_3dglobfp },
    { bldg_wsf3d: inputs().bldg_wsf3d },
    inputs(),
  ] as HeightCreditInputs[];

  it('credits exactly the drawn fallbacks, once each, or refuses', () => {
    for (const drawn of domain) {
      for (const given of presence) {
        const owed = (['bldg_3dglobfp', 'bldg_wsf3d'] as const).filter((id) =>
          drawn.includes(id),
        );
        const missing = owed.find((id) => !given[id]);
        const result = heightCredits('ar', drawn, given);
        if (missing) {
          expect(result).toEqual({
            kind: 'refused',
            reason:
              missing === 'bldg_3dglobfp'
                ? 'globfp_credit_absent'
                : 'wsf3d_credit_absent',
          });
          continue;
        }
        if (result.kind !== 'credits') throw new Error('refused');
        expect(result.lines.map((line) => line.sourceId)).toEqual(owed);
      }
    }
  });
});
