# 0040 — Public trade and benchmark sources, and every held public table in use

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-15 |
| Owner | albarami |
| Decided by | The owner, in the notes of 2026-11-15, 20:35 to 20:43 |
| Amends | Document 04 source scope and PUB-90; rule 10's anchor sentence and Status in AGENTS.md and CLAUDE.md; decision 0022 item 2's calibration priority; decision 0038 items 4 and 8 and inventory rows 1, 4, 12, 14 and 16; the pack passages below |
| Purpose | Use the held public tables, add free trade and benchmark sources, and name their fetch, method and question work without claiming implementation. |
| Read first | Document 04, Source registry; decisions 0022, 0023, 0026, 0034, 0036, 0037 and 0038; AGENTS.md rules 5, 10, 14, 19, 25 and 46 |

## Context

The owner's notes ask for the public tables already in the pack to lead where they publish a calibration target, for trade/export sources within the free allowance, and for wider questions and measured methods. The source-page descriptions in the owner-relayed note are leads, not page verification. This record reads repository documents and registry metadata only: no source, cache, key, private calibration or custodian record was read or fetched. A declared product use is design scope, not evidence of implemented consumption.

## Decision

1. **Comtrade enters version 1.** UN Comtrade is a Public source, no longer a later benchmark. Use the free plan only: 500 calls a day and 100,000 records per call; no background Deliver, Bulk or Async. Use the no-key Public API, limited to 500 records per call, for availability, releases, metadata, reference lists and exploratory test calls by the lead; these are not automated tests. Full fetches use the keyed Data and Tools APIs. Qatar is the reporter; partner reports are mirror checks only, a few partners at a time. Split by year, flow and product chapter, split again whenever the returned count equals the applicable limit, and spread large fetches across days. Use the secondary key only after the primary reaches its daily limit. Record limits and daily call counts in receipts, without keys. If the free plan cannot supply a table, record the gap's size and the plan price for the owner, never evade the limit or buy access. S2-T23 verifies current documentation before fetching.
2. **Header-only keys, lead-only execution.** Read `COMTRADE_PRIMARY_API_KEY` and `COMTRADE_SECONDARY_API_KEY` only from the environment; send either only in `Ocp-Apim-Subscription-Key`, never an address. No worker, reviewer, test, CI job, brief, log, receipt, fixture, error or document holds a key or keyed address. Only the lead's own shell runs a keyed fetch through `./eii build-public`. All automated tests use invented recorded responses, no network and no key. This is a narrow authorised provider interface under PUB-12, not permission to discover page tokens or bypass access controls; rule 14 and the offline-gate boundary remain.
3. **Free downloads and benchmarks.** Add the source families in “New sources and verification ownership”, each only after its task reads its own page for publisher, dataset, version, licence words, access tier, retrieval date and hash. The page descriptions are explicitly unverified leads. Use BACI and Comtrade first for exports/partners, Gravity and Atlas next for models, then benchmarks. Atlas uses finished downloads only, never a rebuild. A registration or paid tier required by a new download is an owner open item, never a workaround; Comtrade's already-authorised keys are the narrow exception in item 2.
4. **Mirror reconciliation.** Compare the portal's own import tables, Comtrade reporter and partner-mirror series and BACI; record the gap by partner and year and known causes. Never merge them into a single figure. Preserve each published figure, source and year, and record incompatible currencies, valuation bases, classifications, periods, coverage and missing cells rather than silently equating them. Unknown causes stay unknown. S2-T26 owns the record; S7-T11 renders it. Certificates of origin and vessel tonnage remain their own measures, not exports.
5. **Every held table has a use.** The audit below records existing declared uses and fetch eligibility individually. Preserve those uses and give each unused table a card, question class, method input or calibration anchor with an owning task, or a recorded reason why none is lawful. Where public tables publish the same figure as private calibration (Qatari share by activity, mean pay, size classes), the public figure leads and private calibration is a cross-check only. Private inputs fill what public tables do not publish, including non-Qatari country-group proportions and pay percentiles; decision 0037's private gender draw remains separate. Compare compatible populations, periods and measures only; a mismatch is a gap, not permission to invent a mapping or override a tolerance. World size bands remain micro below 10, small 10 to 49, medium 50 to 99 and large 100 and over by recorded headcount (decision 0036 item 4); every public table keeps its own classes. S4-T11/T12 implement precedence without printing private values.
6. **A second, narrow nationality anchor.** The world build may sum a Public nationality split over the source's own categories into the nationality groups the worker records carry, solely as a cited calibration anchor of their nationality draw, with source and year, public first and private cross-check only. It is never a record join, segmentation, apportionment to a drawn area, combination with a protected figure or new attribute. A Qatari/non-Qatari table does not invent the split within non-Qataris. Public sex splits never anchor worker, residence or company sex/gender; movement's existing exception stays. Employment gender under decision 0037 remains, drawn solely from the owner's table. This item changes only the nationality-anchor clause, not that field or its release rules.
7. **Questions and measured methods widen.** Amend decision 0038 items 4 and 8: S8-T12/T13 include exports, partners, product concentration, single-origin dependence, change over time, mirror gap, revealed comparative advantage and product-country relatedness, plus source-grain question classes for held tables as specified below. Inventory rows 1/14 (S6-T27) assess the trade histories; row 16 (S7-T22) uses trade/Atlas product-country evidence; row 4 (S6-T28) assesses applicable thin Public cells; row 12's S7-T20 “IPF gravity calibration” uses Gravity as bilateral context where applicable. International distance is not a local travel-time or sales observation. Their blocking audits, baselines and pass tests stay unchanged; unavailable histories or incompatible grains remain explicit refusals. Earlier decision 0038 is not rewritten. L9's product-space context enters this measured work; L5/L6/L7 retain their order.
8. **Repository values.** Follow decision 0034 and PUB-11/PUB-12: an open licence, including Etalab 2.0 only if confirmed by the task, permits values under its attribution terms; a source without one keeps values out of the repository. S2-T23 reads and records Comtrade's terms before any value is committed. Existing registry `commit_allowed: false` rows and the S2-T22 guard are unchanged; any later licensed derived fixture/configuration follows the reviewed registry policy, never a blanket permission to commit downloads. Tests of these fetchers use invented responses regardless of licence.
9. **Unchanged.** Every gate, review rule, check, attack size and tolerance; document 06; no owner networks; no model-written queries, numbers or display prose; no invented attribute on a real place or business beyond decision 0022; no paid spend for these sources. Decision 0035 keeps actual Public attribution and truthful method lineage; it does not turn generated output into an official figure.

## New sources and verification ownership

The owner-relayed note of 20:43 supplies these addresses and descriptions. No external page was opened in drafting this record. “The page states” below means the supplied lead, **to be verified by the named task**, not a confirmed licence, version, schema or availability. Source ids are planned metadata names; the registry is unchanged.

| Planned source_id | Publisher, dataset and page address | Page lead and verification task | Intended use |
|---|---|---|---|
| `un_comtrade` | United Nations Statistics Division, UN Comtrade; https://comtradeapi.un.org/public/v1 ; https://comtradeapi.un.org/data/v1 ; https://comtradeapi.un.org/tools/v1 ; https://uncomtrade.org/docs/un-comtrade-tools/ | Free API limits as supplied in the owner's notes, to be verified by S2-T23; licence/terms text not verified | Qatar imports/exports by product/partner; annual and monthly where available; partner mirror only |
| `cepii_baci` | CEPII, BACI; https://www.cepii.fr/DATA_DOWNLOAD/baci/doc/baci_webpage.html | The page states HS6 bilateral value/quantity reconciled between reporters, version 202501, Etalab 2.0, to be verified by S2-T24 | Free substitute for Comtrade bulk files; separate comparison series |
| `cepii_gravity` | CEPII, Gravity; https://www.cepii.fr/cepii/en/bdd_modele/presentation.asp?id=8 | The page states bilateral distance, contiguity, language, colonial links, trade agreements and GDP, version 202211, Etalab 2.0, to be verified by S2-T25 | Bilateral gravity and relatedness covariates; not local catchment observations |
| `atlas_complexity` | Harvard Growth Lab, Atlas of Economic Complexity; https://atlas.hks.harvard.edu/data-downloads/ ; https://intl-atlas-downloads.s3.amazonaws.com/index.html ; https://dataverse.harvard.edu/dataverse/atlas | The page states finished country-product-year and country-partner-product-year files at four-digit HS with complexity measures, to be verified by S2-T25; licence read on its own page | Finished files only, product/country relatedness comparison and RCA |
| `wb_wdi` | World Bank, World Development Indicators; https://data.worldbank.org/ | The page states a free benchmark route, to be verified by S2-T26; version and licence words not verified | National economic benchmarks in D1 |
| `unctad_fdi` | UNCTAD, UNCTADstat; https://unctadstat.unctad.org/ | The page states FDI flows and country profiles, to be verified by S2-T26; version and licence words not verified | FDI flows separate from project announcements |
| `imf_weo` | International Monetary Fund, World Economic Outlook; https://www.imf.org/ | The page states a free benchmark route, to be verified by S2-T26; version and licence words not verified | Historical macroeconomic benchmark; a publisher forecast is not a project forecast |
| `ilostat_qat` | International Labour Organization, ILOSTAT; https://www.ilo.org/ilostat | Qatar labour-series availability not confirmed by the relayed note; page, version and licence to be verified by S2-T26 | National labour context only if confirmed |

## Held public tables and their use

This is a read-only design-usage audit of document 04 sections “Identity, fetch and licence” and “Coverage, use and traps”, its PUB requirements, document 07's method cards, and TASKS.md's named tasks. Every registry key below is read from `custodian/publicdata/sources.yaml`; family rows with no registry key cover the remaining planned sources in document 04. Each family's listed use applies to each of its slugs; the workbook's four named tables share one source/receipt and their declared roles are listed together. Method/card references are document 07; PUB references are document 04. Task references identify the owning planned work, not proof it runs.

“Fetched by build-public” means eligible by the registry test (row exists, no skip), not a claim about the cache or a successful fetch. Citation-only rows are explicitly No because PUB-04 opens no request; they do have an unskipped metadata row. A skip reason is copied as a state, not endorsed or repaired here. A source can be used by the design while not yet fetchable. No implementation-consumption count can be inferred from this audit.

Audit counts: 111 held/planned source families in section 2.1; 139 registry rows; 171 audit rows after adding missing families; 110 fetch-eligible rows; 12 citation-only rows (unskipped metadata); 122 total unskipped registry rows. No held family has zero declared use: **unused held families: 0; list: none**. This does not assert that all are wired. The research-only sources and their previous unused state are listed separately below, not counted as held tables.

| source_id | Registry key (or missing row) | Fetched by build-public | Declared use and owning requirement/task |
|---|---|---|---|
| `lic_active` | `lic_active` | Yes | C1 licence density; C31 denominator; spine: PUB-67, PUB-72, PUB-104; S7-T04, S6-T15, S2-T04 |
| `lic_cancelled` | `lic_cancelled` | Yes | C2/C22 licence history, C30 forecasts, C31 rates: PUB-94, PUB-103, PUB-104; S7-T04, S7-T10, S6-T14, S6-T15 |
| `lic_issued` | `lic_issued` | Yes | C2/C22 licence history, C30 forecasts, C31 rates: PUB-94, PUB-103, PUB-104; S7-T04, S7-T10, S6-T14, S6-T15 |
| `cus_imp_2025` | `cus_imp_2025` | Yes | C5 baskets and origin concentration, C13 import/production, C30 series: PUB-44, PUB-45, PUB-103; S7-T02, S7-T11, S6-T27 |
| `cus_imp_2019` | `cus_imp_2019` | Yes | C5 baskets and origin concentration, C13 import/production, C30 series: PUB-44, PUB-45, PUB-103; S7-T02, S7-T11, S6-T27 |
| `sec_hr_ind` | `sec_hr_ind` | Yes | C4 published cost shares, C35 scenario reference: PUB-64; S7-T01, S7-T15; no production-value benchmark |
| `sec_hr_goods` | `sec_hr_goods` | Yes | C4 published cost shares, C35 scenario reference: PUB-64; S7-T01, S7-T15; no production-value benchmark |
| `sec_hr_serv` | `sec_hr_serv` | Yes | C4 published cost shares, C35 scenario reference: PUB-64; S7-T01, S7-T15; no production-value benchmark |
| `sec_hr_size` | `sec_hr_size` | Yes | C4 and C24 employer scale: PUB-64, document 07 C24; S7-T01, S7-T07; public classes stay intact |
| `sec_hr_comp_occ` | `sec_hr_comp_occ` | Yes | C10 staffing/national mean context: document 04 Coverage, use and traps; S7-T03, S7-T08 |
| `wage_occ` | `wage_occ` | Yes | C3 pay decomposition, C10 public mean, C41 affordability: PUB-63, PUB-76, PUB-107; S7-T04, S7-T03, S6-T10 |
| `wage_act` | `wage_act` | Yes | C19 national within/mix pay changes and staffing context: MTH-97, PUB-76; S6-T09, S7-T08; OI-03 hold remains |
| `wage_sector` | `wage_sector` | No: publisher_or_licence_unconfirmed | C10 staffing/national mean context: document 04 Coverage, use and traps; S7-T03, S7-T08 |
| `wage_bands_priv` | `wage_bands_priv` | No: publisher_or_licence_unconfirmed | World wage-band boundary/calibration: document 04 Coverage, use and traps; S4-T03; decision 0034 item 3(a) unchanged |
| `work_hours_act` | `work_hours_act` | No: publisher_or_licence_unconfirmed | World schedule anchor, totals over sex only: document 04 Coverage, use and traps, PUB-90; S4-T04 |
| `util_elec` | `util_elec` | Yes | C9 zone momentum and opening scene: document 07 C9; S6-T03, S7-T04 |
| `util_water` | `util_water` | Yes | C9 zone momentum and opening scene: document 07 C9; S6-T03, S7-T04 |
| `transit_monthly` | `transit_monthly` | Yes | C9 public movement context and world calibration: PUB-70; S7-T04, S4-T04 |
| `hotel_segment` | `hotel_segment` | Yes | C30 published-series forecasts and national context: PUB-103; S6-T14, S7-T04 |
| `cpi_group` | `cpi_group` | No: publisher_or_licence_unconfirmed | C30 published-series forecasts and national context: PUB-103; S6-T14, S7-T04 |
| `prop_sales` | `prop_sales` | Yes | C14/C41 property prices and C30 eligible histories: PUB-107, PUB-103; S6-T10, S6-T14 |
| `pop_muni` | `pop_muni` | Yes | C1 licence-density denominator: PUB-72, PUB-83; S7-T04 |
| `zone_population` | `zone_population` | No: cache_fields_unconfirmed; adapter_unavailable | World population/housing calibration: document 04 Coverage, use and traps; S4-T03, S4-T12; source schema still unconfirmed |
| `est_census` | `est_census` | Yes | C6 places coverage and world establishment calibration: PUB-50, PUB-73, PUB-83; S6-T10, S4-T12 |
| `census_hh_type_2020` | `census_hh_type_2020` | No: cache_fields_unconfirmed; adapter_unavailable | World population/housing calibration: document 04 Coverage, use and traps; S4-T03, S4-T12; source schema still unconfirmed |
| `accident` | `accident` | No: publisher_or_licence_unconfirmed | World simulation plausibility hold-out: document 04 Coverage, use and traps; S4-T05 |
| `census_2020_workbook` | `census_2020_workbook` | No: schema_unconfirmed | Tables 1, 2, 151, 152: zone totals, establishment size and municipal establishment counts; document 04 Coverage, use and traps; S4-T12; sheet schema unconfirmed |
| `worldpop_qat_2020` | `worldpop_qat_2020` | No: direct_url_unconfirmed | C12/C18 weights and family-housing calibration: document 04 Coverage, use and traps; S6-T13, S6-T01, S4-T03; never a current population total |
| `census_zone_sector` | `census_zone_sector` | Yes | C7/C8/C17 population, coverage and area context; world calibration: PUB-71, PUB-83; S7-T05, S6-T12, S4-T12 |
| `census_zone_occ` | `census_zone_occ` | Yes | C7/C8/C17 population, coverage and area context; world calibration: PUB-71, PUB-83; S7-T05, S6-T12, S4-T12 |
| `census_zone_hh` | `census_zone_hh` | Yes | C7/C8/C17 population, coverage and area context; world calibration: PUB-71, PUB-83; S7-T05, S6-T12, S4-T12 |
| `census_zone_lab` | `census_zone_lab` | Yes | C7/C8/C17 population, coverage and area context; world calibration: PUB-71, PUB-83; S7-T05, S6-T12, S4-T12 |
| `census_district_pop` | `census_district_pop` | Yes | C7/C8/C17 population, coverage and area context; world calibration: PUB-71, PUB-83; S7-T05, S6-T12, S4-T12 |
| `bnd_zone_2020` | `bnd_zone_2020` | Yes | Frame geometry/check or fallback for area methods: PUB-24 to PUB-30; S2-T02, S3-T04 |
| `bnd_district_2020` | `bnd_district_2020` | Yes | Frame geometry/check or fallback for area methods: PUB-24 to PUB-30; S2-T02, S3-T04 |
| `bnd_hdx` | `bnd_hdx` | Yes | Frame geometry/check or fallback for area methods: PUB-24 to PUB-30; S2-T02, S3-T04 |
| `bnd_muni_2025` | `bnd_muni_2025` | No: publisher_or_licence_unconfirmed | Frame geometry/check or fallback for area methods: PUB-24 to PUB-30; S2-T02, S3-T04 |
| `bnd_geob` | `bnd_geob` | Yes | Frame geometry/check or fallback for area methods: PUB-24 to PUB-30; S2-T02, S3-T04 |
| `places_ovt` | `places_ovt` | No: overture_bucket_not_opened | C6 neighbours, C5/C13 public business context and C34 competitor counts/distances: PUB-47, PUB-92, PUB-102; S3-T05, S6-T10, S7-T14 |
| `bldg_ovt` | `bldg_ovt` | No: overture_bucket_not_opened | Flagship/showcase geometry: PUB-57; S2-T06, S3-T12 |
| `roads_osm` | `roads_osm` | Yes | C7/C12/C25/C39 routing and world traffic: document 04 Coverage, use and traps; S4-T04, S6-T13, S6-T20 |
| `cls_isic4` | `cls_isic4` | Yes | Spine validity and English titles: PUB-33, PUB-40; S2-T04; titles remain blocked while unconfirmed |
| `ref_min_wage` | `ref_min_wage` | No: citation-only metadata; no file request | C10 statutory reference and world wage minimum: MTH-42; S7-T03, S4-T03; decision 0034 item 3(b) unchanged |
| `ref_wps_report` | `ref_wps_report` | No: citation-only metadata; no file request | World calibration rules/plausibility context: document 04 Coverage, use and traps; S4-T03, S4-T04, S4-T05; road-speed index is not a hold-out |
| `ref_expansion_method` | `ref_expansion_method` | No: citation-only metadata; no file request | World calibration rules/plausibility context: document 04 Coverage, use and traps; S4-T03, S4-T04, S4-T05; road-speed index is not a hold-out |
| `ref_gov_hours` | `ref_gov_hours` | No: citation-only metadata; no file request | World calibration rules/plausibility context: document 04 Coverage, use and traps; S4-T03, S4-T04, S4-T05; road-speed index is not a hold-out |
| `ref_friday_closure` | `ref_friday_closure` | No: citation-only metadata; no file request | World calibration rules/plausibility context: document 04 Coverage, use and traps; S4-T03, S4-T04, S4-T05; road-speed index is not a hold-out |
| `ref_transit_hours` | `ref_transit_hours` | No: citation-only metadata; no file request | World calibration rules/plausibility context: document 04 Coverage, use and traps; S4-T03, S4-T04, S4-T05; road-speed index is not a hold-out |
| `ref_summer_work` | `ref_summer_work` | No: citation-only metadata; no file request | World calibration rules/plausibility context: document 04 Coverage, use and traps; S4-T03, S4-T04, S4-T05; road-speed index is not a hold-out |
| `ref_truck_hours` | `ref_truck_hours` | No: citation-only metadata; no file request | World calibration rules/plausibility context: document 04 Coverage, use and traps; S4-T03, S4-T04, S4-T05; road-speed index is not a hold-out |
| `ref_ramadan_public_hours` | `ref_ramadan_public_hours` | No: citation-only metadata; no file request | World calibration rules/plausibility context: document 04 Coverage, use and traps; S4-T03, S4-T04, S4-T05; road-speed index is not a hold-out |
| `ref_ramadan_private_hours` | `ref_ramadan_private_hours` | No: citation-only metadata; no file request | World calibration rules/plausibility context: document 04 Coverage, use and traps; S4-T03, S4-T04, S4-T05; road-speed index is not a hold-out |
| `ref_ramadan_transit_hours` | `ref_ramadan_transit_hours` | No: citation-only metadata; no file request | World calibration rules/plausibility context: document 04 Coverage, use and traps; S4-T03, S4-T04, S4-T05; road-speed index is not a hold-out |
| `ref_traffic_index` | `ref_traffic_index` | No: citation-only metadata; no file request | World calibration rules/plausibility context: document 04 Coverage, use and traps; S4-T03, S4-T04, S4-T05; road-speed index is not a hold-out |
| `prop_resi_units` | `prop_resi_units/weekly-residential-units-sales-bulletin` | Yes | C14/C41 property prices and C30 eligible histories: PUB-107, PUB-103; S6-T10, S6-T14 |
| `visits_museum` | `visits_museum/visitors-of-museums-and-exhibition-by-month-and-museum` | Yes | C26 published venue visits and seasonal/annual world checks: PUB-91; S6-T03, S4-T07 |
| `visits_phcc` | `visits_phcc/phcc-patient-visits-by-health-center-and-region` | Yes | C26 published venue visits and seasonal/annual world checks: PUB-91; S6-T03, S4-T07 |
| `permits_muni` | `permits_muni/total-building-permits-issued-by-municipality-and-type-of-building-type-of-permit` | Yes | C23 construction pipeline and C30 permits history: PUB-103; S7-T10, S6-T14 |
| `permits_muni` | `permits_muni/total-building-completion-certificates-issued-by-municipality-and-type-of-building-type-of` | Yes | C23 construction pipeline and C30 permits history: PUB-103; S7-T10, S6-T14 |
| `permits_muni` | `permits_muni/building-permits-issued-by-type-of-permit-and-month-al-daayen-municipality` | Yes | C23 construction pipeline and C30 permits history: PUB-103; S7-T10, S6-T14 |
| `permits_muni` | `permits_muni/building-permits-issued-by-type-of-permit-and-month-al-khor-and-al-thakhira-municipality` | Yes | C23 construction pipeline and C30 permits history: PUB-103; S7-T10, S6-T14 |
| `permits_muni` | `permits_muni/building-permits-issued-by-type-of-permit-and-month-al-rayyan-municipality` | Yes | C23 construction pipeline and C30 permits history: PUB-103; S7-T10, S6-T14 |
| `permits_muni` | `permits_muni/building-permits-issued-by-type-of-permit-and-month-al-shahhaniya-municipality` | Yes | C23 construction pipeline and C30 permits history: PUB-103; S7-T10, S6-T14 |
| `permits_muni` | `permits_muni/building-permits-issued-by-type-of-permit-and-month-al-shamal-municipality` | Yes | C23 construction pipeline and C30 permits history: PUB-103; S7-T10, S6-T14 |
| `permits_muni` | `permits_muni/building-permits-issued-by-type-of-permit-and-month-al-wakrah-municipality` | Yes | C23 construction pipeline and C30 permits history: PUB-103; S7-T10, S6-T14 |
| `permits_muni` | `permits_muni/building-permits-issued-by-type-of-permit-and-month-doha-municipality` | Yes | C23 construction pipeline and C30 permits history: PUB-103; S7-T10, S6-T14 |
| `permits_muni` | `permits_muni/building-permits-issued-by-type-of-permit-and-month-umm-slal-municipality` | Yes | C23 construction pipeline and C30 permits history: PUB-103; S7-T10, S6-T14 |
| `est_size_act` | `est_size_act/number-of-establishments-and-employees-by-size-of-establishment-and-main-economic-activity-two` | Yes | C24 employer scale: document 07 C24; S7-T07, S7-T12; source-class crosswalk, no re-banding |
| `est_size_act` | `est_size_act/number-of-establishments-and-employees-by-size-of-establishment-and-main-economic-activity-wholesale-and-retail-trade-four-digits` | Yes | C24 employer scale: document 07 C24; S7-T07, S7-T12; source-class crosswalk, no re-banding |
| `est_size_act` | `est_size_act/number-of-establishments-and-employees-by-size-of-establishment-and-main-economic-activity-transport` | Yes | C24 employer scale: document 07 C24; S7-T07, S7-T12; source-class crosswalk, no re-banding |
| `est_size_act` | `est_size_act/number-of-establishments-and-employees-by-size-of-establishment-and-main-economic-activity-social-and-personal-services-two-digits` | Yes | C24 employer scale: document 07 C24; S7-T07, S7-T12; source-class crosswalk, no re-banding |
| `est_size_act` | `est_size_act/number-of-establishments-and-employees-by-size-of-establishment-and-main-economic-activity-energy` | Yes | C24 employer scale: document 07 C24; S7-T07, S7-T12; source-class crosswalk, no re-banding |
| `est_size_act` | `est_size_act/number-of-establishments-and-employees-by-size-of-establishment-and-main-economic-activity-one` | Yes | C24 employer scale: document 07 C24; S7-T07, S7-T12; source-class crosswalk, no re-banding |
| `est_size_act` | `est_size_act/establishments-employees-and-compensation-of-employees-by-economic-activity-business-services` | Yes | C24 employer scale: document 07 C24; S7-T07, S7-T12; source-class crosswalk, no re-banding |
| `mfg_industry` | `mfg_industry/manufacture-of-basic-metals` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-basic-pharmaceutical-products-and-pharmaceutical-preparations` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-beverages` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-chemicals-and-chemical-products` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-coke-and-refined-petroleum-products` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-computer-electronic-and-optical-products` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-electrical-equipment` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-fabricated-metal-products-except-machinery-and-equipment` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-food-products` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-furniture` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-leather-and-related-products` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-machinery-and-equipment-nec` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-manufacture-of-wood-and-of-products-of-wood-and-cork-except-furniture-manufacture` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-motor-vehicles-trailers-and-semi-trailers` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-other-non-metallic-mineral-products` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-other-transport-equipment` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-paper-and-paper-products` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-rubber-and-plastics-products` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-textiles` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/manufacture-of-wearing-apparel` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `mfg_industry` | `mfg_industry/main-manufacturing-products` | Yes | C13 imports against production and supplier context: document 07 C13; S7-T11, S7-T09 |
| `trade_wr` | `trade_wr/purchases-sales-and-stocks-during-the-year-by-type-of-trade-wholesale-and-retail-trade-all` | Yes | D1 national wholesale/retail market-size question, context only: document 04 Coverage, use and traps; S7-T12; never an entrant-sales forecast |
| `pop_muni_age` | `pop_muni_age/population-by-municipality-and-age-groups` | Yes | D3 population customer-context questions at source grain; latter also SYN-89 movement age/gender anchor: S7-T07, S4-T08 |
| `hotels_muni` | `hotels_muni/hotels-and-hotel-apartments-by-municipality` | Yes | D1 accommodation-supply question and SYN-76 facility-count calibration: S7-T12, S4-T07 |
| `trade_logistics` | `trade_logistics/annual-certificates-of-origin-by-type-and-importing-country` | Yes | C13 certificates-of-origin and vessel context; decision 0038 inventory 1, 14, 16 candidates: S7-T11, S6-T27, S7-T22; not export values |
| `trade_logistics` | `trade_logistics/arriving-vessels-gross-and-net-tonnage-by-type-of-vessel-and-country-of-previous-port` | Yes | C13 certificates-of-origin and vessel context; decision 0038 inventory 1, 14, 16 candidates: S7-T11, S6-T27, S7-T22; not export values |
| `trade_logistics` | `trade_logistics/arriving-vessels-gross-and-net-tonnage-by-type-of-vessel-and-country-of-registration-hamad-port0` | Yes | C13 certificates-of-origin and vessel context; decision 0038 inventory 1, 14, 16 candidates: S7-T11, S6-T27, S7-T22; not export values |
| `est_census_2015_muni` | `est_census_2015_muni/distribution-of-business-establishments-and-employees-by-municipalities-according-to-census-2015` | Yes | World fidelity by municipality: document 04 Coverage, use and traps; S4-T05, S4-T12; historical comparison, not current firm count |
| `lf_muni_sex` | `lf_muni_sex/female-population-and-labour-force-by-municipality` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `lf_muni_sex` | `lf_muni_sex/male-population-and-labour-force-by-municipality` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `lf_muni_sex` | `lf_muni_sex/employed-persons-15-years-and-above-by-gender-and-municipality` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `lf_muni_sex` | `lf_muni_sex/unemployed-persons-15-years-and-above-by-gender-and-municipality` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `pop_muni_age_sex` | `pop_muni_age_sex/females-population-by-municipality-and-age-groups-december-2020` | Yes | D3 population customer-context questions at source grain; latter also SYN-89 movement age/gender anchor: S7-T07, S4-T08 |
| `pop_muni_age_sex` | `pop_muni_age_sex/males-population-by-municipality-and-age-groups-december-2020` | Yes | D3 population customer-context questions at source grain; latter also SYN-89 movement age/gender anchor: S7-T07, S4-T08 |
| `active_sex_age_act` | `active_sex_age_act/economically-active-females-15-years-and-above-by-age-group-and-economic-activity` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `active_sex_age_act` | `active_sex_age_act/economically-active-males-15-years-and-above-by-age-group-and-economic-activity` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `active_nat_occ_act` | `active_nat_occ_act/economically-active-non-qatari-females-15-years-and-above-by-occupation-and-economic-activity` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `active_nat_occ_act` | `active_nat_occ_act/economically-active-non-qatari-males-15-years-and-above-by-occupation-and-economic-activity` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `active_nat_occ_act` | `active_nat_occ_act/economically-active-non-qatari-population-15-years-and-above-by-occupation-and-economic-activity` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `active_nat_occ_act` | `active_nat_occ_act/economically-active-qatari-females-15-years-and-above-by-occupation-and-economic-activity` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `active_nat_occ_act` | `active_nat_occ_act/economically-active-qatari-males-15-years-and-above-by-occupation-and-economic-activity` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `active_nat_occ_act` | `active_nat_occ_act/economically-active-qatari-population-15-years-and-above-by-occupation-and-economic-activity` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `comp_nat_act` | `comp_nat_act/number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `comp_nat_act` | `comp_nat_act/number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-building` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `comp_nat_act` | `comp_nat_act/number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-business` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `comp_nat_act` | `comp_nat_act/number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-energy` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `comp_nat_act` | `comp_nat_act/number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-energy0` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `comp_nat_act` | `comp_nat_act/number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-energy1` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `comp_nat_act` | `comp_nat_act/number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-one` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `comp_nat_act` | `comp_nat_act/number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-social` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `comp_nat_act` | `comp_nat_act/number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-social0` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `comp_nat_act` | `comp_nat_act/number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-social1` | Yes | C21/D5 published workforce, occupation/activity and pay-context questions: PUB-90, decision 0038 item 8; S7-T08, S8-T12; source categories/geography only |
| `students_muni` | `students_muni/students-by-level-of-education-municipality-gender-type-of-education-and-nationality-2025-2026` | Yes | D3/D5 education and future-workforce context questions: document 04 Coverage, use and traps; S7-T07, S7-T08; not school capacity |
| `visitors_markets` | `visitors_markets/hotel-guests-by-nationality-hotel-rating-and-hotel-stays` | Yes | D1/D3 visitor-market context and SYN-89 international-visitor anchor: S7-T12, S7-T07, S4-T08 |
| `visitors_markets` | `visitors_markets/visitor-arrivals-by-mode-of-entry` | Yes | D1/D3 visitor-market context and SYN-89 international-visitor anchor: S7-T12, S7-T07, S4-T08 |
| `visitors_markets` | `visitors_markets/visitor-arrivals-by-region` | Yes | D1/D3 visitor-market context and SYN-89 international-visitor anchor: S7-T12, S7-T07, S4-T08 |
| `visitors_markets` | `visitors_markets/visitor-arrivals-trends-by-mode-of-transport-air-land-sea` | Yes | D1/D3 visitor-market context and SYN-89 international-visitor anchor: S7-T12, S7-T07, S4-T08 |
| `fdi_projects` | `fdi_projects` | Yes | D1/D4/D6/D7 announcement context and C30 eligible investment history: PUB-87, PUB-103; S7-T09 to S7-T12, S6-T14 |
| `investqa_pages` | `investqa_pages` | Yes | D1 sector/set-up questions and C4 optional user scenario inputs: PUB-88; S7-T12, S7-T01 |
| `busy_gmaps` | `busy_gmaps` | No: fetcher_owned_by_S2-T16 | C37 public relative busyness; pooled category/hour world anchor: PUB-101; S3-T14, S4-T09 |
| `ntl_blackmarble` | `ntl_blackmarble` | No: fetcher_owned_by_S2-T14 | C36 radiance and clock night lights: PUB-100; S3-T14, S3-T16 |
| `places_fsq` | `places_fsq` | No: fetcher_owned_by_S2-T15 | C6 neighbours, C5/C13 public business context and C34 competitor counts/distances: PUB-47, PUB-92, PUB-102; S3-T05, S6-T10, S7-T14 |
| `worldpop_qat_agesex` | `worldpop_qat_agesex` | No: fetcher_owned_by_S2-T14 | C38 display-only whole-cell population; collapsed world weights: PUB-99; S3-T14, S4-T08 |
| `weather_openmeteo` | `weather_openmeteo` | No: fetcher_owned_by_S2-T14 | Typical seasonal/hourly world weather profiles: PUB-97; S4-T09 |
| `places_fsq` | `places_fsq/copy-2025-01-10` | Yes | C6 neighbours, C5/C13 public business context and C34 competitor counts/distances: PUB-47, PUB-92, PUB-102; S3-T05, S6-T10, S7-T14 |
| `traffic_tomtom_flow` | `no registry row` | No: no registry row | C25 optional live flow/range, no storage: PUB-95; S6-T19 |
| `traffic_tomtom_range` | `no registry row` | No: no registry row | C25 optional live flow/range, no storage: PUB-95; S6-T19 |
| `biz_register` | `no registry row` | No: no registry row | Public company cards/counts and C22 history; attached-world frame: decision 0022 items 1 to 5, decision 0023 item 12; S3-T12, S3-T17, S4-T02, S7-T10 |
| `fc_register` | `no registry row` | No: no registry row | Public company cards/counts and C22 history; attached-world frame: decision 0022 items 1 to 5, decision 0023 item 12; S3-T12, S3-T17, S4-T02, S7-T10 |
| `gis_land_price` | `no registry row` | No: no registry row | C41 guide-price comparison: PUB-107; S6-T10 |
| `gis_rail` | `no registry row` | No: no registry row | D2/D5 site-fit/context questions and map: PUB-105, PUB-108; S3-T12, S6-T12; plans/looks-empty only |
| `gis_phcc` | `no registry row` | No: no registry row | D2/D5 site-fit/context questions and map: PUB-105, PUB-108; S3-T12, S6-T12; plans/looks-empty only |
| `gis_landmarks` | `no registry row` | No: no registry row | Map/frame/place-resolution inputs: PUB-105; S2-T19, S3-T03, S3-T12; source fields confirmed before use |
| `gis_locator` | `no registry row` | No: no registry row | Map/frame/place-resolution inputs: PUB-105; S2-T19, S3-T03, S3-T12; source fields confirmed before use |
| `gis_zoning` | `no registry row` | No: no registry row | D2/D5 site-fit/context questions and map: PUB-105, PUB-108; S3-T12, S6-T12; plans/looks-empty only |
| `gis_address` | `no registry row` | No: no registry row | D2/D5 site-fit/context questions and map: PUB-105, PUB-108; S3-T12, S6-T12; plans/looks-empty only |
| `gis_parcels` | `no registry row` | No: no registry row | D2/D5 site-fit/context questions and map: PUB-105, PUB-108; S3-T12, S6-T12; plans/looks-empty only |
| `gis_poi_comm` | `no registry row` | No: no registry row | C6 competitor counts/distances: PUB-92; S3-T05, S6-T10 |
| `gis_boundaries` | `no registry row` | No: no registry row | Map/frame/place-resolution inputs: PUB-105; S2-T19, S3-T03, S3-T12; source fields confirmed before use |
| `gis_context` | `no registry row` | No: no registry row | Map/frame/place-resolution inputs: PUB-105; S2-T19, S3-T03, S3-T12; source fields confirmed before use |
| `gis_imagery_history` | `no registry row` | No: no registry row | D6 fixed before/after views: PUB-105; S3-T16, S7-T10; pictures, not statistics |
| `bldg_3dglobfp` | `no registry row` | No: no registry row | Building-height fallbacks: PUB-106; S2-T20, S3-T16; not business attributes |
| `bldg_wsf3d` | `no registry row` | No: no registry row | Building-height fallbacks: PUB-106; S2-T20, S3-T16; not business attributes |
| `bank_credit_act` | `no registry row` | No: no registry row | C41 credit/sector-growth context: document 07 C41, PUB-108; S7-T12; missing matched growth series still refuses |
| `tenders_pub` | `no registry row` | No: no registry row | D4 tender demand questions: PUB-93; S7-T09 |
| `dcool_capacity` | `no registry row` | No: no registry row | D1/D6 utilities/capacity context: PUB-108; S7-T10, S7-T12 |
| `trade_ext` | `no registry row` | No: no registry row | D1/D7 trade-context questions: PUB-108; S7-T11, S7-T12; source/table confirmation in S2-T19 |
| `survey_ext` | `no registry row` | No: no registry row | D1 sector/price context: PUB-108; S7-T12; price series enters C30 only after source and method admission |
| `price_ext` | `no registry row` | No: no registry row | D1 sector/price context: PUB-108; S7-T12; price series enters C30 only after source and method admission |
| `hotel_ext` | `no registry row` | No: no registry row | D1/D3 hotel supply/demand context: PUB-108; S7-T12, S7-T07; world use only as SYN-76 permits |
| `talent_ext` | `no registry row` | No: no registry row | D5 public labour context beside released talent: PUB-108, PRV-41; S7-T08; never joined to protected figures |
| `jobseekers` | `no registry row` | No: no registry row | D5 public labour context beside released talent: PUB-108, PRV-41; S7-T08; never joined to protected figures |
| `utilities_ext` | `no registry row` | No: no registry row | D1/D6 utilities/capacity context: PUB-108; S7-T10, S7-T12 |
| `coverage_ext` | `no registry row` | No: no registry row | D2 source-grain network-coverage context: PUB-108; S3-T12, S6-T02 |
| `fdi_stats` | `no registry row` | No: no registry row | D1 national FDI context, separate from announcements: PUB-108; S7-T12 |
| `completions_ext` | `no registry row` | No: no registry row | D6 construction-pipeline context: PUB-108; S7-T10 |
| `tiles3d_google` | `no registry row` | No: no registry row | Optional 3D map mode: PUB-109; S3-T16; live only, no table |

### Research-only and newly planned sources

Before this amendment, document 04's paragraph “Sources mentioned in research but not in v1” excluded Comtrade, Atlas, World Bank and ILOSTAT: unused in version 1 (four named source families, distinct from the held inventory). Items 1 and 3 now assign all four and the additional BACI, Gravity, UNCTADstat and WEO sources below. The earlier 2014–2018 imports have no confirmed source id/table and remain outside version 1; S2-T23 records availability as metadata, without inventing a source or silently extending the portal series. OpenStreetMap POIs retain their PUB-55 reviewer cross-check use and are not merged. GADM remains a research mention, not a newly authorised frame source. The satellite/address provider remains unnamed pending its existing source-row work under PUB-109; S3-T03/S3-T16 own its live use. Conditional Copernicus Sentinel-2 imagery remains decision 0023 item 13's offline-opening-shot source-registration work, not a fetched table or a new task here.

| Planned source_id | Before 0040 | Fetched now | Assigned use/task |
|---|---|---|---|
| `un_comtrade` | Unused in version 1; research-only | No: no registry row | S2-T23; S7-T02/S7-T11 exports, partners and mirror gap |
| `cepii_baci` | New source lead | No: no registry row | S2-T24; S7-T11 exports/partners; S7-T22 relatedness |
| `cepii_gravity` | New source lead | No: no registry row | S2-T25; S7-T20 gravity calibration; S7-T22 country context |
| `atlas_complexity` | Unused in version 1; research-only | No: no registry row | S2-T25; S7-T22 RCA/product-country relatedness |
| `wb_wdi` | Unused in version 1; research-only | No: no registry row | S2-T26; S7-T12 national benchmarks |
| `unctad_fdi` | New source lead | No: no registry row | S2-T26; S7-T12 FDI benchmarks |
| `imf_weo` | New source lead | No: no registry row | S2-T26; S7-T12 macroeconomic benchmarks |
| `ilostat_qat` | Unused in version 1; research-only | No: no registry row | S2-T26 if page confirms; S7-T08 labour benchmarks |

## Wiring and question classes

All additions below are named sub-steps of **queued** tasks in TASKS.md; no completed task is reopened. Source tasks S2-T23 to S2-T26 are new. Their requirements and dependencies are mirrored in document 14. Source acquisition/confirmation precedes its consumers; existing slice gates and review follow-ups include the work.

- S3-T06, **public-source fact bindings**: expose the new typed public facts through existing source-chain validation; no assistant arithmetic.
- S4-T11, **public-first calibration selection**, and S4-T12, **public/private calibration comparison**: `comp_nat_act` leads the compatible Qatari share; `wage_occ`/`wage_act` totals over sex and compatible size/census tables lead their supported targets. OI-03 still blocks unresolved pay facts; no annual compensation is silently equated with monthly wages. Private country-group detail, pay percentiles and the private gender draw retain their own inputs. All public classes and source years remain explicit; no private value is reported.
- S6-T27, **public trade forecast families**: portal imports, `trade_ext`, certificates of origin and eligible Comtrade/BACI/Atlas histories; record frequency, continuity, units and source separately. S6-T28, **public thin-cell candidates**: those trade families and compatible national employee/activity/size tables; no suppression repair and no assertion of a geography they lack.
- S7-T02, **trade origins and concentration**; S7-T11, **exports and mirror evidence**: exports, partners, product concentration, single-origin dependence, temporal change and mirror gap, through C5/C13 and tested method contracts. S7-T22, **RCA and product-country evidence**: Comtrade/BACI and finished Atlas with Gravity covariates where applicable, coordinated with C46's S7-T19. Exact RCA and relatedness formula, denominator and classification mappings are reviewed before implementation; no invented result or graph of owners.
- S7-T20, **Gravity source applicability** within its existing IPF gravity calibration: evaluate bilateral inputs only at their supported grain; preserve the local catchment baseline and missing-sales refusal. No country-level estimate is placed on a named business.
- S7-T08, **held labour-table questions**: `comp_nat_act`, `wage_occ`, `wage_act`, `wage_sector`, `lf_muni_sex`, `active_sex_age_act`, `active_nat_occ_act`, `talent_ext`, `jobseekers`, `students_muni` and confirmed ILOSTAT; each table's public categories/geography, separate from released talent. S7-T07, **held size and population questions**: `est_size_act`, `sec_hr_size`, `pop_muni_age`, `pop_muni_age_sex`, `students_muni`, `hotel_ext`; no source re-banding or school-capacity invention.
- S7-T12, **national benchmark context**: WDI, UNCTADstat, historical WEO, `fdi_stats`, `trade_wr`, `survey_ext`, `price_ext`, `dcool_capacity` and `hotels_muni`; no synthetic substitute, no publisher projection presented as a project backtest. Existing C1 denominator (`pop_muni`), C6 coverage (`est_census`), census/world anchors and C13 logistics remain assigned as in the audit.
- S8-T12/T13, **public-source question matrix**: the eight trade classes of item 7, and table-specific classes for pay/nationality/activity, pay/occupation/activity, employer size, census establishments, municipal population/labour/sex, census sector/occupation/housing, import tariffs/origins and certificates/vessels. Include one row for every audit source and slug with its allowed class or its non-question use (frame, calibration, citation, live imagery), never manufacture a public question from a calibration-only input. Each row names its owning task and tested fact/refusal. Held public tables remain source-specific cells even when they share a question class. Oracle-labelled held-out cases, deterministic graders and planted forbidden-join/source-grain cases remain; no training or model judge.

## Evidence and consequences

The owner's notes of 2026-11-15, 20:35 to 20:43, are the authority for this amendment. Document 04's two source tables and the registry keys are the audit evidence; documents 07 and 09 and TASKS.md provide the method and question ownership. Decisions 0022, 0023, 0026, 0034, 0036, 0037 and 0038 supply the unchanged boundaries. Page addresses above are verification leads only; retrieval dates, hashes, licence words and exact dataset versions remain for S2-T23 to S2-T26. No fetch, implementation test, backtest or measured gain is claimed here.

## Amended passages

- Document 05, In brief and SYN-13: explicitly carry the narrow public-nationality draw anchor (item 6); Q17: source policy answered, category mapping remains open (items 5 and 6).
- Open questions and change control: clarify that the brief wording conflict is resolved by item 6, without repealing decision 0037.
- AGENTS.md and CLAUDE.md: Status and only the single rule 10 sentence naming movement anchors.
- Document 04: source scope, new source-plan section, PUB-90 anchor exception, fetch/access and licence clarifications, and forecast-source admission.
- Document 05: nationality anchor and public-first calibration amendment governing SYN-13 and Q17; private gender and movement unchanged.
- Document 07: source/method wiring and L9 product-space scope; no formula or threshold invented.
- Document 09: public-source question matrix under decision 0038 items 4 and 8.
- TASKS.md and document 14: four fetch tasks and named queued-task sub-steps, dependencies and acceptance criteria.
- docs/README.md: accepted list and decision index.

## Open questions and change control

The lead must settle exact source versions, schemas, compatible category/period mappings and method measurement contracts in the named tasks before their use. Registration/tier obstacles and any free-plan gap with its price go to the owner as item 1 or 3 requires. The wording conflict in item 6's brief is resolved above; no repeal of decision 0037 is inferred. Source-family audit counts are not counts of fetched datasets or implemented consumers. Every substantive change to this decision requires a new record under rule 46.
