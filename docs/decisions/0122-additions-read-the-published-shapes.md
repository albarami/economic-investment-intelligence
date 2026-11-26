# Decision 0122: Additions read the published shapes

| | |
|---|---|
| Status | Proposed |
| Date | 2026-11-25 |
| Owner | The owner |
| Amends | Document 03 section 7.3, Public table columns; S2-T11 additions parsing. |
| Purpose | Admit the source shapes supplied by the lead without rounding measures or guessing countries. |
| Read first | Document 03 section 7.3; `additions/industry.py`, `additions/build.py` and `review/additions_industry.yaml` under `custodian/src/eii_custodian/publicdata/` and `custodian/publicdata/`. |

## Context

The S2-ADDF lead sweep supplies column names and label inventories, rather than
public measure values. Fixtures remain invented; this change reads no real
cache and makes no network request. No live completeness claim follows from
these fixture tests.

## Decision

1. **Activity names stay source-only.** Declare the English and Arabic activity
   name columns for all seven `est_size_act` slugs in their closed `fields`
   lists. Business services uses `economic_activity` and `lnsht_lqtsdy`;
   transport uses `main_economic_activity` and `main_economic_activity_ar`;
   the other five use `main_economic_activity` and `lnsht_lqtsdy_lry_ysy`.
   The existing `pub_establishment_size` contract has no name column: these
   declared fields remain in the selected source snapshot with their activity
   code, and are not released. Every undeclared column still refuses
   `unknown_source_field`; every missing declared column still refuses
   `source_field_absent`. Unconfirmed indicators and missing size classes
   keep their existing refusal or counted omission.
2. **Manufacturing precision only.** Set `pub_manufacturing.value` to
   `DECIMAL(18,6)` and its two manufacturing layouts' parser scale to six.
   Other additions tables keep their existing scales. Accepted values are
   exact: no measure is rounded. A nonzero seventh decimal place refuses
   `measure_precision`; values outside the column's integer capacity refuse
   `value_out_of_column` at assembly. Units, cumulative investment semantics,
   integral-count checks, keys and lineage are unchanged.
3. **Closed country dispositions and certificate aliases.** Add the regional
   labels Caribbean, Central Africa, New Guinea and Timor to
   `regions_not_countries`; they retain the counted `region_not_country`
   outcome. The certificate parser omits labels in the new closed
   `country_labels_withheld` list, counting `country_label_withheld` once per
   otherwise eligible source row: Antigua, Congo, Grand Cayman Islands,
   Kosovo, Macedonia, Mordovia, NOT STATED, Pretoria, Scotland, Tahiti, Taipei,
   Tasmania and Trinidad. Together with the four regions, these are seventeen
   withheld or regional dispositions. These labels receive no country crosswalk row:
   none supplies an unambiguous whole ISO country in the available review
   reference. The exact published label Bosnia maps to BIH, the sole
   Bosnia and Herzegovina row of the committed reference; it is not withheld.
   Other incomplete names are not silently expanded, and no Kosovo ISO code
   is invented. These conservative dispositions remain proposals for
   independent review; labels absent from all applicable lists still refuse
   `country_unreviewed`, with exact spelling and no normalization. The new
   closed `certificate_type_aliases` map binds the four published spellings
   to their already-listed canonical types. Add Certificate for Agricultural
   and Animal Products as its own listed type. Alias targets must be listed
   types; unknown aliases refuse `unknown_certificate_type`. Aliasing happens
   before key validation, so repeated canonical series keys still refuse
   `duplicate_key`. Missing measures and unpublished certificate tokens keep
   their existing counted omissions.

## Evidence and limits

Invented-fixture tests in `test_additions_industry.py` and
`test_additions_build.py` exercise the supplied field names, exact decimal
storage, alias collisions, hostile alias-map leaves and counted omissions.
PROGRESS.md and the task return record actual exits and guard-deletion proofs.
The ISO reference is the committed `custodian/publicdata/review/country_iso3.csv`;
no outside geographic source was fetched. Withholding is deliberately
conservative where the label's intended country cannot be established.

## What would change it

An independently reviewed source statement identifying one complete ISO
country may justify a new exact crosswalk row. A finer manufacturing value
requires a separately reviewed contract change; it is never rounded to fit.
