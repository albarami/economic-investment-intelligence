# 04 — Public Data Pack

| | |
|---|---|
| Status | Draft v0.3, amended by decisions 0016, 0017 and 0019 on 2026-11-12 |
| Date | 2026-11-12 |
| Owner | albarami |
| Purpose | Define every public source the product uses, how it is fetched, licensed, checked, crosswalked and attributed, and what public data cannot give. |
| Read first | [01 Project brief](01_PROJECT_BRIEF.md), [02 Architecture](02_ARCHITECTURE.md), [03 Data contracts](03_DATA_CONTRACTS.md), [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), [decision 0017](decisions/0017-public-data-additions-and-public-splits.md), [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) |

## In brief

- Every figure marked Public comes from a source in the registry below, with URL, licence (or
  basis of use), retrieval date and SHA-256 recorded at fetch time. Nothing is fetched at run time,
  with one named exception: the optional live traffic provider of PUB-95, off by default, which
  stores nothing of a response.
- Fetchers run only in `./eii build-public`, only against an allow-list of hosts, and fail loudly.
  The traffic provider module is not a fetcher of `build-public` and has its own list of hosts
  (PUB-95).
- [Decision 0017](decisions/0017-public-data-additions-and-public-splits.md) adds 77 portal
  datasets in seventeen groups (property sales, venue visits, building permits, employer scale,
  manufacturing, trade, logistics, population, workforce, pay, students and visitors), which the
  registry holds as eighteen source-id families because the decision's group of museum and
  health-centre visits uses two, and two investment sources: the FDI projects dashboard, read on
  every build, and the sector, opportunity, incentive, set-up and law pages of the national
  investment promotion agency. Capex and jobs keep the source's note that they are estimates.
- [Decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) adds
  seven source ids beside the eighteen families: `traffic_tomtom_flow` and `traffic_tomtom_range`
  (a live traffic provider, used only in a session, nothing cached) and five that
  `./eii build-public` fetches: `busy_gmaps` (relative busyness by hour of named venues),
  `ntl_blackmarble` (night-time radiance), `places_fsq` (a further source of the places layer,
  read from its public copy on Source Cooperative without an account), `worldpop_qat_agesex` (population by age and sex on a 100 m
  grid) and `weather_openmeteo` (hourly weather history). The series that tested code forecasts, and
  the source table that holds each, are listed in section 12 (PUB-103), with the released monthly
  series that the same code also forecasts.
- A source without stated reuse terms is validation-only: no value, derived share, title or
  geometry from it enters a release. The only exceptions are the two investment sources, the
  census map layers and `busy_gmaps`, used by the owner's decisions of 2026-11-12 for this personal
  internal project; decision 0017 item 10 closes OI-04 for version 1, and decision 0019 item 19
  names `busy_gmaps`, whose publisher's terms name automated reading (PUB-12). Nothing fetched
  from them is committed, and the archived census 2020 workbook stays validation-only.
- Official figures split by sex or nationality are Public facts, shown only as published, with
  source and year. They are never joined to a synthetic record, used to segment synthetic records,
  combined with a protected figure or apportioned to a drawn area. The one case that is not an
  apportionment is the sum of whole cells of the published age-and-sex population grid over a
  chosen area, for display only (PUB-99).
- A drawn area counts Public points inside it exactly. A statistic published on an official
  geography stays on that geography, or is labelled Inferred where it is apportioned to the shape.
- The verified figures of the master design are regression examples: each has a dataset and an
  exact check. Two public figures conflict (OI-03) and are blocked from display until reconciled.
- Work in slice S2 also builds the frame (zones, districts, municipalities, gazetteer, crosswalks), the
  activity spine, the customs baskets, the hand-verified places of four showcase areas, the venue
  crosswalk, the two page parsers and the candidate record for the flagship building. Slice S2 also
  builds the fetchers and release tables of the five sources of decision 0019 that `build-public`
  fetches. The pooled hourly anchor, the weather profiles
  and the population grid as weights belong to the simulation slice S4; the provider switch, the
  layers and the 3D view belong to the map and journey slices ([TASKS.md](../TASKS.md),
  [14](14_IMPLEMENTATION_PLAN.md)).

## 1. Scope

This document owns the public half of the custodian plane: `custodian/publicdata/` (fetchers, page
parsers and review files) and the release tables whose names start `pub_`, plus `fdi_projects`, the
frame tables `zone`, `municipality`, `gazetteer` and the public parts of `graph_node`, `graph_edge`
and `source_registry`. Methods that compute on these tables (location quotients, pay decomposition,
break-even, bulk-month rule, co-location, apportioning to a drawn shape) are owned by
[07 Economic methods](07_ECONOMIC_METHODS.md). Fact fields, release-table columns and provenance
rules are owned by [03 Data contracts](03_DATA_CONTRACTS.md). The synthetic world reads this pack
but is specified in [05 Synthetic world and simulation](05_SYNTHETIC_WORLD_AND_SIMULATION.md).

Terms used here:

- **Portal**: the Qatar Open Data Portal, `www.data.gov.qa`, which serves datasets through an
  Explore API (version 2.1) and states a licence based on CC BY 4.0 (portal licence page, retrieved
  2026-11-11). The same portal answers the same API and slugs at `www.data.qa`
  ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)).
- **Public cache**: `data/public_cache/`, the local, uncommitted store of fetched files.
- **Registry**: the committed list of sources (`custodian/publicdata/sources.yaml`) and its copy in
  the release table `source_registry`.
- **Licence-activity count**: one activity on one commercial licence. It is not a firm, an
  establishment or a job.
- **Investment sources**: `fdi_projects` (the FDI projects dashboard) and `investqa_pages` (the
  sector, opportunity, incentive, set-up and law pages of the national investment promotion
  agency), used by the owner's decision of 2026-11-12 (PUB-12).
- **Public split**: an official figure split by sex or nationality. It is only ever a Public fact
  (PUB-90).
- **Traffic provider**: the optional live source of traffic flow tiles and traffic-aware
  drive-time areas, used only in a session when `EII_TRAFFIC_PROVIDER` is `tomtom` (PUB-95).
- **Relative busyness**: the published relative index (0 to 100) of how busy a named venue is by
  day of week and hour. It is a Public fact of the venue and never a count of people (PUB-101).

```mermaid
flowchart LR
  A["Allow-listed hosts"] -->|"build-public only"| B["public_cache: file and sidecar"]
  B --> C["Parsers and checks: licence or basis, schema, rows, regression"]
  C --> D["Reviewed configs: spine, baskets, places, crosswalks"]
  D --> E["Release: pub tables, frame, graph, source_registry"]
  E --> F["Product plane: read-only, no network to sources, except the traffic provider module (PUB-95)"]
```

## 2. Source registry

Every source the master design and decisions 0016, 0017 and 0019 rely on is listed here. The key (first
column) is the `source_id` used in the registry, in lineage and in the evidence drawer. Portal
dataset identifiers are the slugs after `/explore/dataset/` in the URLs given by the project
research (retrieved 2026-11-11). Publisher names are those reported by the research; the fetcher
copies the publisher from the portal metadata at fetch time and fails if it differs (PUB-09).

[Decision 0017](decisions/0017-public-data-additions-and-public-splits.md) adds the rows from
`prop_resi_units` onwards: 77 portal datasets in the seventeen groups of the decision, represented
by eighteen source-id families because its group of museum and health-centre visits uses two
(`visits_museum` and `visits_phcc`), then the two investment sources. A source-id family is one
`source_id` with one registry entry per slug. The slugs, publishers, rows, coverage and modified
dates of the 77 datasets were read from the portal's catalogue and records on 2026-11-12, and the
fetcher records them again at every fetch (PUB-85).

[Decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) adds seven
source ids as the last rows of sections 2.1 and 2.2. Their facts were read from the publishers'
pages on 2026-11-12, without any key; a field those pages did not give is written "to be recorded
at the first fetch". The two ids of the live traffic provider (`traffic_tomtom_flow` and
`traffic_tomtom_range`) are not cached sources: they are listed here for their terms and attribution, and have no row in
`source_registry` and no file, because nothing of the provider is fetched into the cache (PUB-95).

### 2.1 Identity, fetch and licence

| source_id | Dataset | Publisher | How fetched | Licence |
|---|---|---|---|---|
| `lic_active` | Active certificates by municipality and business activity | Ministry of Commerce and Industry | portal `moci-active-certificates-by-municipality-and-business-activity` | CC BY (portal) |
| `lic_cancelled` | Cancelled certificates by municipality and business activity | Ministry of Commerce and Industry | portal `moci-canceled-certificates-by-municipality-and-business-activity` | CC BY (portal) |
| `lic_issued` | Issued certificates by municipality and business activity (incomplete) | Ministry of Commerce and Industry | portal `moci-issued-certificates-by-municipality-and-business-activity` | CC BY (portal) |
| `cus_imp_2025` | Qatar Imports 2025-2026 | National Planning Council | portal `qatar-imports-2025-2026` | CC BY (portal) |
| `cus_imp_2019` | Qatar Imports 2019-2024 | National Planning Council | portal `qatar-imports-2019-2024-copy` | CC BY (portal) |
| `sec_hr_ind` | Hotels and restaurants: economic indicators by activity | National Planning Council | portal `hotels-and-restaurants-statistics-economic-indicators-in-hotels-and-restaurants-by-activity1` | CC BY (portal) |
| `sec_hr_goods` | Hotels and restaurants: intermediate goods by type | National Planning Council | portal `hotels-and-restaurants-statistics-estimates-of-intermediate-goods-value-in-hotels-and-restaurants-by0` | CC BY (portal) |
| `sec_hr_serv` | Hotels and restaurants: intermediate services by type | National Planning Council | portal `hotels-and-restaurants-statistics-estimates-of-intermediate-services-value-in-hotels-and-restaurants0` | CC BY (portal) |
| `sec_hr_size` | Hotels and restaurants: establishments and employees by size | National Planning Council | portal `hotels-and-restaurants-number-establishments-employees-by-size-of-establishment-economic-activity` | CC BY (portal) |
| `sec_hr_comp_occ` | Hotels and restaurants: compensation by occupation | National Planning Council | portal `hotels-and-restaurants-statistics-estimates-of-compensation-in-hotels-and-restaurants-by-occupation1` | CC BY (portal) |
| `wage_occ` | Workers in paid employment and monthly average wage by gender and occupation | National Planning Council | portal `workers-in-paid-employment-15-years-and-above-and-monthly-average-wage-q1` | CC BY (portal) |
| `wage_act` | Workers in paid employment and monthly average wage by gender and economic activity | National Planning Council | portal `workers-in-paid-employment-15-years-and-above-and-monthly-average-wage-q` | CC BY (portal) |
| `wage_sector` | Workers in paid employment and average monthly wage by gender and sector | to be confirmed at slice S2 | portal `workers-in-paid-employment-and-average-monthly-wage-by-gender-and-sector` | CC BY (portal) |
| `wage_bands_priv` | Average monthly wage for workers in the private sector | to be confirmed at slice S2 | portal `average-monthly-wage-q-r-for-workers-in-private-sector-in-qatar-2021-2025` | to be confirmed at slice S2 |
| `work_hours_act` | Employed persons and average work hours by gender and economic activity | to be confirmed at slice S2 | portal `employed-persons-15-years-and-above-and-average-work-hours-by-gender-and-economic-activity` | to be confirmed at slice S2 |
| `util_elec` | Electricity total consumption by zone number | Kahramaa | portal `electricity-total-consumption-by-zone-number` | CC BY (portal) |
| `util_water` | Water total consumption by zone number | Kahramaa | portal `water-total-consumption-by-zone-number` | CC BY (portal) |
| `transit_monthly` | Public Transport Users | Ministry of Transport | portal `public-transport-users` | CC BY (portal) |
| `hotel_segment` | Accommodation data by segment (supply, demand, occupancy, ADR, RevPAR) | Qatar Tourism | portal `accommodation-data-by-segment-date-and-key-metrics-supply-demand-occupancy-adr-revpar` | CC BY (portal) |
| `cpi_group` | Consumer price index by expenditure group, monthly | to be confirmed at slice S2 | portal `consumer-price-index-cpi-by-expenditure-group-monthly` | CC BY (portal) |
| `prop_sales` | Weekly Real Estates Sales Bulletin | Ministry of Justice | portal `weekly-real-estates-sales-bulletin` | CC BY (portal) |
| `pop_muni` | Population and labour force by municipality | National Planning Council | portal `population-and-labour-force-by-municipality` | CC BY (portal) |
| `zone_population` | Population, area and population density by zone | to be confirmed at slice S2 | portal `population-area-and-population-density-per-square-kilometers-by-zone` | to be confirmed at slice S2 |
| `est_census` | Number of business establishments by economic activity in census (2010, 2020) | to be confirmed at slice S2 | portal `number-of-business-establishments-by-economic-activity-in-census-2010-2020` | CC BY (portal) |
| `census_hh_type_2020` | Population by type of household, gender and place of residence on the census night, December 2020 | to be confirmed at slice S2 | portal `population-by-type-of-household-gender-and-place-of-residence-on-the-census-night-december-2020` | to be confirmed at slice S2 |
| `accident` | Accident | to be confirmed at slice S2 | portal `accident` | to be confirmed at slice S2 |
| `census_2020_workbook` | Census 2020 detailed results workbook, Tables 1, 2, 151 and 152 | Planning and Statistics Authority | archived copy at `web.archive.org/web/20240422094401/https://www.psa.gov.qa/Style%20Library/PSA/CensusDetailedResults/documents/Qatar_Census_2022_Final_Results.xlsx` | none stated (OI-04) |
| `worldpop_qat_2020` | Constrained 100 m gridded population, 2020 | WorldPop | `https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2020/QAT/v1/100m/constrained/` | CC BY 4.0 |
| `census_zone_sector` | Census 2020 employed population by major economic sector, by zone | statistics authority public map service | `services7.arcgis.com/mffQJB8rpVa5We20/arcgis/rest/services/Population_by_Major_Economic_Sectors_by_Zone_2020_WFL1/FeatureServer` | none stated (OI-04) |
| `census_zone_occ` | Census 2020 employed population by occupation, by zone | statistics authority public map service | `.../Employed_Population_by_Occupation_by_Zone_2020_WFL1/FeatureServer` | none stated (OI-04) |
| `census_zone_hh` | Census 2020 residence for households, by zone | statistics authority public map service | `.../Residence_for_Households_by_Zone_2020_WFL1/FeatureServer` | none stated (OI-04) |
| `census_zone_lab` | Census 2020 residence for workers (labourer groups), by zone | statistics authority public map service | `.../Residence_for_Workers_Labourer_Groups_by_Zone_2020_WFL1/FeatureServer` | none stated (OI-04) |
| `census_district_pop` | Census 2020 population, district level | statistics authority public map service | `.../Population_2020_District_Level/FeatureServer` | none stated (OI-04) |
| `bnd_zone_2020` | Zone_Boundary_2020 (map layer) | statistics authority public map service | `.../Zone_Boundary_2020/FeatureServer` | none stated (OI-04) |
| `bnd_district_2020` | District_2020 (map layer) | statistics authority public map service | `.../District_2020/FeatureServer`; the registry records `layer` 12, the id of District_Boundary_2020, the only layer of this service (the other six map services each have one layer, at id 0) | none stated (OI-04) |
| `bnd_hdx` | Qatar Subnational Administrative Boundaries (COD-AB) | HDX, source Planning and Statistics Authority | landing page `https://data.humdata.org/dataset/cod-ab-qat`; direct machine-readable URL to be confirmed at slice S2 | CC BY-IGO |
| `bnd_muni_2025` | Municipalities in Qatar 2025 | to be confirmed at slice S2 | portal `municipalities-in-qatar-2025` | portal terms only (PUB-12) |
| `bnd_geob` | geoBoundaries Qatar ADM1, ADM2 (fallback only) | geoBoundaries | `https://www.geoboundaries.org/api/current/gbOpen/QAT/ALL/` | CC BY 4.0 |
| `places_ovt` | Overture Places, release 2026-10-21.0, schema 2.0.0 | Overture Maps Foundation (per-record sources) | `s3://overturemaps-us-west-2/release/2026-10-21.0/theme=places/type=place/`, STAC `https://stac.overturemaps.org/2026-10-21.0/catalog.json` | CDLA Permissive 2.0 per source; Foursquare records Apache 2.0; AllThePlaces CC0 1.0 |
| `bldg_ovt` | Overture Buildings, release 2026-10-21.0 (named showcase buildings only) | Overture Maps Foundation | same release, `theme=buildings` | ODbL (theme licence) |
| `roads_osm` | OpenStreetMap Qatar extract (road network) | OpenStreetMap contributors | `https://download.openstreetmap.fr/extracts/asia/qatar-latest.osm.pbf` | ODbL 1.0 |
| `cls_isic4` | ISIC Rev.4 structure (English titles) | United Nations Statistics Division | landing page `https://unstats.un.org/unsd/classifications/Econ`; direct machine-readable URL to be confirmed at slice S2 | UN terms of use; no open licence stated |
| `ref_min_wage` | Qatar minimum wage (Law No. 17 of 2020), reference page | International Labour Organization | citation only: `https://www.ilo.org/resource/news/qatar-adopts-non-discriminatory-minimum-wage` | to be confirmed at slice S2 |
| `ref_wps_report` | Wage Protection Systems in the Gulf Cooperation Council Countries, November 2025 | International Labour Organization | citation only: `https://www.ilo.org/sites/default/files/2025-11/ILO_Beirut_Wage-Protection_Report_R10.pdf` | to be confirmed at slice S2 |
| `ref_expansion_method` | Mobility study methodology v3 | Spanish Ministry of Transport | citation only: `https://ropenspain.github.io/spanishoddata/codebooks/mitma_-_estudio_movilidad_covid-19_informe_metodologico_v3_en.pdf` | to be confirmed at slice S2 |
| `ref_gov_hours` | Flexible working system for the government sector | The Peninsula | citation only: `https://thepeninsulaqatar.com/article/04/09/2024/cgb-announces-flexible-remote-work-system-for-qatar-government-sector` | to be confirmed at slice S2 |
| `ref_friday_closure` | Services exempted from closure during Friday prayers | The Peninsula | citation only: `https://thepeninsulaqatar.com/article/17/08/2025/over-10-services-in-qatar-exempted-from-closure-during-friday-prayers-gazette` | to be confirmed at slice S2 |
| `ref_transit_hours` | Metro and tram service hours from 1 January | Qatar Tribune | citation only: `https://qatar-tribune.com/article/156642/front/metro-tram-service-hours-extended-from-january-1` | to be confirmed at slice S2 |
| `ref_summer_work` | Regulated outdoor summer working hours from 1 June | The Peninsula | citation only: `https://www.thepeninsulaqatar.com/article/31/05/2026/regulated-outdoor-summer-working-hours-come-into-force-on-june-1-in-qatar` | to be confirmed at slice S2 |
| `ref_truck_hours` | Restriction on trucks and large buses within Doha | The Peninsula | citation only: `https://thepeninsulaqatar.com/article/01/06/2024/restriction-on-movement-of-trucks-and-large-buses-within-doha:-traffic-department` | to be confirmed at slice S2 |
| `ref_ramadan_public_hours` | Reduced public-sector hours during Ramadan | Qatar News Agency | citation only: `https://qna.org.qa/en/News-Area/News/2026-2/16/qatar-sets-reduced-working-hours-for-public-sector-during-ramadan` | to be confirmed at slice S2 |
| `ref_ramadan_private_hours` | Ramadan working hours for the private sector | The Peninsula | citation only: `https://s.thepeninsula.qa/article/14/02/2026/ministry-of-labour-announces-ramadan-working-hours-for-private-sector` | to be confirmed at slice S2 |
| `ref_ramadan_transit_hours` | Metro and tram Ramadan hours | The Peninsula | citation only: `https://s.thepeninsula.qa/article/17/02/2026/doha-metro-and-lusail-tram-announce-operating-hours-in-ramadan` | to be confirmed at slice S2 |
| `ref_traffic_index` | Doha Traffic Index 2025 | TomTom | citation only: `https://www.tomtom.com/traffic-index/city/doha/` | proprietary publication; citation-only plausibility comparison |
| `prop_resi_units` | Residential unit sales, weekly bulletin | Ministry of Justice | portal `weekly-residential-units-sales-bulletin` | CC BY (portal) |
| `visits_museum` | Visitors of museums and exhibitions by month and museum | National Planning Council | portal `visitors-of-museums-and-exhibition-by-month-and-museum` | CC BY (portal) |
| `visits_phcc` | Patient visits by health centre and region | Primary Health Care Corporation | portal `phcc-patient-visits-by-health-center-and-region` | CC BY (portal) |
| `permits_muni` | Building permits and completion certificates: totals by municipality and building type, and monthly permits by type for each municipality | National Planning Council | portal `total-building-permits-issued-by-municipality-and-type-of-building-type-of-permit`, `total-building-completion-certificates-issued-by-municipality-and-type-of-building-type-of`, `building-permits-issued-by-type-of-permit-and-month-al-daayen-municipality`, `building-permits-issued-by-type-of-permit-and-month-al-khor-and-al-thakhira-municipality`, `building-permits-issued-by-type-of-permit-and-month-al-rayyan-municipality`, `building-permits-issued-by-type-of-permit-and-month-al-shahhaniya-municipality`, `building-permits-issued-by-type-of-permit-and-month-al-shamal-municipality`, `building-permits-issued-by-type-of-permit-and-month-al-wakrah-municipality`, `building-permits-issued-by-type-of-permit-and-month-doha-municipality`, `building-permits-issued-by-type-of-permit-and-month-umm-slal-municipality` | CC BY (portal) |
| `est_size_act` | Establishments and employees by size of establishment and activity, with compensation | National Planning Council | portal `number-of-establishments-and-employees-by-size-of-establishment-and-main-economic-activity-two`, `number-of-establishments-and-employees-by-size-of-establishment-and-main-economic-activity-wholesale-and-retail-trade-four-digits`, `number-of-establishments-and-employees-by-size-of-establishment-and-main-economic-activity-transport`, `number-of-establishments-and-employees-by-size-of-establishment-and-main-economic-activity-social-and-personal-services-two-digits`, `number-of-establishments-and-employees-by-size-of-establishment-and-main-economic-activity-energy`, `number-of-establishments-and-employees-by-size-of-establishment-and-main-economic-activity-one`, `establishments-employees-and-compensation-of-employees-by-economic-activity-business-services` | CC BY (portal) |
| `mfg_industry` | Manufacturing industries (one dataset per industry) and main manufacturing products | Ministry of Commerce and Industry (industry datasets); National Planning Council (`main-manufacturing-products`) | portal `manufacture-of-basic-metals`, `manufacture-of-basic-pharmaceutical-products-and-pharmaceutical-preparations`, `manufacture-of-beverages`, `manufacture-of-chemicals-and-chemical-products`, `manufacture-of-coke-and-refined-petroleum-products`, `manufacture-of-computer-electronic-and-optical-products`, `manufacture-of-electrical-equipment`, `manufacture-of-fabricated-metal-products-except-machinery-and-equipment`, `manufacture-of-food-products`, `manufacture-of-furniture`, `manufacture-of-leather-and-related-products`, `manufacture-of-machinery-and-equipment-nec`, `manufacture-of-manufacture-of-wood-and-of-products-of-wood-and-cork-except-furniture-manufacture`, `manufacture-of-motor-vehicles-trailers-and-semi-trailers`, `manufacture-of-other-non-metallic-mineral-products`, `manufacture-of-other-transport-equipment`, `manufacture-of-paper-and-paper-products`, `manufacture-of-rubber-and-plastics-products`, `manufacture-of-textiles`, `manufacture-of-wearing-apparel`, `main-manufacturing-products` | CC BY (portal) |
| `trade_wr` | Purchases, sales and stocks during the year by type of trade, wholesale and retail | National Planning Council | portal `purchases-sales-and-stocks-during-the-year-by-type-of-trade-wholesale-and-retail-trade-all` | CC BY (portal) |
| `pop_muni_age` | Population by municipality and age groups | National Planning Council | portal `population-by-municipality-and-age-groups` | CC BY (portal) |
| `hotels_muni` | Hotels and hotel apartments by municipality | National Planning Council | portal `hotels-and-hotel-apartments-by-municipality` | CC BY (portal) |
| `trade_logistics` | Certificates of origin by importing country; arriving vessels by previous port and by registration | Qatar Chamber of Commerce & Industry (certificates of origin); National Planning Council (vessels) | portal `annual-certificates-of-origin-by-type-and-importing-country`, `arriving-vessels-gross-and-net-tonnage-by-type-of-vessel-and-country-of-previous-port`, `arriving-vessels-gross-and-net-tonnage-by-type-of-vessel-and-country-of-registration-hamad-port0` | CC BY (portal) |
| `est_census_2015_muni` | Business establishments and employees by municipality, census 2015 | National Planning Council | portal `distribution-of-business-establishments-and-employees-by-municipalities-according-to-census-2015` | CC BY (portal) |
| `lf_muni_sex` | Population, labour force, employed and unemployed persons by sex and municipality | National Planning Council | portal `female-population-and-labour-force-by-municipality`, `male-population-and-labour-force-by-municipality`, `employed-persons-15-years-and-above-by-gender-and-municipality`, `unemployed-persons-15-years-and-above-by-gender-and-municipality` | CC BY (portal) |
| `pop_muni_age_sex` | Population by municipality, age group and sex | National Planning Council | portal `females-population-by-municipality-and-age-groups-december-2020`, `males-population-by-municipality-and-age-groups-december-2020` | CC BY (portal) |
| `active_sex_age_act` | Economically active females and males by age group and economic activity | National Planning Council | portal `economically-active-females-15-years-and-above-by-age-group-and-economic-activity`, `economically-active-males-15-years-and-above-by-age-group-and-economic-activity` | CC BY (portal) |
| `active_nat_occ_act` | Economically active Qatari and non-Qatari population by occupation and economic activity (all, males, females) | National Planning Council | portal `economically-active-non-qatari-females-15-years-and-above-by-occupation-and-economic-activity`, `economically-active-non-qatari-males-15-years-and-above-by-occupation-and-economic-activity`, `economically-active-non-qatari-population-15-years-and-above-by-occupation-and-economic-activity`, `economically-active-qatari-females-15-years-and-above-by-occupation-and-economic-activity`, `economically-active-qatari-males-15-years-and-above-by-occupation-and-economic-activity`, `economically-active-qatari-population-15-years-and-above-by-occupation-and-economic-activity` | CC BY (portal) |
| `comp_nat_act` | Employees and compensation of employees by nationality and main economic activity (one dataset per survey sector) | National Planning Council | portal `number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity`, `number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-building`, `number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-business`, `number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-energy`, `number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-energy0`, `number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-energy1`, `number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-one`, `number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-social`, `number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-social0`, `number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-social1` | CC BY (portal) |
| `students_muni` | Students by level of education, municipality, sex, type of education and nationality | Ministry of Education and Higher Education | portal `students-by-level-of-education-municipality-gender-type-of-education-and-nationality-2025-2026` | CC BY (portal) |
| `visitors_markets` | Hotel guests by nationality, hotel rating and stays; visitor arrivals | National Planning Council (hotel guests; arrivals by mode of entry and by region); Qatar Tourism (arrival trends by mode of transport) | portal `hotel-guests-by-nationality-hotel-rating-and-hotel-stays`, `visitor-arrivals-by-mode-of-entry`, `visitor-arrivals-by-region`, `visitor-arrivals-trends-by-mode-of-transport-air-land-sea` | CC BY (portal) |
| `fdi_projects` | FDI projects dashboard: announced investment projects, data from fDi Markets | National investment promotion agency | page `https://fdiprojects.invest.qa/`, read on every build and parsed by the FDI page parser (PUB-86, PUB-87) | publisher's own terms as read at fetch; basis of use: owner decision of 2026-11-12 for this personal internal project (PUB-12); the terms of use (`https://www.invest.qa/en/terms-and-conditions?tab=terms-of-use`), read on 2026-11-13, allow copies for personal and non-commercial use while viewing and say that the material should not be copied, modified or reproduced in whole or in part without the publisher's prior written permission and an acknowledgement of the source, so the build switches this source off at fetch, stores nothing of it and names it, until the owner decides (OI-128) |
| `investqa_pages` | Sector, opportunity, incentive, set-up and law pages | National investment promotion agency | pages of `https://www.invest.qa/`, parsed by the agency page parsers (PUB-86, PUB-88); page list confirmed at slice S2 | as `fdi_projects` |
| `traffic_tomtom_flow` | Traffic flow tiles (live layer; nothing cached) | TomTom | live session only, by the traffic provider module (PUB-95) when `EII_TRAFFIC_PROVIDER` is `tomtom`, with `TOMTOM_API_KEY` from the environment; documentation `https://docs.tomtom.com/traffic-api/` and pricing page `https://docs.tomtom.com/pricing`, read 2026-11-12; the provider's host is fixed by the task that builds the module and added to the module's own list by a reviewed registry change | provider terms (`licence_basis: provider_terms`): free monthly allowance of 200,000 tile requests (read 2026-11-12); attribution "© TomTom" while the layer is on; the provider's terms (`https://docs.tomtom.com/legal/terms-and-conditions`, no date or version on the page; read in full on 2026-11-13) license the free plan "for Evaluation Use only", "internal evaluation and testing by you of the Licensed Products" (clause 2.2 and its definitions); they prohibit caching or storing any results except in a client under the result's cache-control headers and never to serve several users (clause 11.4), and nothing is stored; the logos and copyright notices the provider's interfaces generate are kept and other attribution comes from its copyright interface (clause 17.3); the page says nothing on showing the layer beside other map data; showing the layer outside internal evaluation is the owner's decision (OI-130) |
| `traffic_tomtom_range` | Traffic-aware drive-time areas (reachable range; live, nothing cached) | TomTom | as `traffic_tomtom_flow` | provider terms: free monthly allowance of 2,500 reachable-range requests (read 2026-11-12); attribution and storage as `traffic_tomtom_flow` |
| `busy_gmaps` | Google Maps popular times: relative busyness by hour of named venues | Google | the project's own page reader inside `./eii build-public`, for the named venues of a build-time list, never at run time (PUB-101); publisher page "About popular times, wait times and visit duration data", `https://support.google.com/business/answer/6263531`, read 2026-11-12; host to be recorded at the first fetch | no licence for reuse stated; the publisher's terms (`https://policies.google.com/terms` and the Maps additional terms `https://www.google.com/intl/en/help/terms_maps/`, read 2026-11-12) name automated reading and bulk feeds; used by the owner's decision of 2026-11-12, `licence_basis: owner_decision`, named by decision 0019 item 19 (PUB-12) |
| `ntl_blackmarble` | NASA Black Marble VNP46A3: night-time lights, monthly, on a 15 arc-second grid (about 500 m) | NASA | inside `./eii build-public` with the Earthdata token `EARTHDATA_API_KEY` from the environment; product page `https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VNP46A3/` (DOI 10.5067/VIIRS/VNP46A3.002), read 2026-11-12; download host to be recorded at the first fetch | NASA data and information guidance (`https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-information-policy`, read 2026-11-12): NASA acknowledged as the source and the product DOI cited; further terms to be recorded at the first fetch |
| `places_fsq` | Foursquare Open Source Places (public copy on Source Cooperative) | Foursquare | inside `./eii build-public`, from the public copy on Source Cooperative, `https://data.source.coop/fused/fsq-os-places/` (host `data.source.coop`, PUB-03), geospatially partitioned GeoParquet, read without an account; only the files that cover Qatar are fetched (**ASSUMPTION**: found through the dataset's own metadata file; the task that builds the fetcher confirms it); the release used is recorded in the registry and shown with the places; the copy's README `https://data.source.coop/fused/fsq-os-places/README.md` and the access page `https://docs.foursquare.com/data-products/docs/access-fsq-os-places`, read 2026-11-12 | Apache License, Version 2.0, with the publisher's copyright line, as the copy's README states them (read 2026-11-12); the listing holds three dated releases, the newest dated 2025-01-10, and states no update rhythm |
| `worldpop_qat_agesex` | WorldPop age and sex structures, 100 m grids, Qatar | WorldPop | inside `./eii build-public`; pages `https://hub.worldpop.org/project/categories?id=8` and `https://hub.worldpop.org/geodata/listing?id=138`, read 2026-11-12; file URL, host and year to be recorded at the first fetch | CC BY 4.0 (DOI 10.5258/SOTON/WP00841) |
| `weather_openmeteo` | Open-Meteo historical weather, hourly | Open-Meteo | inside `./eii build-public`, into the public cache as a hashed file; documentation `https://open-meteo.com/en/docs/historical-weather-api`, terms `https://open-meteo.com/en/terms` and licence page `https://open-meteo.com/en/licence`, read 2026-11-12; host, location and variables to be recorded at the first fetch | free interface for non-commercial use (`licence_basis: provider_terms`); data CC BY 4.0, with the attribution the publisher asks for |

The `.../` prefix in census and boundary rows is
`https://services7.arcgis.com/mffQJB8rpVa5We20/arcgis/rest/services/`. A portal identifier is
fetched as `https://<host>/api/explore/v2.1/catalog/datasets/<id>/exports/json`, and its
metadata (licence, modified date, publisher) from
`https://<host>/api/explore/v2.1/catalog/datasets/<id>`, where `<host>` is `www.data.gov.qa` or
`www.data.qa` (URL pattern as used by the project research, 2026-11-11; the second host by
decision 0017). A slug names the same dataset on either host, and the registry records the host
that served each file (PUB-03). The investment sources are fetched as pages from their own hosts
and parsed by the page parsers of section 3.2. The sources of decision 0019 are fetched as PUB-95
to PUB-97, PUB-101 and PUB-102 say.

### 2.2 Coverage, use and traps

Coverage facts of the rows above `prop_resi_units` are from the project research, retrieved
2026-11-11. Those of the eighteen source-id families of decision 0017 were read from the portal's
catalogue and records on 2026-11-12; where a family holds several slugs, rows are given per slug,
and modified dates per slug or as the range they span. Those of the two investment sources come
from the dashboard page, read 2026-11-12, and from
[decision 0017](decisions/0017-public-data-additions-and-public-splits.md). Those of the seven
sources of decision 0019 come from the publishers' pages read on 2026-11-12 (section 2.1). All must
be re-recorded by the fetcher.

| source_id | Coverage, grain, last period | Product use | Release table | Known traps |
|---|---|---|---|---|
| `lic_active` | Snapshot "as of May 2025"; municipality x activity code; 13,189 rows; modified 2025-08-04 | capability M3 licences against national rate; capability S1 context; capability S8 denominator; spine input; stock count for the denominator of a base rate where card C31 allows it (PUB-104) | `pub_licence_active` | Arabic names only; 8 municipalities, nothing inside one; 6-digit legacy codes do not follow ISIC; codes predate the June 2026 recoding; not comparable with census establishments |
| `lic_cancelled` | 2015 to May 2025; year-month x municipality x code; 40,472 rows | capability S8 churn with bulk months flagged; D6 licence cancellations over time on the map (PUB-94); forecast input (card C30) and numerator of the licence cancellation rate (card C31), by activity and municipality (PUB-103, PUB-104) | `pub_licence_cancelled` | 1,221 rows (7,386 licences) undated; July 2020 holds 40,791 cancellations; three months hold 43% of dated cancellations, so the backtest and the rates handle the bulk months by the stated rule of the method cards, never silently |
| `lic_issued` | to May 2025; 8,259 rows; 610 codes only | D6 licence issues over time on the map, only for the codes it covers and always with its incompleteness note (PUB-94, [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 11); audit of incompleteness; forecast input (card C30) and numerator of the licence issue rate (card C31), only for the codes it covers, otherwise `NO_DATA` with the existing note (PUB-103, PUB-104) | `pub_licence_issued` | sums to 12,533; restaurants (5610101), cafeteria (5610201), general contracting (4100001) and foodstuff trade (4630901) absent; never compute net formation |
| `cus_imp_2025` | Jan 2025 to Feb 2026; 12-digit tariff line x origin x month; 252,048 rows; modified 2026-10-19 | capability S5 supplier lens; basket unit values; D7 import context and imports against local production with `mfg_industry`; forecast input (card C30) for imports by product, as one series with `cus_imp_2019` by the roll-up of PUB-44 | `pub_customs_import` | quantity units are not all kg; descriptions vary by year; bilingual origin names; the 2025 file alone holds 14 months |
| `cus_imp_2019` | 2019 to 2024; 8-digit lines; 830,494 rows | capability S5 trend before 2025; D7 imports against local production with `mfg_industry`; the earlier part of the forecast series of `cus_imp_2025` | `pub_customs_import` | coarser code than 2025 data: basket lines must roll up (PUB-44), and a forecast series built across the two files rolls the 12-digit lines up to the 8-digit code the same way and says so; slug ends in `-copy` |
| `sec_hr_ind`, `sec_hr_goods`, `sec_hr_serv`, `sec_hr_size` | annual 2018 to 2022; national; activities 551, 561, 562, 563 | capability M6 unit economics and break-even; `sec_hr_size` also employer scale by size class for restaurants and the other hotel and restaurant activities ([07](07_ECONOMIC_METHODS.md) C24); the benchmark of the revenue range of the user's outlet and of the category spend ranges of the site estimate (cards C35 and C33): revenue and costs per establishment, by activity, read from the fields of PUB-64 (the exact fields are recorded by slice S2) | `pub_sector_accounts`; `sec_hr_size` also `pub_establishment_size`, under its own `table_code` | latest year 2022 (a World Cup year); national averages over all outlet types; surplus share jumped after 2019 for an unexplained reason; restaurant revenue conflict (OI-03): while R1 is open the restaurant revenue figure is never the benchmark (PUB-75), and every range built on these tables says that it is national, of 2022 and over all outlet types |
| `sec_hr_comp_occ` | to 2022; national; occupation classes | capability S2 staffing context | `pub_wage_table` | national only |
| `wage_occ` | 2020 to 2025; national; 9 occupation groups x sex | capability S3 national pay card; capability S2 public mean | `pub_wage_table` | means only, no percentiles or area; implies a different 2020 mean from `wage_act` (OI-03) |
| `wage_act` | 2020 to 2023; national; 21 activity sections x sex | capability S2 context; D5 national wage trends by economic activity, with the split of the national change into within-sector and employment-mix components ([07](07_ECONOMIC_METHODS.md) C19, indicator 6 by sector); the only source of wage trends by sector in version 1, which holds no protected split by sector, so national by sector is the finest sector view ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 9) | `pub_wage_table` | as above; includes government and domestic work |
| `wage_sector` | 2017 to 2023; national; sector x sex | capability S2 context: covered private pay versus government pay | `pub_wage_table` | national only |
| `wage_bands_priv` | 2021 to 2025; private-sector wage bands | wage-band boundary source and calibration check | `pub_wage_table` | counts occupations, not workers; exact source columns and types to be confirmed at slice S2 |
| `work_hours_act` | published years and activity grain to be confirmed at slice S2 | simulated schedule anchor | none | exact source columns, types, coverage and last period to be confirmed at slice S2 |
| `util_elec`, `util_water` | annual 2021 to 2026 (2026 = Jan to Aug); about 91 zones | capability M3 zone momentum; opening scene | `pub_zone_utility` | activity proxy, not population; mixes residential, commercial, industrial and district-cooling load; zone numbers 10 and 11 have no 2020 polygon; 2026 partial |
| `transit_monthly` | Jan 2024 to Feb 2026; national by mode (bus, Metro, Lusail Tram) | capability M3; capability M2 public context | `pub_transit_monthly` | no station or hourly detail; Lusail Tram Jan 2026 (132,609) is far below neighbouring months: flag, do not explain |
| `hotel_segment` | Jan 2014 to Mar 2025; monthly by star class | capability M2 public context; forecast input (card C30) for hotel demand and room rate (PUB-103) | `pub_hotel_monthly` | ends March 2025; sample and census properties mixed; the series spans 2020 and the 2022 World Cup year, and the backtest, not a person, decides which model copes (card C30) |
| `cpi_group` | monthly 2020 to 2025 | capability M2 public context (restaurant and hotel prices); forecast input (card C30) for consumer prices; producer prices have no source table yet (open, section 12) | `pub_price_index` | seasonal; confirm the group code at fetch (research records "group 011"); a short series, so the backtest minimum of card C30 decides whether a forecast is returned |
| `prop_sales` | 5 Jul 2020 to 31 Dec 2025; transaction rows (26,719; 25,673 dated); 161 district names; modified 2026-08-31 | capability M3 sale price per square metre with deal count; forecast input (card C30) for the price per district, every forecast shown beside the deal count of its series (PUB-103) | `pub_property_sale` (aggregates only) | district names change after 2023 ('Lusail' becomes 'Lusail 69'); English property type mistranslated, use the Arabic field; few deals in Lusail; rows carry encrypted transaction and parcel identifiers that must not enter the release; a district series below the backtest minimum returns `NO_DATA` (reason key `series_too_short`) |
| `pop_muni` | 2020 to 2025; municipality | denominator for licences per 10,000 residents | `pub_population_municipality` | survey estimate; spelling variants of municipality names |
| `zone_population` | zone population snapshot; coverage and period to be confirmed at slice S2 | calibration cross-check | none until publisher, licence, columns and types are confirmed | no unconfirmed value enters a release |
| `est_census` | 2010 and 2020; national by activity group; 2020 total 71,203 | places coverage note; calibration ([05](05_SYNTHETIC_WORLD_AND_SIMULATION.md)) | `pub_census_national` | national only |
| `census_hh_type_2020` | Census night, December 2020; household type and place of residence | housing-class calibration | none until publisher, licence, columns and types are confirmed | expected source schema to be confirmed at slice S2 |
| `census_2020_workbook` | Census 2020; Tables 1, 2, 151 and 152 | zone totals, establishment size classes and municipal establishment counts for validation | none | no licence stated; validation-only; workbook sheet names, columns and types to be confirmed at slice S2 |
| `worldpop_qat_2020` | constrained 100 m grid, 2020 | relative within-zone family-housing weights, rescaled to separately anchored totals; relative weights for apportioning counts of people to a drawn shape ([07](07_ECONOMIC_METHODS.md) C18) and the free-flow demand layer of reachable access (C12), the only one in public-only mode, both confirmed at slice S2 | for C12, `access_score_grid` (the cell weights and free-flow scores of [03](03_DATA_CONTRACTS.md) DAT-154), once slice S2 confirms the file and licence for that use; for C18, none until slice S2 fixes, with the apportioning weight, how the weights enter the release | raster schema and file URL to be confirmed at slice S2; never treated as a 2025 population total; weights only, never a population figure on screen |
| `accident` | 2024 records with zone field | simulation plausibility hold-out | none | publisher, licence, exact source columns and types to be confirmed at slice S2 |
| `census_zone_*`, `census_district_pop` | December 2020; zone (91) or district (778 with population) | coverage geography and calibration; `census_district_pop` writes `pub_census_district` | `pub_census_zone`, `pub_census_district` | no licence stated for the source; used in the local release by [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 10 (OI-04 closed for version 1), each figure with its source and retrieval date, never committed (PUB-13); every release includes both tables |
| `bnd_zone_2020`, `bnd_district_2020` | 91 zones numbered within 1 to 99; 781 districts | validation of licensed frame geometry | none: the frame uses `bnd_hdx` | no licence stated; decision 0017 item 10 allows them in the local release, but version 1 uses them only to check `bnd_hdx` (PUB-13); never committed; zone numbers 8, 9, 10, 11, 59, 87, 88, 89 unused |
| `bnd_hdx` | 8 municipalities, 91 zones, 781 districts in the files; geometry dated 2015-11-30; modified 2026-08-19 | bilingual names; licensed geometry | `zone`, `municipality`, `gazetteer` | description says 87 zones and 718 districts, files hold 91 and 781; 2015 geometry: check Lusail against the 2020 layer |
| `bnd_muni_2025` | 8 municipality polygons | municipality geometry | `municipality` | no dataset-level licence metadata |
| `bnd_geob` | 8 municipalities, 79 zones (some merged, e.g. '18-19') | fallback if no licensed zone geometry | `zone` (fallback) | coarser, 2015 |
| `places_ovt` | 26,383 records with country QA (26,404 in the bounding box) | capability M3 named places with network distances; capability S9 neighbours; showcase verification; real business points on the map (PUB-92); venue points (PUB-89) | `pub_place` | incomplete (PUB-50); duplicates and junk records; Meta-dominated; taxonomy changed in late 2026; 'Italian' includes pizza through the category hierarchy; a further places source (`places_fsq`) brings its own categories, which map through a reviewed category mapping (PUB-102) |
| `bldg_ovt` | 4,400 footprints in the Lusail box; 73 with a height | flagship and showcase building points | `gazetteer` | most heights unknown; ODbL |
| `roads_osm` | Qatar; about 24.5 MB; changes daily | pyvalhalla graph for `walk` and `drive` areas and network distances; the real road network for simulated congestion by hour and for drive-time areas that change with the hour ([05](05_SYNTHETIC_WORLD_AND_SIMULATION.md), decision 0016); with the traffic provider switched on, traffic-aware drive-time areas also come from `traffic_tomtom_range` as areas of the session (PUB-95) | none (routing graph is a build artefact) | free-flow only; "latest" URL is not a version: the hash is the pin; ODbL share-alike |
| `cls_isic4` | ISIC Rev.4 classes (now a previous ISIC version on the UNSD page) | spine validity check; English class titles | `graph_node` | no Arabic file confirmed (open question); not committed |
| `ref_min_wage` | QAR 1,000 basic plus at least 500 housing and 300 food when not provided in kind | capability S2 statutory minimum line | `pub_wage_table` (one reference row) | a legal fact, not a survey figure; `public_document`, citation-only |
| `ref_wps_report`, `ref_expansion_method`, `ref_gov_hours`, `ref_friday_closure`, `ref_transit_hours`, `ref_summer_work`, `ref_truck_hours`, `ref_ramadan_public_hours`, `ref_ramadan_private_hours`, `ref_ramadan_transit_hours`, `ref_traffic_index` | citation-only public documents | calibration rules or plausibility context in [05](05_SYNTHETIC_WORLD_AND_SIMULATION.md) | none | registry metadata only; no fetched file or dataset schema; H4 road speed is a plausibility comparison, not a hold-out |
| `prop_resi_units` | 2025-08-24 to 2025-12-31; weekly bulletin rows of residential unit sales; 570 rows; modified 2026-08-31 | D2 district price layer beside the pay cards; D6; the reverse location view for property owners and developers | `pub_property_resi` (aggregates only) | encrypted transaction and parcel numbers are dropped before the release (PUB-14); few rows: every price shows its deal count; area names go through the district crosswalk (PUB-28); not the same dataset as `prop_sales`; 570 rows from 2025-08-24 only, so it is expected to fall below the backtest minimum of card C30 and a forecast then returns `NO_DATA` (reason key `series_too_short`) |
| `visits_museum` | 2013 to 2024; monthly by museum or exhibition; 1,372 rows; modified 2026-06-24 | published visitor counts of named public venues (`place_public`, PUB-91); the monthly shape calibrates and checks the simulated footfall ([05](05_SYNTHETIC_WORLD_AND_SIMULATION.md)) | `pub_venue_visits` | the count field is text: parsed by the build, and a value that does not parse fails it; venue names change between years: normalised through the venue crosswalk (PUB-89), never by hand |
| `visits_phcc` | 2020 to 2024, annual, years as columns; by health centre and region; 35 rows; modified 2025-05-28 | published patient visits of named health centres (`place_public`, PUB-91); annual cross-check of simulated presence near them | `pub_venue_visits` | annual only: no monthly shape; the build reads the year columns as periods |
| `permits_muni` | totals by municipality, building type and permit type, 2021 to 2023: permits 264 rows, completion certificates 240 rows, both modified 2026-06-05; monthly permits by type, one dataset per municipality, 2016 to 2023 with 288 rows each, except Al Shahhaniya (2017 to 2023, 252 rows); modified 2026-09-02, except Doha and Umm Slal (2026-08-31) | construction pipeline by municipality: D6, what changed, the reverse location view; forecast input (card C30) for the construction pipeline, the permits side of the expected new households and workers (PUB-103) | `pub_building_permits` | monthly series by municipality end in 2023, so any forecast starts from that last period (PUB-08, PUB-16); Al Shahhaniya starts in 2017; municipality spelling variants (PUB-27); the parameters that turn permits into households and workers have no registered source table yet (open, section 12) |
| `est_size_act` | national; establishments and employees by size of establishment and activity, one survey bulletin per sector; 2015 to 2022, except transport (2014 to 2019) and business services with compensation (2015 to 2021); rows: slug ending `-two` 556, wholesale and retail (four digits) 1,840, transport 356, social and personal services (two digits) 316, energy 2,912, slug ending `-one` 160, business services 324; modified 2026-08-27 to 2026-11-02 | employer scale and wage bill by activity: D1 market entry pack, D3 customer finder, S1, cases C1 and C2 | `pub_establishment_size` | survey bulletins by sector with different last years (transport ends 2019); national only; size-class labels differ between bulletins |
| `mfg_industry` | one dataset per manufacturing industry, rows by licence type, 2019 to 2025, 14 rows each (computer, electronic and optical products: 7), modified 2025-05-27 to 2026-11-03; main manufacturing products, 2016 to 2022, 35 rows, modified 2026-07-25 | industrial capacity per industry: D4 partner and supplier finder, S3, D7 imports against local production (with `cus_imp_2025` and `cus_imp_2019`), case C1 | `pub_manufacturing` | licence-type rows, not plants; investment in QAR million is cumulative licensed investment; one slug repeats 'manufacture-of-'; field names differ slightly between industries |
| `trade_wr` | 2015 to 2022; national; by type of trade, wholesale and retail; 864 rows; modified 2026-11-01 | market context in the market entry pack (D1, S1) | `pub_trade_wr` | context only, never a forecast; national |
| `pop_muni_age` | 2014 to 2024; municipality x age group; 1,584 rows; modified 2026-08-19 | customer segments by area and age (D3) | `pub_population_age` | estimates; spelling variants of municipality names (PUB-27) |
| `hotels_muni` | 2022 to 2024; municipality; 48 rows; modified 2026-08-02 | visitor accommodation supply (D1); calibrates the visitor share of the simulated footfall ([05](05_SYNTHETIC_WORLD_AND_SIMULATION.md)) | `pub_hotels_municipality` | counts of facilities, not rooms or guests |
| `trade_logistics` | certificates of origin by type and importing country, 2019 to 2024, 1,162 rows, modified 2025-05-29; arriving vessels, gross and net tonnage by type of vessel and country of previous port, 2016 to 2022, 1,890 rows, modified 2026-06-20; the same by country of registration (Hamad Port), 2019 to 2023, 717 rows, modified 2026-04-27 | serving the region and logistics access (D7) | `pub_trade_logistics` | a second certificates dataset with fewer rows exists on the portal and is not used; vessel series end in 2022 and 2023 |
| `est_census_2015_muni` | census 2015; municipality; 8 rows; modified 2025-06-02 | calibrates the density of synthetic firms by municipality ([05](05_SYNTHETIC_WORLD_AND_SIMULATION.md)) | `pub_census_2015_municipality` | dated 2015: every use says so; carries municipality geometry, which the frame does not use (section 5) |
| `lf_muni_sex` | 2020 to 2025; municipality x sex; female and male population and labour force, 240 rows each, modified 2026-09-30; employed persons 15 years and above, 96 rows, modified 2026-09-10; unemployed persons 15 years and above, 96 rows, modified 2026-09-06 | workforce available by area and sex, including the unemployed pool: D5 staffing; services aimed at women | `pub_labour_sex_municipality` | survey estimates (Labour Force Sample Survey); Public split by sex on the source's municipality geography only (PUB-90) |
| `pop_muni_age_sex` | 2014 to 2023; municipality x age group x sex; 1,440 rows each; modified 2025-06-02 (females) and 2025-05-07 (males) | customer segments by area, age and sex (D3), for example women aged 25 to 44 | `pub_population_age_sex` | titled December 2020 but holding 2014 to 2023; the year field is a date in one and text in the other; Public split by sex (PUB-90) |
| `active_sex_age_act` | 2017 to 2023; national; sex x age group x economic activity; females 1,551 rows, males 1,617 rows; modified 2026-11-04 | workforce by sex and age for each sector (D5) | `pub_active_sex_age` | national; Public split by sex (PUB-90) |
| `active_nat_occ_act` | national; Qatari and non-Qatari by occupation and economic activity, for all, males and females; 2017 to 2023, except Qatari males and the Qatari population (2017 to 2024); rows: non-Qatari females 1,269, non-Qatari males 1,323, non-Qatari population 1,323, Qatari females 1,206, Qatari males 1,440, Qatari population 1,440; modified 2026-11-04 | the Qatari talent pool by occupation and sector: staffing and Qatarization context (D5) | `pub_active_nationality_occupation` | national; Public split by nationality in the published Qatari and non-Qatari categories only (PUB-90); last year differs (2023 or 2024) |
| `comp_nat_act` | national; employees and annual compensation by nationality and main economic activity, one dataset per survey sector; 2015 to 2022, except the base slug (2016 to 2021) and the slug ending `-building` (2017 to 2022); rows by slug ending: base 72, `-building` 72, `-business` 556, `-energy` 2,872, `-energy0` 1,040, `-energy1` 2,904, `-one` 160, `-social` 1,092, `-social0` 1,072, `-social1` 1,092; modified 2025-08-17 to 2026-11-01 | Qatari and non-Qatari employment and pay per activity: pay benchmarks and Qatarization context (D5, D1) | `pub_compensation_nationality` | one dataset per survey bulletin with different field names; compensation is annual; national; Public split by nationality (PUB-90), never combined with a protected pay figure |
| `students_muni` | school years 2020-2021 to 2025-2026; municipality x level of education x sex x type of education x nationality; 1,570 rows; modified 2026-09-29 | students by area: training providers, family services, the future workforce (D3, D5) | `pub_students` | school years as text ('2025-2026'); Public splits by sex and nationality as published (PUB-90) |
| `visitors_markets` | hotel guests by nationality, hotel rating and stays, 2020 to 2022, 192 rows, modified 2026-06-20; visitor arrivals by mode of entry (3 rows) and by region (6 rows), June to November 2024 with the months as columns, modified 2026-11-04; arrival trends by mode of transport (air, land, sea), 2019 to 2025, 20 rows, modified 2026-10-19 | visitor source markets for hospitality decisions (D1, D3) | `pub_visitor_markets` | two arrival tables hold June to November 2024 as columns; hotel guests end in 2022; Public split by nationality as published (PUB-90) |
| `fdi_projects` | about 1,596 announced projects embedded in one page (the owner's figure, 2026-11-12), one record per project; fields: company, source country, sector, sub-sector, function, project type, capex, jobs, date, location and any further field the page holds; period range from the project dates at fetch | a Public source on the map and in D1, D4, D6 and D7, the market entry pack (S1) and the expansion comparison (S2); announced investment by sector as a forecast input (card C30, PUB-103) | `fdi_projects` (contract in [03](03_DATA_CONTRACTS.md)) | capex and jobs are the source's estimates of publicly announced projects; the dashboard does not capture every project and its data is subject to change; each project names a real investing company: Public-only subject `fdi_project` (PUB-87); page structure and location precision confirmed at slice S2; a forecast of a sector's series carries both notes and has the subject of its series, never a project (PUB-87) |
| `investqa_pages` | the sector, opportunity, incentive, set-up and law pages; parsed into records: sector, opportunity, incentive package with its parameters, set-up step, law with its link; page list confirmed at slice S2 | sector context (D1), the market entry pack (S1), the set-up steps, and the incentive packages as optional inputs of the break-even calculator ([07](07_ECONOMIC_METHODS.md)) | `pub_investqa_record` | page structure confirmed at slice S2; a forecast stated on a page is not loaded as a figure (PUB-88); a page that states no period is shown as read on its retrieval date |
| `traffic_tomtom_flow` | live; no stored period; allowance of 200,000 tile requests a month (read 2026-11-12) | optional live flow tiles as a picture layer when `EII_TRAFFIC_PROVIDER` is `tomtom`; the default is the simulated congestion by hour | none: the provider's tiles are in no table | not a fact: no numeral is read from a tile; attribution "© TomTom" visible while the layer is on; nothing stored, logged or committed; the browser never holds the key or contacts the provider; caveat key `live_traffic_provider`; the provider's terms, read on 2026-11-13, license the free plan for internal evaluation and testing only and prohibit storing results (OI-130; PUB-95) |
| `traffic_tomtom_range` | live; no stored period; allowance of 2,500 reachable-range requests a month (read 2026-11-12) | optional traffic-aware drive-time areas of a session, beside the simulated hour-varying areas | none: the areas are session geometry | bound to the session and seat like a drawn shape and marked with the provider and its retrieval time; the minutes are the user's own request; figures over the area carry the least-real class of their inputs; nothing stored; caveat key `live_traffic_provider` (PUB-95) |
| `busy_gmaps` | relative busyness by day of week and hour (index 0 to 100) for the named venues of a build-time list; period as retrieved | Public facts of `place_public` subjects, worded "Google Maps popular times, relative busyness, retrieved {date}" (card C37, PUB-101); the hour-of-day shape pooled over the named venues of a place category is an anchor of the simulation ([05](05_SYNTHETIC_WORLD_AND_SIMULATION.md)) | `pub_venue_busyness` | a relative index, never a count of people, and never in one component with an estimated-people figure (caveat key `relative_busyness_not_people`); no venue's own level or shape enters a generator; no licence for reuse stated and the publisher's terms name automated reading (PUB-12); values stay in the uncommitted public cache, never in a fixture; left out of the nightly live fetch |
| `ntl_blackmarble` | monthly; 15 arc-second grid (about 500 m); period from the file's own fields | Public layer of night-time radiance by area and month (card C36, PUB-100) | `pub_night_lights` | worded as night-time radiance, not as a measure of business activity (caveat key `night_lights_not_activity`); fetched with the Earthdata token when present (when absent, `build-public` continues and leaves the layer out); NASA acknowledged and the product DOI cited |
| `places_fsq` | three dated releases in the public copy (read 2026-11-12), the newest dated 2025-01-10, no update rhythm stated; size, coverage and last period of the release used to be recorded at the first fetch | a further source of the places layer, for competitors and typical neighbours (PUB-102); the places are shown with the date of the release used | `pub_place_fsq` | the owner decided on 2026-11-12 that this copy, dated 2025-01-10, is used for version 1 as it is, with no account and no newer release for now, and that the newer source wins where a place of the copy disagrees with OpenStreetMap or Overture (PUB-102); `places_ovt` already carries Foursquare-sourced records, so the de-duplication of PUB-51 applies across the two; categories map through a reviewed category mapping; the real-name collision checks extend to it |
| `worldpop_qat_agesex` | 100 m grids by age band and sex; year to be recorded at the first fetch | Public population by age and sex, shown with its source and year; whole cells summed over a chosen area (card C38, PUB-99); the generator reads it only collapsed across age and sex, as weights | `pub_pop_agesex_grid` | `public_splits: [sex]`; display only: never a criterion of a ranking, never combined with or charted with a protected or Simulated figure (caveat key `grid_cells_summed`); a cell counts when its centre lies inside the area and none is split; no synthetic record carries sex or age; the 2020 grid without age and sex stays `worldpop_qat_2020` |
| `weather_openmeteo` | hourly history; place and period to be recorded at the first fetch | typical hourly profiles by season read by the generator, never a dated day ([05](05_SYNTHETIC_WORLD_AND_SIMULATION.md)); the constants of the modulation are manifest entries with ranges and a sweep | none: a generator input in the public cache and the calibration manifest | non-commercial use and CC BY 4.0 attribution; heat and the summer switch (`ref_summer_work`) are kept from counting twice, as the method of 05 states; off if the demonstrator is hosted publicly or commercially until the owner decides ([17](17_DEPLOYMENT_HARDENING.md)) |

Sources mentioned in research but **not in v1**: the 2014 to 2018 imports, Harvard Growth Lab Atlas
files (Later, L9), UN Comtrade, World Bank and ILOSTAT benchmarks, and OpenStreetMap points of
interest (cross-check aid only, PUB-55). Imports against local production (formerly L3) is now in
version 1 ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md)); it uses the
customs data (`cus_imp_2025`, `cus_imp_2019`) with the manufacturing datasets (`mfg_industry`).
GADM is excluded: its licence forbids commercial use and redistribution (gadm.org licence page,
per research).

## 3. Fetcher rules

| ID | Requirement |
|---|---|
| PUB-01 | Public sources are fetched only by `./eii build-public`. No other command, test or product code opens a network connection to a source host, except the traffic provider module of PUB-95 (the optional live traffic provider, off by default). |
| PUB-02 | The product plane (`product/`, `web/`) contains no code path that contacts a source host, except the traffic provider module of PUB-95, which has its own list of hosts and is used only in a session with the provider switched on; the browser contacts only its own origin. A test asserts that the product imports no fetcher module and that the API process makes no request to any source host during the guided story, which runs with the provider off. |
| PUB-03 | The fetcher accepts only HTTPS, or S3 for Overture, to `www.data.gov.qa`, `www.data.qa`, `services7.arcgis.com`, `data.humdata.org`, `s3.us-east-1.amazonaws.com`, `www.geoboundaries.org`, `github.com`, `raw.githubusercontent.com`, `stac.overturemaps.org`, `overturemaps-us-west-2.s3.us-west-2.amazonaws.com`, `download.openstreetmap.fr`, `unstats.un.org`, `data.worldpop.org`, `web.archive.org`, `fdiprojects.invest.qa`, `www.invest.qa` and `data.source.coop` (the public copy of `places_fsq`, [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 21). `www.data.gov.qa` and `www.data.qa` serve the same portal and the same slugs ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)): a dataset is identified by its slug whichever host served it, and the registry records the host each file came from (`fetch_host`). Redirect and storage hosts are checked too. A source whose direct URL or redirect host is still marked to be confirmed at slice S2 is blocked. Adding a host needs a reviewed registry change: the hosts of the sources of decision 0019 that `build-public` fetches (`busy_gmaps`, `ntl_blackmarble`, `weather_openmeteo` and the file host of `worldpop_qat_agesex`) are fixed by the tasks that build their fetchers and are added here that way, and each such source is blocked until then. The hosts of the traffic provider are never added to this list (PUB-95). |
| PUB-04 | Every fetched file is stored in `data/public_cache/<source_id>/<sha256>.<ext>` with a complete sidecar holding the fields of section 3.1. An entry with `kind: public_document` and `fetch_mode: citation_only` opens no network request, requires no cached file, and writes registry metadata with `sha256: "CITATION_ONLY"`. The traffic provider (`fetch_mode: live_session`, PUB-95) is not an entry of the registry: it is listed in section 2 for its terms and attribution, stores no response, has no sidecar and has no row in `source_registry`. |
| PUB-05 | Writes are atomic: a file enters the cache only after its download completes, its SHA-256 is computed and its checks pass. An interrupted run leaves no partial entry. |
| PUB-06 | A failed request is retried at most three times with back-off, then the build exits non-zero with a message naming the `source_id`, the URL and the failed check. There is no silent fallback to an older file. |
| PUB-07 | Each fetched dataset declares its expected column names and types. A source whose schema is marked to be confirmed at slice S2 is blocked; a missing, renamed or retyped column fails the build. Citation-only public documents have no dataset schema. |
| PUB-08 | Each source declares an expected row-count range and last period. A count outside the range or a last period earlier than recorded fails the build. |
| PUB-09 | For portal sources, the fetcher reads the dataset metadata and records licence, publisher and modified date. A missing licence, a licence different from the registry, or a publisher different from the named publisher fails the build. A publisher or licence marked to be confirmed at slice S2 blocks that source until a reviewer records the exact metadata. |
| PUB-10 | When an upstream file changes (new SHA-256), the new version is stored beside the old one. The release manifest names exactly one hash per source, and changing it is a reviewed registry change. |
| PUB-11 | No file is committed unless its licence is stated and permits redistribution. `data/` is never committed. Committed derived files (section 6 configs, test fixtures) record the `source_id` they derive from. |
| PUB-12 | A portal dataset with no dataset-level licence metadata may be used only with `licence_basis: portal_terms` and a reviewer note in the registry; it is never committed. A source whose publisher states no reuse terms covering the use made here may enter a release only when an accepted decision record of the owner names it, with `licence_basis: owner_decision`. [Decision 0017](decisions/0017-public-data-additions-and-public-splits.md) names the sources of this kind that it admits: the two investment sources, `fdi_projects` and `investqa_pages` (the owner's decision of 2026-11-12 for this personal internal project, without a permission request), and the census map layers of PUB-13 (item 10). [Decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 19 names one more, `busy_gmaps` (Google Maps popular times): its publisher states no licence for reuse and its terms name automated reading and bulk feeds; the registry entry records those terms as read at the fetch (page, retrieval date and hash) and `licence_basis: owner_decision`, and the owner decided on 2026-11-12 to use the source in this personal internal project. Its values stay in the uncommitted public cache, never enter the repository or a test fixture, and the source is left out of the nightly live fetch (PUB-101). The investment sources' registry entries record the publisher's own terms as read at fetch (page, retrieval date and hash) and that basis; a changed terms page is a reviewed registry change, like a changed file (PUB-10). They are never committed. If the terms read at fetch forbid the use made here, the source is switched off (no value from it enters a release, and its tools return `NO_DATA`) and the owner is told; this holds for every source but `busy_gmaps`, which stays on by the owner's decision recorded above. If the demonstrator is ever hosted publicly, the owner decides then which of these sources stay on. |
| PUB-13 | Until written terms or permission covering the intended use are recorded, sources marked `none stated` are validation-only. No raw value, derived share, title or geometry from them enters a release; affected tools return `NO_DATA`. The 2020 boundary layers are used only to check licensed HDX geometry. The same release-lineage block applies to unresolved UN classification terms. The two investment sources of PUB-12, `busy_gmaps` and the census map layers (`census_zone_sector`, `census_zone_occ`, `census_zone_hh`, `census_zone_lab`, `census_district_pop`) are the only sources without such terms that enter a release, by the owner's decision ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md) items 6 to 8 and 10, item 10 closing OI-04 for version 1; [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 19 for `busy_gmaps`), each figure with its source and retrieval date and nothing fetched from them committed. The archived census 2020 workbook and every other source without stated reuse terms stay validation-only, and no other source may use that basis without a new decision record. |
| PUB-14 | Transaction and parcel identifiers in `prop_sales` and `prop_resi_units`, and any other identifier column in a public source, are dropped before the release; only aggregates with their deal counts are stored. |
| PUB-15 | `./eii build-public` prints, for the slice S2 gate, 20 randomly drawn stored figures, each with its `source_id`, URL, filter and value, so a reviewer can check them against the source. The seed and the list are saved with the build log. |
| PUB-16 | Fetchers record retrieval time in UTC and never use a file date or a portal "modified" date as the reference period of the data. The reference period comes from the data's own period fields. |
| PUB-17 | The Overture extract is read with DuckDB from the pinned release path, filtered to the Qatar bounding box and `country = 'QA'`, and stored as Parquet. DuckDB 2.x needs `SET geometry_always_xy=true` (research note); read the current DuckDB spatial documentation before writing this step. |
| PUB-18 | ArcGIS feature services are paged at the server's stated maximum (2,000 features per request per research) until the reported total is reached; a short final total fails the build. |
| PUB-80 | Every number and comparison emitted from this pack is produced by a deterministic tested release-build function or by `eii_core.calc`, with a method card and worked regression example. The browser only formats returned facts and never calculates a displayed value. A forecast, base rate, estimate or scenario figure of cards C30 to C35 is such a number: each candidate model, the backtest, the interval and the error measure have a method card and a worked regression example, with seeds where randomness enters. |
| PUB-85 | The seventeen groups of [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) are represented by eighteen source-id families, because the decision's group of museum and health-centre visits uses two (`visits_museum` and `visits_phcc`). Each family keeps one `source_id` and has one registry entry per slug, keyed `<source_id>/<slug>`. Each slug is a dataset of its own for PUB-04 to PUB-10 and PUB-16: its own sidecar, hash, host, declared columns and types, row-count range, last period, and publisher and licence checks. The release manifest names exactly one hash per slug, and lineage and the evidence drawer name the slug. The coverage facts in section 2.2 for these families were read from the portal's catalogue and records on 2026-11-12 and are recorded again at every fetch. Every figure from them is shown as Public with its source, its reference year (or month) and its retrieval date. |
| PUB-95 | The traffic provider module is the one named exception to PUB-01 and PUB-02. It is a module of the API process and is off by default: the setting `EII_TRAFFIC_PROVIDER` is `simulated` unless it is set to `tomtom`, and the module fetches only when the setting is `tomtom`, `TOMTOM_API_KEY` is present in the environment and the presenter's offline control is not set. It opens connections only to the hosts of its own list, which is separate from PUB-03 so that `./eii build-public` cannot reach them; each host is added by a reviewed registry change, fixed by the task that builds the module. It serves live flow tiles (`traffic_tomtom_flow`) and traffic-aware drive-time areas (`traffic_tomtom_range`) and passes them on; the browser never holds the key and contacts only its own origin. Nothing of a response is written to disk, to the release, to the ledger or to a log: the run-time lineage keeps the request, the retrieval time and the response hash, and the provider has no row in `source_registry`, because nothing of it is fetched into the cache: section 2 lists it for its terms and attribution (`fetch_mode: live_session`, `licence_basis: provider_terms`). A live tile is a picture layer with the attribution "© TomTom" visible while the layer is on, and no numeral is read from a tile. A traffic-aware drive-time area is an area of the session: it enters through the adapter, is bound to the session and seat like a drawn shape, and is marked with the provider and its retrieval time; its minutes are the user's own request, and figures over it follow the rules of a drawn shape and carry the least-real class of their inputs (PUB-20, PUB-29). No provider number is a fact: a tile and an area are not release facts, and the source chain of PUB-19 is not claimed for them. Tests never call a live service: their fixtures are made by hand in the documented response format, and no response of a live service is committed. No test, gate, command or the guided story needs the provider, and the test of PUB-02 runs with it off. The provider's developer terms were not read on 2026-11-12, so its rule on storing responses is not verified, and nothing is stored. |
| PUB-96 | `TOMTOM_API_KEY` and `EARTHDATA_API_KEY` may be used by the build now, within the free allowances ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 16). They lie outside the keys of [decision 0018](decisions/0018-priorities-and-amendments-to-decision-0015.md) item 12, which stay unused. Each is read only from the environment and is never printed, logged, committed or put into a work tree, a brief or a sandbox; it appears in no sidecar, registry entry, fixture or error text. `EARTHDATA_API_KEY` serves `ntl_blackmarble` inside `./eii build-public` (`./eii build-public` never fails because `EARTHDATA_API_KEY` is absent: it continues and leaves the night-lights layer out); `TOMTOM_API_KEY` serves only the provider of PUB-95. No test, gate or command and not the guided story needs either key: the fetchers are tested on hand-made fixtures in the documented response format, and no response of a live service is committed. No key or other secret is added for `places_fsq`. The nightly live fetch leaves out `busy_gmaps` and every source that needs a key (`ntl_blackmarble`). |
| PUB-97 | `ntl_blackmarble`, `worldpop_qat_agesex`, `weather_openmeteo` and `places_fsq` are fetched only by `./eii build-public`, into `data/public_cache/<source_id>/` with the sidecar of section 3.1, so that the data input of the generators stays the public cache. These publishers are not portals, so PUB-09 does not apply to them: the registry entry records instead the publisher's terms or licence page as read at the fetch (page, retrieval date and hash, in `terms_sha256`), and a licence different from the registry fails the build. The reference month or period of each comes from the file's own fields (PUB-16), and a changed product version is a reviewed registry change (PUB-10). The weather file is read by the generator only as typical hourly profiles by season, never as a dated day. `places_fsq` is read without an account, only from the files of its public copy that cover Qatar, and its entry records the release used (PUB-102). The non-commercial condition of `weather_openmeteo` falls under the hosting sentence of PUB-12. |

### 3.1 Registry and sidecar record

```yaml
source_id: util_elec            # decision 0017 source-id families: one entry per slug, <source_id>/<slug> (PUB-85)
kind: public_dataset            # public_dataset | public_document
fetch_mode: fetch               # fetch | citation_only (live_session names the traffic provider in the listing of section 2 only, PUB-95)
title_en: Electricity Total Consumption by Zone Number
publisher: Kahramaa            # copied from portal metadata at fetch
fetch_host: www.data.gov.qa    # host that served the file; portal: www.data.gov.qa or www.data.qa (PUB-03)
fetch_url: https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/electricity-total-consumption-by-zone-number/exports/json
landing_url: https://www.data.gov.qa/explore/dataset/electricity-total-consumption-by-zone-number/
licence_id: CC-BY-4.0          # one of the ids in section 4
licence_basis: dataset         # dataset | portal_terms | none_stated | owner_decision (PUB-12) | provider_terms (PUB-95, PUB-97)
licence_url: https://www.data.gov.qa/pages/license/annexes
terms_sha256: null             # owner_decision, or a publisher that is not a portal (PUB-97): hash of the terms or licence page as read at fetch
decision_record: null          # owner_decision only: the record that grants the use (0017 for the investment sources and the census map layers; 0019 for busy_gmaps)
public_splits: []              # split dimensions this Public source may carry: sex, nationality (PUB-90)
commit_allowed: false          # true only for small derived configs and fixtures
retrieved_utc: 2026-11-11T09:00:00Z   # example value
sha256: <64 hex characters>
bytes: <integer>
source_modified: 2026-..       # portal metadata, provenance only
period_first: 2021
period_last: 2026-08
row_count: <integer>
columns: [{name: year, type: integer}, {name: zone_number, type: integer}, {name: value, type: number}]
reconciliation: none           # none | open | resolved:<decision record>
release_tables: [pub_zone_utility]
caveat_keys: [proxy_not_population, partial_latest_year]
```

### 3.2 Investment sources and page parsers

The two investment sources are pages, not portal datasets. On 2026-11-12 the owner decided to use
them in full for this personal internal project
([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)). PUB-12 sets their
basis of use; their fetch follows PUB-01 to PUB-10 like every other source.

| ID | Requirement |
|---|---|
| PUB-86 | The FDI page parser and the agency page parsers are deterministic functions in `custodian/publicdata/` that turn a cached page into typed records. They read only the cached file of PUB-04, never a live page. Each declares the page structure it expects, confirmed at slice S2 ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)); a missing or changed element fails the build, naming the `source_id`, URL and element, and nothing is loaded in part. Their tests use only a small synthetic page shaped like the real one, whose names, figures and text are invented and copy no value or text from the real page. Nothing fetched is committed: the pages and the parsed records stay in the uncommitted `data/` folder (PUB-11), and only the fetchers, the parsers, the contracts and their tests are committed. The publisher's name and terms are recorded from the site at each fetch (PUB-12). |
| PUB-87 | `fdi_projects` is read from the dashboard page `https://fdiprojects.invest.qa/` (data from fDi Markets) on every `./eii build-public`. Every project field the page holds is loaded into the contract `fdi_projects` ([03](03_DATA_CONTRACTS.md)); a field the contract does not declare fails the build until the contract adds it, so no field is dropped silently. A changed page is stored under its new hash and enters a release through the reviewed registry change of PUB-10. Capex keeps the currency and unit the page states; nothing is converted. Every capex and jobs figure carries the source's note that it is an estimate of a publicly announced project, and every count or list of projects carries the note that the dashboard does not capture every project and that its data is subject to change; a forecast of announced investment by sector (card C30) carries both notes in its fact and its chip, and has the subject of its series, never that of a project. The subject `fdi_project` accepts Public slots only: no Synthetic or Simulated fact is attached to it, it is never joined to synthetic firm data, and it is shown as a published announcement with its source and the estimate note, never as a lookup of a firm ([AGENTS.md](../AGENTS.md) rule 24). A project is placed only at the location the page gives, resolved to an official geography through the gazetteer: a location given as a city or municipality is shown on that geography, never at an invented point, and is never counted as inside a drawn shape; an unresolved location has no map position. Its company names are real business names in the public cache, so the name-collision check of SYN-20 covers them. |
| PUB-88 | `investqa_pages` loads the sector, opportunity, incentive, set-up and law pages of `https://www.invest.qa/` into `pub_investqa_record`: one typed record per sector, opportunity, incentive package (with its parameters), set-up step and law (with its link), each with its page URL and retrieval date. Screens show these records only through application templates, with a link to each page. Every number parsed from a page (an incentive parameter, for example) is a typed field shown only as a Public fact; a record whose page states no period is shown as read on its retrieval date. A forecast stated on a page (of revenue, demand, market size or growth) is not loaded as a figure; the record links to the page instead, because a publisher's forecast has no tested method, backtest or lineage of this project ([AGENTS.md](../AGENTS.md) rules 7 and 16, PUB-80). Incentive packages are optional scenario inputs of the break-even calculator of [07](07_ECONOMIC_METHODS.md), tagged "your inputs" with their source page; they never change a Public figure. |

## 4. Licences and attribution

Attribution is shown in three places: the evidence drawer of every Public fact chip, the Trust
centre source list, and every export (briefing pack, reviewer's GIS mirror). Attribution names the
publisher of a public dataset or page; it never presents a publisher as a supplier or endorser of
the POC. The one carve-out is the attribution that the traffic provider's terms require: it names
the provider as the source of the live traffic layer, while that layer is on, and nowhere else
(PUB-95); no endorsement is implied.

| Licence | Sources | Text on screen and in exports (template) | Extra duty |
|---|---|---|---|
| CC BY 4.0 (portal licence) | all portal sources, from either host | "Source: {publisher}, {dataset title}, Qatar Open Data Portal, retrieved {date}. Licensed under CC BY 4.0. {Modified: aggregated by EII.} No endorsement implied." | link to the dataset page; state modifications |
| CC BY-IGO | `bnd_hdx` | "Boundaries: Planning and Statistics Authority via HDX (COD-AB Qatar), CC BY-IGO, retrieved {date}." | link to the HDX page |
| CC BY 4.0 | `bnd_geob` (fallback) | "Boundaries: geoBoundaries, CC BY 4.0, retrieved {date}." | link |
| CDLA Permissive 2.0 | `places_ovt` records from Meta, Microsoft, PinMeTo, Uberall and other listed sources | "Data from {provider}. Available under CDLA Permissive 2.0." plus "Overture Maps Foundation, overturemaps.org, release 2026-10-21.0, accessed {date}." | any shared copy of place data carries the full CDLA Permissive 2.0 text (agreement section 2.1, cdla.dev, checked 2026-11-11) |
| Apache 2.0 | `places_ovt` records sourced from Foursquare; `places_fsq` | "Copyright 2024 Foursquare Labs, Inc. All rights reserved. Licensed under Apache 2.0; transformed to the Overture schema." (for `places_fsq`, the publisher's copyright line as the README of the public copy states it, read 2026-11-12, and the notice of the release used) | link the Foursquare NOTICE file as Overture's attribution page directs; for `places_fsq`, the notice and attribution of the publisher's release (year, link), with the date of the release used |
| CC0 1.0 | `places_ovt` records from AllThePlaces | "Data from AllThePlaces." | none |
| ODbL 1.0 | `roads_osm`, `bldg_ovt` | "© OpenStreetMap contributors. Available under the Open Database License." with a link to `https://www.openstreetmap.org/copyright` | any distributed database derived from these (for example the routing graph) is offered under ODbL |
| Publisher's own terms, used by owner decision ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)) | `fdi_projects` | "Source: {publisher}, FDI Projects dashboard, data from fDi Markets, retrieved {date}. Capex and jobs are estimates of publicly announced projects; the dashboard does not capture every project, and its data is subject to change. No endorsement implied." | link to the dashboard page; the estimate note beside every capex or jobs figure and every count or list of projects (PUB-87); the Trust centre shows the terms as read at fetch and the basis of use |
| Publisher's own terms, used by owner decision ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)) | `investqa_pages` | "Source: {publisher}, {page title}, retrieved {date}. No endorsement implied." | link to each page; the Trust centre shows the terms as read at fetch and the basis of use |
| none stated; used by owner decision ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 10) | census map layers (`census_zone_*`, `census_district_pop`) | "Source: {publisher}, {layer title}, public map service, retrieved {date}. No licence stated. No endorsement implied." | every figure shows its source and retrieval date; nothing fetched is committed (PUB-13) |
| CC BY 4.0 | `worldpop_qat_agesex` (and `worldpop_qat_2020` where it is cited) | "Source: WorldPop, {dataset title}, {year}, CC BY 4.0, DOI 10.5258/SOTON/WP00841, retrieved {date}. No endorsement implied." (wording confirmed from the publisher's page at the first fetch) | link; state modifications (whole cells summed over the chosen area) |
| CC BY 4.0 (data); free interface for non-commercial use | `weather_openmeteo` | "{Attribution as the publisher's licence page asks, recorded at the first fetch}, retrieved {date}. Licensed under CC BY 4.0." | link to the licence page |
| NASA data and information guidance | `ntl_blackmarble` | "Night-time lights: NASA Black Marble VNP46A3, DOI 10.5067/VIIRS/VNP46A3.002, retrieved {date}. NASA is acknowledged as the source. No endorsement implied." (wording confirmed at the first fetch) | acknowledge NASA and cite the product DOI |
| Provider terms | `traffic_tomtom_flow`, `traffic_tomtom_range` | "© TomTom", visible while the live layer is on | nothing stored; no endorsement implied (PUB-95) |
| none stated; used by owner decision ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 19) | `busy_gmaps` | "Google Maps popular times, relative busyness, retrieved {date}. A relative index, not a count of people. No endorsement implied." | the Trust centre shows the terms as read at fetch and the basis of use; nothing fetched is committed (PUB-12, PUB-101) |
| none stated | 2020 boundary layers, archived census workbook | validation-only; no release attribution is rendered | no raw value, derivative, title or geometry enters a release |
| UN terms unresolved | `cls_isic4` | validation-only until intended-use terms are recorded | no classification title or derived mapping enters a release |
| citation-only | `ref_*` | "{Publisher}, {document title}, retrieved {date}." | registry metadata only; no fetched file |

| ID | Requirement |
|---|---|
| PUB-19 | Each Public fact opens an evidence drawer labelled "Source chain" and resolves fact → release table → deterministic method and version → publisher, dataset or page, licence, retrieval date and file hash. The proposed Arabic label remains pending the owner's review. A live provider response is not a fact and has no such chain: a tile is a picture layer and no numeral is read from it, a traffic-aware drive-time area is session geometry with a provenance note (provider, request, retrieval time, response hash), and the minutes of the area are the user's own request (PUB-95). |
| PUB-20 | A composite fact lists every input and takes the least-real provenance class of those inputs. A fact without a complete source chain is not a fact: the release build fails, the validator rejects it and the Fact chip refuses to render it. |
| PUB-21 | The briefing pack and every export carry an attribution block for every source used in them; exports containing place records include the full CDLA Permissive 2.0 text and the Foursquare notice link when such records are present. |
| PUB-22 | The Trust centre lists every source in the registry with licence, retrieval date, hash prefix and the release tables it feeds. |
| PUB-23 | Place attribution is computed per displayed record from its source field (the Overture source field, or the source of a `pub_place_fsq` record); a record whose source has no attribution entry is not displayed. |
| PUB-98 | The sources of decision 0019 follow the attribution table above. The mark of the live traffic layer is shown while the layer is on. `ntl_blackmarble` is acknowledged to NASA with the product DOI, `weather_openmeteo` with the attribution the publisher asks for, `worldpop_qat_agesex` with its source and year, and `busy_gmaps` with its label and retrieval date, in the evidence drawer, the Trust centre list and every export that uses them (PUB-21). The exact text of each is recorded from the publisher's page at the first fetch. |

## 5. The frame: geographies, gazetteer and crosswalks

Public statistics stay on their official geographies and are never blended into a protected figure
(master design section 6). Where one is apportioned to a drawn shape, the result is Inferred
(PUB-29). The frame lets a pin or a drawn area find its zones, districts and municipalities, lets
sources join, and lets the user type a place name in either language.

| Level | Count (research, 2026-11-11) | Geometry source | Names source | Used by |
|---|---|---|---|---|
| Municipality | 8 | `bnd_muni_2025`, check against `bnd_hdx` | `bnd_hdx` (Arabic and English) | licences, population, cancellations, and the municipality tables of decision 0017 (permits, population by age and sex, labour force, hotels, students) |
| Zone | 91 polygons in the 2020 layer | `bnd_hdx` (licensed) checked against `bnd_zone_2020` | `bnd_hdx` | utility series, census shares |
| District | 781 polygons (778 with population) | `bnd_hdx`, checked against `bnd_district_2020` | `bnd_hdx`; `prop_sales` and `prop_resi_units` names via crosswalk | property sales, residential unit sales |
| Grid cell | H3 resolution 9 (Greater Doha) and 8 elsewhere | computed | none | protected and simulated statistics only ([06](06_PRIVACY_AND_DISCLOSURE_CONTROL.md)); no public figure is apportioned to it (the raster aggregation of PUB-100 is not an apportionment) |

| ID | Requirement |
|---|---|
| PUB-24 | Release zone geometry comes from `bnd_hdx` (CC BY-IGO). The 2020 layer is used at build time only to test that every `bnd_hdx` zone matches a 2020 zone number and that Lusail's zone 69 boundary agrees; disagreements are listed in the build report. |
| PUB-25 | A committed `custodian/publicdata/review/zone_crosswalk.csv` lists every zone number seen in any source with one column per source (`bnd_zone_2020`, `bnd_hdx`, `util_elec`, census tables, `bnd_geob`) and a status: `matched`, `absent_in_source`, `merged`, `no_polygon`. Zone numbers 10 and 11 in the utility series and the merged geoBoundaries zones (for example '18-19') must appear with an explicit status. |
| PUB-26 | A utility row whose zone has no polygon is kept in national totals and listed as "zone without boundary" in the coverage note; it is never assigned to a neighbouring zone. |
| PUB-27 | A committed `municipality_names.csv` maps every spelling seen in sources (for example Al Sheehaniya and Al Shahaniya, Umm Slal and Umm Salal, Al Khor and Al Thakhira) to one municipality key. An unmapped spelling fails the build. |
| PUB-28 | A committed `district_crosswalk.csv` maps each `prop_sales` and `prop_resi_units` district name (Arabic and English) to one or more boundary districts, including renamed districts such as 'Lusail' and 'Lusail 69'. Unmatched names are listed and excluded from district figures, never guessed. |
| PUB-29 | A pin finds its zone, district and municipality by point-in-polygon on the pin itself. A drawn area (a drawn shape, a radius, or a walk or drive time from a point) finds every official geography its shape overlaps, by polygon intersection, not only those that hold its vertices. Public point layers (places, venues, and FDI projects with a point location) are counted inside the drawn shape exactly, by point-in-polygon; a count of places is a count of listed records with the note of PUB-50, never a count of businesses. A statistic published on an official geography is shown on that geography, which is named. Where it is apportioned to the drawn shape, the result is labelled Inferred, names the apportioning method of [07 Economic methods](07_ECONOMIC_METHODS.md) and the source geography, and takes its provenance under PUB-20. Public splits by sex or nationality are never apportioned (PUB-90); the one case that is not an apportionment is the sum of whole cells of a published population grid over a chosen area (PUB-99). No public figure is apportioned to grid cells or release units, or blended into a protected figure; the aggregation of a raster measurement by whole pixels (PUB-100) and that whole-cell sum are not apportionments. Figures from the protected record types (business register, employment, residence, wages) snap to whole release units, with the snap sentence, before any figure is read ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md)). |
| PUB-30 | The `gazetteer` table uses the contract fields `place_key`, `kind`, `name_en`, `name_ar`, `aliases`, `lon`, `lat`, `cell`, `showcase_verified` and `source_id` for every municipality, zone, district, showcase area and flagship building. |
| PUB-31 | Arabic search keys remove diacritics and tatweel, unify alef forms, map final ta marbuta to ha and alef maqsura to ya; English keys are lower-cased with punctuation removed. The same function is used by `resolve`; keys are computed in memory and are not release columns. |
| PUB-32 | Arabic names come from `bnd_hdx` or another licensed source. Names the team writes (showcase areas, the flagship building, activity labels) are marked "pending native review" until signed off under OI-09. |
| PUB-81 | In public-only mode, `make_area` uses the fixed base-cell frame, reads no privacy-derived release unit and no Protected or Simulated table, and emits the snap report as technical metadata rather than a Synthetic fact. |
| PUB-82 | The coverage bar uses the finest geography available from a source that may enter a release (PUB-12, PUB-13)—zone, otherwise municipality, otherwise national—and names that geography. It never uses a validation-only value or derivative. |
| PUB-83 | `pop_muni` writes `pub_population_municipality` (`municipality_code`, `period`, `indicator`, `value`, `unit`, `source_id`); `est_census` writes `pub_census_national` (`period`, `indicator`, `value`, `unit`, `source_id`); `census_district_pop` writes `pub_census_district` (`district_key`, `period`, `indicator`, `value`, `unit`, `source_id`). `pub_census_zone` and `pub_census_district` are present in every release and hold the rows of the census map layers that [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 10 admits to the local release (OI-04 closed for version 1); a table whose source is switched off (PUB-12) has zero rows, and no value from a validation-only source enters any fact. National or district census population rows never enter `pub_census_zone` as national aggregates, and population lineage never enters a geometry table. |
| PUB-84 | The closed count `indicator` names and `unit` values for the attacker-view audit (PRV-115) in `pub_population_municipality`, `pub_census_national`, `pub_census_district` and `pub_census_zone` are exactly: `residents` (`persons`), `households` (`households`), `establishments` (`establishments`), `employees` (`persons`). Indicator names are lower snake case. No other indicator is a count for audit selectors until a contract revision adds it. PUB-15 regression values not pinned in [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md) at slice S2 are produced by `./eii build-public`, checked against the source by the reviewer, and written into the method cards by a slice S2 task; slice S7 fails while any remain unpinned (MTH-03). |
| PUB-89 | A committed `custodian/publicdata/review/venue_crosswalk.csv` maps every venue name seen in `visits_museum`, in every year, to one venue key, and each venue key to the `pub_place` record of that venue where a reviewer finds one, with reviewer role and date; health-centre names in `visits_phcc` are mapped the same way. An unmapped name fails the build, and a venue with no reviewed match has no map point. The build normalises names only through this crosswalk and never edits a value by hand ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)). |
| PUB-90 | Official figures split by sex or nationality are Public facts, shown only as published: on the source's own geography and categories (the workforce and pay tables publish Qatari and non-Qatari), each with its source and reference year ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)). A `pub_` table may carry a sex or nationality column only when its source's registry entry declares that dimension in `public_splits` (section 3.1); the schema tests that reject sex, gender and nationality columns keep their full strength on every synthetic and protected contract. No Public split is joined to a synthetic record, used to segment synthetic records or to derive an attribute for them, apportioned to a drawn area (the sum of whole cells of `pub_pop_agesex_grid` over a chosen area under PUB-99 is not an apportionment), or combined with a protected, Synthetic or Simulated figure in any fact, ratio or weight. A calibration input that carries such a split uses only its totals over the split; the generator reads the age-and-sex grid only collapsed across age and sex, as weights. The registry entries of `wage_occ`, `wage_act`, `wage_sector` and `work_hours_act` declare their national sex split the same way. |
| PUB-99 | `pub_pop_agesex_grid` holds the Public grid of `worldpop_qat_agesex` by grid cell, age band, sex, people and year ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 22, card C38). For an area the user chooses, tested code in `eii_core.calc` sums whole cells: a cell counts when its centre lies inside the area, and no cell is split. The sum is Public with its source and year, is for display only, and carries the caveat key `grid_cells_summed`. It is never a criterion of a ranking, is never combined with a protected, Synthetic or Simulated figure, and is never on one chart with one. It is not an apportionment, and a tabulated split stays on its own geography (PUB-90). `worldpop_qat_2020` keeps its role as weights; only `worldpop_qat_agesex` is shown as population. No synthetic record carries sex or age. |
| PUB-100 | The public-data build aggregates the monthly raster of `ntl_blackmarble` to the frame by a stated whole-pixel rule: a pixel counts in the frame cell that holds its centre, and no pixel is split. `pub_night_lights` holds the radiance by frame cell and month, from whole pixels, and is never keyed by release unit, as the contract in [03](03_DATA_CONTRACTS.md) fixes it. The month comes from the file's own period (PUB-16). It is a Public layer worded as night-time radiance (card C36) with the caveat key `night_lights_not_activity`, never as a measure of business activity, and never set beside a protected figure as one number. |

## 6. The activity spine

The spine links the licence activity code, the ISIC Rev.4 class, the Overture place category and,
for playbook activities, the customs basket. It powers the "We understood your question as…" chips
(capability M8) and every join between licence, survey, customs and places facts.

The May 2025 active table holds 4,755 codes. Of 249,622 licence-activity counts, 211,277 (84.6%;
2,035 codes) sit under seven-digit codes whose first four digits are an ISIC class, 11,276 (4.5%;
1,363 codes, mostly a `20xxxxx` series) under other seven-digit codes, 26,844 (10.8%; 1,336
codes) under six-digit legacy codes, and 225 (0.1%; 169 under 13 five-digit codes and 56 under
eight eight-digit codes). Among the legacy codes, 138 codes (3,163 counts) have a
prefix that only looks like an ISIC class; every mapping needs a meaning check and human sign-off.

**The legacy trap, worked example.** The 6-digit code 561000 is named for trade in spare parts and
561050 for electronic spare parts. A mapper that takes the first four digits would file both under
ISIC 5610 Restaurants. The correct result is the "not mappable" bucket. By contrast, 7-digit
5610101 (restaurant) and 5610201 (cafeteria) map to ISIC 5610 after review.

| ID | Requirement |
|---|---|
| PUB-33 | Only 7-digit codes are candidates for an ISIC mapping. A candidate maps to the ISIC class given by its first four digits only if that class exists in `cls_isic4` and a human reviewer approves that the Arabic activity name fits the class title. |
| PUB-34 | The review scope for v1 is: the 200 codes with the largest national active counts; every 7-digit code whose first two digits are 56 (food service); and every playbook code (the codes of the playbook activities and of their basket supplier activities, PUB-41). Codes outside the scope keep the status `unreviewed`. Codes that appear only in `lic_cancelled` follow the same rules. |
| PUB-35 | Offline `spine_match` proposals may use the decision-0014 gateway only to order and pre-fill the human review queue. The provider defaults to `none`; no mapping is automatic, no gateway result is a fact, and every released mapping requires recorded human sign-off. The gateway has no run-time role and no screen presence except the Proof-room lineage line. The approved list is committed as `custodian/publicdata/review/activity_spine.csv` with `code`, `code_length`, `name_ar`, `isic_class`, `status`, `reason`, `reviewed_by_role` and `reviewed_on`; ISIC titles are joined at build time. |
| PUB-36 | Status values are exactly `mapped`, `unreviewed`, `not_mappable_legacy` (6-digit and other lengths), `not_mappable_invalid_prefix`, `not_mappable_rejected`. |
| PUB-37 | ISIC-level figures include only `mapped` codes. The share of licence-activity counts in `unreviewed` and `not_mappable_*` codes is published as a coverage fact beside every ISIC-level figure, and the not-mappable bucket is visible in the spine chips. |
| PUB-38 | Each mapped ISIC class used by a playbook links to Overture categories through a reviewed allow-list (for example ISIC 5610 to `restaurant` and its Italian subcategory). Pizza is included in "Italian" only when the label on screen says "Italian or pizza". |
| PUB-39 | The spine records its code system version (`licence_codes_2025_05`). The commerce ministry began recoding activities to the GCC unified classification from 1 June 2026 (Qatar News Agency, 1 June 2026); a later snapshot with new codes needs a new reviewed version, never a silent remap. |
| PUB-40 | English labels for codes come from the ISIC class title, marked as the class title, not as a translation of the Arabic activity name. |

## 7. Playbook activities and customs baskets

The master design names the restaurant and "the other playbook activities" without listing them.
**ASSUMPTION:** the v1 playbook activities are ISIC 5610 Restaurants (flagship), ISIC 5630 Beverage
serving (coffee shops) and ISIC 5510 Short-term accommodation, because all three are covered by the
same published hotels-and-restaurants survey tables (activities 551, 561, 562, 563 per research),
so capability M6 can use one verified source family. The owner may change the list in a decision record.

Baskets answer "which countries supply this input, at what calculated unit value". A basket is an
editorial choice by the EII team, not an official classification.

| ID | Requirement |
|---|---|
| PUB-41 | Each playbook activity has one basket in `custodian/publicdata/review/baskets.yaml` with at most eight inputs (estimate from research: three activities, eight inputs each). Each input lists its tariff lines, an inclusion reason, excluded lines with reasons, the supplier ISIC class for licensed wholesale depth (for example ISIC 4630), reviewer role and date. |
| PUB-42 | Basket lines are defined at eight digits or finer, chosen from the dataset's own bilingual line descriptions. A 4-digit heading or 6-digit subheading is never a basket line. |
| PUB-43 | Tariff codes in committed files are written in dotted form (digit groups separated by dots) so no bare 8-digit or 11-digit token appears in the repository; the loader strips the dots. |
| PUB-44 | For periods covered only by `cus_imp_2019` (8-digit), a 12-digit basket line rolls up to its 8-digit parent; if that parent also holds lines excluded from the basket, the earlier-period value is marked "includes excluded lines" or not shown. |
| PUB-45 | Unit value is computed as value in QAR divided by net kg, only over rows with kg greater than zero, and labelled "calculated". Rows in other quantity units are counted separately and never converted. The valuation basis is shown as the source states it, or "not stated by the source". |
| PUB-46 | Every basket card carries the label "Basket chosen by the EII team (editorial choice)" and answers "which countries supply this", never "which company to buy from". |

**Pasta example.** Heading 1902 holds pasta and also instant noodles: in 2025, Italian goods under
the heading arrived at QAR 8.69 per kg and Saudi goods at QAR 11.45 (master design section 9), while
a judge's query of the same heading found South Korean goods at QAR 19.56 per kg (feasibility judge,
2026-11-11), consistent with noodles in the mix. A heading-level unit value therefore blends
products. The Italian-restaurant basket lists only lines whose descriptions name pasta (dry, filled
or fresh as the reviewer decides) and excludes lines that name instant noodles. The heading-level
8.69 and 11.45 are regression checks (section 10), never displayed figures.

## 8. Places, named public venues and real businesses

| ID | Requirement |
|---|---|
| PUB-47 | `pub_place` is built only from Overture release 2026-10-21.0, schema 2.0.0. The places layer also takes `places_fsq` as a third source, in a table of its own (`pub_place_fsq`, PUB-102), never merged into `pub_place`; OpenStreetMap points are still never merged (PUB-55). Changing the release is a reviewed registry change that re-runs place verification for the showcase areas. |
| PUB-48 | `pub_place` holds only source-given `place_id`, names, category, coordinates, cell, source release, `source_provider`, `licence`, `confidence` and reviewed `merged_ids`. Verification is separate in `pub_place_verification`, keyed to `pub_place`, with check date, reviewer role, verification link and status. No synthetic or invented attribute (staffing, licence status, sales, footfall, survival or rating) is ever joined to a named place. Published visitor counts of named public venues are Public facts in `pub_venue_visits` (PUB-91) and their relative busyness by hour is a Public fact in `pub_venue_busyness` (PUB-101), never columns of `pub_place` and never footfall. |
| PUB-49 | The display threshold is confidence of at least 0.7 outside showcase areas (**ASSUMPTION:** research counts about 11,400 such records; it trims junk while keeping most named places). Inside showcase areas, the verification status overrides confidence. |
| PUB-50 | Every places answer carries the standing note "Open listings are incomplete": about 26,000 Qatar records against 71,203 establishments counted in Census 2020 (`places_ovt`, `est_census`). Places are named points, never a count of businesses; an absent category reads "not found in public places data". |
| PUB-51 | De-duplication: two records are duplicate candidates when their normalised names match in either language and they lie within 50 m (**ASSUMPTION:** a typical mall-unit spacing). Outside showcase areas the higher-confidence record is kept and the other recorded in `merged_ids`; inside showcase areas the reviewer decides. |
| PUB-52 | Each showcase area (Lusail, West Bay, Msheireb, The Pearl) is defined in `showcase_areas.yaml` by a pin at a named public landmark and the 10-minute `walk` area from it (**ASSUMPTION:** covers the flagship default of walk 5 minutes with margin). Verification covers every place in food-service categories and every place named in a prepared story answer. |
| PUB-53 | Each verified place has a status (`verified_open`, `closed_or_moved`, `not_found`, `duplicate`), check date, reviewer role and verification link in `pub_place_verification`. Results are committed as `verified_places.csv` with the licence texts of the sources it derives from (PUB-21). |
| PUB-54 | Acceptable verification sources are official directories: the tenant directory of the development, mall or district operator, the place's own official website, or a public-authority listing (**ASSUMPTION** on the last two). Review sites, delivery or booking platforms and map-search listings are not sources, and no site is scraped for verification; checks are made by hand. The page parsers of section 3.2 read only the two investment sources of [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) and are not verification sources; neither is the page reader of `busy_gmaps` (PUB-101). |
| PUB-55 | OpenStreetMap points of interest may be viewed by the reviewer as a cross-check aid but are never merged into `pub_place` or `pub_place_fsq` (this keeps ODbL share-alike out of the places tables). |
| PUB-56 | A verified place that is `closed_or_moved` or `not_found` is hidden in showcase answers; the count of hidden records is shown in the coverage note. |
| PUB-91 | `pub_venue_visits` holds the published monthly visitors of museums and exhibitions (`visits_museum`) and the annual patient visits of health centres (`visits_phcc`), keyed by the venue key of PUB-89. They are Public facts of `place_public` subjects, each with its source and year (or month), worded as published visitor counts, never as presence estimates or footfall. The relative busyness of the same venues is a separate Public measure (PUB-101); neither a visitor count nor a relative index ever shares a component with an estimated-people figure. Their monthly shape (each month's share of its year), computed by tested code, is the public shape against which [05](05_SYNTHETIC_WORLD_AND_SIMULATION.md) calibrates and checks the seasonal profile of simulated visitors; the health-centre series serves only as an annual cross-check. A named place's level is never transferred to a Simulated figure, no Simulated figure is attached to a named place, and simulated presence near a venue is worded "estimated people around this location", never "footfall of" the venue ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)). |
| PUB-92 | Real businesses appear only as points from public places data (`pub_place`, PUB-47 to PUB-56) and from public listings registered in section 2 with a licence or basis of use, plus the FDI projects of PUB-87 ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 13). A public listing enters only through a reviewed registry change naming its source, licence, release table and attribution; until one is recorded, real business points come from `pub_place` alone. A real business keeps only its source-given fields: no Synthetic or Simulated figure, and no fit, rank, score, estimate or share computed with a Synthetic or Simulated input, is attached to it, and it is never joined to synthetic firm data; the relative busyness of a venue (PUB-101) is a source-given Public slot of its `place_public` subject. Competitors from public listings enter the site estimate (card C33) as counts and distances only, and the catchment-share scenario (card C34) as the share of the user's outlet and the share of the competitors split by competitor category and distance band, never per named business: no figure for a named competitor is computed for display, shown, stored or logged. [Decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) registers `places_fsq` (PUB-102) and the venues of `busy_gmaps` (PUB-101) by this route. |
| PUB-93 | Public tenders appear, in D4, only from a public source registered in section 2 with its licence and reference period. The source is confirmed at slice S2 ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md)); until one is recorded, no tender is shown and a request for tenders returns `NO_DATA` with its caveat (section 12). No Synthetic or Simulated figure is attached to a tender. |
| PUB-101 | Relative busyness of named venues ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 19, card C37). `pub_venue_busyness` holds, for each venue of a build-time list, the relative index from 0 to 100 by day of week and hour with its retrieval date. It is a Public fact of a `place_public` subject, labelled "Google Maps popular times, relative busyness, retrieved {date}", never a count of people, and it never shares a component with an estimated-people figure or a published visitor count (PUB-91). The project's own page reader fetches it inside `./eii build-public` only, for the named venues of the build-time list, never at run time and never from a user's choice of site; the fixtures of the page reader are invented pages (PUB-86). A second committed crosswalk, `custodian/publicdata/review/venue_busyness_crosswalk.csv`, maps each venue seen in the source to one venue key and to the `pub_place` record that a reviewer finds, with reviewer role and date, like PUB-89: an unmapped name fails the build and a venue with no reviewed match has no map point. The values stay in the uncommitted public cache and never enter the repository or a test fixture, and the source is left out of the nightly live fetch. The fetch is no verification of a place and no evidence that it exists (PUB-54). The registry entry has `licence_basis: owner_decision` and `decision_record: 0019` (PUB-12). Only the hour-of-day shape pooled over the named venues of a place category may calibrate the simulation ([05](05_SYNTHETIC_WORLD_AND_SIMULATION.md)): no venue's own level or shape enters a generator, no Simulated figure takes its level from a named place, and a venue card with its busyness chart shows no estimated-people figure (PUB-61). |
| PUB-102 | Foursquare Open Source Places ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 21). `places_fsq` is a further source of the places layer, for competitors and typical neighbours. It has a table of its own, `pub_place_fsq`, which holds the source-given fields only and is never merged into `pub_place`; its attribution is its own (PUB-23, section 4). Its categories enter the activity spine only through a reviewed category mapping (PUB-38), and the real-name collision checks of PUB-61 and SYN-20 extend to it. Its display threshold and its de-duplication against `pub_place` (PUB-49, PUB-51) are fixed at the first fetch, when its fields are known. It is fetched inside `./eii build-public` from the public copy on Source Cooperative, `https://data.source.coop/fused/fsq-os-places/` (host `data.source.coop`, PUB-03), geospatially partitioned GeoParquet, read without an account; only the files that cover Qatar are fetched (**ASSUMPTION**: found through the dataset's own metadata file; the task that builds the fetcher confirms it). The copy's README states the Apache License, Version 2.0 and the publisher's copyright line (read 2026-11-12). Its listing holds three dated releases, the newest dated 2025-01-10, and states no update rhythm: the registry records the release used and the places are shown with that date. The owner decided on 2026-11-12 that this copy, dated 2025-01-10, is used for version 1 as it is: no account is opened and no newer release is fetched for now. Where a place of the copy disagrees with OpenStreetMap or Overture, which are current, the newer source wins. In the de-duplication of the copy against the places layer (PUB-49, PUB-51) the record of the newer source is kept, and the copy's row for that place is not shown or counted against it; OpenStreetMap points are still not merged (PUB-55), and where the reviewer's cross-check against them disagrees with the copy, the reviewer follows OpenStreetMap. No variable or secret is added for this source. The competitor categories of the catchment-share scenario (card C34) come from the reviewed category mapping of this layer. OpenStreetMap points are not merged (PUB-55). |

## 9. Flagship building selection

Story scene 3 places the Italian restaurant at "the chosen Lusail building". slice S2 verifies and
shortlists candidates; the owner confirms the pin and default cut-offs only after the slice S5
survival report exists. The open extract varies sharply between buildings: one candidate tower had
no restaurant within 250 m while another Lusail landmark had fifteen (master design section 6,
from a judge's check on 2026-11-11).

**Candidate list (initial):** named Lusail buildings found in the Overture buildings theme by the
project research: Manarat Lusail, Burj Al Fardan, Marina Twin Towers, Place Vendôme, Q Tower,
QiG Tower, Sendian Tower. The slice S2 builder may add candidates; each needs a footprint in `bldg_ovt`.

| ID | Requirement |
|---|---|
| PUB-57 | A candidate passes only if all checks hold: (a) named footprint in `bldg_ovt` inside zone 69 or zone 70 (Al Daayen); (b) at least 8 `verified_open` restaurants within the 5-minute walk area; (c) at least 2 `verified_open` Italian restaurants within the 10-minute walk area; (d) `make_area` builds the walk 5 and drive 10 areas without error; (e) the building is a public, commercial or mixed-use landmark, not a private residence. Thresholds (b) and (c) are **ASSUMPTION:** the minimum that makes scene 3's competitor card non-trivial. |
| PUB-58 | slice S2 records passing candidates. After the slice S5 survival report exists, the owner confirms the pin and default cut-offs. The snap and survival reports state any coarsening honestly; no privacy rule is tuned to make the area look finer. If no candidate passes, candidates are added; thresholds change only through a decision record. |
| PUB-59 | The final choice is recorded after the slice S5 survival report in `docs/decisions/NNNN-flagship-building.md`, with every candidate and check result, the places release, verification date, reviewer role, survival result, chosen building and reason, and in `custodian/publicdata/review/flagship.yaml`, which the build reads. |
| PUB-60 | The flagship record also stores the district deal count for sale prices near the building, shown on screen with any median (the 'Lusail 69' medians rest on 6 and 13 deals for 2024 and 2025 per research). |
| PUB-61 | A grid cell may hold synthetic establishments and Public places, but no synthetic establishment carries the key, name or coordinates of a `pub_place`, gazetteer, venue or `fdi_projects` entry. A named synthetic firm is always marked Synthetic, its name never resembles a real place or business name (the build fails on a collision, BRF-31), and it is never drawn as a named point at a real address ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 12). No screen places a Synthetic or Simulated attribute, or an estimate, share or score, on a Public place, a named public venue or an FDI project. The build checks all three rules over the complete tables. |

## 10. Regression examples (master design section 9)

Each row is a test in `custodian/publicdata/tests/` marked `public_data`. These tests run at the end
of every `./eii build-public` against the cached files and block the build on failure. Census rows
run only there, because their files are never committed (PUB-13). Comparisons use unrounded source
values and round only at the end. When an upstream revision changes an expected value, the build
fails until a reviewer updates the value with a note naming the new hash (PUB-10).

| ID | Requirement: the test asserts | Dataset(s) |
|---|---|---|
| PUB-62 | Zone 69 electricity 2021 to 2025: zone 69 value for 2021 equals 429,964,072 and for 2025 equals 1,436,402,796; their ratio rounds (2 dp) to 3.34; the sum over all zones 2025 divided by 2021 rounds to 1.34 | `util_elec` |
| PUB-63 | Mean monthly pay 2020 to 2025 and its split: worker-weighted mean over populated occupation-by-sex groups (17 groups) rounds to 10,084 (2020) and 11,855 (2025); rise 1,771 and 17.6% (1 dp); Kitagawa split with average weights gives 38 within groups and 1,733 from mix; mix share from unrounded parts rounds to 97.8% (1,733 ÷ 1,771 on rounded values gives 97.9%: do not use rounded parts) | `wage_occ` |
| PUB-64 | Restaurants, activity 561, 2022: production value 6,337,897 (QAR thousand); establishments 2,086; employees 41,458; compensation 1,308,140; operating surplus 1,247,422; published average annual wage 31,579; total intermediate goods ÷ production value rounds to 40.6%, intermediate services ÷ production value to 16.5%. The slice S2 builder records the exact field and table for each value in the registry. The average wage is read, not derived: compensation ÷ employees gives about 31,553 (arithmetic check), so derivation would fail | `sec_hr_ind`, `sec_hr_goods`, `sec_hr_serv`, `sec_hr_size` |
| PUB-65 | Pasta calculated import unit value (QAR per kg), 2025: over rows with positive kg and tariff code beginning 1902, Italy Σvalue ÷ Σkg rounds (2 dp) to 8.69 and Saudi Arabia to 11.45; the Italian-restaurant basket's pasta input contains no line the basket marks as noodles; the valuation basis is shown as the source states it or as "not stated by the source" | `cus_imp_2025` |
| PUB-66 | Imports 2025: rows with year 2025 number 216,073 and their QAR value sums to 138.53 bn (2 dp in billions) | `cus_imp_2025` |
| PUB-67 | Active licence-activity counts, May 2025: 13,189 rows; Σ count 249,622; 4,755 distinct codes; the four groups reconcile to the total: 84.6% (211,277) under seven-digit codes with an ISIC-class prefix, 4.5% (11,276) under other seven-digit codes, 10.8% (26,844) under six-digit legacy codes and 0.1% (225: 169 under 13 five-digit codes and 56 under eight eight-digit codes); exactly 138 six-digit codes have a first-four-digit match to an existing ISIC class but remain `not_mappable_legacy`; the spine maps 5610101 to ISIC 5610; code 5610101 counts 361 in Al Daayen and 4,782 nationally | `lic_active` |
| PUB-68 | Cancellations 2015 to 2025: Σ count 161,055, of which 7,386 undated; July 2020 (40,791), June 2022 (14,212) and September 2024 (11,232) together divided by the dated total (153,669) round to 43%; the bulk-month rule of [07 Economic methods](07_ECONOMIC_METHODS.md) flags all three | `lic_cancelled` |
| PUB-69 | Issued series incomplete: Σ count 12,533; 610 distinct codes; zero rows for 5610101 in the source and in `pub_licence_issued`; every fact from `pub_licence_issued` carries the incompleteness note, and no net formation is built from it (PUB-94) | `lic_issued` |
| PUB-70 | Metro riders, December 2025: Metro December 2025 equals 7,375,367 and December 2024 equals 5,529,167; growth rounds (0 dp) to 33% | `transit_monthly` |
| PUB-71 | Private-employer share, two Lusail-area zones: private ÷ all employed residents rounds (0 dp) to 72% for zone 69 and 45% for zone 70; national 1,617,208 ÷ 2,050,252 rounds (1 dp) to 78.9% | `census_zone_sector` |
| PUB-72 | Restaurant licences per 10,000 residents: use the 2025 `pop_muni` values, 111,282 for Al Daayen and 3,219,982 nationally, for the May 2025 snapshot; 361 ÷ 111,282 × 10,000 rounds (0 dp) to 32 and 4,782 ÷ 3,219,982 × 10,000 rounds to 15; the period `2025` is carried on the fact | `lic_active`, `pop_muni` |
| PUB-73 | Open places extract and establishments: records with country QA in release 2026-10-21.0 number 26,383; the 2020 census establishment total equals 71,203 | `places_ovt`, `est_census` |

## 11. Reconciliation before display (OI-03)

Two pairs of public figures disagree. Neither figure of a pair may be displayed until its record is
resolved.

| Item | Figure A | Figure B | Known so far (research, 2026-11-11) |
|---|---|---|---|
| R1 Restaurant size | "restaurant revenue" QAR 8,579,462 thousand, carried from an earlier design draft | production value QAR 6,337,897 thousand, activity 561, 2022, published directly by the National Planning Council | different scope; the revenue figure was not matched to any restaurant table |
| R2 National mean pay, 2020 | QAR 10,084 from `wage_occ` | QAR 10,352 from `wage_act` | both tables report the same paid workers (2,120,841 in 2020; 2,171,062 in 2023) yet imply different means (2023: 11,714 against 11,025); cause unknown |

| ID | Requirement |
|---|---|
| PUB-74 | Sources and facts touched by R1 or R2 carry `reconciliation: open`. The release build refuses to emit any fact whose lineage includes an open item. |
| PUB-75 | R1 procedure: (1) search the portal hotels-and-restaurants tables for the field holding 8,579,462 and record dataset, field, year and activity scope; (2) compare scope on four axes: activities included (561 alone or 55 and 56), measure (revenue, sales or production value), year, and establishments covered; (3) write a decision record stating which table each card uses. Default if no match is found: the unit-economics card uses production value from `sec_hr_ind` and the revenue figure is never shown. |
| PUB-76 | R2 procedure: (1) recompute both weighted means from the fetched tables and confirm the worker totals agree; (2) record both means for every year both tables cover; (3) the national pay card uses `wage_occ` (its decomposition is by occupation; **ASSUMPTION** pending owner sign-off), names the table on the chip and shows both means in the evidence drawer; (4) the two tables are never shown as the same measure side by side; (5) optionally, a query is sent to the publisher through the portal and its answer is added to the record. |
| PUB-77 | An item closes only when its decision record exists and the owner has signed it off; the registry then sets `reconciliation: resolved:<record>`. |

## 12. What public data cannot give, and how the product says so

| Gap | Evidence (research, 2026-11-11, unless stated) | What the product shows |
|---|---|---|
| Rent by district | no official open rent dataset found; the real-estate regulator's weekly press releases give rent contracts by municipality only | break-even takes the user's own rent; caveat "No official rent data by district is published" |
| Openings for restaurant codes | `lic_issued` excludes restaurant codes and sums to 12,533 against 161,055 cancellations | churn shows cancellations only, with "Openings are not published for this activity; net change is unknown" |
| An official input-output table | none found for Qatar; OECD ICIO 2025 covers the UAE and Saudi Arabia but not Qatar | first-round purchases from survey cost shares only; no multiplier anywhere (dropped, master section 3.3) |
| Licences below municipality | open tables are municipality by code | "Municipality figure: Al Daayen is wider than Lusail" |
| Zone population after 2020 | the portal zone table repeats one census snapshot | census shares dated "Census 2020" |
| Cuisine in licences | one restaurant code; no cuisine code | cuisine only from public places, labelled incomplete |
| Station or hourly ridership | national monthly totals only | monthly Public context, never hourly counts |
| Pay percentiles or pay by area | public wage tables give national means only | public means beside Synthetic bands, each marked |
| Public tenders | [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) (2026-11-12) leaves the public source open until slice S2 | no tender is shown until a source is registered (PUB-93); caveat "No public tender source is recorded" |
| A series too short to forecast | the backtest of card C30 needs a minimum series length, fixed in [07](07_ECONOMIC_METHODS.md); several listed series are short, for example `prop_resi_units` (570 rows from 2025-08-24) | `NO_DATA` with reason key `series_too_short`, shown as "not enough history"; never a model without a backtest |
| A base rate without its denominator | the Public tables carry a count for some activities, areas and periods only; the Public licence tables do not link a cancellation to its issue, so a survival base rate has no denominator; `lic_issued` lacks the restaurant, cafeteria, general contracting and foodstuff trade codes | `NO_DATA` with reason key `no_denominator` (PUB-104) |
| A listed series with no source table | producer prices, and the parameters that turn permits into expected new households and workers, have no registered source table (decision 0019 item 2) | listed as open in the table of PUB-103 and not on the list of card C30; no caveat key is made for it, and a question about a forecast of it is declined as a series that is not on the list (`forecast_not_offered`) |

| ID | Requirement |
|---|---|
| PUB-78 | Each gap above except the last (a series with no source table, which is not on the list of card C30) has a `caveat_key` with English and Arabic text (Arabic pending native review, OI-09), attached by the application, not by the model, whenever a question touches the gap; the reason keys `series_too_short` and `no_denominator` are caveat keys of the same kind. |
| PUB-79 | A tool asked for one of these gaps returns `NO_DATA` with the caveat key, never a zero, a proxy dressed as the figure, or an estimate from another economy. |
| PUB-94 | The Public part of the openings and closures view ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 11) shows licence issues from `lic_issued` and licence cancellations from `lic_cancelled` over time on their official geography, worded on screen as licence issues and cancellations, never as business openings or closures ([07 Economic methods](07_ECONOMIC_METHODS.md) C2 and C22). Issues are shown only for the codes the issued series covers, and every issue fact carries the note that the series is incomplete; no net formation (issues minus cancellations) is computed or shown. A code the issued series lacks reads "New licences for this activity are not published, so net change is unknown". Cancellations keep the bulk-month flag of C2. |
| PUB-103 | Forecasts of published series ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) items 2 to 6, card C30; MTH-98 in [07](07_ECONOMIC_METHODS.md) states the model rule). A Public series is forecast only when this pack holds its source table: the series of the first list and the table of each are in the first table below, and a named series without a table is listed there as open and is not on the list of card C30. Card C30 also takes the released monthly series of the window, listed in the second table: they are release tables of the custodian-type feeds, not Public sources, and a forecast of one is a fixed function of rows that are already released. The horizon of a Public series is counted from the source's recorded last period (PUB-08, PUB-16), never from a modified date; that of a released series, from the last released month. A series below the backtest minimum returns `NO_DATA` with reason key `series_too_short`, shown as "not enough history". A released series with a carried-forward month in its window is not forecast and returns the `CARRIED_FORWARD` suppression, as card C21 rules for projections. The provenance of a forecast is the least-real class of its input series (PUB-20): Public for a Public series, Synthetic for a released series, which carries the word "forecast" and the caveat keys `synthetic_not_evidence_about_qatar` and `synthetic_change` beside `forecast_backtest_range`. Its evidence status is Inferred, and its subject and geography are those of its series (the `area` of a released series). A released series is off in public-only mode as a ranking criterion. The licence series keep the names licence issues and licence cancellations (PUB-94): each is forecast on its own and never as a net series, and an issue forecast exists only for the codes the issued series covers. A forecast whose lineage includes an open item of section 11 is not emitted (PUB-74). A publisher's own forecast on a page (PUB-88) is not a forecast of this kind. |
| PUB-104 | Base rates ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 7, card C31). The closure and entry base rates are flows over the published active stock of the same activity and geography, computed from the Public licence tables by activity and on the source's own geography, never for a drawn area and never from the Synthetic births and closures. Each is labelled approximate and shows its numerator, its denominator and its period, and is computed only where the Public tables carry the active stock for that activity, area and period; elsewhere the answer is `NO_DATA` with reason key `no_denominator`. The survival base rate returns `NO_DATA` with reason key `no_denominator`, because the Public licence tables do not link a cancellation to its issue, until a Public source does (OPEN, in the open questions below); no survival figure is promised. The screen words are the licence issue rate and the licence cancellation rate (PUB-94), and a rate is worded as a share of past licences of that activity and area, never as the chance that the user's own venture survives. A stock before the snapshot of `lic_active` is never rebuilt from issues and cancellations, and no net figure is computed or shown (PUB-94). The undated cancellations and the bulk months (PUB-68) are shown beside every rate that touches them, and the bulk-month rule of the method card applies. A code the issued series lacks has no issue rate (PUB-69). A base rate is a Public fact with evidence status Observed, the status of the churn rate of card C2 (fixed arithmetic over published counts, caveat `calculated`), and it carries the caveat key `base_rate_not_your_chance`. A regression test rejects a base-rate fact with a different provenance class, a different evidence status or a missing caveat. |

The series of the first list of decision 0019 item 2, and the source table that holds each:

| Series | Source | Release table | State |
|---|---|---|---|
| Licence issues by activity and municipality | `lic_issued` | `pub_licence_issued` | held; only for the codes it covers (PUB-69) |
| Licence cancellations by activity and municipality | `lic_cancelled` | `pub_licence_cancelled` | held; to May 2025, with the bulk months flagged |
| Property prices by district | `prop_sales` | `pub_property_sale` | held; to 31 December 2025, with the deal count |
| Hotel demand and room rates | `hotel_segment` | `pub_hotel_monthly` | held; to March 2025 |
| Consumer prices | `cpi_group` | `pub_price_index` | held; monthly 2020 to 2025 |
| Producer prices | none | none | open: no source table yet |
| Imports by product | `cus_imp_2025` and `cus_imp_2019` | `pub_customs_import` | held; one series by the roll-up of PUB-44 |
| Announced investment by sector | `fdi_projects` | `fdi_projects` | held; with the notes of PUB-87 |
| Construction pipeline by municipality (permits) | `permits_muni` | `pub_building_permits` | held; series end in 2023 |
| Expected new households and workers from the pipeline | none for the conversion parameters (`census_hh_type_2020` is registered but has no release table until slice S2 confirms its columns) | none | open: no source table yet |

The released monthly series that card C30 also takes ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 6). They are release tables of the custodian-type feeds, not Public sources, and have no row in section 2:

| Series | State |
|---|---|
| Pay level, earner count and wage bill | released for each month of the window; Synthetic |
| Stayer index at municipality level | released for each month of the window; Synthetic |
| Establishments and employment by area | released for each month of the window; Synthetic |

## Open questions and assumptions

ASSUMPTIONS (each also listed in the return message):

1. Section 7 (used by PUB-34 and PUB-41): v1 playbook activities are ISIC 5610, 5630 and 5510, all covered by the
   hotels-and-restaurants survey tables.
2. PUB-49: display threshold of confidence at least 0.7 outside showcase areas.
3. PUB-51: 50 m and matching normalised names define duplicate candidates.
4. PUB-52: a showcase area is the 10-minute walk area from a named landmark pin.
5. PUB-54: operator websites and public-authority listings count as official directories.
6. PUB-57: flagship thresholds of 8 verified restaurants (walk 5) and 2 verified Italian
   restaurants (walk 10).
7. PUB-76: the national pay card uses `wage_occ`.
8. File paths under `custodian/publicdata/` (registry, `review/`, `tests/`) are this document's
   choice within the pinned layout.
9. PUB-85: a decision 0017 source-id family keeps one `source_id` and has one registry entry per
   slug, keyed `<source_id>/<slug>`. The key format is this document's choice; `source_id` stays
   the registry key of [03](03_DATA_CONTRACTS.md).
10. Section 2.2: the release-table names of the decision 0017 source-id families and
    `pub_investqa_record` are this document's choice; [03](03_DATA_CONTRACTS.md) holds their
    columns.
11. PUB-87: reading the dashboard on every build detects a changed page; the changed page enters a
    release only through the reviewed registry change of PUB-10.
12. PUB-89: health-centre names use the venue crosswalk too, and a venue links only to a `pub_place`
    record.
13. PUB-88, as stated by decision 0017: incentive packages are optional scenario inputs of the
    break-even calculator, tagged "your inputs" with their source page; they never change a Public
    figure.
14. PUB-94: the public licence issues of decision 0016 come from `lic_issued`, shown only for the
    codes it covers and always with its incompleteness note.
15. PUB-95 and PUB-97: `fetch_mode: live_session` (the listing of the traffic provider, which has
    no row in `source_registry`) and `licence_basis: provider_terms` (the traffic provider and the
    free Open-Meteo interface) are this document's choice.
16. PUB-100: a pixel counts in the frame cell that holds its centre, with none split, as item 22
    of decision 0019 does for the population grid; the rule is this document's choice, confirmed at
    slice S2.
17. PUB-101: the build-time list of venues is the named venues of the showcase areas (PUB-52) and
    the venues of PUB-89, and the crosswalk file is `venue_busyness_crosswalk.csv`; the owner may
    change either.
18. Section 12: the reason keys `series_too_short` and `no_denominator` are those of decision 0019;
    a series of the owner's list for which this pack holds no source table is listed as open and is
    not on the list of card C30, and no caveat key is made for it.
19. PUB-102: the files of the `places_fsq` copy that cover Qatar are found through the dataset's own
    metadata file; the task that builds the fetcher confirms it ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 21).
20. PUB-102: decided, no longer an assumption (OI-96, closed): the owner decided on 2026-11-12 that
    the `places_fsq` copy, dated 2025-01-10, is used for version 1 as it is: no account is opened and
    no newer release is fetched for now. Where a place of the copy disagrees with OpenStreetMap or
    Overture, which are current, the newer source wins.

Open items touching this document: OI-03 (section 11; while it is open the survey benchmark of the
site estimate and of the revenue range stays off screen, PUB-74), OI-04 (closed for version 1 by decision
0017 item 10: the census map layers enter the local release and the 2020 boundary layers only
check HDX geometry, PUB-13; any wider use is a deployment item of document 17), OI-06 (source
labels for custodian record types; public attribution follows section 4), OI-09 (Arabic names and
caveats).

Open questions: whether UNSD publishes ISIC Rev.4 titles in Arabic (not confirmed on the UNSD page,
2026-11-11; otherwise reviewed team labels); the valuation basis of the customs values; and the
publisher, licence, direct URL or source schema entries explicitly marked to be confirmed at
slice S2.

- OPEN: the page structure of the dashboard and of the agency's pages, the agency's page list,
  where each publisher states its terms, and whether a project's location is a point or a city are
  confirmed at slice S2, against a synthetic test page of the same shape (decision 0017).
- OPEN: whether the dashboard page holds an identifier column, and how PUB-14 applies to it, is
  settled at slice S2 with the page structure.
- OPEN: the public source of tenders is confirmed at slice S2; without one, tenders are not shown
  (decision 0016, PUB-93).
- OPEN: the public listings beyond `places_ovt`, with their licences, are confirmed at slice S2
  (PUB-92).
- OPEN: the apportioning weight for drawn shapes (area, or a licensed public population grid such
  as `worldpop_qat_2020`) is fixed in [07](07_ECONOMIC_METHODS.md) and confirmed at slice S2
  (decision 0016).
- OPEN: the expected row-count range and last period of each new slug and of `fdi_projects`
  (PUB-08), and one regression example per new source-id family (section 10), are fixed at the slice
  S2 gate; the same holds for each source of decision 0019 that `build-public` fetches.
- OPEN: the hosts, file URLs, schemas, last periods and exact terms and attribution text of the
  sources of decision 0019 that `build-public` fetches are recorded at their first fetch.
- OPEN: the traffic provider's terms, read in full on 2026-11-13, license the free plan for internal evaluation
  and testing only and prohibit storing results; nothing is stored (PUB-95); showing the live layer outside internal
  evaluation is the owner's decision (OI-130).
- OPEN: the Public source of each series of decision 0019 item 2 for which section 12 lists no
  table: producer prices, and the parameters that turn permits into expected new households and
  workers.
- OPEN: a Public source that links a cancellation to its issue, so that a survival base rate has a
  denominator; until then it returns `NO_DATA` with reason key `no_denominator` (PUB-104).

## Sources

All retrieved 2026-11-11 unless stated.

- Qatar Open Data Portal, dataset pages and Explore API v2.1, `https://www.data.gov.qa/`, for every
  portal `source_id` in section 2; licence page `https://www.data.gov.qa/pages/license/annexes`.
- Qatar Open Data Portal, catalogue export and record queries (Explore API v2.1),
  `https://www.data.gov.qa/api/explore/v2.1/`, for the 77 datasets of decision 0017 (slug,
  publisher, licence, modified date, rows, first and latest period), retrieved 2026-11-12; the same
  portal answers at `https://www.data.qa/`.
- FDI Projects dashboard, `https://fdiprojects.invest.qa/` (data from fDi Markets), read
  2026-11-12, including its statement that its data includes estimates of publicly announced
  projects, does not capture all investment projects and is subject to change.
- The national investment promotion agency's site, `https://www.invest.qa/` (sector, opportunity,
  incentive, set-up and law pages), read at each fetch; its page list and structure are confirmed
  at slice S2.
- [Decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md),
  [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) and
  [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md),
  recording the owner's decisions of 2026-11-12.
- TomTom, Traffic API documentation and pricing page, `https://docs.tomtom.com/traffic-api/` and
  `https://docs.tomtom.com/pricing`; copyright page of the map service,
  `https://developer.tomtom.com/tomtom-orbis-maps/documentation/copyright`; read 2026-11-12.
- Google, "About popular times, wait times and visit duration data",
  `https://support.google.com/business/answer/6263531`; Terms of Service,
  `https://policies.google.com/terms`; Maps additional terms,
  `https://www.google.com/intl/en/help/terms_maps/`; Places interface reference,
  `https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places`
  (it lists no popular-times field); read 2026-11-12.
- NASA, product page of VNP46A3,
  `https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VNP46A3/` (DOI
  10.5067/VIIRS/VNP46A3.002), and data and information guidance,
  `https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-information-policy`;
  read 2026-11-12.
- Foursquare, access page of the places dataset,
  `https://docs.foursquare.com/data-products/docs/access-fsq-os-places` (Apache 2.0); the public copy
  on Source Cooperative, `https://data.source.coop/fused/fsq-os-places/` with its README and its
  listing; read 2026-11-12.
- WorldPop, age and sex structures, `https://hub.worldpop.org/project/categories?id=8` and
  `https://hub.worldpop.org/geodata/listing?id=138` (CC BY 4.0; DOI 10.5258/SOTON/WP00841); read
  2026-11-12.
- Open-Meteo, terms, licence page and historical weather documentation,
  `https://open-meteo.com/en/terms`, `https://open-meteo.com/en/licence` and
  `https://open-meteo.com/en/docs/historical-weather-api`; read 2026-11-12.
- Statistics authority public ArcGIS services,
  `https://services7.arcgis.com/mffQJB8rpVa5We20/arcgis/rest/services`.
- HDX, Qatar Subnational Administrative Boundaries, `https://data.humdata.org/dataset/cod-ab-qat`.
- geoBoundaries, `https://www.geoboundaries.org/api/current/gbOpen/QAT/ALL/`.
- GADM licence, `https://gadm.org/license.html` (reason for exclusion).
- Overture Maps Foundation: release catalogue `https://stac.overturemaps.org/2026-10-21.0/catalog.json`;
  places guide `https://docs.overturemaps.org/guides/places`; attribution page
  `https://docs.overturemaps.org/attribution/`.
- Community Data License Agreement Permissive 2.0, `https://cdla.dev/permissive-2-0/`.
- OpenStreetMap copyright and licence, `https://www.openstreetmap.org/copyright`; Qatar extract
  `https://download.openstreetmap.fr/extracts/asia/qatar-latest.osm.pbf`.
- United Nations Statistics Division, classifications, `https://unstats.un.org/unsd/classifications/Econ`
  and `https://unstats.un.org/unsd/classifications/Econ/isic`.
- International Labour Organization, "Qatar adopts non-discriminatory minimum wage",
  `https://www.ilo.org/resource/news/qatar-adopts-non-discriminatory-minimum-wage`.
- Planning and Statistics Authority, Census 2020 detailed results workbook, archived at the URL
  recorded for `census_2020_workbook` in section 2.1.
- WorldPop, constrained 100 m population and method note, URLs recorded for `worldpop_qat_2020`
  in section 2.1 and in [05](05_SYNTHETIC_WORLD_AND_SIMULATION.md).
- Citation-only public documents `ref_*`: publisher, title and URL are recorded in section 2.1.
- Qatar News Agency, activity classification update, 1 June 2026,
  `https://qna.org.qa/en/News-Area/News/2026-6/1/moci-launches-commercial-activity-classification-update-for-registered-companies`.
- Qatar News Agency, weekly real-estate press release (rent by municipality only), 18 October 2026,
  `https://qna.org.qa/en/News-Area/News/2026-10/18/aqarat-real-estate-sales-value-rises-in-42nd-week-of-2026`.
- OECD ICIO 2025 annex country list,
  `https://www.iioa.org/conferences/32nd/papers/files/5640_ICIO-tiva-ghg2025annex.pdf`.
- Project research and judges' checks of 2026-11-11 (public economic data, graph value, economic
  methods, public geography and statistics, feasibility and cost) for all counts and figures not
  re-fetched by the author.
