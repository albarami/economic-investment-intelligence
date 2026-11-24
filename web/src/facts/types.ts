/** Fact, lineage and source shapes from document 03 section "9. The fact object". */

export type Language = 'en' | 'ar';

export type Provenance = 'public' | 'synthetic' | 'simulated' | 'suppressed';

export type InputClass = 'public' | 'synthetic' | 'simulated' | 'user_input';

export type EvidenceStatus = 'observed' | 'inferred' | 'still_to_test';

export type Reliability = 'standard' | 'low_count' | 'not_applicable';

export type SourceKind =
  | 'public_dataset'
  | 'public_document'
  | 'reviewed_config'
  | 'synthetic_feed'
  | 'simulation_output';

export type GeographyKind =
  'release_units' | 'public' | 'national' | 'user_scenario' | 'area_shape';

export interface Geography {
  kind: GeographyKind;
  unit_ids?: string[];
  public_code?: string;
  area_id?: string;
  apportioned_from?: string;
}

export interface Fact {
  fact_id: string;
  value: number | string | null;
  unit: string;
  period: string;
  geography: Geography;
  provenance: Provenance;
  input_classes: InputClass[];
  evidence_status: EvidenceStatus;
  reliability: Reliability;
  coverage_keys: string[];
  caveat_keys: string[];
  label_en: string;
  label_ar: string;
  lineage_ref: string;
  release_id: string;
}

export interface SourceRow {
  sourceId: string;
  kind: SourceKind;
  inputClass: InputClass;
  publisher: string;
  datasetOrPage: string;
  licenceOrTerms: string;
  retrievalDate: string;
  sha256: string;
}

export interface LineageRow {
  /** HTTP chain request identity; row citations remain bound to this Fact. */
  factId?: string;
  lineageId: string;
  releaseId: string;
  tableName: string;
  method: string;
  methodVersion: string;
  sourceIds: string[];
  inputClasses: InputClass[];
  /** C37 row citation; the source receipt date remains unchanged. */
  rowRetrievalDate?: string;
  providerUpdatedOn?: string | null;
}

export interface ReleaseRecord {
  releaseId: string;
}

export interface ReleaseTable {
  releaseId: string;
  tableName: string;
}

export type Presentation =
  | 'ordinary'
  | 'estimated_count'
  | 'forecast'
  | 'site_estimate'
  | 'base_rate'
  | 'change';

/** Companion identifiers sit beside the fact. They are not fact properties. */
export interface FactBinding {
  fact: Fact;
  metricKey: string;
  presentation: Presentation;
  /** Fixed-reader selection identity, carried unchanged beside the Fact. */
  qualifiers?: Readonly<{
    day_of_week?: string;
    hour?: string;
    age_band?: string;
    sex?: 'female' | 'male' | 'none';
  }>;
  rangeLowId?: string;
  rangeHighId?: string;
  intervalLowId?: string;
  intervalHighId?: string;
  backtestErrorId?: string;
  estimateLowId?: string;
  estimateHighId?: string;
  numeratorId?: string;
  denominatorId?: string;
  periodId?: string;
  stabilityId?: string;
  directionId?: string;
  loading?: boolean;
  noData?: boolean;
}

export interface RegistryInput {
  facts: readonly FactBinding[];
  releases: readonly ReleaseRecord[];
  tables: readonly ReleaseTable[];
  lineages: readonly LineageRow[];
  sources: readonly SourceRow[];
}

export type MissingLink =
  | 'fact'
  | 'release'
  | 'table'
  | 'lineage'
  | 'method'
  | 'method_version'
  | 'source'
  | 'publisher'
  | 'dataset_or_page'
  | 'licence_or_terms'
  | 'retrieval_date'
  | 'hash'
  | 'release_identity'
  | 'input_class_source'
  | 'source_kind'
  | 'provenance_class'
  | 'companion';

export type ChainDisplay = 'value' | 'withheld';

export type Resolution =
  | { status: 'loading' }
  | { status: 'no_data' }
  | { status: 'refused'; missing: MissingLink }
  | {
      status: 'ready';
      binding: FactBinding;
      lineage: LineageRow;
      sources: SourceRow[];
      table: ReleaseTable;
      display: ChainDisplay;
    };
