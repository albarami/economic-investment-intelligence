/** Select a returned observation; the existing card owns every disclosure level. */
import { useState } from 'react';
import {
  PublicContextCard,
  type ContextPayload,
} from '../cards/PublicContextCard';
import { contextFamilies } from '../cards/public-context-contract';
import { fragmentField } from '../brief/catalogue';
import { FactChip } from '../facts/FactChip';
import type { FactRegistry } from '../facts/registry';
import { text, type Language } from '../i18n';

export function ContextCards({
  cards,
  registry,
  language,
  onOpen,
  chosenArea = false,
}: {
  cards: readonly ContextPayload[];
  registry: FactRegistry;
  language: Language;
  onOpen: (id: string) => void;
  /** The story's area cards are for the chosen area; a named-place card is not. */
  chosenArea?: boolean;
}) {
  const [selection, setSelection] = useState<Record<string, string>>({});
  const [active, setActive] = useState('');
  const available = Object.keys(contextFamilies).filter((family) =>
    cards.some((card) => card.family === family),
  );
  const shown = available.includes(active) ? active : available[0];
  return (
    <>
      <div
        className="context-tabs"
        role="group"
        aria-label={text(language, 'story.cards')}
      >
        {available.map((family) => (
          <button
            type="button"
            key={family}
            data-context-tab={family}
            aria-pressed={shown === family}
            onClick={() => setActive(family)}
          >
            {fragmentField(
              family,
              language === 'ar' ? 'template_ar' : 'template_en',
            )}
          </button>
        ))}
      </div>
      {Object.keys(contextFamilies).map((family) => {
        const options = cards.filter((card) => card.family === family);
        const selected =
          options.find(
            (card) =>
              card.state === 'ready' && card.factId === selection[family],
          ) ?? options[0];
        if (!selected) return null;
        return (
          <div
            key={family}
            data-context-deck={family}
            hidden={family !== shown}
          >
            {options.length > 1 ? (
              <details className="context-options">
                <summary>
                  {fragmentField(
                    family,
                    language === 'ar' ? 'template_ar' : 'template_en',
                  )}
                </summary>
                {options.map((option) =>
                  option.state === 'ready' ? (
                    <button
                      type="button"
                      key={option.factId}
                      data-observation={option.factId}
                      aria-pressed={option === selected}
                      onClick={() =>
                        setSelection({ ...selection, [family]: option.factId })
                      }
                    >
                      {option.family === 'population_age_sex' &&
                      option.ageBand ? (
                        <FactChip
                          variant="reference"
                          language={language}
                          kind="published_text"
                          value={option.ageBand}
                          recordId={option.factId}
                        />
                      ) : null}
                      {option.family === 'venue_busyness' ? (
                        <>
                          <span>
                            {fragmentField(
                              'context_' + option.day,
                              language === 'ar' ? 'template_ar' : 'template_en',
                            )}
                          </span>
                          <FactChip
                            variant="reference"
                            language={language}
                            kind="published_text"
                            value={option.hour}
                            recordId={option.factId}
                          />
                        </>
                      ) : null}
                    </button>
                  ) : null,
                )}
              </details>
            ) : null}
            <PublicContextCard
              language={language}
              registry={registry}
              payload={selected}
              onOpen={onOpen}
            />
            {chosenArea && family !== 'venue_busyness' ? (
              <p className="story-caption" data-part="chosen-area">
                {text(language, 'story.chosenArea')}
              </p>
            ) : null}
          </div>
        );
      })}
    </>
  );
}
