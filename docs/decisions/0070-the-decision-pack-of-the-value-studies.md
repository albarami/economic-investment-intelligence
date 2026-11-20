# Decision 0070: The decision pack of the value studies

| | |
|---|---|
| Status | Accepted, 2026-11-20 |
| Date | 2026-11-20 |
| Owner | The owner |
| Decided by | The owner's decision of 2026-11-20 |
| Amends | [TASKS.md](../../TASKS.md), priority order and task ownership as listed below; [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md), slices S2, S6, S7 and S8 and ENHANCEMENT BACKLOG; [docs/README.md](../README.md), decision index. The assistant chain-slot extension is assigned against document 09 AI-17; task-owned contract and catalogue amendments follow in its implementation. |
| Purpose | Put the existing high-value answers first, assign the agreed additions and keep the remaining value-study work after go-live. |
| Read first | TASKS.md Queue rules, S2-T04, S2-T19, S2-T29, S6-T10, S6-T11, S6-T12, S6-T20, S6-T21, S7-T01, S7-T03, S7-T05, S7-T09, S7-T11, S8-T01, S8-T03 and S8-T06; document 07 cards C4, C7, C10, C11, C13, C16, C39, C40 and C41; document 09 AI-17 and sections 5, 6 and 9; AGENTS.md rules 3, 5, 7, 8, 12 and 16 to 25. |

## Context

The owner's decision of 2026-11-20 selects priorities and additions from the value studies. The existing pack
already owns the six priority answers below. This record changes their order, not their methods, acceptance
criteria or input requirements. The additions have their own queued tasks; no planning entry is evidence of a
working source, release or card.

## Decision

### A — Priority before go-live, with no new data

Put these answers first in the slice S6 and slice S7 work order, subject to their existing dependencies, and in
the guided demo as they become available:

| Priority answer | Existing task and card owners |
|---|---|
| Robust site shortlist, with rank stability under changed weights | S6-T11, document 07 C11 Best-location ranking and rank stability; S6-T21, C40 Best three sites and "how sure" |
| Labour-shed staffing comparison | S6-T20, C39 Talent available near this site; S7-T03, C10 Staffing bands beside published averages and the statutory minimum |
| Imports beside local manufacturing | S7-T11, C13 Imports against local production, with S7-T02's supplier inputs |
| Second-site shared reach | S7-T05, C7 Shared reach between two doors |
| Parcel diligence | S6-T12, C16 Reverse fit and fit lists and document 09 AI-136's plots and zoning; S6-T10, C41 Property price measures for its separate price context |
| Break-even workbench with the user's own rent | S7-T01, C4 Sector unit economics and the break-even and breakpoint calculator |

This is order only. It adds no data, changes no criterion and bypasses no dependency or gate. In particular,
shared reach is never lost sales, parcel evidence never establishes approval or availability, the imports screen
never establishes an opportunity, and rent in the workbench remains the user's own input. Document 09's existing
playbook and claim families carry the answers; this priority note creates no new calculation or claim family.
The guided demo is S10-T03's guided story (DES-113); its existing in-order criterion for the golden conversation (decision 0045 item 2) is unchanged, and whether item A reorders its scenes is raised under AGENTS.md rule 46 rather than decided here.

### B1 — Awards and supplier release with its card family

Add S7-T35 for the awards and supplier release and its closed card family. Use the registered workbook source
`awards_owner_scrape` and the tender portal's newer awarded items, joined by tender id. Reuse S2-T29's intake,
proof and snapshot contracts, retaining the original workbook and portal chains and showing unknown coverage
truthfully. The supplier/award card states only what those Public sources establish. An awarded value is never
turnover or sales, and an award is not a supplier certification. Unmatched or conflicting tender ids remain
explicit rather than being guessed into a match. The older pages in item E are separate enrichment.

This belongs to slice S7 because S7-T09 owns the partner, supplier and tender answer and S7-T02 owns the supplier
lens; S2-T19 and S2-T29 remain the upstream acquisition owners. Task-owned release schemas, methods and catalogue
bindings are reviewed in S7-T35 rather than silently widening the existing `pub_tender` contract.

### B2 — Asking-rent context from listings

Add S6-T40 for asking-rent context from **a property listing source**. The lead records the actual source and its
terms in the source registry row at build time, with the normal publisher, retrieval and hash chain. Show Public
facts labelled **"asking rents from listings"**, with the date and listing count per area and property type.
Listings describe asking rents, not completed tenancies or vacancy. Calculators keep the user's own rent and are
never prefilled.

This belongs to slice S6 beside S6-T10's property context and S6-T12's site-fit context. It is a new Public context
task, not permission to reinterpret a sale or guide price as rent. Existing own-rent calculator criteria remain.

### B3 — Reviewed product-to-activity-to-occupation crosswalk

Add S2-T47 for a reviewed product-to-activity-to-occupation crosswalk. Record both links, their source or editorial
basis, versions and review, and keep unmapped and ambiguous entries explicit. No unreviewed relation becomes a
fact. It belongs to slice S2 because S2-T04 owns the reviewed activity spine and graph relationships and S2-T07
owns the calculation inputs that consume reviewed mappings; document 07 C13 already requires a reviewed product
mapping. A crosswalk adds no worker attribute, inferred qualification or person-level join.

### C — A typed reference to an earlier answer item

Add S8-T19 for a typed reference to an item of an earlier answer in the assistant's chain slot. Document 09 AI-17
currently carries context as typed slots only, never as an earlier model response. Extend that typed context with
an application-resolved item reference; do not carry earlier prose forward or treat a previous answer as a source
of facts. Revalidate the referenced item against the current release, catalogues, session and seat and obtain the
current facts through the existing closed tools. The same validator, accounting, numeral and template rules apply.

This belongs to slice S8 because S8-T01 owns routing, S8-T03 owns brief validation and S8-T06 owns memo and replay.
The task owns the precise closed reference schema and document 09 amendment; this record invents no schema field
or model-supplied identifier.

### E — Older awarded pages, once after the slice S2 gate

Add S2-T46 for a one-time fetch of the older awarded portal pages after the slice S2 gate. Keep them as cached
enrichment, joined to the workbook by tender id, through the existing source registry, receipts and snapshot
archive. Record source dates, the fetched coverage, matches, unmatched items and conflicts. Tests use invented
pages offline; no worker run or test fetches real pages.

This remains slice S2 acquisition work beside S2-T19 and S2-T29, but runs after its gate. It is excluded from
S2-T10's blanket dependency and does not reopen the gate or delay it. S7-T35 consumes the reviewed enrichment;
no periodic historical crawl or new source family is authorized.

### Enhancement backlog

Everything else of these value studies goes into document 14 **ENHANCEMENT BACKLOG**, each with its data needs,
the project rule numbers it touches and **release: after go-live**: real business outcomes; a general own-records
intake beyond the two existing forms; utility readiness; weather; extra forecasts; audit export. This schedules
additional work only; existing approved weather inputs, forecasts and print/export tasks keep their criteria.

## Consequences and change triggers

The task additions are S2-T46, S2-T47, S6-T40, S7-T35 and S8-T19. Each needs its own plan, tests, planted
violations, evidence and independent review. The companion operations task is assigned by decision 0071.
AGENTS.md and CLAUDE.md need no change for this documents-only record. No source was fetched, workbook read,
crosswalk approved or implementation criterion ticked by this change. Further data, a changed calculation,
weakened guard or changed accepted scope needs its own decision under AGENTS.md rule 46.

## Sources

- The owner's decision of 2026-11-20, items A, B1, B2, B3, C and E and the enhancement-backlog direction, supplied
  in the task brief. This is the authority for the additions, not evidence of source contents or implementation.
- [TASKS.md](../../TASKS.md), the task IDs cited above and Queue rules; [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md),
  sections 10, 14, 15 and 16 and **ENHANCEMENT BACKLOG**.
- [07_ECONOMIC_METHODS.md](../07_ECONOMIC_METHODS.md), the named cards in item A and C13's reviewed mapping;
  [09_AI_ASSISTANT.md](../09_AI_ASSISTANT.md), AI-17, AI-36, AI-42, AI-63 and AI-67 and section 3 Playbooks.
- [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md), **S2-T29 cached page and awards contracts** and `pub_tender` in
  **7.3 Columns**; [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md), `awards_owner_scrape` in **2. Source registry**.
- [AGENTS.md](../../AGENTS.md), rules 3, 5, 7, 8, 12, 16 to 25 and 33 to 47.
