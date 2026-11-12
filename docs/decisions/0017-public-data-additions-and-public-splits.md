# 0017 — Public data additions, public splits by sex and nationality, and investment sources

| | |
|---|---|
| Status | Accepted, 2026-11-12 (amendment 4 to the first pack) |
| Date | 2026-11-12 |
| Owner | albarami |
| Purpose | Record the owner's decisions of 2026-11-12 that add 77 portal datasets and two investment sources to the public data pack, that use the census map layers in this internal project, that show official figures split by sex or nationality as Public facts, and that use published visitor counts of named public places to calibrate and check the simulated footfall. |
| Read first | [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md), [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md), [decision 0016](0016-version-1-covers-the-whole-initiative.md) |

## Context

- The pack used 28 datasets of the Qatar Open Data Portal, licensed CC BY 4.0, recorded in [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md) section 2 with publisher, slug, coverage, last period and licence.
- The pack dropped "any nationality dimension or proxy; any sex split at area level" ([01_PROJECT_BRIEF.md](../01_PROJECT_BRIEF.md) section 9.3), and BRF-31, SYN-13 and AGENTS.md rule 10 enforced it everywhere, Public figures included.
- The journeys of [decision 0016](0016-version-1-covers-the-whole-initiative.md) need more public evidence: property prices, the construction pipeline, employer scale by activity, industrial capacity, the workforce by sex and nationality, visitor source markets and investment projects.
- On 2026-11-12 the owner decided to add the portal datasets of a scan of the whole catalogue (2,082 datasets, read that day), to use public splits by sex and nationality, and to use the FDI dashboard and the investment pages of the national investment promotion agency as sources of this personal internal project.

## Decision

### Portal datasets

1. **77 further portal datasets join the public data pack**, licensed CC BY 4.0 like the 28 already used, in seventeen groups. Each is listed in [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md) section 2 with its slug, publisher, rows, coverage and latest period as the portal's catalogue and records showed them on 2026-11-12, its licence line, the journeys that use it and its known traps; the fetcher records them again at every fetch (PUB-09, PUB-16). Every figure from them is shown as Public with its source, its reference year (or month) and its retrieval date.

   | Group | Datasets | Publisher | Latest period (2026-11-12) | Used in |
   |---|---|---|---|---|
   | Residential unit sales (weekly bulletin) | 1 | Ministry of Justice | December 2025 | D2, D6, the reverse location view |
   | Visitors of museums and exhibitions by month; patient visits by health centre | 2 | National Planning Council; Primary Health Care Corporation | 2024 | footfall calibration and check; named public places |
   | Building permits and completion certificates (national and monthly by municipality) | 10 | National Planning Council | 2023 | D6, the reverse location view |
   | Establishments and employees by size and activity, with compensation | 7 | National Planning Council | 2019 to 2022, by bulletin | D1, D3, S1, cases C1 and C2 |
   | Manufacturing industries and main products | 21 | Ministry of Commerce and Industry; National Planning Council | 2025; 2022 | D4, D7, S3, case C1 |
   | Wholesale and retail purchases, sales and stocks | 1 | National Planning Council | 2022 | D1, S1 (context only, never a forecast) |
   | Population by municipality and age | 1 | National Planning Council | 2024 | D3 |
   | Hotels and hotel apartments by municipality | 1 | National Planning Council | 2024 | footfall calibration (visitor share); D1 |
   | Certificates of origin; arriving vessels | 3 | Qatar Chamber of Commerce and Industry; National Planning Council | 2024; 2022 and 2023 | D7 |
   | Establishments and employees by municipality, census 2015 | 1 | National Planning Council | 2015 | calibration of synthetic firm density by municipality |
   | Population, labour force, employed and unemployed by sex and municipality | 4 | National Planning Council | 2025 | D5 |
   | Population by municipality, age and sex | 2 | National Planning Council | 2023 | D3 |
   | Economically active population by sex, age and activity | 2 | National Planning Council | 2023 | D5 |
   | Economically active Qatari and non-Qatari population by occupation and activity | 6 | National Planning Council | 2023 or 2024 | D5 |
   | Employees and compensation by nationality and activity | 10 | National Planning Council | 2021 or 2022 | D5, D1 |
   | Students by level, municipality, sex, type and nationality | 1 | Ministry of Education and Higher Education | school year 2025-2026 | D3, D5 |
   | Hotel guests by nationality; visitor arrivals | 4 | National Planning Council; Qatar Tourism | 2022; 2024 and 2025 | D1, D3 |

2. **Both portal hosts are allowed.** The portal answers the same API at `www.data.qa` and `www.data.gov.qa`; both join the fetcher's allow-list (PUB-03), and the registry records the host each file came from. A dataset is identified by its slug whichever host served it.

### Named public places and the simulated footfall

3. **Published visitor counts are Public facts of named public places.** The monthly visitors of museums and exhibitions, by venue, and the annual patient visits by health centre are shown as Public facts of `place_public` subjects, each with its source and year. They are real counts for named public places; they are not presence estimates.
4. **Their seasonal pattern calibrates and checks the simulated footfall.** The monthly shape of the museum visits (each month's share of its year) calibrates the seasonal profile of simulated visitors, and a test compares the simulated shape with the public shape within a stated tolerance; hotel supply by municipality calibrates the visitor share. The health-centre series is annual and serves only as an annual cross-check. A named place's level is never transferred to a Simulated figure, and no Simulated figure is attached to a named place. Venue names vary between years; the build normalises them through a committed, reviewed crosswalk and never edits a value by hand.

### Splits by sex and nationality

5. **Official figures split by sex or nationality are used.** They are shown as Public facts with their source and year, on the source's own geography and categories (for nationality, the published Qatari and non-Qatari categories). The exclusions of the Dropped list, BRF-31 and SYN-13 and AGENTS.md rule 10 now apply to the synthetic records only: the synthetic records still carry no sex, gender or nationality, and none is derived for them. No Public split is joined to a synthetic record, used to segment synthetic records, apportioned to a drawn area or combined with a protected figure.

### Investment sources

6. **The FDI dashboard.** The national investment promotion agency's FDI projects dashboard (`fdiprojects.invest.qa`, data from fDi Markets) embeds about 1,596 announced projects in one page. The fetcher reads that page on every build and loads every project field into the new contract `fdi_projects`. The projects are a Public source on the map and in every journey where they help (D1, D4, D6 and D7, the market entry pack and the expansion comparison). Capex and jobs keep the source's own note that they are estimates of publicly announced projects, and that the dashboard does not capture every project.
7. **The agency's site.** The fetcher loads the sector, opportunity, incentive, set-up and law pages of `www.invest.qa` into structured records: sector context, the market entry pack, the set-up steps, and the incentive packages offered as optional inputs of the break-even calculator ([07_ECONOMIC_METHODS.md](../07_ECONOMIC_METHODS.md)). Text is rendered by application templates from those records, with a link to each page.
8. **As with every source**, each figure shows its source and retrieval date, and the data stays in the uncommitted `data/` folder. Only the fetcher, the parser, the contract and their tests are committed; the tests use a small synthetic page shaped like the real one. Both hosts join the allow-list. The registry records the publisher's own terms as read at fetch and the basis of use: the owner's decision of 2026-11-12 for this personal internal project, without a permission request.
9. **Real companies in the project records.** An FDI project names a real investing company. Its subject, `fdi_project`, accepts Public slots only: no Synthetic or Simulated fact is attached to it, it is never joined to synthetic firm data, and it is shown as a published announcement with its source and the estimate note, never as a lookup of a firm.

### Census map layers

10. **The census map layers are used in this internal project** (owner's note of 2026-11-12). The statistics authority's public map-service layers, which state no licence (`census_zone_sector`, `census_zone_occ`, `census_zone_hh`, `census_zone_lab`, `census_district_pop`, `bnd_zone_2020`, `bnd_district_2020`), may enter the local release and be shown, each figure with its source and retrieval date; nothing fetched from them is committed. OI-04 is closed for version 1. The written licence question for any use beyond this internal project is a real-deployment item in `docs/17_DEPLOYMENT_HARDENING.md`. The archived census 2020 workbook is not a map layer and stays validation-only (PUB-13).

## Evidence

- The portal's catalogue metadata and record queries of 2026-11-12 for each of the 77 slugs (publisher, licence, modified date, rows, first and latest period), read by the lead; the fetcher re-records them.
- The dashboard's own statement that its data includes estimates of publicly announced projects, does not capture all investment projects and is subject to change (the dashboard page, read 2026-11-12).
- The owner's decisions of 2026-11-12 (project records held by the owner).

## Consequences

- AGENTS.md and CLAUDE.md rule 10 reads: no nationality, sex or gender attribute, dimension or proxy on the synthetic records or on anything derived from them; official figures split by sex or nationality appear only as Public facts with source and year. Rule 8 names `fdi_project` among the Public-only subjects.
- [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md) gains the registry rows, coverage rows, the two hosts, the licence basis of the investment sources, the venue crosswalk and the Public split rule; [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md) gains the release tables and `fdi_projects`; [05](../05_SYNTHETIC_WORLD_AND_SIMULATION.md), [06](../06_PRIVACY_AND_DISCLOSURE_CONTROL.md), [07](../07_ECONOMIC_METHODS.md), [09](../09_AI_ASSISTANT.md), [10](../10_FRONTEND.md), [12](../12_TESTING_AND_QUALITY.md), the [glossary](../GLOSSARY.md) and [01](../01_PROJECT_BRIEF.md) change where they state the replaced rules.
- The schema tests that reject sex, gender and nationality columns keep their full strength on every synthetic and protected contract; Public tables are allowed these dimensions only through their registry entry.
- If the demonstrator is ever hosted publicly, the owner decides then which sources stay on.

## What would change this decision

- A publisher's terms that forbid the use made here, found at fetch: the source is switched off and the owner is told.
- A further owner decision.

## Open questions and assumptions

- ASSUMPTION: the incentive packages are optional scenario inputs of the break-even calculator, tagged "your inputs" with their source page; they never change a Public figure.
- OPEN: the exact page structure of the dashboard and of the agency's pages is confirmed at slice S2, against a synthetic test page of the same shape.

## Sources

- Qatar Open Data Portal, catalogue export and Explore API v2.1, `https://www.data.gov.qa/api/explore/v2.1/` (CC BY 4.0, portal licence page), retrieved 2026-11-12.
- FDI Projects dashboard, `https://fdiprojects.invest.qa/` (data from fDi Markets), read 2026-11-12.
- Owner decisions of 2026-11-12 (project records held by the owner).
