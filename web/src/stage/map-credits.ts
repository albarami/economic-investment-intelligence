/**
 * PUB-110 map credits: the building-height credits of 3D-GloBFP and WSF 3D
 * while a fallback height from them is drawn, and the GIS centre's source line
 * while an imagery-history view is on. Wording is document 04's attribution
 * table; every numeral is a reference chip segment, never plain text.
 */
import { formatFactValue } from '../facts/formatters';
import { text, type Language } from '../i18n';
import { digitInPlain, segmentsBlank } from './layers/checks';
import type { TextSegment } from './layers/payload';

export type HeightSource =
  'recorded' | 'floor_count' | 'bldg_3dglobfp' | 'bldg_wsf3d';
export type FallbackHeightSource = 'bldg_3dglobfp' | 'bldg_wsf3d';

export interface HeightCreditInput {
  retrievalDate: string;
  recordId: string;
  /** WSF 3D only: the catalogue record's year of production. */
  productionYear?: string;
  /** WSF 3D only: the recorded landing page (document 04, `bldg_wsf3d`). */
  landingPage?: string;
}
export type HeightCreditInputs = Partial<
  Record<FallbackHeightSource, HeightCreditInput>
>;

export type HeightCreditReason =
  | 'globfp_credit_absent'
  | 'wsf3d_credit_absent'
  | 'height_retrieval_date_invalid'
  | 'wsf3d_production_year_invalid'
  | 'wsf3d_landing_page_invalid';

export interface HeightCreditLine {
  sourceId: FallbackHeightSource;
  segments: TextSegment[];
  /** The landing page the credit must link to, where document 04 asks one. */
  link?: string;
}
export type HeightCredits =
  | { kind: 'credits'; lines: HeightCreditLine[] }
  | { kind: 'refused'; reason: HeightCreditReason };

/** The release's recorded `gis_*` attribution (document 04 wording, filled). */
export interface GisSourceLineInput {
  attribution: readonly TextSegment[];
  retrievalDate: string;
  recordId: string;
}
export type GisSourceLine =
  | { kind: 'line'; segments: TextSegment[] }
  | {
      kind: 'refused';
      reason:
        | 'gis_source_line_absent'
        | 'gis_retrieval_date_invalid'
        | 'gis_numeral_outside_chip'
        | 'gis_reference_invalid';
    };
const FALLBACKS: readonly FallbackHeightSource[] = [
  'bldg_3dglobfp',
  'bldg_wsf3d',
];
/** Name and licence tokens of document 04 that hold numerals. */
const GLOBFP_NAME = '3D-GloBFP';
const GLOBFP_YEAR = '2024';
const WSF_NAME = 'WSF 3D';
const LICENCE_VERSION = '4.0';

/** True only where the Fact chip's own calendar validation accepts the value. */
export function calendarAccepted(
  value: string,
  unit: 'calendar_date' | 'calendar_year',
): boolean {
  return formatFactValue(value, unit, 'en', 'reference').ok;
}

/** A recorded landing page: an absolute HTTPS address only. */
function landingPageAccepted(value: string | undefined): value is string {
  if (value === undefined || !URL.canParse(value)) return false;
  return new URL(value).protocol === 'https:';
}

function plain(value: string): TextSegment {
  return { kind: 'plain', text: value };
}

function token(value: string, recordId: string): TextSegment {
  return {
    kind: 'reference',
    referenceKind: 'published_text',
    value,
    recordId,
  };
}

function date(value: string, recordId: string): TextSegment {
  return { kind: 'reference', referenceKind: 'calendar_date', value, recordId };
}

function globfpLine(language: Language, input: HeightCreditInput) {
  const id = input.recordId;
  return [
    plain(text(language, 'credits.heights.lead')),
    token(GLOBFP_NAME, id),
    plain(text(language, 'credits.globfp.author')),
    token(GLOBFP_YEAR, id),
    plain(text(language, 'credits.licence')),
    token(LICENCE_VERSION, id),
    plain(text(language, 'credits.retrieved')),
    date(input.retrievalDate, id),
    plain(text(language, 'credits.heights.estimates')),
  ];
}

function wsfLine(language: Language, input: HeightCreditInput, year: string) {
  const id = input.recordId;
  return [
    plain(text(language, 'credits.heights.lead')),
    token(WSF_NAME, id),
    plain(text(language, 'credits.wsf3d.publisher')),
    token(LICENCE_VERSION, id),
    plain(text(language, 'credits.retrieved')),
    date(input.retrievalDate, id),
    plain(text(language, 'credits.heights.estimates')),
    plain(text(language, 'credits.wsf3d.copyright')),
    {
      kind: 'reference',
      referenceKind: 'calendar_year',
      value: year,
      recordId: id,
    },
  ] satisfies TextSegment[];
}

/** The credits owed by the drawn height sources, or the reason none may draw. */
export function heightCredits(
  language: Language,
  drawn: readonly HeightSource[],
  inputs: HeightCreditInputs,
): HeightCredits {
  const lines: HeightCreditLine[] = [];
  for (const sourceId of FALLBACKS.filter((id) => drawn.includes(id))) {
    const input = inputs[sourceId];
    if (!input) {
      return {
        kind: 'refused',
        reason:
          sourceId === 'bldg_3dglobfp'
            ? 'globfp_credit_absent'
            : 'wsf3d_credit_absent',
      };
    }
    if (!calendarAccepted(input.retrievalDate, 'calendar_date')) {
      return { kind: 'refused', reason: 'height_retrieval_date_invalid' };
    }
    if (sourceId === 'bldg_3dglobfp') {
      lines.push({ sourceId, segments: globfpLine(language, input) });
      continue;
    }
    const year = input.productionYear ?? '';
    if (!calendarAccepted(year, 'calendar_year')) {
      return { kind: 'refused', reason: 'wsf3d_production_year_invalid' };
    }
    if (!landingPageAccepted(input.landingPage)) {
      return { kind: 'refused', reason: 'wsf3d_landing_page_invalid' };
    }
    lines.push({
      sourceId,
      segments: wsfLine(language, input, year),
      link: input.landingPage,
    });
  }
  return { kind: 'credits', lines };
}

/** The GIS centre's source line: its recorded attribution and retrieval date. */
export function gisSourceLine(input: GisSourceLineInput): GisSourceLine {
  if (segmentsBlank(input.attribution)) {
    return { kind: 'refused', reason: 'gis_source_line_absent' };
  }
  if (!calendarAccepted(input.retrievalDate, 'calendar_date')) {
    return { kind: 'refused', reason: 'gis_retrieval_date_invalid' };
  }
  if (digitInPlain(input.attribution)) {
    return { kind: 'refused', reason: 'gis_numeral_outside_chip' };
  }
  const chipFails = (segment: TextSegment) =>
    segment.kind === 'reference' &&
    !formatFactValue(segment.value, segment.referenceKind, 'en', 'reference')
      .ok;
  if (input.attribution.some(chipFails)) {
    return { kind: 'refused', reason: 'gis_reference_invalid' };
  }
  return {
    kind: 'line',
    segments: [...input.attribution, date(input.retrievalDate, input.recordId)],
  };
}
