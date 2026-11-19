# Decision 0068: Public map integration follow-ons

| | |
|---|---|
| Status | Lead ruling recorded, 2026-11-19; documents-only task additions, independent review pending |
| Date | 2026-11-19 |
| Owner | The owner |
| Decided by | Lead ruling L-1136 of 2026-11-19, adopting the S3-T10 plan review's CONSULT dispositions C1 to C6 with corrected task numbers |
| Amends | [TASKS.md](../../TASKS.md) (four queued tasks, S3-T10 dependencies and an S3-T09 fix assignment); [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md) section 11 task list and order; [docs/README.md](../README.md) decision index |
| Purpose | Give the unowned Public map integration work its own acceptance criteria, without widening a built task or cutting value. |
| Read first | [TASKS.md](../../TASKS.md) Queue rules, S3-T09, S3-T10 and S3-T23; [08_BACKEND.md](../08_BACKEND.md) sections 6.1, 6.2, 7 and 8.1; [07_ECONOMIC_METHODS.md](../07_ECONOMIC_METHODS.md) Common rules and C9 Zone momentum from utility series; AGENTS.md rules 7, 16 to 23 and 33 to 39 |

## Context

The S3-T10 plan review found routes and behaviour that documents 08 and 07 already require and no built task owns.
Document 08 **8.1 Endpoints** specifies the release and lineage reads, the typed tool route and local map/font paths;
its **6.2 Tool contracts** and **7. Playbooks and the template writer** require the chosen area to survive the
site_check path. Document 07 **1. Common rules**, MTH-08, requires the complete source chain, and **C9 Zone momentum
from utility series** fixes the utility method rather than allowing a substitute opening figure. Assigning these
integration gaps to new tasks preserves both those requirements and the acceptance boundaries of built tasks.

The supplied S3-T10 plan r3, **CONSULT: lead assigns new follow-ons, no widening built tasks**, and its follow-on
dispositions, **Classification**, distinguish new work (C1, C2, C4, C5), the retained opening default (C3), and an
existing-owner repair and evidence holds (C6). L-1136 adopts those dispositions. The draft numbers S3-T23 to S3-T26
cannot be used: [decision 0064](0064-the-narrowing-rows-decided.md) item 6 already assigns S3-T23 to offline satellite
imagery. Under TASKS.md **Queue rules**, L-1136 assigns the four additions S3-T24 to S3-T27.

Read-only inspection of tip-T22, commit `46387fe393952a52be79a2091c5020abf4be5df6`, corroborates the integration
gaps: `api/app.py` mounts neither release nor lineage reads; `api/tools.py` dispatches only make_area and the three
Public context cards; `api/public_layers.py` returns empty gazetteer points and source records without registry
kind/hash bindings; `api/playbooks.py` requires a pin and rejects shape_id. Decision 0061 on that tip, **Open matters
and change control**, leaves playbook shape support and real-store route parity open. These module paths are
relative to `product/src/eii_product/` on that tip. S3-T22, decision 0061 and branch-only modules are named in plain
text, not linked as though they existed on this base. Their presence on a local tip supplies no merge or gate approval.

## Decision

1. **C1 — S3-T24, Mounted Public release and source-chain transport with live parity.** Mount the existing
   `GET /api/release` and `GET /api/facts/{fact_id}/lineage` contracts and bind the browser registry to the verified
   mounted Public release. Source, table and method bindings come from loaded tables, never constants or identifier
   heuristics. Preserve the Fact and tool-envelope schemas. Extend the existing S3-T08 live proof to execute the
   scoped Public layer/card queries of S3-T22 and the added named reads on real PostgreSQL and embedded DuckDB;
   a second-engine stand-in is not live evidence. The built browser must obtain its chains over same-origin HTTP.
   Missing or foreign chain links, fabricated bindings, omitted query executions, fixture provenance and pending
   live receipts each have planted violations in TASKS.md. Depends: S3-T22, S3-T02, S3-T09, S3-T14; reuse S3-T08's
   live proof and coordinate final query coverage with S3-T25 and S3-T26.
2. **C2 — S3-T25, Offline gazetteer resolution through the typed tool route.** Mount the existing resolve contract
   through `POST /api/tools/{tool}`, then carry a selected gazetteer key with an existing closed area preset into
   make_area. The picker rendering remains S3-T10's work. Preserve bilingual candidates, null-cell Public context,
   no-match and outside-land outcomes, and the boundaries-absent sentence. A place plus preset is never an official
   boundary. Unknown fields, key substitution, nearest-cell invention, raw numeral labels, provider attempts and
   missing parity queries each have plants. This adds dispatch work under its own task, not a fifth tool to S3-T22's
   accepted scope. Depends: S3-T22, S3-T03, S3-T04; final real-store evidence uses S3-T24.
3. **C4 — S3-T26, Preserve the chosen Public area in site_check.** Carry the selected polygon, radius, walk or
   free-flow drive area through the existing playbook request, session context, execution, cards and stage output.
   Document the closed input projection using the existing shape_id or pin/mode/cutoff vocabulary. Only an absent
   selection uses the default headline area; a distinct wider context stays identified. Reuse trusted routing and
   session storage; reject conflicting inputs, foreign-session/seat shapes and release mismatches. Forced default
   substitution, wrong-area card calls, accounting bypass, model egress and coordinate logging each have plants.
   No protected or Simulated block or full future site_check bundle is added. Depends: S3-T22, S3-T08, S3-T13;
   S3-T24 supplies final live parity and S3-T25 supplies named-place HTTP selection when used.
4. **C5 — S3-T27, Same-origin offline basemap and glyph assets.** Serve verified local PMTiles with HTTP ranges
   through `/tiles/*.pmtiles` and local glyphs through `/fonts/*`, on the existing API process. Wire the basemap
   extract and glyph configuration into the built app and prove actual geometry and EN/AR labels offline. Reuse
   S1-T04's range proof and S3-T09's shell/font work without widening either. Range corruption, path escape, missing
   fonts/glyphs, null extracts, forbidden labels, removed RTL plugin, missing active attribution, external attempts
   and fixture route bypass each have plants. No download, provider or S3-T20 remote work is required by these
   automated tests. Depends: S1-T04, S3-T02, S3-T09, S3-T22. Record exact mounted asset names/types and the official
   library pages used before implementation, preserving pins and retreat pins (decision 0054).
5. **Order and ownership.** Insert these four queued tasks after S3-T23 and before S3-T10, each in the six-field
   TASKS.md format with testable criteria and a planted violation for every guard. Add all four to S3-T10's Depends
   for its end-to-end step only. Other S3-T10 parts may be built ahead after the S3 re-cut head exists. S3-T25 and
   S3-T26 contribute their query cases before S3-T24's final live evidence closes; this evidence join is not a
   circular build dependency. S3-T11 keeps its existing review-follow-up role and S3-T20 stays after the gate.
6. **C3 keeps its default.** S3-T10 verifies the actual Scene 0 electricity growth/benchmark slot, period and wording
   before binding its dated Fact chip, as the plan's L-1012 Q3 default requires. No literal value, proxy or alternative
   hero is permitted. If unavailable, use only the catalogue unavailable sentence and record the open item; the
   opening-chip criterion stays unmet. No additional task is authorized for C3 by this record.
7. **C6 returns the phone bottom sheet to S3-T09 as a fix.** The S3-T09 amendment under
   [decision 0049](0049-one-product-for-every-screen-size.md) already requires it. On S3-T09's re-cut branch, first
   prove omitted-sheet, overflow and hidden-answer plants fail, then repair the sheet with answer/map visibility
   and drawer focus preserved at the pinned sizes, in both languages and themes. Its own fix commit needs its own
   review. No criterion is ticked and no status changed by this assignment. OI-09 native approval and the S3-T16 and
   S3-T22 reviews on the joined head remain required. Mutation-only evidence is read under
   [decision 0055](0055-mutation-testing-moves-to-after-go-live.md) items 1 to 4; the older draft campaign-gate wording
   neither revives a deferred campaign nor waives an ordinary test or review.
8. **No value is cut.** These are additional integration owners for existing requirements. No built task is silently
   widened; no existing acceptance criterion, source, privacy rule, number rule, command permission, tolerance,
   review, hosted check or slice gate is weakened. This record adds no code and claims no working route or passed gate.

## Consequences

TASKS.md and document 14 section 11 gain the four tasks and their order; S3-T10 names the four end-to-end
prerequisites and S3-T09 retains its repair. Each new task still needs its own plan, tests, evidence and independent
review. Task-owned transport/contract changes occur in that task's reviewed change, not in this documents-only
addition. If the expanded live proof needs additional command authorization, its task updates AGENTS.md and
CLAUDE.md byte-identically; no new command is authorized here.

OPEN_ITEMS.md records unresolved opening-fact availability, usable local assets and final live/joined-head evidence
as OI-320 to OI-322; OI-09 remains the native-approval owner. No release data or cache was inspected to settle them.
Material scope changes need a new decision record under AGENTS.md rule 46. An implementation result, review or
gate is never inferred from a planning document or a local branch tip (rule 47).

## Sources

- L-1136, 2026-11-19: supplied lead ruling adopting CONSULT C1 to C6 and correcting the four task numbers.
- Supplied S3-T10 plan r3, **CONSULT: lead assigns new follow-ons, no widening built tasks**; follow-on dispositions,
  **Classification**, **Draft task entries for the lead**, **Existing-owner fix and evidence checklist** and
  **What the inputs cannot settle**. These are planning evidence, not independent implementation approvals.
- tip-T22 at the full commit above: TASKS.md S3-T22; decision 0061 **Open matters and change control**; API modules
  named in Context, read only with git show. Branch-only files have no local Markdown link.
- [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md) **7.3 Columns** (`source_registry`, `fact_lineage`) and
  **9. The fact object**; [08_BACKEND.md](../08_BACKEND.md) **6.1 Common contract**, **6.2 Tool contracts**,
  **7. Playbooks and the template writer**, **8.1 Endpoints**, BE-104 and BE-116;
  [07_ECONOMIC_METHODS.md](../07_ECONOMIC_METHODS.md) MTH-08 and **C9 Zone momentum from utility series**.
- TASKS.md **Queue rules**, S1-T04, S3-T09, S3-T10, S3-T11 and S3-T23; decision 0064 item 6; decision 0049;
  decision 0055 items 1 to 4; AGENTS.md rules 33 to 39, 42 and 46 to 47.
