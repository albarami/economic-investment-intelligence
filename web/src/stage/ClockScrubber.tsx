/** Direct input has no playback, including when reduced motion is requested. */
import { FactChip } from '../facts/FactChip';
import { direction, text, type Language } from '../i18n';
import { clockDay, clockTimestamp } from './clock';

export function ClockScrubber({
  language,
  dayBasis,
  fraction,
  onFractionChange,
  onChange,
}: {
  language: Language;
  dayBasis?: string;
  fraction: string;
  onFractionChange: (fraction: string) => void;
  onChange: (timestamp: number) => void;
}) {
  const day = clockDay(dayBasis);
  const change = (value: string) => {
    onFractionChange(value);
    if (value.trim() === '') return;
    const timestamp = clockTimestamp(day, Number(value));
    if (timestamp !== null) onChange(timestamp);
  };
  return (
    <section
      className="clock-control"
      data-clock
      data-animation="none"
      dir={direction(language)}
      aria-label={text(language, 'clock.label')}
    >
      <p>{text(language, 'clock.label')}</p>
      <FactChip
        variant="reference"
        language={language}
        kind="calendar_date"
        value={day}
        recordId={day}
      />
      <input
        type="range"
        min="0"
        max="1"
        step="any"
        value={fraction}
        aria-label={text(language, 'clock.label')}
        onChange={(event) => change(event.target.value)}
      />
      <p>{text(language, 'clock.input')}</p>
      <FactChip
        variant="input"
        language={language}
        value={fraction}
        onChange={change}
        presets={[]}
      />
    </section>
  );
}
