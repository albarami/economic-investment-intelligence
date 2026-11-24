/**
 * Firms-by-tower legend. Swatches carry the ramp; words carry the identity.
 * No origin sample is mounted here.
 */
import type { ReactElement } from 'react';

import { FactChip } from '../../facts/FactChip';
import type { FactRegistry } from '../../facts/registry';
import { text, type Language } from '../../i18n';
import type { FcFirmsSection } from './payload';
import { rampToken } from './ramp';

const SWATCH_EDGE = '12px';

const CLASS_WORD = {
  band_low: 'layers.night.class.band_low',
  band_mid_low: 'layers.night.class.band_mid_low',
  band_mid: 'layers.night.class.band_mid',
  band_mid_high: 'layers.night.class.band_mid_high',
  band_high: 'layers.night.class.band_high',
} as const;

const DIRECTION = {
  higher: 'direction.higher',
  lower: 'direction.lower',
  equal: 'direction.equal',
} as const;

type ClassWord = keyof typeof CLASS_WORD;
type DirectionWord = keyof typeof DIRECTION;

function classWord(classId: string): ClassWord | null {
  if (Object.prototype.hasOwnProperty.call(CLASS_WORD, classId)) {
    return classId as ClassWord;
  }
  return null;
}

function directionWord(direction: string): DirectionWord | null {
  if (Object.prototype.hasOwnProperty.call(DIRECTION, direction)) {
    return direction as DirectionWord;
  }
  return null;
}

export function FcFirmsLegend({
  language,
  registry,
  section,
  sourceFactId,
  onOpenChain,
}: {
  language: Language;
  registry: FactRegistry;
  section: FcFirmsSection;
  sourceFactId: string;
  onOpenChain: (factId: string) => void;
}): ReactElement {
  const direction = directionWord(section.direction);
  return (
    <section data-part="fc-firms-legend">
      <p data-legend="name">{text(language, 'layers.fc.name')}</p>
      <span data-legend="unit">{text(language, 'layers.fc.unit')}</span>
      {direction ? (
        <span data-legend="direction">
          {text(language, DIRECTION[direction])}
        </span>
      ) : null}
      <ul>
        {section.breaks.map((band) => {
          const word = classWord(band.class_id);
          const token = rampToken(band.class_id);
          return (
            <li key={band.class_id} data-class={band.class_id}>
              <span
                data-swatch={band.class_id}
                data-ramp={token ?? ''}
                style={{
                  display: 'inline-block',
                  width: SWATCH_EDGE,
                  height: SWATCH_EDGE,
                  background: token ? `var(${token})` : 'transparent',
                }}
              />
              {word ? <span>{text(language, CLASS_WORD[word])}</span> : null}
              <FactChip
                variant="compact"
                figureCell
                factId={band.fact_id}
                registry={registry}
                language={language}
                onOpen={onOpenChain}
              />
            </li>
          );
        })}
      </ul>
      {section.no_data ? (
        <p data-swatch="no-data">{text(language, 'layers.fc.nodata')}</p>
      ) : null}
      {section.coverage_note_keys.includes('zone_without_district') ? (
        <p data-note="zone-without-district">
          {text(language, 'layers.fc.zone')}
        </p>
      ) : null}
      <button type="button" data-action="show-as-table">
        {text(language, 'layers.fc.table')}
      </button>
      <button
        type="button"
        data-action="source-chain"
        data-scope="legend"
        onClick={() => onOpenChain(sourceFactId)}
      >
        {text(language, 'layers.fc.method')}
      </button>
    </section>
  );
}
