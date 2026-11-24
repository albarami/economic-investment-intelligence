/**
 * The Fact chip family. value and compact take a fact id, never free text.
 * No class word or mark is drawn on the chip.
 */
import { useId, useState, type ReactNode } from 'react';

import {
  direction,
  text,
  unitLabel,
  unitWord,
  type Language,
  type StringKey,
} from '../i18n';
import {
  countForm,
  formatFactValue,
  formatRange,
  type SignMode,
} from './formatters';
import { NumericInput, type Preset } from './NumericInput';
import type { FactRegistry } from './registry';
import type { Resolution } from './types';
import type { ModeReason, SpendMeter } from '../stage/map-modes';

export type ValueSize = 'hero' | 'large' | 'standard' | 'inline';

export type ReferenceKind =
  'calendar_date' | 'calendar_month' | 'calendar_year' | 'published_text';

type Open = (factId: string) => void;

export type FactChipProps =
  | {
      variant: 'operational';
      language: Language;
      meter: SpendMeter | null;
      reason: ModeReason | null;
      factId?: never;
      registry?: never;
    }
  | {
      variant: 'value';
      meter?: never;
      size: ValueSize;
      factId: string;
      registry: FactRegistry;
      language: Language;
      onOpen: Open;
      figure?: boolean;
      figureCell?: boolean;
    }
  | {
      variant: 'compact';
      meter?: never;
      factId: string;
      registry: FactRegistry;
      language: Language;
      onOpen: Open;
      figure?: boolean;
      figureCell?: boolean;
    }
  | {
      variant: 'input';
      language: Language;
      value: string;
      onChange: (value: string) => void;
      presets: readonly Preset[];
    }
  | {
      variant: 'input';
      kind: 'preset';
      language: Language;
      value: number;
      unit: 'metres' | 'kilometres' | 'minutes';
      recordId: string;
    }
  | {
      variant: 'reference';
      language: Language;
      kind: ReferenceKind;
      value: string;
      recordId: string;
    };

function Isolate({
  children,
  language,
  automatic,
  opaque,
}: {
  children: ReactNode;
  language: Language;
  automatic: boolean;
  opaque?: boolean;
}) {
  if (automatic)
    return (
      <bdi className="chip-num" dir="auto" lang={language}>
        {children}
      </bdi>
    );
  return (
    <bdi className="chip-num" dir={opaque ? 'auto' : 'ltr'} lang="en">
      {children}
    </bdi>
  );
}

function suppliedDirection(
  registry: FactRegistry,
  parentId: string,
  directionId: string | undefined,
  language: Language,
): string {
  if (!directionId) return '';
  const referencers = registry.directionReferencers(directionId);
  if (referencers.length !== 1 || referencers[0] !== parentId) return '';
  const resolved = registry.resolve(directionId);
  if (resolved.status !== 'ready' || resolved.display !== 'value') return '';
  const value = resolved.binding.fact.value;
  if (resolved.binding.fact.unit !== 'direction' || typeof value !== 'string')
    return '';
  if (value !== 'higher' && value !== 'lower' && value !== 'equal') return '';
  return text(language, `direction.${value}`);
}

function Words({
  language,
  state,
}: {
  language: Language;
  state: 'refused' | 'no_data' | 'error' | 'loading';
}) {
  const key =
    state === 'no_data'
      ? 'chip.noData'
      : state === 'loading'
        ? 'chip.loading'
        : state === 'error'
          ? 'chip.error'
          : 'chip.refused';
  const label = text(language, key);
  if (state === 'loading')
    return <span className="chip-skeleton" aria-label={label} />;
  return <span className="chip-unit">{label}</span>;
}

export function rangeText(
  registry: FactRegistry,
  lowId: string,
  highId: string,
  unit: string,
  language: Language,
): string | null {
  const low = registry.resolve(lowId);
  const high = registry.resolve(highId);
  if (low.status !== 'ready' || high.status !== 'ready') return null;
  if (typeof low.binding.fact.value !== 'number') return null;
  if (typeof high.binding.fact.value !== 'number') return null;
  const formatted = formatRange(
    low.binding.fact.value,
    high.binding.fact.value,
    unit,
    language,
  );
  return formatted.ok ? formatted.text : null;
}

function Bound({
  name,
  shown,
  factId,
  onOpen,
}: {
  name: 'low' | 'high';
  shown: string;
  factId: string;
  onOpen: Open;
}) {
  return (
    <span
      data-bound={name}
      onClick={(event) => {
        event.stopPropagation();
        onOpen(factId);
      }}
      onKeyDown={(event) => {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        event.stopPropagation();
        onOpen(factId);
      }}
    >
      {shown}
    </span>
  );
}

function readyBody(
  resolution: Extract<Resolution, { status: 'ready' }>,
  registry: FactRegistry,
  language: Language,
  factId: string,
  onOpen: Open,
): { state: string; label: string; body: ReactNode } {
  if (resolution.display === 'withheld') {
    // The reason in words, never a value and never zero (decision 0042 item 7).
    const reason = text(language, 'chip.withheld');
    const action = text(language, 'chip.open');
    return {
      state: 'withheld',
      label: language === 'ar' ? `${reason}، ${action}` : `${reason} ${action}`,
      body: <span className="chip-withheld chip-unit">{reason}</span>,
    };
  }
  const fact = resolution.binding.fact;
  const sign: SignMode =
    resolution.binding.presentation === 'change' ? 'always' : 'auto';
  const formatted = formatFactValue(
    fact.value,
    fact.unit,
    language,
    'fact',
    sign,
  );
  if (!formatted.ok) {
    const label = text(language, 'chip.error');
    return {
      state: 'error',
      label,
      body: <span className="chip-unit">{label}</span>,
    };
  }
  let range: string | null = null;
  let lowShown: string | null = null;
  let highShown: string | null = null;
  if (resolution.binding.presentation === 'estimated_count') {
    const lowId = resolution.binding.rangeLowId;
    const highId = resolution.binding.rangeHighId;
    if (!lowId || !highId) {
      const label = text(language, 'chip.error');
      return {
        state: 'error',
        label,
        body: <span className="chip-unit">{label}</span>,
      };
    }
    const low = registry.resolve(lowId);
    const high = registry.resolve(highId);
    if (low.status !== 'ready' || high.status !== 'ready') {
      const label = text(language, 'chip.error');
      return {
        state: 'error',
        label,
        body: <span className="chip-unit">{label}</span>,
      };
    }
    if (typeof low.binding.fact.value !== 'number') {
      const label = text(language, 'chip.error');
      return {
        state: 'error',
        label,
        body: <span className="chip-unit">{label}</span>,
      };
    }
    if (typeof high.binding.fact.value !== 'number') {
      const label = text(language, 'chip.error');
      return {
        state: 'error',
        label,
        body: <span className="chip-unit">{label}</span>,
      };
    }
    const left = formatFactValue(low.binding.fact.value, fact.unit, language);
    const right = formatFactValue(high.binding.fact.value, fact.unit, language);
    if (!left.ok || !right.ok) {
      const label = text(language, 'chip.error');
      return {
        state: 'error',
        label,
        body: <span className="chip-unit">{label}</span>,
      };
    }
    lowShown = left.text;
    highShown = right.text;
    range = `${left.text}\u2013${right.text}`;
  }
  const unit =
    fact.unit === 'percent'
      ? null
      : unitLabel(
          language,
          fact.unit,
          resolution.binding.metricKey,
          countForm(fact.value, language),
        );
  const signed =
    resolution.binding.presentation === 'change'
      ? suppliedDirection(
          registry,
          resolution.binding.fact.fact_id,
          resolution.binding.directionId,
          language,
        )
      : '';
  const action = text(language, 'chip.open');
  const head = [formatted.text, unit, signed].filter((part) => part).join(' ');
  const label = language === 'ar' ? `${head}، ${action}` : `${head} ${action}`;
  return {
    state: 'ready',
    label,
    body: (
      <bdi className="chip-root">
        <span className="chip-figure">
          <Isolate language={language} automatic={false}>
            {formatted.text}
          </Isolate>
          {unit ? <span className="chip-unit">{unit}</span> : null}
          {signed ? <span className="chip-unit">{signed}</span> : null}
        </span>
        {range && lowShown && highShown ? (
          <span className="chip-range">
            <span className="chip-unit">{text(language, 'chip.range')}</span>
            <Isolate language={language} automatic={false}>
              <Bound
                name="low"
                shown={lowShown}
                factId={factId}
                onOpen={onOpen}
              />
              {'\u2013'}
              <Bound
                name="high"
                shown={highShown}
                factId={factId}
                onOpen={onOpen}
              />
            </Isolate>
          </span>
        ) : null}
      </bdi>
    ),
  };
}

export function FactChip(props: FactChipProps) {
  if (props.variant === 'operational') return <OperationalChip {...props} />;
  if (props.variant === 'input') {
    if ('kind' in props) {
      const formatted = formatFactValue(
        props.value,
        props.unit,
        props.language,
      );
      return (
        <span
          className="chip chip-input"
          data-fact-chip="input"
          data-kind="preset"
          data-record={props.recordId}
          data-state={formatted.ok ? 'ready' : 'error'}
        >
          <span className="chip-tag">
            {text(props.language, 'input.yours')}
          </span>
          {formatted.ok ? (
            <>
              <Isolate language={props.language} automatic={false}>
                {formatted.text}
              </Isolate>{' '}
              <span className="chip-unit">
                {unitWord(props.language, props.unit)}
              </span>
            </>
          ) : (
            <Words language={props.language} state="error" />
          )}
        </span>
      );
    }
    return (
      <NumericInput
        language={props.language}
        value={props.value}
        onChange={props.onChange}
        presets={props.presets}
      />
    );
  }
  if (props.variant === 'reference') {
    const formatted = formatFactValue(
      props.value,
      props.kind,
      props.language,
      'reference',
    );
    const date = props.kind.startsWith('calendar');
    if (!formatted.ok) {
      return (
        <span
          className="chip"
          data-fact-chip="reference"
          data-kind={props.kind}
          data-state="error"
        >
          <Words language={props.language} state="error" />
        </span>
      );
    }
    return (
      <span
        className="chip"
        data-fact-chip="reference"
        data-kind={props.kind}
        data-state="ready"
        data-record={props.recordId}
      >
        <Isolate
          language={props.language}
          automatic={date}
          opaque={props.kind === 'published_text'}
        >
          {formatted.text}
        </Isolate>
      </span>
    );
  }
  const resolution = props.registry.resolve(props.factId);
  const view =
    resolution.status === 'ready'
      ? readyBody(
          resolution,
          props.registry,
          props.language,
          props.factId,
          props.onOpen,
        )
      : {
          state:
            resolution.status === 'loading'
              ? 'loading'
              : resolution.status === 'no_data'
                ? 'no_data'
                : 'refused',
          label: text(
            props.language,
            resolution.status === 'loading'
              ? 'chip.loading'
              : resolution.status === 'no_data'
                ? 'chip.noData'
                : 'chip.refused',
          ),
          body: (
            <Words
              language={props.language}
              state={
                resolution.status === 'loading'
                  ? 'loading'
                  : resolution.status === 'no_data'
                    ? 'no_data'
                    : 'refused'
              }
            />
          ),
        };
  const size = props.variant === 'value' ? props.size : 'compact';
  if (props.figure) {
    return (
      <span
        className={props.figureCell ? 'chip figure-cell' : 'chip'}
        data-fact-chip={props.variant}
        data-fact-id={props.factId}
        data-state={view.state}
        data-size={size}
        data-figure="true"
      >
        {view.body}
      </span>
    );
  }
  return (
    <button
      type="button"
      className={props.figureCell ? 'chip figure-cell' : 'chip'}
      data-fact-chip={props.variant}
      data-fact-id={props.factId}
      data-state={view.state}
      data-size={size}
      aria-label={view.label}
      onClick={() => props.onOpen(props.factId)}
      onKeyDown={(event) => {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        props.onOpen(props.factId);
      }}
    >
      {view.body}
    </button>
  );
}

/** One operational object, no release identity and no arithmetic. */
function OperationalChip({
  meter,
  language,
  reason,
}: Extract<FactChipProps, { variant: 'operational' }>) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const quantity = (
    name: string,
    label: StringKey,
    value: number | string,
    unit: 'count' | 'usd' | 'published_text' | 'calendar_date',
  ) => {
    const formatted = formatFactValue(
      value,
      unit,
      language,
      unit === 'published_text' ? 'reference' : 'operational',
    );
    return (
      <span className="operational-quantity figure-cell" data-quantity={name}>
        <span className="chip-unit">{text(language, label)}</span>
        {formatted.ok ? (
          <Isolate language={language} automatic={unit === 'calendar_date'}>
            {formatted.text}
          </Isolate>
        ) : (
          <Words language={language} state="error" />
        )}
      </span>
    );
  };
  return (
    <div
      className="operational-meter"
      data-fact-chip={meter === null ? undefined : 'operational'}
      data-state={meter === null ? 'withheld' : 'ready'}
      onKeyDown={(event) => {
        if (event.key === 'Escape') setOpen(false);
      }}
      lang={language}
      dir={direction(language)}
    >
      {meter === null ? (
        <div className="chip">
          <span className="chip-withheld" />
          <span>
            {text(language, 'operational.unavailable').replace(
              '{reason}',
              text(language, `mapModes.${reason ?? 'network'}`),
            )}
          </span>
        </div>
      ) : (
        <>
          <button
            type="button"
            className="chip"
            aria-expanded={open}
            aria-controls={open ? panelId : undefined}
            onClick={() => setOpen(!open)}
          >
            <span className="operational-quantities">
              <span>{text(language, 'operational.title')}</span>
              {quantity(
                'requests',
                'operational.requests',
                meter.billable_requests,
                'count',
              )}
              {quantity(
                'limit',
                'operational.limit',
                meter.request_limit,
                'count',
              )}
              {quantity('spend', 'operational.spend', meter.spend_usd, 'usd')}
              {quantity(
                'ceiling',
                'operational.ceiling',
                meter.ceiling_usd,
                'usd',
              )}
              <span>{text(language, 'chip.open')}</span>
            </span>
          </button>
          {meter.warning ? (
            <p role="status">{text(language, 'operational.warning')}</p>
          ) : null}
          {open ? (
            <section
              id={panelId}
              role="region"
              aria-label={text(language, 'operational.title')}
            >
              <dl>
                <dt>{text(language, 'operational.source')}</dt>
                <dd>{text(language, 'operational.journal')}</dd>
                <dt>{text(language, 'operational.method')}</dt>
                <dd>
                  <bdi dir="ltr">Budget.meter</bdi>{' '}
                  {quantity(
                    'version',
                    'operational.version',
                    meter.method_version,
                    'published_text',
                  )}
                </dd>
                <dt>{text(language, 'operational.price')}</dt>
                <dd>
                  <bdi dir="ltr">EII_PHOTOREAL_PRICE_PER_THOUSAND</bdi>{' '}
                  {quantity(
                    'price',
                    'operational.priceUnit',
                    meter.price_per_thousand_usd,
                    'usd',
                  )}
                </dd>
                <dt>{text(language, 'operational.pricingPage')}</dt>
                <dd>{text(language, 'operational.toRecord')}</dd>
                <dt>{text(language, 'operational.defaultPriceRead')}</dt>
                <dd>
                  {quantity(
                    'retrieved',
                    'operational.retrieved',
                    meter.default_price_retrieved_on,
                    'calendar_date',
                  )}
                </dd>
                <dt>{text(language, 'operational.ceiling')}</dt>
                <dd>
                  <bdi dir="ltr">SPEND_CEILING_USD</bdi>{' '}
                  {quantity(
                    'ceiling',
                    'operational.ceiling',
                    meter.ceiling_usd,
                    'usd',
                  )}
                </dd>
              </dl>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
