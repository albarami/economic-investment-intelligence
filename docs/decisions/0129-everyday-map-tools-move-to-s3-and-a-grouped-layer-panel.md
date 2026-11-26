# Decision 0129: Four everyday map tools move to slice S3, and a grouped layer panel

| | |
|---|---|
| Status | Accepted under the owner's standing approval of 2026-11-25 22:06 |
| Date | 2026-11-26 |
| Owner | The owner |
| Drafted by | Task R1-DREC129.b1; maker Anthropic, model Claude Opus 5.5 |
| Purpose | Place four of the everyday map tools of decision 0065 as early as their Depends lines allow, and give the owner's request for a designed layer menu its own task, with no acceptance weakened. |
| Amends | Decision 0065 items 4, 5, 7 and 8 in their slice placement only; TASKS.md S7-T30, S7-T31, S7-T33 and S7-T34, the Depends lines of S3-T11 and S7-T06, and new tasks S3-T30 and S3-T31; document 14 section 6 and the task lists of sections 11 and 15; the Decision records table of [docs/README.md](../README.md). No requirement ID, gate sentence, method, privacy rule or acceptance criterion is weakened. |
| Read first | [Decision 0065](0065-eight-everyday-capabilities-of-the-map-screen.md); TASKS.md S3-T09, S3-T10, S3-T11, S3-T12, S7-T06 and S7-T30 to S7-T34; document 10 section 6, **One hero layer at a time**, and section 3.2 Routes; [decision 0049](0049-one-product-for-every-screen-size.md). |

## Context

The owner gave a standing approval on 2026-11-25 at 22:06, relayed by the advisor:

> "anything that increase quality and value and enhance the user experiance we should adpot we already created a mehcnaicms for enahmcents . and we already know our personas and all the data we have and creatred many quseitons how the tool should be able to asnwer them we did alomsot evrything"

The advisor's note applies it to the everyday map tools of decision 0065: each is placed as early as its Depends line allows. In a message of the same evening, at about 21:56, the owner wrote of the layer menu (an excerpt; the omitted words name a public map, which this record does not name under rules 15 and 24):

> "it must be user friendly and easy to use now this desin with drop down lsit is not a nice style and there are many functions dont work or not avialable or i press it and notihng happens"

Two readings support the changes. A capability review compared the eight capabilities of decision 0065 with the live screen and this head. It recommended four moves, in order of value to the user: S7-T33, a phone pass split from S7-T34, S7-T30 and S7-T31. It kept S7-T28, S7-T29, S7-T32 and S10-T08 where they are, because they depend on slice S6, S8, S9 or S10 work or lack production evidence. A panel plan found that no task owns a designed layer control: S3-T12 has no control in its acceptance, and S7-T34 and S10-T03 follow the flagship gate. Lead ruling L-2035 item 4 decided two points. The groups are thematic. A source on every row is a second, sequenced part of the panel task, not a cut.

This record makes no claim that any of these capabilities is built, merged or live.

## Decision

1. **S7-T33, coordinates and go-to, moves to slice S3.** Its ID stays, because a task ID is a stable anchor (rule 33; TASKS.md queue rules). Every acceptance criterion stays word for word. Its Depends line, S2-T02, S3-T03 and S3-T12, names only tasks of slices S2 and S3, so it holds in slice S3.
2. **S7-T34, phone layout, is split.** A new task, **S3-T31 "Phone layout of the S3 map screen"**, takes the phone acceptance of S7-T34 for the map screen that is live now. It depends on S3-T09, which already owes the bottom sheet and the eight named sizes (decision 0049; decision 0068 item 7). S7-T34 keeps its acceptance criteria word for word and stays in slice S7 after S6-T37. Its scope becomes the Explore screen and every control added after S3-T31, and it gains S3-T31 as a dependency. No phone criterion is dropped: S7-T34 still checks every map-screen control at phone width.
3. **S7-T30, download of Public rows, moves to slice S3.** Every Public-only, suppression, protected-value and named-entity acceptance stays word for word: Public rows only, with source, licence and retrieval date; no protected value; suppressed or withheld facts download nothing (PRV-85); and every planted category still fails. Its Depends line, S3-T09, S3-T12 and S3-T19, holds in slice S3.
4. **S7-T31, imagery swipe, moves to slice S3.** Every existing acceptance stays word for word. One criterion is added: the capability shows only when the served release holds a verified dated pair of imagery views with their attribution, and otherwise it is absent. Invented test views never become a claim of live imagery, and a planted mode that shows the swipe without a verified pair fails. Its Depends line, S2-T19 and S3-T16, holds in slice S3.
5. **A new task, S3-T30 "Designed grouped layer panel".** It meets the owner's 21:56 item (c). Under the owner's standing approval of 2026-11-25 22:06 item 1, every row carries a short description in English and Arabic, taken only from closed, application-owned catalogue strings keyed by the registry entry; a planted row without a description and a planted description outside the catalogue each fail, and the Arabic strings pass native Arabic review (OWNER_RULES 36) before the task closes. It replaces the native drop-down of the S3 map screen with a designed panel. The groups are thematic: a closed registry field `group` on each listed entry of the S3-T12 layer registry takes exactly four values, one each for economy, land and planning, places, and transport. The panel holds no hand-written list of keys or groups. Document 10's one-hero-layer rule and the `two_hero_layers` guard stay the authority (FE-49). The task has two parts:
   - **Part A:** the chosen row shows its source through the existing source chain of S3-T09.
   - **Part B:** a source on every row through the existing release and source-chain reads of S3-T09 and S3-T24 only, built as the second, sequenced part of the same task and not a cut (lead ruling L-2035 item 4 as amended by L-2038).

   No new source, route or network path. If the existing reads cannot give a row's source without a new route, the task stops as blocked and a new decision record is needed before any route is added; a source is never dropped from a row (OWNER_RULES 9: no value cut).

   The task depends on S3-T12 and S3-T10. S3-T10 already depends on S3-T22 and S3-T24; part B reuses the existing release and source-chain reads of S3-T09 and S3-T24 only.
6. **Gate placement.** S3-T30, S3-T31, S7-T30, S7-T31 and S7-T33 are built and merged in slice S3's order as soon as their Depends lines are met (TASKS.md queue rules). They do not hold the slice S3 gate. S3-T11 excludes them, as it already excludes S3-T20, so the gate date does not change; the intake row of the owner's 22:06 note records no effect on the gate date. S7-T06 keeps all five among its dependencies, so the slice S7 review follow-up and gate still hold them, as they held S7-T30, S7-T31, S7-T33 and S7-T34 before. No gate sentence is changed.
7. **Nothing else changes.** No requirement ID, gate, method, privacy rule, attack size, tolerance or acceptance criterion is weakened (rules 12 and 20). S7-T28, S7-T29, S7-T32 and S10-T08 keep their slices and Depends lines. Decision 0019 item 17 and the provider rules of decision 0065 item 5 are unchanged.

### Depends lines, checked against the cards

| Task | Old Depends | New Depends | Slices of the dependencies | Placement |
|---|---|---|---|---|
| S7-T33 | S2-T02, S3-T03, S3-T12 | S2-T02, S3-T03, S3-T12 (unchanged) | S2, S3, S3 | slice S3 (item 1) |
| S3-T31, split from S7-T34 | none (new) | S3-T09 | S3 | slice S3 (item 2) |
| S7-T34 | S6-T37 | S6-T37, S3-T31 | S6, S3 | stays in slice S7: S6-T37 is the Explore screen (item 2) |
| S7-T30 | S3-T09, S3-T12, S3-T19 | S3-T09, S3-T12, S3-T19 (unchanged) | S3, S3, S3 | slice S3 (item 3) |
| S7-T31 | S2-T19, S3-T16 | S2-T19, S3-T16 (unchanged) | S2, S3 | slice S3 (item 4) |
| S3-T30 | none (new) | S3-T12, S3-T10 | S3, S3 | slice S3 (item 5) |
| S3-T11 | every other task of slice S3 except S3-T20 | the same, and also except S3-T30, S3-T31, S7-T30, S7-T31 and S7-T33 | — | slice S3 (item 6) |
| S7-T06 | every other task of slice S7 | the same, and also S3-T30, S3-T31, S7-T30, S7-T31 and S7-T33 | — | slice S7 (item 6) |

Every Depends line of the moved tasks holds in slice S3. No dependency is dropped, so no task had to stay in slice S7 for that reason.

## Value and limits

The owner gets the coordinates and go-to tool, the phone pass of the live screen, the Public download, the imagery swipe and a designed layer panel before the flagship gate rather than after it. No acceptance is narrowed. The slice S7 gate still holds every task it held before, and the slice S3 gate keeps its wording and its date. The imagery swipe stays hidden until a verified dated pair exists. The panel will truthfully show unavailable layers until the layer data fixes of S3-T12 and S3-T22 land.

Open for the lead: the gate placement of item 6 is this record's reading of the owner's intake row. If the lead prefers that some of the five tasks hold the slice S3 gate, removing them from S3-T11's exception is the whole change; it strengthens that gate and weakens nothing.
