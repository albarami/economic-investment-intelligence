/** Comparison alternative to a dragging divider; the baseline is never hidden. */
import { useState, type ReactElement } from 'react';
import { FactChip } from '../facts/FactChip';
import type { FactRegistry } from '../facts/registry';
import { direction, text, type Language, type StringKey } from '../i18n';
import { SegmentText } from './layers/Segments';
import type { TextSegment } from './layers/payload';
import {
  calendarAccepted,
  gisSourceLine,
  type GisSourceLineInput,
} from './map-credits';

export type ScenarioComparison = {
  kind: 'scenario';
  baselineFactId: string;
  changedFactId: string;
};
/**
 * One fixed view of S2-T19's imagery history: its capture date and its fixed
 * local picture, a same-origin path served by the application itself.
 */
export type HistoryView = { viewId: string; capturedOn: string; image: string };
export type HistoryComparison = {
  kind: 'imagery-history';
  beforeViewId: string;
  afterViewId: string;
  /** The closed list of fixed views S2-T19 supplies. */
  views: readonly HistoryView[];
  source: GisSourceLineInput;
};
export type ComparisonInput = ScenarioComparison | HistoryComparison;

export type SwipeStates =
  | { kind: 'scenario'; first: string; second: string }
  | {
      kind: 'imagery-history';
      first: HistoryView;
      second: HistoryView;
      sourceLine: TextSegment[];
    }
  | {
      kind: 'refused';
      reason:
        | 'swipe_states_same'
        | 'scenario_state_untested'
        | 'history_view_unknown'
        | 'history_view_date_invalid'
        | 'history_view_image_invalid'
        | 'gis_source_line_absent'
        | 'gis_retrieval_date_invalid'
        | 'gis_numeral_outside_chip'
        | 'gis_reference_invalid';
    };

/** A same-origin picture path: no scheme, no host, no parent-folder step. */
const LOCAL_IMAGE =
  /^\/(?:[A-Za-z0-9_-]+[./])*[A-Za-z0-9_-]+\.(?:png|jpe?g|webp)$/;

/** The two states the swipe may show, or the closed reason it shows none. */
export function swipeStates(
  comparison: ComparisonInput,
  registry: FactRegistry,
): SwipeStates {
  if (comparison.kind === 'scenario') {
    const { baselineFactId: first, changedFactId: second } = comparison;
    if (first === second) {
      return { kind: 'refused', reason: 'swipe_states_same' };
    }
    const untested = [first, second].some((id) => {
      const state = registry.resolve(id);
      return (
        state.status !== 'ready' ||
        state.display !== 'value' ||
        state.binding.fact.geography.kind !== 'user_scenario' ||
        !state.binding.fact.input_classes.includes('user_input')
      );
    });
    if (untested) return { kind: 'refused', reason: 'scenario_state_untested' };
    return { kind: 'scenario', first, second };
  }
  if (comparison.beforeViewId === comparison.afterViewId) {
    return { kind: 'refused', reason: 'swipe_states_same' };
  }
  const find = (id: string) => comparison.views.find((v) => v.viewId === id);
  const first = find(comparison.beforeViewId);
  const second = find(comparison.afterViewId);
  if (!first || !second) {
    return { kind: 'refused', reason: 'history_view_unknown' };
  }
  if (
    ![first, second].every((view) =>
      calendarAccepted(view.capturedOn, 'calendar_date'),
    )
  ) {
    return { kind: 'refused', reason: 'history_view_date_invalid' };
  }
  if (![first, second].every((view) => LOCAL_IMAGE.test(view.image))) {
    return { kind: 'refused', reason: 'history_view_image_invalid' };
  }
  if (first.image === second.image) {
    return { kind: 'refused', reason: 'swipe_states_same' };
  }
  const line = gisSourceLine(comparison.source);
  if (line.kind === 'refused') return line;
  return { kind: 'imagery-history', first, second, sourceLine: line.segments };
}

const KEYS = {
  scenario: {
    label: 'comparison.label',
    first: 'comparison.baseline',
    second: 'comparison.changed',
    showFirst: 'comparison.showBaseline',
    showSecond: 'comparison.showChanged',
  },
  'imagery-history': {
    label: 'comparison.history.label',
    first: 'comparison.history.before',
    second: 'comparison.history.after',
    showFirst: 'comparison.history.showBefore',
    showSecond: 'comparison.history.showAfter',
  },
} as const satisfies Record<string, Record<string, StringKey>>;

export function Swipe({
  language,
  comparison,
  registry,
  onOpen,
}: {
  language: Language;
  comparison: ComparisonInput;
  registry: FactRegistry;
  onOpen: (id: string) => void;
}) {
  const [selected, select] = useState<'first' | 'second'>('first');
  const states = swipeStates(comparison, registry);
  if (states.kind === 'refused') return null;
  const keys = KEYS[states.kind];
  const side = (which: 'first' | 'second'): ReactElement =>
    states.kind === 'scenario' ? (
      <FactChip
        variant="value"
        size="standard"
        language={language}
        factId={states[which]}
        registry={registry}
        onOpen={onOpen}
      />
    ) : (
      <>
        <img
          src={states[which].image}
          alt={text(language, keys[which])}
          data-history-image={states[which].viewId}
        />
        <FactChip
          variant="reference"
          language={language}
          kind="calendar_date"
          value={states[which].capturedOn}
          recordId={states[which].viewId}
        />
      </>
    );
  return (
    <section
      className="scenario-comparison"
      dir={direction(language)}
      aria-label={text(language, keys.label)}
    >
      <div className="comparison-controls">
        <button
          type="button"
          aria-pressed={selected === 'first'}
          onClick={() => select('first')}
        >
          {text(language, keys.showFirst)}
        </button>
        <button
          type="button"
          aria-pressed={selected === 'second'}
          onClick={() => select('second')}
        >
          {text(language, keys.showSecond)}
        </button>
        <button type="button" onClick={() => select('first')}>
          {text(language, 'comparison.reset')}
        </button>
      </div>
      {(['first', 'second'] as const).map((which) => (
        <div
          key={which}
          role="group"
          aria-label={text(language, keys[which])}
          data-emphasis={selected === which}
        >
          <p>{text(language, keys[which])}</p>
          {side(which)}
        </div>
      ))}
      {states.kind === 'imagery-history' ? (
        <p data-credit="gis_imagery_history">
          <SegmentText segments={states.sourceLine} language={language} />
        </p>
      ) : null}
    </section>
  );
}
