# 07 — Economic Methods

| | |
|---|---|
| Status | Draft v0.3, amended by decisions 0016, 0017 and 0019 on 2026-11-12, and by decisions 0021, 0022 and 0023 on 2026-11-13 |
| Date | 2026-11-13 |
| Owner | albarami |
| Purpose | Define every economic, location, footfall, traffic and labour-market method the product computes: inputs, formula, worked example (a regression test), provenance, honesty limits, allowed wording and measured cost. |
| Read first | [01_PROJECT_BRIEF.md](01_PROJECT_BRIEF.md), [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md), [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md), [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md), [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), [decision 0017](decisions/0017-public-data-additions-and-public-splits.md), [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md), [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md), [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) |

## In brief

- Forty-one version 1 (v1) method cards and a list of methods that must not be built. [Decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) moved the three later cards (C11 ranking, C12 reachable access, C13 imports against local production) into v1. Decisions 0016 and [0017](decisions/0017-public-data-additions-and-public-splits.md) added C16 to C29 and amended C3, C4, C7, C14 and C15. [Decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) added C30 to C38 (forecasts, base rates, people present by pay band, the site estimate, two scenarios and three Public layers) and amended C4, C11, C15, C18, C19, C22, C23, C25 and C26. [Decision 0021](decisions/0021-one-speed-for-a-link-and-an-hour.md) fixed the version-1 values of C25 and added its speed floor, the rule of one speed for a link and an hour, the itemised route and the measured limits of the routing engine. [Decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) added C39 (talent available near this site), C40 (best three sites and "how sure") and C41 (property price measures, with how near a planned station is). It amended C11 and C16 (zoning and plots, item 3), C20, C22, C25, C30, C31 and C33 (its data rule, item 12; C30 also item 8), C34 ("how sure", item 5) and C38 (the age profile of the site answer, item 11). No later card remains.
- Every method is a small, pure, tested function. Nothing here needs a GPU, a graph server or a spatial database to compute; every method the research timed ran in about three seconds or less on a CPU. The traffic assignment, the national travel-time matrix, the backtests of C30 and the draws of C33 are not yet timed.
- A pinned worked example is a regression test that must pass in slice S7. An example whose inputs are not yet pinned is an illustrative note, and the slice S7 gate fails while it stays unpinned. A card added by decisions 0016, 0017, 0019 and 0023 has a fixture test now and is pinned at the gate of the slice that builds it (MTH-60).
- Public methods produce real findings about Qatar. Methods run on Synthetic or Simulated layers show a format and a protection, never a fact about a place.
- Rankings, fits and suggestions are tested code over criteria and weights the user can see and change, and every rank has a rank-stability sentence. None is a verdict, a probability, a confidence claim, advice to act or a revenue, demand or success forecast.
- A forecast, an estimate or a base rate appears only as the output of tested code: a forecast of a listed Public series, or of a released monthly series of the window, with its interval from the backtest, its measured backtest error, its method and its source (C30); a base rate with its counts and period (C31); the site estimate with its low, middle and high cases, its main drivers and, while an input is Simulated or Synthetic, the label "estimate on simulated inputs" (C33). A scenario (C34, C35) is the user's, with every assumption visible and editable, and is never called a forecast. Nothing forecasts the success of a venture, nothing is estimated for a named real business, and nothing is a verdict, a probability, a confidence claim or advice to act ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) items 1 to 10).
- Figures from the protected record types snap to whole release units, with the snap sentence. Public points and Simulated layers are computed for the exact shape the user draws. A Public statistic or a released Simulated count reaches that shape only through apportioning (C18), and the result is labelled Inferred. Whole cells of the published population grid by age and sex are summed over an area, which is not apportioning (C38).
- Presence is an estimated count of people with a range, hour by hour (C15, C27). Its seasonal shape is calibrated and checked against published museum visitor counts, and its hour-of-day shape by place category is calibrated to the pooled relative busyness of named venues; no venue's level and no single venue's shape enters it (C26, C37). Traffic is a simple Simulated road assignment (C25) with the default provider; the optional live provider shows flow tiles and traffic-aware drive-time areas, and no figure is read from a tile (C25; ARC-135).
- Several attractive methods would only return the generator's own assumptions on synthetic data. They are listed under "What would be theatre" and are not built.
- Qatar has eight municipalities and about 75 usable census zones. That rules out area typologies beyond three types, complexity below national level and hot-spot statistics.

## 1. Common rules

- **Licence-activity count**: one activity on one commercial licence, as counted in the public licence tables. It is not a firm and not a job.
- **Worked example**: a calculation with real published figures, written here so that a test can reproduce it.
- **Calculated**: a value obtained by fixed arithmetic from published figures, not published itself.
- **Fixture**: invented inputs of an arithmetic test, labelled as such. A fixture is never a figure about a place or a source.
- **Apportioning**: moving a count published on an official geography, or a released Simulated count, onto a drawn shape by a stated weight (C18). The result is an estimate, labelled Inferred.
- **Projection**: a straight-line continuation of a published or released series over a stated window (C21). It is not a forecast.
- **Forecast**: the value of a later period of a series on the closed list of C30, from the candidate model that the series' own backtest chose, shown with its interval from the backtest and its measured backtest error (C30). A projection, a ranking, a fit, an estimate and a scenario are not forecasts.
- **Base rate**: a share of past licences of one activity and one area of the source, with its numerator, denominator and period (C31). It describes past licences, not the user's own venture.
- **Scenario**: a figure computed from assumptions the user sets and can see and change (C4, C34, C35). It is the user's, and it is never called a forecast.

| ID | Requirement |
|---|---|
| MTH-01 | Every displayed number is produced by deterministic tested code in `eii_core.calc`, the release build, or a fixed application-schema read function listed by the data contracts and covered by tests. Nothing else computes, rounds or compares a number, and no model ever does. Each method in this document is a deterministic function in `eii_core.calc` (package `core/`). It does not read a file, the network or a database; callers pass the rows. The custodian build and the product plane call these functions. The browser never computes a displayed number; it formats values it receives. A comparison (difference, ratio, rank or direction) is itself a calculation fact. ASSUMPTION: `core/` is the only package both planes may import, so this is the one place a method can be shared. |
| MTH-02 | Build-time methods run in the custodian plane and write facts into the release: location quotient, churn, decomposition, co-location, coverage, zone momentum, property-sale median, the public series of C13 and C21 to C24, the project counts of C28, the area types of C17 (release table `zone_type`), the access scores of C12 for fixed supply layers, cut-offs and hours (release table `access_score`, with the travel times they use in the manifest artefact `travel_time_matrix`, and, for the population-grid layer at free flow, the Public release table `access_score_grid`), the fixed-composition wage index of C19 (`month_change.stayer_wage_index`, PRV-55), the national wage trends by sector of C19 with their split (MTH-97), the traffic assignment of C25 (over released flows only, after the privacy engine), the seasonal calibration measure of C26 with its hourly shape by place category, and the base rates of C31. The public-data build calls the same package for the night-time radiance by frame cell and month of C36 (`pub_night_lights`) and for the price aggregates of C41 from the deals that C14 keeps (by district, use and quarter: the median price per square foot with its deal count and deal value, the same median over the deals of land without a building with its deal count, and the median deal price of each unit type with its deal count), released as aggregates only (PUB-14) in `pub_property_quarter` ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) section 7.2), whose columns so far hold only the median price per square foot with its deal count and deal value (Open questions), and for the empty test of each land parcel of the national GIS centre, while the parcel number is still a join key inside the build (C16, MTH-118). Request-time methods run in the product plane over release tables only, by calling `eii_core.calc`: the break-even calculator with its incentive inputs, shared reach, band lookup, area presence counts and crowd density, rankings and fits with their stability sentences (C11, C16), similar-area search (C17), area access summaries (C12), apportioning (C18), area income indicators and their monthly changes (C19, C20), changes of Public series (C20), projections of released synthetic series (C21), the forecasts of card C30, of a Public series or of a released monthly series, each computed at request time from release tables, as a projection is (DAT-144), and never written to the release, openings and closures of register companies over an area (C22), drive times and drive-time areas by hour (C25, with the default provider), sums over a sample file (C29), people present by pay band (C32), the site estimate (C33), the two scenarios (C34, C35), radiance over an area (C36), the whole-cell population sums by age and sex (C38), the talent pool and the competing demand of a site, side by side, and the talent ratio of those two figures, which the calculation layer also computes (C39, MTH-122), the best three sites with their runs (C40), the comparisons of the property price measures (C41: guide against deal and affordability over the released price aggregates, and credit against growth), the distance to a planned station (C41, MTH-121), and the plot label and the zoning measure (C16, MTH-118 and MTH-119). A traffic-aware drive-time area of the live provider is fetched by the API process, not computed by a method (C25; ARC-135). The only application-schema arithmetic is in the fixed read functions listed by the data contracts and covered by their regression tests. |
| MTH-03 | A worked example whose inputs, settings and expected result are all written in this document has two tests: an arithmetic test that feeds those inputs into the function and asserts the stated result within the stated tolerance, and a data test that recomputes the same figure from the pinned public file built in slice S2. Regression values that the pack cannot pin today (for example the riyal medians of the property-price method card and the other inputs listed here) are produced by `./eii build-public` at slice S2, checked against the source by the reviewer, and written into the method cards by a slice S2 task; slice S7 fails while any remain unpinned. No value is invented. Four examples are illustrative notes, not passing regression examples, until they are pinned: the Wilson count's period (section 3), the C5 HHI and trend, the C6 seed and full settings, and the C7 coordinates, modes, cut-offs, speed regime, district weights and expected shares. The C14 median prices in riyals are in the same state (MTH-51). |
| MTH-04 | When a data test does not reproduce a worked example, the builder must record the difference in `OPEN_ITEMS.md` and stop. Parameters must not be tuned until the number matches. |
| MTH-05 | A value computed by fixed arithmetic from Public release tables carries provenance `public`, evidence status `observed` and the caveat key `calculated`. An interpretation of such a value (for example "these months look administrative") carries evidence status `inferred`. |
| MTH-06 | A figure computed from the user's own inputs carries evidence status `inferred` and the "your inputs" tag, takes the least-real class of its release inputs as provenance, and is never written to the release or to the ledger as a fact. |
| MTH-07 | A composite of release inputs takes the least-real class of its inputs, computed in code by the shared provenance helper; the method never sets the class by hand. |
| MTH-08 | Every fact a method produces carries a complete source chain: the fact, its release table, the method and version, then the source (publisher, dataset, licence, retrieval date and file hash). The fact names its source table in `lineage_ref`. Where two public tables could give the same quantity, the fact names the one used. A fact without a complete chain is not emitted: the release build fails on it, and the Fact chip refuses it. The evidence drawer is labelled "Source chain". The Arabic label proposed, pending the owner's review, is "السند". |
| MTH-09 | Methods return a value or a status; they never return zero for an unknown. A missing input yields `NO_DATA` with a reason key, and the card shows the reason. |
| MTH-10 | Allowed wording is implemented only as application-owned English and Arabic claim templates. Each brief item carries a `claim_key` and typed fact slots. `layout[]` is an ordered list of component instances. The model may select and order catalogue claims, components and fact ids only; no model-written prose reaches the screen. Component properties are fact ids, release-unit ids or enumerations. One invalid item rejects the brief; one repair attempt; then the template writer uses the playbook's default selection. An `area` subject accepts Public, Synthetic, Simulated and Inferred facts. A claim whose subject is `place_public` or `fdi_project` may have Public slots only; a `register_company` subject, a real company of the public business register or of the financial centre's public register, accepts its Public card facts, the Synthetic employee count of its attached records and, in a list, the rank and fit facts of C16, and never a Simulated fact, an estimate, share or score, or a wage or other labour or residence fact of the company ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) DAT-145); named synthetic firms and their subject `synthetic_firm` are retired; no other subject accepts a Synthetic or Simulated slot ([AGENTS.md](../AGENTS.md) rule 8; [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 20; [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 9; [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)). A build-time scan of the templates rejects numerals, number words, names of real places inside `area` claims, and go or no-go wording, including each card's "never say" phrases. |
| MTH-11 | Caveat keys named in this document (in backticks, for example `calculated`) must exist in the release caveat catalogue with English and Arabic text. If [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) names the catalogue differently, that document wins and the meaning here stands. |
| MTH-54 | Before an answer is shown, code runs the accounting gate's five checks: sources, assumptions, nothing invented, scope, and limits stated. A method fact supplies what those checks read: the source chain (MTH-08), the evidence status (`observed`, `inferred` or `still_to_test`), the "your inputs" tag where the figure uses the user's inputs (MTH-06), and the caveat keys. The method does not set an inferred item's strength; the claim catalogue does. If a check fails, the template writer's default answer is shown. The receipt labels the result "Checked before display". The Arabic label is pending the owner's review. |
| MTH-55 | Each derived statistic normally names exactly one home family in its fact lineage, as section 6.2 of [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) defines (PRV-30). There are three exceptions and no other. The first is the closed list of ratio statistics: mean wage and the coverage, irregular and deployed-elsewhere shares. A ratio statistic takes its numerator and denominator from columns of the same stored rows — one table, one partition, one unit set and one measure where the table has measures — even where those columns belong to two additive families; its fact lineage names both families. Mean wage divides `wage_bill` by `earner_count` on the same stored `ALL` rows of `worker_pay` on `wp_all_money` or `resident_pay` on `rp_all_money`. The three side-count shares divide the applicable side-count column by `earner_count` on the same stored `ALL` rows of `resident_pay` on `rp_housing_count` or `worker_pay` on `wp_site_count`. Earner count on a worker card uses `worker_pay` and `wp_all_count` with no breakdown; earner count on a resident card uses `resident_pay` and `rp_all_count` with no breakdown. Wage bill uses that table's money partition. Band shares, the median band and quartile bands use that table's band partition (`wp_all_quartile` or `rp_all_quartile`), and the count beside those shares is that same family's total. A national card follows these rules, with its earner count on `rp_all_count` or `wp_all_count`. A municipality card differs, because the count partitions `rp_all_count` and `wp_all_count` have no municipality unit ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-16): mean wage, wage bill and the one earner count displayed come from the stored `ALL` rows of that municipality's unit of `rp_all_money` or `wp_all_money`; the median band, band shares and quartile bands, and the denominator of those shares, come from its unit of `rp_all_quartile` or `wp_all_quartile`; the band shares carry no count of their own, and that denominator is never displayed as a second earner count (MTH-76). A housing count and the housing shares beside it use `resident_pay` and `rp_housing_count` with the housing-class breakdown. An occupation count and the occupation shares beside it use `occupation_pay` and `op_res_quartile` with the occupation-group breakdown. C7 earners mode uses one selected count family, `resident_pay` on `rp_all_count` or `worker_pay` on `wp_all_count`, for both the weight and the share. C15 and C27 use the released presence counts of one segment from one partition (PRV-58); C27's all-people sum adds the three segments of one complete group and never reads a stored total. No method returns two routes to one population as two numbers. The second is the people present by pay band of C32, and the site estimate of C33 that reads it, under PRV-126 of [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) (MTH-104). The talent pool and the competing demand of C39 are two figures, each of one home family on the snapped units of its own partition, shown side by side. The talent ratio of MTH-122 is the one further exception: the quotient of those two released figures for the same occupation group and cut-off, and its fact lineage names both families (PRV-127). |
| MTH-56 | A method that reads a figure of the protected record types (business register, employment, residence, wages) takes a snapped area of whole release units from `make_area`, shown with the snap sentence of DES-101 in [11_DESIGN_DIRECTION.md](11_DESIGN_DIRECTION.md), before any figure is read (BE-54), or reads the released rows of one whole municipality or national unit, labelled with that unit's own released area (C19; [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-16, PRV-55). Public point layers and Simulated layers are computed for the exact shape the user drew, set by radius, or chose by walk or drive time and hour. A statistic published on an official geography is shown on that geography; a method puts it, or a released Simulated count of a release unit, on a drawn shape only through C18, and the result is `inferred`. No Public figure is apportioned to grid cells or release units or blended into a protected figure (PUB-29) ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) items 6 and 17). |
| MTH-57 | A ranking, fit or suggestion (C11, C16, C17) is the output of tested code over criteria, directions and weights the user can see and change, and every rank stands with its rank-stability sentence (MTH-45). It is never a verdict, a probability, a confidence claim, advice to act, or a revenue, demand or success forecast, and its weights are labelled a judgement ([AGENTS.md](../AGENTS.md) rule 25). Its criteria may include the forecasts of C30, the base rates of C31 and the site estimate of C33 under MTH-65; a rank that uses them is still not a forecast. A real business from public listings or an FDI project is never scored, fitted, estimated or given a share; a list of them is ordered by distance only, a Public figure (PUB-92). A register company is never scored, estimated or given a share; a list of register companies is ordered only by C16 over criteria the user can see and change, with the rank-stability sentence, and never by, or with a tie broken by, a company's wages or another unreleased labour or residence value (MTH-71; [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)). The scenario of C34 shows the share of the user's outlet and the competitors' share split by competitor category and by distance band only, never a share of one named business. No Public split by sex or nationality is a criterion (PUB-90). |
| MTH-58 | An estimate or another derived figure, that is an apportioned figure (C18), a projection (C21), a forecast (C30), a figure of people present by pay band (C32) or the site estimate (C33), carries evidence status `inferred`, and so does every value computed from an `inferred` input or from the user's inputs (MTH-06), the scenario results of C34 and C35 included. A base rate is a Public fact with evidence status Observed, the status of the churn rate of card C2 (fixed arithmetic over published counts, caveat `calculated`), and it carries the caveat key `base_rate_not_your_chance`. Each companion fact of a base rate has that same status. The whole-cell sums of C38 are Observed. A value computed by fixed arithmetic from release tables, Synthetic and Simulated ones included, is `observed`. That means read from the release, not real: its class still marks it (DAT-91). |
| MTH-59 | Release tables, caveat keys, fact units and subjects added by decisions 0016, 0017, 0019 and 0023 are named here as [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) and [09_AI_ASSISTANT.md](09_AI_ASSISTANT.md) name them, or described where no name exists yet. [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) is the authority: where it names one differently, that document wins and the meaning here stands, as for caveat keys (MTH-11). |
| MTH-60 | Each card added by decisions 0016, 0017, 0019 and 0023 has an arithmetic test on the fixture written in the card now, and a data test pinned from the release by the slice that builds the card. The gate of that slice ([14_IMPLEMENTATION_PLAN.md](14_IMPLEMENTATION_PLAN.md)) fails while a regression value the card lists as unpinned stays unpinned. MTH-03 and MTH-04 apply unchanged, and the card's requirement IDs join the test matrix of TST-197. |

Each card states its compute cost and which research review measured it. All research timings were taken on 2026-11-11 on the build machine with the CPU only; they show that compute is not the constraint and are not promises for the demo. Where no time was recorded, the card says so. A card added on 2026-11-12 says "not yet timed" where no research timing exists.

## 2. Card overview

| Card | Capability | Tool | Output provenance |
|---|---|---|---|
| C1 Licence density and location quotient | capability M3 | `sector_facts` | Public |
| C2 Licence churn with bulk months flagged | capability S8 | `sector_facts` | Public |
| C3 Pay-versus-mix decomposition | capability S3 | `sector_facts` | Public |
| C4 Sector unit economics and break-even | capability M6 | `sector_facts` | Public norms; result is the user's scenario |
| C5 Customs supplier lens | capability S5 | `supplier_lens` | Public |
| C6 Typical neighbours | capability S9 | `scan_places` | Public |
| C7 Shared reach between two doors | capability S6 | `compare_areas` | Public, Synthetic or Simulated by mode |
| C8 Coverage share and reliability mark | capability M5 | `area_evidence` (`coverage`) | Public (share); mark applies to any fact |
| C9 Zone momentum | capability M3 | `sector_facts` | Public |
| C10 Staffing bands beside public anchors | capability S2 | `pay_benchmark` | Synthetic bands beside Public anchors |
| C14 Sale price per square metre | capability M3 | `area_evidence` (`public_context`) | Public |
| C15 Area presence counts | capability M2 | `area_evidence` (`presence`) | Simulated |
| C11 Best-location ranking and rank stability | journey D2 | `area_ranking` | least-real class of the criteria; Public in public-only mode |
| C12 Reachable-access score | journey D2 | `reachable_access` | least-real class of demand, supply and travel times |
| C13 Imports against local production | journey D7; case C1 | `supplier_lens` | Public |
| C16 Reverse fit and fit lists | journeys D2, D3 and D4 | `activity_fit`, `register_companies` | least-real class of the criteria; for lists of register companies, the least-real class of the criteria and filters used |
| C17 Similar areas and three area types | journey D2 | `similar_areas` | Public |
| C18 Apportioning to a drawn shape | every journey with a drawn shape | `area_evidence` | the input's class; Inferred |
| C19 Six income indicators and pay versus mix by month | journeys D1, D2 and D5 | `area_evidence`, `pay_benchmark`, `what_changed`, `labour_facts` | Synthetic; Public for indicator 6 by sector |
| C20 What changed between adjacent months | journeys D5 and D6; service S2 | `what_changed` | the compared facts' class |
| C21 Labour-market projections | journey D5 | `labour_facts` | the series' class; Inferred |
| C22 Openings and closures over time | journey D6 | `openings_closures` | Public (licences and register companies) |
| C23 Construction pipeline | journey D6; the reverse view | `area_evidence` (`public_context`) | Public |
| C24 Employer scale and wage bill by activity | journeys D1 and D3; service S1; cases C1 and C2 | `sector_facts` | Public |
| C25 Traffic assignment and drive times by hour | journeys D2 and D7 | `make_area`, `travel_times`, `area_evidence` (`traffic`), `stage` | Simulated; Public at free flow; a live provider tile is a picture layer and carries no figure |
| C26 Seasonal calibration measure | footfall calibration | none: a release check shown in the Proof room | Public and Simulated shapes |
| C27 Crowd density | journey D2 | `area_evidence` (`presence`), `stage` | Simulated |
| C28 Announced investment projects | journeys D1, D4, D6 and D7 | `investment_context` | Public |
| C29 Sums over a case sample file | cases C3 and C4 | `own_records` | Synthetic, your inputs |
| C30 Forecasts of published series | decision 0019 items 2 to 6 | set by document 08 (family `series_forecast`) | the series' class (Public; Synthetic for a released monthly series); Inferred |
| C31 Entry, closure and survival base rates | decision 0019 item 7 | set by document 08 (family `base_rates`) | Public; Observed |
| C32 People present by pay band | decision 0019 items 11 and 12 | set by document 08 (family `present_by_pay_band`) | Simulated; Inferred |
| C33 Site demand and revenue estimate | decision 0019 item 8 | set by document 08 (family `site_estimate`) | least-real class of the inputs (Simulated while presence is simulated); Inferred, your inputs |
| C34 Catchment-share scenario | decision 0019 item 9 | set by document 08 (family `catchment_scenario`) | Public points and your inputs; Inferred |
| C35 Revenue range of the user's outlet | decision 0019 item 10 | set by document 08 (family `revenue_range_scenario`) | Simulated, your inputs; Inferred |
| C36 Night-time radiance by area and month | decision 0019 item 20 | set by document 08 (family `night_lights`) | Public |
| C37 Relative busyness of named venues | decision 0019 items 18 and 19 | set by document 08 (family `venue_busyness`) | Public |
| C38 Population by age and sex over an area | decision 0019 item 22; decision 0023 item 11 (the age profile of the site answer, journey D2) | set by document 08 (family `population_age_sex`) | Public |
| C39 Talent available near this site | decision 0023 item 1; journey D5 | set by document 08 | Synthetic (Simulated with times at an hour) |
| C40 Best three sites and "how sure" | decision 0023 item 5; journey D2 | set by document 08 (`branch_check` playbook) | least-real class of the inputs; Inferred, your inputs |
| C41 Property price measures | decision 0023 items 3 and 8; journeys D2 and D5 | set by document 08 | Public |

In the Capability column, "capability M" and "capability S" are version 1 capabilities from the master design's value stack. For the cards added by decisions 0016 and 0017, the column names the journeys D1 to D7, the services and the cases of [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md). For C30 to C38 it names the items of [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md), and for C39 to C41 the items of [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) with their journeys; the Tool column names the claim family until document 08 names the tool. In this document a bare C number is always a method card: the cases are written "case C1" to "case C4" and the services "service S1" to "service S3". Everywhere else in this document, "slice S0" to "slice S11" are build slices. ASSUMPTION: C6 is served by `scan_places`, because it reads public places around a pin, which is that tool's job. Tool names are those of [08_BACKEND.md](08_BACKEND.md) section 6.2 (BE-56).

## 3. Shared interval method and reliability mark

This section is used by C1, C2, C8, C10 and C31.

**Interval.** For a proportion with `k` events among `n` units, the product shows the Wilson score interval at 95% (z = 1.96) (Wilson 1927):

```
p      = k / n
centre = (p + z^2 / (2n)) / (1 + z^2 / n)
half   = z * sqrt( p(1-p)/n + z^2/(4 n^2) ) / (1 + z^2 / n)
interval = [centre - half, centre + half]
```

The interval is a descriptive binomial model-based interval. It is not a survey confidence interval, it is not computed from the publisher's sampling design, and it must not be presented as uncertainty in the synthetic world's resemblance to Qatar.

Illustrative note (not a passing regression until the period is pinned): methods research, 2026-11-11, recorded 6 restaurant-licence cancellations among 28 active restaurant licences in Al Shamal, and did not record the period. The arithmetic test does not need the period. With `k = 6`, `n = 28` and `z = 1.96`:

```
p = 6 / 28 = 0.214285714
z^2 = 1.96^2 = 3.8416
numerator = 0.214285714 + 3.8416 / 56 = 0.214285714 + 0.068600000 = 0.282885714
denominator = 1 + 3.8416 / 28 = 1.137200000
centre = 0.282885714 / 1.137200000 = 0.248756344
inner = 0.214285714 * (1 - 0.214285714) / 28 + 3.8416 / (4 * 784) = 0.007238120
half  = 1.96 * sqrt(0.007238120) / 1.137200000
      = 1.96 * 0.085077139 / 1.137200000 = 0.146633127
interval = 0.248756344 - 0.146633127 to 0.248756344 + 0.146633127
         = 0.102123 to 0.395389, which rounds to 0.102 to 0.395
```

That is p = 21.4% and a 95% interval of 10.2% to 39.5%. The slice S7 data test stays failed until the period is written here (MTH-03).

**Reliability mark.** The `reliability` value on a fact is one of `standard`, `low_count` or `not_applicable`, as [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) defines them. This document sets the cut point that maps a count `n` onto those values. The interface shows a mark for `low_count` only.

| Band key | Rule | Screen meaning |
|---|---|---|
| `standard` | n ≥ 30 | no mark on the chip; the interval stays in the Source chain |
| `low_count` | n < 30 | the only value that shows a mark; the interval is shown beside the value |
| `not_applicable` | a published total with no underlying count, or a user scenario | no mark |

| ID | Requirement |
|---|---|
| MTH-12 | `eii_core.calc.wilson(k, n)` returns the interval above; for k = 6, n = 28 it returns 0.102 to 0.395 to three decimals. |
| MTH-13 | Every fact derived from a count carries a `reliability` value set by the table above. The interface shows a mark for `low_count` only. ASSUMPTION: the cut point 30 is the same number as the Set A minimum for a money figure. A released count can still be below 30, and that count is `low_count`. A money figure that the privacy tier publishes has n at least 30 and is `standard`. Quartile publication is a privacy tier, not a second reliability value. |
| MTH-14 | No shrinkage toward a wider-area rate is applied in v1: the observed value is shown with its interval. ASSUMPTION: shrinkage changes the displayed number and needs a prior that a reviewer would have to check; an interval is simpler and shows the same uncertainty. |

## 4. Version 1 method cards

### C1 Licence density and location quotient

**Purpose.** Show how crowded an activity is in a municipality, against the national rate and against the national activity mix.

**Inputs.** `pub_licence_active` (active licence-activity counts by municipality and activity code, snapshot May 2025); `pub_population_municipality` (residents by municipality: `municipality_code`, `period`, `indicator`, `value`, `unit`, `source_id`). The May 2025 snapshot uses the 2025 residents indicator: 111,282 in Al Daayen and 3,219,982 nationally. Activity codes resolve through the activity spine in `graph_node` and `graph_edge`.

**Formula.** For activity `i` and municipality `j`, with `a` = licence-activity counts and `P` = residents:

```
density_ij = 10,000 * a_ij / P_j            national: 10,000 * a_i / P
LQ_ij      = (a_ij / a_j) / (a_i / a)       a_j = all activities in j; a = national total
LQ interval: Wilson interval of (a_ij, a_j) divided by (a_i / a)
```

The denominators `a_j` and `a` include every licence-activity, including legacy six-digit codes in the "not mappable" bucket. The national share is treated as fixed in the interval (ASSUMPTION: the national count is far larger than any local count).

**Worked example (regression).** Methods and data research, portal table of active licences, May 2025:

| Quantity | Value |
|---|---|
| National licence-activity total | 249,622 across 4,755 codes |
| Restaurants (code 5610101), Al Daayen / national | 361 / 4,782 |
| Residents, 2025, Al Daayen / national | 111,282 / 3,219,982 |
| Restaurant licences per 10,000 residents, Al Daayen / national | 32 / 15 (one decimal: 32.4 and 14.9) |
| LQ, restaurants (5610101), Al Daayen | 1.39 |
| LQ, coffee shops (5630112, 173 licences), Al Daayen | 3.05 |

Arithmetic for the densities: 361 / 111,282 × 10,000 = 32.440, which rounds to 32.4 and is shown as 32. 4,782 / 3,219,982 × 10,000 = 14.851, which rounds to 14.9 and is shown as 15.

Tolerance: densities as rounded integers exactly; LQ ± 0.01. The location quotients are the research results; the residents year is 2025, because those two resident counts reproduce 32.4 and 14.9.

**Provenance and status.** Public, `observed`, caveats `calculated`, `licence_activity_not_firm`, `snapshot_may_2025`. **Compute cost.** "Instant" for all cells (methods research; no time recorded).

**Limits and wording.** Municipality level only: eight areas, nothing inside Doha. Al Daayen is not Lusail alone. Only 1,328 of the 13,189 municipality-by-code cells hold 30 or more licences (methods research), so most cells are `low_count`.

Of the May 2025 active licence-activity count of 249,622 (master design section 9, recomputed 2026-11-11): 211,277 / 249,622 = 0.8464, which rounds to 84.6% (2,035 codes whose first four digits are an ISIC class); 11,276 / 249,622 = 0.0452, which rounds to 4.5% (1,363 other 7-digit codes); 26,844 / 249,622 = 0.1075, which rounds to 10.8% (1,336 codes of six digits); 225 / 249,622 = 0.0009, which rounds to 0.1% (169 under 13 five-digit codes and 56 under eight eight-digit codes). Among the six-digit codes, 138 codes (3,163 licence-activity counts) have a prefix that only looks like an ISIC class. MTH-17 forbids mapping by that prefix. The four groups reconcile to 249,622.

- Allowed: "Al Daayen has 32 restaurant licences per 10,000 residents; the national rate is 15. Licence counts are not businesses or jobs." Also: "Coffee-shop licences are 3.05 times as common in Al Daayen's licence mix as in Qatar's."
- Never say: "over-served", "saturated", "too many restaurants", "Lusail has N restaurants".

| ID | Requirement |
|---|---|
| MTH-15 | C1 computes density and LQ for every municipality-by-activity cell and reproduces the worked example above. |
| MTH-16 | C1 does not compute an LQ where the local count is below 10; the card shows the count and "too few licences to compare". ASSUMPTION: at a count of 10 a 95% interval is already about plus or minus 60% of the value, so a smaller count makes the ratio misleading. |
| MTH-17 | C1 computes LQ at the seven-digit code and at the ISIC class reached through the reviewed spine, and never through a prefix of a six-digit legacy code (561000 is spare-parts trade, not restaurants). |

### C2 Licence churn with bulk months flagged

**Purpose.** Show how volatile an activity is, without letting administrative bulk cancellations distort the trend.

**Inputs.** `pub_licence_cancelled` (dated monthly cancellations by municipality and activity, 2015 to May 2025, plus an undated remainder); `pub_licence_active`.

**Formula.**

```
calendar   = every month from January 2015 through May 2025 (125 months)
T_m        = national dated cancellations, all activities, in month m
             a calendar month with no dated rows has T_m = 0
             undated rows are excluded from every T_m
bulk(m)    = T_m > 3 * median(T over those 125 months)
churn_ijy  = C_ijy / A_ij        C = cancellations in year y; A = active stock, May 2025
reported twice: including and excluding flagged months
```

Undated cancellations are shown as a separate count. A Wilson interval is shown when `C ≤ A`, labelled approximate because a flow is divided by a later stock, and labelled as the descriptive interval in section 3.

**Worked example (regression).** Methods, data and graph research:

| Quantity | Value |
|---|---|
| Cancellations 2015–2025 | 161,055, of which 153,669 dated and 7,386 undated |
| Months that must be flagged | July 2020 (40,791), June 2022 (14,212), September 2024 (11,232) |
| Share of dated cancellations in those three months | 43.1% |
| Restaurants (5610101), 2024, Doha: 318 / 2,109 active | 15.1% (including flagged months) |
| Restaurants (5610101), 2024, Al Daayen: 49 / 361 active | 13.6% (including flagged months) |
| ISIC 5610, cancellations 2022–2024 / active May 2025 | 2,510 / 7,878 = 0.32 |

Tolerance: counts exact; shares ± 0.1 percentage point. The rule may flag other months as well; the data test lists every flagged month and the method note in the release records them.

**Provenance and status.** Rates are Public, `observed`, caveat `calculated`. The bulk flag is `observed` (it is a rule); the statement that bulk months are administrative is `inferred`. **Compute cost.** Trivial (feasibility review; no time recorded).

**Limits and wording.** The series ends in May 2025. The open "issued" table holds only 12,533 licences, covers 610 codes and has no restaurant records (data and graph research), so openings and net formation are unknown.

- Allowed: "Restaurant-licence cancellations in Doha in 2024 equalled about 15% of the May 2025 active stock. Bulk months are flagged; they look administrative." Also: "New restaurant licences are not published, so net change is unknown."
- Never say: "net formation", "closures" (for licence cancellations), "N restaurants opened", "the official closure chart is wrong".

| ID | Requirement |
|---|---|
| MTH-18 | C2 flags bulk months by the rule above and flags at least the three months in the worked example. |
| MTH-19 | No function in the repository computes issued minus cancelled licences or a net-formation figure from the public licence tables. Entry and closure base rates are computed from the Public licence tables only by C31, by activity and on the source's own geography, as [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 7 says, and the survival base rate returns `NO_DATA` with `no_denominator` until a Public source links a cancellation to its issue; no rate is computed from the openings and closures of register companies (MTH-85), and the screen words stay "licence issues" and "licence cancellations". |
| MTH-20 | C2 shows every churn rate both with and without flagged months, and labels which is which. |

### C3 Pay-versus-mix decomposition of national mean pay

**Purpose.** Split the change in national mean monthly pay into pay change within groups and change in who is employed (Kitagawa 1955).

**Inputs.** `pub_wage_table`, rows from the portal table "Workers in Paid Employment (15 Years & Above) and Monthly Average Wage by Gender and Occupation" (national, nine occupation groups by sex, 2020 to 2025; 17 groups are populated). Paid workers and mean monthly wage per group and year.

**Formula.** With employment share `s_g` and mean wage `w_g` in years 0 and 1, and bars meaning the average of the two years:

```
mean_t   = sum_g s_gt * w_gt
change   = mean_1 - mean_0
within   = sum_g  s̄_g * (w_g1 - w_g0)      pay change inside groups
mix      = sum_g  w̄_g * (s_g1 - s_g0)      change in who is employed
check    : within + mix == change (exact up to floating point)
fixed-mix counterfactual = sum_g s_g0 * w_g1  vs  mean_0
```

**Worked example (regression).** Methods research, recomputed by the feasibility review, 2026-11-11:

| Quantity | Value |
|---|---|
| Mean monthly pay, 2020 → 2025 | QAR 10,084 → 11,855 (+QAR 1,771, +17.6%) |
| Within groups | QAR 38 |
| Mix | QAR 1,733 (97.8% of the rise) |
| Fixed 2020 mix | about +1.0% (uses 2020 weights, so it differs from the QAR 38 split) |
| Same split by economic activity, 2020 → 2023 | mix QAR 572 of 673 |

Tolerance: ± QAR 1 on each money figure; ± 0.1 percentage point on shares. The same function on the activity table gives the wage trends by sector of C19 (indicator 6), and the activity row above is that branch's span regression (MTH-97).

**Provenance and status.** Public, `observed`, caveats `calculated`, `named_table`, `composition_not_wages`. **Compute cost.** 0.05 s for 15,800 cells by 50 groups (methods research); the national case is trivial.

**Limits and wording.** Only 17 groups: any mix change inside a group counts as pay change. Survey means in nominal riyals. The occupation table and the activity table give the same paid-worker counts but different means: QAR 10,084 against 10,352 for 2020 and 11,714 against 11,025 for 2023 (methods research). This is OI-03.

- Allowed: "In the published table of 17 occupation-by-sex groups, average pay rose 17.6% from 2020 to 2025. About 98% of that rise came from a change in which jobs people hold. Composition drove the average."
- Never say: "wages did not rise", "nobody got a raise", "real pay", any figure in this card without the table's name.

| ID | Requirement |
|---|---|
| MTH-21 | C3 reproduces the worked example and asserts `within + mix == change`. |
| MTH-22 | The C3 card names its table on the card face and shows, in the Source chain (the evidence drawer), the other table's mean for the same year with the line "the two published tables differ; this card uses the occupation table". |
| MTH-23 | C3 is not displayed until OI-03 is recorded as closed in `OPEN_ITEMS.md`. |
| MTH-24 | C3 shows totals across sexes on its card; it uses sex only as a grouping inside the calculation. The table's published split by sex may appear only as a separate Public fact with its source and year, on the table's own national geography and categories, never inside a C3 figure and never beside a Synthetic, Simulated or protected figure ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 5; PUB-90). ASSUMPTION: the national card does not need the split to make its point. |

### C4 Sector unit economics and the break-even and breakpoint calculator

**Purpose.** Show what a business in the activity spends per riyal of output, from published survey tables, and let the user test their own rent, seats, average bill and opening days against those norms. Expected covers and a monthly staff cost are optional.

**Inputs.** `pub_sector_accounts`: the National Planning Council hotels-and-restaurants survey tables (economic indicators by activity; intermediate goods; intermediate services; establishments and employees by size), annual 2018 to 2022. slice S2 records which table holds each field. The v1 worked example is restaurants (ISIC 561). ASSUMPTION: other activities in the same surveys use the same functions once their tables pass the slice S2 checks.

**Public norms (2022, restaurants, ISIC 561).** Feasibility review and methods research:

| Norm | 2022 | Range 2018–2022 |
|---|---|---|
| Production value | QAR 6,337,897 thousand | |
| Establishments / employees | 2,086 / 41,458 | |
| Output per establishment | QAR 3.04 million (calculated) | QAR 2.44 to 3.04 million |
| Output per employee | QAR 152,875 (calculated) | |
| Intermediate goods / services, share of output | 40.6% / 16.5% | |
| Food / beverages, share of output | 29.3% / 5.6% | food 28.0 to 29.3% |
| Building rent, share of output | 11.6% | 11.6 to 15.1% |
| Compensation | QAR 1,308,140 thousand (20.6%) | 20.6 to 25.2% |
| Operating surplus | QAR 1,247,422 thousand (19.7%) | 6.9 to 19.7% |
| Average annual wage | QAR 31,579 | about 31,500 to 32,800 |
| Value added per worker | QAR 65,581 | |

**User inputs (all stated on the card).**

| Input | Unit | Rule |
|---|---|---|
| Monthly rent `R` | QAR | required; never prefilled (no open rent-by-district data was found) |
| Seats `S` | count | required; whole number of at least 1 |
| Average bill per cover `B` | QAR | required |
| Opening days per month `D` | days | default 30, editable. ASSUMPTION: a simple default the user can see and change |
| Expected covers per day `E` | covers | optional; enables breakpoints |
| Monthly staff cost `W` | QAR | optional; switches to mode B |

The calculator posts the six inputs, in this order, to the server method and renders the facts it returns: monthly rent, seats, average bill, opening days, expected covers per day, monthly staff cost. The browser does not compute a displayed number. Breakpoints are returned only when expected covers are entered.

**Formula.** For each survey year `y`, from that year's own shares of output:

```
Mode A (staff varies with sales at the sector norm; rent is the only fixed cost):
  m_y  = rent_share_y + surplus_share_y          (equals 1 minus all non-rent costs)
  F    = R
Mode B (the user's staff cost is fixed):
  m_y  = rent_share_y + surplus_share_y + compensation_share_y
  F    = R + W
break-even revenue per month   Rev*_y = F / m_y
break-even covers per day      N*_y   = ceil( Rev*_y / (B * D) )
seat turns per day             T*_y   = N*_y / S
breakpoints (only when E is given):
  maximum rent                 R_max  = E * B * D * m_y          (mode B: minus W)
  minimum bill                 B_min  = F / (E * D * m_y)
  maximum staff cost (mode B)  W_max  = E * B * D * m_y - R
show the 2022 value and the range across 2018–2022
optional target-surplus scenario (never called break-even):
  U = 0 is break-even and is the default; require 0 <= U < m_y
  required revenue             Rev_U  = F / (m_y - U)
  covers, seat turns and the three breakpoints use (m_y - U) in place of m_y
  the named case uses U = 0.197, the sector's 2022 surplus share, and is labelled
  "to earn the sector's 2022 surplus share"
```

**Worked example (regression).** Norms are real; the user inputs are an illustration.

| Quantity | Value |
|---|---|
| m 2022, mode A (11.6% + 19.7%) | 0.313 |
| Illustrative inputs | R = 40,000; S = 60; B = 120; D = 30 |
| Break-even revenue | QAR 127,796 per month |
| Break-even covers per day | 36 (35.5 rounded up) |
| Seat turns per day | 0.6 |
| With E = 50: maximum rent / minimum bill | QAR 56,340 / QAR 85.20 |

Tolerance: m ± 0.002; money ± 0.5%. A separate arithmetic test checks the norms: 6,337,897 / 2,086 = 3,038.3 thousand; 1,308,140 / 6,337,897 = 20.6%; 1,247,422 / 6,337,897 = 19.7%.

**Target-surplus regression (not break-even).** Same illustrative inputs, mode A, `U = 0.197`. In thousandths of output, the rent share is 116 and the surplus share is 197, so `m = 116 + 197 = 313` thousandths (`0.313`), and `m - U = 313 - 197 = 116` thousandths (`0.116`).

```
required revenue = 40,000 / 0.116 = 40,000,000 / 116
                 = 344,827 + 68/116
                 = 344,827.586..., which rounds to QAR 344,827.59 a month
covers           = 344,827.59 / (120 * 30) = 344,827.59 / 3,600 = 95.785...
                 the next whole number above is 96 covers a day
seat turns       = 96 / 60 = 1.6
with E = 50:
  maximum rent   = 50 * 120 * 30 * 0.116 = 180,000 * 0.116 = QAR 20,880
  minimum bill   = 40,000 / (50 * 30 * 0.116) = 40,000 / 174
                 = 229 + 154/174 = 229.885..., which rounds to QAR 229.89
```

The label on screen is "to earn the sector's 2022 surplus share". At the entered covers, expected revenue is 50 * 120 * 30 = 180,000. Rent of 20,880 is 20,880 / 180,000 = 0.116 of that revenue, and the surplus is 0.197 * 180,000 = 35,460. Those two shares sum to 0.313, which is `m`. This case keeps a surplus. It is not the break-even case. `U = 0` remains the default.

**Optional incentive packages ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 7).** The user may apply one incentive package at a time from the agency's records (`pub_investqa_record`, PUB-88), tagged "your inputs" with its source page; `sector_facts` takes one `incentive_key` ([08_BACKEND.md](08_BACKEND.md)). A package changes only the user's own scenario inputs; it never changes a Public norm or any other Public figure. The calculator reads from a package only these parameter kinds, each held under its key in `pub_investqa_record.parameter_key`:

| Parameter key | Parameter kind | Input it changes | Effect |
|---|---|---|---|
| `rent_share` | a share `a_R` off the rent | `R` | `R' = R * (1 - a_R)` |
| `rent_amount` | a monthly amount `A_R` off the rent (QAR) | `R` | `R' = max(R - A_R, 0)` |
| `staff_share` | a share `a_W` off the staff cost | `W`, mode B only | `W' = W * (1 - a_W)` |
| `staff_amount` | a monthly amount `A_W` off the staff cost (QAR) | `W`, mode B only | `W' = max(W - A_W, 0)` |

Any other parameter, such as an exemption, a one-off amount or a land offer, has the key `other` and is listed with its page link as "not used by this calculator"; a one-off amount is never spread over months. Shares lie from 0 to 1. Within the one package, at most one parameter may change each input; a package with two parameters for the same input is refused with reason `one_package_per_input`.

```
results side by side: without the package, as above, and with it
with it:  F' = R' (mode A) or R' + W' (mode B), used in place of F in every formula above,
          the target-surplus scenario included
rent breakpoint with a package: the highest rent before the package that the entered covers allow,
          R_max' / (1 - a_R) for a share (NO_DATA when a_R = 1) or R_max' + A_R for an amount,
          where R_max' is the maximum rent above, computed with W'
staff-cost breakpoint with a package (mode B): W_max' / (1 - a_W) for a share (NO_DATA when
          a_W = 1) or W_max' + A_W for an amount, where W_max' is the maximum staff cost above,
          computed with R'
the duration the page states is shown beside the second result, or "duration not stated by the source"
```

**Incentive regression (fixture package, not a real offer).** Mode A, the illustrative inputs above, and a fixture package that takes `a_R = 0.25` off the rent. `R' = 30,000`. Break-even revenue is 30,000 / 0.313 = 95,846.65, shown as QAR 95,847 a month. 95,846.65 / 3,600 = 26.62, so 27 covers a day, and 27 / 60 = 0.45 seat turns. With E = 50, the minimum bill is 30,000 / (50 * 30 * 0.313) = 30,000 / 469.5 = 63.90, and the highest rent before the package is 56,340 / 0.75 = QAR 75,120. Without the package the results are those of the break-even example.

**Scenarios beside the calculator ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) items 9 and 10).** The catchment-share scenario (C34) and the revenue range of the user's outlet (C35) join this calculator. C35 shows this card's break-even revenue beside its cases and reads the same survey norms, so it stays off screen while OI-03 is open (MTH-29). No output of this card takes a C33, C34 or C35 figure as an input.

**Provenance and status.** Norms: Public, `observed`, caveats `calculated`, `national_average`, `world_cup_year`. Calculator outputs: Public (least-real release input), `inferred`, "your inputs" tag. With a package, the Source chain also names the package's page and retrieval date, with caveat `agency_page`. **Compute cost.** Trivial (feasibility review; no time recorded).

**Limits and wording.** National averages over all restaurant types and sizes. 2022 was a World Cup year; the surplus share jumped from about 7% (2018–2019) to 15–20% (2020–2022) for reasons not verified. Mode A treats staff as varying with sales, which flatters very small outlets; mode B exists for that reason. The figure 8,579,462 thousand from an earlier design is a different scope and is not used (OI-03).

- Allowed: "At the sector's 2022 cost shares, your rent needs about 36 covers a day to break even (0.6 turns per seat). Across 2018–2022 the figure ranges from {low} to {high}." Also, for the optional scenario only: "To earn the sector's 2022 surplus share, the same inputs need about {covers} covers a day ({turns} turns per seat)." With a package: "With the package you chose, from its page, the same inputs need about {covers} covers a day to break even while the package lasts." The braces are filled by the Fact chip.
- Never say: "you will make a profit", "expected revenue", "demand at this site", "capture rate" (allowed only as the name of the user's input in C35), "go" or "no-go" as a verdict, "break-even" for the surplus-share scenario, "you qualify", "you will receive", or "the incentive makes it profitable".

| ID | Requirement |
|---|---|
| MTH-25 | C4 computes every output for each survey year 2018–2022 and shows the 2022 value with the min–max range across years. |
| MTH-26 | C4 reproduces the break-even worked example, the norm checks above, and the target-surplus regression (`m - U = 0.116`; revenue QAR 344,827.59 a month; 96 covers a day; 1.6 seat turns; with E = 50, maximum rent QAR 20,880 and minimum bill QAR 229.89). |
| MTH-27 | C4 lists every user input and every public norm it used, with year and table, in the Source chain (the evidence drawer). |
| MTH-28 | No code divides a C4 output by presence, footfall or earner counts. C4 never returns a forecast of revenue, demand or capture. It returns the revenue that the user's own inputs would require. The site estimate (C33) and the user's scenarios (C34, C35) are separate cards; none of them is a forecast, and none feeds a C4 output. |
| MTH-29 | C4 is not displayed until OI-03 is recorded as closed in `OPEN_ITEMS.md`. |
| MTH-61 | C4 applies only the four parameter keys above (`rent_share`, `rent_amount`, `staff_share`, `staff_amount`), one package at a time and at most one parameter per input, and returns the results with and without the package side by side, with the duration the page states. It reproduces the incentive fixture: QAR 95,847 a month, 27 covers a day and 0.45 seat turns; with E = 50, a minimum bill of QAR 63.90 and a highest rent before the package of QAR 75,120. |
| MTH-62 | A package parameter is a Public fact from `pub_investqa_record` with its page link and retrieval date, applied only as the user's input, with caveats `your_inputs` and `agency_page`. No package changes a Public norm, no one-off amount is spread over months, and no forecast stated on a page enters the calculator (PUB-88). |

### C5 Customs supplier lens

**Purpose.** For an activity's input basket, show which countries supply each input, at what calculated import unit value (QAR per kg), how concentrated supply is, and how it moves. The valuation basis is shown as the source states it, or as "not stated by the source".

**Inputs.** `pub_customs_import` (National Planning Council imports by tariff code, origin and month; 2025–2026 at twelve digits, 2019–2024 at eight digits; fields include value in QAR and weight in kg); the reviewed basket configuration (activity → at most eight input lines), held as `graph_edge` rows from activity to input to tariff line; `pub_licence_active` for licensed wholesale depth by municipality.

**Formula.** For basket line `h`, origin `o`, window of the latest 12 complete months in the release:

```
Vkg_o = sum of value (QAR) over rows with kg > 0
K_o   = sum of kg over those same rows
UV_o  = Vkg_o / K_o                     calculated import unit value, QAR per kg
V_o   = sum of value over all rows of the origin, including rows with no weight
s_o   = V_o / sum_o V_o                 origin share of value
HHI   = 10,000 * sum_o s_o^2            near 0 = many small origins; 10,000 = one origin
trend = (V_last12 - V_prior12) / V_prior12
```

`UV_o` is `NO_DATA` when `K_o = 0`. The trend is `NO_DATA` when the prior-12-month value is zero. Also shown: the top origin's share and the number of origins. Rows with no weight are excluded from the unit value and counted on the card; they stay inside `V_o`. A month with no row for an origin is drawn as a gap, not as a zero. The HHI is the sum of squared shares, as defined by the United States Department of Justice; no competition-law threshold is applied. Shares, the HHI and the trend use every origin.

The component is named `supplier_lens`. It is drawn as ranked bars, one block per basket input, at most five origins per input. That drawing limit does not drop origins from the sums. The fifteen-node limit applies only to the source chain shown in the Source chain (the evidence drawer).

**Worked example (regression).** Data research, imports 2025 (QAR, value divided by weight):

| Quantity | Value |
|---|---|
| Imports 2025, total | QAR 138.53 bn over 216,073 rows |
| Heading 1902, Italy | QAR 20.08 m for 2,311 t = QAR 8.69 per kg |
| Heading 1902, Saudi Arabia (largest origin) | QAR 36.90 m at QAR 11.45 per kg |
| Heading 0406, Italy / Denmark | QAR 40.61 / 26.06 per kg |
| Heading 1509, Italy / Lebanon | QAR 30.60 / 19.26 per kg |

These are heading-level checks of the data and arithmetic only. Italy: 2,311 t = 2,311,000 kg, and 20,080,000 / 2,311,000 = 8.6889, which rounds to QAR 8.69 per kg. Heading 1902 also holds instant noodles (one origin at QAR 19.56 per kg, feasibility review), so a heading-level value must never be shown as the price of pasta. No HHI and no twelve-month trend were computed by the research. Those two expectations are an illustrative note, not a passing regression, until they are pinned. The slice S7 gate fails while they remain unpinned (MTH-03).

**Provenance and status.** Public, `observed`, caveats `calculated`, `editorial_basket`. **Compute cost.** Light: about 1.1 to 1.7 million rows, served by the embedded engine over Parquet (feasibility review; no time recorded).

**Limits and wording.** Unit value is an average over mixed products and qualities, not a price. Some quantity units are not kg. Descriptions vary by year. The basket is an editorial choice.

- Allowed: "In 2025, this input reached Qatar mainly from these countries, at these calculated import unit values per kilogram (calculated). The source's valuation basis is shown beside them, or the words 'not stated by the source'."
- Never say: "buy from", any company name, "cheapest supplier", "Italian pasta is cheaper", "supply risk score".

| ID | Requirement |
|---|---|
| MTH-30 | Basket lines may be eight digits or finer (PUB-42). A four-digit heading or a six-digit subheading is never a basket line. For a period covered only by the eight-digit table, a finer line rolls up to its eight-digit parent (PUB-44). If that parent also holds lines excluded from the basket, the earlier-period value is marked "includes excluded lines" or withheld. |
| MTH-31 | C5 never displays a figure at four or six digits; heading-level values exist only in tests. |
| MTH-32 | C5 reproduces the worked example unit values to ± QAR 0.01 per kg and the 2025 total to ± QAR 0.01 bn. |
| MTH-33 | The v1 basket configuration covers at most three activities with at most eight lines each, and each line carries a reviewer and a review date. The `supplier_lens` component draws ranked bars, one block per basket input and at most five origins per input. The fifteen-node limit applies only to the source chain in the evidence drawer. |

### C6 Typical neighbours

**Purpose.** Show which place categories an activity is found near across the public places data, and which of them are found near the pin.

**Inputs.** `pub_place` (Overture places, release 2026-10-21.0, pinned); co-location pairs stored in `graph_edge` with `clq`, `p`, `q`, `n_focal`, `n_neighbour`. The third places source, `places_fsq`, keeps its own table `pub_place_fsq`, its attribution and a reviewed category mapping, and it is fetched inside `./eii build-public` from the public copy on Source Cooperative, read without an account, only the files that cover Qatar ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 21); the registry records the release used, and its places are shown with that date. Once it is pinned, C6 and the competitor counts of C33 and C34 may read it; a count or a co-location run reads one places table at a time, named in its lineage, and no count adds or merges the two tables. ASSUMPTION: C12, C16 and C17 keep reading `pub_place` only until a reviewed change adds the third source to them.

**Formula.** Radius co-location quotient (CLQ) in the family of Leslie and Kronenfeld (2011), radius r = 250 m, over points in the Greater Doha box (25.18–25.47 N, 51.35–51.65 E) with confidence of at least 0.5. ASSUMPTION: the box, the confidence filter and r follow the research runs; the exact settings of the feasibility review's run were not all recorded.

```
for each focal point i in A: n_i = other points within r;  n_iB = those of category B
CLQ(A→B) = [ (1/N_A) * sum_i (n_iB / n_i) ] / [ N_B' / (N - 1) ]
           N_B' = N_B, or N_B - 1 when B = A; focal points with n_i = 0 are dropped from N_A
significance: shuffle category labels over all N points 999 times (fixed seed)
           p = (1 + #{CLQ_perm >= CLQ_obs}) / 1000
multiple testing: Benjamini–Hochberg over all candidate B for one A, q <= 0.05
keep: N_B >= 20, CLQ >= 1.2, q <= 0.05; show at most six, highest CLQ first
presence at the pin: B is "found" if at least one B point lies within 250 m (straight line)
```

**Illustrative note (not a passing regression).** Feasibility review, 2026-11-11, Greater Doha extract, 999 permutations, 5% false-discovery control. Focal set "Italian restaurants including pizza places" (174 points). The seed, release hash, category identifiers, candidate set and expected p and q values were not recorded, so this note is not a passing regression until they are written here (MTH-03). The box and the confidence filter are in the formula above.

| Neighbour category | CLQ |
|---|---|
| fast food | 1.98 |
| coffee shop | 1.87 |
| café | 1.53 |
| restaurant | 1.38 |
| fashion store | 1.38 |

With Italian restaurants only (61 points), no neighbour survives. Tolerance: the same five categories survive, CLQ ± 0.05, and none survive for the narrow set.

**Provenance and status.** Public, `observed`, caveats `found_near_not_attract`, `places_incomplete`, `pizza_included`. **Compute cost.** 2.8 s for 999 permutations (feasibility review); 0.4 s for the full national CLQ matrix and 0.6 s for 199 permutations for one activity (graph research).

**Limits and wording.** A label permutation tests association beyond category frequency but does not control for overall density, so it supports "found near", not "attract". The open places extract holds about 26,000 Qatar records against about 71,000 establishments, so absence may be a data gap; the coverage of `pub_place_fsq` is counted when it is pinned. The result with pizza included is the only one that survives; the card must say pizza is included.

- Allowed: "In Greater Doha's public places data, Italian restaurants (including pizza places) are found near fast food, coffee shops, cafés, restaurants and fashion stores. Here, 3 of 5 are found within 250 m." For an absent chip: "not found in public places data".
- Never say: "attract", "draw customers", "missing neighbour", "opportunity", "gap in the market".

| ID | Requirement |
|---|---|
| MTH-34 | C6 is computed at build time; the release holds only pairs that pass the keep rule, with `clq`, `p` and `q`. |
| MTH-35 | The C6 chip row states the focal definition (for the flagship, "including pizza places") on the card face. |
| MTH-36 | The C6 random seed and every parameter in the formula block are written to the method note in the release. |

### C7 Shared reach between two doors

**Purpose.** For a second door, show how much of its reach is already within the first door's reach.

**Inputs.** Areas from `make_area`. In public-only mode the sets are whole base cells of the fixed frame: `make_area` reads no privacy-derived release unit and no protected or simulated table, and the snap report is technical metadata, not a Synthetic fact. Outside public-only mode, earners mode uses whole release units; residents mode reads no protected table, so it may use the exact drawn or travel-time shapes ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 6). Resident weights come from Census 2020 population in `pub_census_district` (`district_key`, `period`, `indicator`, `value`, `unit`, `source_id`), using count indicator `residents` with unit `persons` (PUB-84), joined to the centroid of `district.geometry`. Covered-earner weights come from `resident_pay` or `worker_pay`. The link times of C25 apply when a dial situation or an hour sets drive times. The district population comes from the census map layer that [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 10 admits to the local release (OI-04 closed for version 1); if that layer is switched off (PUB-12), residents mode returns `NO_DATA`.

**Formula.**

```
centre of a district = the centroid of district.geometry
a district counts in X when that centroid lies in a unit of X
  (in public-only mode, in a base cell of X; for an exact shape in residents mode, inside the shape)
a centroid on a shared boundary counts once, in the unit with the smaller id
W(X)          = sum of the mode's weight over X
  residents   : Census 2020 population of districts whose centre lies in X
  earners     : released (treated) earner counts of the units in X
                from one home family (MTH-55): resident_pay on
                rp_all_count, or worker_pay on wp_all_count
                (not available in public-only mode)
shared(B | A) = W(A ∩ B) / W(B)
shared(A | B) = W(A ∩ B) / W(A)
if W(A) = 0 or W(B) = 0: NO_DATA, never zero and never a ratio
```

In earners mode the intersection is itself a set of release units, so the privacy rules of [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) apply to `W(A ∩ B)` and `W(B)`; a failing count makes the share Suppressed. No method asks the privacy engine for a finer unit so that the overlap looks larger (MTH-53).

**Illustrative note (not a passing regression).** Methods research: two points 2.8 km apart in Al Daayen; 10-minute free-flow drive areas held 90,476 and 74,627 Census 2020 residents, and the second lay wholly inside the first (shared 100%); a central Doha point shared 5% at 10 minutes and 48% at 15 minutes with the first. The coordinates, modes, cut-offs, speed regime, input district weights and expected shares are not pinned, so this note is not a passing regression. The slice S7 gate fails until they are written here (MTH-03). An arithmetic test asserts shared(B | A) = 100% when B is a subset of A, 0% when the two sets are disjoint, and `NO_DATA` when either weight is zero.

**Provenance and status.** Residents mode with free-flow times: Public. Earners mode: Synthetic. Any dial situation: Simulated (least-real rule). Evidence status `observed`; caveat `shared_reach_not_sales`. **Compute cost.** A three-ring drive area in 0.12 s and a routing graph built in 5 s with pyvalhalla 3.9.1 (methods research); the set intersection is trivial.

**Limits and wording.** Free-flow speeds overstate reach; residents are 2020 counts; district centres are coarse.

- Allowed: "About 48 in 100 of the residents within 15 minutes of door B are also within 15 minutes of door A."
- Never say: "lost sales", "cannibalisation", "the new branch will take N% of customers".

| ID | Requirement |
|---|---|
| MTH-37 | C7 computes shared reach on snapped sets of whole release units in earners mode and, in public-only mode, on whole base cells of the fixed frame. Residents mode may use the exact shapes, testing each district centre against the shape. One share never mixes snapped and exact shapes, and no protected figure is read for a raw polygon (MTH-56). |
| MTH-38 | C7 shows the mode (residents or covered earners) and the situation on the card face. |

### C8 Coverage share and the reliability mark

**Purpose.** Say how much of an area's earners a wage-based figure can see, and how reliable each small-count figure is.

**Inputs.** A private-employer share from a source that may enter the release (PUB-12, PUB-13): zone rows from `pub_census_zone`, a national row from `pub_census_national` (`period`, `indicator`, `value`, `unit`, `source_id`). `zone` names the geography. Any fact's count feeds the reliability mark (section 3). The census map layers state no licence; [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 10 admits them to the local release of this internal project, each figure with its source and retrieval date, and closes OI-04 for version 1. If a layer is switched off (PUB-12), no value, derived share, title or geometry from it enters a release.

**Formula.**

```
coverage = employed residents working for private employers
           / all employed residents
           on the finest admitted geography (PUB-82) that holds the share:
           zone, otherwise municipality, otherwise national
the card names that geography
if the area spans several zones, the min and max are shown as well (no blending)
if no admitted geography holds the share: NO_DATA
```

ASSUMPTION: the private-employer share is a proxy for wage-protection coverage, as the research states; it is shown as a proxy. "Not measured" is not this gap. It is the coverage label for a person who has no pay in the wage records. An unknown housing class is the separate value `unknown`.

**Validation-file arithmetic.** Methods research, Census 2020. National: 1,617,208 / 2,050,252 = 0.7888, which rounds to 78.9%. The zone figures below are the rounded shares stated with that check. With OI-04 closed for version 1 (decision 0017 item 10), they are regression values for the census layer in the local release (PUB-71).

| Quantity | Value |
|---|---|
| National private-employer share | 78.9% |
| 75 zones with at least 1,000 employed residents | 23% (zone 68) to 99% (zone 57); median 78%; 9 zones below 50% |
| Zone 69 / zone 70 (Al Daayen) | 72% / 45% |

Tolerance: ± 0.5 percentage point.

**Provenance and status.** Public, `observed`, caveat `coverage_private_proxy`, with the source and retrieval date of the census layer. If the layer is switched off (PUB-12), the bar is `NO_DATA` and the validation figures are not release facts. **Compute cost.** Trivial (methods research; no time recorded).

**Limits and wording.** Census 2020 is nearly six years old. The share describes residents, not workers in the zone. The card names the geography it used.

- Allowed, with a zone share in the release: "This pay figure covers private-sector earners only. In 2020, about 72 in 100 employed residents of this zone worked for private employers."
- If the layer is switched off (PUB-12): "The coverage share is not on screen. The census employment layer has no stated licence."
- Never say: "all earners", "the average resident earns", "complete picture", or "Not measured" for this unpublished workplace gap.

| ID | Requirement |
|---|---|
| MTH-39 | Every resident-pay card shows the C8 coverage bar, naming the geography used. The bar uses the finest admitted geography that holds the private-employer share (zone, otherwise municipality, otherwise national; PUB-82): the census map layers enter the local release by [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 10, which closes OI-04 for version 1, and a layer that is switched off (PUB-12) gives `NO_DATA`. The worker-pay card returns `NO_DATA` with reason `coverage_by_workplace_not_published`. It does not use the coverage label "Not measured" for that gap. |
| MTH-40 | C8 never interpolates a census share onto grid cells or blends it into a protected figure. |

### C9 Zone momentum from utility series

**Purpose.** Show which zones are growing in activity, using the utility series, the only current public series published by zone. Night-time radiance by area and month is a grid layer of its own (C36) and is never blended into this card.

**Inputs.** `pub_zone_utility` (electricity and water consumption by zone, annual 2021 to 2026; 2026 is January to August); `zone` with a crosswalk where zone numbering differs between sources.

**Formula.**

```
G_z    = E_z,2025 / E_z,2021                 growth multiple
G_nat  = E_nat,2025 / E_nat,2021
rel_z  = G_z / G_nat
ranked only where E_z,2021 >= 1,000,000 kWh (1 GWh)
the partial 2026 value is shown as "January to August" and never compared with a full year
```

**Worked example (regression).** Data research and feasibility review (MASTER section 9):

| Quantity | Value |
|---|---|
| Zone 69 electricity 2021 → 2025 | 429,964,072 → 1,436,402,796 kWh = 3.34 times |
| National | 41.78 bn → 55.83 bn kWh = 1.34 times |
| Fastest zones above 1 GWh | zone 2 (6.5), zone 72 (5.4), zone 29 (4.0), zone 69 (3.3) |

Tolerance: multiples ± 0.01; the ranking order exact.

**Provenance and status.** Public, `observed`, caveats `calculated`, `activity_proxy_not_population`, `partial_year` where 2026 appears. **Compute cost.** Trivial (feasibility review; no time recorded).

**Limits and wording.** Consumption includes non-residential use and district cooling. It is an activity proxy, not population.

- Allowed: "Electricity use in zone 69 grew 3.34 times from 2021 to 2025; nationally it grew 1.34 times. Electricity is a sign of activity, not a count of people."
- Never say: "population grew", "footfall", "demand grew N%".

| ID | Requirement |
|---|---|
| MTH-41 | C9 reproduces the worked example and never annualises the partial 2026 value. ASSUMPTION: the 1 GWh base filter follows the research ranking and stops tiny bases producing large multiples. |

### C10 Staffing bands beside published averages and the statutory minimum

**Purpose.** For the jobs an outlet hires, show the protected pay bands among people living within reach, beside real national anchors.

**Inputs.** `occupation_pay` (Synthetic released band counts by occupation group and release unit); `pub_wage_table` (national mean monthly wage by occupation group, 2025); `pub_sector_accounts` (restaurant average annual wage); the statutory minimum. ASSUMPTION: the minimum is held as a rule row in `pub_wage_table` with its own lineage, because no pinned table is named for legal rates. The occupation groups an outlet hires are set in the `staffing_and_pay` playbook configuration.

**Statutory minimum (Public).** Law No. 17 of 2020, adopted 30 August 2020: a minimum basic wage of QAR 1,000 a month, plus allowances of at least QAR 500 for housing and QAR 300 for food when the employer does not provide them (International Labour Organization news page, retrieved 2026-11-11).

**Formula.**

```
area           = make_area(pin, mode="drive", cutoff=30 minutes), snapped
               drive 20 and drive 30 are available only to staffing_and_pay
band counts    = sum of released occupation_pay band counts over the area's units
               home family: occupation_pay on op_res_quartile,
               occupation-group breakdown (MTH-55)
median band    = returned only where the exported privacy tier publishes it
quartile range = returned only where the exported privacy tier publishes it
otherwise      = "not available at this area size", and the next wider
                 staffing drive cut-off is offered (5, then 10, then 15, then 20, then 30)
                 if 30 minutes still does not publish the band, the same sentence
                 is shown and no wider cut-off is invented
national mean  = sum over sexes of (workers * mean wage) / sum of workers, per group
restaurant mean monthly equivalent = 31,579 / 12 = 2,631.583..., shown as QAR 2,632
```

**Worked example (regression).** Public anchors only, since bands are Synthetic: national mean 2025 QAR 11,855 (C3 table); restaurant average annual wage 2022 QAR 31,579. Monthly equivalent: 31,579 / 12 = 2,631.583..., which rounds to QAR 2,632. Minimum QAR 1,000 basic, and 1,000 + 500 + 300 = QAR 1,800 when housing and food are paid in cash. A band test on a fixed synthetic fixture asserts that, where the exported tier does not publish the median band or the quartile range, the card says "not available at this area size" and offers the wider area.

**Provenance and status.** Bands: Synthetic, `observed`, caveat `synthetic_demonstration`. They may appear only in a claim or component whose subject is `area`. Anchors: Public, `observed`. They are separate facts with separate chips, never one composite number. **Compute cost.** A sum over 15 to 130 precomputed cells in 0.4 to 3 ms was recorded for smaller catchments (feasibility review, citing the architecture benchmarks). The cell range for the 30-minute drive is not written here until that cut-off is measured.

**Limits and wording.** National means are means; the bands are median and quartile bands. Coverage applies (C8).

- Allowed: "Pay bands here are synthetic: they show the format a linked wage feed would give, not what cooks earn in this area. Beside them: the published national average for the group and the legal minimum."
- Never say: "you should pay", "the market rate here is", "cooks in Lusail earn", any nationality or sex split on this card (official splits appear only as separate Public facts on their own cards, PUB-90).

| ID | Requirement |
|---|---|
| MTH-42 | C10 shows the statutory minimum with its law number and the International Labour Organization source on every staffing card. |
| MTH-43 | C10 never shows a mean, minimum or maximum computed from synthetic records; only released bands. |
| MTH-44 | C10 combines the public table across sexes before display (see MTH-24 for the reason). |

### C14 Sale price per square metre

**Purpose.** Show the median sale price per square metre for a district and year, always with the deal count.

**Inputs.** Transaction rows of the Ministry of Justice weekly real-estate sales bulletin (Qatar Open Data Portal, CC BY, retrieved 2026-11-11), after the district crosswalk has matched the name. The English property-type field is not used. The release table is `pub_property_sale`. Rows that do not match the crosswalk are excluded, never guessed.

**Formula.**

```
keep a row only when the crosswalk matches one district, price_qar > 0 and area_m2 > 0
price_per_m2 = price_qar / area_m2
group by district, year and the reviewed Arabic property type
median       = the median of price_per_m2 in the group
               an even count takes the mean of the two central values
deal_count   = the number of kept rows in the group
zero kept rows: NO_DATA, and the median is null
```

**Worked example.** The deal counts are pinned by the public data pack. The median prices in riyals are not in the pack, so they are not a passing regression until they are written here. The slice S7 gate fails for those medians until then (MTH-51).

| Quantity | Value |
|---|---|
| Crosswalk name "Lusail 69", 2024 | 6 deals |
| Crosswalk name "Lusail 69", 2025 | 13 deals |
| Median QAR per square metre, both years | not pinned |

Arithmetic check of the median rule, on invented inputs that are not a figure about a place: prices 200 and 400 with areas 20 and 20 give 200 / 20 = 10 and 400 / 20 = 20 riyals per square metre. Two values, so the median is (10 + 20) / 2 = 15, and the deal count is 2. Zero kept rows returns `NO_DATA`.

**Residential unit sales ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)).** The same rule serves `pub_property_resi` (`prop_resi_units`, the weekly residential unit sales bulletin, a different dataset from `prop_sales`) for the D2 district price layer and the reverse view. Rows pass the district crosswalk (PUB-28) and lose their identifiers (PUB-14). Each median's basis is held in the column `price_basis` of `pub_property_resi` (document 03): `per_m2` where the rows carry a floor area, otherwise `per_unit`; a positive area is required only for `per_m2`. Slice S2 confirms the fields, and the card names the basis from that column. Medians of different bases are never compared or combined. Every price shows its deal count.

**Provenance and status.** Public, `observed`, caveat `deal_count_shown`. A price is never shown without its deal count. **Compute cost.** Not separately timed.

**Limits and wording.** Few deals sit in the Lusail crosswalk. District names change: the source uses both "Lusail" and "Lusail 69". Identifiers on the source rows never enter the release.

- Allowed: "The median sale price for this district, property type and year, with this deal count."
- Never say: a price without the deal count, "the market will rise", or a value for an unmatched district name.

| ID | Requirement |
|---|---|
| MTH-50 | C14 keeps only crosswalk-matched rows with a positive price and a positive area, sets price per square metre to price divided by area, and returns the median and the deal count by district, year and reviewed Arabic property type. Zero kept rows returns `NO_DATA`. |
| MTH-51 | C14's pinned deal counts for the "Lusail 69" crosswalk are 6 deals in 2024 and 13 deals in 2025. The median prices in riyals are not in the pack. Until they are written here, that part of the example is not a passing regression, and the slice S7 gate fails for it. The invented pair (10 and 20, median 15, two deals) is the arithmetic test of the median rule. |
| MTH-63 | C14 serves `pub_property_resi` with the same keep rule (a positive area required only for `per_m2`), median rule and deal count, on the basis that its column `price_basis` records (`per_m2` or `per_unit`), named on the card; medians of different bases are never compared or combined. Its deal counts and medians are pinned by the slice that builds the price layer (MTH-60). |

### C15 Area presence counts

**Purpose.** Show the estimated people present in an area hour by hour, split into workers, residents and visitors, each with a range, for every day type the release holds: the days of the dial situations, the summer setting and the three event days (journey D2; [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 7). The counts replace the presence index. Beside those segment counts, the card returns three separate outputs for who passes the area in that hour ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 16): a one-way split by `age_band`, by `gender` and by `nationality_group`, each a count and a share from the released rows of `presence_split` (DAT-169, PRV-134). A share is the value's count over the split's own total (the sum of the kind's published values with `other`), and the age output includes `other`. A value below the minimum appears inside `other`; a kind that cannot pass is withheld whole with `BELOW_PANEL_MINIMUM`. A split of an area is, per value, the sum of the published values of the area's snapped whole units; the units' `other` values sum into the area's `other`; a share is over the area's split total; the card says that `other` holds pooled values, and the age value `other` is labelled "under 15 or pooled". A split is never apportioned to a drawn outline. Flow splits are released and reachable through the back end; no claim, card or screen shows them in this decision's sweep. Those of `flow_split` count person trips, with shares over the split's own total, and are never set as parts of the vehicle-trip flow estimate. Any display, on C15 or the site answer, waits for the session on value extraction (the OPEN lines of [09_AI_ASSISTANT.md](09_AI_ASSISTANT.md) and [10_FRONTEND.md](10_FRONTEND.md); the lead's ruling L-174 item 9). No two splits are crossed, and none is crossed with `segment`. No split joins to a worker, residence or company record. A split is shown as its values and their shares; its own total is never shown as the cell's presence figure.

**Inputs.** The released hourly presence counts of `presence_count` by release unit, day type, summer setting, hour and segment (`worker`, `resident`, `visitor`), each with the low and high the release states and its status ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md), DAT-138). The custodian plane releases them only at release-unit grain, under the disclosure controls of [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) (panel minimum, complementary suppression by complete group, rounding). This card does not rescale them.

**Formula.** One tested formula, shared with the synthetic-world checks:

```
count(A, d, h, s, g) = exact sum of the released unit counts over A, a set of whole published
                       units (a map unit or a release-unit candidate of C11), for day type d,
                       hour h, summer setting s and segment g
low and high      = the sum of the unit lows and the sum of the unit highs
                    (an envelope, not a confidence interval)
home family: the released presence table's partition, one segment (MTH-55)
a unit group (unit, day type, hour, summer) is complete when its three segment rows have status
  published; a group withheld as null rows with BELOW_PANEL_MINIMUM is incomplete, and a null is
  never summed as zero (PRV-58, DAT-138)
the three counts of A are returned only when every unit of A has its complete group;
  otherwise all three are withheld with BELOW_PANEL_MINIMUM, and no partial sum is returned
every area from make_area (drawn, radius, walk or drive) takes C18's apportioned counts over the
  units its exact outline overlaps, evidence status inferred
workers, residents and visitors are three facts; their sum is used only by C27 and by the
  all-people line of the hourly chart, from complete groups
```

The seasonal shape of the visitor segment is calibrated and checked against published museum visitor counts (C26). The hour-of-day shape of simulated visits by place category is calibrated to the relative busyness of the named venues of that category, pooled over the venues ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 18; C26, C37). No level is anchored to a public series, hour by hour or otherwise, no single venue's shape is used, and the screen never says that a count is anchored. Public monthly context series and a venue's relative busyness, when shown, are separate Public facts and never share a component with an estimated-people figure.

**Worked example (synthetic fixture, not a finding about a place).** A set A of two published units, one day type, hour and summer setting. Unit U1 has 120 workers (110 to 130), 40 residents (35 to 45) and 30 visitors (25 to 35). Unit U2 has 80 workers (72 to 88), 40 residents (36 to 44) and 20 visitors (16 to 24). Both groups are complete. A has 200 workers (182 to 218), 80 residents (71 to 89) and 50 visitors (41 to 59). Second fixture: the group of U2 is present with status `withheld`: its three rows hold null values and `BELOW_PANEL_MINIMUM`. All three counts of A are withheld with `BELOW_PANEL_MINIMUM`; the function neither sums the nulls as zero nor returns U1's counts as if they described the whole of A.

**Provenance and status.** Simulated; `observed` for a set of whole units, `inferred` for every area from `make_area` (C18, MTH-58). Caveats `estimate_not_footfall`, `movement_not_purchases`. A count is never a named place's footfall. It may appear only in a claim or component whose subject is `area`. **Compute cost.** Not separately timed.

**Limits and wording.** Movement is not purchases. The counts are simulated estimates with a range, not observations of people. Typical hourly weather profiles by season modulate the simulated counts, never a dated day's weather (document 05; C26).

- Allowed: "About {count} estimated people around this location at {hour} on a {day type} ({low} to {high}; Simulated), shown as workers, residents and visitors."
- Never say: "footfall of {building}", "visitors to {business}", "customers", "shoppers", "real-time".

| ID | Requirement |
|---|---|
| MTH-52 | C15 sets each count of a set of whole published units (a map unit or a release-unit candidate of C11) to the exact sum of the released unit counts, with the low and high as the sums of the unit lows and highs, one fact each for workers, residents and visitors, for one day type, hour and summer setting. A unit group (unit, day type, hour, summer) is complete only when its three segment rows have status `published`. The three counts are returned only when every unit has its complete group; otherwise all three are withheld with `BELOW_PANEL_MINIMUM`, no partial sum is returned and no null is summed as zero (PRV-58, DAT-138). Every area from `make_area` (drawn, radius, walk or drive) takes C18's apportioned counts over the units its exact outline overlaps and is `inferred`. The card never rescales, never divides by a mean over units, and never attributes a count to a named building, business or place. The two fixtures above (200, 80 and 50 with their ranges; and the withheld group) are the arithmetic tests. The three movement splits are separate outputs of the same card. A value below the minimum appears inside `other`; a kind that cannot pass is withheld whole with `BELOW_PANEL_MINIMUM`. A share is the count over the split's own total (the sum of the kind's published values with `other`), and the age output includes `other`. A split of an area is, per value, the sum of the published values of the area's snapped whole units; the units' `other` values sum into the area's `other`; a share is over the area's split total; the card says that `other` holds pooled values. A split is never apportioned to a drawn outline. Flow splits are released and reachable through the back end; no claim, card or screen shows them in this decision's sweep, C15 and the site answer included. Those of `flow_split` count person trips, with shares over the split's own total, and are never set as parts of the vehicle-trip flow estimate (PRV-134, DAT-169). Any display waits for the session on value extraction. |

## 5. Method cards added by decisions 0016 and 0017

[Decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) moves the former later cards C11, C12 and C13 into version 1 (item 18) and asks for the other methods below; [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) adds the public data several of them read. [Decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) adds C30 to C38 at the end of this section (items 2 to 22). Their models read the release tables that the five feeds fill (business register, employment, wages, residence and mobility), named by their contract names only: synthetic and simulated data fill them now, and nothing says that real records are used (item 15). Each card is a deterministic function in `eii_core.calc` (MTH-01). Its fixture is the arithmetic test, and the slice that builds it pins its data test (MTH-60).

### C11 Best-location ranking and rank stability

**Purpose.** Rank candidate areas for an activity on criteria the user can see and change, and state beside every rank how far it can move when the weights move (journey D2; decision 0016 item 5).

**Inputs.**

- Candidates of one kind: areas the user builds (pins with walk, drive or radius areas, or drawn shapes); the published release units of one partition inside a region the user draws; or, in public-only mode, the official zones or municipalities.
- For each candidate and criterion, one fact from the card that owns the criterion (for example C1, C6, C9, C12, C14, C15, C18, C19, C30, C31 or C33, or the zoning measure of C16). This card computes no criterion itself.
- The criteria form one closed list, versioned with the catalogue. Each entry names its criterion key, the card that owns it, its release table, its default direction and the candidate kinds it applies to, under MTH-65. Forecasts (C30), base rates (C31) and the site estimate (C33) may be entries, each visible with its value and weight and removable by the user ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 13). The zoning measure of C16 is an entry for the candidate kinds that MTH-119 names, with its default direction "higher ranks higher" ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 3). The list is fixed at slice S2 (open questions), and `area_ranking` ([08_BACKEND.md](08_BACKEND.md)) offers only its entries.
- For each criterion, a direction (higher or lower ranks higher) and a weight: the catalogue default or the user's typed input. The default weights are equal.
- The weight range `δ`, fixed at slice S2.

**Formula.**

```
candidates a with values x_ak for criteria k = 1 .. K
a candidate missing or withheld on a criterion of positive weight is not ranked;
  it is listed with its reason, never imputed and never given zero
normalise over the ranked candidates:
  higher ranks higher   z_ak = (x_ak - min_k) / (max_k - min_k)
  lower ranks higher    z_ak = (max_k - x_ak) / (max_k - min_k)
  max_k = min_k         the criterion cannot separate the candidates: it is shown with
                        "all candidates have the same value" and left out of the score
weights   u_k >= 0, at least one positive;   w_k = u_k / sum_k u_k
score     S_a = 100 * sum_k w_k * z_ak                        (0 to 100)
          S_a orders the candidates only: it is never emitted as a fact or shown (PRV-41, DES-175);
          the facts are each criterion's value, each weight, the rank and the stability bound
rank      r_a = 1 + the number of candidates b with S_b > S_a
          equal scores share a rank and are listed in candidate-id order
fewer than two ranked candidates: NO_DATA
arithmetic is exact (rational numbers from the decimal inputs), so ties never depend on the machine

rank stability of a, over the box of weights from w_k * (1 - δ) to w_k * (1 + δ), 0 < δ < 1:
  for each other candidate b, with d_k = z_bk - z_ak:
    hi_b = sum_k max( w_k * (1 - δ) * d_k , w_k * (1 + δ) * d_k )    b's largest lead over a
    lo_b = sum_k min( w_k * (1 - δ) * d_k , w_k * (1 + δ) * d_k )    b's smallest lead over a
  best rank   1 + the number of b with lo_b > 0      (b leads everywhere in the box)
  worst rank  1 + the number of b with hi_b > 0      (b leads somewhere in the box)
  for every weight setting in the box, the rank of a lies between best and worst, both included
leave-one-out, Source chain only: the rank of a with each criterion's weight set to zero in turn,
          on the same ranked candidates with the same min and max
```

The bound holds because a lead `S_b - S_a` is linear in the weights, so its smallest and largest values over the box sit at corners and equal the two sums above; rescaling the weights to sum to one does not change the sign of a lead. The bound may be wider than the ranks reachable inside the box; it is never narrower.

**Worked example (fixture, not a finding about a place).** Three candidates and two criteria, both "higher ranks higher", with weights 0.6 and 0.4.

| Candidate | x1 | x2 | z1 | z2 | Score | Rank |
|---|---|---|---|---|---|---|
| A | 10 | 40 | 0 | 1 | 40 | 2 |
| B | 20 | 10 | 0.5 | 0 | 30 | 3 |
| C | 30 | 25 | 1 | 0.5 | 80 | 1 |

With the fixture range `δ = 0.25` (not the v1 value), w1 runs from 0.45 to 0.75 and w2 from 0.30 to 0.50; leads are in weighted-sum units, before the factor 100. For A: C's lead has d = (1, −0.5) and lo = 0.45 − 0.25 = 0.20 > 0, so C leads everywhere; B's lead has d = (0.5, −1), hi = 0.375 − 0.30 = 0.075 > 0 and lo = 0.225 − 0.50 = −0.275, so B leads somewhere. A's rank stays between 2nd and 3rd, and 3rd is reached: at the corner (0.75, 0.30) the weighted sums are A 0.30, B 0.375 and C 0.90, so B leads A (after rescaling the weights to sum to one, the scores are about 28.6, 35.7 and 85.7). B's rank also stays between 2nd and 3rd. C's rank 1 does not change: A's largest lead over C is −0.45 + 0.25 = −0.20, and B's is −0.225 − 0.15 = −0.375. Leaving out criterion 2 ranks A 3rd; leaving out criterion 1 ranks A 1st.

**Research note (not a regression).** The methods research timed the former design, a Monte Carlo over Dirichlet weight draws: 1.0 s for 15,800 cells, 6 indicators and 5,000 weight draws. On random test inputs, the site ranked tenth stayed in the top ten in only 29% of draws: an illustration of the check, not a finding about Qatar. Version 1 uses the exact bound instead, so the sentence states a range of ranks, never a share of draws, which would read as a probability. References: OECD and JRC handbook (2008); Saisana, Saltelli and Tarantola (2005).

**Provenance and status.** The least-real class of the criteria facts (DAT-91); Public in public-only mode. Evidence status `inferred`, because the weights are the user's or defaults the user can change (MTH-06). Caveats `your_inputs`, `weights_judgement`, `ranking_not_advice`. **Compute cost.** One pass over the other candidates for each rank shown; not yet timed.

**Limits and wording.** A rank describes the stated criteria and weights, nothing else. Min–max scaling depends on the candidate set: adding or removing a candidate can change every score, and so every rank. Where a criterion is Synthetic or Simulated, the rank shows the format of a register-based ranking, not a finding about the areas; each criterion's class line says which.

- Allowed: "On the criteria and weights you set, this area ranks {rank} of {n}. With every weight moved by up to {δ} of its value, its rank stays between {best} and {worst}." When the two are equal: "... its rank does not change."
- Never say: "the best location", "you should choose", "recommended", "winner", "likely to succeed", "chance", "probability", "confidence", "demand here".

| ID | Requirement |
|---|---|
| MTH-45 | A rank is never shown without its stability sentence beside it, and weights are labelled a judgement. The sentence states the best and worst rank of the C11 bound for the box of weights within `δ` of the weights used (`δ` fixed at slice S2). It never states a share of draws, a probability or a confidence level. The one count of runs allowed is the "holds in X of N runs" sentence of C40, a count of model runs over the user's ranges, shown beside this bound and never as a percentage, a probability or a confidence level ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 5; MTH-115). |
| MTH-64 | C11 normalises, weights, scores and ranks as above in exact arithmetic and reproduces the fixture: scores 40, 30 and 80; ranks 2, 3 and 1; with `δ = 0.25`, A and B between 2nd and 3rd and C unchanged at 1st; A 3rd without criterion 2 and 1st without criterion 1. A candidate missing a criterion is listed as not ranked with its reason, a constant criterion is left out, and fewer than two ranked candidates return `NO_DATA`. The score orders the candidates only and is never emitted as a fact; leave-one-out keeps the same candidates and the same min and max. |
| MTH-65 | Candidates are of one kind, and each criterion is a fact for that candidate's own geography from the card that owns it. User-built areas take protected criteria only through the snap of MTH-56, and a count reaches a drawn shape only through C18. Release-unit candidates take only the released facts of their own partition's family and Public point counts inside each unit; no Public statistic and no apportioned value is put on a unit (PUB-29, MTH-75). Official zones and municipalities, in public-only mode, take Public criteria only and carry the Public class. A forecast (C30) or a base rate (C31) of a Public series ranks only candidates on that series' own geography, or enters as an apportioned count where C18 allows one; it enters by its value alone, and its interval or counts stand beside it and are not carried through the stability bound. A forecast of a released monthly series (C30) is a criterion only of the candidate whose series it is. The site estimate (C33), a forecast of a released monthly series, and any other criterion with a Simulated or Synthetic input are off in public-only mode. A rank that uses these criteria keeps its stability sentence, and leave-one-out shows which criteria move it. No Public split by sex or nationality is a criterion, the whole-cell sums of C38 included (PUB-90), and no list of register companies is ranked by a protected or Simulated figure other than the employee count shown on its cards, and never by a company's wages or another unreleased labour or residence value (PRV-125, MTH-71, [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)). |

### C12 Reachable-access score

**Purpose.** Show how much of a supply layer people can reach within a travel time, allowing for the other people who can reach the same supply, by hour where congestion changes travel time (journey D2; decision 0016 item 5).

**Inputs.**

- Demand locations `i` with weights `P_i`, from one layer: estimated residents present at a stated day type, hour and summer setting (C15, Simulated, at unit centroids), or the population grid `worldpop_qat_2020` at its own 100 m cells (Public, 2020; free flow only), once [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) lists that use. The grid is the only layer in public-only mode and a second layer beside the Simulated one in a protected release. No protected figure is a demand weight of this card (PRV-41): the people present by pay band of C32 are not a layer here, and the age-and-sex grid of C38 is never a demand weight.
- Supply points `j`, each with `S_j = 1`: Public points of one category from `pub_place`, or a reviewed list of gazetteer points.
- Travel times `t_ij` by drive or walk: at free flow (Public), or at an hour `h` from C25 (Simulated). The build writes the unit-to-unit times it uses to the manifest artefact `travel_time_matrix` (from unit, to unit, mode, and free flow or hour, in minutes: Public at free flow, Simulated by hour; [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) DAT-153). A supply point takes the time to the unit that contains it, so a supply point inside the demand location's own unit is at time 0. For the grid layer, `t_ij` is the free-flow time from the graph node of the mode nearest the cell's centre to the graph node of the mode nearest the supply point (ties: lower node id, as C25 loads units); these times are not stored.
- The cut-offs `t0` of each mode and the decay `f`, fixed at slice S2. The build stores a score for each cut-off, and `reachable_access` ([08_BACKEND.md](08_BACKEND.md)) takes one of them as a closed value, never a free number.

**Formula.** Two-step floating catchment (Luo and Wang 2003):

```
f(t) = 0 when t > t0; when t <= t0, f is the decay fixed at slice S2, with f(0) = 1, never increasing
step 1, each supply point j:   D_j = sum_i f(t_ij) * P_i, over every demand location i of the
                               layer in the frame, not only those of one area
                               R_j = S_j / D_j
                               D_j = 0: j is listed as "no one within reach" and left out
                               a supply point whose reach includes a withheld presence group
                               (f(t_ij) > 0 for that i): D_j is unknown, and every demand location
                               that reaches it gives BELOW_PANEL_MINIMUM (PRV-58)
step 2, each demand point i:   A_i = sum_j f(t_ij) * R_j, shown as 10,000 * A_i per 10,000 people
area score of an area X from make_area:
            S(X) = sum_i v_i * A_i / sum_i v_i over the demand locations i of X
            Simulated layer: every unit i that the exact outline of X overlaps, with v_i = w_i * P_i,
              where w_i = area(i ∩ X) / area(i) is the C18 area weight inside the unit
            grid layer: every grid cell whose centre lies in X, with v_i = P_i
            a demand location from which no supply point is within reach has A_i = 0 in either layer,
              and an area whose demand locations all have A_i = 0 has S(X) = 0
            sum_i v_i = 0: NO_DATA; a demand location of X with BELOW_PANEL_MINIMUM, or a unit of X
              whose presence group is withheld: the area score is BELOW_PANEL_MINIMUM, and no
              partial score is returned
check on every run: over the demand locations with a published group, sum_i P_i * A'_i equals
            the sum of S_j over the supply points with a known D_j > 0, where A'_i is step 2
            summed over those supply points only (A'_i = A_i when no group is withheld)
sums run in identifier order, so every run gives identical results
by hour: steps 1 and 2 are repeated with t_ij(h) from C25 for each hour shown
```

**Storage.** The build writes the score of every demand location of the Simulated layer, for each fixed supply layer and cut-off, at free flow and at each hour it computes, to the release table `access_score` (by demand unit, supply layer, mode, cut-off, presence key and traffic setting, with the score, its provenance, its status and its reason; [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) DAT-151); a withheld score is stored with status `withheld`, no score and `BELOW_PANEL_MINIMUM`, never as zero. The grid layer's scores, at free flow only, go to the Public release table `access_score_grid` (by grid cell, supply layer, mode and cut-off, with the cell's weight `P_i`, the score and its status; DAT-154), in both release kinds; every grid row is `published`, and a cell from which no supply point is within reach is stored with its true score 0, as `access_score` stores a unit in that case. The two layers' scores are separate facts and are never combined. An area score is computed at request time from those rows (MTH-02).

**Worked example (fixture, binary decay: f = 1 within `t0`).** Demand i1 holds 1,000 and i2 holds 3,000; supply points j1 and j2; `t0` is 10 minutes; times are 5 minutes from i1 to j1, 20 from i1 to j2, 8 from i2 to j1 and 9 from i2 to j2. Step 1: `R_j1 = 1 / 4,000 = 0.00025` and `R_j2 = 1 / 3,000`. Step 2: i1 has 2.5 per 10,000; i2 has 0.00025 + 0.000333... = 0.000583..., shown as 5.83 per 10,000. Check: 1,000 × 0.00025 + 3,000 × 0.000583... = 0.25 + 1.75 = 2, the two supply points. With both units wholly inside the area (`w = 1`), the area score over i1 and i2 is 2 / 4,000, shown as 5.0 per 10,000. At a fixture hour when i2 to j2 takes 12 minutes, j2 has no one within reach and is left out; i1 and i2 both have 2.5 per 10,000, and the check sums to 1. Withheld fixture: if the presence group of i2 is withheld, j1 and j2 both have i2 within reach, so both `D_j` are unknown; i1, which reaches j1, gives `BELOW_PANEL_MINIMUM`, and so does the area score, never a score from i1 alone. Grid fixture: with i1 and i2 as grid cells at free flow and a third cell i3 of 1,000 people that reaches neither supply point, the step 1 sums do not change (`D_j1` = 4,000 and `D_j2` = 3,000), i1 and i2 keep 2.5 and 5.83 per 10,000, and i3 has `A_i3` = 0, stored as the score 0. The area score over the three cells is (0.25 + 1.75 + 0) / 5,000 = 0.0004, shown as 4.0 per 10,000; over i3 alone it is 0 / 1,000 = 0; and over an area with no populated cell the weights sum to 0, so it is `NO_DATA`.

**Research note (validation test, outside every release).** Methods research: 777 district centres, 609 official landmark points used only as a test supply layer, a 10-minute drive and a Gaussian decay. The per-resident container ratio and the access score agreed only moderately across 75 zones (Spearman 0.47), and zone 69 fell from 3.40 to 0.66 per 10,000. Compute: 0.016 s once travel times exist; the national matrix runs at about 4,600 pairs per second per process. The district populations are Census 2020 figures with no stated licence (OI-04, closed for version 1 by decision 0017 item 10); this research example stays a validation test and never enters a release.

**Provenance and status.** The least-real class of the demand layer, the supply layer and the times: Public for the grid, Public points and free-flow times; Simulated with Simulated residents or any hour's times. Evidence status `observed`, and `inferred` for an area score of the Simulated layer, which uses C18 weights (MTH-58); caveats `calculated`, `access_not_use`.

**Limits and wording.** Access is the potential to reach, not use or demand. Every supply point counts once, whatever its size. The cut-off and the decay are choices, named in the Source chain. Free-flow times overstate reach.

- Allowed: "Within {t0} minutes' drive at {hour} (Simulated traffic), there are about {score} {category} places per 10,000 people, allowing for the other people who can reach the same places."
- Never say: "underserved", "gap in the market", "opportunity", "demand", "customers will come".

| ID | Requirement |
|---|---|
| MTH-46 | C12's research regression (zone 69 at 3.40 and 0.66 per 10,000; Spearman 0.47 across 75 zones) is re-derived with the decay form fixed at slice S2 and runs as a validation test outside every release. If it does not reproduce, MTH-04 applies. |
| MTH-66 | C12 computes the two steps above, with `D_j` over every demand location of the layer in the frame; lists and leaves out a supply point with no one within reach; returns `NO_DATA` (never zero) when a layer is missing; returns `BELOW_PANEL_MINIMUM` for every demand location that reaches a supply point whose reach includes a withheld presence group, and for an area score that draws on one (PRV-58); weights a Simulated layer's area score by C18's area weights over the units the outline overlaps; gives a demand location from which no supply point is within reach, in either layer, its true score 0; returns the area score 0, not `NO_DATA`, for an area whose demand locations all score 0, and `NO_DATA` for an area whose weights sum to 0; and reproduces the fixture: 2.5 and 5.83 per 10,000 and an area score of 5.0; at the fixture hour, 2.5 and 2.5; the withheld case; and the grid case (4.0 over the three cells, 0 over the third cell alone, `NO_DATA` with no populated cell). The check holds on every run. |
| MTH-67 | An hour's score uses C25's times for that hour and carries the Simulated class. A score is Public only when its demand layer, supply layer and times are all Public. No protected figure enters a demand weight or an access score (PRV-41). The one exception of PRV-126, the people present by pay band of C32, is read only by the site estimate of C33, never by this card. No drive time or drive-time area of the live traffic provider enters an access score (C25). |

### C13 Imports against local production

**Purpose.** Set what Qatar imports of an industry's products beside what the industry's public manufacturing tables list, as a screen (journey D7 and case C1; decision 0016 item 18).

**Inputs.** `pub_customs_import` (C5: value in QAR by tariff line, origin and month); `pub_manufacturing` (`mfg_industry`: one dataset per manufacturing industry, with rows by licence type, labour and cumulative licensed investment in QAR million, 2019 to 2025; and the main manufacturing products, 2016 to 2022); a committed, reviewed crosswalk from tariff lines to the manufacturing industries, each line with a reviewer and a review date. Certificates of origin and arriving vessels (`pub_trade_logistics`) stand beside the screen as separate Public context.

**Formula.**

```
industry i, latest 12 complete months in the release:
  M_i = sum of import value (QAR) over the tariff lines the crosswalk maps to i
  the origins with value > 0, the top origin's share and the HHI, by the C5 formulas
  lines the crosswalk does not map are counted and shown as "not mapped"
  a period covered only by the eight-digit table rolls finer lines up as in MTH-30
beside M_i, from the industry's manufacturing table for its latest year:
  the published counts by licence type, labour and cumulative licensed investment (QAR million)
no ratio, difference, share or gap is computed between M_i and a manufacturing figure:
  one is a flow of goods in riyals, the other counts licences and cumulative licensed investment
no unit value is computed: an industry mixes products (MTH-31)
```

**Worked example.** Fixture: tariff lines T1 and T2 map to industry i with 12-month values of QAR 300 and QAR 200; line T3, worth QAR 50, is not mapped. `M_i` is QAR 500, and the card shows one line not mapped, worth QAR 50. Illustrative note, not a passing regression: the methods research found 4 operating and 7 licensed factories in 2025 in the pharmaceutical manufacturing table. Slice S2 pins that pair from `manufacture-of-basic-pharmaceutical-products-and-pharmaceutical-preparations`, in the table's own licence-type terms. The research import figures for pharmaceuticals (3,380 million in 2023 against exports of 20 million) came from the commerce ministry's trade tables, which do not state their currency. Version 1 does not use those tables, so those figures are not a regression of this card.

**Provenance and status.** Public, `observed`, caveats `calculated`, `screen_not_opportunity`, `licence_not_capacity`, `editorial_crosswalk`. **Compute cost.** Light, as C5 (feasibility review; no time recorded).

**Limits and wording.** A licence is not production capacity, and cumulative licensed investment is not output. Import value is not demand. The crosswalk is an editorial choice.

- Allowed: "In the 12 months to {month}, Qatar imported products mapped to this industry worth {value}, from {n} origins. The industry's public manufacturing table lists {operating} operating and {licensed} licensed factories in {year}."
- Never say: "opportunity", "gap in local production", "import substitution potential", "unmet demand", "you should manufacture", "local factories can supply this".

| ID | Requirement |
|---|---|
| MTH-47 | C13 is worded as a screen, never as an opportunity or a recommendation. It shows import values only from the customs tables, in the riyals they state. The commerce ministry's trade tables, whose currency is not stated, are not used in v1, and a figure from them would show no currency label until its currency is confirmed. C13 joins no synthetic figure to a real import figure and computes no ratio, difference or share between an import value and a manufacturing figure. |
| MTH-68 | C13 maps tariff lines to industries only through the reviewed crosswalk, never by a code prefix; it counts and shows unmapped lines and computes no unit value. It reproduces the fixture (`M_i` = QAR 500, one line not mapped, worth QAR 50), and slice S2 pins the pharmaceutical pair from the manufacturing table. |

### C16 Reverse fit and fit lists

**Purpose.** Run the C11 functions with other candidates. The reverse fit ranks activities for one site, for property owners matching tenants to the business mix and the catchment's wage profile (journey D2; decision 0016 item 5). Fit lists order register companies, the real companies of the public business register and of the financial centre's public register, for the customer, partner and supplier finders (journeys D3 and D4; decision 0016 item 12, as [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) amends it: named synthetic firms are retired).

**Inputs, reverse fit.** A site: an `area`, drawn or built around a pin. Candidates: activities the user picks from the activity spine. Criteria come from this closed list, each computed for every activity:

- public places of the activity's category inside the site's exact shape (`pub_place`, counted by point-in-polygon, PUB-29; Public);
- the number of the activity's typical-neighbour categories kept by C6 that are found within 250 m of the site's pin or representative point (C6; Public); an activity for which C6 keeps no neighbour category has no value on this criterion;
- the activity's location quotient in the municipality of the site's pin (C1; Public);
- the share of the catchment's covered residents in the wage bands the user selects for that activity (the band partition of C19, on a snapped catchment; Synthetic);
- estimated people present at the hours the user selects for that activity (C15's unit counts apportioned to the site's outline by C18; Simulated);
- the zoning measure of the activity's use over the site's exact shape (below, MTH-119; Public; [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 3); an activity that the reviewed use mapping cannot match has no value on this criterion.

A site fact that is the same for every activity (for example the price of C14, the pipeline of C23, or the people present at one hour chosen for all activities) cannot separate the activities. It is shown beside the fit as context and takes no part in the score. The permitted height and setbacks of the zone that holds the site's pin or representative point, as `pub_zoning` publishes them, are such facts ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 3).

**Inputs, company fit lists.** Candidates: the register companies the release publishes in `register_company_list` for the search, each with its card fields from `pub_register_company` (every field the register publishes for it, person names excluded) and its employee count from its attached records ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) DAT-140; [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-125; [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)). Filters: the purpose the user chooses, from the one closed list that `register_companies` takes in [08_BACKEND.md](08_BACKEND.md) (`prospects`, `partners`, `suppliers` or `complementary`), each kept through the relation that the reviewed spine records between the user's activity and the activity on a company's card; and the size bands the user selects. The size-band filter's closed list is the bands of the exported parameter set, read from the release (manifest `parameter_set`): `s00_09`, `s10_49` and `s50_plus` under set A, `s00_49` and `s50_plus` under set B. Tested code places each company in a band by its released employee count; a company whose employee count is withheld (`CARRIED_FORWARD`, PRV-125) is in no band and is left out by a size-band filter. A filter selects whole bands only, and a band that the exported set does not hold, such as `no_payroll` or `s01_09`, is not offered. Criteria: the free-flow drive time from the area's pin or, for a drawn shape, its representative point (`eii_core.shapes`) to the drivable node nearest the centroid of the company's `registered_cell` (the C25 loading rule), which is Public; a company whose registered location resolves to no cell has no value on this criterion; and, if the user asks, the size band, which enters as its position among the bands of the exported set (`s00_09` < `s10_49` < `s50_plus` under set A; `s00_49` < `s50_plus` under set B), or the employee count itself, and the user's other typed criteria and weights over the card fields. No company's wages, wage bill or other unreleased labour or residence value, and no Protected or Simulated area figure, is a criterion, a filter or a tie-break.

**Formula.** C11's normalisation, score, rank, stability bound and leave-one-out, with the activities or register companies as candidates. The rank-stability sentence stands beside every fit rank (MTH-45).

**Worked example (fixtures).** C11's fixture with the candidates relabelled as activities gives the same scores, ranks and bounds. Adding a criterion with the same value for all three activities leaves the scores unchanged. Company list: companies F1, F2 and F3 of the invented stand-in register pass the filters with drive times of 12, 7 and 7 minutes. With that one criterion, lower ranking higher, the scores are 0, 100 and 100; F2 and F3 share rank 1 and are listed in key order, and F1 ranks 3rd. With one criterion, no weight change can move a rank.

**Provenance and status.** Reverse fit: the least-real class of the criteria used; `inferred`; caveats `your_inputs`, `weights_judgement`, `ranking_not_advice`, `fit_not_success`; subject `area`. Company lists: the least-real class of the criteria and filters used (Public for card fields and free-flow drive times; Synthetic once the employee count or a size band placed by it enters); `inferred`; caveats `your_inputs`, `weights_judgement`, `ranking_not_advice` (the caveat `firms_fictional` is withdrawn by [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md), since the companies are real); subject `register_company` for each record. **Compute cost.** As C11; not yet timed.

**Zoning and plots in site fit ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) items 3 and 12).** Two Public measures come from the national GIS centre's layers `pub_zoning`, `pub_parcel` and `pub_address_point` ([04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) PUB-105, PUB-108). Tested code in `eii_core.calc` computes both. Areas are geodesic areas on the WGS 84 ellipsoid, as in C18.

```
use u           the use of an activity, through the reviewed mapping of the activity spine to the
                use categories that pub_zoning publishes; an activity the mapping cannot match has
                no use, and no measure is computed for it
zoning measure  z(X, u) = (the area of the part of X inside zoning polygons that permit u)
                          / (the area of X)
                the area of the part of X that no zoning polygon covers is stated beside z
                no zoning polygon meets X: NO_DATA (reason no_zoning_cover)
empty parcel    in the public-data build, while the parcel number is still a join key (PUB-105,
                PUB-14): a parcel of gis_parcels is empty when no address point of gis_address
                carries its parcel number or lies inside its outline, and no building of the
                basemap (PUB-106) meets its outline; the build keeps the result with the parcel,
                with the dates of the layers it read
plot label      at request time, for each parcel whose representative point lies in the site's
                exact shape: "permitted by zoning and looks empty" when the parcel is empty and the
                zoning polygon that holds its representative point permits u (ASSUMPTION); every
                other parcel takes no label
no permit, approval, availability, vacancy or tenancy status is read, computed, stored or shown
```

Fixture (invented layers, not a place): a site's shape of 10 ha has 6 ha in a zone that permits retail, 3 ha in a zone that does not, and 1 ha that no zoning polygon covers, so z = 6 / 10 = 0.60 for retail, with the 1 ha not covered stated beside it; a shape that no zoning polygon meets returns `NO_DATA` with `no_zoning_cover`. Parcels P1 to P4 have their representative points in the shape, P1 to P3 in the retail zone and P4 in the other zone. P1 has no address point and no building, so it takes the label. P2 holds an address point, a building crosses P3, and P4's zone does not permit retail, so none of them takes it.

The zoning measure is Public and `observed` (MTH-05), with the caveat `calculated`. The plot label is Public and `inferred`, because "looks empty" reads the layers as they stood at their survey and retrieval dates, which it shows; it carries the caveat `plot_not_approved`, whose sentence is that of [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) section 12: "Permitted by zoning and looks empty; not shown as approved or available". Zoning says which uses are permitted; it is not a permit, an approval or availability. A parcel with no address point and no building may still be in use, for example as a yard or a car park, may have been built on since the layers' dates, and may not be for sale or rent. The use mapping is a reviewed judgement.

- Allowed: "This plot is permitted by zoning for {use} and looks empty in the public layers of {date}." The caveat `plot_not_approved` stands beside it. For the measure: "{share} of this area lies in zones that permit {use}; {area} of it has no zoning in the public layer."
- Never say: "approved plot", "plot available", "available land", "vacant", "for sale", "for rent", "buildable", "ready to build", "free land", or any other words that call a plot approved or available or give it a permit status.

**Limits and wording.** A fit says how an activity or a company scores on the stated criteria, not whether it would trade well. Wage bands describe covered residents' pay, not spending. The wage-band criterion is Synthetic and the presence criterion Simulated: a fit on them shows the format of a register-based fit, not a finding about the site; each criterion's class line says which. A company list orders real register companies on the stated criteria only: it is not a recommendation, a score of the company or a forecast of a deal, and it never uses a company's wages.

- Allowed: "Of the activities you listed, these score highest at this site on the criteria and weights you set; each rank shows its range." "These companies match the relation and size bands you chose; the nearest by free-flow drive time come first."
- Never say: "best tenant", "will succeed", "recommended tenant", "demand for", "should open", "contact this company", or the name of any real business in a fit list other than a listed register company, whose name comes only from its card.

| ID | Requirement |
|---|---|
| MTH-69 | C16 uses the C11 functions unchanged, with the stability sentence beside every fit rank, and reproduces its fixtures: C11's results for relabelled candidates; no change from a constant criterion; F2 and F3 at rank 1 and F1 at rank 3. |
| MTH-70 | A reverse-fit criterion must differ between activities; a site fact is context only. Wage-band and presence criteria enter only from the user's own selections and carry `your_inputs`. A wage-band share is computed by the band derivations of document 06, and a selection that cuts a merged band returns `SUPPRESSED` (PRV-32). |
| MTH-71 | A company fit list reads only a register company's card fields from `pub_register_company` and its employee count from `register_company_list` ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)); applies the purpose (`prospects`, `partners`, `suppliers` or `complementary`, through the reviewed relation to the activity on the company's card) and the user's size bands, whole bands of the exported parameter set only, into which tested code places each company by its released employee count, as filters; uses as criteria only the card fields, the employee count or its size band, free-flow drive times to the drivable node nearest the centroid of the company's `registered_cell`, which are Public, and the user's typed criteria and weights; ranks a size band by its position among the bands of the exported set; keeps the rank-stability sentence beside every rank (MTH-45); and holds only the companies the release publishes in `register_company_list` under PRV-125, a company whose employee count is withheld being in no size band. No company's wages, wage bill or other unreleased labour or residence value is read, and none orders the list or breaks a tie; no Protected or Simulated area figure is a criterion; and no other real business and no FDI project enters a fit list (MTH-57). |
| MTH-118 | C16 shows a plot only as "permitted by zoning and looks empty", decided by tested code from Public layers only ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) items 3 and 12; PUB-108). A parcel is empty only when the public-data build finds no address point of `gis_address` that carries its parcel number or lies inside its outline, and no building of the basemap (PUB-106) that meets its outline, while the parcel number is still a join key (PUB-105, PUB-14). At request time the label is given only to an empty parcel whose representative point lies in the site's exact shape and in a zoning polygon of `pub_zoning` that permits the use of the user's activity through the reviewed use mapping. The label is `inferred`, shows the layers' dates and carries `plot_not_approved`. No plot is worded, stored or shown as approved, available, vacant, for sale or for rent, and no permit, approval or availability status exists in any table. It reproduces the fixture (P1 labelled; P2, P3 and P4 not), and a planted "approved" or "available" label, in English or in Arabic, fails (TST-247). |
| MTH-119 | The zoning measure z(X, u) of C16 is the geodesic share of an area X that lies inside zoning polygons of `pub_zoning` permitting the use u of an activity, through the reviewed use mapping. The area of X that no zoning polygon covers stands beside it, and an area that no zoning polygon meets returns `NO_DATA` with `no_zoning_cover`. It is Public, `observed` and `calculated`, and is never worded as a permit, an approval or availability. It is a criterion of the reverse fit over the site's exact shape, and an entry of C11's closed criterion list ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 3) for areas the user builds and, in public-only mode, for official zones and municipalities, each over its own outline. It is never a criterion of release-unit candidates, because no Public value is put on a unit (MTH-65). It reproduces the fixture (0.60, with 1 ha not covered; `NO_DATA` with `no_zoning_cover`). |

### C17 Similar areas and three area types

**Purpose.** Find the official zones most like a reference area on stated Public features, and place each in one of at most three area types with its stability figures (journey D2; decision 0016 items 5 and 18).

**Inputs.** Candidates: the official zones of `zone`. Reference: a zone or a user's area. Features: a reviewed list of Public features, fixed at slice S2, each computed for a zone and for a drawn shape by the same definition (for example the density of public places by broad category from `pub_place`, counted by point-in-polygon). A feature published only on zones, such as electricity use (C9), is used only when the reference is a zone. No Synthetic, Simulated or protected figure and no Public split by sex or nationality is a feature, so no such figure is attached to a named zone.

**Formula.**

```
zones c and the reference r with features k = 1 .. K; a zone missing a feature is listed and left out
scale over the candidate zones: z_ck = (x_ck - min_k) / (max_k - min_k); the reference uses the same
  min and max, so its value may fall below 0 or above 1; a constant feature is left out
weights w_k: equal by default, or the user's typed inputs, normalised to sum to one
distance   d(c, r)^2 = sum_k w_k * (z_ck - z_rk)^2, shown as d rounded to two decimals
order      the smallest d^2 first; ties by zone code; the reference zone itself is left out of the order
stability  C11's bound with leads e_k = (z_ak - z_rk)^2 - (z_bk - z_rk)^2
           (zone b is closer than zone a exactly when sum_k w_k * e_k > 0)
types      built once per release: k-means with k = 3 on the scaled features of the candidate zones;
           k-means++ starts from a fixed seed, with a fixed number of restarts, and the run with the
           smallest within-type sum of squares is kept; types are numbered by their centre's first
           feature, then its second
stability  the mean silhouette over zones, and the mean adjusted Rand index between the full grouping
figures    and bootstrap re-groupings drawn with a fixed seed and number of draws; the types are shown
           only when both figures reach the thresholds fixed at slice S2
a user's area takes the type whose centre is nearest, with equal weights
```

**Storage.** The build writes each zone's type, from Public features only, to the release table `zone_type` ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) DAT-152): by zone, with the type's status, the version of the feature list, and the mean silhouette and mean adjusted Rand index of the release, equal on every row, so that the stability figures shown beside the types have a release table in their source chain (MTH-08).

**Worked example (fixture, not a finding about a place).** Zones Z1 to Z4 with features f1 = 1, 1, 5, 5 and f2 = 0, 4, 0, 8 scale to z1 = 0, 0, 1, 1 and z2 = 0, 0.5, 0, 1. With reference Z1 and equal weights, d² is 0.5 × 0.25 = 0.125 to Z2 (d = 0.35), 0.5 to Z3 (d = 0.71) and 1.0 to Z4 (d = 1.00), so the order is Z2, Z3, Z4. With the fixture range `δ = 0.25`, every position stays the same; for example, Z3's largest lead over Z2 is 0.375 × (−1) + 0.625 × 0.25 = −0.21875. The type step has a fixture of three well-separated groups of zones, which it must recover exactly.

**Research note (not a regression).** The methods research on census zones found three types moderately stable (silhouette 0.33; bootstrap adjusted Rand index 0.71) and five or six types not (0.56 and 0.51) (section 7). Those runs used Census 2020 zone layers with no stated licence (OI-04), so v1 recomputes the figures on its licensed features and does not reuse them.

**Provenance and status.** Public. Evidence status `inferred`, because the weights are defaults the user can change, as in C11; `your_inputs` is added when the user changed them. Caveats `calculated`, `weights_judgement`, `area_types_limit`, `similar_on_features_only`. **Compute cost.** Not yet timed; 91 zones keep it small.

**Limits and wording.** Alike on these features does not mean alike as a market. One extreme zone compresses the others' scaled values. Three types are the most the zones support (section 7).

- Allowed: "On the features listed, these zones are most like your area. Your area is type {n} of three; the stability of the types is in the Source chain."
- Never say: "the same market", "twin area", "will perform like", "proven area", or a type name that judges, such as "prime" or "poor".

| ID | Requirement |
|---|---|
| MTH-72 | C17 uses only Public features defined the same way for zones and drawn shapes (a zone-only feature only for a zone reference), orders by weighted squared distance with ties by zone code and the reference zone left out, sets C11's stability bound beside every position, and reproduces the fixture: Z2 0.35, Z3 0.71 and Z4 1.00, with every position unchanged at `δ = 0.25`. |
| MTH-73 | The C17 types come from one build-time k-means run with k = 3 on Public features only, whose seed, restarts and bootstrap draws are written in the release's method note; the types are written to the release table `zone_type`. The silhouette and the bootstrap adjusted Rand index are recomputed on the v1 features and shown with the types, and the three-group fixture is recovered exactly. |

### C18 Apportioning to a drawn shape

**Purpose.** Put a count published on an official geography, or a released Simulated count, onto the exact shape the user drew, as an estimate labelled Inferred beside the published figure (decision 0016 items 6 and 7; PUB-29).

**Inputs.** The count `x_g` of every official geography `g` the shape overlaps, found by polygon intersection (PUB-29); the geography polygons; the shape `S`; the weight below. For Simulated counts: the released unit counts of C15 with their lows and highs, and the unit polygons.

**The weight (fixed here; slice S2 confirms the grid).**

| Count | Weight |
|---|---|
| people living in the geography, as totals (for example population, labour force, employed or unemployed persons) | the population grid `worldpop_qat_2020` (CC BY 4.0, 2020), used only as relative weights inside each geography, never as a population total |
| another count on the reviewed list of apportionable counts (for example licences or building permits) | area |
| a released Simulated count of a release unit (C15) | area inside the unit |

Until slice S2 confirms the grid's file and licence for this use, counts of people are apportioned by area, and the card names that method. The population grid by age and sex (`worldpop_qat_agesex`) is not a weight of this card: its whole cells are summed over an area by C38, which splits no cell and is not apportioning.

**Formula.**

```
area weight         w_g = area(g ∩ S) / area(g)
population weight   w_g = G(g ∩ S) / G(g)
                    G(X) = sum over grid cells c of pop_c * area(c ∩ X) / area(c)
apportioned count   x_S = sum over g of w_g * x_g, rounded half-up to a whole number
Simulated counts    the same, with g the release units the shape overlaps; lows and highs take the
                    same weights; if an overlapped unit's group (unit, day type, hour, summer) is not
                    complete, that is its three segment rows do not all have status published (C15),
                    the shape's three counts are withheld with BELOW_PANEL_MINIMUM
area(g) = 0 or G(g) = 0 for an overlapped g: NO_DATA
areas are geodesic areas on the WGS 84 ellipsoid
the card lists each overlapped geography with its published count and its weight
```

A share, rate, mean, median, price or index is never apportioned: the card shows each overlapped geography's value with the lowest and highest, and blends nothing, as C8 does.

**Worked example (fixtures).** Area weights: G1 holds 1,000 over 100 km², of which 12.5 km² lie in the shape; G2 holds 600 over 20 km², of which 5 km² lie in it. `x_S` = 1,000 × 0.125 + 600 × 0.25 = 125 + 150 = 275. Population weights: G3 holds 20,000, and 1,000 of its grid population of 4,000 lie in the shape, so w = 0.25 and `x_S` = 5,000. Simulated: the shape covers half of unit U1 and a quarter of unit U2, with 120 workers in U1 (110 to 130) and 80 in U2 (72 to 88); the shape has 60 + 20 = 80 workers (73 to 87).

**Provenance and status.** The input's class: Public for a published count, Simulated for a C15 count (PUB-20, DAT-91). Evidence status `inferred`; caveat `apportioned_estimate`, naming the method (area, or the 2020 population grid) and the source geography. Subject `area`. **Compute cost.** Polygon intersections over the overlapped geographies; not yet timed.

**Limits and wording.** Area weighting assumes the count is spread evenly over its geography, which is rarely true. The grid describes 2020 and can miss later growth. A small shape in a large geography gets a small, uncertain share. The published figure on its own geography stays the fact; the apportioned figure is an estimate beside it.

- Allowed: "About {x_S} residents in your shape (estimated: the {year} figure for {geography}, apportioned by the 2020 population grid). The published figure for {geography} is {x_g}."
- Never say: "exactly", "counted in your area", "census of your area", or a tabulated sex or nationality split inside a shape (the whole-cell grid sums of C38 are their own card).

| ID | Requirement |
|---|---|
| MTH-74 | C18 apportions counts only, with the weight of the table above, and reproduces the fixtures: 275; 5,000; and 80 workers (73 to 87). A share, rate, mean, median, price or index is never apportioned; the overlapped geographies' values are shown with their lowest and highest. |
| MTH-75 | C18 never apportions a Public split by sex or nationality (a total over every category of such a split may be apportioned as a total) or a figure of the protected record types, which snap (MTH-56). A tabulated split is never put on a drawn shape; the one exception is C38, whose sums of whole cells of the population grid by age and sex over an area are not an apportionment and are not computed by C18 ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 22). It never writes an apportioned value to the release, to grid cells or to release units. Every apportioned figure is `inferred` and names its method and its source geography. |

### C19 Six income indicators and pay versus mix by month

**Purpose.** Compute the six income indicators of decision 0016 item 9. Indicators 1 to 5 describe covered earners in each month of the window. Indicator 6, wage trends by sector and area separated from changes in worker mix, has two branches. By area, it is the wage trend of the same earners between adjacent months, which keeps changes in worker mix out of it, released only for each municipality unit that contains units of the area and for the national unit (PRV-16, PRV-55; Synthetic), so it is shown per municipality and nationally. By sector, it is a Public national branch over the economic-activity rows of `pub_wage_table`, the public portal's wage series by economic activity: each activity's change between adjacent published years, and C3's split of the national change into pay change within sectors and change in the employment mix. Wage trends by sector come from that public series only, never from a protected split; national by sector is the finest sector view in version 1, so no sector trend is computed for an area or a municipality (owner's answer of 2026-11-12, decision 0016 item 9). [Decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) item 3 has pay by sector in journey D5 use the attached records of the register companies, with middle ranges; its geography and release rules are open (Open questions), and until [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) sets them no card computes it and this card is unchanged.

**Inputs.** Indicators 1 to 5 and indicator 6 by area, for a snapped area only (MTH-56): `resident_pay`, `worker_pay`, `occupation_pay` and `home_area_share` for each month of the one protected window (decision 0016 item 10), and the column `stayer_wage_index` of `month_change` for indicator 6; for indicator 4, the presence counts by hour of C15 for a set of whole units, or of C18 for an area from `make_area`. Every derivation follows section 6.2 of [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) (PRV-30 to PRV-32) and the home-family rule (MTH-55).

Indicator 6 by sector: the rows of the activity table `wage_act` in `pub_wage_table`, under its own `table_code` (workers in paid employment and monthly average wage by gender and economic activity, National Planning Council; national; 21 activity sections by sex; source years 2020 to 2023, as [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) section 2.2 records them): paid workers and mean monthly wage for each activity-by-sex cell and year. "Sector" here is the table's economic activity; the table by institutional sector (`wage_sector`) is not read, and no protected, Synthetic or Simulated figure is an input.

| No. | Indicator | Computed as |
|---|---|---|
| 1 | Average and median wage by residential area, where groups are large enough | mean = `wage_bill` / `earner_count` on the same `ALL` rows (MTH-55); median band from the band partition (PRV-31, PRV-32) |
| 2 | Wage bands and their spread | band shares and the quartile band range (PRV-32) |
| 3 | Covered wage bill and earner count | the primitives of the money and count partitions; per municipality, both from the money partition (below) |
| 4 | Residential income beside presence by time of day | indicators 1 to 3 for residents, beside the presence counts by hour (C15, or C18 for an area from `make_area`), as separate facts and charts; and, for a whole release unit only, the people present by pay band of C32 as a third, Inferred element (PRV-126) |
| 5 | Residence and workplace geography | for located jobs only (PRV-61): the work area's earners by home municipality from `home_area_share`, and the share living in a municipality other than that of their work unit |
| 6 | Wage trends by sector and area, separated from worker mix | by area: the fixed-composition index of the same earners between adjacent months (below; Synthetic); by sector: the Public national branch below, over the activity table of `pub_wage_table`: each activity's difference, ratio and direction between adjacent years, and C3's within-sector and employment-mix components of the national change; never for an area |

Indicators 1 to 3 are also shown per municipality and nationally, from the released rows of whole municipality and national units, which are exact sums over their published units ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-16), each labelled with that unit's own released area, and each statistic from exactly one partition (MTH-55); the mean, a ratio statistic, takes its wage bill and its earner count from the same stored `ALL` rows of the money partition and names both additive families in its fact lineage. Per municipality, where the count partitions have no unit, the mean, the wage bill and the one earner count displayed come from the `ALL` rows of the municipality unit of `rp_all_money` or `wp_all_money`, and the median band, the band shares and quartile bands, with the denominator of those shares, come from the municipality unit of `rp_all_quartile` or `wp_all_quartile`; that denominator is never displayed as a second earner count. Nationally, the mean and the wage bill come from the national unit of `rp_all_money` or `wp_all_money`, the bands from that of `rp_all_quartile` or `wp_all_quartile`, and the earner count from that of `rp_all_count` or `wp_all_count`. The average is never shown alone: a mean appears only with the median band, the band distribution and the earner count of the same area and month (decision 0016 item 9). Where the exported tier does not publish all four, the mean is not shown. Each area indicator is computed for every month of the window on the same unit set; a withheld month is a gap, never a zero, a change between months comes from C20, and the wage trend comes from the index below. Indicator 6 by sector follows the published years of its Public table, and its means stand only beside their paid-worker counts and the caveat of the public-data gap "pay percentiles or pay by area" ([04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) section 12, PUB-78), which states the reason no median or spread is shown: the public wage tables give national means only.

**Wage trend of the same earners (indicator 6, by area).** The fixed-composition index of PRV-55, released in `month_change` ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md), DAT-137).

```
in the release build (custodian plane), for one published month_change row of unit u, table
resident_pay or worker_pay, one measure and one pair of adjacent months (m - 1, m):
  index_u = 100 * B1_u / B0_u        100 times the exact ratio of the later bill to the earlier
                                     one; B0_u and B1_u: the treated wage bills of u's stayers
                                     (the same earners in both months) in months m - 1 and m
  rounded half-up to the nearest multiple of 0.5 by eii_core.calc and released as
  stayer_wage_index only on the published rows of money or quartile tier units at municipality
  level or coarser (unit_kind municipality, one unit per municipality in each of the four pay
  partitions, or national) that PRV-55 and DAT-137 allow; never by sector (wage trends by
  sector come from the Public branch below); B0_u and B1_u are never released
at request time (product plane), for each municipality unit of the money or quartile partition
of that table that contains units of the area's block, and for that partition's national unit
(the block's cell, merged and remainder units carry no index):
  change_u  = index_u - 100, in index points
  direction = higher, lower or equal, by the sign of change_u
  each unit's index and change are facts of their own, labelled with that unit's own released
    area, never as the area's own figure; no index is averaged, weighted or combined across
    units, and none is chained across pairs (the stayer wage bills that would weight them are
    not released)
  a row carried_forward: SUPPRESSED with CARRIED_FORWARD; a published row whose index is null:
    SUPPRESSED with DETAIL_NEEDS_LARGER_GROUP (document 03); never 0, never equal
home family: month_change, that table, partition and measure, breakdown cohort (MTH-55)
```

**Worked example (fixture, not a finding about a place).** U1, U2 and U3 are units at municipality level. Unit U1's stayers had wage bills of 2,000,000 in month 0 and 2,071,000 in month 1: 100 × 2,071,000 / 2,000,000 = 103.55, which lies 0.05 above 103.5 and 0.45 below 104.0, so the release holds 103.5; the change is 3.5 index points, direction higher. Unit U2's bills of 1,000,000 and 1,037,500 give 103.75, exactly half-way, which rounds up to 104.0; the change is 4.0. Unit U3's bills of 1,000,000 and 987,600 give 98.76, released as 99.0; the change is −1.0, direction lower. An area whose block has units inside both U1 and U2 shows the two pairs (103.5 and 104.0), each labelled with its own released area, never an average. If U2's row is carried forward, U2 shows `SUPPRESSED` with `CARRIED_FORWARD`, never 0, and U1 still shows 103.5.

**Wage trend by sector (indicator 6, Public national branch).** Computed in the release build, like C3 (MTH-02), with C3's function and the C20 comparison functions of `eii_core.calc`.

```
cells g: the activity-by-sex cells that the activity table populates in year t, with paid workers
  n_gt > 0 and a mean monthly wage w_gt; a both-sexes total row, where the table holds one, is
  not a cell; sex is a grouping inside the calculation only (MTH-24)
years: every pair of adjacent years (t - 1, t) that the fetched table holds (2020 to 2023: three
  pairs), and the span from its first to its latest year; no adjacent pair spans a missing year
activity a in year t, a total across sexes:
  N_at = sum of n_gt over the cells of a                     paid workers
  W_at = sum of n_gt * w_gt over the cells of a / N_at       mean monthly wage
each activity a and adjacent pair (t - 1, t), by the C20 comparison functions:
  difference = W_at - W_a(t-1), in riyals a month
  ratio      = W_at / W_a(t-1)
  direction  = higher, lower or equal
national split for each adjacent pair and for the span, by C3's function unchanged, with the
  cells g as its groups and s_gt = n_gt / the sum of n_gt over every cell of year t:
  mean_t   = sum_g s_gt * w_gt
  change   = mean_t - mean_(t-1)
  within   = sum_g  s̄_g * (w_gt - w_g(t-1))    within-sector component: pay change inside the groups
  mix      = sum_g  w̄_g * (s_gt - s_g(t-1))    employment-mix component: change in who is employed
  check    : within + mix == change (exact up to floating point)
a cell populated in only one of the two years compared (a pair or the span): that activity's
  facts and the national split for those two years are NO_DATA (reason
  cells_differ_between_years), never 0 and never equal; other activities keep their facts (MTH-09)
a list of activities is ordered by the C20 rule, computed in code (MTH-81)
```

**Worked example, sector branch (fixture, not a finding about a place).** Activity P has two cells: P1 with 100 paid workers at 10,000 a month in year 0 and 150 at 10,500 in year 1, and P2 with 100 at 6,000 and then 150 at 6,300. Activity Q has one cell, Q1, with 200 at 5,000 and then 100 at 5,100. P's mean is 1,600,000 / 200 = 8,000 in year 0 and 2,520,000 / 300 = 8,400 in year 1: difference 400, ratio 1.05, direction higher. Q's is 5,000 and then 5,100: difference 100, ratio 1.02, direction higher. The national mean is 2,600,000 / 400 = 6,500 and then 3,030,000 / 400 = 7,575, a change of 1,075. The cell shares move from 0.25, 0.25 and 0.5 to 0.375, 0.375 and 0.25, so within = 0.3125 × 500 + 0.3125 × 300 + 0.375 × 100 = 287.5 and mix = 10,250 × 0.125 + 6,150 × 0.125 + 5,050 × (−0.25) = 787.5, and 287.5 + 787.5 = 1,075. Pay inside every cell rose by 5% or less, yet the national mean rose by 16.5%, mostly because employment moved from Q to P. If P2 had no row in year 1, P's three facts and the national split for the pair would be `NO_DATA`, and Q's facts would stand.

**Regression, sector branch.** C3's worked example records the same split on the activity table for 2020 → 2023: QAR 572 of a change of QAR 673 (10,352 → 11,025, as C3's limits record the two means) came from mix. It is this branch's span regression, with C3's tolerance of ± QAR 1, and the slice that builds the branch pins it on the activity-by-sex cells from the release, with the latest pair's figures for every activity (MTH-60). If it does not reproduce, MTH-04 applies.

**Provenance and status.** Indicators 1 to 5 and indicator 6 by area: Synthetic, `observed`; caveats `synthetic_not_evidence_about_qatar` and `calculated`, with `synthetic_change` on every change between months, the index included. Subject `area`. The index is the method of `wage_trend_within_mix` in [09_AI_ASSISTANT.md](09_AI_ASSISTANT.md) and of the wage trend that `what_changed` returns in [08_BACKEND.md](08_BACKEND.md). Indicator 6 by sector: Public, `observed` (MTH-05); caveats `calculated`, `named_table` and `composition_not_wages`, as C3; subject `sector` for an activity's figures and `national` for the split, on the national geography; every figure names `wage_act`, its years and its retrieval date, and is a total across sexes. Like C3, the sector branch is not displayed until OI-03 is closed, because the activity table's national mean differs from the occupation table's (MTH-23, PUB-74): the card names its table on its face, and its Source chain shows the occupation table's mean for the same years with the line "the two published tables differ; this card uses the activity table" (MTH-22); the two tables' means are never shown side by side as the same measure (PUB-76). **Compute cost.** Area indicators: sums over released rows; not separately timed. Sector branch: one pass over at most 42 cells a year; not separately timed.

**Limits and wording.** The area figures describe covered earners and wages paid: not every household, not wealth, not spending power. The synthetic months show the format a linked wage feed would give; a change between them is a change in the synthetic world, not in Qatar. The index follows the earners present in both months, so joiners and leavers stay outside it, and a stayer's change of job or hours counts as pay change. The sector branch gives national survey means in nominal riyals for workers in paid employment aged 15 and over, not only covered earners, in the table's 21 activity sections, government and domestic work included, and its years end in 2023. An activity's own change includes any shift between the table's cells inside it; the separation from worker mix is the national split, which holds each cell's share of employment at its two-year average, so a change of mix inside a cell counts as pay change, as in C3. No figure of the sector branch is put on an area, a municipality or a drawn shape.

- Allowed: "In this area's synthetic records, the pay of the earners present in both {month 0} and {month 1} went {direction} by {change} index points; following the same earners keeps changes in who is employed out of this figure. These synthetic figures show the format." The direction and the change are returned facts.
- Allowed, sector branch: "In the published national table by economic activity, average monthly pay in {activity} went {direction} by {difference} between {year a} and {year b}, for {workers} paid workers in {year b}." "Across all activities, {within} of the change in average pay between {year a} and {year b} came from pay changes within sectors and {mix} from a change in the mix of paid employment."
- Never say: "spending power", "household income", "wealth", "rich area", "residents can afford", "real pay", or any sex or nationality split; for the sector branch also "everyone in {activity} got a raise", "the sector is booming", any figure without the table's name, or any sector figure for an area.

| ID | Requirement |
|---|---|
| MTH-76 | C19 computes indicators 1 to 5 and indicator 6 by area only from released tables of a snapped area, by the derivations of document 06, for every month of the window on one unit set, and shows an area mean only with the median band, band distribution and earner count of the same area and month. Indicators 1 to 3 are also computed per municipality and nationally, by the same derivations, labelled with that unit's own released area and under the same rule for a mean (PRV-16), each statistic from one partition only, the mean naming both additive families of its money-partition rows in its fact lineage (MTH-55): per municipality, the mean, the wage bill and the one earner count displayed from the `ALL` rows of the municipality unit of `rp_all_money` or `wp_all_money`, and the median band, the band shares and quartile bands, with the denominator of those shares, from the municipality unit of `rp_all_quartile` or `wp_all_quartile`, that denominator never displayed as a second earner count; nationally, the mean and the wage bill from the national unit of the money partition, the bands from that of the quartile partition and the earner count from that of `rp_all_count` or `wp_all_count`. Every other mapping fails its test in the matrix of TST-197, which asserts each statistic's partition in its fact lineage and, for the mean, both additive families. Indicator 6 by sector is the Public national branch of MTH-97, computed only from the activity table of `pub_wage_table`, the public portal's wage series by economic activity, and never for an area or a municipality; no sector trend is computed from protected tables, and national by sector is the finest sector view in version 1. C19's rows in the matrix of TST-197 are MTH-76, MTH-77, MTH-78, MTH-79 and MTH-97 (MTH-60). |
| MTH-77 | Indicator 4 sets resident pay beside presence counts as separate facts. No code multiplies, divides or otherwise combines pay with presence (section 6), with one exception (PRV-126): the people present by pay band of C32, a fixed function of published rows for a whole release unit, and the site estimate of C33, which reads that figure. Every other number that combines a protected value with a presence, flow or traffic value stays forbidden. |
| MTH-78 | Indicator 6 by area reads only `month_change.stayer_wage_index` of published `resident_pay` or `worker_pay` rows of `money` or `quartile` tier units at municipality level or coarser (`unit_kind` `municipality`, the municipality units of the four pay partitions, or `national`), so it is shown per municipality and nationally, and never by sector: wage trends by sector come only from MTH-97 (DAT-137, PRV-55). The release build computes that index as 100 times the exact ratio of the later stayer wage bill to the earlier one, rounded half-up to the nearest half point, and releases neither bill. The product returns the index, its change (the index minus 100) and its direction, one set of facts for each such unit that contains units of the area's block, labelled with that unit's own released area, and never averages, weights, combines or chains indices; the block's `cell`, `merged` and `remainder` units carry no index. A carried-forward row returns `SUPPRESSED` with `CARRIED_FORWARD`, and a null index on a published row `SUPPRESSED` with `DETAIL_NEEDS_LARGER_GROUP`, never zero or `equal`. It reproduces the fixture (103.5 and 3.5; 104.0 and 4.0; 99.0 and −1.0, direction lower; the carried-forward unit). No Kitagawa split is computed for an area; the split runs only on national Public tables: C3's occupation table and, for indicator 6 by sector, the activity table (MTH-97). |
| MTH-79 | No C19 card shows a Public split by sex or nationality, and no synthetic or protected figure of the worker, residence or company records carries one (PUB-90). Movement aggregates are the one exception (decision 0023 item 16) and they are not this card. |
| MTH-97 | Indicator 6 by sector reads only the rows of `wage_act` in `pub_wage_table`, national, in the release build. For every pair of adjacent years the table holds, it returns each activity's paid workers and mean monthly wage in both years, weighted by paid workers over the activity's populated activity-by-sex cells and totalled across sexes, with their difference, ratio and direction by the C20 comparison functions; and, by C3's function unchanged over the same cells, the national change with its within-sector and employment-mix components, asserting `within + mix == change`, for every adjacent pair and for the span from the first to the latest year. A cell populated in only one of the two years compared gives `NO_DATA` with `cells_differ_between_years` for that activity and for the national split of those years, never 0 or `equal`. Every figure is Public and `observed`, carries `calculated`, `named_table` and `composition_not_wages`, has subject `sector` or `national`, names `wage_act` and its years on the card face with the occupation table's mean in the Source chain (MTH-22), uses sex only as a grouping inside the calculation (MTH-24), shows a mean only beside its paid-worker count and the PUB-78 caveat that the public wage tables give national means only, is never put on an area, a municipality or a drawn shape, and is not displayed until OI-03 is closed (MTH-23, PUB-74). It reproduces the fixture (P 8,000 to 8,400: 400, 1.05, higher; Q 5,000 to 5,100: 100, 1.02, higher; national 6,500 to 7,575: change 1,075, within 287.5 and mix 787.5; the missing-cell case), and the slice that builds it pins the span 2020 → 2023 against C3's activity row (mix QAR 572 of 673). |

### C20 What changed between adjacent months

**Purpose.** Return what changed between two adjacent months. For the synthetic months of the window, the change is the published cohort components of `month_change` (DAT-137), never a difference of two monthly values (BE-115). For a Public series, and for two areas in one month, it is a set of comparison facts: difference, ratio and direction (DAT-134) (journey D6, service S2).

**Inputs.** Three cases, each with its own source.

- Synthetic months: the `month_change` rows of the area's units on one partition of the block's table (MTH-55), for each pair of adjacent months (m − 1, m) of the window, with their `status` (DAT-137).
- Public series: two values of one metric and unit on one official geography, the latest two adjacent periods of the series.
- Two areas in one month: one metric for two areas in the same month, each from its own snapped unit set and one family (MTH-55), or, for a Public figure, each on its own official geography.

**Formula.**

```
synthetic months, the units of area A on one partition, pair (m - 1, m):
  components  joiners, leavers and stayers of resident_pay and worker_pay only: each the exact
              sum of the published month_change components over the units of A (MTH-55)
  status only the month_change rows of occupation_pay, home_area_share and outlet_register are
              month marks with no component, so a pair of them returns its status only (DAT-137)
  no opening or closure is read from month_change: the openings and closures of register
              companies are the Public counts of C22 (DAT-164; decision 0023 item 12)
  any unit of A whose row for the pair is carried_forward, an empty cohort's row included
              (DAT-137): every component SUPPRESSED with CARRIED_FORWARD, never 0, never
              "no change", and no partial sum (BE-53, BE-115)
  month m - 1 or m withheld for A: SUPPRESSED with that month's reason
  no difference, ratio, net change or rate is computed from the components or from the two
              monthly values; the wage trend between the months is C19's index
  a span of several months returns each adjacent pair in turn, never one sum across pairs
Public series (periods p - 1 and p on one geography), or two areas a and b in one month:
  difference = x_p - x_(p-1)       (two areas: x_b - x_a), in the measure's unit
  ratio      = x_p / x_(p-1)       (two areas: x_b / x_a); NO_DATA when the denominator is 0
  direction  = higher, lower or equal
  a band figure returns its direction only
  either value missing: all three NO_DATA; either value withheld: all three SUPPRESSED with its
              reason; never 0, never equal
an area's list of changes is ordered by |ratio - 1|, largest first, then by metric key; changes
  with no ratio follow, by metric key, and month_change components by pair, earliest first, then
  by metric key
never across two releases or two seeds
```

**Worked example (fixtures).** Synthetic months: units U1 and U2 of an area, pair (m − 1, m). U1's `worker_pay` row is published with 12 joiners, 9 leavers and 140 stayers, and U2's with 5 joiners, 6 leavers and 80 stayers: the area has 17 joiners, 15 leavers and 220 stayers, and no difference is computed. If U2's row is carried forward, all three components are `SUPPRESSED` with `CARRIED_FORWARD`; the function returns neither 0 nor U1's components as the area's. Public series or two areas: 120 then 150 give difference 30, ratio 1.25 and direction higher; 0 then 4 give difference 4 and ratio `NO_DATA`. A missing value: all three `NO_DATA`; a withheld value: all three `SUPPRESSED`. Changes with ratios 1.25, 0.90 and 1.05 are listed in that order (0.25, 0.10 and 0.05 from 1).

**Provenance and status.** The compared facts' class; `observed`, or `inferred` when either compared fact is inferred (MTH-58); caveat `calculated`, with `synthetic_change` on every change between synthetic months. Subjects `area`, `municipality` or `national`. **Compute cost.** Trivial; not separately timed.

**Limits and wording.** A change between adjacent months includes the season (summer, Ramadan). Protected values are rounded, so a small change can come from the protection rather than from the records. A carried-forward pair means that a cohort did not pass the protection; it is not a month without change.

- Allowed: "Between {month a} and {month b}, in this area's synthetic records, {joiners} covered earners joined, {leavers} left and {stayers} stayed. These are synthetic months: the change is in the synthetic world, not in Qatar." For a Public series: "Between {period a} and {period b}, {metric} in {geography} went {direction} by {difference}."
- Never say: "trend" or "growth" for a single step, "decline in the market", "because", or "no change" or zero for a carried-forward pair.

| ID | Requirement |
|---|---|
| MTH-80 | C20 returns a change between synthetic months only from the `month_change` rows of the pair: the published joiners, leavers and stayers of `resident_pay` and `worker_pay`, summed over the area's units of one partition, never by subtracting two monthly values. The status-only rows of `occupation_pay`, `home_area_share` and `outlet_register` return their status only. No opening or closure is read from `month_change`: the openings and closures of register companies are the Public counts of C22 ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 12; DAT-137, DAT-164). A pair with any unit's row carried forward, an empty cohort's row included (DAT-137), returns `SUPPRESSED` with `CARRIED_FORWARD`, and a withheld month `SUPPRESSED` with its reason, never zero or `equal` (BE-53, BE-115). It returns difference, ratio and direction (DAT-134) only between two adjacent periods of one Public series on one geography, or between two areas in one month, each from its own unit set and one family; never across releases or seeds. It reproduces the fixtures, the carried-forward unit included. |
| MTH-81 | The order of a list of changes is the rule above, computed in code. A model never selects or orders changes by size ([AGENTS.md](../AGENTS.md) rule 17). |

### C21 Labour-market projections

**Purpose.** Extend a published or released labour-market series by a straight line over a stated window, marked as a projection with its method and period (decision 0016 item 11). A projection is never a revenue, demand or success forecast.

**Inputs.** One series from the reviewed list of projectable series, fixed at slice S2 with each series' window `n` and horizon `h`: a published series on its own geography (for example labour force, employed and unemployed persons by municipality from `pub_labour_sex_municipality`, or the wage table `pub_wage_table`), or a released monthly series of the window (Synthetic).

**Formula.**

```
values y_1 .. y_n over n consecutive periods, with no gap;  t = 1 .. n
b = sum_t (t - t̄)(y_t - ȳ) / sum_t (t - t̄)^2;   a = ȳ - b * t̄      (ordinary least squares)
projection for period n + k, k = 1 .. h:   ŷ = a + b * (n + k)
rules: n >= 3; h <= n; a monthly series uses whole years of months (n a multiple of 12);
       a count projected below zero returns NO_DATA (projection_below_zero)
       a released synthetic series is projected only when no adjacent pair of its window is
       carried forward for any of its units (month_change); otherwise SUPPRESSED with
       CARRIED_FORWARD, never a line through the repeated month
the chart shows the window's values, the line and the projection as a labelled dashed continuation;
no interval is drawn: a projection has no backtest from which a range could be measured
```

**Worked example (fixture).** y = 100, 103, 109, 111 and 117 for t = 1 to 5. Then ȳ = 108 and t̄ = 3; the cross-sum is 42 and the sum of squares 10, so b = 4.2 and a = 95.4. With h = 2, the projection is 120.6 for t = 6 and 124.8 for t = 7.

**Provenance and status.** The series' class; `inferred` (MTH-58); caveat `projection_not_forecast`; a Synthetic series also carries `synthetic_not_evidence_about_qatar` and `synthetic_change`; shown in the Inferred section only (AI-112). Subject: the series' subject. A projection of a Public split by sex or nationality stays on the source's own geography and categories and is never combined with another figure (PUB-90). **Compute cost.** Trivial; not separately timed.

**Limits and wording.** A straight line ignores turning points, policy changes and shocks; it only extends the stated window. A projection of a released synthetic series extends the synthetic world's months; it shows the format, not a trend in Qatar.

- Allowed: "If the straight-line trend of {series} over {window} continued, it would reach about {value} in {period}. This is arithmetic on past values, not a forecast." For a Synthetic series: "If the straight-line trend of this area's synthetic {series} over {window} continued, it would reach about {value} in {period}. These are synthetic months: this shows the format, not a trend in Qatar."
- Never say: "will reach", "forecast", "expected", "likely", "probability", "demand will grow", "the market will".

| ID | Requirement |
|---|---|
| MTH-82 | C21 fits the least-squares line on the stated window only, applies the rules above, draws no interval, labels every value a projection with its method and period, and reproduces the fixture (b = 4.2; 120.6 and 124.8). A released synthetic series with a carried-forward pair in its window, for any of its units, returns `SUPPRESSED` with `CARRIED_FORWARD`, and every Synthetic projection carries `synthetic_not_evidence_about_qatar` and `synthetic_change`. |
| MTH-83 | No projection is an input to another method: no ranking, fit, break-even or access score uses one. No projection is made of revenue, sales, demand, spending or success. Labour-market tightness stays theatre (section 6). A forecast of C30 is not a projection: it has a backtest and a measured error, and it may be a criterion of a ranking as [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 13 says (MTH-65). |

### C22 Openings and closures over time

**Purpose.** Show openings and closures over time on the map (journey D6; decision 0016 item 11): public licence issues and cancellations on their official geography, and the openings and closures of register companies by area and month, read from the register's own dates and monthly snapshots ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 12). No opening or closing month is generated; the synthetic births and closures of the earlier card are withdrawn.

**Inputs.** `pub_licence_issued` (`lic_issued`: incomplete, 610 codes, summing to 12,533; PUB-69, PUB-94) and `pub_licence_cancelled` with the C2 bulk-month flag, by municipality, activity and month. For register companies: `pub_register_company` (the registration date and, where a register file shows it, the cancellation date, with `registered_cell`) and, from the second kept monthly snapshot onward, `pub_register_snapshot` ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) DAT-164). The snapshot of a register file keeps `registered_cell` beside `registration_number`, `period` and `source_id`; it may be null where the location is unresolved. Both are read for the exact shape the user chose (MTH-56: a Public point layer).

**Formula.**

```
Public, municipality j, activity i, a stated span of months:
  issues(j, i, span)        = sum of the issued counts
  cancellations(j, i, span) = sum of the dated cancelled counts, with and without bulk months (C2)
  an activity code the issued series does not cover: NO_DATA
    (reason openings_not_published_for_activity), never zero
  the two series stand side by side; nothing subtracts one from the other (MTH-19)
Register companies, area A (the exact shape), month m, one route at a time.
  Membership on the snapshot route is compared by registration_number.
  An opening takes the entering month's location; a closure takes the preceding month's.
  dates route     openings(A, m) = the companies whose registered_cell on pub_register_company
                                   lies in A and whose registration date falls in m
                  closures(A, m) = the same with the cancellation date
                  wording: companies whose registration or cancellation date falls in the month
  snapshot route  openings(A, m) = companies present in the snapshot of m and absent from that of
                                   m - 1, whose entering month's registered_cell (the snapshot of m)
                                   lies in A
                  closures(A, m) = companies present in the snapshot of m - 1 and absent from that
                                   of m, whose preceding month's registered_cell (the snapshot of
                                   m - 1) lies in A
                  a company absent from both the later snapshot and pub_register_company still
                    counts as a closure when its earlier snapshot places it in A, from the
                    released tables alone
                  wording: newly present or no longer present between the named snapshots;
                    no registration or cancellation-date claim
                  either snapshot not kept: NO_DATA (reason snapshot_not_kept)
  a company of A with no date on the dates route is counted in no month, and the number of such
    companies in A stands beside the two counts; a company with a null registered_cell lies in no area
  each figure names its route; the two routes are never added together
  two counts, with no rate, no net change and no survival figure
```

On screen a Public licence figure is worded as licence issues or licence cancellations, as C2 requires. "Openings and closures" names the journey's view. A dates-route register figure is worded as companies whose registration or cancellation date falls in the month. A snapshot-route figure is worded as companies newly present or no longer present between the named snapshots, and it claims no registration or cancellation date. The entry and closure base rates of the Public licence series, each against the active stock and with its counts and period, are computed by C31 and shown on that card, and their forecasts by C30; this card shows the counts. No rate, net change or survival figure is computed from the register's openings and closures.

**Worked example.** Pinned check: the issued series sums to 12,533 over 610 codes and has no row for restaurants (5610101) (PUB-69). Fixture: issues of 3, 0 and 5 and dated cancellations of 2, 4 and 1 over three months give 8 issues and 7 cancellations, side by side; a code absent from the issued series returns `NO_DATA`, not 0. Register fixture, on the invented stand-in register (not a finding about a place): area A holds R1, registered in March of a fixture year; R2, registered in March and cancelled in September; and R3, which shows no date. The dates route gives 2 openings in March, 1 closure in September and 1 company without a date beside each month. Snapshot fixture: the snapshot of m − 1 holds R1 and R2 and that of m holds R2 and R5, all in A, so m has 1 opening (R5) and 1 closure (R1); with the snapshot of m − 1 not kept, both counts are `NO_DATA` with `snapshot_not_kept`. Separate regression, not part of that 1-and-1 count: a company absent from both the later snapshot and `pub_register_company`, whose earlier snapshot places it in the selected area, still counts as a closure of that area, from the released tables alone. Separate wording fixture: a company appears in a later snapshot and is absent from the earlier one, while its registration date is earlier than that later month or absent; the snapshot figure is worded as newly present between the named snapshots and claims no registration or cancellation month, and a planted snapshot sentence that claims one fails.

**Provenance and status.** Public licence series: Public, `observed`, caveats `calculated`, `licence_activity_not_firm`, and `openings_incomplete` on every issue figure. Register openings and closures: Public, `observed`, caveat `calculated`. The dates route also carries `register_dates_as_published`. The snapshot route does not: it is worded as companies newly present or no longer present between the named snapshots, with no registration or cancellation-date claim. Subjects `municipality` (licences) and `area` (register companies). **Compute cost.** Trivial (as C2).

**Limits and wording.** A licence issue is not a business opening, and a cancellation is not the end of trading; bulk months are administrative. A registration date is not the start of trading, and a cancellation date is not the end of it; a register file may not list companies already cancelled, so closures can be undercounted; monthly snapshots are kept from 2026-11, so the snapshot route has a short history. Snapshot results are companies newly present or no longer present between the named snapshots; they are not a claim that a registration or cancellation date falls in the month.

- Allowed, dates route: "In {month}, {n} companies of the public register in this area have that month as their registration date and {m} as their cancellation date; {k} companies here show no date."
- Allowed, snapshot route: "Between the snapshots of {earlier month} and {later month}, {n} companies of the public register are newly present in this area and {m} are no longer present."
- Allowed, licences: "In {span}, {municipality} recorded {n} licence issues and {m} licence cancellations for this activity. Issues are published for only part of the activities."
- Never say: "net formation", "the market grew", "N businesses opened", "survival rate", "closures" for licence cancellations, or a register count added to a licence count.

| ID | Requirement |
|---|---|
| MTH-84 | C22 shows Public licence issues only for the codes the issued series covers, each with `openings_incomplete`; returns `NO_DATA`, never zero, for other codes; keeps the C2 bulk-month flag on cancellations; never subtracts one series from the other; and reproduces the pinned sum (12,533 over 610 codes) and the fixture (8 and 7). |
| MTH-85 | Changed by [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 12: the synthetic births and closures are withdrawn, and no opening or closing month is generated. The openings and closures of register companies are Public counts over the exact shape, by the dates route or the snapshot route of DAT-164, each figure naming its route and the two never added together; a company with no date is counted in no month and the number of such companies stands beside the counts; the snapshot route returns `NO_DATA` with `snapshot_not_kept` while either snapshot is missing. No code computes a rate, a net change or a survival figure from them (section 6), and the register fixtures (2 openings in March, 1 closure in September and 1 company without a date; 1 opening and 1 closure by snapshot; `NO_DATA` without the earlier snapshot) are their arithmetic test. A separate regression counts as a closure a company absent from both the later snapshot and `pub_register_company` whose earlier snapshot places it in the selected area, from the released tables alone. A separate wording fixture is a company appearing in a later snapshot despite an earlier or absent registration date: the snapshot figure is worded as newly present between the named snapshots and claims no registration or cancellation month, and a planted snapshot sentence that claims one fails. |

### C23 Construction pipeline

**Purpose.** Show the building pipeline by municipality from building permits and completion certificates (journey D6 and the reverse view; decision 0017).

**Inputs.** `pub_building_permits` (`permits_muni`): monthly permits by type of permit for each municipality, 2016 to 2023 (Al Shahhaniya from 2017), and annual permits and completion certificates by municipality and type of building, 2021 to 2023. Municipality names pass the spelling map of PUB-27.

**Formula.**

```
monthly permits   P(j, type, m)
trailing sum      T(j, type, m) = sum of P over months m-11 .. m, only when all 12 are present
change            (T(m) - T(m-12)) / T(m-12); NO_DATA when T(m-12) is 0 or missing
annual permits and completion certificates by municipality and type of building, side by side
national          the sum of the eight municipalities, only when all eight are present for the period
nothing subtracts completions from permits, and no permit is counted as a start
```

**Worked example (fixture).** Twelve months of 10 permits and then twelve months of 12 give T = 120 and then 144, a change of (144 − 120) / 120 = 0.20. A municipality with a missing month in the window returns `NO_DATA` for that window. The 2023 totals by municipality are pinned from the source by the slice that builds this card (MTH-60).

**New households and workers by municipality ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 2).** The pipeline is turned into new households and workers only through a C30 forecast of the annual completion certificates by municipality and type of building, multiplied by stated Public averages (households per completed residential building, workers per completed non-residential building), each a Public fact with its source and year, shown beside the result. The forecast's value and both interval ends are multiplied by the same average. Nothing subtracts completions from permits, no permit is counted as a start, and no permit series enters the forecast. The annual series holds three points (2021 to 2023), fewer than the backtest minimum of C30, so this returns `NO_DATA` with reason `series_too_short` until the series is long enough; an average that the public data pack does not hold returns `NO_DATA` with its reason. The result is Inferred (C30) and carries `permit_not_start` and `forecast_backtest_range`.

**Provenance and status.** Public, `observed`, caveats `calculated`, `permit_not_start`. Subjects `municipality` or `national`. **Compute cost.** Trivial; not separately timed.

**Limits and wording.** A permit is an approval, not a start. A completion certificate is not linked to a permit in the data. The series end in 2023.

- Allowed: "In the 12 months to {month}, {municipality} issued {n} building permits of this type, {direction} the previous 12 months. In {year} it issued {c} completion certificates." For the forecast, once the series is long enough: "Forecast of completion certificates of this type in {municipality} for {year}: {value}, range {low} to {high}. At the published average of {average} households per completed building ({source}, {year}), that corresponds to about {households} new households, range {low} to {high}."
- Never say: "construction boom", "oversupply", "prices will fall", "units coming to market", "a pipeline of N homes".

| ID | Requirement |
|---|---|
| MTH-86 | C23 computes trailing sums only over complete 12-month windows, never subtracts completions from permits, sums municipalities to a national figure only when all eight are present, and reproduces the fixture (120, 144 and 0.20). New households and workers come only from a C30 forecast of the completion certificates times stated Public averages, each shown, and return `NO_DATA` with `series_too_short` while the annual series has three points. |

### C24 Employer scale and wage bill by activity

**Purpose.** Show how an activity's employees spread across establishment sizes, and the wage bill its survey publishes (journeys D1 and D3, service S1, cases C1 and C2; decision 0017).

**Inputs.** `pub_establishment_size`: from `est_size_act`, establishments and employees by size class and activity, national, one survey bulletin per sector, 2015 to 2022 (transport 2014 to 2019; business services, with compensation, 2015 to 2021); and, under its own `table_code`, the hotels and restaurants size table `sec_hr_size` (2018 to 2022), from which restaurants (ISIC 561) and the other hotel and restaurant activities are read ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) section 7.3). Slice S2 confirms that table's columns; if it gives restaurants no size class, the card returns `NO_DATA` for restaurants (MTH-09). The totals of `sec_hr_size` also enter `pub_sector_accounts`, which has no size-class column, for C4. A committed, reviewed crosswalk of size-class labels, because the labels differ between bulletins.

**Formula.**

```
activity i, year y, size class c as the bulletin labels it: E_ic establishments, L_ic employees
employee share of class c        L_ic / sum_c L_ic
establishment share of class c   E_ic / sum_c E_ic
employees per establishment      sum_c L_ic / sum_c E_ic
wage bill                        the compensation the table publishes, where it does
compensation per employee        compensation / employees, from one table, activity and year only
classes are compared across bulletins only through the reviewed crosswalk; a class it does not map
keeps its own label and is never split or merged by guess
```

**Worked example.** Fixture: four classes with 100, 40, 15 and 5 establishments and 200, 260, 330 and 1,210 employees give employee shares of 10%, 13%, 16.5% and 60.5%, and 2,000 employees in 160 establishments, 12.5 per establishment. Illustrative note: restaurants (ISIC 561) had 41,458 employees in 2,086 establishments in 2022 (C4), which is 19.87, shown as 19.9 employees per establishment. It becomes a regression of this card only if slice S2 finds both figures for restaurants in a bulletin of `pub_establishment_size`; if that bulletin publishes other figures, slice S2 pins those instead (MTH-60).

**Provenance and status.** Public, `observed`, caveats `calculated`, `establishment_survey`. Subjects `sector` or `national`. **Compute cost.** Trivial; not separately timed.

**Limits and wording.** National survey estimates. An establishment is a site, not a firm. Bulletins end in different years. Compensation is annual and nominal.

- Allowed: "In {year}, {share} of {activity}'s employees worked in establishments of {class} (national survey)."
- Never say: "market size", "customers", "demand", "large buyers here", or any area figure from this national table.

| ID | Requirement |
|---|---|
| MTH-87 | C24 computes shares and employees per establishment from one table, activity and year; computes compensation per employee only within one table; compares size classes only through the reviewed crosswalk; and reproduces the fixture (10%, 13%, 16.5% and 60.5%; 12.5). |

### C25 Traffic assignment and drive times by hour

**Purpose.** Build Simulated congestion by hour on the real road network, and the drive times and drive-time areas that follow from it (journeys D2 and D7; decision 0016 item 8). It is the simplest form the decision asks for: released hourly flows assigned to the road graph with one fixed volume-delay rule.

**Inputs.** The drive graph from `roads_osm` (ODbL; the graph is a build artefact); the free-flow speeds and link capacities by road class, fixed at slice S1 with their sources; the released hourly origin-destination flows between release units, in vehicle trips per hour (Simulated; document 03 names the table); the volume-delay parameters α and β and the speed floor s_min, fixed at slice S1 ([decision 0021](decisions/0021-one-speed-for-a-link-and-an-hour.md)). It never reads a feed row or a protected row.

**Formula.**

```
links l with length L_l (in whole metres, the length that the routing graph of the release holds for
          the link's edge; a length that is not whole is refused), free-flow speed s0_l (a whole number
          of km/h by road class, from s_min to 140), free-flow time t0_l = L_l / s0_l and capacity c_l
          (by road class); identifiers are compared as text, by code point
loading   a unit's trips start and end at the drivable node nearest its centroid by great-circle
          distance on a sphere of radius 6,371,008.8 m, the difference of latitudes taken exactly
          (ties: lower node id)
paths     one free-flow shortest path per origin and destination (ties: the lexicographically
          smallest node sequence, then the smallest sequence of link ids); trips within one unit are
          not assigned; a released flow between two units whose loading nodes have no directed path
          between them makes the assignment return NO_DATA, reason no_path, naming the pair
volumes   v_l(h) = sum of the released vehicle trips of hour h whose path uses l
          (all-or-nothing assignment)
delay     x_l(h) = s0_l / (1 + α * (v_l(h) / c_l)^β)            the one volume-delay rule, as a speed
speed     w_l(h) = max(s_min, round_half_up(x_l(h))), a whole number of km/h, never below the speed
          floor s_min; t_l(h) = L_l / w_l(h); a link without a row at hour h has w_l(h) = s0_l and
          t_l(h) = t0_l; w_l(h) and t_l(h) are the only speed and time of link l at hour h that anything
          shows or uses, and the routing graph of hour h carries w_l(h) (decision 0021)
speed ratio  w_l(h) / s0_l rounded half-up to three decimals (the released speed_ratio); the
          product reads the speed back as round_half_up(speed_ratio * s0_l), which is w_l(h) exactly
volume band: the volume-to-capacity ratio v_l(h) / c_l placed in the closed ordered list vb1 to
          vbK; each band holds its lower edge and not its upper edge, and the last band has no upper
          edge; K and the edges are fixed at slice S1 with α and β, written in the release's method
          note and never tuned (MTH-04)
drive time from point p at hour h: the routing engine's route over the routing graph of hour h,
          shown as the times t_l(h) of its links and one line "turns at junctions +N s": N is the
          engine's route time minus the exact sum of those link times, 0 when that difference is
          within 0.001 s for each link of the route (the engine prints times to the millisecond),
          otherwise rounded half-up to whole milliseconds; the total is the exact sum of the link
          times and N, so the parts add up; refused, never shown: a route whose engine time is below
          the sum of its link times by more than 0.001 s for each link, and a route of one link whose
          engine time differs from its link time by more than 0.001 s (it passes no junction); N
          holds everything the engine adds beyond the link times; the product computes no route of
          its own
situation: a drive time or drive-time area for a dial situation uses, on each link, the whole speed
          round_half_up(L_l / m_l) and the time L_l over that speed, where m_l is the arithmetic
          mean of t_l(h) over the hours that situation_windows gives the situation, on its day type
          and summer setting, as SYN-70 does for presence (a link without a row at an hour takes
          t0_l for that hour); the situation's routing graph carries those speeds
drive-time area (p, h, T): the routing engine's outline of the points within T minutes of p over the
          routing graph of hour h; it includes the engine's turn costs at junctions; protected
          figures snap it to whole release units (MTH-56), and Public and Simulated layers use the
          area itself; hours with the same speed w_l(h) on every link share one routing graph
          (SYN-53, decision 0021)
area slowdown at hour h for an area X (the traffic block of area_evidence):
          r(X, h) = sum_l len(l ∩ X) * r_l(h) / sum_l len(l ∩ X), over the road links inside X,
          where len(l ∩ X) is the geodesic length on the WGS 84 ellipsoid of the part of link l inside
          X and r_l(h) is its speed_ratio, or 1.000 where the link has no traffic_hourly row at that
          hour (free flow); rounded half-up to three decimals; no road link inside X: NO_DATA
gateway times (journey D7): the drive time from an area's pin to each gateway on a reviewed list of
          Public points (ports, the airport, free zones, land border crossings)
```

**Worked example (fixture, not a road in Qatar).** Nodes O, M and D. Link O→D is 10 km at a free-flow 60 km/h, so 10 minutes, with a capacity of 1,000 vehicles an hour. Links O→M and M→D are 6 km each at 60 km/h, 6 minutes each. The fixture rule has α = 1 and β = 2 (not the v1 values). At hour h, 500 vehicle trips go from O to D. The free-flow path is O→D (10 minutes against 12), so O→D carries 500 and O→M and M→D carry none. O→D then runs at 60 / (1 + (500 / 1,000)²) = 48 km/h, already a whole speed, and takes 12.5 minutes: a speed ratio of 0.8. The drive time from O to D at hour h is 12 minutes, through M; on the routing engine the route adds nothing at M (measured), so its line for turns at junctions reads +0 s. The assigned flow stays on O→D: the method does not move traffic to the quicker road, which is its main limit.

Further fixtures. Volume band: with fixture edges at 0.25 and 0.75 (not the v1 values), the ratio 500 / 1,000 = 0.5 on O→D lies in vb2. Situation: over a two-hour fixture window in which O→D takes 12.5 minutes in the first hour and has no row in the second (10 minutes), the mean is (12.5 + 10) / 2 = 11.25 minutes, 53.33 km/h on 10 km; the situation's speed on O→D is the whole speed 53 km/h, and its time 600 / 53 = 11.32 minutes (to two decimals). Area slowdown: an area holds 3 km of a link at a speed ratio of 0.750 and 1 km of a link with no row at that hour, so r = (3 × 0.750 + 1 × 1.000) / 4 = 3.25 / 4 = 0.8125, shown as 0.813. Speed floor: with a fixture floor of 10 km/h (also the v1 value) and 3,000 vehicle trips from O to D at an hour, the rule gives 60 / (1 + (3,000 / 1,000)²) = 6 km/h (100 minutes) on O→D; the floor makes it 10 km/h, 60 minutes and a speed ratio of 10 / 60 = 0.167; the volume-to-capacity ratio of 3 lies in the last band (vb3 with the fixture edges); and the drive time from O to D is 12 minutes, through M. Whole speed: a residential link (35 km/h at free flow) whose rule speed is 10.29 km/h runs at 10 km/h; its ratio is released as 10 / 35 = 0.286, from which round_half_up(0.286 × 35) = round_half_up(10.01) = 10 km/h is read back.

**Provenance and status.** With the default provider (`simulated`), link speeds, drive times and drive-time areas by hour: Simulated, `observed`, caveat `traffic_simulated`. Free-flow times: Public, `observed`. Gateway times: subject `area`, as the trip from the area, caveat `trip_from_area` (AI-118). **Compute cost.** Not yet timed on a real network: free-flow paths are found once for all hours, and each hour reloads the same paths; a release builds one routing graph for each distinct set of whole link speeds and one for each situation, which task S1-T11 timed only on synthetic fixtures (decision 0021).

**Road traffic and the movement source ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 12).** The road traffic of this card is kept as part of the movement source: it is the released hourly flows of that source assigned to the road graph by the rule above, and it adds no data of its own beyond the stated free-flow speeds, capacities and volume-delay parameters. OPEN (owner): the owner is asked to confirm that road traffic is part of the movement source; until he answers, the card stands as written.

**Live traffic provider ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 17; ARC-135).** The setting `EII_TRAFFIC_PROVIDER` is `simulated` by default, and everything above is the default. With `tomtom`, the key `TOMTOM_API_KEY` present and the presenter's offline control not set, the API process fetches live flow tiles and traffic-aware drive-time areas from the provider (`traffic_tomtom_flow`, `traffic_tomtom_range`) and passes them on; this card computes nothing from them. A live tile is a picture layer shown with the attribution "© TomTom" while the layer is on; no numeral is read from a tile, and no tile enters the assignment, the volume bands, the area slowdown, an access score (C12), a fit (C16) or a calibration (section 6). A traffic-aware drive-time area is an area of the session: it enters through the adapter as the second route beside the user's drawing, is bound to the session and seat like a drawn shape, and is marked with the provider and its retrieval time. It is session geometry with a provenance note (provider, request, retrieval time and response hash), not a fact; its minutes are the user's own request. Figures over it follow the rules of a drawn shape: protected figures snap to whole release units (MTH-56), Public and Simulated layers use the area itself, and each figure carries the least-real class of its own inputs. Nothing of a response is written to disk, to the release, to the ledger or to a log. With the provider on, a figure over a stored session area is repeatable for that area. No test, gate, command or the guided story needs the provider: its tests read hand-made fixtures in the documented response format. Caveat `live_traffic_provider`.

**Limits and wording.** Drivers do not move away from congestion in this method, so busy roads look slower, and parallel roads emptier, than they would. One rule covers every road class, and the capacities and free-flow speeds are assumptions. No link is shown slower than the speed floor, so the heaviest congestion is understated, and a link's speed is a whole number of kilometres per hour. Drive times and drive-time areas include the routing engine's turn costs at junctions: a route shows them as one line, and an area's legend says so once. The routing engine's own differences from the method were measured on the synthetic fixtures of task S1-T11 and each is pinned in a test with exactly this bound ([decision 0021](decisions/0021-one-speed-for-a-link-and-an-hour.md) item 9): a single link's engine time agrees with its time L_l / w_l(h) within 0.001 seconds; a route's engine time agrees with its itemised total within 0.001 seconds for each link; turn costs depend on the movement (on the spike's crossing, 0.017 seconds straight through, 2.105 seconds for one turn and 5.394 seconds for the opposite turn), and each pinned cost holds within 0.001 seconds or the engine is qualified again; at a turn, a node's entry into an area's outline moves by the difference of the two route times (the turn's cost less the straight-through cost) within 0.2 seconds (largest measured 0.151661 seconds); and a node of the fixtures enters a drive-time area's outline up to 40 seconds from its route time, because the engine draws the outline from a grid (largest measured 34.004 seconds; entries measured to within 0.01 seconds). The line of turns holds everything the engine adds beyond the link times: on the fixtures that is turn costs only, while on a real network the engine's costs at gates, tolls, ferries and border crossings would join it, and the slice S3 task that shows routes names or separates them. The spike routed between nodes only: how the end links of a route from a point inside a link (an area's pin, a gateway) are timed is fixed in writing by the slice S3 task that shows such routes, and the parts still add up. On the worked and the hourly fixtures the engine's route between any two nodes that have a path uses the links of the method's shortest path (not on the crossing, whose turn costs can choose another route); on the real road network that, and the size of every difference above, is not measured. The loading distance is checked against an independent, well-conditioned formula within 0.0000001 metres at loading distances, a check of its floating-point evaluation and not of the engine. Trips inside one unit stay off the network. With the default provider the flows are simulated, so the congestion is too.

- Allowed: "Simulated traffic: at {hour} on a {day type}, traffic on this road moves at about {ratio} of its free-flow speed." For an area: "Simulated traffic: at {hour} on a {day type}, traffic on the roads of this area moves at about {ratio} of free-flow speed, weighted by road length." "Drive time from this area to {gateway} at {hour}: about {minutes} minutes (Simulated traffic)." A route's breakdown: the time of each road link, then "turns at junctions +{seconds} s". On the legend of a drive-time area, once: "Includes turn costs at junctions." With the provider on: "Live traffic layer from the provider (© TomTom); no figure is read from it." "Drive-time area from the live provider, retrieved {time}; figures over it follow the rules of a drawn shape."
- Never say: "live traffic" or "real-time" of a Simulated figure, "measured congestion", "a traffic jam at {named place}", a congestion figure without the Simulated mark, or any figure read from a provider tile.

| ID | Requirement |
|---|---|
| MTH-88 | C25 reads only the released hourly flows and the Public road graph, never a feed row or a protected row (decision 0016 item 8). A release whose flows are not vehicle trips per hour returns `NO_DATA` with reason `flow_unit_not_vehicle_trips`. |
| MTH-89 | C25 uses one volume-delay rule for every link. α, β, the speed floor, the free-flow speeds, the capacities and the number and edges of the volume bands are fixed at slice S1 before any traffic is built, written in the release's method note and never tuned to match a published figure or a provider's tile (MTH-04). Tie rules are fixed, so every run gives identical results with the default provider. It reproduces the fixture: 12.5 minutes, 48 km/h and a ratio of 0.8 on O→D, and a 12-minute drive time through M; the volume-band fixture (vb2); and the floor fixture (3,000 trips: 10 km/h, 60 minutes, a ratio of 0.167, the last band, and 12 minutes through M). A link's speed at an hour is the whole speed of [decision 0021](decisions/0021-one-speed-for-a-link-and-an-hour.md), made by the method and never below the floor, and the product reads it back exactly from the released ratio. |
| MTH-90 | With the default provider (`simulated`), every link speed by hour, every hour-dependent drive time and drive-time area, and every figure computed on such an area carries the Simulated class (SYN-54). A traffic-aware drive-time area of the live provider is session geometry with a provenance note (provider, request, retrieval time and response hash), not a fact and not Simulated; a figure over it follows the rules of a drawn shape and carries the least-real class of its own inputs, and no numeral is read from a provider tile (ARC-135). A free-flow time is Public. A gateway time is a figure of the trip from the area, never the gateway's own (AI-118). A situation's link takes the speed of its length over the mean of the link's times over the situation's hours, rounded half-up to a whole km/h, and the time at that speed, and an area's slowdown is the length-weighted mean of the speed ratios of the road links inside its outline, with a link without a row at 1.000; both reproduce their fixtures (53 km/h and 600 / 53 minutes; 0.813). |

### C26 Seasonal calibration measure

**Purpose.** Measure the seasonal shape of the published museum visitor counts and of the simulated visitors, as each month's share of its year, so that the public shape can calibrate the simulator and the calibration fit F19 of [05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md) can confirm that it was applied ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 4; PUB-91). It is a calibration fit, never a hold-out.

**Inputs.** `pub_venue_visits` from `visits_museum`: monthly visitors by venue, 2013 to 2024, with venue names through the crosswalk of PUB-89. The simulated visitor presence of each month of 2025, from the cube's daily visitor values, as document 05 defines it for F19. The complete years of the public shape and the tolerance τ of F19, fixed at slice S1 (document 05).

**Formula.** One definition of the public shape, the parameter `mob.visitor_month_shape` of document 05:

```
for each complete year y (a value for each of its twelve months) and month m:
  share(m, y) = V(m, y) / the sum of V over the twelve months of y
public V(m, y): the visits of month m of year y, summed over venues after the crosswalk
public shape     P(m) = the mean over the complete years fixed at slice S1 of share(m, y);
                 this is mob.visitor_month_shape
simulated shape  Q(m) = the share of month m in the simulated visitor presence of 2025 (F19)
gap              D = the largest |Q(m) - P(m)| over the twelve months, shown in percentage points
test             pass when D <= τ, otherwise fail: a test-result fact
```

**Worked example (fixture).** Public: 100 visitors in every month, so each share is 1 / 12 = 0.0833. Simulated: 110 in January, 90 in February and 100 in every other month, 1,200 in all, so January is 0.0917 and February 0.0750. D = 10 / 1,200 = 0.0083, shown as 0.83 percentage point. The pass or fail against τ is a separate assertion.

**Hourly shape by place category ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 18).** The hour-of-day shape of simulated visits by place category is calibrated to the relative busyness of the named venues of that category (`busy_gmaps`, `pub_venue_busyness`; C37), pooled over the venues so that no venue's level or own shape enters a generator. The anchors of [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 4 keep their roles, and the health-centre series stays the annual cross-check of document 05.

```
for each place category g of the build-time venue list, and each day of week d that a day type of
document 05 covers:
  r_v(d, h)  the published relative index (0 to 100) of venue v of category g at hour h
  s_v(d, h)  = r_v(d, h) / the sum of r_v(d, ·) over the hours of d       the venue's level drops out
             a venue-day with any hour missing, or whose indices sum to 0, is left out
  H_g(d, h)  = the mean of s_v(d, h) over the venues of g kept for d       the pooled shape
             computed only when at least the minimum number of venues fixed at slice S1 is kept;
             otherwise the category keeps the default shape of document 05 for d, and no single
             venue's shape is used
simulated  Q_g(d, h) = the share of hour h in the simulated visits of category g on d
gap        D_g = the largest |Q_g(d, h) - H_g(d, h)| over the hours, in percentage points
test       pass when D_g <= the hourly tolerance fixed at slice S1 with τ: a calibration fit, never a hold-out
```

**Worked example, hourly shape (fixture, invented venues over a fixture day of three hours).** Venue V1 has indices 20, 40 and 40, which sum to 100, so its shares are 0.2, 0.4 and 0.4. Venue V2 has 10, 10 and 30, which sum to 50, so its shares are 0.2, 0.2 and 0.6; its lower level does not count. The pooled shape is (0.2 + 0.2) / 2 = 0.2, (0.4 + 0.2) / 2 = 0.3 and (0.4 + 0.6) / 2 = 0.5. A simulated shape of 0.25, 0.25 and 0.5 gives gaps of 0.05, 0.05 and 0, so D = 5 percentage points.

**Weather profiles ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 23).** The generator reads typical hourly weather profiles by season made from `weather_openmeteo` in the public cache, never a dated day. The constants of the modulation are manifest entries with ranges and a sweep (document 05), fixed with τ before any calibration run and never changed to pass (MTH-92). Both shapes above are measured after the modulation. How heat and the summer setting are kept from counting twice is stated by document 05; this card reads no weather value.

**Provenance and status.** P(m) and H_g: Public, `observed`, caveat `calculated`. Q(m) and Q_g: Simulated, `observed`. D, D_g and the test results are calibration checks shown in the Proof room, not facts about Qatar; caveat `seasonal_shape_only`, and `relative_busyness_not_people` on the hourly check. The health-centre series is annual and gives no monthly or hourly shape, so it is not used here. **Compute cost.** Trivial; not separately timed.

**Limits and wording.** The monthly check covers the monthly shape of visitors only: not hourly presence, not levels, not workers or residents, and not any named place. The hourly check covers only the hour-of-day shape of simulated visits by place category against the pooled shape it was set from: not levels, and not any named venue. Each public shape is the calibration input, so agreement with it is built in: the result shows that the calibration was applied and tests nothing independent (SYN-61, SYN-62). Museum visits stand for visiting in general only as a seasonal pattern, and the relative busyness of a category's named venues only as an hourly pattern.

- Allowed: "The simulated visitors' monthly pattern was set from published museum visitor counts. As a calibration fit against that same pattern, the largest monthly gap is {gap} percentage points against a fixed tolerance of {τ}: {result}. This shows that the calibration was applied; it is not an independent check." The result word comes from the test-result fact. For the hourly shape: "The simulated hour-of-day pattern of visits to {category} was set from the published relative busyness of {n} named venues of that category, pooled; no venue's level was used. As a calibration fit against that pooled pattern, the largest hourly gap is {gap} percentage points: {result}."
- Never say: "validated footfall", "accurate visitor numbers", "the museum's visitors" for a Simulated figure, "hold-out", "validated", "calibrated" of an hourly count or level, or the name of a venue beside a Simulated figure.

| ID | Requirement |
|---|---|
| MTH-91 | C26 computes the public shape once, as `mob.visitor_month_shape` of document 05 (each month's share of its year in visits summed over venues after the crosswalk, averaged over the complete years fixed at slice S1), the simulated shape of 2025 as F19 defines it, and the largest absolute gap between the two, and reproduces the fixture (D = 10 / 1,200). |
| MTH-92 | τ (the tolerance of F19) and the complete years are fixed at slice S1 before any calibration run and are never changed to pass (MTH-04). C26 is a calibration fit, never a hold-out: it is never called a validation or a check against independent data, and its result is rendered as pass or fail from the test-result fact, never as a fixed "within". No venue's level is transferred to a Simulated figure, and no Simulated figure is attached to a named place (decision 0017 item 4). The hour-of-day shape of simulated visits by place category is set only from the pooled shape H_g above, each venue's indices first divided by their own day's sum, and only when the minimum number of venues fixed at slice S1 is kept; no single venue's shape enters a generator. The hourly tolerance, that minimum and the weather constants are fixed at slice S1 before any calibration run and are never changed to pass. It reproduces the hourly fixture (pooled shape 0.2, 0.3 and 0.5; D = 5 percentage points) ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) items 18 and 23). |

### C27 Crowd density

**Purpose.** Show estimated people per square kilometre on the map and for an area, hour by hour (journey D2; decision 0016 item 7).

**Inputs.** The released presence counts of C15, with their lows and highs, for each published unit; C15's sums for a release unit or release-unit candidate, or C18's apportioned counts for every area from `make_area`; the unit or shape polygons and the municipal boundaries of the frame.

**Formula.**

```
density = count / area_km2, and the same for the low and the high,
          rounded half-up to whole people per square kilometre
area_km2  the geodesic area on the WGS 84 ellipsoid of the unit's cells clipped to the municipal
          boundaries of the frame (SYN-78), and for a shape, of the shape clipped the same way
map layer one value per published unit, segment, day type, hour and summer setting
all people workers + residents + visitors of one complete group, never a stored total
a release unit or release-unit candidate uses C15's sums; every area from make_area uses C18's
          apportioned counts
```

**Worked example (fixture).** A unit of 0.5 km² has 120 workers (110 to 130), 40 residents (35 to 45) and 30 visitors (25 to 35) at 13:00. That is 240 workers per km² (220 to 260). All people number 190 (170 to 210), so 380 per km² (340 to 420).

**Provenance and status.** Simulated; `observed` for whole units, `inferred` for every area from `make_area`. Caveats `estimate_not_footfall`, `density_estimated`. Subject `area`. **Compute cost.** Trivial; not separately timed.

**Limits and wording.** The denominator includes empty land inside the unit, so a large unit shows a lower density than its busiest part. Units differ in size, and the legend says so.

- Allowed: "About {density} estimated people per square kilometre around this location at {hour} (Simulated)."
- Never say: "crowded venue", "busy mall", "footfall of {building}", "unsafe crowd", or a density for a named building or business.

| ID | Requirement |
|---|---|
| MTH-93 | C27 divides released counts, their lows and their highs by the geodesic area in square kilometres of the unit's cells, or of the shape, clipped to the municipal boundaries of the frame (SYN-78). A release unit or release-unit candidate uses C15's sums and is `observed`; every area from `make_area` uses C18's apportioned counts and is `inferred`. It reproduces the fixture: 240 (220 to 260), and for all people 380 (340 to 420). |
| MTH-94 | The all-people density adds the three segments of one complete group and never reads a stored total. It is computed only if document 05 defines the three segments as exclusive for each hour; otherwise only the three segment densities are shown. Its wording is "estimated people per square kilometre around this location", never a named building's or business's crowd or footfall. |

### C28 Announced investment projects

**Purpose.** Count the announced projects of the FDI projects dashboard, and sum their announced capex and jobs, by sector, source country, year and stated location (journeys D1, D4, D6 and D7, services S1 and S2; decision 0017 item 6).

**Inputs.** `fdi_projects`: one record per announced project, with every field as published, and capex in the currency and unit the page states (PUB-87).

**Formula.**

```
count of projects by sector, source country, announcement year and, where the page states one, location
announced capex and announced jobs summed over the same keys, in the page's currency and unit
announced capex is summed only over projects with the same capex_unit; a group holding several
  units returns one sum per unit with its project count, never a converted total
a project with no stated capex or jobs is still counted, and each sum states how many projects it covers
no figure is computed for one company, and no filter or search runs on a company name
```

**Worked example (fixture).** Three projects in one sector and year, with capex of 10, none stated and 30 in one unit, and jobs of 5, 7 and none stated: the count is 3; capex is 40 from 2 of the 3 projects; jobs are 12 from 2 of the 3. Second fixture: in one group, two projects state capex of 10 and 30 in one unit and a third states 5 in another unit; the group returns two capex sums, 40 from 2 projects in the first unit and 5 from 1 project in the second, never one total.

**Provenance and status.** Public, `observed`, caveats `calculated` and `fdi_estimates` beside every count, capex or jobs figure. Subjects `national`, `municipality` or `sector` for counts; `fdi_project` for one project, with Public slots only. **Compute cost.** Trivial; not separately timed.

**Limits and wording.** The projects are announcements, not realised investment. Capex and jobs are the source's estimates of publicly announced projects; the dashboard does not capture every project, and its data is subject to change.

- Allowed: "{n} announced projects in {sector} in {year} (FDI projects dashboard, data from fDi Markets; capex and jobs are the source's estimates of publicly announced projects, and the dashboard does not capture every project)."
- Never say: "invested", "jobs created", "realised", "{company} invested", "top investors", "investors are flocking".

| ID | Requirement |
|---|---|
| MTH-95 | C28 counts and sums `fdi_projects` records only by sector, source country, year and stated location; sums capex only within one `capex_unit`, returning one sum per unit and never a converted total; states how many records each sum covers; computes no figure for one company and offers no company filter (AI-110); keeps `fdi_estimates` beside every capex or jobs figure; joins no synthetic figure; and reproduces the fixtures (3; 40 from 2 of 3; 12 from 2 of 3; and the two capex sums of the second fixture, 40 and 5). |

### C29 Sums over a case sample file

**Purpose.** Compute the facts that cases C3 and C4 take from the company's own sample file: a distributor's delivery records and a retail chain's branch sales (decision 0016 item 4).

**Inputs.** The rows of a sample file loaded in the session: Synthetic, standing for the company's own records (AI-116).

**Formula.**

```
counts and sums of the file's rows by the file's own keys (branch, delivery area, month)
shares within the file (for example each area's share of deliveries)
a branch's change between two months of the file: difference, ratio and direction by the C20
  comparison functions (the file is the company's own records, not months of the release)
a branch against the median branch of the file in the same month: difference and direction;
  an even number of branches takes the mean of the two middle values, as C14
case C3 access, at free flow only, so that the facts stay Synthetic:
  depots d    each depot of the file and, when one is given, the candidate depot the user placed
              (its pin's base cell)
  t(d, c)     the free-flow drive time of C25 from the drivable node nearest the centre of d's cell
              to the drivable node nearest the centre of customer cell c (ties: lower node id)
  units within T of d = the sum of the file's units whose customer cell c has t(d, c) <= T,
              for T one of the drive cut-offs of make_area (5, 10 or 15 minutes)
  share within T of d = that sum / the sum of all the file's units
  a customer cell with no route from d: d's two figures return NO_DATA, and the cell is listed
  times by hour are shown by the depots' drive areas of make_area, never inside these figures
area facts (C15, C19, C20, C22) stand beside these as separate facts, never divided or multiplied by them
```

**Worked example (fixtures).** Branches B1, B2 and B3 sold 90, 120 and 100 in one month. The median branch sold 100, so B1 is 10 below it (direction lower). With a fourth branch B4 that sold 110, the two middle values are 100 and 110, so the median is 105 and B1 is 15 below it. Access: customer cells c1, c2 and c3 hold 30, 50 and 20 of the file's 100 units; free-flow times are 4, 12 and 8 minutes from depot D1 and 14, 6 and 9 minutes from depot D2. Within 10 minutes, D1 reaches c1 and c3, 50 units or 0.50 of the file, and D2 reaches c2 and c3, 70 units or 0.70.

**Provenance and status.** Synthetic (the file; the free-flow times are Public, so the least-real class is Synthetic), `inferred`, caveats `your_inputs` and `sample_file`. Subject `area`: the area the records describe. Never written to the release, the store or the ledger (MTH-06; AI-116). **Compute cost.** Trivial; not separately timed.

**Limits and wording.** The sample file is synthetic and stands for a company's own records. A difference between a branch and its area is not a cause. Free-flow times overstate reach at busy hours; the drive areas by hour show the difference.

- Allowed: "In your file, branch {b} sold {difference} {direction} the middle branch in {month}. Beside it, this area's estimated people and covered pay changed as shown." The direction comes from the returned direction fact. For case C3: "Within {T} minutes' free-flow drive of depot {d}, your file holds {units} delivered units, {share} of the file."
- Never say: "capture rate" (allowed only as the name of the user's input in C35), "share of footfall", "sales per visitor", "the area is the problem", "the branch is the problem", "will improve".

| ID | Requirement |
|---|---|
| MTH-96 | C29 computes only counts, sums, shares within the file, C20 comparison facts between two months of the file, differences from the median branch (the mean of the two middle values for an even number of branches) and, for case C3, the units and the share of the file within a free-flow drive cut-off of each depot. No code divides or multiplies a sample-file figure by presence, footfall, earner counts or pay (section 6). Its facts carry `your_inputs` and the Synthetic class, are never written to the release, store or ledger, and reproduce the fixtures (median 100 and B1 10 below; median 105 and B1 15 below; 50 units and 0.50 for D1, 70 units and 0.70 for D2). |

### C30 Forecasts of published series

**Purpose.** Forecast each series of a closed, versioned list of published series (Public series, and the released monthly statistics of the custodian-type feeds) with a model that the series' own backtest chooses, and show every forecast with its interval from the backtest, its measured backtest error, its method and its source ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) items 2 to 6).

**Inputs.**

- One series of the closed, versioned list of forecastable series, with its source table, its geography (the source's own), its period (month, quarter or year) and its horizon `h`. The first list is that of decision 0019 item 2: licence issues and licence cancellations by activity and by the source's own area (`pub_licence_issued`, only for the codes it covers, and `pub_licence_cancelled`, with the bulk months of C2 flagged); property prices by district (the medians of C14, each with its deal count); hotel demand and room rates; consumer and producer prices; imports by product (`pub_customs_import`, on basket lines of eight digits or finer, MTH-30 and MTH-31); announced investment by sector (the project counts and announced capex of C28); and the construction pipeline, through the annual completion certificates by municipality (C23). [Decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 8 adds one Public series: the quarterly median price per square foot of C41 by district and use (m = 4), each quarter with its deal count. It is a series of its own unit and period, beside the annual medians per square metre of C14 and never joined to them. A Public series is forecast only when the public data pack holds its source table; a named series without one is listed there as open and returns `NO_DATA`. On screen the licence series keep their names, licence issues and licence cancellations (PUB-94), and no net series is formed from them.
- The released monthly series of the window, on the same list ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 6): pay level, earner count and wage bill, the stayer index at municipality level, and employment by area, each read from the released rows of its own unit set and partition as C19 and C21 read them (MTH-55, MTH-56). Under [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 12 the establishments of an area by month are register companies by their own dates, a Public count of DAT-164 rather than a released synthetic series (ARC-138); whether their forecast joins the closed list as a Public series is fixed with the list at the slice that builds the card (Open questions). Such a forecast is a fixed function of rows that are already released, so it reveals nothing that those rows do not; it is a labelled projection from the released months, not a protected statistic of a later month (PRV-54), and it states no change between two months (ARC-130). Its origin is the last released month. A series with a carried-forward month in its window, for any of its units, is not forecast and returns `SUPPRESSED` with `CARRIED_FORWARD`, as C21 rules for projections. A request for a protected statistic of a month outside the window, or for a series across windows, is still refused (PRV-54).
- The closed, versioned list of candidate models. ASSUMPTION, confirmed at the slice that builds the card: seasonal naive, drift and simple exponential smoothing; a longer list needs a library pin.
- The error measure, the backtest minimum and the interval rule below, each an ASSUMPTION confirmed at the same slice.

**Formula.**

```
series     y_1 .. y_n: the longest run of consecutive periods with a published value, on one geography
           and in one unit, ending at the latest period; a period before a gap is not used
           season length m = 12 for a monthly series, 4 for a quarterly one, 1 for an annual one
candidates (the closed list; ASSUMPTION), each fitted on y_1 .. y_o only, forecasting y_(o+k), k = 1 .. h:
  seasonal naive   ŷ(o+k | o) = y_(o+k-m*ceil(k/m))              with m = 1, the last value
  drift            ŷ(o+k | o) = y_o + k * (y_o - y_1) / (o - 1)
  simple exponential smoothing
                   level l_1 = y_1;  l_t = α * y_t + (1 - α) * l_(t-1);  ŷ(o+k | o) = l_o
                   α from the grid 0.1, 0.2 .. 0.9 with the smallest sum of squared one-step errors
                   (y_t - l_(t-1)) over t = 2 .. o; ties: the smaller α
backtest   rolling origin: origins o = L, L + 1 .. n - h, with L = max(2h, m + 1) periods of history at
           the first origin; at each origin every candidate forecasts the next h periods
           errors e_c(o, k) = y_(o+k) - ŷ_c(o+k | o)
minimum    at least three origins (n - h - L + 1 >= 3) and at least twice the horizon of history at the
           first origin (L >= 2h) (ASSUMPTION); otherwise NO_DATA with reason series_too_short, never a
           model without a backtest
error      the mean absolute scaled error, one fixed measure (ASSUMPTION):
           q = the mean of |y_t - y_(t-m)| over t = m + 1 .. n, one scale for every candidate
           MASE_c = the mean of |e_c(o, k)| over every origin and horizon, divided by q
           q = 0: the same mean, unscaled, in the series' unit
selection  the candidate with the smallest MASE_c; ties: the earlier candidate in the closed list;
           no person and no language model chooses a model
forecast   the chosen candidate refitted on y_1 .. y_n: ŷ(n+k), k = 1 .. h
interval   at each horizon k, from the chosen candidate's own backtest errors at k (ASSUMPTION):
             low  = ŷ(n+k) + the smallest e(o, k)
             high = ŷ(n+k) + the largest e(o, k)
caption    y = the number of backtest values at k; x = how many of them lie inside the range that the
           other y - 1 errors give around their own backtest forecast: the value at origin o counts
           when the smallest e(o', k) <= e(o, k) <= the largest e(o', k), taken over the origins o'
           other than o; no value is checked against a range built with its own error, so x is
           measured and can be smaller than y; both are Fact chips
a series that cannot be negative: a point forecast below zero returns NO_DATA (reason
           forecast_below_zero); an interval end below zero is shown as zero and marked
a released monthly series (Synthetic): the origin is the last released month of the window; a month of
           the window carried forward for any unit of the series: SUPPRESSED with CARRIED_FORWARD,
           never a model through the repeated month
each forecast's lineage names the method and version and the series; the model and the horizon
           identify the fact, and the interval ends, the backtest error and the number of backtest
           points are facts of the same computation, shown with it
each forecast is computed at request time from release tables and is never written to the release
```

**Worked example (fixture, not a series about a place).** An annual series (m = 1) of five values, 10, 12, 11, 13 and 14, with h = 1, and a fixture list of two candidates, seasonal naive (with m = 1, the last value) and drift. L = max(2, 2) = 2, so the origins are 2, 3 and 4: three origins, the minimum. Seasonal naive forecasts 12, 11 and 13 against 11, 13 and 14, with errors −1, +2 and +1. Drift forecasts 12 + (12 − 10) / 1 = 14, 11 + (11 − 10) / 2 = 11.5 and 13 + (13 − 10) / 3 = 14 against the same values, with errors −3, +1.5 and 0. The scale is q = (2 + 1 + 2 + 1) / 4 = 1.5. Seasonal naive has MASE (1 + 2 + 1) / 3 / 1.5 = 0.889; drift has (3 + 1.5 + 0) / 3 / 1.5 = 1.000; seasonal naive is chosen. Its forecast for period 6 is 14, with a range of 14 − 1 = 13 to 14 + 2 = 16. The caption counts 1 of 3: the error +1 lies between the other two, −1 and +2, while −1 lies below both of the others and +2 above both. The error is shown as 0.89. With the first four values only, the origins are 2 and 3, two origins, so the answer is `NO_DATA` with `series_too_short`; so is any series of three annual points (C23). Smoothing recursion: with α = 0.5 on 10, 12 and 11, the levels are 10, 11 and 11, so the forecast is 11; the grid choice of α has its own fixture at the slice that builds the card.

**Provenance and status.** The series' class: Public, or Synthetic for a released monthly series; `inferred` (MTH-58); caveat `forecast_backtest_range`, with the series' own caveats (for example `openings_incomplete` on a licence-issue series, the deal count beside a price series, `fdi_estimates` on announced investment) and the reliability mark where a count below 30 enters (MTH-13). Subject and geography: those of the series. A forecast of a released monthly series carries the word "forecast", the Synthetic class and the caveats `synthetic_not_evidence_about_qatar` and `synthetic_change` beside `forecast_backtest_range`; its subject is the `area` of its series, and its origin is the last released month. A forecast of a Public split by sex or nationality stays on the source's own geography and categories and is never combined with another figure (PUB-90). **Compute cost.** Not yet timed.

**Limits and wording.** A forecast continues the pattern that the chosen candidate found in past values; a shock, a policy change or a turning point that is not in the series is not in the forecast. A short series has few origins, so its range rests on few values. The range is built from the backtest's own errors: it is not a probability or a confidence level, and it is never said to hold for the next value. A forecast chart draws the range as a band with its caption; the projection of C21 keeps its own rules and stays a projection. A forecast of a released monthly series continues the synthetic world's months; it shows the format, not a trend in Qatar. A price forecast is of a median with its deal counts; a forecast of announced investment is of announcements, not realised investment (C28).

- Allowed: "Forecast of {series} for {period}: {value}, range {low} to {high}. In the backtest {x} of {y} past values fell inside the range that the other past errors gave; its error was {error}." With it, the method line: "Method: {candidate}, chosen in code by backtest; source: {source}." For a released monthly series: "Forecast of this area's synthetic {series} for {month}: {value}, range {low} to {high}. In the backtest {x} of {y} past values fell inside the range that the other past errors gave; its error was {error}. These are synthetic months: this shows the format, not Qatar." A series too short for the backtest is shown as "not enough history".
- Never say: "will", "probability", "confidence", "likely", "certain", "chance", "odds", "the market will rise", a forecast of the success of a venture, or a forecast for a named business, owner or person.

| ID | Requirement |
|---|---|
| MTH-98 | C30 forecasts only a series of the closed, versioned list: a Public series whose source table the public data pack holds, or a released monthly series of the window; it chooses the model of each series by the rolling-origin backtest above, from the closed candidate list only: the candidate with the smallest mean absolute scaled error, ties by list order. No person and no language model chooses a model. A series with fewer than three origins, or with less than twice the horizon of history at the first origin, returns `NO_DATA` with reason `series_too_short`, shown as "not enough history", never a model without a backtest. It reproduces the fixture: MASE 0.889 for seasonal naive against 1.000 for drift; forecast 14, range 13 to 16, 1 of 3; `NO_DATA` with four values; the smoothing levels 10, 11 and 11. |
| MTH-99 | Every forecast is shown with its interval and its measured backtest error. The interval at each horizon runs from the forecast plus the smallest to the forecast plus the largest backtest error of the chosen candidate at that horizon, and its caption states how many past values of the backtest fell inside the range that the other past errors gave, each value checked against a range built without its own error, and how many there were, both as Fact chips and never as a percentage. It is never called a probability or a confidence level and never said to hold for the next value. A forecast chart draws it as a band with that caption. The projection of C21 keeps its own rules and is never shown as a forecast. |
| MTH-100 | A forecast is `inferred`, takes the subject, geography and class of its series, and its lineage names the method and version and the series; the model and the horizon identify the fact, and the interval ends, the backtest error and the number of backtest points are facts of the same computation, shown with it, resolving to the source like any fact (MTH-08). Every forecast of card C30, of a Public series or of a released monthly series, is computed at request time by `eii_core.calc` from release tables, as a projection is (DAT-144), and none is written to the release. A forecast of a released monthly series carries the Synthetic class, the word "forecast" and the caveats `synthetic_not_evidence_about_qatar` and `synthetic_change` beside `forecast_backtest_range`, has the subject `area` of its series and the last released month as its origin, is a labelled projection from the released months and not a protected statistic of a later month (PRV-54), states no change between two months (ARC-130), and is off in public-only mode as a ranking criterion (MTH-65); a series with a carried-forward month in its window returns `SUPPRESSED` with `CARRIED_FORWARD`. A forecast of a Public split by sex or nationality stays on the source's own geography and categories. The licence series keep their names, licence issues and licence cancellations (PUB-94), and no net series is formed. The class `forecast_not_offered` declines three cases: a forecast of the success of a venture; a forecast, estimate, share, score, rank or fit for a named real place, building, business, owner or person; and a forecast of a series that is not on the list. |

### C31 Entry, closure and survival base rates

**Purpose.** Show, for an activity on the source's own geography, what share of past licences were issued, cancelled or still held, as base rates from the Public licence tables with their counts and period ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 7). A base rate describes past licences of that activity and area, not the user's own venture.

**Inputs.** `pub_licence_issued` (only the 610 codes it covers; PUB-69, PUB-94), `pub_licence_cancelled` with the C2 bulk-month flag, and `pub_licence_active` (the May 2025 snapshot), by municipality and activity. Never the openings and closures of register companies (MTH-85), and never a drawn area.

**Formula.**

```
municipality j (or national), activity i, calendar year y:
  A(j, i)    = active licence-activity count at the May 2025 snapshot, the one stock the tables carry
  I(j, i, y) = licence issues in y;  C(j, i, y) = dated licence cancellations in y (C2)
entry base rate     I(j, i, y) / A(j, i)
closure base rate   C(j, i, y) / A(j, i)            the churn rate of C2, by the same function
both reported including and excluding the bulk months of C2; issues take the same bulk rule over the
  issued series' own national monthly totals (ASSUMPTION)
each rate is shown with its numerator, its denominator and its period, and with the Wilson interval
  of section 3 where the numerator does not exceed the denominator, labelled approximate because a
  flow is divided by a later stock; a denominator below 30 is low_count (MTH-13)
an activity code the issued series does not cover: the entry base rate is NO_DATA
  (reason openings_not_published_for_activity), never zero
A(j, i) = 0 or missing: NO_DATA (reason no_denominator)
survival base rate  the share of the licences issued in one period that were not cancelled within a
  stated time; the Public tables count issues and cancellations by month and never link a cancellation
  to its issue, so they do not carry the cohort that is its denominator: NO_DATA (reason
  no_denominator) until a Public table carries it
no figure of issues minus cancellations is computed or shown (MTH-19)
```

**Worked example (fixtures).** Activity P in one municipality: issues of 3, 0 and 5 in the months of a year (the C22 fixture) give 8 issues against 40 active licences, an entry base rate of 8 / 40 = 0.20. Activity Q: 6 dated cancellations in the year against 28 active licences give a closure base rate of 6 / 28 = 0.214, with the Wilson interval 0.102 to 0.395 of MTH-12, marked `low_count` because 28 is below 30. A code that the issued series does not cover gives `NO_DATA` with `openings_not_published_for_activity` for entry; an active count of 0 gives `NO_DATA` with `no_denominator`; the survival base rate gives `NO_DATA` with `no_denominator`.

**Provenance and status.** A base rate is a Public fact with evidence status Observed, the status of the churn rate of card C2 (fixed arithmetic over published counts, caveat `calculated`), and it carries the caveat key `base_rate_not_your_chance`. Each companion fact of that rate, the ends of the Wilson interval included where the numerator does not exceed the denominator, has the same status. Further caveats are `licence_activity_not_firm`, `snapshot_may_2025`, and `openings_incomplete` on every entry rate. Subjects `municipality`, `national` or `sector`, on the source's own geography. **Compute cost.** Trivial (as C2); not separately timed.

**Limits and wording.** A licence issue is not a business opening, and a cancellation is not the end of trading. A flow is divided by the later stock of May 2025, so a rate is approximate. Issues are published for part of the activities only, and bulk months are administrative. Most municipality-by-activity cells are small (C1), so many rates carry the `low_count` mark.

- Allowed: "In {year}, licence cancellations for this activity in {municipality} equalled {rate} of the active licences of May 2025 ({cancellations} cancellations; {active} active licences). This describes past licences of this activity and area, not your own business." For entry: "In {year}, licence issues for this activity in {municipality} equalled {rate} of the active licences of May 2025 ({issues} issues; {active} active licences). Issues are published for only part of the activities."
- Never say: "odds", "chance", "probability", "your survival rate", "likely to close", "net formation", "N businesses opened", "closures" for licence cancellations, "the market grew".

| ID | Requirement |
|---|---|
| MTH-101 | C31 computes entry and closure base rates by activity on the source's own geography only, never for a drawn area, from the Public licence tables: each with its numerator, denominator and period, including and excluding bulk months, the closure base rate by C2's churn function. It returns `NO_DATA` with `openings_not_published_for_activity` for an entry rate of a code the issued series does not cover, `NO_DATA` with `no_denominator` where the Public tables carry no denominator, and the survival base rate as `NO_DATA` with `no_denominator` until a Public table carries the cohort. It reproduces the fixtures: 0.20; 0.214 with the interval 0.102 to 0.395 and `low_count`; the three `NO_DATA` cases. |
| MTH-102 | No base rate is computed from the openings and closures of register companies, and no figure of issues minus cancellations is computed or shown (MTH-19, MTH-85). A base rate is worded as a share of past licences of that activity and area, never as the chance that the user's own venture survives; the word "odds" is never on screen, and the screen words stay "licence issues" and "licence cancellations". A base rate enters a ranking only under MTH-65. |

### C32 People present by pay band

**Purpose.** For a whole release unit, a day type and an hour, show the simulated workers and residents present split by pay band ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) items 11 and 12; PRV-126).

**Inputs.**

- One whole release unit, or a set of whole units of the snapped unit list of PRV-18, with a day type, an hour and a summer setting. Never a drawn outline, and never an area from `make_area` through C18.
- The published presence groups of the unit's cells (C15: workers, residents and visitors, each with its low and high and its status).
- The published pay-band shares of the same unit for one month of the window, the month the card shows: the worker-pay partition (`worker_pay` on `wp_all_quartile`) for workers present, and the resident-pay partition (`resident_pay` on `rp_all_quartile`) for residents present (MTH-55).
- Nothing else. No table is added to the release, no dimension is added to the presence key (PRV-34, PRV-58), and mobility still meets wage statistics only area to area (PRV-99).

**Formula.**

```
W, R, V   workers, residents and visitors present in unit u (C15's exact sums over u's cells, complete
          groups only), each with its low and high
b_k^W     the published share of pay band k among the covered earners of u, worker_pay, wp_all_quartile
b_k^R     the same in resident_pay, rp_all_quartile
workers present in band k     = W * b_k^W, and the same for the low and the high
residents present in band k   = R * b_k^R, and the same for the low and the high
each rounded half-up to a whole number; the bands of a segment may then differ from its count by
          rounding, and the card says so
a set of whole units: the exact sum of the unit figures, only when every unit's figure is returned
Visitors have no pay band and are shown as one count without a band. The band shares are those of
          the unit's covered earners, so the figure does not separate people who have no wage
          record: it assumes that the workers and residents present have the pay bands of the
          unit's covered workers and residents, and its caveat says so
returned only when every row it draws on is published: a withheld, suppressed, carried-forward or
          remainder row is never filled in, and the segment's bands pass through the suppression
          reason of the row that is missing (an incomplete presence group: BELOW_PANEL_MINIMUM)
never apportioned to a drawn outline
```

**Worked example (synthetic fixture, not a finding about a place).** Unit U1 has 200 workers (180 to 220), 80 residents (72 to 88) and 30 visitors present at one hour. Its worker band shares are 0.25, 0.5 and 0.25, and its resident band shares 0.5, 0.5 and 0. Workers present by band: 50 (45 to 55), 100 (90 to 110) and 50 (45 to 55). Residents present by band: 40 (36 to 44), 40 (36 to 44) and 0. Visitors: 30, with no pay band. Second fixture: U1's resident band row is suppressed; the residents' bands return `SUPPRESSED` with that row's reason, and the workers' bands still stand. Third fixture: U1's presence group is withheld; every band returns `BELOW_PANEL_MINIMUM`.

**Provenance and status.** Simulated mark; `inferred` (MTH-58); caveats `present_by_pay_band_assumed` (it assumes that the workers and residents present have the pay bands of the unit's covered workers and residents) and `estimate_not_footfall`. Subject `area`. **Compute cost.** Not yet timed.

**Limits and wording.** The figure assumes that the people present in a unit have the pay bands of that unit's covered workers or residents; it does not observe anyone's pay. Pay bands describe covered earners' pay, not spending. The counts are simulated.

- Allowed: "About {count} estimated workers present here at {hour} on a {day type} are in pay band {band} ({low} to {high}; Simulated). This assumes that the people present have the pay bands of this area's workers."
- Never say: "spending", "spending power", "income present", "purchasing power", "rich crowd", "customers", "footfall of {building}".

| ID | Requirement |
|---|---|
| MTH-103 | C32 computes, in the product plane, for a whole release unit or a set of whole units of the snapped unit list of PRV-18, the workers present by band as the published worker count times the published band shares of `worker_pay` on `wp_all_quartile`, and the residents present by band as the published resident count times those of `resident_pay` on `rp_all_quartile`, with lows and highs, rounded half-up. It returns a segment's bands only when every row it draws on is published, passes through the suppression reason of the missing row, never fills a withheld, suppressed, carried-forward or remainder row. Visitors have no pay band and are shown as one count without a band. The band shares are those of the unit's covered earners, so the figure does not separate people who have no wage record: it assumes that the workers and residents present have the pay bands of the unit's covered workers and residents, and its caveat says so. It is never apportioned to a drawn outline. It reproduces the three fixtures. |
| MTH-104 | C32 is the one combination of presence and pay (PRV-126; MTH-77). It is Inferred, carries the Simulated mark and the caveat `present_by_pay_band_assumed`, and is never called spending, spending power, income present or purchasing power. No method but C33 reads it, it is never a demand weight of C12, and no table or presence-key dimension is added for it. |

### C33 Site demand and revenue estimate

**Purpose.** For an area or pin that the user chose, give a low, a middle and a high monthly revenue of an outlet of one activity, from a model of its catchment over ranges the user states, with the main drivers ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 8; [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 12). It is an estimate of the model, never a forecast, and never an estimate for a named real building or business.

**Inputs.**

- The area or pin the user chose, as an `area` subject. The catchment is snapped to whole release units of PRV-18, shown with the snap sentence, because C32 is never apportioned.
- The activity, with its row of the hotels-and-restaurants survey (`pub_sector_accounts`, C4), and the opening hours, day types and opening days per month that the user states.
- People present by pay band through the day (C32) for the units of the catchment, and visitors present (C15) as one group with no band.
- Competitors from public listings of the activity's category (`pub_place`, or `pub_place_fsq` once pinned; one table at a time, C6) as a count and their straight-line distances from the pin or the representative point. A named competitor keeps only its Public facts and its distance, and a register company also its card's employee count, which enters no figure of this card ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-65; [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)).
- The uncertain parameters, each the user's own typed range with no prefill, visible, editable and tagged "your inputs", as the capture rate and average bill of C35 are ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 12): the share of the people present in an opening hour who buy in the category, by pay band and for visitors; the spend per purchase by pay band and for visitors, which is never called spending power; and the distance scale `D` of the competition rule. No default range is calibrated or invented, because no confirmed source holds card spending; the survey's output per establishment, 2018 to 2022 (C4), stands beside the result as a Public benchmark only and sets no range. Until the user has entered every range, the estimate returns `NO_DATA` with reason `inputs_not_entered`.
- The number of draws `N`, fixed at the slice that builds the card, and the release seed (ASSUMPTION).

**Formula.**

```
for each opening hour h of each stated day type, over the units of the catchment:
  P(b, h)  people present in pay band b (C32);  V(h)  visitors present (C15), with no band
competition share   σ = 1 / (1 + sum_j max(0, 1 - d_j / D))
                    d_j = the straight-line distance from the pin to competitor j; only the sum
                    enters, and no term is computed for display for one competitor
monthly revenue     M = days * σ * sum_h ( sum_b P(b, h) * a_b * s_b + V(h) * a_V * s_V )
                    a = the share of people present in an hour who buy; s = the spend per purchase
draws               N draws with the release seed; each uncertain parameter drawn uniformly and
                    independently from its stated range (ASSUMPTION); M computed for each draw
cases               low, middle and high = the 10th, 50th and 90th percentiles of the N values of M
                    (ASSUMPTION), each the value at rank ceil(p * N) of the values sorted upward
main drivers        one at a time: each uncertain parameter is set to the low and then the high end of
                    its range, every other parameter at the middle of its range;
                    swing = |M(high end) - M(low end)|; drivers ordered by swing, largest first, ties by
                    parameter key
a row that C32 or C15 does not return: the estimate passes its reason through and is not computed
```

**Worked example (fixture, not a finding about a place).** One pay band, one opening hour, no visitors and 30 opening days; 100 people present; the share who buy runs from 0.1 to 0.3 and the spend per purchase from 20 to 40; one competitor at 0.5 km with `D` = 1 km, so σ = 1 / (1 + 0.5) = 2/3. At the middle of both ranges, M = 30 × 2/3 × 100 × 0.2 × 30 = 20 × 600 = 12,000. Swings: the share who buy gives 20 × 300 = 6,000 and 20 × 900 = 18,000, a swing of 12,000; the spend per purchase gives 20 × 400 = 8,000 and 20 × 800 = 16,000, a swing of 8,000; so the share who buy is the first driver. Percentile rule: for ten draws of 1,000, 2,000 .. 10,000, the low case is the value at rank 1 (1,000), the middle at rank 5 (5,000) and the high at rank 9 (9,000).

**Provenance and status.** The least-real class of the inputs, Simulated while presence is simulated (MTH-07); `inferred`, with the "your inputs" tag because every range is the user's own (MTH-06); caveats `estimate_on_simulated_inputs` while any input is Simulated or Synthetic, `your_inputs`, `national_average`, `movement_not_purchases` and `present_by_pay_band_assumed`. Subject `area`. Never written to the release or the ledger. Off in public-only mode, and unavailable while OI-03 keeps the survey figures off screen (MTH-29). **Compute cost.** Not yet timed.

**Limits and wording.** The estimate describes the stated model and ranges, not observed sales. The cases are cases of the model. The survey figures are national averages over all outlets of the activity. The competition rule counts competitors by distance only and ignores their size. While presence is simulated, the estimate shows the format a linked mobility feed would give, not a finding about the place.

- Allowed: "Estimate on simulated inputs: with the ranges shown, this model gives an outlet of this activity here a monthly revenue of {low} in its low case, {middle} in its middle case and {high} in its high case. The inputs that move it most are {driver 1} and {driver 2}."
- Never say: "forecast", "will earn", "expected revenue", "chance", "probability", "confidence", "likely", "spending power", "income present", "purchasing power", "customers will come", any figure for a named competitor, or a share of draws.

| ID | Requirement |
|---|---|
| MTH-105 | C33 computes the monthly revenue of the model above over the whole release units of the snapped catchment, from C32's people present by pay band, C15's visitors, the competitor count and distances, and the stated ranges; draws each uncertain parameter from its range with the release seed; returns the 10th, 50th and 90th percentiles of the draws as the low, middle and high cases, by the nearest-rank rule; and returns the main drivers by the one-at-a-time swing, largest first. The same release and inputs return the same cases and drivers. It reproduces the fixture: 12,000 at the middle; swings 12,000 and 8,000; cases 1,000, 5,000 and 9,000 for the ten draws. |
| MTH-106 | C33 carries the label "estimate on simulated inputs" while any input is Simulated or Synthetic, has subject `area`, and is never an estimate for a named real building or business; no figure for a named competitor is computed for display, shown, stored or logged. The share who buy and the spend per purchase by band are the user's own typed ranges with no prefill, and no range is calibrated or invented by the application ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 12); a missing range returns `NO_DATA` with `inputs_not_entered`; the spend per purchase is never called spending power. The estimate is off in public-only mode, is unavailable while OI-03 is open (MTH-29), is never called a forecast, and enters a ranking only under MTH-65. |

### C34 Catchment-share scenario

**Purpose.** In the user's scenario, show the share of choices that the user's outlet would take and the share of the competitors split by competitor category and by distance band (for example Italian restaurants within 500 m; other restaurants), never per named business, when customers choose by distance and by an attractiveness that the user sets ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 9). It joins the break-even calculator (C4), is the user's scenario and is never called a forecast.

**Inputs.**

- The user's outlet at the pin of the area the user chose.
- Competitors: the public places within the catchment that compete with the activity (one places table, C6), each with its category from the reviewed category mapping of the places layer and its distance from the outlet. A named competitor keeps only its Public facts and its distance, and a register company also its card's employee count, which enters no figure of this card ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-65; [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)).
- The distance bands, a closed list of this card (ASSUMPTION): within 500 m, 500 m to 1 km, 1 km to 2 km, and beyond 2 km of the outlet.
- Customer locations: the base cells of the fixed frame whose centre lies in the catchment, each counted once with equal weight (ASSUMPTION).
- The user's settings, each visible and editable and tagged "your inputs": the attractiveness `A_u` of the user's outlet against the competitors as a group (default 1), or one attractiveness for each competitor category, never for one named business; the distance exponent `λ`; and the distance floor `d_0`. The defaults of `λ` and `d_0` are fixed at slice S2 (ASSUMPTION).

**Formula.**

```
for each customer location i:
  user's term        T_u(i) = A_u * max(d_iu, d_0)^(-λ)
  competitors' term  T_c(i) = sum_j A_c(j) * max(d_ij, d_0)^(-λ)
                     A_c(j) = 1, or the attractiveness the user set for the category of j
  p_u(i) = T_u(i) / (T_u(i) + T_c(i))
user's outlet share  S_u = the mean of p_u(i) over the customer locations
competitors' share   S_c = 1 - S_u
cells                each competitor j falls in one cell: its category and its distance band from the outlet;
                     a cell that holds a single competitor is merged into the next wider cell: the same
                     category in the next distance band, then the cell "other"; repeated from the
                     nearest band outward; a merged cell is named by its category and the bands it joins
cell share           S(K) = the mean over i of [sum over j in K of A_c(j) * max(d_ij, d_0)^(-λ)] / (T_u(i) + T_c(i));
                     the cell shares sum to S_c
no split             when the cell "other" still holds a single competitor after the merges, the split is not
                     shown: the card shows S_u and S_c only, because the shown cells and S_c would give that
                     competitor's share by subtraction
one competitor       when the list holds one competitor in all, the card shows S_u only and says that one
                     competitor is listed; it states no share for the competitors
no customer location: NO_DATA; no competitor: S_u = 1, and the card says that no competitor is listed
no share or term is computed for display for one competitor
```

**Worked example (fixture, not a finding about a place).** `λ` = 1, `A_u` = 2, `A_c` = 1, and `d_0` below every distance. Location i1 is 1 km from the outlet and 1 km and 2 km from two competitors: `T_u` = 2 and `T_c` = 1 + 0.5 = 1.5, so `p_u` = 2 / 3.5 = 4/7. Location i2 is 2 km from the outlet and 1 km from each competitor: `T_u` = 1 and `T_c` = 2, so `p_u` = 1/3. `S_u` = (4/7 + 1/3) / 2 = 19/42, shown as 0.45, and `S_c` = 23/42, shown as 0.55.

**Split fixture (not a finding about a place).** One customer location i, `λ` = 1, every attractiveness 1 and `d_0` below every distance. The outlet is 1 km from i, so `T_u` = 1. Competitors a and b, of category K1 and within 500 m of the outlet, are each 1 km from i; competitor c, of K1 and 1 km to 2 km from the outlet, is 2 km from i; competitor d, of K2 and 1 km to 2 km from the outlet, is 2 km from i. So `T_c` = 1 + 1 + 0.5 + 0.5 = 3, `S_u` = 1 / 4 = 0.25 and `S_c` = 3 / 4 = 0.75. The cell of K1 within 500 m holds a and b: (1 + 1) / 4 = 0.50. The cell of K1 at 1 km to 2 km holds c alone, so it is merged into K1 beyond 2 km, which then holds c alone and is merged into "other"; the cell of K2 at 1 km to 2 km holds d alone and goes the same way. "Other" holds c and d: (0.5 + 0.5) / 4 = 0.25. The cells sum to 0.50 + 0.25 = 0.75 = `S_c`, and no cell shows one competitor. Without competitor d, `T_c` = 1 + 1 + 0.5 = 2.5, `S_u` = 1 / 3.5 = 2/7, shown as 0.29, and `S_c` = 5/7, shown as 0.71; c would be alone in "other", so no split is shown. With competitor a alone, `T_c` = 1 and `S_u` = 1 / 2 = 0.50; the card shows the outlet's share only and says that one competitor is listed.

**Provenance and status.** Public points and Public geometry with the user's inputs: Public class; `inferred`, "your inputs" tag (MTH-06); caveats `scenario_not_forecast` and `your_inputs`. Subject `area`. Never written to the release or the ledger. **Compute cost.** Not yet timed.

**"How sure" beside the scenario ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 5).** Where the scenario is shown for one of the three sites that C40 chose in the same answer, the "how sure" sentence of C40 stands beside its result. Its count of runs and its named input are taken unchanged from the result of C40's runs (`location_allocation`, [08_BACKEND.md](08_BACKEND.md) BE-133), with X a Fact chip. This card runs no Monte Carlo or Sobol runs of its own and computes no count: the sentence counts runs of C40's model over the user's ranges, not runs of this scenario. Where no C40 result holds the site, no such sentence is shown. The sentence never states a percentage, a probability, a confidence level or a chance (MTH-115).

**Limits and wording.** The scenario holds only the stated distance rule and attractiveness; it is not calibrated to any sales or movement (section 6). Equal weights for the frame cells ignore where people are. The places data is incomplete (C6). The categories are those of the reviewed category mapping of the places layer, and the distance bands are the card's closed list.

- Allowed: "In your scenario, with the attractiveness and distance rule you set, your outlet would take {share} of the choices of people across this area, and the {n} listed competitors together {share}. This is your scenario, not a forecast." For each cell of the split: "{category} within {band}: {share}, {k} listed places." and "Other listed competitors: {share}, {k} listed places." Where no split is shown, the first sentence stands alone. With one listed competitor: "In your scenario, with the attractiveness and distance rule you set, your outlet would take {share} of the choices of people across this area. One competitor is listed. This is your scenario, not a forecast." Beside the result, for one of the three sites of C40, C40's sentence in the form its result takes, for example: "The choice of these three sites holds in {X} of {N} runs over your ranges and is most sensitive to {input}. This counts runs of the model; it is not a probability."
- Never say: "forecast", "will capture", "market share of {business}", any share for a named competitor, a cell that holds or names a single competitor, "you will win", "best", "chance", "probability", "likely".

| ID | Requirement |
|---|---|
| MTH-107 | C34 computes the user's outlet share, the competitors' share and its split by competitor category and by distance band by the rule above, the bands from the card's closed list and every cell that holds a single competitor merged into the next wider cell; where "other" still holds a single competitor after the merges it shows no split, and with one competitor in all it shows the outlet's share only, with every setting visible, editable and tagged "your inputs", one attractiveness for the competitors as a group or for each competitor category and never for one named business; it computes, shows, stores and logs no share or term for one competitor; it fits nothing to simulated movement; it is never called a forecast and carries `scenario_not_forecast`; and it reproduces the fixtures (19/42 and 23/42; 0.25 for the outlet, 0.50 for K1 within 500 m and 0.25 for "other"; no split without competitor d, 2/7 and 5/7; the outlet's share alone, 0.50, with one competitor). |
| MTH-120 | Where C34 is shown for one of the three sites that C40 chose in the same answer, the "how sure" sentence of C40 stands beside its result, with the count of runs and the named input taken unchanged from C40's runs (`location_allocation`, BE-133; MTH-114, MTH-115) and X a Fact chip ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 5). C34 runs no runs of its own and computes no count. Without a C40 result for the site, no such sentence is shown, and a planted one beside such a scenario fails. The sentence never states a percentage, a probability, a confidence level or a chance. |

### C35 Revenue range of the user's outlet

**Purpose.** In the user's scenario, show low, middle and high monthly revenue cases for the user's outlet beside the break-even point and a Public benchmark ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 10). It is the user's scenario and is never called a forecast.

**Inputs.**

- The area the user chose and its estimated people present by hour (C15 for a set of whole units, C18 for an area from `make_area`), all people of complete groups, over the opening hours and the day type that the user states.
- The user's assumptions, each with a low, a middle and a high value, visible, editable and tagged "your inputs": the capture rate (the share of the people present in each opening hour that the user assumes become covers of the outlet) and the average bill; and the opening days per month (C4's input `D`). These inputs join the closed list of typed scenario inputs ([08_BACKEND.md](08_BACKEND.md)).
- The Public benchmark: the survey's output per establishment of the activity (C4 norms), its 2022 value and its range across 2018 to 2022, shown per month; and C4's break-even revenue from the user's own C4 inputs.

**Formula.**

```
H        = the sum over the opening hours h of the all-people count present at h (C15 or C18);
           H_low and H_high = the sums of the lows and of the highs
low      = H_low  * capture rate (low)    * average bill (low)    * days
middle   = H      * capture rate (middle) * average bill (middle) * days
high     = H_high * capture rate (high)   * average bill (high)   * days
benchmark  the survey's output per establishment / 12: the 2022 value and the 2018-2022 range (C4)
break-even C4's break-even revenue for 2022 from the user's C4 inputs, shown beside the three cases
any withheld presence group: SUPPRESSED with BELOW_PANEL_MINIMUM, never filled in
```

**Worked example (fixture, not a finding about a place).** Two opening hours with 100 (90 to 110) and 200 (180 to 220) people present give H = 300 (270 to 330). With a capture rate of 0.01, 0.02 and 0.03, an average bill of 80, 100 and 120 and 30 days: low = 270 × 0.01 × 80 × 30 = 6,480; middle = 300 × 0.02 × 100 × 30 = 18,000; high = 330 × 0.03 × 120 × 30 = 35,640. Beside them stands C4's break-even revenue for the same user's C4 inputs (QAR 127,796 a month in C4's example).

**Provenance and status.** Simulated, the least-real class of its inputs (MTH-07); `inferred`, "your inputs" tag (MTH-06); caveats `scenario_not_forecast`, `your_inputs`, `national_average` and `movement_not_purchases`. Subject `area`. Never written to the release or the ledger. Off in public-only mode, because its presence input is Simulated, and off screen while OI-03 is open, like the break-even calculator (MTH-29). **Compute cost.** Trivial; not separately timed.

**Limits and wording.** The capture rate and the average bill are the user's assumptions, and the people present are simulated. The benchmark is a national average over all outlets of the activity. Measures of present size, such as a wage bill (C24), a number of firms or retail sales where a Public table publishes them, are measurements with their own class and are not part of this card.

- Allowed: "Your scenario: with your capture rate and average bill, and the estimated people present here (Simulated), monthly revenue would be {low} in your low case, {middle} in your middle case and {high} in your high case. The sector's 2022 output per establishment was {benchmark} a month, and your break-even revenue is {break-even}. This is your scenario, not a forecast."
- Never say: "forecast", "expected revenue", "you will make a profit", "will earn", "demand at this site", "go" or "no-go" as a verdict, "chance", "probability", "likely", "customers will come".

| ID | Requirement |
|---|---|
| MTH-108 | C35 computes the low, middle and high cases as the presence sum times the user's capture rate, average bill and opening days of the same case, shows them beside the survey benchmark per month and C4's break-even revenue, and reproduces the fixture (6,480; 18,000; 35,640). Every assumption is visible, editable and tagged "your inputs"; the result carries `scenario_not_forecast`, is never called a forecast, is off in public-only mode and off screen while OI-03 is open (MTH-29). The words "capture rate" name only this input of the user: the build-time scan allows them only as the label of that input in this card's templates. |

### C36 Night-time radiance by area and month

**Purpose.** Show the night-time radiance of an area by month as a Public layer ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 20). It is worded as night-time radiance, not as a measure of business activity.

**Inputs.** NASA Black Marble VNP46A3 (`ntl_blackmarble`): monthly radiance on a 15 arc-second grid, about 500 m, fetched with the Earthdata token inside `./eii build-public`, which continues and leaves this layer out when `EARTHDATA_API_KEY` is absent ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 16), and held as a hashed file in the public cache, with the product's quality flags; the cells of the fixed frame; an area the user chooses, a release unit or an official geography.

**Formula.**

```
for each month and each cell c of the fixed frame (the public-data build, writing pub_night_lights):
  the pixels whose centre lies in c, leaving out fill values and the pixels that the product's quality
  flag marks as poor, by the flag rule fixed at slice S2
  radiance(c, month) = the mean of their radiance; no pixel kept: NO_DATA, never 0
  no pixel is split, so nothing is apportioned
an area, a release unit or an official geography X:
  the mean of radiance(c, month) over the frame cells c whose centre lies in X, each cell counted
  once (ASSUMPTION); no such cell with a value: NO_DATA
```

**Worked example (fixture).** Cell c1 holds the centres of pixels with radiance 2, 4 and 6 and of one fill pixel, so radiance(c1) = (2 + 4 + 6) / 3 = 4. Cell c2 holds one pixel of 10, so radiance(c2) = 10. An area that holds the centres of c1 and c2 has (4 + 10) / 2 = 7. A cell that holds only fill pixels is `NO_DATA`.

**Provenance and status.** Public, `observed` (MTH-05); caveats `calculated` and `night_lights_not_activity`; NASA acknowledged as the source and the product DOI cited. Subject `area` or the official geography. Never blended into C9 or into a protected or Simulated figure. **Compute cost.** Not yet timed.

**Limits and wording.** Radiance measures light seen from orbit at night: street lighting, roads, ports, industry and flares all add to it, and cloud, moonlight and season can disturb a month. It is not business activity, population or footfall. A pixel of about 500 m is coarser than many areas, and a cell's value covers the pixels whose centre lies inside it.

- Allowed: "Night-time radiance here in {month}: {value} nanowatts per square centimetre per steradian (NASA Black Marble, VNP46A3). Night-time light is not a measure of business activity."
- Never say: "economic activity", "business activity", "busy", "footfall", "population", "prosperity", "demand", "a growing area".

| ID | Requirement |
|---|---|
| MTH-109 | C36 takes the mean radiance of the kept pixels whose centre lies in each frame cell, by month, leaving out fill values and pixels flagged poor by the rule fixed at slice S2, splits no pixel, and returns `NO_DATA`, never 0, where no pixel is kept; an area, release unit or official geography takes the mean of the cell values whose centre lies inside it. It is Public, carries `night_lights_not_activity`, cites the product DOI, is worded as night-time radiance and never as business activity, is never blended into another figure, and reproduces the fixture (4; 10; 7; `NO_DATA`). |

### C37 Relative busyness of named venues

**Purpose.** Show the published relative busyness by hour of a named venue as a Public fact of that venue ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 19). It is a relative index, never a count of people.

**Inputs.** `pub_venue_busyness` from `busy_gmaps`: venue, day of week, hour, relative index from 0 to 100, and retrieval date, for the named venues of a build-time list. The project's own page reader fetches it inside `./eii build-public`, never at run time; the values stay in the uncommitted public cache and never enter the repository or a test fixture, and the source is left out of the nightly live fetch. The publisher states no licence for reuse, and its terms name automated reading; the owner decided on 2026-11-12 to use it in this personal internal project, and decision 0019 names it under PUB-12 with `licence_basis: owner_decision`.

**Formula.**

```
venue v, day of week d, hour h: the index as published, 0 to 100; no arithmetic on a venue's own row
an hour with no published index: NO_DATA, never 0
a list of named venues around a site is ordered by distance only (PUB-92), never by the index
the pooled hour-of-day shape by place category of C26 is the only computation that reads these rows
```

**Worked example (fixture, invented venues).** An invented venue's rows for hours 9, 10 and 11 hold 40, nothing and 100: the card shows 40, `NO_DATA` and 100, never 0 for hour 10. Three invented venues at 300 m, 100 m and 200 m from a pin are listed at 100 m, 200 m and 300 m, whatever their indices.

**Provenance and status.** Public, `observed`; subject `place_public`, Public slots only (MTH-10); labelled "Google Maps popular times" with its retrieval date; caveat `relative_busyness_not_people`. It never shares a component with an estimated-people figure (C15, C27), is never a score, rank, fit or criterion (MTH-57), and no venue's level or own shape is transferred to a Simulated figure (MTH-92). **Compute cost.** Trivial; not separately timed.

**Limits and wording.** The index is relative to the venue's own busier times, as the publisher describes it, so it is not a count of people and not a level to compare between venues. Hand-made fixtures test the code; no real value enters a test.

- Allowed: "Google Maps popular times, retrieved {date}: at {hour} on {day}, this venue shows {index} on its own relative scale of 0 to 100. This is not a count of people."
- Never say: "{n} people at {venue}", "visitors to {venue}", "footfall of {venue}", "busiest venue", "best time to visit", "crowded", "customers", or a Simulated figure beside a venue's index.

| ID | Requirement |
|---|---|
| MTH-110 | C37 shows a named venue's relative busyness only as published, as a Public fact of a `place_public` subject labelled "Google Maps popular times" with its retrieval date, returns `NO_DATA` (never 0) for an hour with no index, orders a list of venues by distance only, never puts the index in a component with an estimated-people figure, never scores, ranks or fits a venue by it, and reproduces the fixture. Its values come only from the uncommitted public cache filled by `./eii build-public`; no test fixture holds a real value, and the source is left out of the nightly live fetch. |

### C38 Population by age and sex over an area

**Purpose.** Show the Public population by age and sex of an area the user chooses, as the sum of whole cells of a published population grid ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 22). The sum is not an apportionment, and it is display only. In the site answer of journey D2 it gives the age profile of the people living here: the population by age, with no split by sex (`split` `none`), over the area of the living block, as its own Public component after the two blocks. It never sits inside either block, in one calculation with them or on one chart with them, because no worker, residence or company record carries age (movement aggregates are the one exception, decision 0023 item 16, and they are not this card; SYN-13; [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 11 and its assumption).

**Inputs.** `pub_pop_agesex_grid` from `worldpop_qat_agesex` (100 m grid cells, age band, sex, people, year; CC BY 4.0); an area the user chooses or an official geography.

**Formula.**

```
area X, year, age band a, sex s:
  people(X, a, s) = the sum of people(c, a, s) over the grid cells c whose centre lies in X
                    (a centre on the boundary counts as inside; ASSUMPTION); no cell is split
  rounded half-up to a whole number after summing; a total across age bands or sexes is the sum of
                    the same cells, rounded once
  no cell centre in X: NO_DATA
it applies no weight and splits no cell, so it is not an apportionment (C18)
```

**Worked example (fixture).** Cells g1 and g2 have their centres in the area and g3 does not. For one age band, the female values are 10.4, 12.3 and 30.0 and the male values 11.2, 13.1 and 25.0. The area holds 10.4 + 12.3 = 22.7 females, shown as 23, and 11.2 + 13.1 = 24.3 males, shown as 24; both sexes together hold 47.0, shown as 47. Cell g3 is left out. An area with no cell centre is `NO_DATA`.

**Provenance and status.** Public, `observed` (MTH-05); caveats `calculated` and `grid_cells_summed`, with the source and year. Subject `area`. Display only: never a ranking criterion (MTH-65), a feature of C17, a demand weight of C12 or a weight of C18; never combined with a protected, Synthetic or Simulated figure, and never on one chart with one. The generator reads the grid only collapsed across age and sex, as weights (document 05), except the movement generator's anchors of decision 0023 item 16; no worker, residence or company record carries sex or age (SYN-13, DAT-141). **Compute cost.** Not yet timed.

**Limits and wording.** The grid holds modelled estimates for one year. A cell whose centre lies inside counts whole even where part of it lies outside, and a cell whose centre lies outside is left out.

- Allowed: "About {people} people of {age band} ({sex}) lived in {year} in the 100 m grid cells whose centres lie in this area (WorldPop modelled estimates, CC BY 4.0; whole cells summed)."
- Never say: "customers", "counted", "census of your area", "exactly", or this figure beside a Simulated, Synthetic or protected figure.

| ID | Requirement |
|---|---|
| MTH-111 | C38 sums whole cells of `pub_pop_agesex_grid` whose centre lies in the area, splitting no cell and applying no weight, and rounds once after summing; it returns `NO_DATA` for an area with no cell centre; it is Public with `grid_cells_summed`, display only, never a criterion, feature or weight, never combined or charted with a protected, Synthetic or Simulated figure; and it reproduces the fixture (23; 24; 47). |

**Cards added by decision 0023.** [Decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) adds C39 (item 1), C40 (item 5) and C41 (item 8). Each is a deterministic function in `eii_core.calc` (MTH-01); a library named on a card (PySAL `spopt` and SALib, for C40) is pinned at the start of the task that builds it, after its current documentation and licence are read, and its result must equal the card's arithmetic on the card's fixtures. Every worked example below uses invented round numbers: none is a figure about a place.

### C39 Talent available near this site

**Purpose.** For a site, show two released figures side by side within 10, 20 and 30 minutes' drive, and the talent ratio of those two figures. The talent pool is the covered earners of an occupation group who live within reach, with their pay as band counts, the median band and the middle range. The competing demand is the jobs of the same occupation group held at workplaces within reach. The ratio is the quotient of those two released figures for the same occupation group and the same cut-off (MTH-122). The home-to-work flows are drawn as aggregate flows (journey D5, the map and the guided story; [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 1). The answer is called "Talent available near this site", never "who can work for you", so that it never reads as a list of people. The card's closed list 10, 20 and 30 is its own, through `workers_within_reach`, in every playbook whose bundle calls that tool ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-111 holds them in its enumeration). No drive-time catchment goes beyond 30 minutes (decision 0023 item 17).

**Inputs.**

- The site: a pin the user chose, or the representative point of a drawn shape (`eii_core.shapes`). For each cut-off of the closed list 10, 20 and 30 minutes, the drive-time area of the site from C25, at free flow (Public) or at an hour of the release (Simulated while traffic is simulated). A request above 30 minutes is refused (TST-256).
- Each drive-time area snaps to whole release units like every area, before any protected figure is read (MTH-56; [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-17, PRV-18). It snaps once on the partition of each figure: `op_res_quartile` for the talent pool, `op_work_quartile` for the competing demand and `ha_work_count` for the flows. Each figure is a block with its own snapped set, snap sentence and released area (PRV-20, PRV-22). A remainder is never added to a sum; a withheld unit is left out, and the snap report names its cells.
- Talent pool: the published band counts of `occupation_pay` on the residence basis (`op_res_quartile`, occupation-group breakdown; MTH-55), for one month of the window.
- Competing demand: the published counts of `occupation_pay` on the workplace basis (`op_work_quartile`, occupation-group breakdown) for the same month. They count one job per person, employer group and month (PRV-08).
- The split of the talent pool into Qatari and non-Qatari: only a released nationality-group breakdown of the residence family (PRV-09), read on its own partition (PRV-21). Document 06 places that breakdown at slice S5 (its Open questions); until it is configured, no split is offered.
- Flows: the published `home_area_share` counts of the same month. Their work units are those of `ha_work_count`, and each home unit is one whole municipality of `ha_home` ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) section 4.4).

**Formula.**

```
site s; cut-off t0 in {10, 20, 30} minutes; occupation group g; one month of the window
R, W, K       the snapped sets of the drive-time area of s at t0 on op_res_quartile,
              op_work_quartile and ha_work_count (PRV-18)
talent pool of g, over R
  count       P = the exact sum of g's published band counts over the units of R (MTH-55)
  bands       the band ranges whose boundaries every unit of R shares (document 06 section 6.2);
              P(b) = the sum of g's counts in range b; a merged band row is never split, and a
              range wider than one band carries BANDS_MERGED; no shared inner boundary: every
              band figure SUPPRESSED with BANDS_NOT_SHARED (PRV-32)
  median band the first range whose running count reaches P / 2 (section 6.2)
  middle range from the first range whose running count reaches P / 4 to the first that
              reaches 3P / 4 (the quartile bands of section 6.2); a running count equal to the
              fraction takes that range and the next together
  minimums    the median band only if P >= 30 (A) or 50 (B); the band counts and the middle
              range only if P >= 100 (A) or 200 (B); otherwise SUPPRESSED with
              DETAIL_NEEDS_LARGER_GROUP (PRV-31)
competing demand of g, over W
  count       J = the exact sum of g's published counts, all bands, over the units of W
a unit of R or W in which g has no leaf of its own (pooled in other, PRV-35): every figure of g
              over that set SUPPRESSED with SPLIT_NOT_PUBLISHABLE (PRV-21), never a partial sum
              and never a zero
a unit whose atoms for the month repeat an earlier month (PRV-56) enters with them, and each
              figure that sums it carries CARRIED_FORWARD (PRV-123)
side by side  P and J are two facts, each of one home family (PRV-30)
ratio         Rto = P / J, the quotient of the two released figures for the same g and t0,
              shown to one decimal, halves up, labelled "qualified people per competing job
              within t0 minutes" (MTH-122). It is never called competition-adjusted and never
              an index. Either input suppressed or below its minimum: the ratio is not shown,
              reason ratio_input_withheld. J = 0: the ratio is not shown, reason
              no_competing_jobs. Computed only from the two released tables, never from records
              and never before release (PRV-127)
split of P    the Qatari and non-Qatari counts of the released breakdown, only where its cell is
              published; otherwise withheld with its reason (SPLIT_NOT_PUBLISHABLE,
              POOLED_IN_REMAINDER, REMAINDER_FAILED or DETAIL_NEEDS_LARGER_GROUP; PRV-21), and
              no part of it is shown; no breakdown configured: DIMENSION_NOT_OFFERED
flows         for each home unit h of ha_home: F(h) = the exact sum of the published
              home_area_share counts from h to the units of K; one line from h to the snapped
              area, its width F(h) (ASSUMPTION); the pooled other row is listed as a total with
              no line, because it has no single home area; no line comes from any other value
              the animation samples moving marks from F(h) with a fixed seed, as SYN-59 does;
              no mark is a person or a trip, and no path of a person exists
no withheld or suppressed value is filled in, and no null is a zero
sums run in identifier order, so every run gives identical results
```

**Worked example (invented round numbers).** Residence units H1, H2 and H3 of `op_res_quartile`, and workplace units J1, J2 and J3 of `op_work_quartile`. The site's 10-minute area snaps to {H1} and {J1}, its 20-minute area to {H1, H2} and {J1, J2}, and its 30-minute area to {H1, H2} and {J1, J2, J3}: H3 is withheld, so it is left out and the snap report names its cells. For one occupation group, H1 holds 60, 50 and 30 earners in bands F1, F2 and F3, and H2 holds 40, 30 and 20. J1, J2 and J3 hold 300, 500 and 200 jobs of the group.

- At 10 minutes the talent pool is 140, with 60, 50 and 30 by band. Half of 140 is 70, first reached in F2 (60, then 110), so the median band is F2. A quarter, 35, is reached in F1, and three quarters, 105, in F2, so the middle range runs from F1 to F2. The competing demand is 300 jobs. The ratio is 140 / 300, shown as 0.5.
- At 20 minutes the talent pool is 230, with 100, 80 and 50. Its median band is F2 (115 is first reached at 180), and its middle range runs from F1 to F2 (57.5 is reached in F1, 172.5 in F2). The competing demand is 800 jobs. The ratio is 230 / 800, shown as 0.3.
- At 30 minutes the talent pool is still 230, because H3 is left out. The competing demand is 1,000 jobs. The ratio is 230 / 1,000, shown as 0.2.

Minimums: under set B the 10-minute pool of 140 shows its median band, but its band counts and middle range return `SUPPRESSED` with `DETAIL_NEEDS_LARGER_GROUP`; at 20 and 30 minutes, 230 passes. A second group with 20 and 10 earners in F1 and F2 of H1 has a 10-minute pool of 30: under set A its median band is F1 (half, 15, is reached at 20), and its band counts and middle range return `SUPPRESSED` with `DETAIL_NEEDS_LARGER_GROUP`. Where either released figure is suppressed, the ratio is not shown, with reason `ratio_input_withheld`. Where the competing demand is zero, the ratio is not shown, with reason `no_competing_jobs`.

Merged bands: if H2 held 40 in F1 and 50 in F2 and F3 together, the 20-minute pool would have the ranges F1 (100) and F2 to F3 (130), with no figure for F2 or F3 alone. Half of 230 is first reached in F2 to F3, the median band, which carries `BANDS_MERGED`, and the middle range runs from the bottom of F1 to the top of F3. If instead H1 held 60 in F1 and 80 in F2 and F3 together, and H2 held 70 in F1 and F2 together and 20 in F3, the two units would share no inner boundary: every band figure of the 20-minute pool would return `SUPPRESSED` with `BANDS_NOT_SHARED`, while its count, 230, stands.

Pooled group and split: if the group had no leaf of its own in H2, its people pooled in `other`, every 20- and 30-minute figure of its pool would return `SUPPRESSED` with `SPLIT_NOT_PUBLISHABLE`, never H1's 140 alone; the 10-minute figures stand. With no nationality-group breakdown configured, the Qatari and non-Qatari split returns `DIMENSION_NOT_OFFERED`.

Flows: the 10-minute area snaps on `ha_work_count` to {K1, K2}. The published `home_area_share` rows are 120 from municipality M1 and 40 from M2 into K1, and 80 from M1 and 30 from `other` into K2. Two lines are drawn: 200 from M1 and 40 from M2. The 30 of `other` is listed as other home areas, with no line.

**Provenance and status.** The talent pool, the competing demand and the flows are Synthetic and `observed`, as fixed arithmetic over released rows (MTH-58). Each takes the least-real class of its inputs, so it is Simulated where the drive-time area is at an hour while traffic is simulated (MTH-07). Caveats `synthetic_not_evidence_about_qatar` and `calculated` on every figure, with `labour_pool_not_applicants` on the talent pool and `jobs_not_openings` on the competing demand. Subject `area`. No figure names or isolates one employer, a register company included (PRV-125). Never written to the release or the ledger. **Compute cost.** Sums over the units of the snapped sets; not yet timed.

**Limits and wording.** The talent pool counts covered earners who live within reach. They are employees of the private sector only, the employment the records hold ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 12). They are not job seekers or applicants, and nothing says they would change jobs. The competing demand counts jobs that covered earners hold, not open positions. The two figures come from two families on two partitions, each with its own snapped area, and stand side by side. The talent ratio is their quotient for the same occupation group and cut-off, from the two released tables only (MTH-122). Where people live is shown only on the areas of PRV-130: the pool is one total over each snapped catchment, and each flow starts from a whole municipality. The cut-offs are drive times from the site; at another hour the drive can take longer or shorter. No cut-off is above 30 minutes (decision 0023 item 17).

- Allowed: "Talent available near this site: about {pool} covered earners in {group} live within {t0} minutes' drive. Their median pay band is {median band}, and the middle half of them earn within the bands {low band} to {high band}. Beside them, {jobs} jobs in {group} are held at workplaces within the same drive. Qualified people per competing job within {t0} minutes: {ratio}." For a flow: "{count} covered earners who work in this area live in {municipality}."
- Never say: "who can work for you", "available to hire", "job seekers", "candidates", "you can recruit", "talent shortage", a difference of the two figures, the name of an employer or a person, an address, or a path of a person. The ratio is never called competition-adjusted and never an index.

| ID | Requirement |
|---|---|
| MTH-112 | C39 computes, for each cut-off of the closed list 10, 20 and 30 minutes and one month of the window, the talent pool from the published band counts of `occupation_pay` on `op_res_quartile` over the drive-time area snapped on that partition, and the competing demand from the published counts of the same occupation group of `occupation_pay` on `op_work_quartile` over the same area snapped on that partition (MTH-56; [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-17, PRV-18, PRV-20). Each is the exact sum of published leaves of one family (MTH-55). It gives the band counts, the median band and the middle range only on the band ranges that every unit of the snapped set shares and only where the minimums of PRV-31 are met, and never splits a merged band row (document 06 section 6.2, PRV-32). It returns `SPLIT_NOT_PUBLISHABLE` for a group without a leaf of its own in a unit of the set, never a partial sum; leaves out a withheld unit and names it in the snap report; and fills in no withheld or suppressed value. It draws the flows only as exact sums of published `home_area_share` rows from each home unit of `ha_home` into the area snapped on `ha_work_count`, and lists a pooled `other` row with no line. It reproduces the fixtures: pools of 140, 230 and 230, the median band F2 and the middle range F1 to F2 at 10 and 20 minutes, and 300, 800 and 1,000 jobs, with H3 left out and named; under set B, the 10-minute band counts and middle range `SUPPRESSED` with `DETAIL_NEEDS_LARGER_GROUP` and the median band shown; the group of 30 with the median band F1 and no band counts under set A; the merged bands, 100 and 130, with the median band F2 to F3 noted `BANDS_MERGED` and the middle range from F1 to F3; `BANDS_NOT_SHARED` with the count 230 standing; `SPLIT_NOT_PUBLISHABLE` for the pooled group at 20 and 30 minutes; `DIMENSION_NOT_OFFERED` for the split; and the flows 200 and 40, with 30 listed and no line; and the ratios 0.5, 0.3 and 0.2. |
| MTH-113 | C39 and its flows follow the cases of [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 1, and a planted violation of each fails (TST-251 to TST-254). (a) Group statistics only, through the release rules of document 06: each pool, demand and flow figure is an exact sum of published leaves, each of which passed the minimum counts of people and of employer groups and the dominance tests of PRV-24; the talent ratio is the quotient of two such released figures under MTH-122; and pay is shown only as band counts, the median band and the middle range; a pool cell below a minimum, such as the band counts of a group under the minimum of PRV-31 or a figure that draws on a leaf that was not published, fails. (b) No name, identifier, residential address, one person's pay or person-level row is read, returned or shown. (c) Where people live is shown no finer than the district (PRV-130): the pool is one total over the whole snapped set of each cut-off, which stands where that set holds a single release unit (the 10-minute fixtures of MTH-112), and it is never broken down by release unit; each flow starts from a whole municipality of `ha_home`; a pool figure over anything other than the whole snapped set of its cut-off, such as one figure for each release unit of a set of several, or a line whose home end is finer than a whole municipality of `ha_home`, such as a residence unit, a building, a street or a block, fails. (d) A commute line is only a total of published `home_area_share` rows between a whole home municipality and the site's snapped area; a line from any other value, such as four commuters from a municipality with no published row, fails. (e) No employer, a register company included, is named, listed or marked beside a pool, a demand figure or a flow (PRV-125), and a planted employer name in the answer fails. (f) The Qatari and non-Qatari split is shown only where its cell is published, and is otherwise withheld with its reason. C39 adds no table, dimension or row to the release and is computed in the product plane at request time. It forms the talent ratio only as MTH-122 states, from the two released tables, and PRV-127 refuses any other ratio of two protected families and any ratio computed before release. The answer is named "Talent available near this site", never "who can work for you". The flows' moving marks are sampled from the published totals with a fixed seed and are never trails of individuals (SYN-59). The same cases bind every other talent answer of this document: the pay benchmark of C10 meets them as written, and the Qatarization planner takes them when its card is written (Open questions). |
| MTH-122 | The talent ratio of card C39 ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 1; PRV-127) is the quotient of the card's two released figures for the same occupation group and the same cut-off of the closed list 10, 20 and 30 minutes. Tested code in `eii_core.calc` computes it from the two released tables only, after the privacy engine's work, and shows it to one decimal, halves up. Its label is "qualified people per competing job within N minutes". It is never called competition-adjusted and never an index. Its lineage names both released tables. Where either input is suppressed or below the minimum count, the ratio is not shown and the reason key is `ratio_input_withheld`. Where the competing-jobs figure is zero, no ratio is shown and the reason key is `no_competing_jobs`. It reproduces the fixtures 0.5, 0.3 and 0.2. A ratio computed from records, or before release, fails (TST-257). A ratio with a suppressed input fails (TST-258). The ratio from the two released tables passes (TST-259). |

### C40 Best three sites and "how sure"

**Purpose.** Choose three sites from candidates of one kind by a location-allocation model over criteria and ranges the user can see and change, show their shared reach with the company's own branches, and state how sure the choice is as "holds in X of 1,000 runs; most sensitive to ..." (journey D2 and the `branch_check` playbook; decision 0023 item 5). It extends C11's rank-stability sentence and card C34: it uses C34's distance rule, and C34's result for one of the three sites takes its "how sure" sentence (MTH-120). It gives no go/no-go verdict and no probability claim (AGENTS.md rule 25).

**Inputs.**

- Candidates of one kind, as C11 defines them; the company's own branches as points the user enters, or the branches of the case C4 file (your inputs).
- Demand: one demand layer of C12, the population grid at free flow (Public) or estimated residents present (C15, Simulated), never a protected figure (PRV-41).
- Travel times from C25, at free flow or at the hour shown.
- The model that chooses the three sites, one of a closed list: maximal coverage (the three sites that cover the most demand within the catchment limit `T`) and p-median with p = 3 (the least sum of demand times travel time raised to the distance exponent `λ`), each as PySAL `spopt` solves it; ties go to the candidate set that comes first in candidate-id order. Beside the three, set cover, as PySAL `spopt` solves it, reports the fewest eligible candidates that cover all demand within `T` in the base run, as a count; it never chooses the sites and is not part of the runs. When some demand lies beyond `T` of every eligible candidate, that count is `NO_DATA` with reason `not_coverable` (MTH-09), and the three sites stand.
- The uncertain inputs, each a range the user sees and changes: `λ`, `T`, the rent of each candidate and the wage level of its catchment. The rent is the user's own input, in QAR a month as the rent of C4; where the user gives none, the run uses the guide land price (C41) and the recorded deal price per square foot (C41) of the candidate's district as the two ends of a cost range in QAR a square foot, formed only where both are per square foot as C41 compares them, labelled as prices and never as rents ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 12). The wage level is the median pay band of the covered earners living within reach of the candidate: the band family of `resident_pay` on `rp_all_quartile` over the candidate's drive-time area (C25) at the base run's catchment limit, snapped to whole release units before any protected figure is read (MTH-56; [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-18), derived as section 6.2 of that document does and only under PRV-31 and PRV-32, with that one family named in its fact lineage (MTH-55); it is drawn between that band's bounds. A median band with no upper bound (B12, the open top band of [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) DAT-16, or a range that ends at B12, such as a merged range of [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-26 or the coarse range B05 to B12 of PRV-25) has no middle and no range to draw from. Its upper end is the user's own input, above the band's lower bound; where the user gives none, the candidate is not eligible in any run and is listed with the reason `open_top_band`. No upper end is invented or derived from protected rows, and the band's lower bound never stands in for the wage level. A band returned `SUPPRESSED` is a withheld figure: the candidate is not eligible in any run and is listed with that reason. ASSUMPTION: the base run's catchment limit (the middle of the range of `T`), so that each candidate has one band, the range the user sees. In a run, a candidate is eligible when its drawn rent is within the user's rent ceiling (QAR a month) or, where its cost range is of prices, its drawn price is within the user's price ceiling (QAR a square foot), and its drawn wage level is within the user's wage ceiling; a price is never compared with the rent ceiling, nor a rent with the price ceiling.
- The number of Monte Carlo runs `N` = 1,000 and the release seed; the Saltelli base sample of the Sobol runs, fixed at the slice that builds the card (ASSUMPTION).

**Formula.**

```
base run       every uncertain input at the middle of its range; the eligible candidates; the
               model's three sites S0
set cover      in the base run only, beside S0: the fewest eligible candidates that together reach
               every demand point within T, as a count; a demand point beyond T of every eligible
               candidate: NO_DATA (reason not_coverable), and S0 stands
shared reach   for each own branch k: the demand weight within T of k and of at least one site of S0,
               and its share of k's own covered weight (C7's shared-reach notion; never lost sales)
Monte Carlo    N runs with the release seed; each uncertain input drawn uniformly and independently
               from its range; in each run the model chooses its three sites S_r
holds          X = the number of runs with S_r = S0; a count of runs, never a share called a
               probability
Sobol          SALib's Saltelli design over the same ranges; at each design point the eligible
               candidates are found again and the model is solved again; Y = 1 when its three
               sites equal S0, otherwise 0 (the event that "holds" counts), never the objective
               value of a fixed S0; the total-order index of each input; "most sensitive to"
               names the input with the largest index, ties by input key; where Y takes one value
               over the whole design, no index is computed and no input is named (reason key
               holds_constant_in_design; MTH-09)
a candidate missing a criterion, with a withheld figure, or with an open median band and no upper
               end from the user, is not eligible in any run and is listed with its reason, never imputed
```

**Worked example (invented round numbers).** Maximal coverage with `T` = 10 minutes. Demand points d1 to d4 weigh 100, 200, 300 and 400. Within 10 minutes, candidate A covers d1 and d2, B covers d2 and d3, C covers d4, and D covers nothing (it reaches d1 in 12 minutes). The three sites are A, B and C, covering 1,000; the next best set, B, C and D, covers 900. Set cover on the same times: d1 is reached only by A, d3 only by B and d4 only by C, so the count is 3. If A were not eligible in the base run, no eligible candidate would reach d1 within 10 minutes: the count would be `NO_DATA` (`not_coverable`), and maximal coverage would still pick B, C and D (900). An own branch K covers d3 and d4 (700) within 10 minutes, and the three sites cover both, so K's shared reach is 700, all of its covered weight. Counting fixture: four listed runs choose {A, B, C}, {A, B, C}, {B, C, D} and {A, B, C}, so the choice holds in 3 of 4 runs. Sobol fixture: Y = 2 x1 + x2 with x1 and x2 uniform on 0 to 1 has variance 4/12 + 1/12 = 5/12, so the total-order indices are 0.8 for x1 and 0.2 for x2 and the result is most sensitive to x1; SALib's estimate must fall within a tolerance fixed at the slice. That fixture tests the estimator only. Rent fixture: in the example above, with `T` fixed at 10 minutes, the only uncertain inputs are the user's rent ranges, 0 to 100 for A and 0 to 50 for B, against the user's rent ceiling of 75. The base run (A at 50, B at 25) picks A, B and C. At a design point where A's rent is above 75, A is not eligible and the model picks B, C and D, so Y = 1 exactly when A's rent is at most 75: the total-order index is 1 for A's rent and 0 for B's, and the choice is most sensitive to the rent of A. The objective value of the fixed set A, B and C stays 1,000 at every point and would name no rent.

**Provenance and status.** The least-real class of the inputs (MTH-07); `inferred`, with the "your inputs" tag (MTH-06); caveats `your_inputs`, `ranking_not_advice` and `runs_not_probability`, and, where a run uses guide or recorded prices for a missing rent, `price_not_rent`. Subject `area` for each site; never a named building or business. Never written to the release or the ledger. **Compute cost.** Not yet timed: 1,000 runs of a small integer model, plus one solve of the model at each point of the Sobol design, at request time.

**Limits and wording.** The choice describes the stated model, demand layer and ranges, nothing else. A run count says how often the same three sites came out over the ranges the user set; it is not a probability, a confidence level or a chance of success. Guide and recorded prices are prices, not rents.

- Allowed: "On the criteria and ranges you set, the model picks these three sites. The choice holds in {X} of {N} runs over your ranges and is most sensitive to {input}. This counts runs of the model; it is not a probability." Where no index is computed (`holds_constant_in_design`), the second sentence reads: "The choice holds in {X} of {N} runs over your ranges; no input stood out in the sensitivity runs." With branches: "Your branch {label} shares {share} of the reach it covers within {T} minutes with the three sites."
- Never say: "best location", "you should open", "recommended", "probability", "chance", "confidence", "likely", "lost sales", "cannibalisation", or a rent for a guide or recorded price.

| ID | Requirement |
|---|---|
| MTH-114 | C40 chooses three sites by the model the user picks from the closed list (maximal coverage or p-median with p = 3), over eligible candidates of one kind, a demand layer of C12 and the travel times of C25; reports beside them the set-cover count of the base run, or `NO_DATA` with reason `not_coverable` when some demand lies beyond `T` of every eligible candidate, and never lets set cover choose the sites; reports the shared reach of each own branch; runs `N` = 1,000 seeded Monte Carlo runs and the Sobol design over the stated ranges, solving the model again at each design point, with Y the holds indicator and never the objective value of a fixed S0, and, where Y takes one value over the whole design, computing no index and naming no input (reason key `holds_constant_in_design`); and reproduces the fixtures (A, B and C covering 1,000 against 900; a set-cover count of 3, and `not_coverable` with B, C and D still picked when A is not eligible; K's shared reach 700; 3 of 4 runs; total-order indices 0.8 and 0.2 within the slice's tolerance, a test of the estimator only; in the rent fixture, indices 1 and 0 within the same tolerance with the rent of A named, which an output built on the objective of a fixed S0 fails; a candidate whose median band is B12 is eligible in no run and is listed with `open_top_band` while the user gives no upper end, and is drawn up to the user's upper end once given). The same release, inputs and seed give the same sites, counts and indices. |
| MTH-115 | The sentence of C40 states the count of runs ("holds in X of N runs") and the input with the largest total-order index, or, where no index is computed, that no input stood out (MTH-114), always beside C11's rank-stability bound where a rank is shown; it never states a percentage, a probability, a confidence level or a chance, and it never names a verdict ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 5; MTH-45). No protected figure is a demand weight (PRV-41); the wage level enters only as an eligibility ceiling on the released median band; the rent is the user's own input or, labelled as prices, the guide and recorded prices of C41, and never an invented rent; a drawn price is compared only with the user's price ceiling in QAR a square foot, never with the rent ceiling. |

### C41 Property price measures

**Purpose.** From the property sales bulletins of the Justice Ministry and the banks' credit by economic activity, show the price per square foot by district, use and quarter with deal counts and values, the guide land price against the recorded deal price, affordability against pay, and bank credit by sector against the sector's growth, with forecasts only through C30; and, beside the prices, how near a planned station is (journeys D2 and D5; decision 0023 items 3 and 8).

**Inputs.**

- In the public-data build only (MTH-02): the deal rows of `prop_sales` and `prop_resi_units` as C14 keeps them (crosswalk-matched district and positive price, with a positive area for every `prop_sales` deal and for the `prop_resi_units` deals of price basis `per_m2`; MTH-63), with property type and use read from the Arabic label and the usage field through a reviewed mapping table; the English labels are not used. The build releases only the aggregates of the formula below (by district, use and quarter: the median price per square foot with its deal count and deal value, the same median over the deals of land without a building with its deal count, and the median deal price of each unit type with its deal count; PUB-14), in `pub_property_quarter` ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) section 7.2). Its columns so far hold only the median price per square foot with its deal count and deal value; the other two aggregates wait for S2-T19 (Open questions). No deal row reaches the release or the product (ARC-16); the request-time measures read only these aggregates.
- The guide land prices by district of the national GIS centre's 2026 layer (decision 0023 item 3), by the use categories that layer publishes: `pub_land_price` ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) section 7.3), with its price basis as the layer states it.
- Public pay figures for the affordability ratio: the national mean monthly wage by occupation group of `pub_wage_table`, combined across the source's sex categories and weighted by paid workers, as C10 does (MTH-24, MTH-44); no affordability figure is computed from one sex's row or from a split by nationality (PUB-90). The released pay bands of residents and workers of an area stand beside it only.
- Bank credit by economic activity, `pub_bank_credit` ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) section 7.3), and a Public series of the same sector's growth, matched through a reviewed sector crosswalk. The growth series joins document 03 when [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) names it (Open questions).

**Formula.**

```
area in square feet = area in square metres / 0.09290304 (one foot is exactly 0.3048 metres), or the
               source's own square feet where it gives them
price per square foot   p = price_qar / area_ft2 for each kept deal with a positive floor area: every
               kept deal of prop_sales and only the prop_resi_units deals of price basis per_m2 (C14);
               per_unit deals carry no floor area and give no price per square foot: NO_DATA
by district, use and quarter:  median of p (an even count takes the mean of the two central values),
               deal_count = kept deals, deal_value = sum of price_qar; zero kept deals: NO_DATA
guide against deal      for one district, use and quarter, over the kept deals whose reviewed property
               type is land without a building only (a deal with a building or a residential unit is
               never set against the guide land price): p_land = median of their p, with their deal
               count; difference = p_land - guide price per square foot; ratio = p_land / guide price
               (DAT-134); only where both are per square foot; a use the mapping cannot match returns
               NO_DATA; no such kept deal returns NO_DATA (reason key no_land_deals)
affordability           years of pay = median deal price of a unit type / (12 * w), where w = sum over
               sexes of (paid workers * mean wage) / sum of paid workers for one occupation group of
               the Public wage table, never one sex's row (MTH-24, MTH-44); only on a median of price
               basis per_unit (a price per unit sold, unit qar); a median per square metre is never
               divided by a wage: NO_DATA; the released pay bands of the area's residents and
               workers stand beside it as their own facts, never in one number with a price (PRV-41)
credit against growth   credit growth = (C(y) - C(y-1)) / C(y-1) by sector; sector growth from its Public
               series the same way; both shown, with their difference and direction (DAT-134)
forecasts               only through C30, on the series that decision 0023 item 8 adds to its list: the
               quarterly median p by district and use, with its deal counts; a quarter with zero kept
               deals has no value, so the quarters before it are not used (C30's series rule)
no rent is computed, labelled or shown: rents have no open source
```

**Worked example (invented round numbers).** One district, residential use, one quarter, two deals of land without a building: one of QAR 1,000,000 for 2,000 square feet (500 per square foot) and one of QAR 1,500,000 for 2,500 square feet (600 per square foot). The median is 550, the deal count 2 and the deal value QAR 2,500,000. A floor area of 100 square metres is 1,076.39 square feet. Against a guide land price of 500 per square foot, the two land deals give a difference of 50 and a ratio of 1.10. An occupation group's two sex cells, 600 paid workers at QAR 9,000 and 400 at QAR 11,500, combine to a Public mean wage of QAR 10,000 a month; a unit price of QAR 1,000,000 against it is 8.33 years of pay. Credit of 100 then 110 is a growth of 10%; sector output of 200 then 210 is 5%; the difference is 5 points, direction higher.

**Provenance and status.** Public, `observed` (MTH-05); caveats `calculated` and `deal_count_shown`, `guide_price_not_market_price` on the comparison, and `price_not_rent` wherever a price stands near a cost input. Every price shows its deal count. Subjects: the district, `sector` or `national`. **Compute cost.** Trivial; not separately timed.

**How near a planned station is ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 3).** Beside the prices of the cost view of journeys D2 and D5, and on the map, tested code in `eii_core.calc` measures how near a planned station is, from `pub_rail_plan` ([04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) section 2.2). Distances are geodesic on the WGS 84 ellipsoid, as in C25.

```
site point p     the pin, or the representative point of a drawn shape (eii_core.shapes)
nearest station  the planned station k of pub_rail_plan with the least geodesic distance d(p, k),
                 ties by the layer's station key; shown with its published name and line
protection zone  whether p lies inside a protection zone of the layer, as published
no station in the layer: NO_DATA
the distance stands beside the prices as its own fact and never enters one number with a price
```

Fixture (not a place): two points on the equator at longitudes 0 and 0.01 degrees lie 1,113.19 m apart, the WGS 84 equatorial radius of 6,378,137 m times 0.01 × π / 180. With planned stations S1 and S2 at 1.2 km and 3.4 km from p, the nearest is S1 at 1.2 km; with no station in the layer, the result is `NO_DATA`.

The distance and the zone test are Public and `observed` (MTH-05), with the caveats `calculated` and `planned_not_operating`; their subject is `area`, the site. A planned station is a plan: it is never shown as operating, and no opening date, demand or price effect is computed from it.

- Allowed: "The nearest planned station, {station} on the {line} line, is about {distance} from this site in a straight line. It is planned, not operating."
- Never say: "metro access", "on the metro", "served by rail" or "the station will raise prices".

**Limits and wording.** Few deals sit in some districts and quarters, so a median moves with one deal. A guide price is a published valuation of land, not a market price; only deals of land without a building are set against it, because a deal with a building carries the building's value, and a district and quarter with no such deal shows no comparison. Affordability uses a national mean wage, not the pay of the area. Credit is a stock of lending, not investment or output.

- Allowed: "In {quarter}, the median recorded sale price for {use} in {district} was {price} a square foot over {count} deals worth {value}." "The 2026 guide land price here is {guide} a square foot; recorded sales of land without a building, over {count} deals, were {difference} {direction}."
- Never say: "rent", "the market will rise", "undervalued", "a bargain", "you can afford", a price without its deal count, or a ratio of a price to a protected pay figure.

| ID | Requirement |
|---|---|
| MTH-116 | C41 keeps deals as C14 does, converts areas by the exact factor 0.09290304, returns the median price per square foot with its deal count and deal value by district, use and quarter from deals with a positive floor area only (every kept `prop_sales` deal; of `prop_resi_units`, price basis `per_m2` only), the guide-against-deal difference and ratio over the kept deals of land without a building only, with their deal count (`NO_DATA` with `no_land_deals` where none is kept), affordability only on a median of price basis `per_unit` and against a Public mean wage only, the occupation group's mean of `pub_wage_table` combined across the source's sex categories and weighted by paid workers, never one sex's row (MTH-24, MTH-44), and credit growth beside sector growth with their difference and direction; a price per square foot of a `per_unit` median and years of pay of a `per_m2` median each return `NO_DATA` (a planted fixture of each), and medians of different bases are never compared or combined (MTH-63); it reproduces the fixture (550, 2 and 2,500,000; 1,076.39; 50 and 1.10; 10,000 and 8.33; 10%, 5% and 5 points), and a planted deal with a building added to the fixture's quarter leaves 50 and 1.10 unchanged. |
| MTH-117 | C41 shows no price without its deal count, computes and shows no rent and never labels a price a rent, combines no price with a protected pay figure in one number (PRV-41), reads property type and use only through the reviewed mapping of the Arabic label and the usage field, and forecasts only through C30. |
| MTH-121 | C41 shows how near a planned station is ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 3): the geodesic distance on the WGS 84 ellipsoid from the site's pin, or the representative point of a drawn shape, to the nearest planned station of `pub_rail_plan`, ties by the layer's station key, with that station's published name and line, and whether the point lies inside a published protection zone; `NO_DATA` where the layer holds no station. It is Public and `observed`, with `calculated` and `planned_not_operating`. A planned station is never shown as operating, no opening date, demand or price effect is computed from it, and the distance never enters one number with a price. It reproduces the fixture (1,113.19 m on the equator; S1 at 1.2 km; `NO_DATA` with no station). |

## 6. What would be theatre

"Theatre" here means a method whose output on synthetic or simulated data can only return what the generator or simulator was told. These must not be built on synthetic or simulated data, except in the labelled forms that a row below names ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) items 6 to 10), and most have no honest public substitute in v1.

| Method | Why it is theatre here |
|---|---|
| Gravity or Huff catchment calibration and capture shares (Huff 1964) | Calibration needs real outlets, customer origins and sales; none is public. The simulator places workplaces with a gravity model (see [05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md)), so fitting a gravity model to simulated movement recovers the simulator's own settings. A share computed by distance and an attractiveness that the user sets is the user's scenario (C34): it fits nothing, shows the user's outlet and the competitors split by competitor category and by distance band only, and a cell that holds a single competitor is merged into the next wider cell. Where a single competitor is still left after those merges, no split is shown, only the share of the user's outlet and the share of the competitors together; with one competitor in all, only the share of the user's outlet is shown and no share is stated for the competitors. It computes no figure for a named competitor. |
| Survival curves (Kaplan and Meier 1958) | Need each licence's issue and cancellation dates, held only in the register. On the synthetic register a survival curve returns the generator's assumption, so none is built from it. The Public licence tables count issues and cancellations without linking them, so the survival base rate of C31 returns `NO_DATA` until a Public table carries the cohort. |
| Entry rates and net formation | The open "issued" table holds 12,533 licences over 610 codes and no restaurant records, so entry is known only for the codes it covers: its issues are shown as published counts (C22), and the entry and closure base rates of C31 are computed from the Public tables only where they carry the numerator and the denominator. Net formation, issues minus cancellations, is never computed or shown. The openings and closures of register companies are shown only as two counts from the register's own dates and snapshots (C22; [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 12), never as an entry rate, a survival figure or net formation. |
| Shift-share (Dunn 1960) | Needs counts by area and activity at two dates; the public table is one snapshot (May 2025). On synthetic data it decomposes planted growth. A second real snapshot would make it real, so every refresh of the public table should be stored. |
| Labour-market tightness | About 2,988 unemployed against 2.36 million employed in 2025 and no public vacancy series (methods research); on synthetic records hiring and separation rates are parameters. Card C39 shows the talent pool and the jobs of the same occupation group within reach side by side, and the talent ratio of those two released figures (MTH-122). Tightness beyond that ratio stays theatre. |
| Multipliers from other economies' input-output tables | No official Qatari input-output or supply-use table was found; the OECD 2025 inter-country tables do not include Qatar. Another economy's coefficients beside Qatar facts would be read as Qatar facts. The real survey cost shares (C4) answer "what does this business buy". |
| Economic complexity or relatedness below national level (Hidalgo and Hausmann 2009) | Eight municipalities cannot support it. Even nationally, Qatar's distance to every non-exported product lies between 0.953 and 0.992 and 54% of export value is unclassified, so a ranking is close to noise. |
| Relatedness from synthetic co-licensing | Returns the generator's co-licensing rule. |
| Sales, revenue or demand forecasts, "spending power present", capture rates | A revenue or demand figure presented as a finding about a place or a named business, or a money figure of spending power, would multiply simulated presence by synthetic pay by an assumed rate, or divide a company's sales by presence; there are no sales data. Allowed in its place, only as [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) items 8 to 10 say: the site estimate of C33, with its low, middle and high cases, its main drivers and the label "estimate on simulated inputs"; and the user's scenarios of C34 and C35, never called forecasts, in which "capture rate" names only the user's own input. Still not built: success scores, a money figure of spending power, and any figure for a named competitor. Resident pay and presence stand side by side (C19), except the people present by pay band of C32 (PRV-126), and a sample file's figures are never divided by presence (C29). |
| Differences between two synthetic releases shown as trends | The difference is a seed or a parameter change, not a change in Qatar. Months inside the one window of one world are shown only as synthetic changes with the Synthetic mark (C20). |
| A seasonal check on the calibration years called a validation | The simulated shape is set from the same public shape, so agreement is built in. C26 is reported as the calibration fit F19 of document 05, never as a hold-out or a validation, and it tests no hourly presence, level or named place. |
| Traffic tuned until it matches a published congestion figure | Tuning the volume-delay parameters to a public figure makes any agreement circular (the plausibility comparison of [05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md) already warns of this). The parameters are fixed before any traffic is built (C25). A live provider's tile is never used to tune them either. |
| Success scores and policy-lever simulation | A score of how likely a venture is to succeed, or a simulation of what a policy lever would change, would return the generator's settings and read as advice. Neither is built ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 27). |
| A forecast of a protected or synthetic series in the product plane | On synthetic data a forecast continues the generator's settings, so it is never shown as a finding about Qatar. Allowed only in the labelled form of [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 6: C30 forecasts the released monthly series of the window from released rows only, with the Synthetic class, the word "forecast" and the caveats that synthetic months show the format, not Qatar; such a forecast is not a protected statistic of a later month and states no change between two months (PRV-54, ARC-130). A protected statistic of a month outside the window, and a series across windows, are still refused (PRV-54). |

| ID | Requirement |
|---|---|
| MTH-48 | No module in the repository implements any method in the table above against synthetic or simulated release tables, except the labelled forms that a row names as allowed: the forecasts of the released monthly series of C30, the site estimate of C33 and the user's scenarios of C34 and C35. The assistant's must-decline set includes a question for each part of a row that stays theatre, and a forecast it does not offer is declined under the class `forecast_not_offered`; a question about a listed series, a base rate, the site estimate or a scenario is answered by its own family (C30 to C35). |

## 7. Where the units are too few

| Geography | Units | Supports | Rules out |
|---|---|---|---|
| Municipality | 8 | location quotients, densities, churn rates | complexity and relatedness, clustering, hot-spot statistics, any correlation or regression across municipalities |
| Census zone | 91, of which 75 have at least 1,000 employed residents | similarity search and three coarse area types (C17), rank correlations | more than three area types: three types were moderately stable (silhouette 0.33; bootstrap adjusted Rand index 0.71), five and six were not (0.56 and 0.51) (methods research) |
| Grid cell | about 15,800 at H3 resolution 8 and 110,800 at resolution 9 nationally | protected statistics after pooling | any public statistic blended or apportioned onto cells or release units (PUB-29) |

| ID | Requirement |
|---|---|
| MTH-49 | No v1 screen shows a clustering of municipalities or a hot-spot map. The similar-areas search of C17 may show at most three area types, each with its stability figures, and only when those figures reach the thresholds fixed at slice S2 ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 18). |
| MTH-53 | No method asks for a finer privacy partition so that an area looks smaller. Coarseness is reported by the snap report and the survival report. The flagship pin and the default cut-offs (walk 5 minutes and drive 10 minutes) are confirmed only after the survival report of slice S5 exists. The 30-minute drive cut-off is not one of those defaults. Drive 20 and drive 30 exist only as `make_area` cut-offs in `staffing_and_pay`. Card C39's closed list 10, 20 and 30 minutes is named apart from those `make_area` cut-offs and is available in every playbook whose bundle calls `workers_within_reach` ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) items 1 and 17; [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-111). No drive-time catchment goes beyond 30 minutes, and a request above 30 minutes is refused (TST-256). |

## Open questions and assumptions

ASSUMPTIONS (each also marked where it is used):

1. Method functions live in `eii_core.calc` (MTH-01); the reliability cut point is 30, and there is no shrinkage (MTH-13, MTH-14).
2. Municipal residents for May 2025 come from `pub_population_municipality` for 2025 (111,282 and 3,219,982); no LQ below a local count of 10; the national share is fixed in the LQ interval (C1, MTH-16).
3. C6 is served by `scan_places`; its box, confidence filter and radius follow the research runs, and the seed is not yet recorded (section 2, C6).
4. C4: opening days default to 30; `U = 0` is break-even and is the default; mode A treats staff as varying with sales; mode B uses the user's staff cost. An incentive package changes only the rent or the staff cost; one package applies at a time, with at most one parameter per input, and a one-off amount is never spread over months (MTH-61, MTH-62).
5. The 1 GWh base filter for zone rankings (MTH-41). Basket lines follow PUB-42 and PUB-44 (MTH-30).
6. District population for C7 is read from `pub_census_district` and the centre is the centroid of `district.geometry`. The private-employer share is a proxy for coverage only when that census layer is licensed (C8).
7. C10: the statutory minimum is a rule row in `pub_wage_table`; the staffing area is a 30-minute drive, available only to `staffing_and_pay`; the public wage table is combined across sexes (MTH-24, MTH-44).
8. The rank-stability sentence states the guaranteed best and worst rank over the box of weights within `δ` of the weights used (MTH-45). It replaces the Dirichlet weight draws of the earlier design, whose share of draws would read as a probability.
9. C18: counts of people are apportioned by the 2020 population grid as relative weights, other listed counts by area, and Simulated counts by area inside the unit (MTH-74).
10. C21: a projection needs at least three points, the fewest that leave a scatter around the line to show; its horizon never exceeds its window, and a monthly window is whole years (MTH-82).
11. C25: all-or-nothing assignment on free-flow paths, with one volume-delay rule of the Bureau of Public Roads form, is the simplest form [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 8 asks for (MTH-89).
12. C27: the three presence segments are exclusive for each hour; document 05 is asked to confirm it (MTH-94).
13. C16: company fit lists use free-flow drive times to the drivable node nearest the centroid of the register company's `registered_cell`, which are Public; a list takes the Synthetic class only when the employee count, or a size band placed by it, enters as a criterion or filter (MTH-71, [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)).
14. The new release tables are named as document 04 names them; document 03 is the authority (MTH-59). The tables added by decision 0019 (`pub_venue_busyness`, `pub_night_lights`, `pub_place_fsq` and `pub_pop_agesex_grid`) follow the same rule. No release table of forecasts is added: every forecast of card C30 is computed at request time from release tables and is never written to the release.
15. C19 indicator 6 by sector: "sector" is the economic activity of the national activity table `wage_act`; its groups are the table's populated activity-by-sex cells, as C3 groups the occupation table by occupation and sex; a both-sexes total row is not read; and a cell populated in only one year of a pair gives `NO_DATA` (MTH-97).
16. C30, confirmed at the slice that builds it: the candidate list is seasonal naive, drift and simple exponential smoothing (a longer list needs a library pin); the one error measure is the mean absolute scaled error; the backtest minimum is at least three origins and at least twice the horizon of history at the first origin; the interval at each horizon runs between the smallest and the largest backtest error of the chosen candidate at that horizon, and the caption counts the backtest values that lie inside the range built from the other errors (MTH-98, MTH-99). Several listed series are short, and their forecasts return `NO_DATA` until the minimum is met.
17. C31: the closure base rate is C2's churn rate against the May 2025 stock, the one stock the tables carry; issues take C2's bulk rule over their own national monthly totals (MTH-101).
18. C33, confirmed at the slice that builds it: the cases are the 10th, 50th and 90th percentiles of the draws by the nearest-rank rule; the seed is the release seed; each uncertain parameter is drawn uniformly and independently from its range; the parameter ranges are the user's own typed ranges with no prefill ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 12; MTH-105, MTH-106).
19. C34 and C35: the ranges and settings are the user's stated, visible and editable inputs; C34 weights the frame cells of the catchment equally, and its distance bands are within 500 m, 500 m to 1 km, 1 km to 2 km and beyond 2 km of the outlet (MTH-107, MTH-108).
20. C36: an area takes the mean of the cell values whose centre lies inside it, each cell counted once; C38: a cell centre on the boundary counts as inside (MTH-109, MTH-111).
21. The places table `pub_place_fsq` is read one table at a time and never merged with `pub_place`; C12, C16 and C17 keep `pub_place` until a reviewed change (C6).
22. `places_fsq`: the files of the public copy that cover Qatar are found through the dataset's own metadata file, as the task that builds the fetcher confirms. The age of the copy is decided, not assumed: the owner decided on 2026-11-12 that this copy, dated 2025-01-10, is used for version 1 as it is, with no account and no newer release for now, and where a place of the copy disagrees with OpenStreetMap or Overture, which are current, the newer source wins (C6, [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 21).
23. C39: each flow line runs from a whole home municipality of `ha_home` to the site's drive-time area at the cut-off shown, snapped on `ha_work_count`. It is the coarsest released pair that keeps the site in view, and it never ends at one work unit (MTH-112, MTH-113). Whether this form meets the case "totals between district pairs" is the owner's question (OI-147).
24. C16: the zoning test of a parcel reads the zoning polygon that holds the parcel's representative point; the zoning measure and the distance to a planned station are geodesic on the WGS 84 ellipsoid, as C18 and C25 measure (MTH-118, MTH-119, MTH-121).

Open items from the master design that touch this document:

- OI-03: the two restaurant totals and the two wage-table means. C3, C4, the sector branch of C19, the site estimate of C33 and the revenue range of C35 stay hidden until it is closed (MTH-23, MTH-29, MTH-97, MTH-106, MTH-108).
- OI-04: closed for version 1 by [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 10. The census map layers enter the local release, each figure with its source and retrieval date, so C7 resident weights and C8 shares are release facts; the research examples of C12 and C17 still run outside every release. The coverage bar uses the finest admitted geography and names it, or returns `NO_DATA` (PUB-82). Any use beyond this internal project needs written licence terms ([17_DEPLOYMENT_HARDENING.md](17_DEPLOYMENT_HARDENING.md)).
- OI-11: privacy thresholds are proposals. C7 earners mode, C10, C15, C19, C39 and C40 inherit the exported tier; they do not set a second threshold. C22 reads no protected figure since [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 12.

Open questions:

- Which months besides the three named ones does the bulk rule flag, once the median is taken over the 125-month calendar (C2)?
- The Wilson count's period, the C5 HHI and trend, the C6 seed and remaining settings, the C7 coordinates and weights, and the C14 median prices in riyals are not pinned. slice S7 fails while any of them remains unpinned (MTH-03, MTH-51).
- The 30-minute staffing catchment has not been timed, so its cell range is not written on C10.
- The weight range `δ` of the rank-stability bound is fixed at slice S2 (MTH-45).
- C11: the closed criterion list (criterion key, owning card, release table, default direction and the candidate kinds it applies to) is fixed at slice S2 under MTH-65; `area_ranking` in [08_BACKEND.md](08_BACKEND.md) offers only its entries. The forecasts of C30, the base rates of C31 and the site estimate of C33 that may be criteria join it there, each with the geography its series allows.
- C16: the reviewed relation that gives an activity its prospects, partners, suppliers and complementary activities is reviewed at slice S2, and document 03 holds it in the activity spine.
- The apportioning weight is fixed by C18. Slice S2 confirms the population grid's file and licence for this use, and document 04 lists the use ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md)). The slice that fetches `worldpop_qat_agesex` confirms the file, age bands and year of C38 the same way.
- C12: the decay form, the cut-offs of each mode, the supply layers, and the modes and presence keys that `access_score` stores (with the largest cut-off of each mode, which bounds `travel_time_matrix`) are fixed at slice S2 (DAT-151, DAT-153). The population grid is a demand layer only once document 04 lists that use; its scores are stored at free flow in the Public table `access_score_grid` of both release kinds (DAT-154), while `access_score` and `travel_time_matrix` exist only in a protected release.
- C17: the feature list, the seed, the restarts, the bootstrap draws and the two stability thresholds are fixed at slice S2.
- C25: α, β, the speed floor, the free-flow speeds and the capacities by road class, and the number and edges of the volume bands, were fixed at slice S1, with their sources, by [decision 0021](decisions/0021-one-speed-for-a-link-and-an-hour.md); the free-flow speeds, the capacities and the band edges are assumptions (OI-123). Documents 03 and 05 must state that the released hourly flows are vehicle trips; until they do, C25 returns `NO_DATA` (MTH-88).
- C26: τ and the complete years of the public shape are fixed at slice S1 with F19 (document 05), and so are the hourly tolerance, the minimum number of venues of a pooled shape and the constants of the weather modulation.
- C21: the reviewed list of projectable series, with each window and horizon, is fixed at slice S2.
- C30: the closed, versioned list of forecastable series, Public and released, with each source or release table, period and horizon, and the closed candidate list are fixed at the slice that builds the card. OPEN: the Public source of each series of decision 0019 item 2 for which the public data pack holds no table yet; such a series returns `NO_DATA` until it does.
- C31: OPEN: a Public table that links licence cancellations to their issue cohort; until one exists, the survival base rate returns `NO_DATA` with `no_denominator`.
- C33: the number of draws and the parameter keys are fixed at the slice that builds the card and written in the release's method note; no default range exists ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 12).
- C34: the defaults of the distance exponent and the distance floor are fixed at slice S2.
- C36: the quality-flag rule of the night-time radiance product is fixed at slice S2.
- C13 and C24: the tariff-line crosswalk (with its source and licence) and the size-class crosswalk are reviewed at slice S2.
- C28 and C4: the page structures of the dashboard and of the agency's pages, the capex currency, and the incentive parameter kinds the pages carry are confirmed at slice S2 ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)).
- Document 03 holds what these cards write and read: the release tables `access_score` (C12, DAT-151), `access_score_grid` (C12, DAT-154) and `zone_type` (C17, DAT-152), the manifest artefact `travel_time_matrix` (C12, DAT-153), the column `stayer_wage_index` decimal(7,1) of `month_change` (C19, DAT-137; no stayer wage bill is released), the column `price_basis` of `pub_property_resi` (C14: `per_m2` or `per_unit`) and the `traffic` field of the area record, which names a dial situation and its summer setting whose link times C25 averages over the situation's hours (section 9.2). It also holds the provenance note of a traffic-aware drive-time area of the live provider (provider, request, retrieval time and response hash; C25), the release tables `pub_venue_busyness` (C37), `pub_night_lights` (C36), `pub_place_fsq` (C6) and `pub_pop_agesex_grid` (C38), and, for [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md), `pub_property_quarter`, `pub_land_price` and `pub_bank_credit` (C41). Forecasts of C30 are computed at request time from release tables and are never written to the release.
- Document 03 must define fact units for people per square kilometre (C27), kilometres per hour (C25) and night-time radiance in nanowatts per square centimetre per steradian (C36), a geography kind for a drawn shape, the release tables of presence counts, hourly flows and link speeds, the register snapshots of DAT-164 (the synthetic births and closures are withdrawn by decision 0023), and the caveat keys this document adds: `access_not_use`, `apportioned_estimate`, `editorial_crosswalk`, `establishment_survey`, `licence_not_capacity`, `openings_incomplete`, `permit_not_start`, `seasonal_shape_only`, `similar_on_features_only`, `forecast_backtest_range`, `estimate_on_simulated_inputs`, `scenario_not_forecast`, `base_rate_not_your_chance`, `present_by_pay_band_assumed`, `relative_busyness_not_people`, `night_lights_not_activity`, `live_traffic_provider` and `grid_cells_summed` (MTH-11, MTH-59), and the reason keys `series_too_short`, `no_denominator` and `forecast_below_zero`.
- The slice that builds each card added by decisions 0016, 0017, 0019 and 0023 is set by [14_IMPLEMENTATION_PLAN.md](14_IMPLEMENTATION_PLAN.md); its gate pins the card's data tests (MTH-60), and the cards join the matrix of TST-197.
- Settled by [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 12: the synthetic births and closures of C22 are withdrawn and replaced by the register's own dates and monthly snapshots (MTH-85); establishments by area are a Public count of register companies, and whether their forecast joins the list of C30 is fixed with that list.
- OPEN ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md)): the reason and caveat keys of C16, C22, C33 and C39 to C41 and the fact rows of C39 to C41 are defined in [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) (DAT-90, the caveat-key table, DAT-165 to DAT-168). The metric keys of the zoning measure (MTH-119) and of the distance to a planned station (MTH-121) join its section 9 at S6-T12 and S6-T10 (MTH-11, MTH-59). The caveat that named an adjusted figure of C39 is withdrawn (MTH-122).
- OPEN ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md)): the tolerance of the Sobol fixture and the Saltelli base sample of C40, and the use crosswalk between the guide prices and the deal rows and the sector crosswalk of credit of C41, are fixed at the slice that builds each card.
- OPEN ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 8): `pub_property_quarter` holds the median price per square foot with its deal count and deal value. The median over the deals of land without a building and the median deal price of each unit type, each with its deal count, which C41 reads, are not yet among its columns. S2-T19 confirms them at the first fetch, with the columns of `pub_land_price` and `pub_bank_credit` and the sector growth series ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md), Open questions); until then the measures that read them return `NO_DATA`.
- OPEN ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) items 3 and 12): the reviewed mapping of the activity spine to the use categories of `pub_zoning`, the building footprints and their date that the empty test of a parcel reads (the basemap's buildings of PUB-106), and the columns of `pub_parcel`, `pub_zoning`, `pub_address_point` and `pub_rail_plan` are fixed at S2-T19 and at the slice that builds C16 (MTH-118, MTH-119, MTH-121). Until then no plot takes a label, and the zoning measure and the distance to a planned station return `NO_DATA`.
- ANSWERED (owner, 2026-11-14; [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 1; OI-140): the owner answered yes. The talent ratio of card C39 is the quotient of the two released figures for the same occupation group and cut-off (MTH-122), the one exception to PRV-30 and PRV-18. It is never called competition-adjusted and never an index. The two-step floating catchment is not used.
- OPEN (owner; OI-147): whether a commute line from a whole home municipality to the site's snapped catchment meets the case "totals between district pairs" (assumption 23; PRV-131). Until the owner answers, card C39 draws that form and no finer one.
- OPEN ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) items 1 and 15): the Qatarization planner of journey D5 (which roles Qataris hold in the private sector, at what pay, and where the talent is by district) has no method card yet. When it is written, it follows the cases of item 1 (MTH-113) and reads the Qatari and non-Qatari split only from the released nationality-group breakdown of PRV-09, once document 06 configures it at slice S5.
- OPEN ([decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 13): hot and cold spots, the "what changed this month" card and primary-care access are listed "if time allows". Each gets its method text when its task is named, and MTH-49 stands until the task that builds hot and cold spots is named and its card is written.
- OPEN (owner, [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 12): whether the road traffic of C25 is part of the movement source.
- OPEN (decision 0022): the geography, partition and release rules of pay by sector with middle ranges from the attached records (decision 0022 item 3, journey D5); until [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) sets them, no card computes it and C19 is unchanged.
- OPEN (decision 0022): which code list the activity on a register company's card follows, and so how the reviewed relation of C16 reaches it ([05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md) Q14).
- OPEN (decision 0022): the note of C6 that absence of a place may be a data gap compares the open places extract with a census count of establishments; whether it is restated against the register's count once the register file is read.

## Sources

All retrieved 2026-11-11 unless stated. Research figures were gathered on 2026-11-11 by the project's economic-methods, graph, public-data and feasibility reviews from the sources below.

Qatar Open Data Portal (CC BY), dataset pages under https://www.data.gov.qa/explore/dataset/:

- Licences (Ministry of Commerce and Industry): `moci-active-certificates-by-municipality-and-business-activity`, `moci-canceled-certificates-by-municipality-and-business-activity`, `moci-issued-certificates-by-municipality-and-business-activity` (the last only to show it is incomplete).
- Population and wages (National Planning Council): `population-and-labour-force-by-municipality`, `workers-in-paid-employment-15-years-and-above-and-monthly-average-wage-q1` (by occupation), `workers-in-paid-employment-15-years-and-above-and-monthly-average-wage-q` (by activity).
- Restaurant sector accounts (National Planning Council): `hotels-and-restaurants-statistics-economic-indicators-in-hotels-and-restaurants-by-activity1`, `hotels-and-restaurants-statistics-estimates-of-intermediate-goods-value-in-hotels-and-restaurants-by0`, `hotels-and-restaurants-statistics-estimates-of-intermediate-services-value-in-hotels-and-restaurants0`, `hotels-and-restaurants-number-establishments-employees-by-size-of-establishment-economic-activity`.
- Imports (National Planning Council): `qatar-imports-2025-2026`, `qatar-imports-2019-2024-copy`.
- Utilities: `electricity-total-consumption-by-zone-number`, `water-total-consumption-by-zone-number`.
- Property sales (Ministry of Justice): `weekly-real-estates-sales-bulletin`.
- Trade by product group (the research example of C13, not used in v1): `trade-data-for-pharmaceutical-products`.
- Added by [decision 0017](decisions/0017-public-data-additions-and-public-splits.md), CC BY 4.0, metadata retrieved 2026-11-12; every slug is listed in [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) section 2: visitors of museums and exhibitions by month (`visitors-of-museums-and-exhibition-by-month-and-museum`, C26); building permits and completion certificates (`permits_muni`, C23); establishments and employees by size and activity (`est_size_act`, C24); manufacturing industries and main products (`mfg_industry`, C13), including `manufacture-of-basic-pharmaceutical-products-and-pharmaceutical-preparations`; certificates of origin and arriving vessels (`trade_logistics`, C13); labour force by sex and municipality (`lf_muni_sex`, C21); residential unit sales (`weekly-residential-units-sales-bulletin`, C14).

Investment sources, used under the publisher's own terms as read at fetch, on the basis of the owner's decision of 2026-11-12 for this personal internal project ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)):

- FDI Projects dashboard of the national investment promotion agency, data from fDi Markets, read 2026-11-12 (C28): https://fdiprojects.invest.qa/
- The agency's sector, opportunity, incentive, set-up and law pages (C4 incentive inputs): https://www.invest.qa/

Sources added by [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md), pages read 2026-11-12 without any key; [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) holds each with its publisher, licence or terms and retrieval date:

- TomTom Traffic API, live flow tiles and reachable range (`traffic_tomtom_flow`, `traffic_tomtom_range`; C25, off by default; nothing of a response is stored; attribution "© TomTom"): https://docs.tomtom.com/traffic-api/ ; pricing and free allowance: https://docs.tomtom.com/pricing ; copyright: https://developer.tomtom.com/tomtom-orbis-maps/documentation/copyright . The developer terms page needs a login and was not read.
- Google Maps popular times (`busy_gmaps`; C26, C37): no licence for reuse stated; used on the owner's decision of 2026-11-12 for this personal internal project, with `licence_basis: owner_decision` under PUB-12; the publisher's terms read: https://support.google.com/business/answer/6263531 , https://policies.google.com/terms and https://www.google.com/intl/en/help/terms_maps/ .
- NASA Black Marble VNP46A3, monthly night-time radiance (`ntl_blackmarble`; C36), DOI 10.5067/VIIRS/VNP46A3.002, NASA acknowledged as the source: https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VNP46A3/ ; data and information policy: https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-information-policy
- Foursquare Open Source Places (`places_fsq`; C6, C33, C34; Apache 2.0): the access page, https://docs.foursquare.com/data-products/docs/access-fsq-os-places ; fetched from the public copy on Source Cooperative, geospatially partitioned GeoParquet read without an account, whose README states the Apache License, Version 2.0 and whose listing holds three dated releases, the newest dated 2025-01-10, and states no update rhythm: https://data.source.coop/fused/fsq-os-places/README.md and https://data.source.coop/fused/fsq-os-places/ . The registry records the release used.
- WorldPop age and sex structures, 100 m (`worldpop_qat_agesex`; C38; CC BY 4.0; DOI 10.5258/SOTON/WP00841): https://hub.worldpop.org/project/categories?id=8 and https://hub.worldpop.org/geodata/listing?id=138
- Open-Meteo historical weather (`weather_openmeteo`; C26 weather profiles; free interface for non-commercial use, data CC BY 4.0, with the attribution the publisher asks for): https://open-meteo.com/en/terms , https://open-meteo.com/en/licence and https://open-meteo.com/en/docs/historical-weather-api . Any use beyond this internal project is settled by [17_DEPLOYMENT_HARDENING.md](17_DEPLOYMENT_HARDENING.md).

Other public sources:

- Statistics authority Census 2020 zone and district layers (no licence stated; OI-04): https://services7.arcgis.com/mffQJB8rpVa5We20/arcgis/rest/services/Population_by_Major_Economic_Sectors_by_Zone_2020_WFL1/FeatureServer and https://services7.arcgis.com/mffQJB8rpVa5We20/arcgis/rest/services/Population_2020_District_Level/FeatureServer
- Overture Maps Foundation places, release 2026-10-21.0 (CDLA Permissive 2.0): https://docs.overturemaps.org/guides/places ; OpenStreetMap Qatar extract (ODbL): https://download.openstreetmap.fr/extracts/asia/qatar-latest.osm.pbf
- International Labour Organization, "Qatar adopts non-discriminatory minimum wage" (Law No. 17 of 2020), checked 2026-11-11: https://www.ilo.org/resource/news/qatar-adopts-non-discriminatory-minimum-wage
- United States Department of Justice, Herfindahl–Hirschman Index definition, checked 2026-11-11: https://www.justice.gov/atr/herfindahl-hirschman-index
- OECD inter-country input-output tables 2025, annex country list: https://www.iioa.org/conferences/32nd/papers/files/5640_ICIO-tiva-ghg2025annex.pdf
- WorldPop, constrained 100 m population, 2020 (CC BY 4.0), used by C18 and C12 as weights only: https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2020/QAT/v1/100m/constrained/

Method references (DOI links; the three marked were checked 2026-11-11; the references added on 2026-11-12 were not checked):

- Kitagawa (1955), components of a difference between two rates: https://doi.org/10.1080/01621459.1955.10501299
- Isserman (1977), location quotient: https://doi.org/10.1080/01944367708977758
- Wilson (1927), probable inference (checked): https://doi.org/10.1080/01621459.1927.10502953
- Benjamini and Hochberg (1995), false discovery rate (checked): https://doi.org/10.1111/j.2517-6161.1995.tb02031.x
- Leslie and Kronenfeld (2011), the colocation quotient (checked): https://doi.org/10.1111/j.1538-4632.2011.00821.x
- Applebaum (1966), trade areas: https://doi.org/10.2307/3150201 ; Luo and Wang (2003), two-step floating catchment: https://doi.org/10.1068/b29120
- OECD and JRC (2008), composite indicators handbook: https://doi.org/10.1787/9789264043466-en ; Saisana, Saltelli and Tarantola (2005): https://doi.org/10.1111/j.1467-985X.2005.00350.x
- Huff (1964), trading areas: https://doi.org/10.2307/1249154 ; Kaplan and Meier (1958): https://doi.org/10.1080/01621459.1958.10501452 ; Dunn (1960), shift-share: https://doi.org/10.1111/j.1435-5597.1960.tb01705.x
- Eurostat and OECD (2007), business demography manual: https://doi.org/10.1787/9789264041882-en ; Hidalgo and Hausmann (2009), economic complexity: https://doi.org/10.1073/pnas.0900943106
- Bureau of Public Roads (1964), Traffic Assignment Manual, U.S. Department of Commerce: the volume-delay form of C25 (no DOI); the sources of C25's version-1 values are listed in [decision 0021](decisions/0021-one-speed-for-a-link-and-an-hour.md)
- Goodchild and Lam (1980), areal interpolation, Geo-Processing: the area weighting of C18 (no DOI)
- Lloyd (1982), least squares quantization (k-means): https://doi.org/10.1109/TIT.1982.1056489 ; Arthur and Vassilvitskii (2007), k-means++ (ACM-SIAM Symposium on Discrete Algorithms; no DOI)
- Rousseeuw (1987), silhouettes: https://doi.org/10.1016/0377-0427(87)90125-7 ; Hubert and Arabie (1985), comparing partitions (adjusted Rand index): https://doi.org/10.1007/BF01908075
- Hyndman and Koehler (2006), mean absolute scaled error, the error measure of C30: https://doi.org/10.1016/j.ijforecast.2006.03.001
- Added by decision 0023, not checked: Hakimi (1964), p-median: https://doi.org/10.1287/opre.12.3.450 ; Church and ReVelle (1974), maximal covering location: https://doi.org/10.1007/BF01942293 ; Toregas, Swain, ReVelle and Bergman (1971), location set covering: https://doi.org/10.1287/opre.19.6.1363 ; Sobol' (2001), global sensitivity indices: https://doi.org/10.1016/S0378-4754(00)00270-6 ; Saltelli (2002), sensitivity indices from model evaluations: https://doi.org/10.1016/S0010-4655(02)00280-1 . The libraries PySAL `spopt` (BSD-3) and SALib (MIT) are read and pinned at the task that uses them (C40). C39 uses no library. The talent ratio is the quotient of the two released figures (MTH-122), and PySAL `access` is not used.
