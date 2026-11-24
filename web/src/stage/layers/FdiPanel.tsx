/**
 * FDI list, card and credits. Numbers stay in Fact chips.
 * Filters hide rows. They do not count the rows that remain.
 */
import { useState } from 'react';

import { FactChip } from '../../facts/FactChip';
import type { FactRegistry } from '../../facts/registry';
import { text, type Language } from '../../i18n';
import { FDI_FILTERS, FDI_WORD_FIELDS, type FdiFilter } from './fdi';
import type {
  FdiFilterValue,
  InvestmentCredits,
  LayerFeature,
  LayerPayload,
  TextSegment,
} from './payload';
import { SegmentText } from './Segments';

export interface FdiFeature {
  feature_id: string;
  fact_id?: string;
  year?: string;
  metric_key: string;
  words?: Record<string, string>;
  field_segments?: LayerFeature['field_segments'];
  caveat_keys?: string[];
  capex_fact_id?: string;
  jobs_fact_id?: string;
  lon_fact_id?: string;
  lat_fact_id?: string;
  announced?: {
    referenceKind: 'calendar_year' | 'calendar_month' | 'calendar_date';
    value: string;
    recordId: string;
  };
  filter?: FdiFilterValue;
}

export function FdiBlock({
  language,
  registry,
  listed,
  marks,
  features,
  credits,
  countFacts,
  filterOptions,
  selectedId,
  onOpenChain,
}: {
  language: Language;
  registry: FactRegistry;
  listed: readonly string[];
  marks: readonly string[];
  features: readonly FdiFeature[];
  credits: InvestmentCredits | null;
  countFacts: readonly { fact_id: string; year: string }[];
  filterOptions?: LayerPayload['filter_options'];
  selectedId: string;
  onOpenChain: (factId: string) => void;
}) {
  const [filters, setFilters] = useState<FdiFilterValue>({});
  const shown = listed.filter((id) => matches(features, id, filters));
  const cardId =
    shown.find((id) => id === selectedId) ?? shown[0] ?? listed[0] ?? '';
  return (
    <section data-part="fdi-panel">
      <ul data-part="fdi-filters">
        {FDI_FILTERS.map((key) => (
          <li key={key} data-filter={key}>
            {text(language, filterLabel(key))}
            {(filterOptions?.[key] ?? []).map((option) => {
              const choice = typeof option === 'string' ? option : option.key;
              return (
                <button
                  key={choice}
                  type="button"
                  data-choice={choice}
                  aria-pressed={filters[key] === choice}
                  onClick={() =>
                    setFilters((current) => ({
                      ...current,
                      [key]: current[key] === choice ? undefined : choice,
                    }))
                  }
                >
                  {typeof option === 'string' ? (
                    <bdi>{choice}</bdi>
                  ) : (
                    <SegmentText segments={option.label} language={language} />
                  )}
                </button>
              );
            })}
          </li>
        ))}
      </ul>
      <div data-part="fdi-card" data-project-card={cardId}>
        <FdiFields
          language={language}
          registry={registry}
          feature={features.find((feature) => feature.feature_id === cardId)}
          onOpenChain={onOpenChain}
        />
        <FdiCredits language={language} credits={credits} surface="card" />
      </div>
      <ul data-part="fdi-list">
        {shown.map((id) => (
          <li
            key={id}
            data-project={id}
            data-mark={marks.includes(id) ? 'yes' : 'no'}
          >
            <FdiFields
              language={language}
              registry={registry}
              feature={features.find((feature) => feature.feature_id === id)}
              onOpenChain={onOpenChain}
            />
          </li>
        ))}
      </ul>
      <FdiCredits language={language} credits={credits} surface="list" />
      <div data-part="fdi-legend">
        {countFacts.map((row) => (
          <span key={row.fact_id} data-count-fact={row.fact_id}>
            <FactChip
              variant="compact"
              factId={row.fact_id}
              registry={registry}
              language={language}
              onOpen={onOpenChain}
            />
            {row.year ? (
              <FactChip
                variant="reference"
                language={language}
                kind="calendar_year"
                value={row.year}
                recordId={`${row.fact_id}-year`}
              />
            ) : null}
          </span>
        ))}
        <FdiCredits language={language} credits={credits} surface="legend" />
      </div>
    </section>
  );
}

function matches(
  features: readonly FdiFeature[],
  id: string,
  filters: FdiFilterValue,
): boolean {
  const feature = features.find((item) => item.feature_id === id);
  if (!feature) return false;
  for (const key of FDI_FILTERS) {
    const chosen = filters[key];
    if (!chosen) continue;
    if (feature.filter?.[key] !== chosen) return false;
  }
  return true;
}

function filterLabel(
  key: FdiFilter,
):
  | 'layers.fdi.filter.sector'
  | 'layers.fdi.filter.country'
  | 'layers.fdi.filter.period'
  | 'layers.fdi.filter.location' {
  if (key === 'sector') return 'layers.fdi.filter.sector';
  if (key === 'source_country') return 'layers.fdi.filter.country';
  if (key === 'period') return 'layers.fdi.filter.period';
  return 'layers.fdi.filter.location';
}

export function FdiCredits({
  language,
  credits,
  surface,
}: {
  language: Language;
  credits: InvestmentCredits | null;
  surface: 'card' | 'list' | 'legend';
}) {
  return (
    <details data-part="fdi-credits" data-surface={surface}>
      <summary>{text(language, 'layers.fdi.credits')}</summary>
      {credits ? (
        <dl>
          <dt data-credit-label="publisher">
            {text(language, 'layers.fdi.credit.publisher')}
          </dt>
          <dd data-credit-field="publisher">
            <SegmentText segments={credits.publisher} language={language} />
          </dd>
          <dt data-credit-label="gatherer">
            {text(language, 'layers.fdi.credit.gatherer')}
          </dt>
          <dd data-credit-field="gatherer">
            <SegmentText segments={credits.gatherer} language={language} />
          </dd>
          <dt data-credit-label="read_on">
            {text(language, 'layers.fdi.credit.read_on')}
          </dt>
          <dd data-credit-field="read_on">
            <FactChip
              variant="reference"
              language={language}
              kind="calendar_date"
              value={credits.read_on}
              recordId={`fdi-read-on-${surface}`}
            />
          </dd>
        </dl>
      ) : null}
      {credits ? (
        <a data-credit-field="dashboard" href={credits.dashboard_url}>
          {text(language, 'layers.fdi.dashboard')}
        </a>
      ) : null}
      <p data-caveat="fdi_estimates_sentence">
        {text(language, 'layers.fdi.caveat.estimates')}
      </p>
      <p data-caveat="fdi_coverage_sentence">
        {text(language, 'layers.fdi.caveat.coverage')}
      </p>
    </details>
  );
}

function FdiFields({
  language,
  registry,
  feature,
  onOpenChain,
}: {
  language: Language;
  registry: FactRegistry;
  feature: FdiFeature | undefined;
  onOpenChain: (factId: string) => void;
}) {
  if (!feature) return null;
  const capexId =
    feature.capex_fact_id ??
    (feature.metric_key === 'fdi_capex' ? feature.fact_id : undefined);
  const jobsId =
    feature.jobs_fact_id ??
    (feature.metric_key === 'fdi_jobs' ? feature.fact_id : undefined);
  return (
    <div data-fdi-fields="all">
      {FDI_WORD_FIELDS.map((field) => (
        <FdiWord
          key={field}
          field={field}
          value={feature.words?.[field]}
          segments={feature.field_segments?.[field]}
          language={language}
        />
      ))}
      <FactSlot
        field="capex_value"
        estimate
        factId={capexId}
        year={feature.year}
        language={language}
        registry={registry}
        onOpenChain={onOpenChain}
      />
      <FactSlot
        field="jobs"
        estimate
        factId={jobsId}
        year={feature.year}
        language={language}
        registry={registry}
        onOpenChain={onOpenChain}
      />
      <FactSlot
        field="lon"
        factId={feature.lon_fact_id}
        year={feature.year}
        language={language}
        registry={registry}
        onOpenChain={onOpenChain}
      />
      <FactSlot
        field="lat"
        factId={feature.lat_fact_id}
        year={feature.year}
        language={language}
        registry={registry}
        onOpenChain={onOpenChain}
      />
      <span data-field="announced">
        {feature.announced ? (
          <FactChip
            variant="reference"
            language={language}
            kind={feature.announced.referenceKind}
            value={feature.announced.value}
            recordId={feature.announced.recordId}
          />
        ) : (
          text(language, 'layers.fdi.unstated')
        )}
      </span>
    </div>
  );
}

function FactSlot({
  field,
  factId,
  year,
  estimate = false,
  language,
  registry,
  onOpenChain,
}: {
  field: string;
  /** Capex and jobs: the announced-estimate label sits in the value's own slot. */
  estimate?: boolean;
  factId: string | undefined;
  year: string | undefined;
  language: Language;
  registry: FactRegistry;
  onOpenChain: (factId: string) => void;
}) {
  if (!factId) {
    return (
      <span data-field={field}>{text(language, 'layers.fdi.unstated')}</span>
    );
  }
  return (
    <span className="figure-cell" data-field={field}>
      <FactChip
        variant="value"
        size="standard"
        factId={factId}
        registry={registry}
        language={language}
        onOpen={onOpenChain}
      />
      {year ? (
        <FactChip
          variant="reference"
          language={language}
          kind="calendar_year"
          value={year}
          recordId={`${factId}-year`}
        />
      ) : null}
      {estimate ? (
        <span data-label="announced">
          {text(language, 'layers.fdi.announced')}
        </span>
      ) : null}
    </span>
  );
}

function FdiWord({
  field,
  value,
  language,
  segments,
}: {
  field: string;
  value: string | undefined;
  language: Language;
  segments?: readonly TextSegment[];
}) {
  if (segments)
    return (
      <span data-field={field}>
        <SegmentText segments={segments} language={language} />
      </span>
    );
  if (!value) {
    return (
      <span data-field={field}>{text(language, 'layers.fdi.unstated')}</span>
    );
  }
  return (
    <span data-field={field}>
      <bdi>{value}</bdi>
    </span>
  );
}
