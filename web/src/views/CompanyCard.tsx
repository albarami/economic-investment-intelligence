/**
 * Published card of one register company: the register's published fields
 * that this release carries, and nothing else. The employee count comes only
 * from the Protected company list; where the release does not hold it, the
 * card says so with its reason and never shows a zero (DAT-140).
 */
import type { ReactElement } from 'react';

import { text, type Language, type StringKey } from '../i18n';
import type {
  CompanyEmployeeCount,
  FcCompanyRow,
} from '../stage/layers/payload';
import { SegmentText } from '../stage/layers/Segments';

const CARD_FIELDS = new Set([
  'trade_name',
  'activity',
  'establishment_nationality',
]);
const FIELD_LABELS: Partial<Record<string, StringKey>> = {
  establishment_nationality: 'layers.company.nationality',
};
const ABSENT_TEXT: Record<CompanyEmployeeCount['reason_key'], StringKey> = {
  protected_not_in_public_release: 'layers.company.employees_absent',
};

export function CompanyCard({
  row,
  language,
  employeeCount,
}: {
  row: Pick<FcCompanyRow, 'row_id' | 'fields'>;
  language: Language;
  employeeCount?: CompanyEmployeeCount;
}): ReactElement {
  return (
    <section data-part="company-card" data-row={row.row_id}>
      {row.fields.map((field) => {
        if (!CARD_FIELDS.has(field.key)) return null;
        const label = FIELD_LABELS[field.key];
        return (
          <p key={field.key} data-field={field.key}>
            {label ? (
              <span data-label={field.key}>{text(language, label)} </span>
            ) : null}
            {field.segments ? (
              <SegmentText segments={field.segments} language={language} />
            ) : (
              <bdi>{field.text}</bdi>
            )}
          </p>
        );
      })}
      {employeeCount ? (
        <p
          data-field="employee_count"
          data-state={employeeCount.state}
          data-reason={employeeCount.reason_key}
        >
          {text(language, ABSENT_TEXT[employeeCount.reason_key])}
        </p>
      ) : null}
    </section>
  );
}
