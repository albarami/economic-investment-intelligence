/**
 * The answer column. A failed gate draws the application default only.
 */
import { FactChip } from '../facts/FactChip';
import type { FactRegistry } from '../facts/registry';
import { direction, text, type Language } from '../i18n';
import { answerAccepted, fragmentField, type AnswerDraft } from './catalogue';

export function Brief({
  id,
  language,
  registry,
  draft,
  onOpen,
  inert,
}: {
  id?: string;
  language: Language;
  registry: FactRegistry | null;
  draft: AnswerDraft | null;
  onOpen: (factId: string) => void;
  inert?: boolean;
}) {
  const accepted =
    draft !== null && registry !== null && answerAccepted(draft, registry);
  const headline =
    fragmentField(
      'foundation_headline',
      language === 'ar' ? 'template_ar' : 'template_en',
    ) ?? '';
  const lead =
    fragmentField(
      'foundation_decision',
      language === 'ar' ? 'lead_ar' : 'lead_en',
    ) ?? '';
  return (
    <section
      id={id}
      tabIndex={-1}
      className="brief"
      lang={language}
      dir={direction(language)}
      aria-label={text(language, 'shell.brief')}
      data-state={accepted ? 'shown' : 'default'}
      inert={inert ? true : undefined}
    >
      <h1 data-fragment="foundation_headline">{headline}</h1>
      <p data-component="foundation_note">{lead}</p>
      {accepted && registry && draft ? (
        <div data-part="slots">
          {draft.slots.map((slot) => (
            <FactChip
              key={slot.factId}
              variant="value"
              size="standard"
              factId={slot.factId}
              registry={registry}
              language={language}
              onOpen={onOpen}
            />
          ))}
        </div>
      ) : null}
    </section>
  );
}
