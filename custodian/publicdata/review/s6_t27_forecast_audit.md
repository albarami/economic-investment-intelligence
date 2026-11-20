# S6-T27 step-one series and source-shape audit

Maker: OpenAI; model: GPT-6 Codex. Persona: principal forecasting methods
architect. Strict self-review: statistical reviewer rejecting leaked windows,
empty denominators and unpinned fits. Different-maker implementation review is
pending with the lead. This is a metadata audit, not source acceptance.

Authority: TASKS.md S6-T27; decision 0038 items 2, 7 and inventory items 1 and
14; decision 0040 item 7; the supplied ruling L-1228 points 1 to 13. Evidence:
`s2_t17_forecast_series.md`, `s6_t25_generated_series.md`, the tracked source
registry `custodian/publicdata/sources.yaml`, and its BACI/Atlas configuration
files. No cache, receipt body or custodian record was read. Actual receipt hashes,
retrieval dates, per-key continuity and row-carried units remain unverified.
Registry attribution is metadata, not a complete Public fact source chain.

## Public series inventory

Each row is separate by source, measure and published geography/category. A
published span is an upper bound, never a measured longest contiguous run.
HS revision is not applicable except for product trade. Every row is **blocked**
for a Public acceptance run until the missing facts below are supplied.

| Series / source key | Table; frequency; unit | Published history metadata; blocking fact |
|---|---|---|
| licence_issues / lic_issued | pub_licence_issued; month; count | S2-T17 states 146 months; activity/municipality run and receipt chain unverified |
| licence_cancellations / lic_cancelled | pub_licence_cancelled; month; count | S2-T17 states 111 months; per-key continuity, bulk flags and receipts unverified |
| property_prices / prop_sales | pub_property_sale; year; qar_per_m2 | Six years including a partial first year; too few conformal targets even at that upper bound |
| hotel_demand / hotel_segment | pub_hotel_monthly; month; row-carried demand unit | S2-T17 states 135 months; per-segment continuity, demand unit and receipts unverified |
| hotel_adr / hotel_segment | pub_hotel_monthly; month; row-carried adr unit | Separate measure; 135-month metadata does not establish a per-segment run or unit |
| announced_project_count / fdi_projects | fdi_projects; year; count | Nine years stated by S2-T17; too few conformal evaluation targets |
| announced_capex / fdi_projects | fdi_projects; year; currency/unit unverified | Nine years; too few targets; valuation, unit and receipt chain unverified |
| construction_pipeline / permits_muni completion-certificates dataset | pub_building_permits; year; count | Three years; series_too_short under the retained C30 minimum |
| consumer_prices / cpi_group | pub_price_index; month; unconfirmed | publisher_or_licence_unconfirmed retained from S2-T17 |
| producer_prices | no table; frequency/unit unconfirmed | no_source_table retained |
| imports_by_product / cus_imp_2019 and cus_imp_2025 | pub_customs_import; month; row-carried unit/currency/valuation | past_count_not_stated retained; HS revision per period and mapping unverified; never stitch the two sources |
| expected_households_and_workers | no table; frequency/unit unconfirmed | no_conversion_parameter_source_table retained |
| property_prices_quarterly / prop_sales and prop_resi_units | pub_property_quarter; quarter; qar_per_sqft | awaiting_reviewed_use_map_and_district_crosswalk retained; no kept contiguous run established |
| establishments_by_area / register snapshots | pub_register_snapshot; month; count | Conditional route; no mounted monthly history or per-area continuity established |
| trade_ext / each of its four dataset keys | no release-table binding in registry; published year fields, unit unverified | S2-T19 blocked: source wiring, frequency, unit, receipts and per-category runs await confirmation |
| un_comtrade | pub_comtrade_trade; frequency/unit/HS revision unconfirmed | S2-T23 blocked: registry metadata pending; no cache or history read |
| cepii_baci | pub_baci_trade; year contract, unit/HS revision unconfirmed | S2-T24 blocked: baci.yaml confirmed=false, blank source version, publisher hash and HS revision |
| atlas_complexity | finished country/product and country/partner/product tables; year contract; measure unit unconfirmed | S2-T25 blocked: atlas.yaml confirmed=false, downloads, mapping, version and hashes pending |
| trade_logistics / annual-certificates-of-origin-by-type-and-importing-country | pub_trade_logistics; year field; count | Registry span 2019 to 2024 only; at most six annual points; insufficient targets; receipts/continuity unverified; HS not applicable |
| wage_occ, wage_act, wage_sector | Registry's separate Public wage tables; source frequency and row-carried pay unit to confirm | Audit each source/category/sex split at its own national grain; source span is not a measured series run |
| comp_nat_act / each dataset | Registry's Public employee/compensation tables; frequency and row units to confirm | Each source/activity/nationality measure separate; no measured contiguous run or receipt chain |
| est_size_act / each dataset; sec_hr_size | Registry's Public establishment/employee/size tables; frequency and row units to confirm | Each source size class/measure separate; no measured contiguous run or receipt chain |

Publisher and licence are retained in the registry, including the National
Planning Council's portal trade rows and Qatar Chamber of Commerce & Industry's
certificates row (CC-BY-4.0 as registered). Pending publishers/terms are not
invented or treated as a licence gate. No public sex/nationality split is joined
to generated data; no published category or geography is apportioned.

## Generated families and F audit

The seven separate catalogue keys are pay_level (qar_per_month), earner_count
(count), wage_bill (qar), stayer_index (index), employment_by_area (count),
employment_by_occupation_residence (count), and
employment_by_occupation_workplace (count). All are monthly. Source feeds,
release tables, allowed unit sets, partition keys and shape restrictions are
recorded per key in the S6-T25 audit and `c30-series-v3`; HS is not applicable.
They share the existing release input contract, never person records.

S6-T25 reports a configured capacity of 23 months, with 22 adjacent stayer pairs;
these are capacities, not observed lengths. With first origin 13 and nine earlier
monthly residuals needed, capacity permits at most one eligible target for a
level of 9/10 (none for the stayer pairs). A single such series cannot supply the
minimum 12. No pool across protected windows is allowed. A family of several
lawful series would still require each run and its fixed membership audited.
Actual released histories, receipt chains and full source-to-release substitution
remain **blocked**, as S6-T25 explicitly records. No fit proves those dependencies.

F is available for bounded calculation fixtures: one ordered period/value row
per series, a fixed unit/geography/partition, and the existing feed/table
identities. Actual go-live volumes and complete generator/protection swap parity
remain blocked with their owners in S6-T25. Invented real-shaped fixtures use the
same harness entry point; they do not claim full pipeline or real-source parity.

## Stopping and independent fixture work

No Public or released-family acceptance run is authorised by this audit. Missing
continuity, unit, HS mapping or complete lineage stops that family with its
reason. Unknown values remain unknown. Under L-1228 point 11, independent harness
proof proceeds on invented/generated fixtures only. Frozen initial-prefix scale,
prospective selection and conformal intervals use `s6-t27-prefix-mase-v1` under
evals; production C30 and its fixtures are unchanged. The return proposes open
items for the lead; TASKS.md criteria remain unticked.
