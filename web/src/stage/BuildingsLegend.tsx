/**
 * Legend of the 3D buildings: heights are estimates, shadows use estimated
 * heights, and each fallback's measured error opens behind "More evidence"
 * (FE-52, FE-143; decision 0048 items 2 and 4; decision 0064 item 25).
 * Every numeral is a Fact chip.
 */
import type { ReactElement } from 'react';

import { FactChip } from '../facts/FactChip';
import type { FactRegistry } from '../facts/registry';
import { direction, text, type Language, type StringKey } from '../i18n';
import type {
  BuildingHeightsRead,
  BuildingRow,
  FallbackError,
  FallbackSlot,
  HeightSource,
  ShadowSelection,
} from './buildings3d';

const ERROR_ROWS: readonly (readonly [FallbackSlot, StringKey])[] = [
  ['pairs_fact_id', 'buildings.error.pairs'],
  ['mean_signed_fact_id', 'buildings.error.meanSigned'],
  ['mean_abs_fact_id', 'buildings.error.meanAbs'],
  ['median_abs_fact_id', 'buildings.error.medianAbs'],
];

function sourceKey(source: HeightSource): StringKey {
  return `buildings.source.${source}` as StringKey;
}

function FallbackRow({
  language,
  registry,
  error,
  onOpenChain,
}: {
  language: Language;
  registry: FactRegistry;
  error: FallbackError;
  onOpenChain: (factId: string) => void;
}): ReactElement {
  return (
    <section data-fallback={error.source}>
      <h4>{text(language, sourceKey(error.source))}</h4>
      {'reason' in error ? (
        <p data-reason="no_pairs">
          {text(language, 'buildings.error.noPairs')}
        </p>
      ) : (
        <dl>
          {ERROR_ROWS.map(([field, label]) => (
            <div key={field}>
              <dt>{text(language, label)}</dt>
              <dd>
                <FactChip
                  variant="compact"
                  factId={error[field]}
                  registry={registry}
                  language={language}
                  onOpen={onOpenChain}
                />
              </dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

/** The fallback panel of decision 0064 item 25. */
export function FallbackPanel({
  language,
  registry,
  errors,
  onOpenChain,
}: {
  language: Language;
  registry: FactRegistry;
  errors: readonly FallbackError[];
  onOpenChain: (factId: string) => void;
}): ReactElement {
  return (
    <section data-part="fallback-panel" dir={direction(language)}>
      <h3>{text(language, 'buildings.fallbackPanel')}</h3>
      {errors.map((error) => (
        <FallbackRow
          key={error.source}
          language={language}
          registry={registry}
          error={error}
          onOpenChain={onOpenChain}
        />
      ))}
    </section>
  );
}

/** One picked building's height source and that source's measured error. */
function BuildingEvidence({
  language,
  registry,
  building,
  errors,
  onOpenChain,
}: {
  language: Language;
  registry: FactRegistry;
  building: BuildingRow;
  errors: readonly FallbackError[];
  onOpenChain: (factId: string) => void;
}): ReactElement {
  const error = errors.find((entry) => entry.source === building.height_source);
  return (
    <section data-part="building-evidence">
      <p data-height-source={building.height_source}>
        {text(language, sourceKey(building.height_source))}
      </p>
      {error ? (
        <FallbackRow
          language={language}
          registry={registry}
          error={error}
          onOpenChain={onOpenChain}
        />
      ) : null}
    </section>
  );
}

/** Renders only a read accepted whole: its slots are bound to their facts. */
export function BuildingsLegend({
  language,
  heights,
  selection,
  picked,
  onOpenChain,
}: {
  language: Language;
  heights: BuildingHeightsRead;
  selection: ShadowSelection;
  picked?: BuildingRow;
  onOpenChain: (factId: string) => void;
}): ReactElement {
  const { registry, fallback_errors: errors } = heights;
  return (
    <section
      data-part="buildings-legend"
      className="buildings-legend"
      dir={direction(language)}
    >
      <p data-words="heights-estimates">
        {text(language, 'buildings.estimates')}
      </p>
      {selection.casting.length > 0 ? (
        <p data-words="shadow-estimated">
          {text(language, 'buildings.shadowEstimated')}
        </p>
      ) : null}
      {selection.limited ? (
        <p data-words="shadow-limited" role="status">
          {text(language, 'buildings.shadowLimited')}
        </p>
      ) : null}
      <details data-part="more-evidence">
        <summary>{text(language, 'buildings.moreEvidence')}</summary>
        {picked ? (
          <BuildingEvidence
            language={language}
            registry={registry}
            building={picked}
            errors={errors}
            onOpenChain={onOpenChain}
          />
        ) : null}
        <FallbackPanel
          language={language}
          registry={registry}
          errors={errors}
          onOpenChain={onOpenChain}
        />
      </details>
    </section>
  );
}
