/** C36-C38, application-owned text and one isolated display fact per card. */
import { useId, useState, type ReactElement } from 'react';
import { fragmentField } from '../brief/catalogue';
import { FactChip } from '../facts/FactChip';
import { WithheldMark } from '../facts/ProvenanceMark';
import type { FactRegistry } from '../facts/registry';
import type { Resolution } from '../facts/types';
import type { Language } from '../i18n';
import { text } from '../i18n';
import { formatFactValue } from '../facts/formatters';
import { contextFamilies, type ContextFamily } from './public-context-contract';
import './public-context.css';

type Day =
  | 'monday'
  | 'tuesday'
  | 'wednesday'
  | 'thursday'
  | 'friday'
  | 'saturday'
  | 'sunday';
type Ready = { state: 'ready'; factId: string };
export type ContextPayload =
  | (Ready & { family: 'night_lights' })
  | (Ready & {
      family: 'venue_busyness';
      retrievedOn: string;
      providerUpdatedOn: string | null;
      day: Day;
      hour: string;
    })
  | (Ready & {
      family: 'population_age_sex';
      ageBand: string | null;
      sex: 'female' | 'male' | 'none';
    })
  | {
      family: ContextFamily;
      state: 'no_data';
      reason: 'missing_input' | 'no_forecast';
    };

function words(key: string, language: Language): string {
  return (
    fragmentField(key, language === 'ar' ? 'template_ar' : 'template_en') ?? ''
  );
}

function dateAccepted(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    formatFactValue(value, 'calendar_date', 'en', 'reference').ok
  );
}

export function contextAccepted(
  payload: unknown,
  registry: FactRegistry,
): payload is ContextPayload {
  if (!payload || typeof payload !== 'object') return false;
  const item = payload as Record<string, unknown>;
  if (
    typeof item.family !== 'string' ||
    !Object.hasOwn(contextFamilies, item.family)
  )
    return false;
  const family = item.family as ContextFamily;
  if (item.state === 'no_data') {
    return (
      Object.keys(item).length === 3 &&
      (item.reason === 'missing_input' ||
        (family === 'venue_busyness' && item.reason === 'no_forecast'))
    );
  }
  if (item.state !== 'ready' || typeof item.factId !== 'string') return false;
  const keys = ['family', 'state', 'factId'];
  if (family === 'venue_busyness') {
    keys.push('retrievedOn', 'providerUpdatedOn', 'day', 'hour');
    if (
      !dateAccepted(item.retrievedOn) ||
      (item.providerUpdatedOn !== null && !dateAccepted(item.providerUpdatedOn))
    )
      return false;
    if (
      ![
        'monday',
        'tuesday',
        'wednesday',
        'thursday',
        'friday',
        'saturday',
        'sunday',
      ].includes(String(item.day))
    )
      return false;
    if (
      typeof item.hour !== 'string' ||
      !/^(?:[0-9]|1[0-9]|2[0-3])$/.test(item.hour)
    )
      return false;
  }
  if (family === 'population_age_sex') {
    keys.push('ageBand', 'sex');
    if (
      item.ageBand !== null &&
      (typeof item.ageBand !== 'string' ||
        !formatFactValue(item.ageBand, 'published_text', 'en', 'reference').ok)
    )
      return false;
    if (!['female', 'male', 'none'].includes(String(item.sex))) return false;
  }
  if (
    Object.keys(item).length !== keys.length ||
    Object.keys(item).some((key) => !keys.includes(key))
  )
    return false;
  const resolved = registry.resolve(item.factId);
  if (resolved.status !== 'ready') return false;
  const { binding, table } = resolved;
  const fact = binding.fact;
  const spec = contextFamilies[family];
  if (
    binding.metricKey !== spec.metric ||
    fact.unit !== spec.unit ||
    table?.tableName !== spec.table ||
    fact.label_en !== spec.label
  )
    return false;
  if (
    (fact.provenance !== 'public' && fact.provenance !== 'suppressed') ||
    fact.evidence_status !== 'observed' ||
    binding.presentation !== 'ordinary'
  )
    return false;
  if (fact.input_classes.length !== 1 || fact.input_classes[0] !== 'public')
    return false;
  if (
    !fact.caveat_keys.includes(spec.caveat) ||
    fact.geography.kind !== spec.geography ||
    fact.geography.apportioned_from !== undefined
  )
    return false;
  if (
    family === 'night_lights' &&
    fact.caveat_keys.includes('grid_cells_summed')
  )
    return false;
  if (
    family === 'venue_busyness' &&
    (fact.period !== item.retrievedOn ||
      resolved.lineage.rowRetrievalDate !== item.retrievedOn ||
      resolved.lineage.providerUpdatedOn !== item.providerUpdatedOn ||
      binding.qualifiers?.day_of_week !== item.day ||
      binding.qualifiers?.hour !== item.hour)
  )
    return false;
  if (
    family === 'population_age_sex' &&
    (binding.qualifiers?.age_band !== (item.ageBand ?? 'all') ||
      binding.qualifiers?.sex !== item.sex)
  )
    return false;
  return true;
}

type Level = 'answer' | 'comparison' | 'evidence';

/** Native buttons supply Enter, Space and pointer activation without dragging. */
function ContextLevel({
  level,
  language,
  factId,
  children,
}: {
  level: Level;
  language: Language;
  factId?: string;
  children: ReactElement;
}) {
  const id = useId();
  const [open, setOpen] = useState(level === 'answer');
  return (
    <section data-context-level={level}>
      <button
        type="button"
        id={`${id}-control`}
        aria-expanded={open}
        aria-controls={`${id}-content`}
        onClick={() => setOpen(!open)}
      >
        {words(`context_level_${level}`, language)}
      </button>
      <div
        id={`${id}-content`}
        role="region"
        aria-labelledby={`${id}-control`}
        hidden={!open}
        data-fact-id={factId}
        className="context-level-body"
      >
        {open ? children : null}
      </div>
    </section>
  );
}

/** Read the same resolved chain as the answer; citation text may contain digits. */
function ContextEvidence({
  resolved,
  language,
}: {
  resolved: Extract<Resolution, { status: 'ready' }>;
  language: Language;
}) {
  const fields = [
    [
      'drawer.release',
      resolved.link === 'table'
        ? resolved.table.tableName
        : resolved.binding.fact.release_id,
      resolved.binding.fact.fact_id,
    ],
    ['drawer.method', resolved.lineage.method, resolved.lineage.lineageId],
  ] as const;
  return (
    <dl className="context-chain">
      {fields.map(([label, value, recordId]) => (
        <div key={label}>
          <dt>{text(language, label)}</dt>
          <dd>
            <FactChip
              variant="reference"
              kind="published_text"
              value={value}
              recordId={recordId}
              language={language}
            />
            {label === 'drawer.method' ? (
              <FactChip
                variant="reference"
                kind="published_text"
                value={resolved.lineage.methodVersion}
                recordId={resolved.lineage.lineageId}
                language={language}
              />
            ) : null}
          </dd>
        </div>
      ))}
      {resolved.sources.flatMap((source) =>
        (
          [
            ['drawer.publisher', source.publisher, 'published_text'],
            ['drawer.dataset', source.datasetOrPage, 'published_text'],
            ['drawer.licence', source.licenceOrTerms, 'published_text'],
            ['drawer.retrieved', source.retrievalDate, 'calendar_date'],
            ['drawer.hash', source.sha256, 'published_text'],
          ] as const
        ).map(([label, value, kind]) => (
          <div
            key={`${source.sourceId}-${label}`}
            data-context-source={source.sourceId}
          >
            <dt>{text(language, label)}</dt>
            <dd>
              <FactChip
                variant="reference"
                kind={kind}
                value={value}
                recordId={source.sourceId}
                language={language}
              />
            </dd>
          </div>
        )),
      )}
    </dl>
  );
}

export function PublicContextCard({
  payload,
  registry,
  language,
  onOpen,
}: {
  payload: ContextPayload;
  registry: FactRegistry;
  language: Language;
  onOpen: (factId: string) => void;
}) {
  if (!contextAccepted(payload, registry)) return null;
  const spec = contextFamilies[payload.family];
  const resolved =
    payload.state === 'ready' ? registry.resolve(payload.factId) : null;
  const reason =
    payload.state === 'no_data'
      ? payload.reason === 'no_forecast'
        ? 'context_no_forecast'
        : 'context_no_data'
      : resolved?.status === 'ready' && resolved.display === 'withheld'
        ? 'context_withheld_reason'
        : null;
  return (
    <article
      className="public-context-card"
      data-context-family={payload.family}
      lang={language}
      dir={language === 'ar' ? 'rtl' : 'ltr'}
    >
      <h2>
        <bdi>{words(payload.family, language)}</bdi>
      </h2>
      <ContextLevel
        level="answer"
        language={language}
        factId={payload.state === 'ready' ? payload.factId : undefined}
      >
        {payload.state === 'no_data' ? (
          <p data-state="NO_DATA">{words(reason!, language)}</p>
        ) : (
          <>
            {resolved?.status === 'ready' && resolved.display === 'withheld' ? (
              <div
                className="layer-sample context-withheld"
                data-pattern="hatch-lock"
                data-state="withheld"
              >
                <span className="chip-withheld">
                  <WithheldMark language={language} />
                </span>
                <p>{words('context_withheld_reason', language)}</p>
              </div>
            ) : (
              <FactChip
                variant="value"
                size="large"
                factId={payload.factId}
                registry={registry}
                language={language}
                onOpen={onOpen}
              />
            )}
            {resolved?.status === 'ready' &&
            payload.family !== 'venue_busyness' ? (
              <FactChip
                variant="reference"
                kind={
                  payload.family === 'night_lights'
                    ? 'calendar_month'
                    : 'calendar_year'
                }
                value={resolved.binding.fact.period}
                recordId={payload.factId}
                language={language}
              />
            ) : null}
            {payload.family === 'venue_busyness' ? (
              <div className="context-meta">
                <bdi>{words(`context_${payload.day}`, language)}</bdi>
                <FactChip
                  variant="reference"
                  kind="published_text"
                  value={payload.hour}
                  recordId={payload.factId}
                  language={language}
                />
                <span>{words('context_retrieved', language)}</span>
                <FactChip
                  variant="reference"
                  kind="calendar_date"
                  value={payload.retrievedOn}
                  recordId={payload.factId}
                  language={language}
                />
                {payload.providerUpdatedOn === null ? (
                  <span>{words('context_update_not_stated', language)}</span>
                ) : (
                  <>
                    <span>{words('context_updated', language)}</span>
                    <FactChip
                      variant="reference"
                      kind="calendar_date"
                      value={payload.providerUpdatedOn}
                      recordId={payload.factId}
                      language={language}
                    />
                  </>
                )}
              </div>
            ) : null}
            {payload.family === 'population_age_sex' ? (
              <div className="context-meta">
                {payload.ageBand === null ? (
                  <span>{words('context_all_ages', language)}</span>
                ) : (
                  <>
                    <span>{words('context_age_band', language)}</span>
                    <FactChip
                      variant="reference"
                      kind="published_text"
                      value={payload.ageBand}
                      recordId={payload.factId}
                      language={language}
                    />
                  </>
                )}
                <span>{words(`context_${payload.sex}`, language)}</span>
              </div>
            ) : null}
            <button type="button" onClick={() => onOpen(payload.factId)}>
              {words('context_source', language)}
            </button>
          </>
        )}
      </ContextLevel>
      <ContextLevel
        level="comparison"
        language={language}
        factId={payload.state === 'ready' ? payload.factId : undefined}
      >
        <p>{words(spec.comparison, language)}</p>
      </ContextLevel>
      <ContextLevel
        level="evidence"
        language={language}
        factId={payload.state === 'ready' ? payload.factId : undefined}
      >
        <>
          {reason ? <p>{words(reason, language)}</p> : null}
          {resolved?.status === 'ready' ? (
            <ContextEvidence resolved={resolved} language={language} />
          ) : null}
        </>
      </ContextLevel>
      <p data-caveat={spec.caveat}>
        <bdi>{words(spec.caveat, language)}</bdi>
      </p>
    </article>
  );
}
