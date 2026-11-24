# Decision 0100: The address-search box splits: the place picker stays in S3, the ask bar moves to S8-T16

| | |
|---|---|
| Status | Proposed, 2026-11-23 |
| Date | 2026-11-23 |
| Owner | The owner |
| Amends | TASKS.md S3-T03 and S8-T16 only. It changes no requirement row, no code and no test. It does not amend decision 0023 item A7; it splits where its amendment box is delivered. |
| Purpose | Record the split of the S3-T03 address-search box of decision 0023 item A7: the place-picker half is delivered in S3-T03, the ask-bar half moves to S8-T16. |
| Read first | [decision 0023](0023-ten-additions-and-the-data-rule.md) item A7; [decision 0079](0079-dated-gis-snapshot-and-structured-address-search.md) items 5 and 6; TASKS.md S3-T03 and S8-T16; [decision 0084](0084-public-tenders-in-a-separate-run.md) for the shape of this record |

## Context

The S3-T03 amendment box of decision 0023 item A7 covers two delivery surfaces in one box: "the live address search of the ask bar and the place picker". The place-picker half is built and confirmed: it was built on the slice S3 train (package S3-P4), decided by `web/tests/component/resolve-picker.test.tsx`, and confirmed by a different maker's review (`.overnight/IN/PICKER-REVIEW.md`, CONFIRMED). The ask-bar half is not built and belongs with the context-aware ask bar that S8-T16 owns. The S3-T03 Delivery line records that the split needs a decision record under CLAUDE.md rule 46, so the A7 box stays unticked. This record is that record. Nothing here claims either half is built; this record only fixes where each half is delivered and what each half owes.

## Decision

1. **The split.** The words "the live address search of the ask bar" of the S3-T03 A7 amendment box move to S8-T16; the words "and the place picker" stay with S3-T03. S3-T03's box is met in S3 by the picker half once this record is accepted. S8-T16 gains the ask-bar half as its own box, with the full duties below. The box is not ticked by this record: acceptance of this record only fixes the split; each half ticks on its own evidence.

2. **Each half keeps the box's full duties.** Whichever task delivers a half, that half: goes through the local server with `ESRI_API_KEY` only (OPS-73); shows a result and flies to it; never writes a result to a file, the database, the ledger or a log, and a planted write of one fails; with no key, or offline, only the gazetteer resolves places; and its tests never call the keyed address provider.

3. **The cited rows apply to both halves.** AI-130, FE-142, BE-136, BE-137, TST-249 and OPS-73 keep their full wording for each half; no requirement row is weakened, shortened or moved to another row, and no test, plant or tolerance is dropped or relaxed.

4. **Nothing is dropped and no test is weakened.** The amendment box of S3-T03 is delivered by the two halves together; each duty of the box binds whichever half carries it, and the union of the two tasks' boxes is the whole A7 box. Decision 0023 item A7 itself is unchanged, as are BE-135, BE-136, decision 0079 items 5 and 6 (the offline structured-address reader stays with S2-T51 and S3-T29's deferral), and every requirement the box cites.

## Consequences

- TASKS.md S3-T03 gains an amendment line citing this record: the A7 box is met in S3 by the picker half once this record is accepted, and the box itself stays unticked until the whole box's duties are met.
- TASKS.md S8-T16 gains an amendment box citing this record for the ask-bar half, with the full duties of item 2.
- No acceptance criterion of any task is ticked by this record. The S3-T03 A7 box stays unticked until this record is accepted and the picker half's evidence holds; the ask-bar box of S8-T16 ticks only on its own task's evidence.
- This record changes documents only: no code, test, command, gate or bound changes.

## What would change this decision

- Non-acceptance: if the owner or the lead rejects the split, the A7 box returns to S3-T03 as a single box with both halves.
- A change to decision 0023 item A7 itself would reopen this split under rule 46.

## Sources

- TASKS.md S3-T03 and S8-T16; [decision 0023](0023-ten-additions-and-the-data-rule.md) item A7; [decision 0079](0079-dated-gis-snapshot-and-structured-address-search.md) items 5 and 6.
- `web/tests/component/resolve-picker.test.tsx`, the test that decides the picker half.
- `.overnight/IN/PICKER-REVIEW.md`, the different-maker review that confirmed the picker half.
- Requirement rows AI-130, FE-142, BE-136, BE-137, TST-249 and OPS-73 of documents 09, 10, 08, 12 and 13.
