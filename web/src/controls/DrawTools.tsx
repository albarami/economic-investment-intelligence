/**
 * Tool group, chips and the refusal panel. A sibling of the Stage,
 * under the interface direction. Logical properties only.
 */
import { FactChip } from '../facts/FactChip';
import { direction, text, type Language } from '../i18n';
import { reasonTextKey } from './present';
import { presetsFor, type AreaPreset } from './presets';
import {
  beginUsePointer,
  dispatch,
  submitUseClick,
  submitUsePointer,
  usePort,
} from '../state/area-actions';
import { useArea } from '../state/store';

const TOOLS = ['polygon', 'radius', 'travel'] as const;

export function DrawTools({ language }: { language: Language }) {
  const port = usePort();
  const area = useArea();
  if (!port) {
    return (
      <div
        className="draw-tools"
        data-part="draw-tools"
        lang={language}
        dir={direction(language)}
      >
        <p data-part="draw-unavailable">{text(language, 'draw.unavailable')}</p>
      </div>
    );
  }
  const session = area.session;
  const presented = area.presented;
  const presets = presetsFor(session.tool);
  return (
    <div
      className="draw-tools"
      data-part="draw-tools"
      lang={language}
      dir={direction(language)}
    >
      <div role="group" aria-label={text(language, 'draw.tools')}>
        {TOOLS.map((tool) => (
          <button
            key={tool}
            type="button"
            className="draw-tool"
            data-tool={tool}
            aria-pressed={session.tool === tool}
            onClick={() => dispatch({ type: 'select-tool', tool })}
          >
            {text(language, toolLabel(tool))}
          </button>
        ))}
      </div>
      {session.selectedKnob !== null ? (
        <p role="status">{text(language, 'draw.moveVertex')}</p>
      ) : null}
      {session.tool === 'travel' ? (
        <p data-part="mode-heading">{text(language, 'draw.mode.walk')}</p>
      ) : null}
      <PresetRow
        language={language}
        presets={session.tool === 'travel' ? presets.slice(0, 3) : presets}
        mode={session.mode}
        cutoff={session.cutoff}
      />
      {session.tool === 'travel' ? (
        <>
          <p data-part="mode-heading">{text(language, 'draw.mode.drive')}</p>
          <PresetRow
            language={language}
            presets={presets.slice(3)}
            mode={session.mode}
            cutoff={session.cutoff}
          />
        </>
      ) : null}
      <button
        type="button"
        className="draw-tool"
        data-part="use-area"
        onPointerDown={() => beginUsePointer()}
        onPointerUp={(event) => {
          if (event.pointerType !== 'mouse') event.preventDefault();
          submitUsePointer(event.pointerType);
        }}
        onClick={(event) => submitUseClick(event.detail)}
      >
        {text(language, 'draw.use')}
      </button>
      {session.phase === 'drawing' || session.phase === 'editing' ? (
        <button
          type="button"
          className="draw-tool"
          data-part="cancel-area"
          onClick={() => dispatch({ type: 'escape' })}
        >
          {text(language, 'draw.cancel')}
        </button>
      ) : null}
      {presented?.showRefusal ? (
        <div data-part="refusal" data-status={presented.status}>
          <p>{text(language, reasonTextKey(presented))}</p>
          <PresetRow
            language={language}
            presets={presets}
            mode={session.mode}
            cutoff={session.cutoff}
          />
        </div>
      ) : null}
    </div>
  );
}

function PresetRow({
  language,
  presets,
  mode,
  cutoff,
}: {
  language: Language;
  presets: readonly AreaPreset[];
  mode: AreaPreset['mode'] | null;
  cutoff: number | null;
}) {
  if (presets.length === 0) return null;
  return (
    <div data-part="presets">
      {presets.map((preset) => (
        <button
          key={preset.id}
          type="button"
          className="draw-preset"
          data-part="preset"
          data-preset={preset.id}
          aria-pressed={mode === preset.mode && cutoff === preset.cutoff}
          onClick={() =>
            dispatch({
              type: 'preset',
              mode: preset.mode,
              cutoff: preset.cutoff,
            })
          }
        >
          <FactChip
            variant="input"
            language={language}
            kind="preset"
            value={preset.value}
            unit={preset.unit}
            recordId={preset.recordId}
          />
        </button>
      ))}
    </div>
  );
}

function toolLabel(
  tool: (typeof TOOLS)[number],
): 'draw.polygon' | 'draw.radius' | 'draw.travel' {
  if (tool === 'polygon') return 'draw.polygon';
  if (tool === 'radius') return 'draw.radius';
  return 'draw.travel';
}
