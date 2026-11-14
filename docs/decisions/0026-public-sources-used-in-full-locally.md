# 0026 — Public sources used in full locally

| | |
|---|---|
| Status | Accepted, 2026-11-14 |
| Date | 2026-11-14 |
| Owner | Project owner |
| Decided by | The owner, on 2026-11-14, his words relayed by his advisor (items 1 to 6, 8 and 9); the advisor under the owner's delegation of the same morning (items 7, 10, 11 and 12), which the owner's words on public sources then confirmed for item 7 |
| Amends | Decisions 0016, 0017, 0019 and 0023 where they switch a source off, limit it or name it as an exception because of its terms; PUB-12, PUB-13, PUB-93 and PUB-108 and what repeats them; method card C4 and PUB-64; DAT-60 and SYN-57 |
| Purpose | Record full use of visitor-readable public sources in the personal, local version 1, truthful terms and a separate going-live list, with the decided corrections to the frame definition, feed minimum and restaurant norms. |
| Read first | [01_PROJECT_BRIEF.md](../01_PROJECT_BRIEF.md), [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md), [07_ECONOMIC_METHODS.md](../07_ECONOMIC_METHODS.md), [17_DEPLOYMENT_HARDENING.md](../17_DEPLOYMENT_HARDENING.md) |

## Context

Earlier rules made some sources validation-only, switched them off because of their terms, or admitted them one by one as exceptions. The owner has decided that every source readable as a visitor is used and shown in full in this personal, local project. The repository remains public. Its restrictions on committing source data remain strict. The same morning's delegated decisions settle the project display, Greater Doha's definition, the feed minimum under set B and the restaurant norms.

## Decision

1. Every public source is used and shown in full in version 1. The owner's words are: "remember this is perosonal project
this caul portal no one will see it publicly so dont limit to authirty it will stay local so i can use that data if
its public not matter who owns it. when we plant o make it for real we will follow the legel root". Version 1 is a personal, local project that nobody outside the owner's organisation sees. Every source that a visitor can read without signing in is used and shown in full, whoever owns it. Reuse terms do not switch a source off, make it validation-only, bar it from a release or limit display. A source still stays absent, with `NO_DATA` and its caveat, when it is not fetched, its file, address or schema is not confirmed, it fails checks or it cannot be read as a visitor. Those reasons keep their own names.

2. Public means what any visitor's browser receives: no sign-in, no paywall, no robot check passed, no call of a site's back end with a key or token found in its pages, and read at a visitor's pace. A source needing any of these is not read. This is the advisor's reading, adopted. The host allow-list (PUB-03) and every fetch rule stay.

3. Each source's terms are read and recorded in document 04 in the publisher's own words with the date read. The pack never says there are no terms when the publisher states some. Registry licence fields say what the publisher states: an open licence where the dataset states one (`licence_basis: dataset`), the portal's terms where only those exist (`portal_terms`), and for every source without an open licence covering the use the basis is `owner_decision`. That means the owner's decision for a personal, local project, this record. No source needs a decision naming it one by one. Decisions 0017, 0019 and 0023 remain as history.

4. Document 17 keeps one list of sources whose terms need permission or a licence before real use, with the publisher's own words and the date read, filled as terms are read. Real use means anyone outside the owner's organisation is given access, a page showing source records is published, or the product is used commercially. Nothing on that list holds back version 1. Existing going-live rules stay and point to the list. Its first entries are the investment projects page, for which the agency's written permission and reading the data gatherer's terms are needed before outside access or publication of a page showing these records, and the sources that decisions 0017, 0019 and 0023 admitted without stated terms: the agency's pages, relative busyness, census map layers and national GIS layers, each with what its publisher states.

5. The repository is public even though the product is local. No record, name or value of a source not under an open licence appears in the repository, a test, a fixture, a committed screenshot, a brief or a document. Fetched data stays in the uncommitted cache. Tests use stand-ins of the same shape with invented values. PUB-12's never-committed rule, DAT-85, DAT-142 and the registry's `commit_allowed` remain unchanged.

6. Every figure shows its source, its date and the publisher's own caveat. An estimate is labelled as an estimate.

7. An investment project (`fdi_projects`) is shown in full inside the product. Every field may appear on its card, in lists and on the map: the investing company and parent, origin country and city, sector and sub-sector, business function, project type, date, city, free zone, address, map point, capital and jobs figures and short description. No field is dropped at loading. Each card, list and map legend states the source in collapsed credits: the agency as publisher, the data gatherer as the page names it, the date read and a dashboard link. The page's own caveat appears with it: the data "includes estimates of publicly announced projects" and "does not capture all investment projects". Capital and jobs are always labelled as announced estimates. They are never added to measured figures, and are never shown beside them without that label. A project accepts Public facts only, is never joined to a register company's attached records, and has no named query filtering by company name (DAT-142; AGENTS.md rule 8). Document 04, PUB-12 and the source's rows, record the footer notice read on 2026-11-14 from the fetch of 2026-11-13: "Reproduction of these pages, whether in whole or in part, is only permissible with the prior written authorization of Investment Promotion Agency LLC. These pages are to be used for information purposes only". The source is no longer listed among publishers stating no reuse terms. Its basis of use is item 3.

8. The tender portal's public pages are read under item 2 and tenders are shown in full. Its terms are read and recorded under item 3 and, where permission is needed for real use, listed under item 4. Reading terms is no longer a condition of fetching or showing. No tender is shown only while no public source readable as a visitor is recorded; PUB-93's `NO_DATA` and caveat stay for that case.

9. The agency's pages (`investqa_pages`), relative busyness (`busy_gmaps`), census map layers, national GIS centre's layers, 2025 municipalities dataset, classification source and population grid follow items 1 and 3 like every other public source. None is an exception, validation-only or barred from release because of terms. Technical statements remain: the frame's geometry comes from the licensed boundary source, the 2020 map layers are joined by keys, and an unconfirmed file address or schema remains unconfirmed.

10. Greater Doha is five whole municipalities in version 1, the lead's assumption recorded as OI-151 and kept in the frame's review file. Wherever the name appears on a screen or card, its definition appears with it, naming the five municipalities. Until task S2-T02 merges, a pack passage refers to the five municipalities of the frame's review file without listing their names.

11. OI-150 is closed with Option A. TST-32 stands as written. DAT-60 and SYN-57 say that the simulator omits rows of the count tables `presence_hourly` and `od_hourly` under the minimum panel devices of the active parameter set, 20 under set A and 30 under set B, before conformance. Nothing else about the two sets changes.

12. Restaurant production value is not a field of the present datasets, by the lead's reading of the four datasets on 2026-11-14. It is neither derived nor shown and leaves every card, story beat, worked example, regression row and evaluation question naming it. Card C4 keeps its shares of output, computed by tested code from published figures only. A goods or services component's share is its value divided by its group's total, multiplied by the publisher's percentage of that group to output, from "percentage of intermediate goods to output" or "percentage of intermediate services to output". Compensation's share is compensation divided by employees divided by the published "productivity of employee"; operating surplus uses the same rule. "Output per employee", QAR 152,875 for 2022, is published and is no longer labelled calculated. "Production value" and "Output per establishment" leave the norms table. The lead checked all five survey years on the real files and reproduced the shares and ranges. The arithmetic test uses published figures: for 2022, 1,308,140 thousand ÷ 41,458 ÷ 152,875 = 20.6%; 1,247,422 thousand ÷ 41,458 ÷ 152,875 = 19.7%; food 29.3%, beverages 5.6% and building rent 11.6% by the component rule; goods 40.6% and services 16.5% as published. PUB-64 keeps establishments 2,086, employees 41,458, compensation 1,308,140, operating surplus 1,247,422, published average annual wage 31,579 and the two published percentages 40.6% and 16.5%. Reconciliation R1, restaurant revenue against production value, is closed by the absence of that field. Its record is the reconciliation record of task S2-T03, not yet merged.

## Evidence

- The owner's words and decisions of 2026-11-14, relayed by his advisor at 09:57, 10:02 and 10:03, and the advisor's decisions under that morning's delegation, recorded in the run's binding wording W1 to W12 (project records held by the owner).
- The lead's rulings L-204, L-206, L-207 and L-211 of that run, as recorded in the binding wording.
- The investment dashboard footer fetched on 2026-11-13 and read on 2026-11-14, as supplied in W7; no fresh fetch was made for this editorial sweep.
- The lead's reading of the four restaurant datasets on 2026-11-14 and check of all five survey years, as supplied in W12. These are reported source checks, not new calculations by this editor.

## Consequences

- Wherever a rule asks for a source's licence, including AGENTS.md rules 5, 7 and 19, REV-20 and the public-total inventory of document 06, the registry's record of what the publisher states together with the basis of use is that element. AGENTS.md, CLAUDE.md and document 06 are not changed by this record.
- Decision records 0024 (task S1-T14) and 0025 (task S2-T03) are numbered and arrive with their own pull requests.
- Earlier decision records are not rewritten. This record governs the replaced terms restrictions. Technical fetch limits, provenance labels, the sex and nationality rules, the ban on joining a project to attached company records, all privacy parameters except item 11's stated correction, and the gateway rules stay.
- The documentation index records this decision. Open-item history is kept with dated updates; OI-150 closes with Option A. Document 17 holds the one going-live permissions list.

## Amended passages

The following is the full inventory of passages considered across the six editing groups, by document and stable anchor. Inclusion records the scope of the sweep, not a claim that every passage changes. AGENTS.md and its byte-identical CLAUDE.md copy, and document 06, remain unchanged under Consequences. Technical statements and passages already agreeing with this decision remain. Inventory labels are kept below; the root README's "What it will do" is its current "What version 1 will show" section, and its opening public-data sentence is under "Honesty statement". The document 06 inventory's unverified mobility reference is PRV-58 as cited by PRV-134; no new requirement is created.

### AGENTS.md

- Rule 5 (CLAUDE.md is its byte-identical copy)
- Rule 19 (CLAUDE.md is its byte-identical copy)

### OPEN_ITEMS.md

- OI-03 — Conflicting restaurant and wage figures (OPTIONS)
- OI-04 — Census map-layer licence (DONE SO FAR)
- OI-98 — Public source of each forecast series without a table (OPTIONS)
- OI-100 — Sources that stay off under a public or commercial hosting (WHY)
- OI-100 — Sources that stay off under a public or commercial hosting (OPTIONS)
- OI-150 — The feed minimum of the conformance suite under parameter set B
- OI-04 — Census map-layer licence (OPTIONS)
- OI-100 — Sources that stay off under a public or commercial hosting (NEEDED and DONE SO FAR)

### README.md

- What it will do (bullet "The businesses.")
- Opening section (the paragraph on synthetic records, simulation and public data)
- Journeys table, row 'D4 Whom to partner with'

### TASKS.md

- S2-T01
- S2-T13
- S2-T16
- S2-T19
- S2-T20
- S2-T08
- slice S2 gate
- S3-T12
- S7-T09
- S7-T12
- S4-T08
- S4-T04
- S5-T09
- S2-T12
- S7-T10
- S7-T11
- S7-T01

### docs/01_PROJECT_BRIEF.md

- BRF-105 (section 6.6 Ten additions and the data rule)
- Section 14, risk row 'A public layer with no stated licence used as if redistributable.'
- Section 14, risk row 'A public layer with no stated licence used as if redistributable.' (busy_gmaps exception)
- Section 14, risk row 'A public layer with no stated licence used as if redistributable.' (wider use)
- Open questions and assumptions: 'OPEN (decision 0016), settled in part by decision 0023 item 10' (tenders)
- BRF-88 (section 6.3 The living map)
- BRF-64 (section 6.3 The living map)
- Section 12 Honesty position and reading guidance, row 'An announced project is an estimate.'
- BRF-06 (section 6.1)
- Section 7 The flagship journey, beat 3 'Evidence before words'
- Open items that touch this document: OI-03
- Open questions and assumptions: OPEN (decision 0016), apportioning weight
- Journey table row D4, and BRF-39
- Open items that touch this document: OI-04
- Sources: 'The investment sources of decision 0017'
- BRF-83

### docs/02_ARCHITECTURE.md

- Open questions and assumptions: 'OPEN, narrowed by decision 0023 item 10' (tenders_pub)
- ARC-136 (section 4.5)
- ARC-13 (section 3.3 The generator sandbox and the network rule)
- ARC-132 (section 4.5)
- Section 4.2 Manifest fields, row `sources`
- Section 2 Components, row 'Public fetchers'
- Section 1.3 The three planes and the data flow, step 1 `./eii build-public`
- Section 10 Deployment path
- ARC-129, and the open question on the apportioning weight that cites ARC-129
- Opening summary table, row 'Grid and release unit'

### docs/03_DATA_CONTRACTS.md

- Section 7.2 Table catalogue, row `pub_tender`
- DAT-168 (section 7.3 Columns), requirement
- DAT-168 (section 7.3 Columns), GIS layers basis
- DAT-168 (section 7.3 Columns), check column
- Open questions and assumptions: 'Settled by decision 0023 item 10' (tenders_pub)
- Section 7.3 Columns, row `source_registry` (column `licence_basis`)
- DAT-157 (section 7.3 Columns), requirement
- DAT-157 (section 7.3 Columns), check column
- Sources: 'Relative busyness (`busy_gmaps`)'
- DAT-142 (section 7.3 Columns), caveat key
- DAT-142 (section 7.3 Columns), source line
- DAT-60 (section 6.5 `mobility.v1`)
- Section 6.5 `mobility.v1`, table `presence_hourly`, column `panel_devices`
- Open questions and assumptions: master-design open items note (OI-11)
- Open questions and assumptions: master-design open items note (OI-03)
- Section 1.1 Terms, 'Base cell'
- Section 1.1 Terms
- Section 7.3 Columns, row `pub_venue_visits` (column `name_ar`)
- Open questions and assumptions: OPEN, apportioning weight for drawn shapes
- DAT-85
- DAT-158
- Section 7.3 Columns, row `grid_cell`
- DAT-51
- Section 6.5 `mobility.v1`, paragraph on the tables `presence_split_hourly` and `od_split_hourly`

### docs/04_PUBLIC_DATA_PACK.md

- PUB-82
- PUB-83
- PUB-93
- PUB-101
- PUB-55
- PUB-32
- Section 10 Regression examples, PUB-64
- Section 11 Reconciliation before display, row R1 Restaurant size
- PUB-75
- Section 11 Reconciliation before display, introduction
- Open questions and assumptions, open items paragraph (OI-03)
- Section 12 What public data cannot give, row Public tenders
- Open questions and assumptions, OPEN: the public source of tenders
- Open questions and assumptions, OPEN (decision 0022): the licence or basis of use of each register
- Open questions and assumptions, OPEN (decision 0023): the publisher, host and licence of bldg_wsf3d
- Open questions and assumptions, open items paragraph (OI-04)
- Open questions and assumptions, OPEN: whether the dashboard page holds an identifier column
- Open questions and assumptions, OPEN: the page structure of the dashboard and of the agency's pages
- Sources, FDI Projects dashboard entry
- Sources, GADM licence entry
- Open questions and assumptions, OPEN: the apportioning weight for drawn shapes
- Open questions and assumptions, assumption 15 (PUB-95 and PUB-97)
- In brief (bullet 'A source without stated reuse terms is validation-only')
- In brief (same bullet, last sentence)
- In brief (decision 0023 bullet)
- 1. Scope, term 'Investment sources'
- 2. Source registry, decision 0022 paragraph
- 2.1 Identity, fetch and licence, row census_2020_workbook
- 2.1 Identity, fetch and licence, rows census_zone_sector, census_zone_occ, census_zone_hh, census_zone_lab, census_district_pop, bnd_zone_2020, bnd_district_2020
- 2.1 Identity, fetch and licence, row ref_traffic_index
- 2.1 Identity, fetch and licence, row fdi_projects
- 2.1 Identity, fetch and licence, row busy_gmaps
- 2.1 Identity, fetch and licence, rows biz_register and fc_register
- 2.1 Identity, fetch and licence, rows gis_land_price to gis_imagery_history
- 2.1 Identity, fetch and licence, row bldg_wsf3d
- 2.1 Identity, fetch and licence, row tenders_pub
- 2.2 Coverage, use and traps, row sec_hr_ind, sec_hr_goods, sec_hr_serv, sec_hr_size
- 2.2 Coverage, use and traps, row census_2020_workbook
- 2.2 Coverage, use and traps, row census_zone_*, census_district_pop
- 2.2 Coverage, use and traps, row bnd_zone_2020, bnd_district_2020
- 2.2 Coverage, use and traps, row fdi_projects
- 2.2 Coverage, use and traps, row busy_gmaps
- 2.2 Coverage, use and traps, rows gis_land_price to gis_imagery_history
- 2.2 Coverage, use and traps, paragraph 'Sources mentioned in research but not in v1'
- PUB-09
- PUB-12
- PUB-12 (switch-off sentence)
- PUB-12 (GIS centre and tender sentences)
- PUB-12 (last sentence)
- PUB-13
- PUB-13 (boundary layers, UN terms and closing sentence)
- PUB-97
- PUB-105
- PUB-106
- PUB-108
- 3.1 Registry and sidecar record (licence_basis key)
- 3.1 Registry and sidecar record (decision_record key)
- PUB-87
- 4. Licences and attribution, table row fdi_projects
- 4. Licences and attribution, table row census map layers
- 4. Licences and attribution, table row busy_gmaps
- 4. Licences and attribution, table row gis_* layers
- 4. Licences and attribution, table row bldg_wsf3d
- 4. Licences and attribution, table row tenders_pub
- 4. Licences and attribution, table row 'none stated' (2020 boundary layers, archived census workbook)
- 4. Licences and attribution, table row cls_isic4
- PUB-22
- 5. The frame, level table row Zone, and PUB-24
- 2.2 Coverage, use and traps, rows `bnd_hdx` and `bnd_geob`
- PUB-54
- PUB-14
- PUB-105 (sentence on sign-in)
- PUB-105 (sentences on the fields kept)
- 2. Source registry, decision 0022 paragraph (sentence on how the register files are collected)
- PUB-101 (sentence on the page reader)
- PUB-86
- 3.1 Registry and sidecar record (key `terms_sha256`)
- 3.2 Investment sources and page parsers (opening paragraph)
- 4. Licences and attribution, table row `investqa_pages` (and 2.1 row `investqa_pages`, 'as `fdi_projects`')
- 2.2 Coverage, use and traps, row `weather_openmeteo`
- PUB-71 (section 10 Regression examples)
- 2.2 Coverage, use and traps, row `fdi_projects` (first cell)
- In brief (bullet on decision 0017)
- Table of forecast series (PUB-103), row 'Announced investment by sector'
- 5. The frame, level table row 'Grid cell'

### docs/05_SYNTHETIC_WORLD_AND_SIMULATION.md

- SYN-57
- 12.6 What the transport surveys do not give us
- 18. Not modelled, and dropped ideas (row: A transport-model fit benchmark on the scorecard)
- 18. Not modelled, and dropped ideas (row: Mode choice beyond one assumed public-transport share)
- Open questions and assumptions, Q1
- manifest entry mob.trip_rate.office_worker
- manifest entries sched.school_day_start and sched.school_day_end; 12.5 schedule table row School day
- Sources [S41]
- SYN-10 (zone-count paragraph that follows it)
- Sources [S3] and [S6]
- Calibration manifest entry `mob.hourly_shape_by_category`
- Calibration manifest entry `pop.sector_by_zone`
- 16. Validation scorecard, 'Plausibility comparison (not a hold-out)'
- SYN-55
- SYN-10
- SYN-89

### docs/06_PRIVACY_AND_DISCLOSURE_CONTROL.md

- Open questions and assumptions (open-items paragraph, OI-04)
- PRV-115
- Terms, 'Base cell'; worked example with roots R1 and R2
- Mobility release requirement cited by PRV-134 as PRV-58 (its ID was not verified); parameter table rows 'Mobility feed' and `min_panel_devices`

### docs/07_ECONOMIC_METHODS.md

- C8 Coverage share and the reliability mark (Inputs)
- C8 Coverage share and the reliability mark (Provenance and status)
- C8 Coverage share and the reliability mark (Limits and wording)
- MTH-39
- C12 (Research note, validation test, outside every release)
- C17 Similar areas and three area types (Research note)
- Open questions and assumptions, item 6
- Open questions and assumptions, OI-04 item
- C37 Relative busyness of named venues (Inputs)
- Sources (decision 0019 sources: Google Maps popular times)
- Sources (Investment sources)
- Sources (Other public sources: Statistics authority Census 2020 zone and district layers)
- C4 Sector unit economics (Public norms table, row Production value)
- C4 Sector unit economics (Public norms table, rows Output per establishment and Output per employee)
- C4 Sector unit economics (Public norms table, share-of-output rows)
- C4 Sector unit economics (Worked example, tolerance and norm arithmetic)
- MTH-26
- C4 Sector unit economics (Limits and wording)
- Open questions and assumptions, OI-03 item
- C35 Revenue range of the user's outlet (Inputs)
- C35 Revenue range of the user's outlet (Formula)
- C35 Revenue range of the user's outlet (Limits and wording, Allowed)
- MTH-108
- C28 Announced investment projects (Purpose)
- C28 Announced investment projects (Provenance and status)
- C28 Announced investment projects (Limits and wording, Allowed)
- MTH-95
- C28 Announced investment projects (Formula); MTH-95
- C6 co-location (Formula)
- C6 co-location (Limits and wording, Allowed)
- C7 Shared reach between two doors (Inputs)
- Sources: Open-Meteo historical weather
- C8 Coverage share and the reliability mark (Validation-file arithmetic and its table)
- C30 (Provenance and status)
- C6 Typical neighbours (Illustrative note)
- C4 Sector unit economics (Purpose)
- C4 Sector unit economics (Public norms table, rows Compensation and Operating surplus)
- C4 Sector unit economics (Formula)
- C4 Sector unit economics (Target-surplus regression)
- C4 Sector unit economics (Limits and wording, Allowed)
- C33 Site demand and revenue estimate (Inputs)

### docs/08_BACKEND.md

- 6.2 Tool contracts, `investment_context` Inputs row (PUB-108)
- Open questions and assumptions, item "Settled (decision 0023 item 10, PUB-108)"
- Open questions and assumptions, item "Settled (BE-57; decision 0023)"
- BE-114
- 15. Tests each module ships with, journey tools row (BE-114)
- 6.2 Tool contracts, `sector_facts` Outputs row (MTH-26)
- BE-55, and the open question on the apportioning weight that cites BE-117
- 6.2 Tool contracts, `area_evidence` Outputs row (block `coverage`); Open items paragraph, OI-04
- 6.2 Tool contracts, `investment_context` Outputs row
- Module table, row `grid`; section 15 tests, row `eii_core.shapes` (BE-117)
- 6.2 Tool contracts, Outputs row of the site estimate tool (the row that cites BE-123)

### docs/09_AI_ASSISTANT.md

- Open questions and assumptions, item "OPEN: the public source of tenders is confirmed at slice S2" (PUB-108)
- 3. Playbooks, `partner_finder` row
- AI-110
- 5.1 Claim and component families added for version 1, FDI projects row
- 3. Playbooks, `rank_areas` row
- AI-117 (and section 5.1, row 'Real businesses and tenders')
- AI-53
- AI-88
- 3. Playbooks, row `market_entry` (and In brief, bullet on new families)
- AI-21

### docs/10_FRONTEND.md

- 4.5 Rooms, Trust centre row (tender source, PUB-108)
- 4.5 Rooms, Trust centre row (basis of use, owner_decision, PUB-105)
- Open questions and assumptions, item "OPEN: the public source of tenders is named by decision 0023 item 10"
- FE-96
- 14. Asset pipeline, Zone geometry row (PUB-13)
- FE-116
- 4.3 Evidence card types in v1, `fdi_projects` row
- FE-139
- 14. Asset pipeline, Sprites row
- 4.3 Evidence card types in v1, row `tenders`
- 4.4 Stage controls and small visual components, row 'Coverage bar'; Open items, OI-04
- 13. Testing, row 'Visual'
- 6. Map layers, row 'Announced investment projects'
- 13. Testing, numbered item 11
- 4.8 Journey views, row 'FDI list'
- 6. Map layers, 'Extruded buildings' (and Sources, Overpass counts)
- 4.4 Stage controls and small visual components, row 'Break-even calculator'; FE-28; 4.3 row `unit_economics`

### docs/11_DESIGN_DIRECTION.md

- DES-178
- DES-82
- 10.13 Fixed sentences of the version 1 families, `fdi_estimates` row
- Sources, FDI projects dashboard row
- 16. Design audit gates, "Firms, splits and sources" row
- 10.2 The four hero cards of the flagship, slot 4 "What a restaurant costs to run"
- Scene 0 — The living map, real public evidence first, On screen row
- Scene 1 — The Qatari day, hour by hour, On screen and Words on screen rows
- Open items table, row OI-04
- DES-161 (and DES-162)
- DES-192
- Scene 7 — The international entrant's headquarters evidence pack (On screen, Words on screen); Scene 8 — The four cases
- DES-60
- DES-110; Scene 5 — Costs and suppliers (On screen)

### docs/12_TESTING_AND_QUALITY.md

- TST-196
- TST-237
- TST-210
- TST-219
- 3.5 Regression examples from the verified public figures (Restaurants (activity 561), 2022 row)
- TST-260
- Open questions and assumptions (apportioning weight)
- TST-216
- Open items touching this document: OI-04
- TST-91
- 3.5 Regression examples, paragraph 'For C4 under MTH-25 and MTH-26'; TST-53

### docs/13_DEPLOYMENT_AND_OPERATIONS.md

- Commands table, `./eii build-public` row
- OPS-66
- OPS-72
- OPS-69

### docs/14_IMPLEMENTATION_PLAN.md

- 10. slice S2, Scope
- 10. slice S2, Scope (decision 0019 paragraph)
- 10. slice S2, Scope (decision 0023 paragraph)
- S2-T01
- S2-T19
- S2-T08
- 10. slice S2, Gate
- PLN-25
- S2-T13
- 21. Risk register (Public licences or OI-03 reconciliations block figures)
- 21. Risk register (An investment source changes its page or its terms)
- 21. Risk register (A source of decision 0019 changes its page, access or terms)
- 23. Open items during a run
- Open questions and assumptions (OPEN, public source of tenders)
- Open questions and assumptions (OPEN, apportioning weight)
- 11. slice S3, Scope
- Open items paragraph, OI-04
- 10. slice S2, Scope (decision 0017 paragraph); Visible outcome

### docs/15_REVIEWER_CHECKLIST.md

- REV-25
- REV-29
- REV-20

### docs/16_DEMO_RUNBOOK.md

- Scene 3 — The flagship: one location, drawn (Point at row)
- Scene 5 — Costs and suppliers (Appears row)
- Section 6, "Prepared answers to hard questions", row "Where do popular times, live traffic, night-time lights, places and weather come from, and may you use them?"
- Section 6, row "Where do the investment projects and the agency's information come from, and may you use them?"
- Section 6, row "Can a company look up a competitor or a person?"
- D23 (section 3.1, day-before checklist)
- RUN-16
- Section 7, Tone
- Story scene whose Appears row begins 'A company journey for the first persona' (Appears, Point at), the scene of Case C1, and the list of things never said
- Sources: FDI projects dashboard

### docs/17_DEPLOYMENT_HARDENING.md

- Section 6 "Public and investment sources if hosted publicly", opening paragraph
- DHA-86
- DHA-52
- DHA-50
- DHA-51
- In brief (the bullet listing the six areas)
- DHA-87
- DHA-70
- DHA-53
- DHA-85
- Open questions and assumptions: 'OPEN: which sources stay on' and 'OPEN (decision 0022): whether the two public registers stay on'

### docs/GLOSSARY.md

- FDI project
- Public
- Source registry
- Source chain (sanad)
- Base cell
- Open questions and assumptions: OPEN, apportioning weight

### docs/README.md

- In brief (bullet on decision records)


## What would change this decision

A further owner decision changes the local scope or these rules. Real use triggers the permissions and licences on document 17's list; it does not retroactively restrict version 1. A source that stops being visitor-readable or fails its technical checks stays absent under items 1 and 2.

## Open questions and assumptions

- Greater Doha's five whole municipalities remain the lead's assumption, OI-151, in the frame's review file. Their names are not copied into the pack before task S2-T02 merges.
- Source files, addresses and schemas still need technical confirmation where the pack says so. Terms are recorded as read, and document 17's list is filled as they are read.
- The reconciliation record of task S2-T03 has not merged. Item 12 does not claim that the wage-table reconciliation is closed.

## Sources

- The owner's and advisor's decisions and the lead's rulings of 2026-11-14, recorded in the run's binding wording W1 to W12 and described under Evidence (project records held by the owner).
- The investment dashboard, https://fdiprojects.invest.qa/, footer and caveat as supplied in W7, fetched on 2026-11-13 and read on 2026-11-14; its notice is quoted in item 7.
- [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md), PUB-12, PUB-13, PUB-64, PUB-93 and PUB-108; [07_ECONOMIC_METHODS.md](../07_ECONOMIC_METHODS.md), method card C4; [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md), DAT-60; [05_SYNTHETIC_WORLD_AND_SIMULATION.md](../05_SYNTHETIC_WORLD_AND_SIMULATION.md), SYN-57; [12_TESTING_AND_QUALITY.md](../12_TESTING_AND_QUALITY.md), TST-32.
- Decisions [0016](0016-version-1-covers-the-whole-initiative.md), [0017](0017-public-data-additions-and-public-splits.md), [0019](0019-forecasts-estimates-scenarios-and-self-serve-sources.md) and [0023](0023-ten-additions-and-the-data-rule.md), as historical records amended here.
