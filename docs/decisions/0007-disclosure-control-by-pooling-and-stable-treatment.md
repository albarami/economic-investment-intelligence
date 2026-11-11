# 0007 — Disclosure control by pooling and stable treatment

| | |
|---|---|
| Status | Accepted, 2026-11-11 |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Record why protected statistics are released as a partition of pooled units with a treatment applied once, and what is not claimed for it. |
| Read first | [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](../06_PRIVACY_AND_DISCLOSURE_CONTROL.md), [0006](0006-fixed-grid-and-pin-based-areas.md) |

## Context

- Wage statistics for small areas can disclose a person or an employer in three ways: directly, through a small count; by dominance, when one employer is most of a unit; and by subtraction of two answers.
- Hiding failing cells is not enough. A hidden cell can be recomputed from totals unless more cells are hidden, and every total then comes out low by an unknown amount.
- Three designs proposed three engines. Whatever is chosen, the thresholds are proposals: data owners set the real ones (open item OI-11).

## Decision

1. The protected units are the person and the employer group (establishments rolled up to legal entity and to a hidden group).
2. Partition. Roots are the non-empty intersections of resolution-7 parents with municipalities. A whole-cell release unit is one base grid cell or a union of whole base cells inside one root. The only cross-root unions are a remainder made from failed roots of one municipality and the terminal `ha_home` unit made from every residence whole-cell unit and remainder of one municipality (PRV-13). A finer level is published only where every sibling cell passes (all-or-nothing). Each contributor universe has one parent-linked nested (laminar) partition family: a coarser partition is made only by merging units of the finer one, and two independent merges never cross. Whatever still fails joins a municipality remainder, published only if it passes. Pool, do not hide: nothing is hidden yet derivable.
3. Released primitives are additive only: earner count, band counts and wage bill. Additivity holds inside one additive family: one release table, one partition, one measure where the table has measures, and one breakdown. Every stored total is the exact sum of the treated leaves of its own family. Different families are not required to be equal; PRV-71 bounds their treatment differences. Every protected figure normally names one home family, a count and its adjacent non-ratio shares use the same family, and no output puts two routes to one population side by side (PRV-29, PRV-30). The only exception is the closed ratio-statistic list: mean wage and the coverage, irregular and deployed-elsewhere shares take numerator and denominator columns from the same stored rows and name both additive families in their lineage. Median bands, quartile bands and other shares are derived from one family's treated primitives. There are no minima and no maxima, and the top band is open.
4. Two parameter sets are always evaluated inside the custodian plane, A and the stricter B, so the cost of each is visible. Set A: counts need 10 covered earners and 5 unrelated employer groups; money and the median band need 30 earners; quartile bands need 100; the largest employer group holds at most 40% of earners or of the wage bill and the top two at most 75%; the largest single wage is at most 15% of a unit's wage bill; counts are rounded to 5 and money to QAR 100. The full table for both sets is in document 06. Exactly one selected parameter set's protected tables are exported as one release folder (PRV-05).
5. Treatment is applied once, at build time, and stored, so identical questions return identical answers. `window_key` is the SHA-256 of canonical JSON holding the protected `period` and, in name order, `{name, sha256}` for `business_register.v1`, `employment.v1`, `residence.v1` and `wages.v1`, using each feed's manifest `feed_sha256`; nothing else enters it. Continuous integration checks the register alone and permits one `protected_sha256` per `window_key` and one `window_key` per `world_seed`. A uniqueness conflict refuses freeze; after a freeze, any change of rules version, exported set, treatment code or world generator requires a new `world_seed` and a new build before another freeze. `./eii freeze` runs twice with no new flag: the first run appends the register line and writes pending `freeze.json`; after normal merge, the second run from the containing base-branch commit builds and verifies the application archive, writes its checksum and marks the descriptor complete. For a frozen release only, the register shipped inside the installed application is the allow-list: install or start refuses with exit 7 if that register lacks the matching line or `freeze.json` is incomplete, and the remedy is to finish the freeze rather than change the seed. No signed export-register receipt substitutes for that line (PRV-120).
6. Closure is proved in each build by exhaustive within-family structural checks for candidate A, candidate B and again for the selected export. At least 10,000 seeded fuzz pairs run for each candidate and are repeated for the selected export. The attacker-view audit has one acceptance model: every published protected leaf is fixed month by month to its untreated aggregate, declared attacker knowledge is checked against sealed truth before use, and the published-means-passed, survival and configured public-total constraints apply (PRV-112 to PRV-116). Indistinguishable targets form one target class; the audit report records person and employer-group target-class counts, solve counts, outward-rounded interval widths, elapsed time and pass or fail. A measured time budget set at the start of slice S5 is not relaxed. The failed-population implications of a merged band, a category pooled into `other`, merged siblings, a withheld remainder and a reason code are outside that model; PRV-76 requires at least one typed attack for each signal. The audit is evidence under its stated attacker, not a proof of non-disclosure. With controls off the attack suite must recover every typed release predicate; with controls on it must recover none, under both sets. Version 1 exports one protected window; cross-period attacks, including the mover case, are deferred to backlog item L4.
7. Not claimed: differential privacy, security certification, or real suppression rates.

## Evidence

- Engineering judge (2026-11-11): the all-or-nothing split is the simplest rule of the three designs that is safe against subtraction across the hierarchy. A whole-cell release unit is one base grid cell or a union of whole base cells inside one root; PRV-13 defines the municipality remainder and terminal `ha_home` exceptions. Hiding cells and auditing the bounds "is harder to build and to prove than a partition of safe units", and hidden cells that contribute nothing make every total low by an unknown amount.
- The same judge's inference, narrowed by the additive-family rule (PRV-29): each contributor universe needs one nested partition family so cross-tier geography cannot isolate an unpublished sliver. Numeric equality is required only within one additive family; the consistency audit bounds differences across families.
- Published practice, collected by the project research (pages retrieved 2026-11-11). The Australian statistics office's confidentiality guide describes subtraction between tables, a minimum-contributor rule and a dominance rule, with the example that the top two units may not contribute more than 75% of a cell's value. The United Kingdom statistics office's census method gives each record a fixed key, so that the same perturbation is applied to every instance of a cell and a repeated request gets the same answer. That is the idea behind decision 5.
- Limit, same research: Asghar and Kaafar (2020) defeated bounded-noise protection in a statistical office's online table builder by writing different queries that evaluate to the same answer. Thresholds with consistent treatment are established practice and carry no formal guarantee. The fixed catalogue of units and tables is the mitigation.
- The orders of magnitude follow thresholds that statistical offices publish. The numbers themselves are this project's proposals and are not measured on real data.

## Consequences

- Answers are coarser where data is thin. The survival report shows what was published, pooled or withheld under each set.
- Subtraction within one additive family yields sums of that family's published leaves. Cross-family differences are not required to be zero and are bounded by the consistency audit; cross-universe and configured public-total residuals are handled by the attacker-view audit.
- A change of thresholds is a new release with a new rules version, never a run-time setting.
- Every blank has a reason ("Why can't I see this?"), and Suppressed is a first-class mark.
- Every answer carries a privacy receipt.

## What would change this decision

- Data owners setting other thresholds. This is expected (OI-11); it changes parameters, not the design.
- A requirement for a formal privacy guarantee: a different method and a new record.
- An attack, from the suite or from an independent reviewer, that recovers a canary with controls on. The build fails and the design is revised before any release.
- A survival report that shows unacceptable loss: pooling of failing siblings is added before resolution is changed (engineering judge).

## Open questions and assumptions

- OI-11: privacy thresholds are proposals; data owners set the real ones.
- This record makes no ASSUMPTION.

## Sources

- EII engineering-and-delivery-risk judgement and AI-patterns research, 2026-11-11 (project records held by the owner).
- Australian Bureau of Statistics, Data Confidentiality Guide, page on treating aggregate data, https://www.abs.gov.au/about/data-services/data-confidentiality-guide/treating-aggregate-data ; retrieved by the research on 2026-11-11.
- Office for National Statistics, methodology page on protecting personal data in Census 2021 results, https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates/methodologies/protectingpersonaldataincensus2021results ; retrieved by the research on 2026-11-11.
- Asghar and Kaafar, Proceedings on Privacy Enhancing Technologies, 2020, https://www.petsymposium.org/popets/2020/popets-2020-0031.php ; retrieved by the research on 2026-11-11.
