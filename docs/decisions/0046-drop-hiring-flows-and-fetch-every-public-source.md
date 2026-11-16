# Decision 0046 — Drop hiring flows and fetch every public source

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-16 |
| Decision authority | The owner's note relayed by the lead on 2026-11-16 at 11:10 and the owner's words relayed by the advisor at 12:41 and 12:52, with lead rulings L-694, L-700 items 2 and 4, L-701, L-705, L-707, L-708 and L-709. |

## Context

The owner no longer wants the hiring-and-leaving question-bank gap carried forward. Its method card and task leave version 1. Employment spells, monthly joiner/leaver/mover structures and their aggregate calibration remain shared world-build and privacy material, not a reason to retain the retired analysis.

The owner also requires every public source to be fetched. A licence or an uncertain publisher answer does not exclude a visitor-readable source. Decision 0034 still prevents a value from a source without an open licence entering the repository; public values stay in the uncommitted cache with receipts and hashes.

The owner then ruled, in words relayed by the advisor at 12:41 and 12:52, that the state procurement awards workbook the owner collected is not private: it is the owner's own scrape, saved on 2026-11-03, of the public award reports on the state procurement portal. It is Public under decision 0026, but it is not an official table and its completeness is unknown.

Two supplied source groups resolve existing registry obstacles and add public pages outside the registry. They are implementation plans, not evidence of a successful fetch. The age-and-sex WorldPop grid already has the `worldpop_qat_agesex` registry row, the `pub_pop_agesex_grid` contract and S2-T14 as its owner, so the new work extends that path rather than adding a duplicate.

The individual decision question bank is not in the repository; the lead holds it in the owner's relayed note of 2026-11-13. By the lead's count of that bank (lead ruling L-705), it holds 109 questions in 16 user groups; the ministries' group holds 8 of them, and 3 questions, one each for business and technology suppliers, schools and training providers, and recruitment firms, cite gap N1 as their evidence, leaving 98 questions in 15 groups. S6-T04 receives the bank from the lead, excludes those questions and records both numbers, with a test that asserts them; no one-question-per-gap assumption is made.

## Decision

1. **Retire hiring and leaving flows and gap N1.** S7-T18 and method card C45 are withdrawn and retain their IDs. Remove only C45's share of MTH-124 and TST-267; C42, C43, C44, C46 and C34's fitted variant remain. Remove S7-T18 only from S7-T13's dependencies. Close OI-135 by appending the decision, preserving its earlier text. Remove N1 from the question-bank gaps and from document 04 section 12. Every N1 question is excluded when S6-T04 enters the bank; the historical declared total is not presented as a current recount. The amendments below retire the corresponding passages of decisions 0023 and 0036 without editing those accepted records.

2. **Keep the shared world build.** Retire no employment-spell, monthly-transition, stayer-wage, mover, joiner, entrant or aggregate hiring/leaving-rate calibration structure outside C45 and S7-T18. The complete retained-use inventory is under **Amended passages**. No world-build material exists solely for N1, so none is removed. C39's talent-pool and competing-job ratio remains independent.

3. **Fetch every public source through the normal seam.** Decision 0023 item 12 and decision 0026 stand: every visitor-readable public source is fetched and used in full locally. Uncertain licence or publisher terms are recorded and never block that fetch. PUB-01 to PUB-16, especially PUB-12 and PUB-13, continue to govern citation, the uncommitted cache and local use. Decision 0034 and every commit flag continue to prevent unlicensed source values entering the repository. Synthetic data remains limited to the confirmed sources of decision 0023 item 12; no public source is replaced by synthetic data.

4. **Add S2-T28 for the twelve newly unblocked registry rows.** Insert the lead's entry after S2-T27, with queued status and the amendment line of lead ruling L-701, which settles the portal column types, the municipality polygons' column types, the accident table's year-partition paging, the nationality-column guard and the Overture listing check. It covers `wage_sector`, `wage_bands_priv`, `work_hours_act`, `cpi_group`, `zone_population`, `census_hh_type_2020`, `accident`, `bnd_muni_2025`, `places_ovt`, `bldg_ovt`, `worldpop_qat_2020` and `census_2020_workbook`. It lifts the resolved skip reasons, keeps the five rows owned by S2-T14, S2-T15 and S2-T16 unchanged, uses year-partition accident pages and the existing whole-file Overture part-row reader, and retains all rule-10 and commit guards. The census workbook keeps the row's Census 2020 identity and records the supplied filename's 2022 wording as a lead question. The amendment of this record's review fix adds L-701's column-value guard and the `bnd_muni_2025` publisher text with its read date; the accident table's sixteen fields, its nationality split and its birth-year column kept as a public age attribute that no card uses until a later ruling; `places/fetch.py` changing only to share a constant; and the snapshot timing of lead ruling L-694: no live re-fetch overwrites a cached file before S2-T27's archive merges, and after it these rows enter that archive as dated snapshots. Under lead ruling L-707, the accident row is not activated in S2-T28, because the main line has no bounded transport read: it keeps the skip reason `partition_byte_bound_unconfirmed` while its year-partition plan, receipt and refusals are built and tested offline, and S2-T29 activates it through S2-T25's shared bounded reader; every existing reader of the place and building cache receives the rows it received before, with the listing envelope beside them.

5. **Add S2-T29 for public sources outside every registry.** The task registers and fetches the insurance tables; Visit Qatar and Qatar National Convention Centre event calendars; the Tawteen supplier page; Manateq tariff page; Monaqasat classified list; education ministry private-school directory; and the existing `worldpop_qat_agesex` age-and-sex file folder. It also confirms direct URLs for S2-T19's `gis_boundaries` and `gis_imagery_history`, lifting only `direct_url_unconfirmed`. WorldPop stays on S2-T14's fetcher and registry row. Calendar and list pages become dated table snapshots in S2-T27's immutable archive. Decision 0045 item 4 supplies daily re-fetch for tender notices and event pages and weekly re-fetch for supplier credentials; a source with no fitting published schedule uses the existing `none` with `frequency_unconfirmed` handling, never an invented cadence. Helper-read counts are leads, not committed facts. Under lead ruling L-708, the Monaqasat classified-company list is supplier credentials with weekly re-fetch, opened by a host-scoped pin of the intermediate certificate its server omits; the private-school directory, which resets the connection with verification on or off, is tried with a normal browser user agent and then a browser-driven capture, and an access failure is recorded with its date; and the municipality polygons' registry row records that the portal states no publisher, licence, description or update frequency.

6. **Keep transport verification and rule 10 whole.** TLS verification is never disabled. For the leaf-only chains of Monaqasat and the education ministry, S2-T29 specifies host-scoped SHA-256 pins of each issuing intermediate certificate, another-maker security review, and planted wrong-pin and other-host refusals. Public sex and nationality splits stay in source categories and geography; whole published grid cells may be summed over an area; no split joins to or segments worker, residence or company records. S2-T29 is Deep because it changes certificate-pinning and hash-pinned input controls.

7. **Leave every other control unchanged.** Decision 0035 stands in full. Apart from this record's two slice S2 gate sentences, no gate, privacy rule, attack size, tolerance, rule 10 or rules 16 to 25, or synthetic-source set changes. The event calendars are to become dated Public snapshots, not proof that every events question has coverage. The private-school directory supplies no capacity, enrolment or catchment, so the school-capacity refusal and decision 0045's OI-[LEAD-3] remain. Supplier and tariff pages do not close the supplier-certification question gap.

8. **Register the owner's scrape of the public award reports.** Under lead ruling L-709, S2-T29 registers the awards workbook as `awards_owner_scrape`, "owner scrape of public award reports, retrieved 2026-11-03", taken by `./eii build-public` from an uncommitted intake folder with its hash and receipt. Each row keeps the original column names and its `report_url` as its proof link; text dates are normalised with the unparsed count reported; the row count and the date range are recorded with completeness unknown, and no total is stated as all state awards; blank cells stay blank, never zero. A seeded sample of 30 links is re-fetched through the normal seam and the match rate recorded as the check on the scrape. A match report joins the awards to the company registers by registration number only after the independent name-consistency check, keeping and counting unmatched rows. Awarded values by company are shown with their source link and date and never as turnover or sales. A weekly `award_reports` family checks for new award reports. No value of the workbook enters the repository (decision 0034). The tender-notice work of S2-T13 and S2-T19 is a different source and stays. The awards source serves the supplier-certification gap (N6, OI-138) as evidence, without closing it.

## Consequences

- TASKS.md withdraws S7-T18 and queues S2-T28 and S2-T29. S2-T08 depends on both new source tasks so its source-completeness gate includes their outputs. Document 14 names both tasks and adds their gate sentences.
- The slice S2 gate adds: **eleven of the twelve unblocked public sources fetch through the normal seam with receipts and hashes, and the accident table's year-partition plan and refusals pass offline until S2-T29 activates it through the shared bounded reader**.
- The slice S2 gate also adds: **the sources of S2-T29 have normal-seam registry rows and dated Public snapshots, with wrong-pin and other-host TLS attempts refused**. These are gate conditions, not claims that the sources have already been fetched.
- BRF-104, AI-129 and the glossary distinguish the declared historical bank from the bank that remains. The remaining total is the lead's count under ruling L-705, confirmed by S6-T04's test, never a figure inferred from gap labels.
- Document 04's events row now records the two calendar sources planned for registration by S2-T29; its school and supplier rows retain their unanswered capacity and certification limits. OI-137, OI-138 and OI-139 are not closed.
- The new tasks and gate conditions do not assert implementation, successful retrieval or a passed gate.

## Amended passages

### Decision 0023

- **Item A9, decision question bank:** the list of bank gaps no longer includes hiring and leaving flows. Every N1 question is excluded from the catalogue and evaluation seeds. The stated 109 questions for 16 user groups is the declared historical total, not a recount after the ministries' group or N1 removals; S6-T04 records the N1 removal count and resulting total from the supplied bank.
- **Item A10, collecting data:** delete the sentence that makes hiring and leaving flows wait for the value-extraction session. That analysis is withdrawn, not deferred. The ten open-data families and the rest of the item stand.
- **Item 12, data rule:** unchanged and reaffirmed by item 3 above.

### Decision 0036

- **Item 4, aggregate realism:** unchanged. Its aggregate hiring-and-leaving-rate calibration is shared world-build material under SYN-90 and is not the retired C45 analysis.
- **Item 6, section 6 eligibility inventory:** remove the labour-market-tightness eligibility entry associated with C45. C39 remains its own method.
- **Item 6, method inventory:** MTH-124 now names C42, C43, C44, C46 and C34's fitted variant, excluding C45.
- **Item 6, task mapping:** remove S7-T18 from the slice S7 mapping. S7-T16, S7-T17, S7-T19 and S7-T20 remain.

### Decision 0045

- **Item 7, sources not added:** the statement that no live-events-calendar source is added is amended for the Visit Qatar and Qatar National Convention Centre pages registered as dated Public snapshots by S2-T29. Their coverage is recorded only after fetch and does not by itself close question-bank gap N4 or OI-137. The school-capacity limitation and decision 0045's OI-[LEAD-3] are unchanged; a private-school directory is not capacity, enrolment or catchment evidence.
- **Item 4 and the snapshot archive:** unchanged and reused for the new dated snapshots and cadences.

### Current pack and task documents

- **TASKS.md, S7-T18:** the heading and ID remain, followed by `Withdrawn by decision 0046` and the existing withdrawn-delivery form. **S7-T13:** remove only S7-T18 from its dependency list. **S6-T04 and S8-T05:** exclude every N1 question, plant its refusal, and use S6-T04's recount of the supplied bank without inferring a total. **S2-T08:** add S2-T28 and S2-T29 to its integration dependencies and source-completeness criterion. **S2-T27:** insert the supplied S2-T28 entry immediately after it, then S2-T29 in the same task form.
- **Document 01, BRF-104:** remove N1 from the live gaps, exclude its questions and mark 109 as the declared historical total pending S6-T04's recount.
- **Document 03, `employment_spell`, DAT-32 to DAT-34, DAT-71, DAT-73, DAT-137 and DAT-164:** retain employment spells, adjacent-month structures, stayers, joiners, leavers, movers and `stayer_wage_index`, and spells bounded by register dates. These serve the release contracts and privacy controls, not only C45. No passage changes.
- **Document 04, section 12:** remove the hiring-and-leaving row and N1 from the seven-gap list, leaving six historical gaps. Change the open caveat-key sentence to those six. Amend the events row for S2-T29's planned dated snapshots without closing N4. **Section 2.4, Public pages outside the registry — decision 0046:** new; it lists the planned rows `insurance_tables`, `events_visit_qatar`, `events_qncc`, `suppliers_tawteen`, `manateq_tariffs`, `monaqasat_classified`, `schools_private_directory` and `awards_owner_scrape` with their snapshot and use limits. **Open items touching this document:** OI-135 to OI-139 becomes OI-136 to OI-139. **Sections 2.1 and 2.2:** retain `worldpop_qat_agesex` and its S2-T14 ownership; the decision 0046 source plan reuses that row.
- **Document 05, wage manifest, SYN-25, SYN-29, monthly employment transitions, pay-composition truth fixtures, mover/joiner/entrant canaries, SYN-72 and SYN-90:** retain all joiner, leaver, mover, stayer and aggregate hiring/leaving-rate uses. They drive the synthetic world, composition tests and privacy canaries. No passage changes.
- **Document 06, adjacent-month cohorts and PRV-29, PRV-44, PRV-45, PRV-55, PRV-56, PRV-69, PRV-71, PRV-75, PRV-76, PRV-112, PRV-113, PRV-116 and PRV-121, with related assumptions and limitations:** retain `month_change`, stayer wage indices, exact attacker-view constraints, mover/joiner/entrant canaries and cross-month attacks unchanged. No passage changes.
- **Document 07, MTH-83:** remove the C45 sentence. **C45:** retain the heading and ID with an explicit withdrawal and no build criteria. **MTH-124:** enumerate C42, C43, C44, C46 and C34's fitted variant. **Section 6:** remove the labour-market-tightness row. Retain C19/MTH-78's stayer index, C20/MTH-80's joiner/leaver/stayer changes, C31/MTH-123's employment-retention branch and C39's independent ratio.
- **Document 09, AI-129:** remove hiring and leaving flows from the live gap list and the OI-135 reference; exclude all N1 questions and require S6-T04's actual recount. Retain the other gaps and the declared historical total with that qualification.
- **Document 12, TST-267:** test the remaining revised methods C42, C43, C44, C46 and C34's fitted variant rather than every revised method including C45. TST-206 and the other cohort and stayer tests remain unchanged.
- **Document 14, slice S2:** add S2-T28 and S2-T29 to the task list, S2-T08's integration and both gate sentences, with the accident activation in S2-T29. **Slice S7:** remove the S7-T18 task line. No other dependency changes.
- **OPEN_ITEMS.md, OI-135:** append the closure by this decision and retain all previous text. The introductory historical N1 summary remains as history; no other open item is edited.
- **Glossary, decision question bank:** apply the same N1 exclusion and historical-total qualification as BRF-104 and AI-129.
- **Documentation index:** add this record to the accepted-record sentence and decision table.

## Proposed open items

- **OI-[LEAD-1] — S2-T29 TLS pinning:** approve the Deep implementation and another-maker security review for host-scoped SHA-256 pins of the issuing intermediate certificates of Monaqasat and the education ministry, including planted wrong-pin and other-host refusals. TLS verification must never be disabled.
- **OI-[LEAD-2] — Census workbook identity:** confirm that the supplied archived workbook filename containing 2022 is the intended file for the registry row whose title says Census 2020. Keep the row identity and record the filename until answered.
- **OI-[LEAD-3] — Question bank supplied to S6-T04:** the lead supplies the decision question bank from the owner's relayed note to S6-T04, with no product name other than EII; S6-T04's test confirms the lead's count (8 ministries' questions and 3 N1 questions removed, 98 questions in 15 groups remaining). The declared historical 109 is not that result.
- **OI-[LEAD-4] — Municipality polygons' publisher and licence:** the portal's dataset page states no publisher, licence, description or update frequency (the advisor's reading of 2026-11-16, matching the lead's); the gap is recorded in the registry and the file is fetched for local use under decision 0026. It stays open until a publisher statement is found.
- **OI-[LEAD-5] — Overture parts of a later release:** selecting the Qatar parts at a later Overture release is left to a later task; S2-T28 checks the registered release only.
- **OI-[LEAD-6] — Accident partition byte spans:** the lead reads each year partition's size live and records it in document 04 before S2-T29 activates the accident row; no bound is invented.
- **OI-[LEAD-7] — Private-school directory access:** if neither a normal browser user agent nor a browser-driven capture opens the directory, the lead tells the advisor in one line and the row records the access failure with its date.
- **OI-[LEAD-8] — Accident perpetrator birth-year use:** whether any card may use the accident table's perpetrator birth-year column, and under which caveat key, is a proposed open item (lead ruling L-707 item K3); no card uses the column until it is answered.

## Sources

- The owner's relayed note of 2026-11-16 at 11:10.
- Lead rulings L-694, L-700 items 2 and 4, L-701 (the first build round of S2-T28), L-705, L-707 (the second build round of S2-T28), L-708 (the advisor's source checks of 2026-11-16 at 12:36) and L-709 (the awards workbook).
- The owner's words relayed by the advisor on 2026-11-16 at 12:41 and 12:52.
- The independent review of this record by another maker (findings D1 to D7), adopted in full.
- The lead's S2-T28 task entry, with the amendment of lead ruling L-701.
- [Decision 0023](0023-ten-additions-and-the-data-rule.md), items A9, A10 and 12; [decision 0026](0026-public-sources-used-in-full-locally.md); [decision 0034](0034-licence-questions-of-public-sources-are-answered-at-a-go-live.md); [decision 0035](0035-what-the-audience-sees-names-no-data-origin-and-the-backend-marks-it.md); and [decision 0036](0036-generated-data-stands-for-the-future-real-data.md).
- [Decision 0044](0044-the-conversation-test-lab.md) and [decision 0045](0045-eiis-own-capabilities-and-the-snapshot-archive.md), the accepted documentation base for this drafting task.
- Documents 01, 03 to 07, 09, 12 and 14 at the stable anchors named above; PUB-01 to PUB-16, PUB-90, PUB-97 and PUB-99; and AGENTS.md rules 3, 5, 7, 10, 12, 13, 19 and 37.
