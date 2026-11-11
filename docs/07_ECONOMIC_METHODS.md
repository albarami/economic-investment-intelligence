# 07 — Economic Methods

| | |
|---|---|
| Status | Draft v0.2, corrected after independent review on 2026-11-11 (see PROGRESS.md) |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Define every economic and location method the product computes: inputs, formula, worked public example (a regression test), provenance, honesty limits, allowed wording and measured cost. |
| Read first | [01_PROJECT_BRIEF.md](01_PROJECT_BRIEF.md), [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md), [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md), [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) |

## In brief

- Twelve version 1 (v1) method cards, three short cards for later slices, and a list of methods that must not be built.
- Every method is a small, pure, tested function. Nothing here needs a GPU, a graph server or a spatial database to compute; every method the research timed ran in about three seconds or less on a CPU.
- A pinned worked example is a regression test that must pass in slice S7. An example whose inputs are not yet pinned is an illustrative note, and the slice S7 gate fails while it stays unpinned.
- Public methods produce real findings about Qatar. Methods run on Synthetic or Simulated layers show a format and a protection, never a fact about a place.
- Several attractive methods would only return the generator's own assumptions on synthetic data. They are listed under "What would be theatre" and are not built.
- Qatar has eight municipalities and about 75 usable census zones. That rules out area typologies beyond three types, complexity below national level and hot-spot statistics.

## 1. Common rules

- **Licence-activity count**: one activity on one commercial licence, as counted in the public licence tables. It is not a firm and not a job.
- **Worked example**: a calculation with real published figures, written here so that a test can reproduce it.
- **Calculated**: a value obtained by fixed arithmetic from published figures, not published itself.

| ID | Requirement |
|---|---|
| MTH-01 | Every displayed number is produced by deterministic tested code in `eii_core.calc`, the release build, or a fixed application-schema read function listed by the data contracts and covered by tests. Nothing else computes, rounds or compares a number, and no model ever does. Each method in this document is a deterministic function in `eii_core.calc` (package `core/`). It does not read a file, the network or a database; callers pass the rows. The custodian build and the product plane call these functions. The browser never computes a displayed number; it formats values it receives. A comparison (difference, ratio, rank or direction) is itself a calculation fact. ASSUMPTION: `core/` is the only package both planes may import, so this is the one place a method can be shared. |
| MTH-02 | Build-time methods (location quotient, churn, decomposition, co-location, coverage, zone momentum, property-sale median) run in the custodian plane and write facts into the release. Request-time methods (break-even calculator, shared reach, band lookup, area presence index) run in the product plane over release tables only, by calling `eii_core.calc`. The only application-schema arithmetic is in the fixed read functions listed by the data contracts and covered by their regression tests. |
| MTH-03 | A worked example whose inputs, settings and expected result are all written in this document has two tests: an arithmetic test that feeds those inputs into the function and asserts the stated result within the stated tolerance, and a data test that recomputes the same figure from the pinned public file built in slice S2. Regression values that the pack cannot pin today (for example the riyal medians of the property-price method card and the other inputs listed here) are produced by `./eii build-public` at slice S2, checked against the source by the reviewer, and written into the method cards by a slice S2 task; slice S7 fails while any remain unpinned. No value is invented. Four examples are illustrative notes, not passing regression examples, until they are pinned: the Wilson count's period (section 3), the C5 HHI and trend, the C6 seed and full settings, and the C7 coordinates, modes, cut-offs, speed regime, district weights and expected shares. The C14 median prices in riyals are in the same state (MTH-51). |
| MTH-04 | When a data test does not reproduce a worked example, the builder must record the difference in `OPEN_ITEMS.md` and stop. Parameters must not be tuned until the number matches. |
| MTH-05 | A value computed by fixed arithmetic from Public release tables carries provenance `public`, evidence status `observed` and the caveat key `calculated`. An interpretation of such a value (for example "these months look administrative") carries evidence status `inferred`. |
| MTH-06 | A figure computed from the user's own inputs carries evidence status `inferred` and the "your inputs" tag, takes the least-real class of its release inputs as provenance, and is never written to the release or to the ledger as a fact. |
| MTH-07 | A composite of release inputs takes the least-real class of its inputs, computed in code by the shared provenance helper; the method never sets the class by hand. |
| MTH-08 | Every fact a method produces carries a complete source chain: the fact, its release table, the method and version, then the source (publisher, dataset, licence, retrieval date and file hash). The fact names its source table in `lineage_ref`. Where two public tables could give the same quantity, the fact names the one used. A fact without a complete chain is not emitted: the release build fails on it, and the Fact chip refuses it. The evidence drawer is labelled "Source chain". The Arabic label proposed, pending the owner's review, is "السند". |
| MTH-09 | Methods return a value or a status; they never return zero for an unknown. A missing input yields `NO_DATA` with a reason key, and the card shows the reason. |
| MTH-10 | Allowed wording is implemented only as application-owned English and Arabic claim templates. Each brief item carries a `claim_key` and typed fact slots. `layout[]` is an ordered list of component instances. The model may select and order catalogue claims, components and fact ids only; no model-written prose reaches the screen. Component properties are fact ids, release-unit ids or enumerations. One invalid item rejects the brief; one repair attempt; then the template writer uses the playbook's default selection. A Synthetic or Simulated fact may appear only where the claim or component subject is `area`. A claim whose subject is `place_public` may have Public slots only. A build-time scan of the templates rejects numerals, number words, names of real places inside `area` claims, and go or no-go wording, including each card's "never say" phrases. |
| MTH-11 | Caveat keys named in this document (in backticks, for example `calculated`) must exist in the release caveat catalogue with English and Arabic text. If [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) names the catalogue differently, that document wins and the meaning here stands. |
| MTH-54 | Before an answer is shown, code runs the accounting gate's five checks: sources, assumptions, nothing invented, scope, and limits stated. A method fact supplies what those checks read: the source chain (MTH-08), the evidence status (`observed`, `inferred` or `still_to_test`), the "your inputs" tag where the figure uses the user's inputs (MTH-06), and the caveat keys. The method does not set an inferred item's strength; the claim catalogue does. If a check fails, the template writer's default answer is shown. The receipt labels the result "Checked before display". The Arabic label is pending the owner's review. |
| MTH-55 | Each derived statistic normally names exactly one home family in its fact lineage, as section 6.2 of [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) defines (PRV-30). The only exception is the closed list of ratio statistics: mean wage and the coverage, irregular and deployed-elsewhere shares. A ratio statistic takes its numerator and denominator from columns of the same stored rows — one table, one partition, one unit set and one measure where the table has measures — even where those columns belong to two additive families; its fact lineage names both families. Mean wage divides `wage_bill` by `earner_count` on the same stored `ALL` rows of `worker_pay` on `wp_all_money` or `resident_pay` on `rp_all_money`. The three side-count shares divide the applicable side-count column by `earner_count` on the same stored `ALL` rows of `resident_pay` on `rp_housing_count` or `worker_pay` on `wp_site_count`. Earner count on a worker card uses `worker_pay` and `wp_all_count` with no breakdown; earner count on a resident card uses `resident_pay` and `rp_all_count` with no breakdown. Wage bill uses that table's money partition. Band shares, the median band and quartile bands use that table's band partition (`wp_all_quartile` or `rp_all_quartile`), and the count beside those shares is that same family's total. A housing count and the housing shares beside it use `resident_pay` and `rp_housing_count` with the housing-class breakdown. An occupation count and the occupation shares beside it use `occupation_pay` and `op_res_quartile` with the occupation-group breakdown. C7 earners mode uses one selected count family, `resident_pay` on `rp_all_count` or `worker_pay` on `wp_all_count`, for both the weight and the share. C15 uses `presence_index` on `px_base` for one segment (PRV-58); no presence total is stored (PRV-59). No method returns two routes to one population as two numbers. |

Each card states its compute cost and which research review measured it. All research timings were taken on 2026-11-11 on the build machine with the CPU only; they show that compute is not the constraint and are not promises for the demo. Where no time was recorded, the card says so.

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
| C15 Area presence index | capability M2 | `area_evidence` (`presence`) | Simulated |
| C11 Rank stability (later) | backlog item L1 | not in v1 | least-real input class |
| C12 Reachable-access score (later) | backlog item L2 | not in v1 | Public or least-real input class |
| C13 Imports against local production (later) | backlog item L3 | not in v1 | Public |

In the Capability column, "capability M" and "capability S" are version 1 capabilities from the master design's value stack, and "backlog item L" is a later item. Everywhere else in this document, "slice S0" to "slice S11" are build slices. ASSUMPTION: C6 is served by `scan_places`, because it reads public places around a pin, which is that tool's job.

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

Tolerance: ± QAR 1 on each money figure; ± 0.1 percentage point on shares.

**Provenance and status.** Public, `observed`, caveats `calculated`, `named_table`, `composition_not_wages`. **Compute cost.** 0.05 s for 15,800 cells by 50 groups (methods research); the national case is trivial.

**Limits and wording.** Only 17 groups: any mix change inside a group counts as pay change. Survey means in nominal riyals. The occupation table and the activity table give the same paid-worker counts but different means: QAR 10,084 against 10,352 for 2020 and 11,714 against 11,025 for 2023 (methods research). This is OI-03.

- Allowed: "In the published table of 17 occupation-by-sex groups, average pay rose 17.6% from 2020 to 2025. About 98% of that rise came from a change in which jobs people hold. Composition drove the average."
- Never say: "wages did not rise", "nobody got a raise", "real pay", any figure in this card without the table's name.

| ID | Requirement |
|---|---|
| MTH-21 | C3 reproduces the worked example and asserts `within + mix == change`. |
| MTH-22 | The C3 card names its table on the card face and shows, in the Source chain (the evidence drawer), the other table's mean for the same year with the line "the two published tables differ; this card uses the occupation table". |
| MTH-23 | C3 is not displayed until OI-03 is recorded as closed in `OPEN_ITEMS.md`. |
| MTH-24 | C3 never shows a sex split on screen; it uses sex only as a grouping inside the calculation. ASSUMPTION: the master design drops sex splits at area level, and the national card does not need one to make its point. |

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

**Provenance and status.** Norms: Public, `observed`, caveats `calculated`, `national_average`, `world_cup_year`. Calculator outputs: Public (least-real release input), `inferred`, "your inputs" tag. **Compute cost.** Trivial (feasibility review; no time recorded).

**Limits and wording.** National averages over all restaurant types and sizes. 2022 was a World Cup year; the surplus share jumped from about 7% (2018–2019) to 15–20% (2020–2022) for reasons not verified. Mode A treats staff as varying with sales, which flatters very small outlets; mode B exists for that reason. The figure 8,579,462 thousand from an earlier design is a different scope and is not used (OI-03).

- Allowed: "At the sector's 2022 cost shares, your rent needs about 36 covers a day to break even (0.6 turns per seat). Across 2018–2022 the figure ranges from {low} to {high}." Also, for the optional scenario only: "To earn the sector's 2022 surplus share, the same inputs need about {covers} covers a day ({turns} turns per seat)." The braces are filled by the Fact chip.
- Never say: "you will make a profit", "expected revenue", "demand at this site", "capture rate", "go" or "no-go" as a verdict, or "break-even" for the surplus-share scenario.

| ID | Requirement |
|---|---|
| MTH-25 | C4 computes every output for each survey year 2018–2022 and shows the 2022 value with the min–max range across years. |
| MTH-26 | C4 reproduces the break-even worked example, the norm checks above, and the target-surplus regression (`m - U = 0.116`; revenue QAR 344,827.59 a month; 96 covers a day; 1.6 seat turns; with E = 50, maximum rent QAR 20,880 and minimum bill QAR 229.89). |
| MTH-27 | C4 lists every user input and every public norm it used, with year and table, in the Source chain (the evidence drawer). |
| MTH-28 | No code divides a C4 output by presence, footfall or earner counts. C4 never returns a forecast of revenue, demand or capture. It returns the revenue that the user's own inputs would require. |
| MTH-29 | C4 is not displayed until OI-03 is recorded as closed in `OPEN_ITEMS.md`. |

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

**Inputs.** Snapped areas from `make_area`. In public-only mode the sets are whole base cells of the fixed frame: `make_area` reads no privacy-derived release unit and no protected or simulated table, and the snap report is technical metadata, not a Synthetic fact. Outside public-only mode the sets are whole release units. Resident weights come from Census 2020 population in `pub_census_district` (`district_key`, `period`, `indicator`, `value`, `unit`, `source_id`), using count indicator `residents` with unit `persons` (PUB-84), joined to the centroid of `district.geometry`. Covered-earner weights come from `resident_pay` or `worker_pay`. `speed_factor` applies when a dial situation sets drive times. A district population taken from a source with no stated licence does not enter the release (open item OI-04); residents mode then returns `NO_DATA`.

**Formula.**

```
centre of a district = the centroid of district.geometry
a district counts in X when that centroid lies in a unit of X
  (in public-only mode, in a base cell of X)
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
| MTH-37 | C7 computes shared reach only on snapped sets of whole release units or, in public-only mode, on whole base cells of the fixed frame, never on raw polygons. |
| MTH-38 | C7 shows the mode (residents or covered earners) and the situation on the card face. |

### C8 Coverage share and the reliability mark

**Purpose.** Say how much of an area's earners a wage-based figure can see, and how reliable each small-count figure is.

**Inputs.** A licensed private-employer share: zone rows from `pub_census_zone`, a national row from `pub_census_national` (`period`, `indicator`, `value`, `unit`, `source_id`). `zone` names the geography. Any fact's count feeds the reliability mark (section 3). While open item OI-04 is open, the census map layers have no stated licence. They are validation-only: no value, derived share, title or geometry from them enters a release.

**Formula.**

```
coverage = employed residents working for private employers
           / all employed residents
           on the finest licensed geography that holds the share:
           zone, otherwise municipality, otherwise national
the card names that geography
if the area spans several zones, the min and max are shown as well (no blending)
if no licensed geography holds the share: NO_DATA
```

ASSUMPTION: the private-employer share is a proxy for wage-protection coverage, as the research states; it is shown as a proxy. "Not measured" is not this gap. It is the coverage label for a person who has no pay in the wage records. An unknown housing class is the separate value `unknown`.

**Validation-file arithmetic (not a release fact while OI-04 is open).** Methods research, Census 2020. National: 1,617,208 / 2,050,252 = 0.7888, which rounds to 78.9%. The zone figures below are the rounded shares stated with that check. They stay out of the release until the licence is recorded.

| Quantity | Value |
|---|---|
| National private-employer share | 78.9% |
| 75 zones with at least 1,000 employed residents | 23% (zone 68) to 99% (zone 57); median 78%; 9 zones below 50% |
| Zone 69 / zone 70 (Al Daayen) | 72% / 45% |

Tolerance: ± 0.5 percentage point.

**Provenance and status.** When the source licence is recorded: Public, `observed`, caveat `coverage_private_proxy`. While it is not, the bar is `NO_DATA` and the validation figures are not release facts. **Compute cost.** Trivial (methods research; no time recorded).

**Limits and wording.** Census 2020 is nearly six years old. The share describes residents, not workers in the zone. The card names the geography it used.

- Allowed, once a zone share is licensed: "This pay figure covers private-sector earners only. In 2020, about 72 in 100 employed residents of this zone worked for private employers."
- While OI-04 is open: "The coverage share is not on screen. The census employment layer has no stated licence."
- Never say: "all earners", "the average resident earns", "complete picture", or "Not measured" for this unpublished workplace gap.

| ID | Requirement |
|---|---|
| MTH-39 | Every resident-pay card shows the C8 coverage bar, naming the geography used. While OI-04 is open the bar is `NO_DATA`, because no share from an unlicensed census layer is released. When a licence is recorded, the bar uses the finest licensed geography that holds the private-employer share (zone, otherwise municipality, otherwise national). The worker-pay card returns `NO_DATA` with reason `coverage_by_workplace_not_published`. It does not use the coverage label "Not measured" for that gap. |
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
- Never say: "you should pay", "the market rate here is", "cooks in Lusail earn", any nationality or sex split.

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

**Provenance and status.** Public, `observed`, caveat `deal_count_shown`. A price is never shown without its deal count. **Compute cost.** Not separately timed.

**Limits and wording.** Few deals sit in the Lusail crosswalk. District names change: the source uses both "Lusail" and "Lusail 69". Identifiers on the source rows never enter the release.

- Allowed: "The median sale price for this district, property type and year, with this deal count."
- Never say: a price without the deal count, "the market will rise", or a value for an unmatched district name.

| ID | Requirement |
|---|---|
| MTH-50 | C14 keeps only crosswalk-matched rows with a positive price and a positive area, sets price per square metre to price divided by area, and returns the median and the deal count by district, year and reviewed Arabic property type. Zero kept rows returns `NO_DATA`. |
| MTH-51 | C14's pinned deal counts for the "Lusail 69" crosswalk are 6 deals in 2024 and 13 deals in 2025. The median prices in riyals are not in the pack. Until they are written here, that part of the example is not a passing regression, and the slice S7 gate fails for it. The invented pair (10 and 20, median 15, two deals) is the arithmetic test of the median rule. |

### C15 Area presence index

**Purpose.** Sum released `presence_score` leaves over an area's complete published units, separately for workers, residents and visitors.

**Inputs.** `presence_index` for the area's published units: `presence_score` by segment (`worker`, `resident`, `visitor`), situation and the `summer` flag. The feed normalisation that produces `presence_score` is the fixed-scale formula of PRV-59 in [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) and [05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md) (`presence_scale` and `flow_scale` committed at slice S1). This card does not normalise again. `summer` false is season `regular`; `summer` true is season `summer`. The situation windows are those in [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md).

**Formula.** One tested formula, shared with the synthetic-world checks:

```
index(A, segment, situation, summer) =
    exact sum of presence_score leaves
    over the published units of snapped area A
    home family: presence_index on px_base, one segment (MTH-55)
    no presence total is stored (PRV-59)
a unit group (unit_id, situation, summer) is complete when all three
    segment rows are present; the release holds a group whole or not
    at all (PRV-58)
the three area indices are returned only when every unit of A has its
    complete group; otherwise all three are withheld with
    BELOW_PANEL_MINIMUM, and no partial sum is returned
workers, residents and visitors are three facts; never one count
```

The dial is Simulated. It is not anchored hour by hour to any public series, and the screen never says that it is. Public monthly context series, when shown, are separate Public facts.

**Worked example (synthetic fixture, not a finding about a place).** Two published units in area A, one situation, `summer` false. Unit U1 has scores 12.5 (worker), 4.0 (resident) and 3.0 (visitor). Unit U2 has 7.5, 4.0 and 2.0. Both groups are complete. Workers: 12.5 + 7.5 = 20.0. Residents: 4.0 + 4.0 = 8.0. Visitors: 3.0 + 2.0 = 5.0. Second fixture: the group of U2 is absent from the release (`BELOW_PANEL_MINIMUM`). All three area indices are withheld with `BELOW_PANEL_MINIMUM`; the function does not return 12.5, 4.0 and 3.0 as if they described the whole area.

**Provenance and status.** Simulated, `observed`. The index is not a count and not a named place's footfall. It may appear only in a claim or component whose subject is `area`. **Compute cost.** Not separately timed.

| ID | Requirement |
|---|---|
| MTH-52 | C15 sets the area index to the exact sum of released `presence_score` leaves over the published units of the snapped area, one fact each for workers, residents and visitors. The three indices are returned only when every unit of the area has its complete `(unit_id, situation, summer)` group; otherwise all three are withheld with `BELOW_PANEL_MINIMUM` and no partial sum is returned (PRV-58). It does not divide by a mean over units and does not rescale to 100. The two fixtures above (workers 20.0, residents 8.0, visitors 5.0; and the withheld case) are the arithmetic tests. |

## 5. Later method cards (short)

### C11 Rank stability for site ranking (L1)

A weighted sum of normalised indicators with user weights, plus a Monte Carlo over weights and a leave-one-indicator-out test; the card reports how often each site stays in the top ten and its 5th to 95th percentile rank. Measured: 1.0 s for 15,800 cells, 6 indicators and 5,000 weight draws (methods research). On random test inputs the site ranked tenth stayed in the top ten in only 29% of draws: an illustration of the check, not a finding about Qatar. A public-only mode (zone or district inputs) carries the Public mark; otherwise the least-real class. References: OECD and JRC handbook (2008); Saisana, Saltelli and Tarantola (2005).

| ID | Requirement |
|---|---|
| MTH-45 | A rank is never shown without its stability sentence beside it, and weights are labelled a judgement. ASSUMPTION: weights are drawn from a Dirichlet distribution centred on the user's weights; its spread is fixed in the L1 slice. |

### C12 Reachable-access score (L2)

Two-step floating catchment area (Luo and Wang 2003): each supply point's ratio of supply to the distance-weighted population that can reach it, summed over the points each place can reach, with a Gaussian distance decay. Research test (methods research): 777 district centres, 609 official landmark points used only as a test supply layer, 10-minute drive; the per-resident container ratio and the access score agreed only moderately across 75 zones (Spearman 0.47), and zone 69 fell from 3.40 to 0.66 per 10,000. Compute: 0.016 s once travel times exist; the national matrix runs at about 4,600 pairs per second per process. Needs the national travel-time matrix, which is not in v1.

| ID | Requirement |
|---|---|
| MTH-46 | The L2 regression example is the zone 69 pair (3.40 and 0.66) and the rank correlation 0.47, re-derived with the decay form written in the L2 slice. |

### C13 Imports against local production (L3)

For a product group: imports, exports and re-exports 2019–2023 from the commerce ministry's trade tables, and operating and licensed factories with labour and investment from the manufacturing tables (methods research). Example: pharmaceutical imports 3,380 million in 2023 against exports of 20 million, with 4 operating and 7 licensed factories in 2025. The trade tables do not state their currency; the research found magnitudes consistent with riyals. These tables are not among the pinned v1 release tables, so L3 must add them to the release contract first.

| ID | Requirement |
|---|---|
| MTH-47 | C13 is worded as a screen, never as an opportunity or a recommendation, shows no currency label until the currency is confirmed, and joins no synthetic figure to a real import figure. |

## 6. What would be theatre

"Theatre" here means a method whose output on synthetic or simulated data can only return what the generator or simulator was told. These must not be built on synthetic or simulated data, and most have no honest public substitute in v1.

| Method | Why it is theatre here |
|---|---|
| Gravity or Huff catchment calibration and capture shares (Huff 1964) | Calibration needs real outlets, customer origins and sales; none is public. The simulator places workplaces with a gravity model (see [05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md)), so fitting a gravity model to simulated movement recovers the simulator's own settings. |
| Survival curves (Kaplan and Meier 1958) | Need each licence's issue and cancellation dates, held only in the register. On the synthetic register a survival curve returns the generator's assumption. |
| Entry rates and net formation | The open "issued" table holds 12,533 licences over 610 codes and no restaurant records; it cannot give entry. On synthetic data, entry is planted. |
| Shift-share (Dunn 1960) | Needs counts by area and activity at two dates; the public table is one snapshot (May 2025). On synthetic data it decomposes planted growth. A second real snapshot would make it real, so every refresh of the public table should be stored. |
| Labour-market tightness | About 2,988 unemployed against 2.36 million employed in 2025 and no public vacancy series (methods research); on synthetic records hiring and separation rates are parameters. |
| Multipliers from other economies' input-output tables | No official Qatari input-output or supply-use table was found; the OECD 2025 inter-country tables do not include Qatar. Another economy's coefficients beside Qatar facts would be read as Qatar facts. The real survey cost shares (C4) answer "what does this business buy". |
| Economic complexity or relatedness below national level (Hidalgo and Hausmann 2009) | Eight municipalities cannot support it. Even nationally, Qatar's distance to every non-exported product lies between 0.953 and 0.992 and 54% of export value is unclassified, so a ranking is close to noise. |
| Relatedness from synthetic co-licensing | Returns the generator's co-licensing rule. |
| Sales, revenue or demand forecasts, "spending power present", capture rates | Each multiplies simulated presence by synthetic pay by an assumed rate. There are no sales data. |
| Differences between two synthetic releases shown as trends | The difference is a seed or a parameter change, not a change in Qatar. |

| ID | Requirement |
|---|---|
| MTH-48 | No module in the repository implements any method in the table above against synthetic or simulated release tables, and the assistant's must-decline set includes a question for each row. |

## 7. Where the units are too few

| Geography | Units | Supports | Rules out |
|---|---|---|---|
| Municipality | 8 | location quotients, densities, churn rates | complexity and relatedness, clustering, hot-spot statistics, any correlation or regression across municipalities |
| Census zone | 91, of which 75 have at least 1,000 employed residents | similarity search, three coarse area types, rank correlations | more than three area types: three types were moderately stable (silhouette 0.33; bootstrap adjusted Rand index 0.71), five and six were not (0.56 and 0.51) (methods research) |
| Grid cell | about 15,800 at H3 resolution 8 and 110,800 at resolution 9 nationally | protected statistics after pooling | any public statistic blended onto cells |

| ID | Requirement |
|---|---|
| MTH-49 | No v1 screen shows an area typology, a clustering of municipalities or a hot-spot map; a later "areas like this" feature may show at most three zone types with their stability figures. |
| MTH-53 | No method asks for a finer privacy partition so that an area looks smaller. Coarseness is reported by the snap report and the survival report. The flagship pin and the default cut-offs (walk 5 minutes and drive 10 minutes) are confirmed only after the survival report of slice S5 exists. The 30-minute drive cut-off is specified for staffing only and is not one of those defaults. |

## Open questions and assumptions

ASSUMPTIONS (each also marked where it is used):

1. Method functions live in `eii_core.calc` (MTH-01); the reliability cut point is 30, and there is no shrinkage (MTH-13, MTH-14).
2. Municipal residents for May 2025 come from `pub_population_municipality` for 2025 (111,282 and 3,219,982); no LQ below a local count of 10; the national share is fixed in the LQ interval (C1, MTH-16).
3. C6 is served by `scan_places`; its box, confidence filter and radius follow the research runs, and the seed is not yet recorded (section 2, C6).
4. C4: opening days default to 30; `U = 0` is break-even and is the default; mode A treats staff as varying with sales; mode B uses the user's staff cost.
5. The 1 GWh base filter for zone rankings (MTH-41). Basket lines follow PUB-42 and PUB-44 (MTH-30).
6. District population for C7 is read from `pub_census_district` and the centre is the centroid of `district.geometry`. The private-employer share is a proxy for coverage only when that census layer is licensed (C8).
7. C10: the statutory minimum is a rule row in `pub_wage_table`; the staffing area is a 30-minute drive, available only to `staffing_and_pay`; the public wage table is combined across sexes (MTH-24, MTH-44).
8. Dirichlet weight draws for rank stability (MTH-45).

Open items from the master design that touch this document:

- OI-03: the two restaurant totals and the two wage-table means. C3 and C4 stay hidden until it is closed (MTH-23, MTH-29).
- OI-04: the census map layers' licence. Until it is recorded, C7 resident weights and C8 shares do not enter a release. The coverage bar uses the finest licensed geography and names it, or returns `NO_DATA`.
- OI-11: privacy thresholds are proposals. C7 earners mode and C10 inherit the exported tier; they do not set a second threshold.

Open questions:

- Which months besides the three named ones does the bulk rule flag, once the median is taken over the 125-month calendar (C2)?
- The Wilson count's period, the C5 HHI and trend, the C6 seed and remaining settings, the C7 coordinates and weights, and the C14 median prices in riyals are not pinned. slice S7 fails while any of them remains unpinned (MTH-03, MTH-51).
- The 30-minute staffing catchment has not been timed, so its cell range is not written on C10.

## Sources

All retrieved 2026-11-11 unless stated. Research figures were gathered on 2026-11-11 by the project's economic-methods, graph, public-data and feasibility reviews from the sources below.

Qatar Open Data Portal (CC BY), dataset pages under https://www.data.gov.qa/explore/dataset/:

- Licences (Ministry of Commerce and Industry): `moci-active-certificates-by-municipality-and-business-activity`, `moci-canceled-certificates-by-municipality-and-business-activity`, `moci-issued-certificates-by-municipality-and-business-activity` (the last only to show it is incomplete).
- Population and wages (National Planning Council): `population-and-labour-force-by-municipality`, `workers-in-paid-employment-15-years-and-above-and-monthly-average-wage-q1` (by occupation), `workers-in-paid-employment-15-years-and-above-and-monthly-average-wage-q` (by activity).
- Restaurant sector accounts (National Planning Council): `hotels-and-restaurants-statistics-economic-indicators-in-hotels-and-restaurants-by-activity1`, `hotels-and-restaurants-statistics-estimates-of-intermediate-goods-value-in-hotels-and-restaurants-by0`, `hotels-and-restaurants-statistics-estimates-of-intermediate-services-value-in-hotels-and-restaurants0`, `hotels-and-restaurants-number-establishments-employees-by-size-of-establishment-economic-activity`.
- Imports (National Planning Council): `qatar-imports-2025-2026`, `qatar-imports-2019-2024-copy`.
- Utilities: `electricity-total-consumption-by-zone-number`, `water-total-consumption-by-zone-number`.
- Property sales (Ministry of Justice): `weekly-real-estates-sales-bulletin`.
- Trade by product group (backlog item L3 example): `trade-data-for-pharmaceutical-products`.

Other public sources:

- Statistics authority Census 2020 zone and district layers (no licence stated; OI-04): https://services7.arcgis.com/mffQJB8rpVa5We20/arcgis/rest/services/Population_by_Major_Economic_Sectors_by_Zone_2020_WFL1/FeatureServer and https://services7.arcgis.com/mffQJB8rpVa5We20/arcgis/rest/services/Population_2020_District_Level/FeatureServer
- Overture Maps Foundation places, release 2026-10-21.0 (CDLA Permissive 2.0): https://docs.overturemaps.org/guides/places ; OpenStreetMap Qatar extract (ODbL): https://download.openstreetmap.fr/extracts/asia/qatar-latest.osm.pbf
- International Labour Organization, "Qatar adopts non-discriminatory minimum wage" (Law No. 17 of 2020), checked 2026-11-11: https://www.ilo.org/resource/news/qatar-adopts-non-discriminatory-minimum-wage
- United States Department of Justice, Herfindahl–Hirschman Index definition, checked 2026-11-11: https://www.justice.gov/atr/herfindahl-hirschman-index
- OECD inter-country input-output tables 2025, annex country list: https://www.iioa.org/conferences/32nd/papers/files/5640_ICIO-tiva-ghg2025annex.pdf

Method references (DOI links; the three marked were checked 2026-11-11):

- Kitagawa (1955), components of a difference between two rates: https://doi.org/10.1080/01621459.1955.10501299
- Isserman (1977), location quotient: https://doi.org/10.1080/01944367708977758
- Wilson (1927), probable inference (checked): https://doi.org/10.1080/01621459.1927.10502953
- Benjamini and Hochberg (1995), false discovery rate (checked): https://doi.org/10.1111/j.2517-6161.1995.tb02031.x
- Leslie and Kronenfeld (2011), the colocation quotient (checked): https://doi.org/10.1111/j.1538-4632.2011.00821.x
- Applebaum (1966), trade areas: https://doi.org/10.2307/3150201 ; Luo and Wang (2003), two-step floating catchment: https://doi.org/10.1068/b29120
- OECD and JRC (2008), composite indicators handbook: https://doi.org/10.1787/9789264043466-en ; Saisana, Saltelli and Tarantola (2005): https://doi.org/10.1111/j.1467-985X.2005.00350.x
- Huff (1964), trading areas: https://doi.org/10.2307/1249154 ; Kaplan and Meier (1958): https://doi.org/10.1080/01621459.1958.10501452 ; Dunn (1960), shift-share: https://doi.org/10.1111/j.1435-5597.1960.tb01705.x
- Eurostat and OECD (2007), business demography manual: https://doi.org/10.1787/9789264041882-en ; Hidalgo and Hausmann (2009), economic complexity: https://doi.org/10.1073/pnas.0900943106
