/**
 * A typed user value or a closed preset. No fact, no source chain, no result.
 */
import type { Language, StringKey } from '../i18n';
import { text } from '../i18n';

export interface Preset {
  id: string;
  labelKey: StringKey;
  text: string;
}

export function NumericInput({
  language,
  value,
  onChange,
  presets,
}: {
  language: Language;
  value: string;
  onChange: (value: string) => void;
  presets: readonly Preset[];
}) {
  return (
    <span className="chip chip-input" data-fact-chip="input">
      <span className="chip-unit">{text(language, 'input.yours')}</span>
      <input
        className="chip-num"
        dir="ltr"
        lang="en"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={text(language, 'input.yours')}
      />
      {presets.map((preset) => (
        <button
          key={preset.id}
          type="button"
          className="chip"
          data-preset={preset.id}
          onClick={() => onChange(preset.text)}
        >
          {text(language, preset.labelKey)}
        </button>
      ))}
    </span>
  );
}
