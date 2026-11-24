/**
 * Subject rules of document 03 section 9.1. A suppressed fact is judged
 * by the class it would otherwise have.
 */
export const FACT_KINDS = [
  'card_field',
  'employee_count',
  'rank',
  'fit',
  'estimate',
  'share',
  'score',
  'wage',
  'wage_bill',
  'labour_residence',
  'ordinary',
] as const;

export type FactKind = (typeof FACT_KINDS)[number];

export interface SubjectFact {
  provenance: string;
  kind: FactKind;
  underlyingClass: string | null;
  inList: boolean;
  stabilityPresent: boolean;
}

const SUBJECTS = new Set([
  'area',
  'place_public',
  'fdi_project',
  'register_company',
]);

const CLASS_LIST = ['public', 'synthetic', 'simulated'] as const;

const CLASSES = new Set<string>(CLASS_LIST);

const NAMED = new Set(['place_public', 'fdi_project']);

const COMPANY_REFUSED = new Set([
  'estimate',
  'share',
  'score',
  'wage',
  'wage_bill',
  'labour_residence',
]);

const METRIC_KIND: Record<string, FactKind> = {
  card: 'card_field',
  employee_count: 'employee_count',
  rank: 'rank',
  fit: 'fit',
  estimate: 'estimate',
  share: 'share',
  score: 'score',
  wage: 'wage',
  wage_bill: 'wage_bill',
};

export function factKind(metric: string): FactKind {
  return METRIC_KIND[metric] ?? 'ordinary';
}

export function subjectFactFromMetric(
  provenance: string,
  metric: string,
): SubjectFact {
  return {
    provenance,
    kind: factKind(metric),
    underlyingClass: null,
    inList: false,
    stabilityPresent: false,
  };
}

function rankAdmitted(fact: SubjectFact): boolean {
  return fact.inList && fact.stabilityPresent;
}

function namedAllows(kind: FactKind, provenance: string): boolean {
  if (provenance !== 'public') return false;
  return kind === 'ordinary';
}

function companyAllows(
  kind: FactKind,
  provenance: string,
  fact: SubjectFact,
): boolean {
  if (COMPANY_REFUSED.has(kind)) return false;
  if (provenance === 'simulated') return false;
  if (kind === 'employee_count') return provenance === 'synthetic';
  if (kind === 'card_field') return provenance === 'public';
  if (kind === 'rank' || kind === 'fit') {
    if (!rankAdmitted(fact)) return false;
    return provenance === 'public' || provenance === 'synthetic';
  }
  return false;
}

function areaAllows(kind: FactKind, fact: SubjectFact): boolean {
  if (kind === 'employee_count') return false;
  if (kind === 'rank' || kind === 'fit') return rankAdmitted(fact);
  return true;
}

function everyUnderlyingClass(subject: string, fact: SubjectFact): boolean {
  return CLASS_LIST.every((underlyingClass) =>
    subjectAllowsFact(subject, { ...fact, underlyingClass }),
  );
}

export function subjectAllowsFact(subject: string, fact: SubjectFact): boolean {
  if (!SUBJECTS.has(subject)) return false;
  let provenance = fact.provenance;
  if (provenance === 'suppressed') {
    if (fact.underlyingClass === null)
      return everyUnderlyingClass(subject, fact);
    if (!CLASSES.has(fact.underlyingClass)) return false;
    provenance = fact.underlyingClass;
  } else if (!CLASSES.has(provenance)) {
    return false;
  }
  const judged: SubjectFact = { ...fact, provenance };
  if (subject === 'area') return areaAllows(judged.kind, judged);
  if (NAMED.has(subject)) return namedAllows(judged.kind, provenance);
  return companyAllows(judged.kind, provenance, judged);
}
