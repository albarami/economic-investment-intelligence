# Decision 0069: The tender workbook taken as is and the portal read incrementally

| | |
|---|---|
| Status | Proposed, 2026-11-20; the lead records acceptance after confirming the owner's already recorded decision |
| Date | 2026-11-20 |
| Owner | The owner |
| Decided by | The owner's decision of 2026-11-20, relayed in the S2-T29W task brief |
| Amends | TASKS.md S2-T13, S2-T19 and S2-T29; document 14 section 10 slice S2 Gate; document 04 sections 2.1 Identity, fetch and licence, 2.2 Coverage, use and traps, 2.4 Public pages outside the registry and the tender reading; docs/README.md Decision records index |
| Purpose | Use the existing awards workbook and avoid re-reading the portal's complete awarded history, while preserving provenance, refusals and source distinctions |
| Read first | Decisions 0026 and 0046 item 8; decision 0064 item 41; TASKS.md S2-T13, S2-T19 and S2-T29; document 04 tender reading and awards source row |

## Context

The owner's decision of 2026-11-20 says to take the awards workbook as is and to
"build on what we already have not redo something we already did". The workbook
is already registered as `awards_owner_scrape` under decision 0046 item 8 and
TASKS.md S2-T29. Its pending profile, byte bound and pin filename currently hold
its normal build dispatch. The relayed aggregate profile supplies the sheet,
original columns, counts, date-storage behavior and measured byte size. Builder
tools receive that profile only, never a workbook row.

The portal list reader already collects six lists in two languages. Reading its
entire awarded history duplicates acquisition work behind the dated workbook.
The workbook and lists carry different columns; neither replaces the other's
source chain. This decision changes acquisition of the awarded list only.

## Decision

1. **Take the existing workbook as is.** Activate its normal intake from
   `data/public_cache/intake/awards_owner_scrape/`, with the workbook's SHA-256,
   explicit manifest and receipt. Read only `Awarded Contracts `, including its
   trailing space. Keep the ten original column names and each `report_url`.
   Map proof company to `Company name`, registration to
   `Commercial Registration Number` and value to `Approved Value`, keeping the
   source report's reviewed Arabic headings. The lead's measured size is
   2 534 256 bytes; round it up to the next power-of-two MiB, 4 MiB, as the
   acquisition ceiling, never a row bound. Reuse the tender host's already
   pinned intermediate for the same host, verifying both its existing PEM hash
   and the awards declaration's DER hash; missing bytes, changed hashes,
   disabled verification and wrong-host use remain refusals.
2. **Make the date assumption explicit.** The aggregate profile reports 9048
   data rows: 5453 day/month/year text dates, 3592 stored spreadsheet date
   cells and 3 blanks. Its dated range is 2022-12-19 to 2025-09-24. The lead's
   **ASSUMPTION**, based on the aggregate evidence supplied, is that stored date
   cells had their day and month swapped on import. Read day = stored month and
   month = stored day. Record this assumption and the separate stored-cell count
   in build evidence; normalise text dates day first, report unparsed physical
   row numbers, and keep blanks blank. A value cell is never turned into zero.
   The build measures its own counts and latest date; profile figures never
   replace those observations or become a constant cut-off.
3. **Read the awarded list incrementally.** At build time derive its cut-off
   from the latest parsed date in the bounded, hash-verified workbook intake.
   In each language read newest first and stop after the first page whose
   tenders all have award dates on or before that cut-off. A mixed page is read
   and the next page decides. A newer tender following an older one, within or
   across fetched pages, refuses with `award_order_invalid`; a missing award
   date refuses with `award_date_missing`. Record the workbook hash, cut-off,
   pages read and stop page. The archive verifies the stop against the intake
   and fetched pages. If intake is absent or refused, the awarded list is read
   in full and records why. That is independent-source acquisition behavior;
   the workbook refusal still prevents its publication and a successful
   assembly. All five other lists retain their full reads, page bounds and
   existing checks. No network operation runs in a test.
4. **Keep the sources complementary.** The workbook supplies the awarded
   company, registration number and approved value. The portal lists supply
   buying entity, category, tender type and company size. Preserve each source's
   own columns and dated lineage; invent no historical list field, award total,
   turnover or sales figure. The seeded proof sample and decision 0064 item 41's
   background re-check and name-consistency requirements remain unchanged.
5. **Keep snapshot and deployment scope separate.** The workbook is a dated
   snapshot, like the other data. A keep-updated mechanism belongs to deployment
   and remains an open item. The existing weekly cadence declaration is not
   evidence that such a mechanism runs. No acceptance checkbox is ticked here.

## Consequences

TASKS.md gains unticked amendment criteria on S2-T13, S2-T19 and S2-T29. Document
14's slice S2 gate records the complementary source coverage, dynamic cut-off
and stop evidence, or the reason for a full awarded-list read. Document 04's
source rows, tender reading and intake instructions describe that behavior.
Older requirements to use the tender portal in full are qualified by item 3's
awarded-list acquisition rule; licence terms still limit neither local fetching
nor showing under decision 0026.

The existing intake and list readers are extended rather than duplicated.
Provenance, source-specific refusals, privacy, security, commit flags, public
split rules, numerical methods and review gates remain required. AGENTS.md and
CLAUDE.md need no rule amendment. This proposed record claims no live workbook
read, successful portal fetch, independent implementation approval or slice gate.

## Open questions and assumptions

- The lead's stored-date interpretation in item 2 is an assumption from the
  supplied aggregate profile, not a row-level verification by the builder.
- Deployment must own the mechanism for keeping both dated sources updated;
  its schedule, operator and evidence remain to be assigned.
- The lead runs the real intake and portal build, checks the same-host pin
  against its existing local bytes, and obtains the required independent review.

## Sources

- The owner's decision of 2026-11-20 and aggregate-only workbook profile,
  relayed in task brief S2-T29W, **INTENT**, **THE WORKBOOK: AGGREGATE PROFILE ONLY**
  and **TASK** items 2, 3 and 5; no workbook row was supplied.
- [Decision 0026](0026-public-sources-used-in-full-locally.md), **Decision**;
  [decision 0046](0046-drop-hiring-flows-and-fetch-every-public-source.md) item 8;
  [decision 0064](0064-the-narrowing-rows-decided.md) item 41.
- [TASKS.md](../../TASKS.md), S2-T13, S2-T19 and S2-T29;
  [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md), **2.4 Public pages outside
  the registry — decision 0046** and the tender reading;
  [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md), **10. slice S2 —
  Public pack, frame, spine, places and investment sources**, **Gate**.
