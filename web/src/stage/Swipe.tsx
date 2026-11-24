/** Comparison alternative to a dragging divider; the baseline is never hidden. */
import { useState } from 'react';
import { FactChip } from '../facts/FactChip';
import type { FactRegistry } from '../facts/registry';
import { direction, text, type Language } from '../i18n';

export type ScenarioComparison = {
  kind: 'scenario';
  baselineFactId: string;
  changedFactId: string;
};
/** S2-T19 supplies these fixed view identities; no image is fabricated here. */
export type HistoryComparison = {
  kind: 'imagery-history';
  beforeViewId: string;
  afterViewId: string;
};
export type ComparisonInput = ScenarioComparison | HistoryComparison;

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
  const [selected, select] = useState<'baseline' | 'changed'>('baseline');
  if (comparison.kind !== 'scenario') return null;
  if (comparison.baselineFactId === comparison.changedFactId) return null;
  const states = [comparison.baselineFactId, comparison.changedFactId].map(
    (id) => registry.resolve(id),
  );
  if (
    states.some(
      (state) =>
        state.status !== 'ready' ||
        state.display !== 'value' ||
        state.binding.fact.geography.kind !== 'user_scenario' ||
        !state.binding.fact.input_classes.includes('user_input'),
    )
  )
    return null;
  return (
    <section
      className="scenario-comparison"
      dir={direction(language)}
      aria-label={text(language, 'comparison.label')}
    >
      <div className="comparison-controls">
        <button
          type="button"
          aria-pressed={selected === 'baseline'}
          onClick={() => select('baseline')}
        >
          {text(language, 'comparison.showBaseline')}
        </button>
        <button
          type="button"
          aria-pressed={selected === 'changed'}
          onClick={() => select('changed')}
        >
          {text(language, 'comparison.showChanged')}
        </button>
        <button type="button" onClick={() => select('baseline')}>
          {text(language, 'comparison.reset')}
        </button>
      </div>
      <div
        role="group"
        aria-label={text(language, 'comparison.baseline')}
        data-emphasis={selected === 'baseline'}
      >
        <p>{text(language, 'comparison.baseline')}</p>
        <FactChip
          variant="value"
          size="standard"
          language={language}
          factId={comparison.baselineFactId}
          registry={registry}
          onOpen={onOpen}
        />
      </div>
      <div
        role="group"
        aria-label={text(language, 'comparison.changed')}
        data-emphasis={selected === 'changed'}
      >
        <p>{text(language, 'comparison.changed')}</p>
        <FactChip
          variant="value"
          size="standard"
          language={language}
          factId={comparison.changedFactId}
          registry={registry}
          onOpen={onOpen}
        />
      </div>
    </section>
  );
}
