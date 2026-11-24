import { fragmentField } from '../brief/catalogue';
import { text, type Language } from '../i18n';

/** Five descriptors, only supplied journeys become actions (decision 0042 item 7). */
export const JOURNEYS = [
  { key: 'site', provided: true },
  { key: 'suppliers', provided: false },
  { key: 'talent', provided: false },
  { key: 'competition', provided: false },
  { key: 'forecasts', provided: false },
] as const;

export function PublicOpening({
  language,
  onStart,
}: {
  language: Language;
  onStart: () => void;
}) {
  return (
    <section className="public-opening" data-scene="opening">
      <h1>{text(language, 'opening.question')}</h1>
      <nav aria-label={text(language, 'opening.journeys')}>
        {JOURNEYS.filter((journey) => journey.provided).map((journey) => (
          <button
            type="button"
            key={journey.key}
            data-journey={journey.key}
            onClick={onStart}
          >
            {text(language, 'opening.action.site')}
          </button>
        ))}
        <button type="button" data-action="guided-story" onClick={onStart}>
          {text(language, 'opening.guided')}
        </button>
      </nav>
      <p data-fragment="opening_electricity_unavailable">
        {fragmentField(
          'opening_electricity_unavailable',
          language === 'ar' ? 'template_ar' : 'template_en',
        )}
      </p>
    </section>
  );
}
