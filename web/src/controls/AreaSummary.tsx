/**
 * Shape, mode and cut-off, read beside the answer.
 * A drawn polygon says in words that it has no mode or cut-off.
 */
import { FactChip } from '../facts/FactChip';
import { text, type Language } from '../i18n';
import { reasonTextKey } from './present';
import { DISTANCE_PRESETS, DRIVE_PRESETS, WALK_PRESETS } from './presets';
import { useArea } from '../state/store';

const PRESETS = [...DISTANCE_PRESETS, ...WALK_PRESETS, ...DRIVE_PRESETS];

export function AreaSummary({ language }: { language: Language }) {
  const presented = useArea().presented;
  if (!presented?.showSummary) return null;
  if (presented.shapeKind === 'polygon') {
    return (
      <div data-part="area-summary" data-shape="polygon">
        <p>{text(language, 'draw.summary.polygon')}</p>
        <p data-part="no-mode">{text(language, 'draw.summary.noMode')}</p>
        {presented.showRefusal ? (
          <p data-part="summary-reason">
            {text(language, reasonTextKey(presented))}
          </p>
        ) : null}
      </div>
    );
  }
  const preset = PRESETS.find(
    (item) => item.mode === presented.mode && item.cutoff === presented.cutoff,
  );
  return (
    <div
      data-part="area-summary"
      data-shape={presented.shapeKind}
      data-mode={presented.mode ?? ''}
    >
      {presented.namedPlace ? (
        <p data-part="place-preset">{text(language, 'draw.summary.place')}</p>
      ) : null}
      <p>{text(language, kindLabel(presented.shapeKind))}</p>
      {presented.mode ? (
        <p data-part="mode-word">{text(language, modeLabel(presented.mode))}</p>
      ) : null}
      {presented.freeFlow ? (
        <p data-part="free-flow">{text(language, 'draw.freeFlow')}</p>
      ) : null}
      {preset ? (
        <FactChip
          variant="input"
          language={language}
          kind="preset"
          value={preset.value}
          unit={preset.unit}
          recordId={preset.recordId}
        />
      ) : null}
      {presented.showRefusal ? (
        <p data-part="summary-reason">
          {text(language, reasonTextKey(presented))}
        </p>
      ) : null}
    </div>
  );
}

function kindLabel(
  kind: 'polygon' | 'radius' | 'walk' | 'drive',
):
  | 'draw.summary.polygon'
  | 'draw.summary.radius'
  | 'draw.summary.walk'
  | 'draw.summary.drive' {
  if (kind === 'polygon') return 'draw.summary.polygon';
  if (kind === 'walk') return 'draw.summary.walk';
  if (kind === 'drive') return 'draw.summary.drive';
  return 'draw.summary.radius';
}

function modeLabel(
  mode: 'distance' | 'walk' | 'drive',
): 'draw.mode.distance' | 'draw.mode.walk' | 'draw.mode.drive' {
  if (mode === 'walk') return 'draw.mode.walk';
  if (mode === 'drive') return 'draw.mode.drive';
  return 'draw.mode.distance';
}
