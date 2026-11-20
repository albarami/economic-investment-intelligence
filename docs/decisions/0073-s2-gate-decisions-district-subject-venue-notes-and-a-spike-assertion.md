# Decision 0073: S2 gate decisions on district subject, venue closure notes and a spike assertion

| | |
|---|---|
| Status | Accepted, 2026-11-20; the owner's decision of 2026-11-20 |
| Date | 2026-11-20 |
| Owner | The owner |
| Decided by | The owner's S2 gate answers of 2026-11-20 on OI-102, PO-S2-116 and S2-T44 criterion 5, relayed in package P26 |
| Amends | [OPEN_ITEMS.md](../../OPEN_ITEMS.md), OI-102, PO-S2-116 and the PO-S2-118 disposition; [TASKS.md](../../TASKS.md), S2-T17 and S2-T44; [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md), section 9.1 and open points; [08_BACKEND.md](../08_BACKEND.md), decision 0019 open points; [09_AI_ASSISTANT.md](../09_AI_ASSISTANT.md), subjects and decision 0019 open points; [docs/README.md](../README.md), decision index |
| Purpose | Close three slice S2 gate questions: the district subject of Public series forecasts, whether venue visits carry a separate closure-status column, and whether one node-test assertion change in pull request 104 is accepted |
| Read first | OI-102, PO-S2-116 and TASKS.md S2-T44 in [OPEN_ITEMS.md](../../OPEN_ITEMS.md) and [TASKS.md](../../TASKS.md); lead ruling L-1141; documents 03 section 9.1, 04 venue visits paragraph, 08 and 09 open points; PROGRESS.md S2-T44; pull request 104 |

## Context

The slice S2 gate groups three owner answers given on 2026-11-20 after the advisor's
recommendations were put to him. OI-102 asked which subject carries a forecast of a
Public series on district geography, especially property prices by district. Documents
03, 08 and 09 carried the same lead assumption pending owner confirmation. PO-S2-116
asked whether `pub_venue_visits` should gain a separate closure-status column after
lead ruling L-1141 admitted nine published note cells as reviewed missing values of the
`number` field. S2-T44 criterion 5 forbade assertion, plant, layer-count and
committed-evidence changes; pull request 104 merged a readiness fix that changed the
node test's expected listener-removal list because the fix removes an idle listener the
old test still expected.

This record is documents and closure only. It claims no new implementation, no changed
bound or limit, and no passed gate.

## Decision

1. **District subject of Public series on district geography (closes OI-102).** The
   subject of a forecast of a Public series on district geography is the publisher's
   own district label with its municipality: the `district` subject, Public slots only,
   never a drawn area, never apportioned and never an `area` subject, and adding no
   attribute to a real place. Property prices by district, method card C41, the
   financial-centre firm count by district (AI-137) and every other Public series on
   district geography use the same subject once its source table exists.

   The owner's answer, quoted word for word:

   > for number 7 i agree to your reoemndation

   The recommendation he agreed to: a district forecast takes the publisher's own
   district label as its subject (Public only, never apportioned).

2. **No closure-status column on venue visits (closes PO-S2-116).** The nine published
   note cells of the museum-visits table stay reviewed missing values under lead ruling
   L-1141: counted in missing-measure coverage, never stored as zero and never stored
   as a number. Document 03 keeps `value int` and adds no status column. Closure or
   restricted opening is not stored as a separate fact.

   The owner's answer, quoted word for word:

   > for 11 keep dfefualt

   The default he kept: the nine published note cells of the venue-visits table stay
   reviewed missing values; no status column is added.

3. **One recorded exception to S2-T44 criterion 5 (disposes PO-S2-118 and ticks the
   criterion with the exception named).** The node test's changed expected
   listener-removal list in pull request 104 is accepted as the one recorded exception
   to the literal no-assertion-change criterion. The change records a listener the fix
   now removes. No bound, time limit, retry, skip, layer count, plant or committed
   evidence changed; no browser assertion was weakened.

   The owner's answer, quoted word for word:

   > for 12 i agree

   The recommendation he agreed to: pull request 104 changed one assertion (the node
   test's expected listener-removal list) where the criterion said no assertion changes;
   the change is accepted by this recorded amendment.

## Consequences and change triggers

Documents 03, 08 and 09 replace their OI-102 assumption lines with the decided rule of
item 1, citing this record. S2-T17's acceptance criterion that fixes the district
subject is ticked when this record merges. S2-T44 criterion 5 is ticked with the
exception of item 3 named in the task entry and delivery line. PO-S2-118's proposed
S2-T44 closure is adopted through this disposition, not through a separate item
heading. A different district subject, a stored closure status, a further assertion
change without a new decision, or any raised bound or weakened check requires a new
decision record under rule 46.

## Sources

- The owner's S2 gate answers of 2026-11-20 on OI-102, PO-S2-116 and S2-T44 criterion
  5, supplied in package P26 with the advisor's recommendations.
- [OPEN_ITEMS.md](../../OPEN_ITEMS.md), OI-102 and PO-S2-116; lead ruling L-1141;
  [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md), venue visits inventory paragraph;
  [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md), `pub_venue_visits`; TASKS.md S2-T17,
  S2-T44 and S6-T14; PROGRESS.md S2-T44; pull request 104.