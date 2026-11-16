# 0031 — Relative busyness of named venues from a provider's interface

| | |
|---|---|
| Status | Proposed, 2026-11-16: the lead's record of the owner's decisions, for the owner's confirmation |
| Date | 2026-11-16 |
| Owner | Project owner |
| Decided by | The project owner: the owner's note of 2026-11-14 allowing the provider's two keys for this source; the owner's decisions on class, coverage and plan of the same evening, relayed by the owner's advisor under the owner's delegation; and the owner's decision on the plan of 2026-11-15, which replaces the free-credits limit of the first draft (project records of the run, outside the pack). The lead's rulings of 2026-11-16 settle the label, the smallest number of venues, the update date, the basis of use, the source id and the wording of PUB-12 |
| Supersedes | In part, [decision 0019](0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 19: its source (the page of one publisher), its label, its page reader, and its sentences on that publisher's terms and on the basis of use. Every other clause of item 19 stands. Item 18 stands. |
| Amends | Documents 01, 02, 03, 04, 05, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 and 17, TASKS.md (tasks S2-T01, S2-T16, S2-T21, the slice S3 task of cards C36 to C38 and the slice S2 gate) and docs/README.md, in the passages listed in the amendment list that goes with this record. In document 04 it amends the PUB-12 sentence that [decision 0040](0040-public-trade-sources-and-held-tables-in-use.md) item 2 added on registration and paid access; decision 0040 itself is not edited. [Decision 0026](0026-public-sources-used-in-full-locally.md) is not changed: this source follows its item 3. |
| Purpose | Record the one source of the relative busyness by hour of a named venue, the class and basis in which its figure enters, its label and dates, how many requests a run sends, how coverage gaps are shown, how the two keys are held, how spending is capped, and how PUB-12 reads such an interface. |
| Read first | [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md) PUB-12 and PUB-101; [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md) DAT-85 and DAT-157; [05_SYNTHETIC_WORLD_AND_SIMULATION.md](../05_SYNTHETIC_WORLD_AND_SIMULATION.md) SYN-86; [07_ECONOMIC_METHODS.md](../07_ECONOMIC_METHODS.md) card C37; decisions 0019, 0026, 0034, 0035 and 0040; AGENTS.md rules 4, 5, 7, 8, 14, 24 and 25 |

## Context

- Decision 0019 item 19 made the relative busyness by hour of a named venue a Public fact of a `place_public` subject, read by the project's own page reader from the venue's page of one publisher. Item 18 made the hour-of-day shape, pooled over the named venues of each place category, an anchor of the simulation (SYN-86).
- That page source cannot serve the build. A read of one venue page with plain requests found no weekly figure in the first response. A test with the project's own browser, as a visitor, found that the page shows a visitor a limited view without the figures, and that the full view lies behind a sign-in. Under PUB-12 such a source is not read.
- The owner then allowed the build to use a provider's interface for this source, with two keys, and asked for a coverage test of about 40 named venues across place types. On 2026-11-15 the owner decided that the two keys run on the owner's paid plan within a monthly credit limit set in writing.
- The provider calls its figure a forecast: seven days of 24 hourly values, each from 0 to 100, relative to the venue's own peak of the week. A request that creates a venue's forecast costs more credits than a query that reads a stored forecast back.
- AGENTS.md rule 4 allows "a published relative-busyness figure of a named venue" as a Public fact and forbids a real mobility feed. Rules 24 and 25 allow a forecast only from tested code with its backtest. A change of source needs a decision record (rule 46).

## Decision

1. **The provider's interface is the one source.** The interface of the provider BestTime replaces the page reader of decision 0019 item 19 as the one source of the relative busyness by hour of a named venue. The page of decision 0019 is not read. The source id is `busy_besttime`, which replaces `busy_gmaps` in every live passage of the pack, in the registry and in the code and tests that hold it; the accepted records 0019, 0023, 0026 and 0040 keep the old id or the old source as history. The figure is read inside `./eii build-public` only, for the named venues of a build-time list, never at run time and never from a user's choice of site.
2. **Class, basis and status.** The figure enters as a published relative busyness of a named venue: a Public fact of a `place_public` subject, with the provider as publisher. Its licence text is the provider's terms, recorded truthfully with the date read, and its registry row has `licence_basis: provider_terms`, the basis that DAT-85 and PUB-12 give to a provider's interface used under its own terms (decision 0026 item 3). DAT-85 and the matching sentence of PUB-12 name this source's interface beside those of PUB-95 and PUB-97. Its evidence status stays Observed: the figure is observed as the provider publishes it.
3. **What is taken, and the origin of the figures.** Nothing is taken but the venue's own relative hourly figures: seven days of 24 values. No person, device, trip or count enters, and the figure is not a mobility feed. The caveat of card C37 stays as it is: a relative index, never a count of people, never in one component with an estimated-people figure. The provider's words on the origin of its figures are held now as two fragments, quoted here as fragments: "derived from anonymized mobile signals" (its documentation) and "based on aggregated and anonymized signals from external, third-party sources" (its terms). The whole sentence of the terms page is copied into document 04 at the lead's terms read before the first fetch. The build of task S2-T16 fails while the terms text of the registry row is empty.
4. **Label and dates.** A screen labels the figure "BestTime relative busyness". It never calls it a forecast, because it is a published figure and not a forecast of the project's tested code, and never "foot traffic". Each figure shows its retrieval date and, beside it, the provider's own update date of that venue's figures. Where the provider's answer states no update date, the screen shows "update date not stated".
5. **Requests in a run.** For each venue of the build-time list, a run sends at most one request that creates the venue's forecast and, after it, at most one query of the stored forecast, which reads the provider's update date. It never sends a second request of either kind for one venue. An answer whose shape differs from the documented shape fails the build with a message that names the source and a key-free form of the address, and nothing is loaded from it. The reader stops before a request that would pass the run's credit limit, and nothing further is sent in that run. The run's credit limit is read in the lead's shell from the environment variable `EII_BESTTIME_RUN_CREDIT_LIMIT`, a whole number of credits that is not committed; a keyed run refuses to start when it is unset or not a whole number above zero.
6. **Coverage and the pooled shape.** Coverage is accepted as measured. A venue for which the provider publishes no figure shows no figure, with that reason; nothing is filled in from another venue. The venue crosswalk of PUB-101 is unchanged: a venue counts only when the provider's matched venue is the one asked for, and the matched name is compared in memory and never committed. The smallest number of venues with a figure that makes a pooled hour-of-day shape for a category group (`mob.hourly_shape_min_venues`, SYN-86) is 3. A group below it gets no anchor from this source and keeps the flat shape of SYN-86 (every hour 1).
7. **The keys.** The provider's two keys are read from the environment only, and only the lead's own shell runs a keyed fetch through `./eii build-public`. Neither key is ever printed, logged, committed or put in a brief, worktree, sandbox, fixture or document. Where the provider takes a key as an address parameter, the address that carries it is never written to a log, receipt, error, cache name, fixture or file, and every failure message names a key-free form of the address (PUB-06).
8. **Plan and credit cap.** The two keys run on the owner's paid plan. Spending is capped by a monthly credit limit that the owner set in writing, counted from the provider's own account figures. The lead stops at the cap, records the credits used and tells the owner. The cap's number, the plan's name and price and every account detail stay out of the repository.
9. **PUB-12 and the visitor rule.** One clause is added to PUB-12: a provider's interface admitted by a decision record and read with the project's own key in the lead's shell (decisions 0019, 0040 item 2 and this record) is not a visitor reading and is not barred by the visitor rule. The clause names the records, not the keys. It gives no permission to find page tokens or to pass an access control.
10. **Tests, gates and the nightly run.** No test, gate, command of `./eii test`, CI job or the guided story needs either key or the network. Tests read invented answers of the provider's documented shape only. The source stays out of the nightly live fetch; the list of TST-52 is renamed and not widened.
11. **Values and the registry row.** The fetched values stay in the uncommitted public cache, in the releases and in the freeze bundles; no repository file, fixture, test, brief or document holds one. The registry row keeps `commit_allowed: false`. Its host joins the allow-list of PUB-03 by the reviewed registry change of task S2-T16.

## Evidence

- The coverage test of 2026-11-14: 40 named venues of Greater Doha, one request that creates a forecast for each, with no retry. 22 returned an hourly forecast, 15 were found with no forecast and 3 were not found. In all 22 the provider's matched venue has the name asked for and lies inside the country.
- By place type (asked, with a forecast): shopping mall 5, 4; traditional market 2, 1; museum, library and culture 5, 4; park 3, 2; restaurant 5, 5; cafe 4, 0; hypermarket and grocery 4, 2; hotel 4, 0; entertainment 3, 1; sport 2, 1; transport 2, 1; convention centre 1, 1.
- The provider's text for a venue found without a forecast: "Venue found, but could not forecast this venue. Potential issues: This place is too new, or not does not have enough volume (visitors) to make a forecast."
- The answers that create a forecast held no update-date field. The update date is a field of the answer of a stored-forecast query. In the test, one read-back of each stored forecast showed update dates between 2026-04-11 and 2026-10-11, none on the day of the request. Those dates are not reused. Values are in steps of 5.
- The provider's documentation and terms, read 2026-11-14: "derived from anonymized mobile signals"; "based on aggregated and anonymized signals from external, third-party sources"; the percentages are "relative to that specific venue's peak traffic of the week"; a venue "generally needs to be a public business with at least 100 visitors per week"; data may be used "within your commercial applications, products, or services"; redistribution, resale or sublicensing "as a standalone product or on a data marketplace" is prohibited without written permission. The terms state nothing on attribution or on storing; the provider's questions page says values may be stored.

## Consequences

- The registry row of `busy_gmaps` is replaced by a row of `busy_besttime`: the provider as publisher, its terms as the licence text, `licence_basis: provider_terms` with no decision record (the registry loader admits a decision record only with `owner_decision`), `commit_allowed: false`, out of the nightly live fetch.
- `pub_venue_busyness` gains `provider_updated_on`, the provider's update date, beside `retrieved_on` (items 4 and 5).
- Every label "Google Maps popular times" in the pack becomes "BestTime relative busyness"; the caveat key `relative_busyness_not_people` and its meaning stay (items 3 and 4).
- `mob.hourly_shape_min_venues` is set to 3 (item 6).
- Task S2-T16 is re-planned as a reader of the provider's interface in place of a page reader (TASKS.md).
- Document 13 lists the two keys among the environment variables.

## Amended passages

Listed in the amendment list that goes with this record. Decision 0019 is not edited; the decision index of docs/README.md records that its item 19 is superseded in part by this record once confirmed. Decisions 0023, 0026 and 0040 are not edited.

## What would change this decision

- A change of the provider's terms, of the origin it states for its figures, or of the shape of its answer. The terms are read again at each fetch, and a changed terms page fails the build until a reviewer records it (PUB-10).
- The owner's change of the plan or of the credit cap.
- A public source of the same kind that a visitor can read under PUB-12.

## What is not decided

- The venues of the build-time list. That list is a data file of task S2-T16, never part of this record; its venues are chosen for the pooled shapes first.
- The going-live position of this source. It stays on document 17's list (decision 0026 item 4; decision 0034 item 1).

## Sources

- The owner's note of 2026-11-14, the owner's decisions relayed by the owner's advisor the same evening, and the owner's decision on the plan of 2026-11-15 (project records of the run, outside the pack).
- The lead's coverage test of the provider's interface, 2026-11-14, and the records of the page source (project records of the run, outside the pack).
- The lead's rulings on the first draft of this record, 2026-11-16 (project records of the run, outside the pack).
- BestTime, interface documentation, terms of service and questions page, read 2026-11-14; their addresses and hashes are recorded in the registry row by task S2-T16 at the lead's terms read before the first fetch.
