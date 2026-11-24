import { direction, text, type Language } from '../i18n';
import {
  MODE_NAMES,
  selectedMode,
  type MapMode,
  type MapModes,
} from './map-modes';

export function MapModeSwitch({
  language,
  modes,
  selected,
  onChange,
}: {
  language: Language;
  modes: MapModes;
  selected: MapMode;
  onChange: (mode: MapMode) => void;
}) {
  const active = selectedMode(selected, modes);
  const visible = MODE_NAMES.filter(
    (mode) => mode !== 'satellite' || modes[mode].reason !== 'no_key',
  );
  return (
    <div
      className="map-mode-switch"
      role="radiogroup"
      aria-label={text(language, 'mapModes.label')}
      dir={direction(language)}
    >
      {visible.map((mode) => {
        const state = modes[mode];
        return (
          <div key={mode}>
            <button
              type="button"
              role="radio"
              aria-checked={active === mode}
              disabled={!state.available}
              aria-describedby={
                !state.available ? `map-reason-${mode}` : undefined
              }
              onClick={() => onChange(mode)}
              onKeyDown={(event) => {
                if (
                  !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(
                    event.key,
                  )
                )
                  return;
                event.preventDefault();
                const buttons = Array.from(
                  event.currentTarget
                    .closest('[role="radiogroup"]')
                    ?.querySelectorAll<HTMLButtonElement>(
                      'button:not(:disabled)',
                    ) ?? [],
                );
                const index = buttons.indexOf(event.currentTarget);
                const backward =
                  event.key === 'ArrowUp' ||
                  (event.key === 'ArrowLeft' && language === 'en') ||
                  (event.key === 'ArrowRight' && language === 'ar');
                const next =
                  buttons[
                    (index + (backward ? buttons.length - 1 : 1)) %
                      buttons.length
                  ];
                next?.focus();
                next?.click();
              }}
            >
              {text(language, `mapModes.${mode}`)}
            </button>
            {!state.available ? (
              <p id={`map-reason-${mode}`}>
                {text(language, `mapModes.${state.reason}`)}
              </p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
