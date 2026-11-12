# 07 — Economic Methods

| | |
|---|---|
| Status | Draft v0.3, amended by decisions 0016 and 0017 on 2026-11-12 |
| Date | 2026-11-12 |
| Owner | albarami |
| Purpose | Define every economic, location, footfall, traffic and labour-market method the product computes: inputs, formula, worked example (a regression test), provenance, honesty limits, allowed wording and measured cost. |
| Read first | [01_PROJECT_BRIEF.md](01_PROJECT_BRIEF.md), [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md), [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md), [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md), [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) |

## In brief

- Twenty-nine version 1 (v1) method cards and a list of methods that must not be built. [Decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) moved the three later cards (C11 ranking, C12 reachable access, C13 imports against local production) into v1. Decisions 0016 and [0017](decisions/0017-public-data-additions-and-public-splits.md) added C16 to C29 and amended C3, C4, C7, C14 and C15. No later card remains.
- Every method is a small, pure, tested function. Nothing here needs a GPU, a graph server or a spatial database to compute; every method the research timed ran in about three seconds or less on a CPU. The traffic assignment and the national travel-time matrix are not yet timed.
- A pinned worked example is a regression test that must pass in slice S7. An example whose inputs are not yet pinned is an illustrative note, and the slice S7 gate fails while it stays unpinned. A card added by decisions 0016 and 0017 has a fixture test now and is pinned at the gate of the slice that builds it (MTH-60).
- Public methods produce real findings about Qatar. Methods run on Synthetic or Simulated layers show a format and a protection, never a fact about a place.
- Rankings, fits and suggestions are tested code over criteria and weights the user can see and change, and every rank has a rank-stability sentence. None is a verdict, a probability, a confidence claim, advice to act or a revenue, demand or success forecast.
- Figures from the protected record types snap to whole release units, with the snap sentence. Public points and Simulated layers are computed for the exact shape the user draws. A Public statistic or a released Simulated count reaches that shape only through apportioning (C18), and the result is labelled Inferred.
- Presence is an estimated count of people with a range, hour by hour (C15, C27). Its seasonal shape is calibrated and checked against published museum visitor counts (C26). Traffic is a simple Simulated road assignment (C25).
- Several attractive methods would only return the generator's own assumptions on synthetic data. They are listed under "What would be theatre" and are not built.
- Qatar has eight municipalities and about 75 usable census zones. That rules out area typologies beyond three types, complexity below national level and hot-spot statistics.

## 1. Common rules

- **Licence-activity count**: one activity on one commercial licence, as counted in the public licence tables. It is not a firm and not a job.
- **Worked example**: a calculation with real published figures, written here so that a test can reproduce it.
- **Calculated**: a value obtained by fixed arithmetic from published figures, not published itself.
- **Fixture**: invented inputs of an arithmetic test, labelled as such. A fixture is never a figure about a place or a source.
- **Apportioning**: moving a count published on an official geography, or a released Simulated count, onto a drawn shape by a stated weight (C18). The result is an estimate, labelled Inferred.
- **Projection**: a straight-line continuation of a published or released series over a stated window (C21). It is not a forecast.

| ID | Requirement |
|---|---|
| MTH-01 | Every displayed number is produced by deterministic tested code in `eii_core.calc`, the release build, or a fixed application-schema read function listed by the data contracts and covered by tests. Nothing else computes, rounds or compares a number, and no model ever does. Each method in this document is a deterministic function in `eii_core.calc` (package `core/`). It does not read a file, the network or a database; callers pass the rows. The custodian build and the product plane call these functions. The browser never computes a displayed number; it formats values it receives. A comparison (difference, ratio, rank or direction) is itself a calculation fact. ASSUMPTION: `core/` is the only package both planes may import, so this is the one place a method can be shared. |
| MTH-02 | Build-time methods run in the custodian plane and write facts into the release: location quotient, churn, decomposition, co-location, coverage, zone momentum, property-sale median, the public series of C13 and C21 to C24, the project counts of C28, the area types of C17 (release table `zone_type`), the access scores of C12 for fixed supply layers, cut-offs and hours (release table `access_score`, with the travel times they use in the manifest artefact `travel_time_matrix`, and, for the population-grid layer at free flow, the Public release table `access_score_grid`), the fixed-composition wage index of C19 (`month_change.stayer_wage_index`, PRV-55), the national wage trends by sector of C19 with their split (MTH-97), the traffic assignment of C25 (over released flows only, after the privacy engine) and the seasonal calibration measure of C26. Request-time methods run in the product plane over release tables only, by calling `eii_core.calc`: the break-even calculator with its incentive inputs, shared reach, band lookup, area presence counts and crowd density, rankings and fits with their stability sentences (C11, C16), similar-area search (C17), area access summaries (C12), apportioning (C18), area income indicators and their monthly changes (C19, C20), changes of Public series (C20), projections of released synthetic series (C21), synthetic births and closures over an area (C22), drive times and drive-time areas by hour (C25) and sums over a sample file (C29). The only application-schema arithmetic is in the fixed read functions listed by the data contracts and covered by their regression tests. |
| MTH-03 | A worked example whose inputs, settings and expected result are all written in this document has two tests: an arithmetic test that feeds those inputs into the function and asserts the stated result within the stated tolerance, and a data test that recomputes the same figure from the pinned public file built in slice S2. Regression values that the pack cannot pin today (for example the riyal medians of the property-price method card and the other inputs listed here) are produced by `./eii build-public` at slice S2, checked against the source by the reviewer, and written into the method cards by a slice S2 task; slice S7 fails while any remain unpinned. No value is invented. Four examples are illustrative notes, not passing regression examples, until they are pinned: the Wilson count's period (section 3), the C5 HHI and trend, the C6 seed and full settings, and the C7 coordinates, modes, cut-offs, speed regime, district weights and expected shares. The C14 median prices in riyals are in the same state (MTH-51). |
| MTH-04 | When a data test does not reproduce a worked example, the builder must record the difference in `OPEN_ITEMS.md` and stop. Parameters must not be tuned until the number matches. |
| MTH-05 | A value computed by fixed arithmetic from Public release tables carries provenance `public`, evidence status `observed` and the caveat key `calculated`. An interpretation of such a value (for example "these months look administrative") carries evidence status `inferred`. |
| MTH-06 | A figure computed from the user's own inputs carries evidence status `inferred` and the "your inputs" tag, takes the least-real class of its release inputs as provenance, and is never written to the release or to the ledger as a fact. |
| MTH-07 | A composite of release inputs takes the least-real class of its inputs, computed in code by the shared provenance helper; the method never sets the class by hand. |
| MTH-08 | Every fact a method produces carries a complete source chain: the fact, its release table, the method and version, then the source (publisher, dataset, licence, retrieval date and file hash). The fact names its source table in `lineage_ref`. Where two public tables could give the same quantity, the fact names the one used. A fact without a complete chain is not emitted: the release build fails on it, and the Fact chip refuses it. The evidence drawer is labelled "Source chain". The Arabic label proposed, pending the owner's review, is "السند". |
| MTH-09 | Methods return a value or a status; they never return zero for an unknown. A missing input yields `NO_DATA` with a reason key, and the card shows the reason. |
| MTH-10 | Allowed wording is implemented only as application-owned English and Arabic claim templates. Each brief item carries a `claim_key` and typed fact slots. `layout[]` is an ordered list of component instances. The model may select and order catalogue claims, components and fact ids only; no model-written prose reaches the screen. Component properties are fact ids, release-unit ids or enumerations. One invalid item rejects the brief; one repair attempt; then the template writer uses the playbook's default selection. An `area` subject accepts Public, Synthetic, Simulated and Inferred facts. A claim whose subject is `place_public` or `fdi_project` may have Public slots only; a `synthetic_firm` subject accepts Synthetic slots only; no other subject accepts a Synthetic or Simulated slot ([AGENTS.md](../AGENTS.md) rule 8; [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 20; [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 9). A build-time scan of the templates rejects numerals, number words, names of real places inside `area` claims, and go or no-go wording, including each card's "never say" phrases. |
| MTH-11 | Caveat keys named in this document (in backticks, for example `calculated`) must exist in the release caveat catalogue with English and Arabic text. If [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) names the catalogue differently, that document wins and the meaning here stands. |
| MTH-54 | Before an answer is shown, code runs the accounting gate's five checks: sources, assumptions, nothing invented, scope, and limits stated. A method fact supplies what those checks read: the source chain (MTH-08), the evidence status (`observed`, `inferred` or `still_to_test`), the "your inputs" tag where the figure uses the user's inputs (MTH-06), and the caveat keys. The method does not set an inferred item's strength; the claim catalogue does. If a check fails, the template writer's default answer is shown. The receipt labels the result "Checked before display". The Arabic label is pending the owner's review. |
| MTH-55 | Each derived statistic normally names exactly one home family in its fact lineage, as section 6.2 of [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) defines (PRV-30). The only exception is the closed list of ratio statistics: mean wage and the coverage, irregular and deployed-elsewhere shares. A ratio statistic takes its numerator and denominator from columns of the same stored rows — one table, one partition, one unit set and one measure where the table has measures — even where those columns belong to two additive families; its fact lineage names both families. Mean wage divides `wage_bill` by `earner_count` on the same stored `ALL` rows of `worker_pay` on `wp_all_money` or `resident_pay` on `rp_all_money`. The three side-count shares divide the applicable side-count column by `earner_count` on the same stored `ALL` rows of `resident_pay` on `rp_housing_count` or `worker_pay` on `wp_site_count`. Earner count on a worker card uses `worker_pay` and `wp_all_count` with no breakdown; earner count on a resident card uses `resident_pay` and `rp_all_count` with no breakdown. Wage bill uses that table's money partition. Band shares, the median band and quartile bands use that table's band partition (`wp_all_quartile` or `rp_all_quartile`), and the count beside those shares is that same family's total. A housing count and the housing shares beside it use `resident_pay` and `rp_housing_count` with the housing-class breakdown. An occupation count and the occupation shares beside it use `occupation_pay` and `op_res_quartile` with the occupation-group breakdown. C7 earners mode uses one selected count family, `resident_pay` on `rp_all_count` or `worker_pay` on `wp_all_count`, for both the weight and the share. C15 and C27 use the released presence counts of one segment from one partition (PRV-58); C27's all-people sum adds the three segments of one complete group and never reads a stored total. No method returns two routes to one population as two numbers. |
| MTH-56 | A method that reads a figure of the protected record types (business register, employment, residence, wages) takes a snapped area of whole release units from `make_area`, shown with the snap sentence of DES-101 in [11_DESIGN_DIRECTION.md](11_DESIGN_DIRECTION.md), before any figure is read (BE-54). Public point layers and Simulated layers are computed for the exact shape the user drew, set by radius, or chose by walk or drive time and hour. A statistic published on an official geography is shown on that geography; a method puts it, or a released Simulated count of a release unit, on a drawn shape only through C18, and the result is `inferred`. No Public figure is apportioned to grid cells or release units or blended into a protected figure (PUB-29) ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) items 6 and 17). |
| MTH-57 | A ranking, fit or suggestion (C11, C16, C17) is the output of tested code over criteria, directions and weights the user can see and change, and every rank stands with its rank-stability sentence (MTH-45). It is never a verdict, a probability, a confidence claim, advice to act, or a revenue, demand or success forecast, and its weights are labelled a judgement ([AGENTS.md](../AGENTS.md) rule 25). A real business from public listings or an FDI project is never scored or fitted; a list of them is ordered by distance only, a Public figure (PUB-92). No Public split by sex or nationality is a criterion (PUB-90). |
| MTH-58 | An estimate, that is an apportioned figure (C18) or a projection (C21), carries evidence status `inferred`, and so does every value computed from an `inferred` input or from the user's inputs (MTH-06). A value computed by fixed arithmetic from release tables, Synthetic and Simulated ones included, is `observed`. That means read from the release, not real: its class still marks it (DAT-91). |
| MTH-59 | Release tables, caveat keys, fact units and subjects added by decisions 0016 and 0017 are named here as [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) and [09_AI_ASSISTANT.md](09_AI_ASSISTANT.md) name them, or described where no name exists yet. [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) is the authority: where it names one differently, that document wins and the meaning here stands, as for caveat keys (MTH-11). |
| MTH-60 | Each card added by decisions 0016 and 0017 has an arithmetic test on the fixture written in the card now, and a data test pinned from the release by the slice that builds the card. The gate of that slice ([14_IMPLEMENTATION_PLAN.md](14_IMPLEMENTATION_PLAN.md)) fails while a regression value the card lists as unpinned stays unpinned. MTH-03 and MTH-04 apply unchanged, and the card's requirement IDs join the test matrix of TST-197. |

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
| C16 Reverse fit and fit lists | journeys D2, D3 and D4 | `activity_fit`, `synthetic_firms` | least-real class of the criteria; Synthetic for firm lists |
| C17 Similar areas and three area types | journey D2 | `similar_areas` | Public |
| C18 Apportioning to a drawn shape | every journey with a drawn shape | `area_evidence` | the input's class; Inferred |
| C19 Six income indicators and pay versus mix by month | journeys D1, D2 and D5 | `area_evidence`, `pay_benchmark`, `what_changed`, `labour_facts` | Synthetic; Public for indicator 6 by sector |
| C20 What changed between adjacent months | journeys D5 and D6; service S2 | `what_changed` | the compared facts' class |
| C21 Labour-market projections | journey D5 | `labour_facts` | the series' class; Inferred |
| C22 Openings and closures over time | journey D6 | `openings_closures` | Public; Synthetic for synthetic births and closures |
| C23 Construction pipeline | journey D6; the reverse view | `area_evidence` (`public_context`) | Public |
| C24 Employer scale and wage bill by activity | journeys D1 and D3; service S1; cases C1 and C2 | `sector_facts` | Public |
| C25 Traffic assignment and drive times by hour | journeys D2 and D7 | `make_area`, `travel_times`, `area_evidence` (`traffic`), `stage` | Simulated; Public at free flow |
| C26 Seasonal calibration measure | footfall calibration | none: a release check shown in the Proof room | Public and Simulated shapes |
| C27 Crowd density | journey D2 | `area_evidence` (`presence`), `stage` | Simulated |
| C28 Announced investment projects | journeys D1, D4, D6 and D7 | `investment_context` | Public |
| C29 Sums over a case sample file | cases C3 and C4 | `own_records` | Synthetic, your inputs |

In the Capability column, "capability M" and "capability S" are version 1 capabilities from the master design's value stack. For the cards added by decisions 0016 and 0017, the column names the journeys D1 to D7, the services and the cases of [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md). In this document a bare C number is always a method card: the cases are written "case C1" to "case C4" and the services "service S1" to "service S3". Everywhere else in this document, "slice S0" to "slice S11" are build slices. ASSUMPTION: C6 is served by `scan_places`, because it reads public places around a pin, which is that tool's job. Tool names are those of [08_BACKEND.md](08_BACKEND.md) section 6.2 (BE-56).

## 3. Shared interval method and reliability mark

This section is used by C1, C2, C8 and C10.

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
| MTH-19 | No function in the repository computes issued minus cancelled licences, an entry rate or a net-formation figure from the public licence tables. |
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

**Provenance and status.** Norms: Public, `observed`, caveats `calculated`, `national_average`, `world_cup_year`. Calculator outputs: Public (least-real release input), `inferred`, "your inputs" tag. With a package, the Source chain also names the package's page and retrieval date, with caveat `agency_page`. **Compute cost.** Trivial (feasibility review; no time recorded).

**Limits and wording.** National averages over all restaurant types and sizes. 2022 was a World Cup year; the surplus share jumped from about 7% (2018–2019) to 15–20% (2020–2022) for reasons not verified. Mode A treats staff as varying with sales, which flatters very small outlets; mode B exists for that reason. The figure 8,579,462 thousand from an earlier design is a different scope and is not used (OI-03).

- Allowed: "At the sector's 2022 cost shares, your rent needs about 36 covers a day to break even (0.6 turns per seat). Across 2018–2022 the figure ranges from {low} to {high}." Also, for the optional scenario only: "To earn the sector's 2022 surplus share, the same inputs need about {covers} covers a day ({turns} turns per seat)." With a package: "With the package you chose, from its page, the same inputs need about {covers} covers a day to break even while the package lasts." The braces are filled by the Fact chip.
- Never say: "you will make a profit", "expected revenue", "demand at this site", "capture rate", "go" or "no-go" as a verdict, "break-even" for the surplus-share scenario, "you qualify", "you will receive", or "the incentive makes it profitable".

| ID | Requirement |
|---|---|
| MTH-25 | C4 computes every output for each survey year 2018–2022 and shows the 2022 value with the min–max range across years. |
| MTH-26 | C4 reproduces the break-even worked example, the norm checks above, and the target-surplus regression (`m - U = 0.116`; revenue QAR 344,827.59 a month; 96 covers a day; 1.6 seat turns; with E = 50, maximum rent QAR 20,880 and minimum bill QAR 229.89). |
| MTH-27 | C4 lists every user input and every public norm it used, with year and table, in the Source chain (the evidence drawer). |
| MTH-28 | No code divides a C4 output by presence, footfall or earner counts. C4 never returns a forecast of revenue, demand or capture. It returns the revenue that the user's own inputs would require. |
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

**Inputs.** `pub_place` (Overture places, release 2026-10-21.0, pinned); co-location pairs stored in `graph_edge` with `clq`, `p`, `q`, `n_focal`, `n_neighbour`.

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

**Limits and wording.** A label permutation tests association beyond category frequency but does not control for overall density, so it supports "found near", not "attract". The open places extract holds about 26,000 Qatar records against about 71,000 establishments, so absence may be a data gap. The result with pizza included is the only one that survives; the card must say pizza is included.

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

**Purpose.** Show which zones are growing in activity, using the only current public zone-level series.

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
               drive 30 is available only to staffing_and_pay
band counts    = sum of released occupation_pay band counts over the area's units
               home family: occupation_pay on op_res_quartile,
               occupation-group breakdown (MTH-55)
median band    = returned only where the exported privacy tier publishes it
quartile range = returned only where the exported privacy tier publishes it
otherwise      = "not available at this area size", and the next wider
                 staffing drive cut-off is offered (5, then 10, then 15, then 30)
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

**Purpose.** Show the estimated people present in an area hour by hour, split into workers, residents and visitors, each with a range, for every day type the release holds: the days of the dial situations, the summer setting and the three event days (journey D2; [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 7). The counts replace the presence index.

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

The seasonal shape of the visitor segment is calibrated and checked against published museum visitor counts (C26). Nothing is anchored hour by hour to a public series, and the screen never says that it is. Public monthly context series, when shown, are separate Public facts.

**Worked example (synthetic fixture, not a finding about a place).** A set A of two published units, one day type, hour and summer setting. Unit U1 has 120 workers (110 to 130), 40 residents (35 to 45) and 30 visitors (25 to 35). Unit U2 has 80 workers (72 to 88), 40 residents (36 to 44) and 20 visitors (16 to 24). Both groups are complete. A has 200 workers (182 to 218), 80 residents (71 to 89) and 50 visitors (41 to 59). Second fixture: the group of U2 is present with status `withheld`: its three rows hold null values and `BELOW_PANEL_MINIMUM`. All three counts of A are withheld with `BELOW_PANEL_MINIMUM`; the function neither sums the nulls as zero nor returns U1's counts as if they described the whole of A.

**Provenance and status.** Simulated; `observed` for a set of whole units, `inferred` for every area from `make_area` (C18, MTH-58). Caveats `estimate_not_footfall`, `movement_not_purchases`. A count is never a named place's footfall. It may appear only in a claim or component whose subject is `area`. **Compute cost.** Not separately timed.

**Limits and wording.** Movement is not purchases. The counts are simulated estimates with a range, not observations of people.

- Allowed: "About {count} estimated people around this location at {hour} on a {day type} ({low} to {high}; Simulated), shown as workers, residents and visitors."
- Never say: "footfall of {building}", "visitors to {business}", "customers", "shoppers", "real-time".

| ID | Requirement |
|---|---|
| MTH-52 | C15 sets each count of a set of whole published units (a map unit or a release-unit candidate of C11) to the exact sum of the released unit counts, with the low and high as the sums of the unit lows and highs, one fact each for workers, residents and visitors, for one day type, hour and summer setting. A unit group (unit, day type, hour, summer) is complete only when its three segment rows have status `published`. The three counts are returned only when every unit has its complete group; otherwise all three are withheld with `BELOW_PANEL_MINIMUM`, no partial sum is returned and no null is summed as zero (PRV-58, DAT-138). Every area from `make_area` (drawn, radius, walk or drive) takes C18's apportioned counts over the units its exact outline overlaps and is `inferred`. The card never rescales, never divides by a mean over units, and never attributes a count to a named building, business or place. The two fixtures above (200, 80 and 50 with their ranges; and the withheld group) are the arithmetic tests. |

## 5. Method cards added by decisions 0016 and 0017

[Decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) moves the former later cards C11, C12 and C13 into version 1 (item 18) and asks for the other methods below; [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) adds the public data several of them read. Each card is a deterministic function in `eii_core.calc` (MTH-01). Its fixture is the arithmetic test, and the slice that builds it pins its data test (MTH-60).

### C11 Best-location ranking and rank stability

**Purpose.** Rank candidate areas for an activity on criteria the user can see and change, and state beside every rank how far it can move when the weights move (journey D2; decision 0016 item 5).

**Inputs.**

- Candidates of one kind: areas the user builds (pins with walk, drive or radius areas, or drawn shapes); the published release units of one partition inside a region the user draws; or, in public-only mode, the official zones or municipalities.
- For each candidate and criterion, one fact from the card that owns the criterion (for example C1, C6, C9, C12, C14, C15, C18 or C19). This card computes no criterion itself.
- The criteria form one closed list, versioned with the catalogue. Each entry names its criterion key, the card that owns it, its release table, its default direction and the candidate kinds it applies to, under MTH-65. The list is fixed at slice S2 (open questions), and `area_ranking` ([08_BACKEND.md](08_BACKEND.md)) offers only its entries.
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
| MTH-45 | A rank is never shown without its stability sentence beside it, and weights are labelled a judgement. The sentence states the best and worst rank of the C11 bound for the box of weights within `δ` of the weights used (`δ` fixed at slice S2). It never states a share of draws, a probability or a confidence level. |
| MTH-64 | C11 normalises, weights, scores and ranks as above in exact arithmetic and reproduces the fixture: scores 40, 30 and 80; ranks 2, 3 and 1; with `δ = 0.25`, A and B between 2nd and 3rd and C unchanged at 1st; A 3rd without criterion 2 and 1st without criterion 1. A candidate missing a criterion is listed as not ranked with its reason, a constant criterion is left out, and fewer than two ranked candidates return `NO_DATA`. The score orders the candidates only and is never emitted as a fact; leave-one-out keeps the same candidates and the same min and max. |
| MTH-65 | Candidates are of one kind, and each criterion is a fact for that candidate's own geography from the card that owns it. User-built areas take protected criteria only through the snap of MTH-56, and a count reaches a drawn shape only through C18. Release-unit candidates take only the released facts of their own partition's family and Public point counts inside each unit; no Public statistic and no apportioned value is put on a unit (PUB-29, MTH-75). Official zones and municipalities, in public-only mode, take Public criteria only and carry the Public class. No Public split by sex or nationality is a criterion (PUB-90). |

### C12 Reachable-access score

**Purpose.** Show how much of a supply layer people can reach within a travel time, allowing for the other people who can reach the same supply, by hour where congestion changes travel time (journey D2; decision 0016 item 5).

**Inputs.**

- Demand locations `i` with weights `P_i`, from one layer: estimated residents present at a stated day type, hour and summer setting (C15, Simulated, at unit centroids), or the population grid `worldpop_qat_2020` at its own 100 m cells (Public, 2020; free flow only), once [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) lists that use. The grid is the only layer in public-only mode and a second layer beside the Simulated one in a protected release. No protected figure is a demand weight (PRV-41).
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
| MTH-67 | An hour's score uses C25's times for that hour and carries the Simulated class. A score is Public only when its demand layer, supply layer and times are all Public. No protected figure enters a demand weight or an access score (PRV-41). |

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

**Purpose.** Run the C11 functions with other candidates. The reverse fit ranks activities for one site, for property owners matching tenants to the business mix and the catchment's wage profile (journey D2; decision 0016 item 5). Fit lists rank named synthetic firms for the customer, partner and supplier finders (journeys D3 and D4; decision 0016 item 12).

**Inputs, reverse fit.** A site: an `area`, drawn or built around a pin. Candidates: activities the user picks from the activity spine. Criteria come from this closed list, each computed for every activity:

- public places of the activity's category inside the site's exact shape (`pub_place`, counted by point-in-polygon, PUB-29; Public);
- the number of the activity's typical-neighbour categories kept by C6 that are found within 250 m of the site's pin or representative point (C6; Public); an activity for which C6 keeps no neighbour category has no value on this criterion;
- the activity's location quotient in the municipality of the site's pin (C1; Public);
- the share of the catchment's covered residents in the wage bands the user selects for that activity (the band partition of C19, on a snapped catchment; Synthetic);
- estimated people present at the hours the user selects for that activity (C15's unit counts apportioned to the site's outline by C18; Simulated).

A site fact that is the same for every activity (for example the price of C14, the pipeline of C23, or the people present at one hour chosen for all activities) cannot separate the activities. It is shown beside the fit as context and takes no part in the score.

**Inputs, firm fit lists.** Candidates: the named synthetic firms the release publishes for the search, each showing only a fictional name, activity, size band and area. Filters: the purpose the user chooses, from the one closed list that `synthetic_firms` takes in [08_BACKEND.md](08_BACKEND.md) (`prospects`, `partners`, `suppliers` or `complementary`), each kept through the relation that the reviewed spine records between the user's activity and a firm's activity; and the size bands the user selects. The size-band filter's closed list is the bands of the exported parameter set, read from the release (manifest `parameter_set`), as `firm_list` holds them: `s00_09`, `s10_49` and `s50_plus` under set A, `s00_49` and `s50_plus` under set B (PRV-125). A filter selects whole joined bands only, and a band that the exported set does not hold, such as `no_payroll` or `s01_09`, is not offered. Criteria: the free-flow drive time from the area's pin or, for a drawn shape, its representative point (`eii_core.shapes`) to the drivable node nearest the centroid of the firm's release unit (the C25 loading rule), which is Synthetic because the unit comes from `firm_list`; and, if the user asks, the size band, which enters as its position among the bands of the exported set (`s00_09` < `s10_49` < `s50_plus` under set A; `s00_49` < `s50_plus` under set B). Free-flow times keep every fit Synthetic, as the `synthetic_firm` subject requires ([AGENTS.md](../AGENTS.md) rule 8).

**Formula.** C11's normalisation, score, rank, stability bound and leave-one-out, with the activities or firms as candidates. The rank-stability sentence stands beside every fit rank (MTH-45).

**Worked example (fixtures).** C11's fixture with the candidates relabelled as activities gives the same scores, ranks and bounds. Adding a criterion with the same value for all three activities leaves the scores unchanged. Firm list: firms F1, F2 and F3 pass the filters with drive times of 12, 7 and 7 minutes. With that one criterion, lower ranking higher, the scores are 0, 100 and 100; F2 and F3 share rank 1 and are listed in id order, and F1 ranks 3rd. With one criterion, no weight change can move a rank.

**Provenance and status.** Reverse fit: the least-real class of the criteria used; `inferred`; caveats `your_inputs`, `weights_judgement`, `ranking_not_advice`, `fit_not_success`; subject `area`. Firm lists: Synthetic; `inferred`; caveats `your_inputs`, `weights_judgement`, `ranking_not_advice`, `firms_fictional`; subject `synthetic_firm` for each record. **Compute cost.** As C11; not yet timed.

**Limits and wording.** A fit says how an activity or a firm scores on the stated criteria, not whether it would trade well. Wage bands describe covered residents' pay, not spending. The wage-band criterion is Synthetic and the presence criterion Simulated: a fit on them shows the format of a register-based fit, not a finding about the site; each criterion's class line says which. Synthetic firms are fictional: a list shows the format a register-based search would give.

- Allowed: "Of the activities you listed, these score highest at this site on the criteria and weights you set; each rank shows its range." "These fictional firms match the relation and size bands you chose; the nearest by free-flow drive time come first."
- Never say: "best tenant", "will succeed", "recommended tenant", "demand for", "should open", "contact this company", or any real business name in a fit list.

| ID | Requirement |
|---|---|
| MTH-69 | C16 uses the C11 functions unchanged, with the stability sentence beside every fit rank, and reproduces its fixtures: C11's results for relabelled candidates; no change from a constant criterion; F2 and F3 at rank 1 and F1 at rank 3. |
| MTH-70 | A reverse-fit criterion must differ between activities; a site fact is context only. Wage-band and presence criteria enter only from the user's own selections and carry `your_inputs`. A wage-band share is computed by the band derivations of document 06, and a selection that cuts a merged band returns `SUPPRESSED` (PRV-32). |
| MTH-71 | A firm fit list reads only a firm record's fictional name, activity, size band and area; applies the purpose (`prospects`, `partners`, `suppliers` or `complementary`, through the reviewed relation) and the user's size bands, whole bands of the exported parameter set only, as filters; uses only free-flow drive times to the drivable node nearest the centroid of the firm's release unit, which are Synthetic; ranks a size band by its position among the bands of the exported set; and holds only the firms the release publishes under the minimum, dominance and complement rules of document 06. No firm's wages, wage bill or headcount is read, and no real business or FDI project enters a fit list (MTH-57). |

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

Until slice S2 confirms the grid's file and licence for this use, counts of people are apportioned by area, and the card names that method.

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
- Never say: "exactly", "counted in your area", "census of your area", or a sex or nationality split inside a shape.

| ID | Requirement |
|---|---|
| MTH-74 | C18 apportions counts only, with the weight of the table above, and reproduces the fixtures: 275; 5,000; and 80 workers (73 to 87). A share, rate, mean, median, price or index is never apportioned; the overlapped geographies' values are shown with their lowest and highest. |
| MTH-75 | C18 never apportions a Public split by sex or nationality (a total over every category of such a split may be apportioned as a total) or a figure of the protected record types, which snap (MTH-56). It never writes an apportioned value to the release, to grid cells or to release units. Every apportioned figure is `inferred` and names its method and its source geography. |

### C19 Six income indicators and pay versus mix by month

**Purpose.** Compute the six income indicators of decision 0016 item 9. Indicators 1 to 5 describe covered earners in each month of the window. Indicator 6, wage trends by sector and area separated from changes in worker mix, has two branches. By area, it is the wage trend of the same earners between adjacent months, which keeps changes in worker mix out of it, released only for a unit at municipality level or coarser that contains the area (PRV-55; Synthetic). By sector, it is a Public national branch over the economic-activity rows of `pub_wage_table`: each activity's change between adjacent published years, and C3's split of the national change into pay change within sectors and change in the employment mix. No sector trend is computed for an area, because the release holds no protected split by activity ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) leaves it open).

**Inputs.** Indicators 1 to 5 and indicator 6 by area, for a snapped area only (MTH-56): `resident_pay`, `worker_pay`, `occupation_pay` and `home_area_share` for each month of the one protected window (decision 0016 item 10), and the column `stayer_wage_index` of `month_change` for indicator 6; for indicator 4, the presence counts by hour of C15 for a set of whole units, or of C18 for an area from `make_area`. Every derivation follows section 6.2 of [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) (PRV-30 to PRV-32) and the home-family rule (MTH-55).

Indicator 6 by sector: the rows of the activity table `wage_act` in `pub_wage_table`, under its own `table_code` (workers in paid employment and monthly average wage by gender and economic activity, National Planning Council; national; 21 activity sections by sex; source years 2020 to 2023, as [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) section 2.2 records them): paid workers and mean monthly wage for each activity-by-sex cell and year. "Sector" here is the table's economic activity; the table by institutional sector (`wage_sector`) is not read, and no protected, Synthetic or Simulated figure is an input.

| No. | Indicator | Computed as |
|---|---|---|
| 1 | Average and median wage by residential area, where groups are large enough | mean = `wage_bill` / `earner_count` on the same `ALL` rows (MTH-55); median band from the band partition (PRV-31, PRV-32) |
| 2 | Wage bands and their spread | band shares and the quartile band range (PRV-32) |
| 3 | Covered wage bill and earner count | the primitives of the money and count partitions |
| 4 | Residential income beside presence by time of day | indicators 1 to 3 for residents, beside the presence counts by hour (C15, or C18 for an area from `make_area`), as separate facts and charts |
| 5 | Residence and workplace geography | for located jobs only (PRV-61): the work area's earners by home municipality from `home_area_share`, and the share living in a municipality other than that of their work unit |
| 6 | Wage trends by sector and area, separated from worker mix | by area: the fixed-composition index of the same earners between adjacent months (below; Synthetic); by sector: the Public national branch below, over the activity table of `pub_wage_table`: each activity's difference, ratio and direction between adjacent years, and C3's within-sector and employment-mix components of the national change; never for an area |

The average is never shown alone: a mean appears only with the median band, the band distribution and the earner count of the same area and month (decision 0016 item 9). Where the exported tier does not publish all four, the mean is not shown. Each area indicator is computed for every month of the window on the same unit set; a withheld month is a gap, never a zero, a change between months comes from C20, and the wage trend comes from the index below. Indicator 6 by sector follows the published years of its Public table, and its means stand only beside their paid-worker counts and the caveat of the public-data gap "pay percentiles or pay by area" ([04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) section 12, PUB-78), which states the reason no median or spread is shown: the public wage tables give national means only.

**Wage trend of the same earners (indicator 6, by area).** The fixed-composition index of PRV-55, released in `month_change` ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md), DAT-137).

```
in the release build (custodian plane), for one published month_change row of unit u, table
resident_pay or worker_pay, one measure and one pair of adjacent months (m - 1, m):
  index_u = 100 * B1_u / B0_u        100 times the exact ratio of the later bill to the earlier
                                     one; B0_u and B1_u: the treated wage bills of u's stayers
                                     (the same earners in both months) in months m - 1 and m
  rounded half-up to the nearest multiple of 0.5 by eii_core.calc and released as
  stayer_wage_index only on the published rows of money or quartile tier units at municipality
  level or coarser (unit_kind municipality or national) that PRV-55 and DAT-137 allow; by
  sector only where a protected split by activity exists, which the release does not hold;
  B0_u and B1_u are never released
at request time (product plane), for each unit at municipality level or coarser of the money or
quartile partition of that table that contains units of the area's block (the block's cell,
merged and remainder units carry no index):
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
| MTH-76 | C19 computes indicators 1 to 5 and indicator 6 by area only from released tables of a snapped area, by the derivations of document 06, for every month of the window on one unit set, and shows an area mean only with the median band, band distribution and earner count of the same area and month. Indicator 6 by sector is the Public national branch of MTH-97, computed only from the activity table of `pub_wage_table` and never for an area; no sector trend is computed from protected tables while the release holds no protected split by activity. C19's rows in the matrix of TST-197 are MTH-76, MTH-77, MTH-78, MTH-79 and MTH-97 (MTH-60). |
| MTH-77 | Indicator 4 sets resident pay beside presence counts as separate facts. No code multiplies, divides or otherwise combines pay with presence (section 6). |
| MTH-78 | Indicator 6 by area reads only `month_change.stayer_wage_index` of published `resident_pay` or `worker_pay` rows of `money` or `quartile` tier units at municipality level or coarser (`unit_kind` `municipality` or `national`), and by sector only where a protected split by activity exists, which the release does not hold (DAT-137, PRV-55). The release build computes that index as 100 times the exact ratio of the later stayer wage bill to the earlier one, rounded half-up to the nearest half point, and releases neither bill. The product returns the index, its change (the index minus 100) and its direction, one set of facts for each such unit that contains units of the area's block, labelled with that unit's own released area, and never averages, weights, combines or chains indices; the block's `cell`, `merged` and `remainder` units carry no index. A carried-forward row returns `SUPPRESSED` with `CARRIED_FORWARD`, and a null index on a published row `SUPPRESSED` with `DETAIL_NEEDS_LARGER_GROUP`, never zero or `equal`. It reproduces the fixture (103.5 and 3.5; 104.0 and 4.0; 99.0 and −1.0, direction lower; the carried-forward unit). No Kitagawa split is computed for an area; the split runs only on national Public tables: C3's occupation table and, for indicator 6 by sector, the activity table (MTH-97). |
| MTH-79 | No C19 card shows a Public split by sex or nationality, and no synthetic or protected figure carries one (PUB-90). |
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
  components  joiners, leavers and stayers (resident_pay, worker_pay), or openings and closures
              (outlet_register): each the exact sum of the published month_change components
              over the units of A (MTH-55)
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
| MTH-80 | C20 returns a change between synthetic months only from the `month_change` rows of the pair: the published components summed over the area's units of one partition, never by subtracting two monthly values; a pair with any unit's row carried forward, an empty cohort's row included (DAT-137), returns `SUPPRESSED` with `CARRIED_FORWARD`, and a withheld month `SUPPRESSED` with its reason, never zero or `equal` (BE-53, BE-115). It returns difference, ratio and direction (DAT-134) only between two adjacent periods of one Public series on one geography, or between two areas in one month, each from its own unit set and one family; never across releases or seeds. It reproduces the fixtures, the carried-forward unit included. |
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
no interval is drawn, because an interval would read as a confidence claim
```

**Worked example (fixture).** y = 100, 103, 109, 111 and 117 for t = 1 to 5. Then ȳ = 108 and t̄ = 3; the cross-sum is 42 and the sum of squares 10, so b = 4.2 and a = 95.4. With h = 2, the projection is 120.6 for t = 6 and 124.8 for t = 7.

**Provenance and status.** The series' class; `inferred` (MTH-58); caveat `projection_not_forecast`; a Synthetic series also carries `synthetic_not_evidence_about_qatar` and `synthetic_change`; shown in the Inferred section only (AI-112). Subject: the series' subject. A projection of a Public split by sex or nationality stays on the source's own geography and categories and is never combined with another figure (PUB-90). **Compute cost.** Trivial; not separately timed.

**Limits and wording.** A straight line ignores turning points, policy changes and shocks; it only extends the stated window. A projection of a released synthetic series extends the synthetic world's months; it shows the format, not a trend in Qatar.

- Allowed: "If the straight-line trend of {series} over {window} continued, it would reach about {value} in {period}. This is arithmetic on past values, not a forecast." For a Synthetic series: "If the straight-line trend of this area's synthetic {series} over {window} continued, it would reach about {value} in {period}. These are synthetic months: this shows the format, not a trend in Qatar."
- Never say: "will reach", "forecast", "expected", "likely", "probability", "demand will grow", "the market will".

| ID | Requirement |
|---|---|
| MTH-82 | C21 fits the least-squares line on the stated window only, applies the rules above, draws no interval, labels every value a projection with its method and period, and reproduces the fixture (b = 4.2; 120.6 and 124.8). A released synthetic series with a carried-forward pair in its window, for any of its units, returns `SUPPRESSED` with `CARRIED_FORWARD`, and every Synthetic projection carries `synthetic_not_evidence_about_qatar` and `synthetic_change`. |
| MTH-83 | No projection is an input to another method: no ranking, fit, break-even or access score uses one. No projection is made of revenue, sales, demand, spending or success. Labour-market tightness stays theatre (section 6). |

### C22 Openings and closures over time

**Purpose.** Show openings and closures over time on the map (journey D6; decision 0016 item 11): public licence issues and cancellations on their official geography, and synthetic firm births and closures by area and pair of adjacent months.

**Inputs.** `pub_licence_issued` (`lic_issued`: incomplete, 610 codes, summing to 12,533; PUB-69, PUB-94) and `pub_licence_cancelled` with the C2 bulk-month flag, by municipality, activity and month. For synthetic firms: the `openings` and `closures` of the `month_change` rows whose `table_name` is `outlet_register`, by release unit and pair of adjacent months, all activity classes together (no activity class is released for them), read for a snapped area with each row's `status` (DAT-137).

**Formula.**

```
Public, municipality j, activity i, a stated span of months:
  issues(j, i, span)        = sum of the issued counts
  cancellations(j, i, span) = sum of the dated cancelled counts, with and without bulk months (C2)
  an activity code the issued series does not cover: NO_DATA
    (reason openings_not_published_for_activity), never zero
  the two series stand side by side; nothing subtracts one from the other (MTH-19)
Synthetic, snapped area A, all activity classes together, for the pair (m-1, m) of the window:
  births(A, m) and closures(A, m) = exact sums of month_change.openings and month_change.closures
  over the units of A, one family each (MTH-55): two counts, with no rate, no net change and no
  survival figure
  any unit of A whose outlet_register row for the pair is carried_forward, an empty cohort's
  row included (DAT-137): both counts SUPPRESSED with CARRIED_FORWARD, never 0 and no partial sum
```

On screen a Public figure is worded as licence issues or licence cancellations, as C2 requires. "Openings and closures" names the journey's view, and "births and closures" are said only of synthetic firms.

**Worked example.** Pinned check: the issued series sums to 12,533 over 610 codes and has no row for restaurants (5610101) (PUB-69). Fixture: issues of 3, 0 and 5 and dated cancellations of 2, 4 and 1 over three months give 8 issues and 7 cancellations, side by side; a code absent from the issued series returns `NO_DATA`, not 0. Synthetic fixture: for one pair, unit U1's published row has 2 openings and 1 closure and unit U2's has 1 and 3, so the area has 3 births and 4 closures. If U2 had no opening in the pair, its empty openings cohort would fail and carry U2's row forward (DAT-137), as a failing cohort does: in both cases both counts are `SUPPRESSED` with `CARRIED_FORWARD`, never 0 and never U1's counts alone.

**Provenance and status.** Public series: Public, `observed`, caveats `calculated`, `licence_activity_not_firm`, and `openings_incomplete` on every issue figure. Synthetic: Synthetic, `observed`, caveats `synthetic_not_evidence_about_qatar` and `synthetic_change`. Subjects `municipality` (Public) and `area` (Synthetic). **Compute cost.** Trivial (as C2).

**Limits and wording.** A licence issue is not a business opening, and a cancellation is not the end of trading; bulk months are administrative. Synthetic births and closures follow the generator's settings: they show the format a register feed would give, not events in Qatar.

- Allowed: "In {span}, {municipality} recorded {n} licence issues and {m} licence cancellations for this activity. Issues are published for only part of the activities." "Synthetic: {births} firm births and {closures} closures in this area between {month a} and {month b}, showing the format."
- Never say: "net formation", "the market grew", "N businesses opened", "survival rate", or "closures" for licence cancellations.

| ID | Requirement |
|---|---|
| MTH-84 | C22 shows Public licence issues only for the codes the issued series covers, each with `openings_incomplete`; returns `NO_DATA`, never zero, for other codes; keeps the C2 bulk-month flag on cancellations; never subtracts one series from the other; and reproduces the pinned sum (12,533 over 610 codes) and the fixture (8 and 7). |
| MTH-85 | Synthetic births and closures are exact sums of the `openings` and `closures` of `month_change` rows of `outlet_register` over a snapped area, for one pair of adjacent months and all activity classes together, one family each, shown as two counts with the Synthetic mark. A pair with any unit's row carried forward, an empty cohort's row included (DAT-137), returns both counts `SUPPRESSED` with `CARRIED_FORWARD`, never zero. No code computes a rate, a net change or a survival figure from them (section 6), and the synthetic fixture (3 births and 4 closures; the empty and the failing cohort, each carrying U2's row forward) is their arithmetic test. |

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

**Provenance and status.** Public, `observed`, caveats `calculated`, `permit_not_start`. Subjects `municipality` or `national`. **Compute cost.** Trivial; not separately timed.

**Limits and wording.** A permit is an approval, not a start. A completion certificate is not linked to a permit in the data. The series end in 2023.

- Allowed: "In the 12 months to {month}, {municipality} issued {n} building permits of this type, {direction} the previous 12 months. In {year} it issued {c} completion certificates."
- Never say: "construction boom", "oversupply", "prices will fall", "units coming to market", "a pipeline of N homes".

| ID | Requirement |
|---|---|
| MTH-86 | C23 computes trailing sums only over complete 12-month windows, never subtracts completions from permits, sums municipalities to a national figure only when all eight are present, and reproduces the fixture (120, 144 and 0.20). |

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

**Inputs.** The drive graph from `roads_osm` (ODbL; the graph is a build artefact); the free-flow speeds and link capacities by road class, fixed at slice S1 with their sources; the released hourly origin-destination flows between release units, in vehicle trips per hour (Simulated; document 03 names the table); the volume-delay parameters α and β, fixed at slice S1. It never reads a feed row or a protected row.

**Formula.**

```
links l with length L_l, free-flow time t0_l and capacity c_l (by road class)
loading   a unit's trips start and end at the drivable node nearest its centroid (ties: lower node id)
paths     one free-flow shortest path per origin and destination (ties: the lexicographically
          smallest node sequence); trips within one unit are not assigned
volumes   v_l(h) = sum of the released vehicle trips of hour h whose path uses l
          (all-or-nothing assignment)
delay     t_l(h) = t0_l * (1 + α * (v_l(h) / c_l)^β)            the one volume-delay rule
speed     s_l(h) = L_l / t_l(h);  speed ratio t0_l / t_l(h)
volume band: the volume-to-capacity ratio v_l(h) / c_l placed in the closed ordered list vb1 to
          vbK; each band holds its lower edge and not its upper edge, and the last band has no upper
          edge; K and the edges are fixed at slice S1 with α and β, written in the release's method
          note and never tuned (MTH-04)
drive time from point p at hour h: the shortest path over the times t_l(h)
situation: a drive time or drive-time area for a dial situation uses, on each link, the arithmetic
          mean of t_l(h) over the hours that situation_windows gives the situation, on its day type
          and summer setting, as SYN-70 does for presence; a link without a row at an hour takes
          t0_l for that hour
drive-time area (p, h, T): the area within T minutes of p over t_l(h); protected figures snap it to
          whole release units (MTH-56), and Public and Simulated layers use the area itself; hourly
          times reach the routing graph by the mechanism SYN-53 chooses at slice S1
area slowdown at hour h for an area X (the traffic block of area_evidence):
          r(X, h) = sum_l len(l ∩ X) * r_l(h) / sum_l len(l ∩ X), over the road links inside X,
          where len(l ∩ X) is the geodesic length on the WGS 84 ellipsoid of the part of link l inside
          X and r_l(h) is its speed_ratio, or 1.000 where the link has no traffic_hourly row at that
          hour (free flow); rounded half-up to three decimals; no road link inside X: NO_DATA
gateway times (journey D7): the drive time from an area's pin to each gateway on a reviewed list of
          Public points (ports, the airport, free zones, land border crossings)
```

**Worked example (fixture, not a road in Qatar).** Nodes O, M and D. Link O→D is 10 km at a free-flow 60 km/h, so 10 minutes, with a capacity of 1,000 vehicles an hour. Links O→M and M→D are 6 km each at 60 km/h, 6 minutes each. The fixture rule has α = 1 and β = 2 (not the v1 values). At hour h, 500 vehicle trips go from O to D. The free-flow path is O→D (10 minutes against 12), so O→D carries 500 and O→M and M→D carry none. O→D then takes 10 × (1 + (500 / 1,000)²) = 12.5 minutes: a speed of 48 km/h and a speed ratio of 0.8. The drive time from O to D at hour h is 12 minutes, through M. The assigned flow stays on O→D: the method does not move traffic to the quicker road, which is its main limit.

Further fixtures. Volume band: with fixture edges at 0.25 and 0.75 (not the v1 values), the ratio 500 / 1,000 = 0.5 on O→D lies in vb2. Situation: over a two-hour fixture window in which O→D takes 12.5 minutes in the first hour and has no row in the second (10 minutes), the situation's time on O→D is (12.5 + 10) / 2 = 11.25 minutes. Area slowdown: an area holds 3 km of a link at a speed ratio of 0.750 and 1 km of a link with no row at that hour, so r = (3 × 0.750 + 1 × 1.000) / 4 = 3.25 / 4 = 0.8125, shown as 0.813.

**Provenance and status.** Link speeds, drive times and drive-time areas by hour: Simulated, `observed`, caveat `traffic_simulated`. Free-flow times: Public, `observed`. Gateway times: subject `area`, as the trip from the area, caveat `trip_from_area` (AI-118). **Compute cost.** Not yet timed: free-flow paths are found once for all hours, and each hour reloads the same paths. Slice S1 times it.

**Limits and wording.** Drivers do not move away from congestion in this method, so busy roads look slower, and parallel roads emptier, than they would. One rule covers every road class, and the capacities and free-flow speeds are assumptions. Trips inside one unit stay off the network. The flows are simulated, so the congestion is too.

- Allowed: "Simulated traffic: at {hour} on a {day type}, traffic on this road moves at about {ratio} of its free-flow speed." For an area: "Simulated traffic: at {hour} on a {day type}, traffic on the roads of this area moves at about {ratio} of free-flow speed, weighted by road length." "Drive time from this area to {gateway} at {hour}: about {minutes} minutes (Simulated traffic)."
- Never say: "live traffic", "measured congestion", "real-time", "a traffic jam at {named place}", or a congestion figure without the Simulated mark.

| ID | Requirement |
|---|---|
| MTH-88 | C25 reads only the released hourly flows and the Public road graph, never a feed row or a protected row (decision 0016 item 8). A release whose flows are not vehicle trips per hour returns `NO_DATA` with reason `flow_unit_not_vehicle_trips`. |
| MTH-89 | C25 uses one volume-delay rule for every link. α, β, the free-flow speeds, the capacities and the number and edges of the volume bands are fixed at slice S1 before any traffic is built, written in the release's method note and never tuned to match a published figure (MTH-04). Tie rules are fixed, so every run gives identical results. It reproduces the fixture: 12.5 minutes, 48 km/h and a ratio of 0.8 on O→D, and a 12-minute drive time through M; and the volume-band fixture (vb2). |
| MTH-90 | Every link speed by hour, every hour-dependent drive time and drive-time area, and every figure computed on such an area carries the Simulated class (SYN-54). A free-flow time is Public. A gateway time is a figure of the trip from the area, never the gateway's own (AI-118). A situation's link time is the mean of the link's times over the situation's hours, and an area's slowdown is the length-weighted mean of the speed ratios of the road links inside its outline, with a link without a row at 1.000; both reproduce their fixtures (11.25 minutes; 0.813). |

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

**Provenance and status.** P(m): Public, `observed`, caveat `calculated`. Q(m): Simulated, `observed`. D and the test result are a calibration check shown in the Proof room, not a fact about Qatar; caveat `seasonal_shape_only`. The health-centre series is annual and gives no monthly shape, so it is not used here. **Compute cost.** Trivial; not separately timed.

**Limits and wording.** The check covers the monthly shape of visitors only: not hourly presence, not levels, not workers or residents, and not any named place. The public shape is the calibration input, so agreement with it is built in: the result shows that the calibration was applied and tests nothing independent (SYN-61, SYN-62). Museum visits stand for visiting in general only as a seasonal pattern.

- Allowed: "The simulated visitors' monthly pattern was set from published museum visitor counts. As a calibration fit against that same pattern, the largest monthly gap is {gap} percentage points against a fixed tolerance of {τ}: {result}. This shows that the calibration was applied; it is not an independent check." The result word comes from the test-result fact.
- Never say: "validated footfall", "accurate visitor numbers", "the museum's visitors" for a Simulated figure, "hold-out", "validated", or "calibrated" of an hourly figure.

| ID | Requirement |
|---|---|
| MTH-91 | C26 computes the public shape once, as `mob.visitor_month_shape` of document 05 (each month's share of its year in visits summed over venues after the crosswalk, averaged over the complete years fixed at slice S1), the simulated shape of 2025 as F19 defines it, and the largest absolute gap between the two, and reproduces the fixture (D = 10 / 1,200). |
| MTH-92 | τ (the tolerance of F19) and the complete years are fixed at slice S1 before any calibration run and are never changed to pass (MTH-04). C26 is a calibration fit, never a hold-out: it is never called a validation or a check against independent data, and its result is rendered as pass or fail from the test-result fact, never as a fixed "within". No venue's level is transferred to a Simulated figure, and no Simulated figure is attached to a named place (decision 0017 item 4). |

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
- Never say: "capture rate", "share of footfall", "sales per visitor", "the area is the problem", "the branch is the problem", "will improve".

| ID | Requirement |
|---|---|
| MTH-96 | C29 computes only counts, sums, shares within the file, C20 comparison facts between two months of the file, differences from the median branch (the mean of the two middle values for an even number of branches) and, for case C3, the units and the share of the file within a free-flow drive cut-off of each depot. No code divides or multiplies a sample-file figure by presence, footfall, earner counts or pay (section 6). Its facts carry `your_inputs` and the Synthetic class, are never written to the release, store or ledger, and reproduce the fixtures (median 100 and B1 10 below; median 105 and B1 15 below; 50 units and 0.50 for D1, 70 units and 0.70 for D2). |

## 6. What would be theatre

"Theatre" here means a method whose output on synthetic or simulated data can only return what the generator or simulator was told. These must not be built on synthetic or simulated data, and most have no honest public substitute in v1.

| Method | Why it is theatre here |
|---|---|
| Gravity or Huff catchment calibration and capture shares (Huff 1964) | Calibration needs real outlets, customer origins and sales; none is public. The simulator places workplaces with a gravity model (see [05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md)), so fitting a gravity model to simulated movement recovers the simulator's own settings. |
| Survival curves (Kaplan and Meier 1958) | Need each licence's issue and cancellation dates, held only in the register. On the synthetic register a survival curve returns the generator's assumption. |
| Entry rates and net formation | The open "issued" table holds 12,533 licences over 610 codes and no restaurant records; it cannot give entry, so its issues are shown only as published counts for the codes it covers (C22). On synthetic data, entry is planted: synthetic births and closures are shown only as two counts with the Synthetic mark, never as an entry rate, a survival figure or net formation. |
| Shift-share (Dunn 1960) | Needs counts by area and activity at two dates; the public table is one snapshot (May 2025). On synthetic data it decomposes planted growth. A second real snapshot would make it real, so every refresh of the public table should be stored. |
| Labour-market tightness | About 2,988 unemployed against 2.36 million employed in 2025 and no public vacancy series (methods research); on synthetic records hiring and separation rates are parameters. |
| Multipliers from other economies' input-output tables | No official Qatari input-output or supply-use table was found; the OECD 2025 inter-country tables do not include Qatar. Another economy's coefficients beside Qatar facts would be read as Qatar facts. The real survey cost shares (C4) answer "what does this business buy". |
| Economic complexity or relatedness below national level (Hidalgo and Hausmann 2009) | Eight municipalities cannot support it. Even nationally, Qatar's distance to every non-exported product lies between 0.953 and 0.992 and 54% of export value is unclassified, so a ranking is close to noise. |
| Relatedness from synthetic co-licensing | Returns the generator's co-licensing rule. |
| Sales, revenue or demand forecasts, "spending power present", capture rates | Each multiplies simulated presence by synthetic pay by an assumed rate, or divides a company's sales by presence. There are no sales data. Resident pay and presence stand side by side only (C19), and a sample file's figures are never divided by presence (C29). |
| Differences between two synthetic releases shown as trends | The difference is a seed or a parameter change, not a change in Qatar. Months inside the one window of one world are shown only as synthetic changes with the Synthetic mark (C20). |
| A seasonal check on the calibration years called a validation | The simulated shape is set from the same public shape, so agreement is built in. C26 is reported as the calibration fit F19 of document 05, never as a hold-out or a validation, and it tests no hourly presence, level or named place. |
| Traffic tuned until it matches a published congestion figure | Tuning the volume-delay parameters to a public figure makes any agreement circular (the plausibility comparison of [05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md) already warns of this). The parameters are fixed before any traffic is built (C25). |

| ID | Requirement |
|---|---|
| MTH-48 | No module in the repository implements any method in the table above against synthetic or simulated release tables, and the assistant's must-decline set includes a question for each row. |

## 7. Where the units are too few

| Geography | Units | Supports | Rules out |
|---|---|---|---|
| Municipality | 8 | location quotients, densities, churn rates | complexity and relatedness, clustering, hot-spot statistics, any correlation or regression across municipalities |
| Census zone | 91, of which 75 have at least 1,000 employed residents | similarity search and three coarse area types (C17), rank correlations | more than three area types: three types were moderately stable (silhouette 0.33; bootstrap adjusted Rand index 0.71), five and six were not (0.56 and 0.51) (methods research) |
| Grid cell | about 15,800 at H3 resolution 8 and 110,800 at resolution 9 nationally | protected statistics after pooling | any public statistic blended or apportioned onto cells or release units (PUB-29) |

| ID | Requirement |
|---|---|
| MTH-49 | No v1 screen shows a clustering of municipalities or a hot-spot map. The similar-areas search of C17 may show at most three area types, each with its stability figures, and only when those figures reach the thresholds fixed at slice S2 ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 18). |
| MTH-53 | No method asks for a finer privacy partition so that an area looks smaller. Coarseness is reported by the snap report and the survival report. The flagship pin and the default cut-offs (walk 5 minutes and drive 10 minutes) are confirmed only after the survival report of slice S5 exists. The 30-minute drive cut-off is specified for staffing only and is not one of those defaults. |

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
13. C16: firm fit lists use free-flow drive times to the drivable node nearest the centroid of the firm's release unit, so that every fit stays Synthetic (MTH-71).
14. The new release tables are named as document 04 names them; document 03 is the authority (MTH-59).
15. C19 indicator 6 by sector: "sector" is the economic activity of the national activity table `wage_act`; its groups are the table's populated activity-by-sex cells, as C3 groups the occupation table by occupation and sex; a both-sexes total row is not read; and a cell populated in only one year of a pair gives `NO_DATA` (MTH-97).

Open items from the master design that touch this document:

- OI-03: the two restaurant totals and the two wage-table means. C3, C4 and the sector branch of C19 stay hidden until it is closed (MTH-23, MTH-29, MTH-97).
- OI-04: closed for version 1 by [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 10. The census map layers enter the local release, each figure with its source and retrieval date, so C7 resident weights and C8 shares are release facts; the research examples of C12 and C17 still run outside every release. The coverage bar uses the finest admitted geography and names it, or returns `NO_DATA` (PUB-82). Any use beyond this internal project needs written licence terms ([17_DEPLOYMENT_HARDENING.md](17_DEPLOYMENT_HARDENING.md)).
- OI-11: privacy thresholds are proposals. C7 earners mode, C10, C15, C19 and C22 inherit the exported tier; they do not set a second threshold.

Open questions:

- Which months besides the three named ones does the bulk rule flag, once the median is taken over the 125-month calendar (C2)?
- The Wilson count's period, the C5 HHI and trend, the C6 seed and remaining settings, the C7 coordinates and weights, and the C14 median prices in riyals are not pinned. slice S7 fails while any of them remains unpinned (MTH-03, MTH-51).
- The 30-minute staffing catchment has not been timed, so its cell range is not written on C10.
- The weight range `δ` of the rank-stability bound is fixed at slice S2 (MTH-45).
- C11: the closed criterion list (criterion key, owning card, release table, default direction and the candidate kinds it applies to) is fixed at slice S2 under MTH-65; `area_ranking` in [08_BACKEND.md](08_BACKEND.md) offers only its entries.
- C16: the reviewed relation that gives an activity its prospects, partners, suppliers and complementary activities is reviewed at slice S2, and document 03 holds it in the activity spine.
- The apportioning weight is fixed by C18. Slice S2 confirms the population grid's file and licence for this use, and document 04 lists the use ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md)).
- C12: the decay form, the cut-offs of each mode, the supply layers, and the modes and presence keys that `access_score` stores (with the largest cut-off of each mode, which bounds `travel_time_matrix`) are fixed at slice S2 (DAT-151, DAT-153). The population grid is a demand layer only once document 04 lists that use; its scores are stored at free flow in the Public table `access_score_grid` of both release kinds (DAT-154), while `access_score` and `travel_time_matrix` exist only in a protected release.
- C17: the feature list, the seed, the restarts, the bootstrap draws and the two stability thresholds are fixed at slice S2.
- C25: α, β, the free-flow speeds and the capacities by road class, and the number and edges of the volume bands, are fixed at slice S1, with their sources. Documents 03 and 05 must state that the released hourly flows are vehicle trips; until they do, C25 returns `NO_DATA` (MTH-88).
- C26: τ and the complete years of the public shape are fixed at slice S1 with F19 (document 05).
- C21: the reviewed list of projectable series, with each window and horizon, is fixed at slice S2.
- C13 and C24: the tariff-line crosswalk (with its source and licence) and the size-class crosswalk are reviewed at slice S2.
- C28 and C4: the page structures of the dashboard and of the agency's pages, the capex currency, and the incentive parameter kinds the pages carry are confirmed at slice S2 ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)).
- Document 03 holds what these cards write and read: the release tables `access_score` (C12, DAT-151), `access_score_grid` (C12, DAT-154) and `zone_type` (C17, DAT-152), the manifest artefact `travel_time_matrix` (C12, DAT-153), the column `stayer_wage_index` decimal(7,1) of `month_change` (C19, DAT-137; no stayer wage bill is released), the column `price_basis` of `pub_property_resi` (C14: `per_m2` or `per_unit`) and the `traffic` field of the area record, which names a dial situation and its summer setting whose link times C25 averages over the situation's hours (section 9.2).
- Document 03 must define fact units for people per square kilometre (C27) and kilometres per hour (C25), a geography kind for a drawn shape, the release tables of presence counts, hourly flows, link speeds and synthetic births and closures, and the caveat keys this document adds: `access_not_use`, `apportioned_estimate`, `editorial_crosswalk`, `establishment_survey`, `licence_not_capacity`, `openings_incomplete`, `permit_not_start`, `seasonal_shape_only` and `similar_on_features_only` (MTH-11, MTH-59).
- The slice that builds each card added by decisions 0016 and 0017 is set by [14_IMPLEMENTATION_PLAN.md](14_IMPLEMENTATION_PLAN.md); its gate pins the card's data tests (MTH-60), and the cards join the matrix of TST-197.

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
- Bureau of Public Roads (1964), Traffic Assignment Manual, U.S. Department of Commerce: the volume-delay form of C25 (no DOI)
- Goodchild and Lam (1980), areal interpolation, Geo-Processing: the area weighting of C18 (no DOI)
- Lloyd (1982), least squares quantization (k-means): https://doi.org/10.1109/TIT.1982.1056489 ; Arthur and Vassilvitskii (2007), k-means++ (ACM-SIAM Symposium on Discrete Algorithms; no DOI)
- Rousseeuw (1987), silhouettes: https://doi.org/10.1016/0377-0427(87)90125-7 ; Hubert and Arabie (1985), comparing partitions (adjusted Rand index): https://doi.org/10.1007/BF01908075
