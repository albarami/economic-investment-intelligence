export type ClassKey = 'public' | 'synthetic' | 'simulated' | 'suppressed';
export type UnitKind = 'count' | 'share';
export type SourceInput =
  | {
      provenance: 'public';
      publisher: string;
      dataset: string;
      source: string;
      licence: string;
      retrieved: string;
      sha256: string;
    }
  | {
      provenance: 'synthetic' | 'simulated';
      origin: 'synthetic' | 'simulated';
      dataset: string;
      generator: { name: string; version: string };
      sha256: string;
    };
export type ChainRecord = {
  table: string;
  method: string;
  method_version: string;
  source: string;
  generator: { name: string; version: string };
  inputs: SourceInput[];
};
export type FactRecord = {
  id: string;
  value: number;
  unit: UnitKind;
  unit_key: string;
  provenance: ClassKey;
  origin?: 'synthetic' | 'simulated';
  input_classes: ClassKey[];
  geography_key: string;
  chain: ChainRecord | null;
};
export type FactView = {
  id: string;
  value: number;
  unit: UnitKind;
  unitKey: string;
  provenance: ClassKey;
  origin?: 'synthetic' | 'simulated';
  inputClasses: ClassKey[];
  geographyKey: string;
  chain: ChainRecord | null;
};
export type FirmRecord = {
  name: string;
  activity: string;
  size_band: string;
  cell: string;
};
export type EstablishmentRecord = {
  row_key: string;
  name_ar: string;
  name_en: string;
  establishment_type: string;
  establishment_subtype: string;
  legal_form: string;
  business_type: string;
  business_category: string;
  classification: string;
  registration_status: string;
  registration_issue_date: string;
  registration_expiry_date: string;
  licence_status: string;
  licence_issue_date: string;
  licence_expiry_date: string;
  branches: number | null;
  employees: number | null;
  municipality: string;
  zone: string;
  lon: number;
  lat: number;
};
export type Release = {
  origin?: 'synthetic';
  generator?: { name: string; version: string };
  coverage: 'not_measured' | 'available';
  release_id: string;
  basemap: { present: true; url: string } | { present: false; missing: string };
  buildings: { present: true; url: string } | { present: false };
  district: { en: string; ar: string; lon: number; lat: number } | null;
  places: { en: string; ar: string; lon: number; lat: number }[];
  district_labels: {
    en: string;
    ar: string;
    lon: number;
    lat: number;
    min_zoom: number;
  }[];
  // Round 5g, finding 22: the date of the register count, YYYY-MM-DD.
  period: string;
  layer: {
    id: string;
    unit_key: string;
    provenance: ClassKey;
    origin?: 'synthetic' | 'simulated';
    generator?: { name: string; version: string };
    resolution: number;
    breaks: number[];
    cells: [string, number, number][];
  };
  facts: FactRecord[];
  firms: FirmRecord[];
  establishments: EstablishmentRecord[];
};
export const RELEASE_ID: string;
export const CLASSES: ClassKey[];
export const UNITS: UnitKind[];
export const FIRM_KEYS: string[];
export function validateRelease(release: unknown): Release;
export function factView(fact: FactRecord): FactView;
export function serialiseRelease(release: Release): string;
export const SHARE_FROM_STEP: number;
