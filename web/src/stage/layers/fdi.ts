/** The FDI list filters are a closed set of four. */

export const FDI_FILTERS = [
  'sector',
  'source_country',
  'period',
  'stated_location',
] as const;

/** Published word fields of document 03 `fdi_projects`, in column order. */
export const FDI_WORD_FIELDS = [
  'project_key',
  'company',
  'source_country',
  'source_country_iso3',
  'sector',
  'sub_sector',
  'business_function',
  'project_type',
  'capex_unit',
  'location_text',
  'municipality_code',
  'place_key',
  'project_id',
  'project_year',
  'project_month',
  'capex_currency',
  'tags',
  'tech_level_id',
  'city_id',
  'world_region_id',
  'src_country_id',
  'fdi_sector_id',
  'src_world_region_id',
  'src_state_id',
  'function_id',
  'src_city_id',
  'sector_id',
  'state_id',
  'country_id',
  'parent_company_id',
  'project_type_id',
  'src_state_name',
  'freezone_name',
  'city_name',
  'state_name',
  'src_world_region_name',
  'country_name',
  'description',
  'parent_company_name',
  'naics_sub_sector_name',
  'src_city_name',
  'state_abbr',
  'world_region_name',
  'parent_company_website',
  'fdi_sector_name',
  'province',
] as const;

export type FdiWordField = (typeof FDI_WORD_FIELDS)[number];

/** The contract columns that arrive as Fact chips rather than words. */
export const FDI_FACT_FIELDS = [
  'capex_value',
  'jobs',
  'announced',
  'lat',
  'lng',
] as const;

/** Every column of document 03 `fdi_projects`; none is dropped at loading. */
export const FDI_CONTRACT_FIELDS: readonly string[] = [
  ...FDI_WORD_FIELDS,
  ...FDI_FACT_FIELDS,
];

export type FdiFilter = (typeof FDI_FILTERS)[number];

export function fdiFilterAllowed(key: string): key is FdiFilter {
  return (FDI_FILTERS as readonly string[]).includes(key);
}
