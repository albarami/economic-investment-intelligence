# Decision 0064: The 58 rows of the narrowing table, decided

| | |
|---|---|
| Status | Accepted, decided by the owner on 2026-11-19 (relayed 00:59); recorded by the lead |
| Date | 2026-11-19 |
| Owner | The owner |
| Decided by | The owner's note of 2026-11-19, relayed by the owner's advisor at 00:59, agreeing to the advisor's recommendation for each of rows 1 to 21 of the narrowing table, with rows 22 to 58 proceeding as suggested; recorded by the lead's ruling L-1029, under AGENTS.md rule 46; read with the owner's note relayed at 00:35 and the lead's ruling L-1026 (no terms, licence or permission question is put to the owner; [decision 0059](0059-publisher-terms-are-a-record-not-a-gate.md)) |
| Amends | TASKS.md: the queue rules (item 45); the acceptance criteria of S2-T04, S2-T06, S2-T08, S2-T10, S2-T14, S2-T16, S2-T19, S2-T20, S2-T24 to S2-T29, S3-T03, S3-T09, S3-T16, S4-T02, S4-T05, S4-T08, S4-T13, S5-T09, S6-T04, S6-T10, S6-T14, S6-T15, S6-T17 and S6-T19, by amendment lines, each citing its item; new tasks S2-T35 to S2-T39, S3-T23 and S7-T25 to S7-T27. OPEN_ITEMS.md: OI-130 and OI-136 to OI-139 closed; OI-27, OI-96, OI-123, OI-144, OI-170, OI-171, OI-214 and OI-257 updated; OI-304 to OI-313 opened. AI-129 and the open questions of document 09; section 12 and the open questions of document 04; the traffic-provider open questions of documents 02 and 13; the open points on the Qatarization planner and the recovery tracker in documents 01, 09 and 10 and the glossary; the slice lists and an open question of document 14; the decision index of docs/README.md. [Decision 0016](0016-version-1-covers-the-whole-initiative.md) item 21 (a cross-country entry comparison stays out) and [decision 0019](0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 21 (the places copy dated 2025-01-10) are amended in those points only, by items 21 and 14 |
| Purpose | Record the owner's decision on every row of the narrowing table: what is kept, restored, changed, reopened or not yet decided, and the task or open item that carries each. |
| Read first | [Decision 0059](0059-publisher-terms-are-a-record-not-a-gate.md); [decision 0055](0055-mutation-testing-moves-to-after-go-live.md); [decision 0026](0026-public-sources-used-in-full-locally.md); AGENTS.md rules 3, 4, 8, 10, 12, 24, 25 and 27 |

## Context

The lead's narrowing table of 2026-11-19 (L-1017 part A, reviewed at 00:35, outside the pack) lists in 58 rows what the
build has narrowed since the plan was written, what each costs, where it came from, whether the owner approved it, and
the lead's suggestion. The owner's note relayed at 00:35 and ruling L-1026 rewrote the table so that every row is a
value or spend choice: no row asks the owner a terms, licence or permission question, reading a source's terms is kept
as a record and never a gate (decision 0059), and a KEEP that a hard rule holds names the rule.

The advisor's message of 00:49 gave a recommendation for each of rows 1 to 21 and asked the owner to answer by row
number. The owner answered at 00:59 that they agreed with the recommendation for every row and asked that work continue on
every free seat and tool. The advisor applied the recommendations, with the subscription rule of
00:55 for rows 2 and 6 (a paid plan goes on the subscriptions file for the owner), and rows 22 to 58 proceed as the
table suggests. Ruling L-1029 records this and asks the lead to apply each row to TASKS.md and OPEN_ITEMS.md through
the normal task flow.

## Decision

Each item names its row, the decision, its effect and what carries it. KEEP changes nothing. A task named here carries
the item through an amendment line or a new task in TASKS.md, citing "decision 0064 item N"; an open item named here
holds what is still to confirm. The row numbers are the table's.

1. **Row 1, KEEP.** The two investment sources (the FDI projects dashboard and the agency's site) stay on in the
   registry, the nightly fetch and their release tables, as the owner's words of 2026-11-12 and decision 0026 left them.
   Their remaining gaps are item 32. No task: kept.
2. **Row 2, RESTORE.** The optional live traffic layer (live flow tiles and traffic-aware drive-time areas) may be shown
   in showings to others under the provider's paid plan, a spend choice the lead lists for the owner on the
   subscriptions file; until the owner takes that plan, the free plan serves the owner's own evaluation. The plan's
   name and price are to confirm (OI-304). Rules 4 and 27 hold unchanged: the provider is off by default, stores
   nothing of a response, shows its attribution, and is never needed by a test, a gate, a command or the guided story;
   simulated traffic stays the default of every showing. Carried by S6-T19; closes OI-130.
3. **Row 3, KEEP.** The agency's page text is shown in full, unchanged, as a quotation with the date read; no
   model-written summary or translation of it is shown (rule 21). No task: kept.
4. **Row 4, CHANGE.** Values of sources without an open licence stay out of the repository (decision 0026 item 5;
   [decision 0034](0034-licence-questions-of-public-sources-are-answered-at-a-go-live.md)), and the expected values
   that are therefore not pinned by a committed test (the numeric findings of PUB-71 among them) are pinned in the
   lead's local real-cache test, the custodian data tests that only the lead's shell runs (rule 44), reading the
   uncommitted cache. The depth of checking is kept and nothing is committed. Carried by S2-T35.
5. **Row 5, RESTORE.** The financial centre's public company register gets a registry row and is read through the
   normal seam of `./eii build-public`, its terms reading kept as a record (decision 0059). Its company names enter the
   complete inventory of real names that S2-T15 built and the collision check of S4-T05 calls (S4-T05's seam), so
   that the world build's collision check sees that register's companies. No price. Carried by S2-T36 and S4-T05.
6. **Row 6, RESTORE (offline imagery).** Satellite imagery without a network is restored under an imagery-provider plan
   that includes offline tiles, a spend choice the lead lists for the owner on the subscriptions file; its name and
   price are to confirm (OI-305). It is off by default; the open map stays the default and the mode of the guided story;
   it is never needed by a test, a gate, a command or the guided story (rules 4 and 27). Address-search results stay
   unstored: that half of row 6 is kept. Until the owner holds the plan, OPS-73, TST-248 and every other statement that
   no tile is stored stand unchanged; where offline tiles may then be kept, and how those statements change for them,
   is fixed by the carrying task's own reviewed change with planted checks, and no tile ever enters the repository.
   Carried by S3-T23.
7. **Row 7, CHANGE to the spend meter.** The photorealistic 3D mode takes the spend meter of L-1017 part B in place of
   the per-view budget: no per-view budget (the 600-tile view limit of S3-T16 and TST-255 is withdrawn), no lowered
   detail, a running total in billable requests and in USD, and a warning at 80 percent of the ceiling until one showing
   is measured. The micro-pass then measures a full showing of Doha and of all Qatar, and the owner names the ceiling
   (OI-306). Until then the owner's ceiling of USD 20 in total holds with its project-wide hard stop (3,333 billable
   requests at USD 6.00 per 1,000, lowered if the price read is higher). Carried by S3-T16.
8. **Row 8, RESTORE inside the free credits already decided.** The lead makes the capped keyed run of the relative
   busyness reader from the lead's own shell, within the free credits the owner has already decided, then refreshes it by a
   scheduled keyed run from the lead's own shell. The source stays out of the nightly live fetch (decision 0026), its
   values stay in the uncommitted cache, and each value is shown as relative busyness, never as a count of people
   (rules 4 and 24). The cap's number and every account detail stay out of the repository. Carried by S2-T16.
9. **Row 9, NOT YET.** The tolerance values of S4-T12 stay open. The owner approves decision 0062 once, after its
   redraft has passed its review; no tolerance is fixed, tuned or run before then (rule 12). S4-T12 is unchanged; the
   wait is held by OI-307.
10. **Row 10, KEEP the deferral.** Mutation campaigns stay deferred until after go live under decision 0055, the owner's
    ruling of 2026-11-18 14:10; no background campaign is added. The table's suggestion of one background campaign is
    not taken. No task: kept.
11. **Row 11, RESTORE as L-975 (b) requires.** Every file that the per-file ceiling of 300 MiB refuses and that feeds a
    figure or a card gets a named per-source ceiling or a bounded read in the next pass of S2-T08 part B; among them
    the WSF 3D height file (2,142,396,344 bytes, the last fallback for building heights) and the two import exports
    (`cus_imp_2019` among them). The ceiling stays for every other file, and no value is lost (L-975). Whether the list
    of refused files is made is to confirm (OI-308). Carried by S2-T08.
12. **Row 12, RESTORE: yes to N2 to N7.** The owner's yes to the question groups N2 to N7 of the decision question bank
    is given (N1 stays retired by [decision 0046](0046-drop-hiring-flows-and-fetch-every-public-source.md)). S6-T04
    builds their playbooks. Each answers only from a registered Public source or the user's own input; a question
    without one stays a gap with its reason (AI-129); no synthetic data stands in (rule 3; decision 0023 item 12); a rent
    stays the user's own input, and a price is never relabelled as a rent. Carried by S6-T04; closes OI-136 to OI-139.
13. **Row 13, RESTORE: confirmed.** The owner confirms the gender draw of S4-T13 under decision 0037: gender is drawn only
    from the owner's gender mix by occupation group and activity, is null with release coverage "not drawn" without that
    table, and is never shown for a person (rule 10). Carried by S4-T13.
14. **Row 14, CHANGE.** The owner's choice for the places copy `places_fsq` is the newest dated release at each refresh,
    on the S2-T15 path (the public copy read without an account), with the release date recorded in the registry and
    shown beside the places; earlier snapshots are kept (S2-T27). This amends decision 0019 item 21's fixed release
    dated 2025-01-10 from the first refresh on. Carried by S2-T37.
15. **Row 15, RESTORE.** The `Employed` indicator of the municipal population source is loaded: the count of employed
    people by municipality, a Public fact on the source's own geography with its source and year, never joined to a
    synthetic record, used to segment one, apportioned to a drawn area or combined with a protected figure (rule 10).
    Under L-998 no exposure caution narrows it. How slice S5's attack model counts the published figure stays a point of
    its privacy design, where no rule is relaxed for it. Carried by S2-T38; OI-170 updated.
16. **Row 16, KEEP.** The three utility-account fields of the address points are not taken: no figure, layer or question
    needs them, and the numbers identify households. No task: kept.
17. **Row 17, KEEP.** Firm networks and the oversight screen stay out of version 1: rules 8 and 24 forbid looking up firms
    and owners, and paths may have no firm edges (ARC-85; decisions 0016 and 0023). No task: kept.
18. **Row 18, KEEP.** The advanced-method spikes stay deferred, the two privacy-method spikes S5-T12 and S5-T13 among
    them: the release keeps its tested privacy rules, and rule 12 forbids tuning privacy to show finer areas. No task:
    kept.
19. **Row 19, KEEP.** The owner's other scope choices stand: no catchment beyond 30 minutes, no presenter's sheet, no
    on-screen origin labels ([decision 0035](0035-what-the-audience-sees-names-no-data-origin-and-the-backend-marks-it.md)),
    and the live assistant and the second-model fallback at go live (OI-01, OI-30; S8-T05, S8-T14). No task: kept.
20. **Row 20, KEEP.** Hiring and leaving flows stay retired (decision 0046); the shared spells stay, so cards C39, C42 to
    C44 and C46 still answer. No task: kept.
21. **Row 21, REOPEN as a later card.** The cross-country comparison of starting a business returns to the plan as a later
    card, built once the benchmark sources of item 22 are read (S2-T26). This amends the point of decision 0016 item 21
    that kept a cross-country entry comparison out. Carried by S7-T25; OI-27 updated.
22. **Row 22, RESTORE.** The lead confirms the URL and the byte bound of each registry row not read by the live build
    from the publisher's metadata, and no bound is invented. Then S2-T24 reads BACI, S2-T25 Gravity and the Atlas of
    complexity, S2-T26 Comtrade, World Development Indicators, UNCTAD FDI, IMF WEO and ILOSTAT, and S2-T28 the accident
    table (activated through S2-T29's amendment of 2026-11-16). The other six rows and the live build record are to
    confirm (OI-309). Carried by S2-T24, S2-T25, S2-T26 and S2-T28.
23. **Row 23, RESTORE.** The Earthdata key now exists: the lead runs the keyed fetch of the monthly night-time radiance
    from the lead's own shell and registers each month after November 2026 as it is published. No test, gate or command
    needs the key (OI-103 is unchanged). Carried by S2-T14.
24. **Row 24, RESTORE.** Each of the 13 citation-only rows (twelve reference pages and the national GIS locator) is kept
    as a dated, hashed snapshot (S2-T27; rule 5), each host added by a reviewed registry change; the GIS locator serves
    address search (S3-T03). How the locator is reached within OPS-65 and ARC-35, which let only `./eii build-public`
    contact a public source host, is to confirm (OI-311). Carried by S2-T27 and S3-T03.
25. **Row 25, RESTORE.** Building heights regain the hand list of landmark heights, GlobalBuildingAtlas measured against
    the recorded heights (its terms read as a record), and a heights step that cannot be skipped (S2-T20), and the
    fallback panel (S3-T16). Where GlobalBuildingAtlas stands in the height order of decision 0023 item A2 is recorded
    from its measured error for the owner (OI-310). Carried by S2-T20 and S3-T16.
26. **Row 26, RESTORE.** The 40 waiting registry rows are confirmed and `pub_pop_agesex_grid` is loaded. Carried by
    S2-T14.
27. **Row 27, RESTORE.** The live run of S2-T06 part B is finished: the real places of the flagship story. Carried by
    S2-T06.
28. **Row 28, RESTORE.** A source that refuses automated reading is tried by the browser-capture route of S2-T29 before
    any dated skip stands; where a login is required, the account is a set-up or spend choice the lead lists for the
    owner. Carried by S2-T29.
29. **Row 29, RESTORE.** The ten open-data families get their tables. Carried by S2-T19.
30. **Row 30, RESTORE.** A free choice of imagery dates over the GIS centre's imagery-history layer replaces the three
    fixed before-and-after views. How the dates are served within OPS-65 and ARC-35 is to confirm (OI-311). Carried by
    S2-T19 and S3-T16.
31. **Row 31, RESTORE.** The showing features cut or deferred return in their S3 and S6 tasks: four playback behaviours,
    pages PAGE-2 and PAGE-6, the satellite opening shot, the what-changed card, and hot and cold spots. Hot and cold spots
    are already committed to S7-T23 by decision 0038 (R8) and stay there unchanged; the task IDs of the others are to
    confirm (OI-312).
32. **Row 32, RESTORE.** The agency's Arabic pages are read, the full-page column is added once decision 0029 settles
    it, and the FDI project-to-area crosswalk is filled by lead review, with no name matching (OI-178, OI-181, OI-182).
    Carried by S2-T39.
33. **Row 33, RESTORE.** The company register snapshot regains the financial-centre companies and the rows without a
    registration number, and its activity code, establishment nationality, statuses and licence dates, with the
    activity-code check proved (OI-186, OI-187, OI-190, OI-192, OI-193). Carried by S2-T04 part B and S4-T02.
34. **Row 34, RESTORE.** Card C6 regains its count, flag and neighbour quotients. Carried by S6-T10.
35. **Row 35, RESTORE.** Closures come from the cancellations table. The three bed-linen trade lines enter the import
    baskets only if the basket allows them and OI-171's condition holds (the nomenclature cited as a source); whether
    the basket limit of eight lines (MTH-33) is the cause is to confirm (OI-171). Carried by S6-T15.
36. **Row 36, RESTORE.** The events calendars of S2-T29 feed the event model and its trips: only dated events from those
    snapshots, with no complete-events claim. Carried by S4-T08.
37. **Row 37, RESTORE.** Generated flows are converted to vehicle trips, and the congestion plausibility check of the
    slice S4 gate then runs. Carried by S4-T08.
38. **Row 38, RESTORE.** Card C30 forecasts every listed series for which a Public series exists, the monthly
    establishments-by-area series among them where one exists, always with its backtest interval and measured error
    (rule 25). Carried by S6-T14.
39. **Row 39, RESTORE.** The base-rate card is restored in S6-T15 part B: entry and closure base rates in full, in both
    languages, with the screen, claims beyond the municipality where the source's own geography gives them, Arabic
    templates with no English inside, and the three caveats registered. Survival stays `NO_DATA` until a Public source
    is recorded (OI-97). Carried by S6-T15.
40. **Row 40, RESTORE to exactly what rules 8 and 25 permit.** The assistant regains claims in the first catalogues,
    register-company ranks as the output of tested code over criteria the user can see and change, estimates beyond
    areas where rule 25 permits them, and inferred items that can carry "still to test", with no wider permission
    (OI-237, OI-238, OI-239, OI-247). Carried by S3-T09 part B.
41. **Row 41, RESTORE.** Every award report link is checked in the background, not only the sample of 30, and spaces
    are normalised before names are matched (OI-277). Carried by S2-T29.
42. **Row 42, RESTORE.** The interface fonts, local icons and aligned figures in tables are delivered (OI-43, OI-89).
    Carried by S3-T09, which builds the Fact chip and the core answer interface.
43. **Row 43, RESTORE.** Each narrowed check of numbers and provenance is restored in its own task before its slice gate:
    PO-S2-36 (later Parquet column orders), PO-S2-44 (the break pass), PO-S2-48 (the C8 replay) and PO-S2-59 (the
    purity guard) by a fix in S2-T10; the independent class check (FE-42) and the numeral lexicons in S3-T09. The task
    of the period and bound checks on 14 rows is to confirm (OI-312).
44. **Row 44, RESTORE.** The recovery tracker and the Qatarization planner get their tasks: S7-T26 builds the planner in
    journey D5 under decision 0023 items 1 and 15; S7-T27 first writes the recovery tracker's passage from the owner's
    description, through a decision record if it adds scope (rule 46), then builds it. OI-144 stays open for that
    description.
45. **Row 45, RESTORE.** A plan item left as an open item in place of the thing it owes closes in its own task before
    that task's gate; any new narrowing of that kind goes to the owner first (L-996 b). The table names: the unproven
    criteria of S2-T01, S2-T04, S3-T16 and S4-T14 to S4-T16; the work merged with open items in S3-T03 and S3-T12; the
    cut scopes of the routes of S3-T08 and the as-of reading of S2-T27; the lineage identifier; the zone columns; the
    full employment feed (S4-T02); the four placeholder commands (OI-84); and the F5 calibration values, which are to
    confirm (OI-313). Recorded as a queue rule of TASKS.md.
46. **Row 46, CHANGE.** The private-school directory is read by the retry route of S2-T29, and its school-level count
    fields are taken as published; the director, telephone and e-mail fields are kept out as personal data. No capacity
    is estimated (decision 0023 item 12). Carried by S2-T29.
47. **Row 47, CHANGE.** The building cap of the shadows is set from the frame rate measured on the owner's showing
    machine, so that a full showing draws every shadow in view; the scaling stays only for weaker devices
    ([decision 0048](0048-the-shadow-clock-serves-every-area.md)). Carried by S3-T16.
48. **Row 48, CHANGE.** The map is drawn at the full pixel ratio on the owner's showing screen when the measured frame
    rate allows it (OI-121). Carried by S3-T16.
49. **Row 49, CHANGE.** The site estimate is shown as low, middle and high with its main drivers (rule 25), with cited
    Public defaults the user can edit where a source exists, and never attached to a named building (rule 24); where
    no source exists, the input stays the user's own. Carried by S6-T17.
50. **Row 50, CHANGE.** Sector pay gains the area figure from released synthetic wage tables under document 06 beside the
    national Public mean, its origin carried as decision 0035 requires. This is the owner's yes to R7 of
    [decision 0038](0038-advanced-methods-are-measured-spikes.md) (OI-214). No area-sector dimension is released until
    document 06's rules pass it in the custodian plane. The carrying task is to confirm (OI-312).
51. **Row 51, CHANGE.** The snapshot archive gets a copy on a drive the owner holds, with no network integration; this
    answers S2-T27's open question on where the archive persists. Carried by S2-T27.
52. **Row 52, CHANGE.** The first audience showing, not the build, waits until one bilingual usability session has run.
    No build task: the hold is recorded on OI-257.
53. **Row 53, CHANGE.** Fractional speeds are kept once the method rule is confirmed (OI-120, OI-123). Until then the whole
    speed of [decision 0021](0021-one-speed-for-a-link-and-an-hour.md) stands; the change takes a new method version
    (MTH-04, MTH-89), and no release control of document 06 changes. Carried by S5-T09.
54. **Row 54, KEEP.** Generated employment covers the private sector only: rule 3 limits synthetic records to the
    confirmed private-sector sources. No task: kept.
55. **Row 55, KEEP.** Generated flows carry no trip purpose: rule 3 limits movement to area, hour and origin-destination.
    No task: kept.
56. **Row 56, KEEP.** Grid cells with poor-quality flags stay out: they would show false radiance. No task: kept.
57. **Row 57, KEEP.** The flagship location check requires the whole building footprint: a partial footprint could credit
    a neighbour's places to a named building (rule 24; OI-233). No task: kept.
58. **Row 58, KEEP.** The imagery provider's places service is not used: its results cannot be stored, so they could never
    carry the complete source chain of rule 19; open places do. No task: kept.

## Passages amended

- TASKS.md: one queue rule (item 45); amendment lines, each citing its item, in the tasks named in the header; new tasks
  S2-T35 to S2-T39, S3-T23 and S7-T25 to S7-T27, each with status queued. No criterion is ticked and no status that
  records a merge is changed.
- OPEN_ITEMS.md: OI-130 closed by item 2; OI-136, OI-137, OI-138 and OI-139 closed by item 12; updates on OI-27 (item
  21), OI-96 (item 14), OI-123 (item 53), OI-144 (item 44), OI-170 (item 15), OI-171 (item 35), OI-214 (item 50) and
  OI-257 (item 52); OI-304 to OI-313 opened for what is to confirm.
- Document 09: AI-129's sentence on the remaining gaps, and its open question on the gaps of the question bank (item 12).
- Document 04: in section 12, the rows of school capacity, an events calendar and supplier certifications; the source
  rows of `events_qncc`, `schools_private_directory` and `traffic_tomtom_flow`; the list of open items touching the
  document; and the open question that named OI-130 (items 2, 12, 28, 36 and 46).
- Documents 02 and 13: the open question on showing the live traffic layer outside internal evaluation (item 2).
- Documents 01, 09 and 10 and the glossary: the open points on the Qatarization planner and the recovery tracker now
  name their tasks (item 44).
- Document 14: the new tasks in the slice lists of S2, S3 and S7, and the open question on the gaps of the question
  bank (item 12).
- docs/README.md: this record's line in the decision index.

## Passages the carrying tasks amend in their own change

The requirement texts below state what an item changes and are amended by the task that builds the change, in its own
reviewed change, as decision 0059 left its code to S2-T08 part B:

- Item 7 (S3-T16): the one-view limit of 600 tiles in TST-255 and in the rows of document 12 on the photorealistic 3D
  mode and its provider; the view budget in BE-139, in document 08's `photoreal_tiles/` row and route, and in OPS-74
  and the spend row of document 13; the meter, the warning at 80 percent and the unchanged hard stop take their place.
- Item 6 (S3-T23): OPS-73, TST-248, OPS-41 and the freeze bundle list of document 13, for offline tiles only, once the
  owner holds the plan.
- Item 14 (S2-T37): every statement of the fixed release dated 2025-01-10: in document 04, the `places_fsq` rows of
  sections 2.1 and 2.2 and of section 4, PUB-102 in section 8, and its note under "Open questions and assumptions";
  the OI-96 settled point of document 01; ARC-136 of document 02; DAT-157 and the `pub_place_fsq` contract note of
  document 03; the `places_fsq` method note of document 07; the `places_fsq` backend note of document 08; the OI-96
  point of document 09; OPS-72 of document 13; the section 10 (slice S2) paragraph and the OI-96 point of document 14;
  the sources answer of document 16; and the `places_fsq` entries of the Sources lists of documents 01, 03 and 07.
  Decision 0019 item 21 and decision 0040's held-tables row stay as accepted
  records, read with item 14.
- Item 15 (S2-T38): the contract of `pub_population_municipality` in document 03.

## What does not change

Every hard rule, privacy invariant, check, gate, review and hosted check stays as it is; no running job is stopped
(the owner's note, point 4). Decisions 0016, 0019, 0021, 0026, 0034, 0035, 0037, 0038, 0048, 0055 and 0059 are not
rewritten; items 14 and 21 amend one point each of decisions 0019 and 0016, and items 50 and 53 act through the open
items those decisions name. No terms, licence or permission question is put to the owner (decision 0059; L-1026). The
hard stop of the photorealistic 3D mode stays at the owner's ceiling. No synthetic data stands in for any source (rule
3).

## Sources

- The owner's note relayed by the owner's advisor at 00:59 on 2026-11-19, and the lead's ruling L-1029 that records it
  (project records of the run, outside the pack).
- The owner's note relayed at 00:35 on 2026-11-19 and the lead's ruling L-1026 (the same records).
- The lead's narrowing table of 2026-11-19 (L-1017 part A), the lead's rulings it cites (among them L-975, L-996,
  L-998, L-1015 and L-1017 part B), and the owner's rulings of 2026-11-18 (the same records).
- TASKS.md and OPEN_ITEMS.md as they stand on the base branch.
