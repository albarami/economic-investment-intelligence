# Decision 0062: Tolerances of the calibration fit (S4-T12)

| | |
|---|---|
| Status | Accepted, 2026-11-19: the owner's single approval of revision 3 (r3), relayed by the owner's advisor at 05:49, in these words: "all yes and the rotation i will tell you when"; every open point takes its stated default; recorded by the lead |
| Date | 2026-11-18; revisions 2 and 3 on 2026-11-19; accepted on 2026-11-19 |
| Owner | The owner |
| Drafted by | Anthropic Claude Opus 5.5, as a senior official-statistics methodologist, for the lead, under the owner's note of 23:13 on 2026-11-18 (the lead proposes; the owner approves the whole record once) and the lead's ruling L-1011 |
| Revised after | The independent review REVIEW-0062-R1 (another maker; REJECTED with findings R1 to R6 and notes N1 to N5). Every section changed in revision 2 is marked **(r2)**. Then REVIEW-0062-R2 (the same reviewing maker; APPROVED with non-blocking notes S1 to S3); every section changed in revision 3 is marked **(r3)** |
| Decided by | The owner, on 2026-11-19, under AGENTS.md rule 46: the owner's note relayed by the owner's advisor at 05:49 answered the advisor's list of five, whose item 4 was this record, with "all yes and the rotation i will tell you when". It is a plain yes: every open point below takes its stated default, X1 stays a named gap (option C of open point 9 was not chosen), and no extra allowance is given beyond the record. Recorded by the lead's ruling L-1063 item 3 |
| Amends | Document 05 section 9 (the tolerance cells of F19 and F21) and section 16 (Annual cross-check X1); TASKS.md S4-T12 (an amendment line); the accepted-record sentence and the Decision records table of docs/README.md, with the status of [decision 0064](0064-the-narrowing-rows-decided.md), whose row 9 this record decides; OPEN_ITEMS.md OI-307, closed. Not changed by this record: SYN-60's `custodian/mobility/scorecard.yaml`, the calibration manifest, the S4-T12 roster declarations of plan revision 2 page 2 and any code under `custodian/` or `core/`, which belong to task S4-T12 (Consequences) |
| Purpose | Propose every tolerance that the S4-T12 fit needs and no document sets, each with the method that produced it and an executable planted violation, or record that it stays open |
| Read first | Document 05 section 9 (F7 to F21), SYN-31 to SYN-35, SYN-60, SYN-86, SYN-89 to SYN-92, section 16; document 07 the Interval paragraph, MTH-12, MTH-13; document 12 TST-265; decisions 0031 item 6, 0036 items 4 and 6, 0037, 0040 items 5 and 6, 0050 items 2 and 3, 0051 items 1 to 8; the S4-T12 plan revision 2 |

## Summary for the owner (r2; r3)

How to read this table:
- **"stays open"** means no defensible method gives the value. The check stays a named gap and S4-T12 acceptance stays incomplete.
- **"Owner choice"** is "yes" when the record asked the owner a separate question about the value (the open points at the end). The owner's yes of 2026-11-19 accepted the default of each such point. Otherwise the value needed only the owner's single approval.
- **Rules B, H, W and A** are the four exact rules for a share that the generator draws. They are explained under Method sources.
- **"Per declaration"** means the producing task declares which rule applies; with no declaration the check is a `MISSING_METHOD` gap, never a pass.
- Nothing was active before the owner's yes of 2026-11-19.

| # | Value | Proposal or "stays open" | Method in one line | Owner choice |
|---|---|---|---|---|
| 0 | Fit-wide level for every drawn share | 95%, one family over all drawn-share tests of the fit | Doc 07's 95%; Bonferroni over K tests, K frozen from declarations and denominators | yes (points 8 and 10) |
| 1 | SIZE `fit.public_size.tolerance` | 2 percentage points per Public class share, cells of 1,000 units or more, the table's own classes | Pack convention F7/F8 (doc 05 section 9) | yes (point 5) |
| 2 | NATIONALITY `fit.comp_nat_act.tolerance` | Rule B on the Qatari share by activity, or H or A per declaration | Exact binomial (or hypergeometric) tails, tested code | yes (point 8) |
| 3 | EMPLOYMENT_GENDER `fit.gender_mix.tolerance` | Rule B by occupation × activity per declaration; `NOT_DRAWN` without the table | Exact binomial tails, tested code | yes (point 8) |
| 4a | SPREAD `fit.salary_spread.estimator` | Hyndman–Fan type 7 | Tested: it recovers the declared construction | no |
| 4b | SPREAD `fit.salary_spread.ratio_definition` | R_p = Q̂(p) / Q*(p), each declared p, basic and net apart | Decisions 0036 item 6 and 0051 items 2 and 6 | no |
| 4c | SPREAD `fit.salary_spread.tolerance` | Q̂(p) within q/2 of the construction's own exact type-7 value L(p); **extra allowance zero**; every group of 1 job or more | Exact construction prediction plus the rounding bound only, tested code | yes (point 3) |
| 5 | MEANS `fit.public_mean.tolerance` | 10% of the Public figure | Pack convention F11 (doc 05 section 9) | yes (point 4) |
| 6 | F15 estimator, tie rule, district rule | Average-rank Spearman; mid-ranks; published district medians only | Tested code; X1's existing `tie_rule: average_ranks` | no |
| 7 | F19 `scorecard.calibration.F19.tolerance` | Rule proposed; **the number stays open** | Leave-one-out median gap of complete years, with a flat-shape guard, tested code | yes (point 1) |
| 8 | F21 `scorecard.calibration.F21.tolerance`, minimum venues, years | Rule proposed; minimum venues 3; no years apply; **the number stays open** | Same rule over venues; 3 read from decision 0031 item 6 | yes (points 2 and 13) |
| 9 | MOVEMENT_AGE `fit.mob.age_band.tolerance` | Rule B on persons for presence splits, Rule W on person trips for flow splits, per declaration | Exact tails, tested code | yes (point 8) |
| 10 | MOVEMENT_GENDER `fit.mob.gender.tolerance` | As item 9 | Exact tails, tested code | yes (point 8) |
| 11 | MOVEMENT_NATIONALITY `fit.mob.nationality_group.tolerance` | Exact for the simulated groups; **`international_visitors` stays open** | Aggregation identity (SYN-89) | yes (point 6) |
| 12 | JOINERS `fit.wage.joiner_rate.tolerance` | Rule B or A per declaration, n = the previous month's covered stock | Exact tails, tested code | yes (point 8) |
| 13 | LEAVERS `fit.wage.leaver_rate.tolerance` | As item 12, closures included; clustered closures are a gap unless declared under Rule W | Exact tails, tested code | yes (point 8) |
| 14 | ACCOMMODATION `fit.res.labour_accommodation_share.tolerance` | Rule B per worker, Rule W per employer cluster (worker-weighted) or A, per declaration | Exact tails, tested code | yes (points 8 and 12) |
| 15 | STALENESS `fit.res.address_staleness.tolerance` | Rule B or A per declaration, n = the residents who moved | Exact tails, tested code | yes (point 8) |
| 16a | X1 threshold, part of `scorecard.cross_check.X1.tolerance` | ρ at least 0.60 | Pack magnitude convention H2 (doc 05 section 16) | yes (point 9) |
| 16b | X1 minimum zones, part of the same declaration | **stays open**; X1 stays a gap until it closes. r3: a conservative candidate of 54 zones and three other options went to the owner at point 9, who accepted its default: X1 stays a gap | No minimum is established by the proposed exact derivation for all admitted tie patterns; coverage/admission policy stays open. | yes (point 9) |
| 17 | OTHER_CORRELATIONS `fit.correlations.additional` | **stays open** | No sourced target in the pack | no |

The single approval also covers three things:
- the zero extra allowance of item 4c;
- the predeclared sample-size and family rule of binding condition 5;
- the declaration duty of the producing tasks set out under Method sources.

## Acceptance (2026-11-19)

The owner accepted revision 3 as written, with one plain yes (Decided by). The accepting change alters no value, rule, threshold, method, plant or test count. It only:
- sets the status, the date, Decided by and Amends;
- writes each open point with the default the owner accepted (Open points);
- puts in the past tense, or replaces, the sentences that said an approval was still to come;
- cites the derivations at their committed place, `docs/decisions/0062/` (Sources).

## What changed in revision 3 (r3)

| Review note (REVIEW-0062-R2) | Section | Change |
|---|---|---|
| S1 | Summary for the owner, item 16b | The impossibility sentence is replaced by the review's wording. |
| S1, developed at the lead's choice | Item 16, V2 and V5; open point 9 | The conservative Cantelli bound is developed as a candidate minimum of **54 zones**, with its method, its conservatism, its coverage cost and the owner's options. New exact finding: a universal minimum must be at least **40** (one high zone against two gives 2/n). Nothing becomes active; X1 stays `MISSING_TOLERANCE`. |
| S2 | Item 16, V3 | The threshold sentence now holds ρ at 0.60 and raises the threshold, as the test does. |
| S3 | Item 4, "What A = 0 means in practice" and V3; open point 3 | SPREAD certifies only the declared percentiles, each within q/2 of L(p). L(p) is named as the n = 30 interval centre, with its five values. |
| — | Sources; the derivation files | REVIEW-0062-R2 and the reviewer's scratch derivation are cited. 13 derivation tests are added (93 in all). |

The rules, values and plants of revision 2 are otherwise unchanged.

## What changed in revision 2 (r2)

| Review item | Change |
|---|---|
| R1 | r1's normal score band (Rule D) and its Šidák level are withdrawn. **Rule B** takes their place: exact binomial tails, equal predeclared tail allocation, Bonferroni over one frozen fit-wide family, with sparse cells and endpoints handled. Power is now computed exactly under the stated alternative. The "no tighter band is lawful" and "fails almost surely" sentences are removed. Fixed pack checks run separately (binding condition 3). The crossing with a 2-point band is put to the owner (point 8). The review's counterexamples are tests. |
| R2 | Each conditional family now binds numerator, denominator, target population, mechanism, weights, conditional independence and eligibility as declarations the producing task must make. The method follows from the mechanism: B, H, W or A, otherwise `MISSING_METHOD`. Person-trip flow targets stay person-trip and accommodation stays worker-weighted. Fixtures cover unequal clusters, repeated trips and a finite population. |
| R3 | SPREAD now compares with the construction's exact type-7 value L(p) plus q/2 only. The interpolation part is zero at grid-aligned knots. r1's envelope is quantified as an extra allowance, not proposed. The p90 = 7,050 counterexample fails. |
| R4 | The n < 30 exclusion is withdrawn. Every group with at least one job is tested. Release and privacy eligibility (MTH-13) is separate and unchanged. The n = 21 case passes. |
| R5 | 0.60 is kept only as the H2 magnitude convention. The minimum of 12 zones and the universal 0.023 are withdrawn. An exact tie-aware permutation calculation is added. The 12-zone tied fixture gives 1/12, and the minimum stays open. |
| R6 | There is one executable derivation plant per value, with a passing or boundary control, including the cross-family K and missing-method branches. These are derivation plants, not the production guards that S4-T12 will build. |
| N1 | The revisions and statuses of decisions 0031, 0050 and 0051 as read are pinned under Sources. |
| N2, N3 | F19 no longer claims robustness. A sensitivity example is added, and each worked example uses one fixture. |
| N4 | The zero extra allowance is stated as part of the approval request. |
| N5 | Binding condition 5 separates forbidden residual-based tuning from the predeclared sample-size and family rule. |

## Context

The S4-T12 plan revision 2 builds the calibration fit so that every missing tolerance shows as a named gap, with no number chosen in its place, and acceptance stays incomplete. The lead's note of 22:45 on 2026-11-18 lists the values that no document sets. The owner's note of 23:13 approves the way of working:
- one record proposes each value with the method that produced it, labelled a recommendation;
- where no defensible derivation exists, the value stays open;
- tolerances must not be loose enough to make a fit pass that should fail;
- there is one planted violation per value.

The lead's ruling L-1011 binds the same points. Each value gives the method that produced it or says "stays open", and nothing is active before the owner's single yes.

This record is documents-only. Its accepting change amends only the pack documents named under Amends; it changes no code, configuration, manifest or test (Consequences).

## Binding conditions of this record (r2)

1. **No value was active before the owner's yes of 2026-11-19.** Until then every declaration below stayed a named gap in the S4-T12 roster. A value of this record reaches `custodian/mobility/scorecard.yaml`, the calibration manifest, the fit roster or a test constant only through task S4-T12, and a value this record leaves open stays a named gap there.
2. **Sources remain the owner's own choice, and no value is reduced without asking the owner** (owner notes of 2026-11-18, 20:21 to 20:53).
   - Where a value depends on a source, a year or a location, this record names the choice and leaves it to the owner.
   - No tolerance, minimum, threshold, level or allowance below may be loosened later without asking the owner. A change after approval needs a new decision record that shows the old and the new value (SYN-35).
3. **Existing tolerances are unchanged, and every fixed pack check still runs on its own (r2).**
   - Unchanged: F7/F8 (2 percentage points, zones of at least 1,000 employed), F11 (10%), F12 (identical order), F13 (15%), F14, F15's 0.1, F16 (exact), F20 (exact), H1 (at least 0.80), H2 (at least 0.60), H3 (within 30%), the unknown-housing thresholds of decision 0050, every exact check, every privacy minimum and attack size, and every solver tolerance.
   - The drawn-share rules below never replace, absorb or weaken one of those checks.
   - A fixed check does not count in the family K of binding condition 5, and its outcome never depends on K.
4. **Reports stay value-free** (SYN-91, TST-265). Every rule is evaluated inside the custodian plane. The fit report carries only `check_id`, `tolerance_ref` and `passed`, plus gap rows `{check_id, gap_reason}`. No target, observed value, residual, count, limit, cell label or probability leaves the fit.
5. **Comparison conventions** (plan revision 2 page 3), r2:
   - Every comparison is exact rational or integer arithmetic. No float decides a pass.
   - Equality at the tolerance passes.
   - A family of cells passes only when every cell passes (AND).
   - An empty family, an empty cell or an undefined statistic is never a pass: it is `FIT_UNDEFINED` or a gap.
   - **Forbidden: tuning on residuals.** A tolerance, level, limit or allowance computed from the output's numerators, observed values or differences from target is refused (`FIT_SPEC_MISSING`).
   - **Approved with this record: the predeclared sample-size and family rule.** Rules B, H and W necessarily use each cell's denominator, the declared unit weights and the fit-wide count K. These are fixed by the frozen roster and the producing task's declarations before any numerator is read. K is computed from declarations and denominators only (`fit_family_size` takes no numerator).
6. **This record proposes no source, no population mapping and no input.**
   - The `inputs.*` declarations of plan page 2 belong to the producing tasks named in the plan, and this record fills none of them.
   - Where a rule holds only under a producing task's declaration, the record says which declaration it needs. Without that declaration the check stays a gap.
7. **Derivation plants are not production guards (r2).** The tests named below are derivation plants on invented fixtures. They show that each proposed rule fails a planted wrong world and passes a right one. The production guards are S4-T12's own plants (plan revision 2 page 3), built and reviewed with the task.

## Method sources (r2)

### Rule B: exact binomial tails (replaces r1's Rule D; r2)

**When it applies.** The producing task declares that each unit of the tested statistic carries equal weight and falls in the category independently with the same probability t, the target (`iid_equal_weight`). The count k of n units is then Bin(n, t).

**The rule (recommendation).** Let c = α / (2K), with α = 5% (the pack's 95%, document 07 Interval paragraph) and K the fit-wide number of tests.
- The cell passes if and only if P(X ≤ k) ≥ c and P(X ≥ k) ≥ c, for X ~ Bin(n, t).
- Equivalently, lo ≤ k ≤ hi, where lo is the smallest k with P(X ≤ k) ≥ c and hi is the largest k with P(X ≥ k) ≥ c.
- The tails are computed exactly in integer arithmetic (`binomial_limits`).

**Why it is valid at every n.**
- Under the target, each tail rejects with probability below c, so a cell rejects with probability below α / K.
- Bonferroni then holds the whole fit's false-fail chance below α without any independence assumption. This matters for movement cells, which are dependent, and across check families.
- The limits are checked against the brute-force acceptance set for every n from 1 to 35 (`RuleB.test_limits_equal_the_brute_force_acceptance_set`).
- The bound is checked at n = 1, 2, 5, 10, 30 and 80, at sparse, middle and endpoint targets, for K = 1, 8 and 1,000 (`RuleB.test_cell_false_fail_is_below_alpha_over_k_for_every_small_cell`).

**Tail allocation.** Equal, α / (2K) per tail, declared before the run. No one-sided test is proposed.

**K (r2).**
- K is one count for the whole fit: the number of drawn-share tests summed over every family of the fit (nationality, gender, movement, flows, accommodation, staleness).
- A cell of two categories is one test, because k and n − k reject together. A cell of three or more categories is one test per category.
- Exact checks (Rule A) and fixed pack checks use no part of α.
- K is computed from the frozen roster and the denominators before any numerator is read (`CrossFamilyK`).
- K = 1,000 in the worked examples is invented. The real K comes from the frozen roster.

**Edge cases.**
- A target of 0 requires k = 0, and a target of 1 requires k = n.
- n = 0 is `FIT_UNDEFINED`.
- A sparse cell is valid but has little power. Example: at n = 10 and t = 1% only k ≥ 2 fails, so a downward bias there cannot be seen.

**What a pass means.** A pass shows only that the count is consistent with a draw from the target at the stated level. It does not show that any bias smaller than the detectable size is absent. No maximum permissible discrepancy is inferred from a failure to reject.

**The review's counterexamples** (exact; `RuleB` tests and the derivation module's printed output):

| Case | r1's normal band, exact false fail | Rule B limits | Rule B, exact false fail |
|---|---|---|---|
| K = 1, n = 10, t = 1% | 0.0956 (= 1 − 0.99¹⁰) | 0 to 1 | 0.0043 |
| 8 such cells, K = 8 | 0.5525 (= 1 − 0.99⁸⁰) | 0 to 2 | 0.0009 |
| K = 1,000 cells, n = 30, t = 0.1% | about 1 | 0 to 2 | 0.0040 |
| K = 20 cells, n = 400, t = 30% | 0.0520 | 93 to 148 | 0.0431 |

**Power, computed exactly under the actual alternative.**
- Take n = 1,000, t = 2%, K = 1,000. The limits are 5 to 40.
- r1 claimed 95% power for a 2.52-point bias. The exact power of r1's own band there is 0.882, and Rule B's exact power is 0.759.
- The smallest upward bias that Rule B catches with at least 95% exact power is **3.18 points** (`least_bias_for_power`, 0.01-point steps).
- Power for any other cell is computed the same way when the lead needs it. No power figure in this record comes from a normal approximation.

**Worked limits at K = 1,000** (`RuleB.test_worked_limits_of_the_record`):

| n | t | Limits lo to hi | In points |
|---|---|---|---|
| 5,000 | 4% | 146 to 258 | −1.08 / +1.16 |
| 2,000 | 12% | 183 to 301 | −2.85 / +3.05 |
| 50,000 | 30% | 14,585 to 15,417 | −0.83 / +0.83 |
| 50,000 | 70% | 34,583 to 35,415 | −0.83 / +0.83 |
| 20,000 | 8% | 1,447 to 1,758 | −0.77 / +0.79 |
| 200,000 | 65% | 129,134 to 130,864 | about ±0.43 |
| 1,000,000 | 1.5% | 14,510 to 15,495 | about ±0.05 |

### Rules H, W and A: the other declared mechanisms (r2)

- **Rule H (without replacement).**
  - When: the producing task fixes a count M of marked units in a finite population of N and the tested cell is a random set of n of them.
  - Law: the cell count is hypergeometric. Rule H is the same two-tail test on the exact hypergeometric law (`hypergeometric_pmf`, `pmf_tail_pass`).
  - Binomial on such a cell is too wide. Example, N = 100, M = 30, n = 50 at K = 1: binomial accepts 9 to 22, while the exact law accepts 11 to 19 (`FinitePopulation`).
- **Rule W (independent units of unequal weight).**
  - When: the unit of the draw is not the unit of the statistic. Examples are one person whose several trips all carry the person's category, or one employer cluster whose workers share one accommodation draw.
  - Law: the tested count is S = Σ w_j B_j, with B_j independent Bernoulli(p_j) and w_j the declared weight (trips of the person in the cell, or workers of the cluster in the cell). Rule W is the same two-tail test on the exact law of S (`weighted_bernoulli_pmf`). A count the mechanism cannot produce fails.
  - The statistic stays trip-weighted or worker-weighted. The target holds only if Σ w_j p_j = t · Σ w_j, which the declaration must state.
  - Cost: exact computation grows with the number of units times the total weight. The S4-T12 build must show it is computable at the real cell sizes, or the check stays a `MISSING_METHOD` gap.
- **Rule A (deterministic allocation).**
  - When: the producing task allocates round(n · t) units under a declared rounding (half to even in the fixtures).
  - The check is exact: any difference is `FIT_EXACT_MISMATCH`, and no α is spent.
  - Allocation without a declared rounding is a `MISSING_DECLARATIONS` gap.
- **No declared mechanism, or another mechanism** (for example a Poisson count, or a mixture of individual and cluster draws): `MISSING_METHOD`. Rule B is refused on units of unequal weight, which also yields `MISSING_METHOD` (`Declarations`, `RepeatedTrips`).

### The declaration each conditional family needs (r2)

Every conditional family needs seven declarations from its producing task in its named `inputs.*` declaration, frozen before the run:
- **numerator**
- **denominator**
- **target population** (where the target share applies)
- **unit and weights**
- **mechanism** (iid equal weight, weighted independent, without replacement, or deterministic allocation)
- **conditional independence** (what the draw may not depend on)
- **eligibility and omission**

A missing field is `MISSING_DECLARATIONS`, and a missing or unsupported mechanism is `MISSING_METHOD`. Neither is ever a pass. What this record binds for each family:

| Family | Numerator / denominator | Target population and target | Mechanism → rule | Weights, independence, eligibility |
|---|---|---|---|---|
| MOVEMENT_AGE, MOVEMENT_GENDER, presence splits | Simulated persons present in the cell in a band / all simulated persons present, each once, counted **before panel expansion** | The population for which the producing task declares the anchor share of `mob.split_anchor.population_age_sex` to be the expected share. If behaviour depends on age or gender, a presence cell is not that population: the family must then be declared at the grain where the anchor holds (for example all simulated persons of the municipality, each once), or it is a gap | iid per person → B; allocation → A | Equal weights. The person's band must not depend on where and when they are present, unless the population is declared at the anchor grain. Cells the count tables omit under the panel minimum are declared before the run, never chosen after |
| MOVEMENT_AGE, MOVEMENT_GENDER, flow splits | Person trips of the cell by persons in the band / all person trips of the cell (SYN-89: person trips, not visitors, not vehicle trips) | The trip-weighted share whose expectation the producing task declares | Per-person draw → W with weights = the person's trips in the cell; B is refused unless every weight is 1 | Trip counts are part of the frozen structure, read before categories. The band must not depend on the number of trips, or the expectation must be declared |
| MOVEMENT_NATIONALITY, simulated groups | Simulated persons (presence) or their trips (flow) by group / the same total | The simulated people behind the cell | Aggregation → exact | None |
| MOVEMENT_NATIONALITY, `international_visitors` | Not declared by the pack | Not declared | **Stays open** → `MISSING_METHOD` | Closed by S4-T09 Part B's declaration |
| NATIONALITY (`comp_nat_act`) | Synthetic private workers in the activity who are Qatari / all synthetic private workers in the activity, on the table's own population and period | The activity's Public Qatari share, if `inputs.comp_nat_act.compatibility` declares it to be the draw's target | iid per worker → B; a fixed national count spread at random → H with that law's own target; fixed per-activity count → A | Equal weights; the worker's group must not depend on anything but the declared target cell |
| EMPLOYMENT_GENDER | Synthetic private workers of a gender in occupation × activity / those with gender drawn | The owner's table share for the cell (never read here) | iid per worker → B (the S4-T13 draw read at its head); allocation → A | Without the table: `NOT_DRAWN` |
| JOINERS | Spells started in month m / covered stock at the end of month m − 1 (doc 05 section 7.1) | `wage.joiner_rate` | Bin(stock, t) count → B; round(stock · t) → A; a Poisson count → `MISSING_METHOD` | One cell per month. The months of the window are declared before the run |
| LEAVERS | Spells ended in month m, staff of closing establishments included / covered stock at the end of month m − 1 | `wage.leaver_rate` | iid per worker → B; allocation → A; closures drawn per establishment → W only if declared as disjoint independent units, otherwise `MISSING_METHOD` | As joiners |
| ACCOMMODATION | Workers of the employment feed in occupation group g whose residence row is `labour_accommodation` / workers of the feed in g, worker-weighted (decision 0050 item 2) | `res.labour_accommodation_share.g`, from the manifest only | iid per worker → B; per employer cluster → W, with weights = the cluster's workers of group g; allocation → A. Never a count of clusters in place of workers | The declaration states whether rows of housing class `unknown` are in the denominator. Anchored F3/F7 margins prevail: a conflict is reported, never resolved by widening |
| STALENESS | Movers who keep their previous cell / residents who moved (SYN-33) | `res.address_staleness` | iid per mover → B; allocation → A | One national cell |

### Fixed bands and Rule B: the trade-off (r2)

The pack holds no fixed band for any drawn share above. The nearest convention is F7/F8's 2 points. The two acceptance sets cross, so neither rule is stronger everywhere:

| Cell (K = 1,000) | Count | Rule B | 2 points |
|---|---|---|---|
| n = 2,000, t = 12% | 298 | passes | fails |
| n = 5,000, t = 4% | 280 | fails | passes |
| n = 1,000, t = 2% | 0 (the group was never drawn) | fails | passes |

There are three ways to use them. The owner chooses at open point 8:
- **(a) Rule B alone (recommended).** The fit-wide false-fail chance of a correct world stays below 5%.
- **(b) Rule B AND 2 points.** This is stronger where the 2-point band is the narrower one, at a known cost: a correct world fails much more often. At n = 400 and t = 30%, one cell fails with exact probability 0.354, against 0.00004 under Rule B alone. At n = 2,000 and t = 12% it fails with exact probability 0.0053, which compounds over many cells.
- **(c) 2 points alone (not recommended).** It passes a group that was never drawn.

### The F7/F8 convention (read from the pack)

Document 05 section 9 sets F7/F8 at 2 percentage points with a floor of 1,000 employed per zone. F7/F8 compares Public share margins against a synthetic world built from other inputs. This record reuses that convention only for a cross-source comparison of the same kind (SIZE), not for a drawn share.

### The leave-one-out median gap (computed by tested code; r2)

For F19 and F21 the anchor is a set of rows of the Public source itself: the complete years of the museum series, or the venues of a category group. Each row is turned into shares.

- **The rule.** The tolerance τ is the median, over the rows, of the largest difference between one row and the equal-weight mean of the other rows (`loo_median_gap`). It needs at least 3 rows.
- **What it measures.** The anchor's own row-to-row spread: a simulated shape passes if it matches the anchor as closely as a typical real row matches the others.
- **It is not robust in general (r2, N2).** The median is taken over leave-one-out means, and each of those means moves with every row. Sensitivity fixture (`PlantF19.test_sensitivity_one_row_moves_tau_from_zero_to_a_quarter`):
  - four identical rows (1, 0, 0) give τ = 0;
  - adding one row (0, 1, 0) gives τ = 1/4;
  - the flat-shape guard still admits that anchor, because the flat gap is 7/15.
- **The choice of rows matters, and it is the owner's** (open point 1). On the invented museum fixture the effect is small:
  - fixture A, four clean years: τ = 1/50;
  - fixture B, the same years plus one closure year: τ = 13/600.

  On another anchor the effect can be large. The lead's run therefore reports τ for each candidate set of years.
- **Informativeness guard (recommendation).** The tolerance is admitted only if the flat shape fails it. Otherwise the anchor cannot tell its shape from noise, and the check is a gap (`UNSUPPORTED_COVERAGE`), never a pass.

## The values

Each value lists:
- its declarations (plan revision 2 names);
- V1, the recommendation, accepted by the owner's yes of 2026-11-19;
- V2, the method;
- V3, failing and passing examples;
- V4, the planted violation and its executable derivation test;
- V5, what stays open.

All example figures are invented. Every Rule B example uses an invented K = 1,000.

### 1. SIZE: `fit.public_size`

- **Declarations filled:** `fit.public_size.tolerance`. Not filled: `inputs.public_size.compatibility` (S2-T02, S2-T11, S4-T11).
- **V1 (recommendation):**
  - Each share in a Public size class differs from the world's share in the same class by at most 2 percentage points.
  - Shares are taken in the Public table's own classes and in the table's own measure (establishments or employees), within each activity cell of the table. Seven classes stay seven, and nothing is re-banded (decision 0040 item 5; decision 0051 item 2).
  - Only activity cells with at least 1,000 units of that measure in both sources are compared. A smaller cell is a gap (`UNSUPPORTED_COVERAGE`).
  - The world assigns each unit to a class by its recorded December headcount.
- **V2 (method):** read from the pack: the F7/F8 convention for a like cross-source check (document 05 section 9).
  - The size tables run 2015 to 2022 against a 2025 world (document 04 `est_size_act`, `sec_hr_size`).
  - Document 04 records no stated precision for them, so no tolerance can be read from the publisher.
  - This is a cross-source comparison, not draw noise, so Rule B is not used.
- **V3 (examples):** an activity cell of 4,000 employees with a Public class share of 30%.
  - **Fails:** a world share of 32.01%.
  - **Passes:** 32.00% (equality is inclusive).
- **V4 (planted violation):** `plant_size_class_shift_3pp`. A world moves 3 points from the smallest to the largest class in a cell of 4,000. **SIZE must fail.**
  - Tests: `PlantSize.test_plant_three_point_shift_fails`, with the boundary control `test_control_two_points_passes_at_the_boundary`.
  - Re-banding seven classes into four is refused (`FIT_PUBLIC_SIZE_REBANDING`), and a cell under 1,000 is a gap (`test_small_cell_is_a_gap_and_rebanding_is_refused`).
- **V5 (open):** none for the value. See open point 5.

### 2. NATIONALITY: `fit.comp_nat_act` (r2)

- **Declarations filled:** `fit.comp_nat_act.tolerance`. Not filled: `inputs.comp_nat_act.compatibility`, `inputs.nationality_mix` (S4-T11).
- **V1 (recommendation):** the Qatari share of synthetic private workers in each activity cell of `comp_nat_act`, tested by the rule its declaration selects.
  - The family's declaration row is in the table under Method sources.
  - The target is the Public Qatari share that the nationality draw uses as its anchor (decision 0040 item 6).
- **V2 (method):** Rule B (or H or A) as above, tested code.
  - It is valid only when `inputs.comp_nat_act.compatibility` declares the Public share to be the draw's own target for that activity. Otherwise the check is a gap (`MISMATCHED_POPULATION` or `MISMATCHED_PERIOD`).
  - Non-Qataris are never split (`FIT_UNSUPPORTED_NATIONALITY_SUBDIVISION`).
- **V3 (examples):** n = 5,000, target 4%, limits 146 to 258.
  - **Passes:** 146, 200 and 258.
  - **Fails:** 145 and 259.
- **V4 (planted violation):** `plant_national_share_for_every_activity`. One national weight of 6% is used where the activity's target is 4%, giving 300 of 5,000. **NATIONALITY must fail.**
  - Tests: `PlantNationality.test_plant_national_share_for_every_activity` and `test_control_and_boundaries`.
  - While the generator draws nationality nationally rather than by activity, as at the S4-T03 head read for r1, the check correctly fails wherever the activity share differs.
- **V5 (open):** none, given the declaration.

### 3. EMPLOYMENT_GENDER: `fit.gender_mix` (r2)

- **Declarations filled:** `fit.gender_mix.tolerance`. Not filled: `inputs.gender_mix` (S4-T11, S4-T13).
- **V1 (recommendation):** Rule B (or A) per declaration, on each gender share in each occupation group × activity cell of the owner's gender table.
  - The target is the table's share, which this record never reads.
  - Without the table the field is null, and the check is a `NOT_DRAWN` gap: no zero, no pass, and no Public substitute (decision 0037; SYN-92; `PUBLIC_SEX_JOIN_FORBIDDEN`).
- **V2 (method):** Rule B, tested code. Gender is drawn per worker from the owner's table under decision 0037, as in the S4-T13 code read for r1.
- **V3 (examples):** n = 2,000, target 12%, limits 183 to 301 (−2.85 / +3.05 points).
  - **Passes:** 183, 240 and 301.
  - **Fails:** 182 and 302.
  - A cell this size cannot reveal a small bias: Rule B's exact power is low for a shift under about 3 points. A smaller bias repeated over many cells is not claimed to be caught.
- **V4 (planted violation):** `plant_uniform_gender_draw`. A 50/50 draw gives 1,000 of 2,000 where the target is 12%. **EMPLOYMENT_GENDER must fail.**
  - Tests: `PlantEmploymentGender.test_plant_uniform_gender_draw`, `test_control_and_boundaries` and `test_without_the_table_it_is_not_drawn_never_a_pass`.
- **V5 (open):** none.

### 4. SPREAD: `fit.salary_spread` (r2; r3)

- **Declarations filled:**
  - `fit.salary_spread.estimator`
  - `fit.salary_spread.ratio_definition`
  - `fit.salary_spread.tolerance`, with extra allowance zero
  - Not filled: `inputs.salary_spread.format`, `inputs.pay_reference`, `inputs.coverage_policy` (S4-T03; decision 0051 A2 to A4).
- **V1 (recommendation):**
  - **Estimator:** Hyndman–Fan type 7.
    - Sort the group's final values x₍₀₎ ≤ … ≤ x₍ₙ₋₁₎ and set h = (n − 1)·p and j = ⌊h⌋. Then Q̂(p) = x₍ⱼ₎ + (h − j)(x₍ⱼ₊₁₎ − x₍ⱼ₎); a group of one has Q̂(p) = x₍₀₎.
    - It is applied separately for basic and net, in each spread group (occupation group × actual activity × world band; decision 0036 items 4 and 6, decision 0051 item 2), at every quantile p the declared series carries.
  - **Ratio definition:** R_p = Q̂(p) / Q*(p), where Q*(p) is the declared value of the owner's series at p.
  - **The construction's own value L(p), r2.** L(p) is type 7 applied to the undisturbed, unrounded construction of decision 0051 item 3: ranks i/(n − 1), a singleton at rank 1/2, linear between declared quantiles, flat tails. In closed form:
    - n = 1: L(p) = Q*(1/2).
    - n ≥ 2: with w = 1/(n − 1), L(p) interpolates Q* linearly between the rank-grid points j·w and (j + 1)·w.
    - The signed interpolation discrepancy is D_p = L(p) − Q*(p). It is zero at a grid-aligned knot, where (n − 1)·p is an integer.
  - **Tolerance, r2:** at every declared p, |Q̂(p) − L(p)| ≤ q/2 + A, where q is the declared monetary precision and A is the extra allowance.
    - Equivalently, R_p lies in [(L(p) − q/2 − A) / Q*(p), (L(p) + q/2 + A) / Q*(p)].
    - **A = 0 was part of the approval request (N4), and the owner accepted it.**
  - **Groups tested, r2 (R4):** every spread group with at least one job. A group with no job has no SPREAD row.
    - MTH-13's n ≥ 30 is a display-reliability and privacy publication rule. It is unchanged and does not govern this internal check.
- **V2 (method):** computed by tested code (`construct`, `hf7`, `predicted_hf7`, `interpolation_discrepancy`, `spread_check`).
  - The closed form equals type 7 of the construction for every n from 1 to 159 (`PlantSpread.test_prediction_equals_type7_of_the_construction`).
  - Rounding each value to q, half to even, moves each order statistic by at most q/2. Type 7 is a convex combination of two order statistics, so Q̂ moves by at most q/2. So q/2 is the only allowance the undisturbed construction needs, and every rounded construction from n = 1 to 159 passes with A = 0 (`test_every_rounded_construction_passes_with_zero_allowance`).
  - Type 6 is not construction-consistent: it misses p25 at n = 21, where type 7 recovers it.
- **What A = 0 means in practice (r3, S3).** Every declared final percentile must be within q/2 of L(p); other aspects of the distribution are not certified. A processing step fails this check when the resulting declared percentile lies outside that interval. Decision 0051 item 6 names the steps that can disturb the construction: tail truncation, tiny cells, mean scaling, the basic floor and median repair.
  - Such a step can be a median-repair shift in a level cell that pools spread groups, or a mean scaling factor other than 1. A step that leaves every declared percentile inside its interval passes.
  - Decision 0051 items 1 and 4 already provide that incompatible simultaneous targets stop world acceptance. No source or pack convention gives a positive allowance.
- **V3 (examples):** invented series p10 = 1,000, p25 = 1,500, p50 = 2,500, p75 = 4,000, p90 = 7,000; q = 1.
  - **n = 101:** every knot is grid-aligned, D_p = 0, so each Q̂(p) must lie within 0.5 of the declared value.
    - **Fails:** p90 at 7,050 with the median exact (`test_plant_p90_7050_fails_under_zero_allowance`). This is the review's counterexample.
    - **Fails:** tails squeezed by 10% around an exact median, and a 10% scaling followed by median repair.
    - **Passes:** the rounded construction.
  - **n = 30 (r3, S3):** the construction itself gives D_p of 300/29, 125/29, 500/29, 2,625/29 and −1,800/29 (about +10.3, +4.3, +17.2, +90.5 and −62.1). The interval centre is L(p) = Q*(p) + D_p: 29,300/29, 43,625/29, 73,000/29, 118,625/29 and 201,200/29 (about 1,010.3, 1,504.3, 2,517.2, 4,090.5 and 6,937.9). The check accepts Q̂ from L(p) − 0.5 to L(p) + 0.5. A final p75 of exactly 4,000 at n = 30 is therefore a disturbance and fails.
  - **n = 21:** every knot is recovered exactly and the group passes (`test_n21_internal_group_is_tested_and_passes`; R4).
  - **n = 1 and 2** are definable: a singleton must equal the declared median, and a pair must equal the two flat tails (`test_singleton_and_pair_are_definable`).
- **V4 (planted violation):** `plant_tails_squeezed_median_exact` and `plant_p90_7050`. **SPREAD must fail** in both, even though the exact-median check passes (plan plant 2; decision 0051 item 8). The tests are listed in V3.
- **r1's envelope, quantified as an extra allowance (r2, R3).** r1 accepted |Q̂ − Q*| ≤ B_p + q/2, with B_p = (w/4)·Σ|slope change| over the knots in the rank bracket.
  - Beyond the proposed interval it admits an extra B_p + |D_p| (`r1_extra_slack`).
  - At n = 101 that is 25/3, 5/3, 5, 35 and 50 at p10 to p90. At n = 21 it is 125/3, 25/3, 25, 175 and 250.
  - It is not proposed, and it is not adopted: the owner accepted zero extra allowance (open point 3). The test `test_extra_allowance_is_explicit_and_quantified` shows that an allowance of 49.5 at p90 would pass the 7,050 plant.
- **V5:** none open for the rule. A basic p10 below `wage.minimum` stays an input conflict that fails (decision 0051 item 4).

### 5. MEANS: `fit.public_mean`

- **Declarations filled:** `fit.public_mean.tolerance`. Not filled: `inputs.public_mean.admissions`, `inputs.pay_resolution`, `inputs.monthly_wages` (S2-T03, S2-T11, S4-T11, S4-T03 Part B).
- **V1 (recommendation):** each further admitted Public monthly mean (`wage_occ` by occupation, `wage_act` by activity) may differ from the remeasured covered synthetic mean, on the same basis, population and period, by at most 10% of the Public figure.
  - An annual figure is never compared as monthly (`ANNUAL_AS_MONTHLY`).
  - OI-03 stays.
- **V2 (method):** read from the pack: the convention for the like check F11 (document 05 section 9; kept by decision 0051 item 6). Decision 0051 item 1 scales, repairs and then remeasures, the same sequence as F11. F13's 15% is not reused, because F13's figure is annual.
- **V3 (examples):** Public mean 5,000.
  - **Passes:** 4,500 and 5,500 (equality is inclusive).
  - **Fails:** 5,501.
- **V4 (planted violation):** `plant_mean_lifted_after_repair_12pct`. **MEANS must fail.**
  - Tests: `PlantMeans.test_plant_mean_lifted_twelve_percent`, `test_control_and_boundary` and `test_annual_is_never_monthly`.
- **V5 (open):** none for the value. See open point 4.

### 6. F15: estimator, tie rule and district eligibility (r2: the worked figures)

- **Declarations filled:** `fit.res.wage_sorting.estimator`, `fit.res.wage_sorting.tie_rule`, `fit.res.wage_sorting.district_eligibility`. Not filled: `inputs.residence_wages_prices` (S4-T03 homes). The tolerance, within 0.1 of `res.wage_sorting`, is existing and unchanged.
- **V1 (recommendation):**
  - **Estimator:** Spearman's coefficient, as Pearson's correlation of average ranks. There is one pair per employed family-housing resident: the monthly wage on the declared basis and month, and the median sale price of the resident's home district.
  - **Tie rule:** average (mid) ranks on both sides. The shortcut 1 − 6Σd²/(n(n² − 1)) is forbidden, because it is wrong under ties, and ties are certain here.
  - **District eligibility:** a district counts only if the admitted Public sales source publishes a median sale price for it in the declared period. A district with no published median, or a suppressed one, is excluded, never imputed. No minimum number of sales is added beyond the publisher's own rule.
  - Fewer than two distinct values on either side is `FIT_UNDEFINED`.
  - The band comparison is exact: no square root is taken (`spearman_cmp`).
- **V2 (method):** computed by tested code (`average_ranks`, `spearman_cmp`, `f15_check`). Average ranks are X1's tie rule already fixed in `scorecard.yaml`, and plan revision 2 says "reuse average-rank Spearman".
- **V3 (examples):** target 0.3, band [0.2, 0.4].
  - On the plant fixture, ρ ≈ 0.1429 (r1 wrote 1/7; that was a rounding) and fails, while the shortcut gives 3/14 ≈ 0.214 and would pass.
  - On the control fixture, ρ ≈ 0.289 and passes, while the shortcut gives 23/56 ≈ 0.411 and would fail.
- **V4 (planted violation):** `plant_spearman_shortcut_under_ties`.
  - Wages: 9000, 1500, 9000, 9000, 1000, 1000, 3000, 1200.
  - District prices: 20, 30, 10, 20, 10, 10, 20, 30.
  - **F15 must fail.**
  - Tests: `PlantF15.test_plant_shortcut_passes_a_world_the_estimator_fails`, with the control `test_control_estimator_passes_a_world_the_shortcut_fails` (wages 3000, 3000, 3000, 9000, 1500, 1200, 3000, 3000; prices 30, 20, 30, 10, 10, 10, 30, 20).
- **V5 (open):** none.

### 7. F19: `scorecard.calibration.F19.tolerance` (r2: V3)

- **Declarations filled:** `scorecard.calibration.F19.tolerance`, rule only; the number stays open. Not filled: `inputs.visitor_month_shape` (S4-T07, S4-T09, S2-T11).
- **V1 (recommendation):** τ₁₉ is the leave-one-out median gap of the complete years that form `mob.visitor_month_shape`.
  - Each year is a row of 12 monthly shares of its year, summed over venues.
  - The value is in **shares**, because `visitors.seasonal_gap` compares shares.
  - It needs at least 3 complete years and is subject to the informativeness guard.
  - F19 passes if the largest monthly difference between the simulated 2025 shape and the anchor is at most τ₁₉.
- **V2 (method):** computed by tested code (`shares`, `mean_rows`, `loo_gaps`, `loo_median_gap`, `max_gap`, `shape_check`).
  - The cube carries a two-level season (section 12.8), so the simulated month shape differs from the anchor by construction. The rule asks whether the model reproduces the anchor as well as one real year reproduces the others.
  - The number must be computed from the hashed public-cache file of `visits_museum`, which this drafting run may not read.
- **V3 (examples, one fixture each; N3):**
  - **Fixture A (four clean years):** τ = 1/50 = 0.02. A flat simulation has gap 37/600 ≈ 0.0617 and **fails**. A simulation equal to the first year **passes** (`PlantF19.test_fixture_a_four_clean_years`, `test_plant_flat_month_shape_fails_and_control_passes`).
  - **Fixture B (the same years plus one closure year):** τ = 13/600 ≈ 0.0217. The flat gap against that anchor is 37/750 ≈ 0.0493 and also fails (`test_fixture_b_with_a_closure_year`).
- **V4 (planted violation):** `plant_flat_month_shape`: every simulated month share is 1/12. **F19 must fail.** If the anchor itself is flat enough that a flat shape passes, or there are fewer than 3 rows, F19 is the gap `UNSUPPORTED_COVERAGE` (`test_flat_anchor_and_too_few_rows_are_gaps`).
- **V5 (stays open, the number only).** It closes when:
  - the owner chooses the complete years (open point 1), seeing τ with and without the candidate unusual year;
  - the lead runs the tested function over the hashed file and records the hash and the result;
  - the owner approves the number before it is copied into `scorecard.yaml` (SYN-60).

  A failed F19 is remedied by a model change, never by a wider τ (document 05 section 9).

### 8. F21: `scorecard.calibration.F21.tolerance`, minimum venues and years of history (r2: the source pins)

- **Declarations filled:** `scorecard.calibration.F21.tolerance`, rule only; the number stays open. Not filled: `inputs.hourly_shape_weather` (S4-T09 Part B, S2-T16, S2-T14).
- **V1 (recommendation):**
  - **Tolerance:** τ₂₁ is one number: the median, over all venue rows, of each venue's leave-one-out gap within its own category group and day type.
    - Each venue row is the venue's 24 hourly indexes divided by their sum, so the pooled shape of SYN-86 is the equal-weight mean of the rows.
    - The value is in **percentage points**, because `hourly.hourly_gap` multiplies by 100.
    - It is measured with the weather modulation off (document 05 section 9).
    - A (group, day type) cell where the flat shape passes τ₂₁ is the gap `UNSUPPORTED_COVERAGE`.
  - **Minimum venues:** 3 (`mob.hourly_shape_min_venues`, decision 0031 item 6). This equals the leave-one-out rule's own minimum. Below it the group keeps the flat shape and has no anchor and no F21 row (SYN-86). Decision 0031 is still Proposed (Sources; open point 13).
  - **Years of history:** none apply to the busyness anchor, which is a retrieved weekly profile with no year rows.
- **V2 (method):** computed by tested code (the same functions as F19). The number needs the hashed public-cache file of the busyness source, which this run may not read.
- **V3 (examples):** three invented venue rows over three hours: the document 07 card C26 venues (20, 40, 40) and (10, 10, 30), and a third venue (2, 3, 5).
  - Their pooled shape is (0.2, 0.3, 0.5) and their leave-one-out gaps are 15, 15 and 0 points, so τ = 15 points.
  - **Fails:** the flat shape, gap 16.7 points, so the cell is informative.
  - **Passes:** (0.25, 0.25, 0.5), gap 5 points.
  - Tests: `PlantF21.test_c26_fixture` and `test_plant_flat_hourly_shape_fails_and_control_passes`.
- **V4 (planted violation):** `plant_flat_hourly_shape`. **F21 must fail** for that group and day type. Two venues give no anchor (`test_below_three_venues_has_no_anchor`). The weather-enabled plant of plan plant 6 stays separate.
- **V5 (stays open):**
  - **The number.** It closes with the lead's run over the hashed file, recorded with its hash, and the owner's approval. Whether a number derived from the provider's data stands in the repository follows decision 0034 (open point 7).
  - **The weather profile's years of history and location.** These are inputs of S4-T09 Part B's modulation (SYN-87), not of F21. They are the owner's source choice (open point 2).

### 9. MOVEMENT_AGE: `fit.mob.age_band` (r2)

- **Declarations filled:** `fit.mob.age_band.tolerance`. Not filled: `inputs.movement_age_split` (S4-T09 Part B; `mob.movement_age_bands`, OI-148).
- **V1 (recommendation):** each `age_band` share (the six bands plus `other`) is tested by the rule its declaration selects.
  - **Presence splits:** Rule B on persons, each once, before panel expansion.
  - **Flow splits:** Rule W on person trips, never Rule B on distinct persons.
  - The target is the anchor share from `mob.split_anchor.population_age_sex`, summed over the source's own categories (SYN-89), at the target population the declaration names. See the declaration table.
- **V2 (method):** Rules B and W, tested code. The tests of different cells are dependent; Bonferroni needs no independence. The r1 Šidák argument is withdrawn.
- **V3 (examples):** n = 50,000 persons, target 30%, limits 14,585 to 15,417.
  - **Passes:** 15,417.
  - **Fails:** 15,418.
- **V4 (planted violations):**
  - `plant_age_band_shift_one_point`: 15,500 of 50,000 against 30%. **MOVEMENT_AGE must fail** (`PlantMovement.test_plant_age_band_shift_one_point`).
  - `plant_flow_split_tested_on_distinct_persons`: a flow cell of 30 persons with 1 to 3 trips each, tested by Rule B on persons. **It must be refused** (`MISSING_METHOD`), while Rule W on its trips passes (`test_plant_flow_split_tested_on_distinct_persons`; `RepeatedTrips`).
- **V5 (open):** none, given the declaration. Without it, the check is a gap.

### 10. MOVEMENT_GENDER: `fit.mob.gender` (r2)

- **Declarations filled:** `fit.mob.gender.tolerance`. Not filled: `inputs.movement_gender_split` (S4-T09 Part B).
- **V1 (recommendation):** as item 9, on each `gender` share. Movement gender is never joined to employment gender (decision 0037; AGENTS.md rule 10).
- **V2 (method):** Rules B and W.
- **V3 (examples):** n = 50,000, invented target 70%, limits 34,583 to 35,415.
  - **Passes:** 35,000.
  - **Fails:** 25,000.
- **V4 (planted violation):** `plant_movement_gender_uniform`: 50/50 where the anchor is 70/30. **MOVEMENT_GENDER must fail** (`PlantMovement.test_plant_movement_gender_uniform`). Plan plant 5's prohibited-join plant (`FIT_RECORD_JOIN_FORBIDDEN`) stays.
- **V5 (open):** none, given the declaration.

### 11. MOVEMENT_NATIONALITY: `fit.mob.nationality_group` (r2: plants)

- **Declarations filled:** `fit.mob.nationality_group.tolerance`, for the groups of simulated people only. Not filled: `inputs.movement_nationality_split` (S4-T09 Part B).
- **V1 (recommendation):**
  - **Groups other than `international_visitors`:** exact. The split is the aggregation of the simulated people behind the cell (`mob.split_nationality_from_simulated`, SYN-89). Any difference is `FIT_EXACT_MISMATCH`.
  - **`international_visitors`:** stays open.
- **V2 (method):** read from SYN-89. The split is an aggregation, not a draw.
- **V3 (examples):** 1,000 persons behind a cell, 140 of them in group A.
  - **Passes:** a written A count of 140.
  - **Fails:** 141.
- **V4 (planted violation):** `plant_nationality_split_redrawn`. **MOVEMENT_NATIONALITY must fail** with `FIT_EXACT_MISMATCH` (`PlantMovement.test_plant_nationality_split_redrawn`). An undeclared `international_visitors` family is a `MISSING_METHOD` gap (`test_international_visitors_without_declaration_is_a_gap`).
- **V5 (stays open, `international_visitors`).** The pack states neither the denominator of the share in each movement cell nor whether it is drawn per person or allocated. It closes when S4-T09 Part B declares the anchor's denominator and mechanism; the rule then follows from the declaration table, and the owner confirms the source (open point 6).

### 12. JOINERS: `fit.wage.joiner_rate` (r2)

- **Declarations filled:** `fit.wage.joiner_rate.tolerance`. Not filled: `inputs.monthly_joiners` (S4-T03 Part B).
- **V1 (recommendation):** each month's joiners as a share of the previous month's covered stock, by the rule the declaration selects (B or A; a Poisson count is a gap). There is one cell per month of the window.
  - The target is `wage.joiner_rate` (ASSUMED 1.5% a month; document 05 sections 3.1 and 7.1).
  - The target is an assumption, so the check proves only that the generator honours its own parameter. It is a calibration fit, which survives the retirement of hiring analysis (decision 0046 item 2).
- **V2 (method):** Rule B or A, tested code.
- **V3 (examples):** previous stock 1,000,000, target 1.5%, limits 14,510 to 15,495.
  - **Passes:** 15,000 and 15,495.
  - **Fails:** 15,496.
- **V4 (planted violation):** `plant_joiners_on_current_stock`: joiners computed on a stock that grew 5% in the month, giving 15,750. **JOINERS must fail** (`PlantFlows.test_plant_joiners_on_current_stock`).
  - **Stated limit:** the same 5% denominator error is not caught in a stock of 100,000 (1,575 against 1,500 passes; `test_the_same_denominator_error_is_not_caught_in_a_small_stock`).
- **V5 (open):** none, given the declaration.

### 13. LEAVERS: `fit.wage.leaver_rate` (r2)

- **Declarations filled:** `fit.wage.leaver_rate.tolerance`. Not filled: `inputs.monthly_leavers` (S4-T03 Part B).
- **V1 (recommendation):** each month's leavers as a share of the previous month's covered stock, including the staff of a closing establishment (document 05 section 7.1), by the rule the declaration selects.
  - The target is `wage.leaver_rate` (ASSUMED 1.5% a month).
  - If closures are drawn per establishment, the leavers are clustered. Rule W then applies only if the declaration makes the establishments and the remaining workers disjoint, independent units; otherwise the check is `MISSING_METHOD`.
- **V2 (method):** Rule B, W or A, tested code.
- **V3 (examples):** the limits of item 12. 14,510 passes and 14,509 fails.
- **V4 (planted violation):** `plant_leavers_exclude_closures`: 1,000 closure leavers left out, so 14,000 are counted. **LEAVERS must fail** (`PlantFlows.test_plant_leavers_exclude_closures`).
- **V5 (open):** none, given the declaration.

### 14. ACCOMMODATION: `fit.res.labour_accommodation_share` (r2)

- **Declarations filled:** `fit.res.labour_accommodation_share.tolerance`. Not filled: `inputs.accommodation_by_occupation` (S4-T03 homes).
- **V1 (recommendation):** the worker-weighted share of workers with `labour_accommodation` in each occupation group 1 to 9 and `unmapped`, by the rule the declaration selects.
  - Rule B if drawn per worker.
  - Rule W if drawn per employer cluster, with weights equal to the cluster's workers of the group.
  - Rule A if allocated.
  - The target is `res.labour_accommodation_share.<group>`, from the manifest only (SYN-31; decision 0050 items 2 and 3).
  - **A count of clusters never replaces the count of workers.** Two clusters of 1 and 99 workers with one housed give a cluster share of 1/2, but a worker share of 1/100 or 99/100.
- **V2 (method):** Rules B, W and A, tested code. SYN-31 houses workers with their employer, so a cluster draw is plausible.
  - Under a cluster draw, Rule B on workers is the wrong law and fails correct worlds: with the 99-worker cluster housed it rejects at K = 1, while Rule W passes (`UnequalClusters.test_plant_worker_binomial_fails_a_correct_cluster_world`).
- **V3 (examples):**
  - Per worker: n = 200,000, target 65%, limits 129,134 to 130,864. **Passes:** 130,000.
  - Per cluster: 40 invented clusters of 1 to 40 workers (820 workers). **Passes:** 533 housed (65%).
- **V4 (planted violation):** `plant_accommodation_one_share_for_all_groups`: one share of 30% where the group's target is 65%. **ACCOMMODATION must fail.**
  - Per worker: 60,000 of 200,000 (`PlantResidence.test_plant_accommodation_one_share_for_all_groups`).
  - Per cluster: 231 of 820 (`UnequalClusters.test_rule_w_catches_one_share_for_all_groups`).
  - The plan-5 literal plant stays.
- **V5 (open):** none for the rule. The draw unit and the treatment of `unknown` rows await the S4-T03 homes declaration (open point 12). Anchored F3/F7 margins prevail, so a conflict is reported, never resolved by widening.

### 15. STALENESS: `fit.res.address_staleness` (r2)

- **Declarations filled:** `fit.res.address_staleness.tolerance`. Not filled: `inputs.moved_residents` (S4-T03 homes).
- **V1 (recommendation):** the share of movers who keep their previous cell, by the rule the declaration selects (B or A). The target is `res.address_staleness` (ASSUMED 8%; SYN-33), and n is the residents who moved. It is one national cell.
- **V2 (method):** Rule B or A, tested code.
- **V3 (examples):** n = 20,000, target 8%, limits 1,447 to 1,758. **Passes:** 1,600.
- **V4 (planted violation):** `plant_staleness_over_all_residents`: 8% of 200,000 residents (16,000) counted against 20,000 movers. **STALENESS must fail** (`PlantResidence.test_plant_staleness_over_all_residents`).
- **V5 (open):** none, given the declaration.

### 16. X1: `scorecard.cross_check.X1.tolerance` (r2; r3)

- **Declarations filled:** the threshold part of `scorecard.cross_check.X1.tolerance`. **The minimum number of zones stays open**, so X1 stays the gap `MISSING_TOLERANCE` until it closes. Not filled: `inputs.health_presence_pairs` (S4-T07, S4-T09, source tasks).
- **V1 (recommendation):**
  - **Threshold:** X1 passes if Spearman's ρ (average ranks, as already fixed in `scorecard.yaml`) is at least **0.60**. It is computed over the zones that hold a centre, using the summed latest annual patient visits against simulated annual mean presence (document 05 section 16).
    - The comparison is exact and inclusive. The test fixture has ρ = 3/5 exactly and passes (`PlantX1.test_threshold_is_inclusive_and_exact`).
  - **Minimum zones:** stays open.
  - X1 stays a cross-check, never a hold-out or a calibration.
- **V2 (method):**
  - **The threshold** is the pack's magnitude convention for the like check H2 (document 05 section 16): the rank correlation of an indirect zone-level activity proxy with simulated activity, at least 0.60. It is a magnitude convention and makes no claim about statistical significance.
  - **Why no fixed minimum is proposed (R5).** r1's minimum of 12 and its 0.023 came from a normal approximation that ties invalidate. The exact, tie-aware calculation (`exact_null_upper_tail`, which enumerates every arrangement with the observed ties and is checked against brute force in `test_exact_null_equals_brute_force`) gives the following:
    - **12-zone tied fixture:** each series has eleven equal low values and one high value. A structureless world reaches ρ ≥ 0.60 with probability exactly 1/12 ≈ 0.083, not 0.023 (`test_twelve_zone_tied_fixture`).
    - **The one-high family at n zones:** the probability is exactly 1/n (`test_one_high_family_needs_twenty_zones_for_five_percent`). Any fixed minimum below 20 therefore admits an input whose structureless world passes more than 5% of the time.
    - 20 is necessary for that family. It is not shown to be sufficient for every tie pattern, so no number is proposed.
  - **A conservative fixed minimum: the Cantelli bound (r3, S1; a candidate for the owner, not active).**
    - **(a) Method in one line.** Under the exact permutation null, for fixed nonconstant centred rank vectors of n zones, E[ρ] = 0 and Var(ρ) = 1/(n − 1) whatever the ties, so the one-sided Cantelli inequality gives P(ρ ≥ r) ≤ 1/(1 + (n − 1)r²); at r = 3/5 and a 5% level the smallest n with a bound of at most 5% is **54**, where the bound is **25/502 ≈ 0.0498** (`cantelli_null_bound`, `cantelli_first_n`).
    - **Checked in exact rational arithmetic.** At n = 53 the bound is 25/493 ≈ 0.0507, above 5% by 7/9,860. The bound falls as n grows, so every n ≥ 54 holds (`X1CantelliBound.test_first_n_at_three_fifths_and_five_percent_is_54`). The mean and variance are confirmed by listing every permutation of five tied and untied fixtures (`test_null_moments_hold_under_ties_by_brute_force`).
    - **It is never below the exact null tail** on the 19 tied and untied fixtures of the derivation (n from 3 to 54), at ten thresholds from 0.1 to 1 (`test_bound_is_never_below_the_exact_null_tail_on_the_fixtures`). At 0.60, for example, the twelve-zone tied fixture has exact 1/12 against a bound of 0.202; untied n = 9 has exact 2,509/51,840 ≈ 0.048 against 0.258.
    - **Planted wrong variance.** Using 1/n in place of 1/(n − 1) falls below the exact tail (one-high fixture at 12 zones and r = 1: 1/13 against 1/12), disagrees with the exact second moment, and would lower the candidate to 53. It fails (`test_plant_wrong_variance_one_over_n_fails`).
    - **(b) It is conservative.** Under the stated permutation null, the false-pass probability is at most the bound and can equal it; for some tie patterns the bound is conservative, so a smaller exact minimum may suffice. Untied ranks need only **9** zones exactly (8 give 1,159/20,160 ≈ 0.0575; 9 to 11 are at most 5% in `test_untied_ranks_need_nine_zones_exactly`, and 12 to 14 were checked the same way while drafting). Over all tie patterns, however, no minimum below **40** holds: one high zone on one side against two on the other gives exactly 2/n, and 2/39 > 5% (`test_one_high_against_two_high_needs_forty_zones`). No two-level pattern exceeds 5% from 40 to 54 (`test_worst_two_level_pattern`). The smallest minimum valid for every tie pattern therefore lies between 40 and 54. The exact value is not computed, because every multi-level tie pattern would have to be searched.
    - **(c) Coverage cost.** X1 compares the zones that hold a centre (document 05 section 16, Annual cross-check X1). The centres are those of `visits_phcc`, which document 04 records as 35 rows "by health centre and region". So X1 compares **at most 35 zones**; the exact number of zones holding a centre is **to record**, from the committed crosswalk. **54 is not reachable**, and neither is any universal minimum, since such a minimum is at least 40. With document 04's recorded 35-row coverage, adopting 54 would turn X1 from `MISSING_TOLERANCE` into `UNSUPPORTED_COVERAGE`; future source coverage requires a newly reviewed zone count and admission decision. At 35 zones the Cantelli bound at 0.60 is 25/331 ≈ 0.076.
    - **(d) The owner's choice** was open point 9. The owner accepted its default: 54 is not adopted, option C was not chosen, and X1 stays the gap `MISSING_TOLERANCE`.
    - The exactness above holds under the uniform permutation model; it does not establish geographic exchangeability of zones.
- **V3 (examples, r3, S2):** With the minimum otherwise satisfied, ρ = 0.60 passes a 0.60 threshold and fails a threshold of 0.60 + 10⁻⁹. While the minimum is open, X1 is a gap whatever ρ is.
- **V4 (planted violation):** `plant_x1_passing_while_its_minimum_is_open`: 11 zones, or 2 zones, with ρ = 1. **X1 must be the gap**, not a pass (`PlantX1.test_plant_x1_passing_while_its_minimum_is_open`). The current code accepts 2 or more zones.
- **V5 (stays open, the minimum).** Ways to close it:
  1. **A conditional exact guard (candidate, not proposed active).** Admit X1 only when the exact tie-aware probability that a structureless world reaches 0.60, computed on the observed tie pattern, is at most 5%.
     - The tool exists and is tested.
     - Its feasibility at the real zone count is not shown: the enumeration grows quickly when there are many zones and few ties.
     - It closes when S4-T07 and S4-T09 give the zone count and the lead shows the computation, with another maker's review.
  2. The owner sets a minimum as the owner's own judgement, knowing the one-high family above.
  3. Another reviewed method.
  4. **(r3)** The Cantelli candidate of 54 zones, or the size-dependent threshold derived from the same bound. Both are set out with their costs at open point 9.

  The owner may also judge 0.60 too strict for an indirect proxy (open point 9). Only the owner may lower it.

### 17. OTHER_CORRELATIONS: `fit.correlations.additional`

- **Declarations filled:** none. **Stays open.**
- **V1 (recommendation):** no additional pair is proposed. The declaration stays the named gap, so that SYN-90's "unavailable calibration is reported" holds.
- **V2 (reason):** a lawful pair needs a sourced target at its own grain, population and period (plan revision 2 page 2), and the pack holds none.
  - The shared basic and net ranks, and the employer effects, are construction assumptions, not empirical targets.
  - F15, H1, H2 and X1 stay separate.
- **V3 (examples):** not applicable.
- **V4 (planted violation):** `plant_construction_assumption_as_target`. A pair whose target is a construction assumption **must be refused** with `FIT_SPEC_MISSING`, and with no pair the gap remains (`PlantOtherCorrelations`).
- **V5 (what would close it):** the owner names a source that publishes a joint table or correlation at a lawful grain. Each pair then gets the plan's full enumeration and its own record.

## Plants common to every drawn-share rule (r2)

These come in addition to the one plant per value above. All are executable derivation plants (binding condition 7).

- `plant_per_family_k`: each family uses its own K in place of the fit-wide K.
  - Eight families of one cell each (n = 400, t = 30%): the fit-wide rule passes a count that the per-family rule fails.
  - Per-family K gives an exact independent false-fail chance above 5%; the fit-wide K keeps it at or below 5% (`CrossFamilyK.test_plant_per_family_k`).
- `plant_strict_boundary`: `≤` becomes `<`. Both boundary counts pass under the rule and fail under the plant (`CommonPlants.test_plant_strict_boundary`).
- `plant_tolerance_from_output`: a tolerance taken from the output is refused with `FIT_SPEC_MISSING` (`CommonPlants.test_plant_tolerance_from_output`).
- `plant_missing_method`: no mechanism, an unknown mechanism, or Rule B on units of unequal weight is `MISSING_METHOD`, and a missing declaration field is `MISSING_DECLARATIONS`. None is ever a pass (`Declarations`).
- `plant_binomial_for_finite_population`: binomial accepts a count that the exact hypergeometric law rejects (`FinitePopulation.test_plant_binomial_passes_a_count_the_exact_law_rejects`).

## Consequences

- With the owner's approval of 2026-11-19:
  - The S4-T12 roster binds each declaration named above to this record's `tolerance_ref`.
  - The producing tasks must make the family declarations of the declaration table; until they do, each family is a gap.
  - Document 05 section 9 gets the F19 and F21 rules, and section 16 gets X1's threshold, in this record's accepting change. X1 stays a gap until its minimum closes.
  - F19 and F21 get their numbers only after those are computed from the hashed public files and approved (SYN-60).
  - The S4-T12 fit check may run (the owner's note of 2026-11-19, relayed at 05:49). Every value that stays open is a named gap in it.
- The accepting change amends documents only. `custodian/mobility/scorecard.yaml` (SYN-60), the calibration manifest, the fit roster and any code or test under `custodian/` or `core/` are not changed by it: they belong to task S4-T12, with its own plan, build, review and evidence.
- The S4-T12 build turns the derivation plants into production guards with their own tests and review. Nothing here claims that any guard exists or passes.
- The values that stay open keep their gap rows, so S4-T12 acceptance stays incomplete until they close.
- The work stays beside the S2 critical path and does not block it.

## Open points for the owner (r2; r3) and the defaults accepted

The owner's plain yes of 2026-11-19 accepted the stated default of every point below, as the lead's question of 2026-11-19 01:53 listed them. Each point keeps its text and adds the default accepted. A point whose default is to stay open stays open as written.

1. **F19 years.** Which complete years of `visits_museum` form `mob.visitor_month_shape` and τ₁₉? 2022 is a World Cup year (document 05 Q3). τ is not robust in general to one unusual year (sensitivity fixture), so the lead's run shows τ with and without each candidate year.
   - **Default accepted:** that procedure. The lead's run over the hashed file shows τ₁₉ with and without each candidate year, and the owner picks the years; until then the years and τ₁₉ stay open (item 7, V5).
2. **Weather profile.** The years of history and the location for `weather.hourly_profile_by_season` are the owner's source choice. F21 does not depend on them.
   - **Default accepted:** the pack's source as registered.
3. **SPREAD allowance (r3, S3).** Zero extra allowance is in the request. Every declared final percentile must be within q/2 of L(p); other aspects of the distribution are not certified. A processing step (mean scaling, flooring, truncation or median repair) fails this check when the resulting declared percentile lies outside that interval, and the failure stops world acceptance (decision 0051 items 1 and 4).
   - A positive allowance, or excluding groups under 30 jobs, is the owner's alternative.
   - Each weakens the check by a stated amount: r1's envelope would add up to 50 at p90 at n = 101. An under-30 exclusion leaves small groups unchecked.
   - **Default accepted:** zero extra allowance, and every spread group of 1 job or more is tested (item 4). Neither alternative was chosen.
4. **Means.** The recommendation is 10% (the F11 convention). The stricter alternative is the published figure's own rounding plus the declared precision, under which almost any median repair fails.
   - **Default accepted:** 10% of the Public figure (item 5).
5. **Size.** Should Rule B replace 2 points if S4-T11 draws class membership directly from the Public table? Should only the employee measure count, not establishment counts?
   - **Default accepted:** 2 percentage points, in the Public table's own classes and measure (item 1); Rule B does not replace it.
6. **International visitors.** The share's denominator and mechanism await S4-T09 Part B, and the owner confirms the source.
   - **Default accepted:** it stays open until S4-T09 Part B declares the denominator and mechanism (item 11, V5).
7. **Committing derived numbers (not an owner question; lead's ruling L-1026).** A source's terms reading is a record, never a gate (decision 0059). Whether τ₁₉ and τ₂₁, derived from the museum and busyness data, stand in the repository follows decision 0034: where a source has no open licence, its values stay in the local review folder and the repository holds only the method and the hash.
8. **Rule B or a fixed band (new in r2).** The two acceptance sets cross (see the trade-off section).
   - (a) Rule B alone is recommended.
   - (b) Rule B and 2 points is stronger in some cells, but makes a correct world fail far more often (0.354 per cell at n = 400, t = 30%).
   - (c) 2 points alone passes a group that was never drawn.
   - **Default accepted:** (a), the exact rule B alone, with no fixed band; Rules H, W and A apply where a declaration selects them (items 2, 3 and 9 to 15).
9. **X1 (r3).** Is 0.60 appropriate for an indirect proxy? Lowering it is the owner's call only. The minimum number of zones stays open, and X1 stays `MISSING_TOLERANCE` until it closes. The options, from item 16, V2 and V5:
   - **(A) Adopt 54**, the first n at which the Cantelli bound is at most 5% (the bound is 25/502 there). Cost: with document 04's recorded 35-row coverage, option A yields `UNSUPPORTED_COVERAGE` and X1 does not inform the scorecard; future source coverage requires a newly reviewed zone count and admission decision. A universal exact minimum, between 40 and 54, has the same cost.
   - **(B) Keep X1 a gap** (the status quo). Cost: with document 04's recorded 35-row coverage, neither A nor B lets X1 inform the scorecard. The effect is that of (A), with a more honest label.
   - **(C) A size-dependent threshold from the same bound.** With n frozen from the committed crosswalk before the run, X1 passes only if ρ ≥ 0.60 and ρ² ≥ 19/(n − 1), so the Cantelli bound at the observed n is at most 5% (`cantelli_threshold_sq`). The threshold only rises above 0.60, never falls. Cost: at 35 zones the threshold is √(19/34) ≈ 0.75; at 30 zones about 0.81; below 20 zones it exceeds 1 and X1 cannot pass. It is conservative, so some worlds with real structure fail. It also changes the threshold of item 16a.
   - **(D) The conditional exact guard on the observed tie pattern** (item 16, V5 option 1). Cost: its computation at the real zone count is not shown; the current enumeration grows exponentially with untied zones.
   - The drafter's reading, not a choice: (A) and (B) give the same result on the pack's geography. Only (C) is shown computable at up to 35 zones. (D) would be the least conservative if it proves computable.
   - **Default accepted:** (B). The threshold stays 0.60, the minimum number of zones stays open, and X1 stays the named gap `MISSING_TOLERANCE`. Option (C) was not chosen.
10. **Fit-level false fail.** One family at 95% over every drawn-share test means a correct world fails at most about one time in twenty. The remedy for a fail is a model change or a new recorded seed under the owner's rule, never a widened tolerance and never choosing seeds until one passes.
    - **Default accepted:** 95 percent, one family over every drawn-share test of the fit.
11. **Conditional families.** Items 2, 3 and 9 to 15 hold only under the producing tasks' declarations (S4-T03 Part B and homes, S4-T09 Part B, S4-T11, S4-T13). Without one, the check is `MISSING_METHOD` or `MISSING_DECLARATIONS`, never a default pass.
    - **Default accepted:** a check with no declaration stays a named gap.
12. **Accommodation.** The draw unit (worker or employer cluster) and whether `unknown` rows are in the denominator await the S4-T03 homes declaration.
    - **Default accepted:** it stays open until the S4-T03 homes declaration.
13. **Decision 0031.** The minimum of 3 venues rests on decision 0031 item 6, which is still "Proposed … for the owner's confirmation". If the owner confirms another number, F21's minimum follows it.
    - **Default accepted:** the minimum follows decision 0031 item 6: 3 venues, or the number the confirmed record sets.

## Sources (r2; r3)

- **Pack, at the checked-out base `6fabe34ba5e12543c08ef97c1ae64b83e0a2cc4f`:**
  - Document 05: section 9 (F7 to F21), SYN-31 to SYN-35, SYN-60, SYN-86, SYN-87, SYN-89 to SYN-92, sections 3.1, 7.1, 12.8 and 16 (H1 to H3 and Annual cross-check X1), and Q3. The manifest rows cited are `wage.joiner_rate`, `wage.leaver_rate`, `res.labour_accommodation_share.*`, `res.employers_per_accommodation`, `res.address_staleness`, `res.wage_sorting`, `mob.visitor_month_shape`, `mob.hourly_shape_by_category`, `mob.hourly_shape_min_venues`, `mob.movement_age_bands`, `mob.split_anchor.population_age_sex`, `mob.split_anchor.visitor_arrivals` and `mob.split_nationality_from_simulated`.
  - Document 07: the Interval paragraph, MTH-12, MTH-13, card C26.
  - Document 12: TST-265.
  - Document 04: `est_size_act`, `sec_hr_size`, `comp_nat_act`, `wage_occ`, `wage_act`, `pop_muni_age_sex`, `visitors_markets`, `visits_museum`, `visits_phcc`, and the busyness source rows.
  - Decisions 0036 items 4 and 6, 0037, 0040 items 5 and 6, and 0046 item 2.
- **Decision records absent from the checked-out base, read with `git show` (N1):**
  - **Decision 0031**, item 6 (minimum venues 3). Read at commit `519d9b258d3690648bec6be65d835d2e7601320a`; the same text is on origin/main at `d66d742c3736168560278d717da257fdaa34aac5`. Status as read: "Proposed, 2026-11-16: the lead's record of the owner's decisions, for the owner's confirmation".
    - The checked-out base's documents 04, 05 and 07 still name the earlier busyness source. Which source feeds F21 follows the confirmed record.
  - **Decision 0050**, items 2 and 3. Read at commit `03b09151879ad531522b935b47e5c582aa84d57c`, an ancestor of origin/main. Status as read: Accepted.
  - **Decision 0051**, items 1 to 8. Read at commit `537aa6005254f2f9866649a437c1ad4e2accdb0e`, an ancestor of origin/main. Status as read: Accepted.
  - origin/main as read: `b380109f0cc29c9fb7d68d0987989cfed8daebbe` (2026-11-18). The lead records the authoritative status before integrating.
  - **At acceptance**, on main `1fdbd2a5ffb48c2063bd01247ba7da33a7d8b5a6` (2026-11-19): [decision 0031](0031-venue-busyness-from-a-provider-interface.md) is Proposed, and [decision 0050](0050-the-homes-of-the-generated-workers.md) and [decision 0051](0051-the-december-pay-reference.md) are Accepted.
- **Plan:** the S4-T12 plan revision 2, pages 1 to 3. **Rulings:** the lead's rulings L-1011 and, for the acceptance, L-1063 item 3. **Owner's approval:** the owner's note of 2026-11-19 relayed at 05:49, items 1 and 2, answering the lead's question of 2026-11-19 01:53. **Reviews:** REVIEW-0062-R1, and REVIEW-0062-R2 with its scratch derivation of the Cantelli bound (r3).
- **Code read for r1, never changed:**
  - `custodian/mobility/scorecard.yaml`, and `custodian/src/eii_custodian/mobility/visitors.py` and `hourly.py`, at the S4-T09 part A head `5bbed98`.
  - The S4-T03 head `7fe92e4` and the S4-T13 head `d718c29`.
- **Derivations:** [`docs/decisions/0062/derive_tolerances.py`](0062/derive_tolerances.py) and [`test_derive_tolerances.py`](0062/test_derive_tolerances.py). Standard library only, invented inputs only, exact arithmetic for every decision. The printed output and the r3 test run are the lead's evidence and are not committed. r3: 93 tests, exit 0, on Python 3.14.4 with no random seed.
  - At acceptance the two files are committed with lint and format changes only, so that the repository's `ruff check` and `ruff format --check` pass: `functools.cache` for `lru_cache(maxsize=None)`, `itertools.pairwise` for two successive-pair `zip` calls, `strict=False` on the other `zip` calls, `ClassVar` annotations on five test fixtures, the formatter's layout and the run command in the test docstring. No function changed its result: the module's printed output equals the r3 output byte for byte.
  - Run from the repository root: `uv run --locked python -m unittest discover -s docs/decisions/0062 -p 'test_*.py' -v` (93 tests, exit 0, on Python 3.14.6).
- **Not read:** no owner calibration table, custodian record, public-cache file, `.env` or private folder. Every value that would need one stays open.
