import type { RefusalState } from '../api/refusal';
import { text, type Language } from '../i18n';

/** Diagnostic attributes carry closed codes only; visible words are catalogue-owned. */
export function RefusalNotice({
  refusal,
  language,
}: {
  refusal: RefusalState;
  language: Language;
}) {
  return (
    <p
      role="alert"
      data-http-status={refusal.http_status ?? 'no_response'}
      data-refusal-code={refusal.code}
      data-message-key={refusal.message_key}
      data-catalogue-key={refusal.catalogue_key}
    >
      {text(language, refusal.catalogue_key)}
    </p>
  );
}
