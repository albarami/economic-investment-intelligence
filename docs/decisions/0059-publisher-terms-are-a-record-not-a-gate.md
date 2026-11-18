# Decision 0059: The publisher's terms of a source are a record, not a gate

| | |
|---|---|
| Status | Accepted, 2026-11-18 20:51: the owner approved the change in these words; recorded by the lead |
| Date | 2026-11-18 |
| Owner | The owner |
| Decided by | The owner's decision of 2026-11-18 20:51, under AGENTS.md rule 46, with the owner's words of 20:53 on the public sources |
| Amends | TASKS.md S2-T08 acceptance criterion 2, S2-T19 acceptance criterion 1 (the planted row with no basis of use), S2-T16 (the empty terms text of the busyness provider), S2-T29 acceptance criterion 1 (the planted missing basis) and the slice S2 gate (the same plant); PUB-97 and the busyness passage of section 2 of document 04; the plant list of the announced-project archive in document 03; document 14 slice S2 task lines S2-T08 and S2-T19 (the same plant) and the slice S2 exit list (the same plant); the decision index of docs/README.md |
| Purpose | Make the reading of a source's terms (the terms in the publisher's own words, the date read and the basis of use) a record that never fails a criterion, holds a build back or removes, hides or refuses a source. |
| Read first | [Decision 0026](0026-public-sources-used-in-full-locally.md); [decision 0034](0034-licence-questions-of-public-sources-are-answered-at-a-go-live.md) item 1; PUB-12 of [document 04](../04_PUBLIC_DATA_PACK.md) |

## Context

The pack asked every source of the public build to carry the publisher's terms in its own words with the date read and
the basis of use, and S2-T08 made that a pass-or-fail condition of the public build: a source whose terms reading was
pending, unread or unreadable (a page that answers 403, a terms host that is not on the allow-list, a review not yet
done) held the whole build back from counting as a successful public build. The registry reader also refused a row
with an empty terms text, an empty date read or an empty basis of use.

The owner answered on 2026-11-18 at 20:51: the private records are already excluded by the synthetic data, and
everything else is public. At 20:53 the owner added that every source in the registry is public data that the owner
chose and asked for, needing no permission, terms reading or licence decision, for the owner's personal use (decision
0034).

## Decision

1. **The terms reading is a record.** For version 1 the terms in the publisher's own words, the date read and the basis
   of use are recorded where they are known. A field that is pending, unread or unreadable is recorded as pending, with
   the reason when one is known. It fails no acceptance criterion, holds no build back from counting as a successful
   public build, and removes, hides or refuses no data, source or output.
2. **What the registry keeps.** The terms fields already in the registry stay as they are. An empty terms text takes the
   registry's existing marker for terms not yet read; an empty date read is recorded as pending; an empty basis of use
   is recorded with the basis value `pending`, which no decision record is needed for and which is never committable.
   A value that is malformed rather than missing (an unknown basis, a date that is not a date, a terms review file that
   does not match its rows) is still refused, because it is a typing error and not a pending reading.
3. **What stays.** Every other guard and planted violation stays. No source is switched off, limited in release or
   display, or excluded because of its terms (decision 0026). Only a basis of `dataset` may be committed (decision 0026
   item 5; the slice S2 gate's "no file without a stated licence is committed"). The privacy and number checks, the
   other-maker reviews and the synthetic data for everything private are unchanged.
4. **The plants.** A planted row or source whose terms are pending, unread or unreadable now shows that it does not
   fail: the source is still fetched and its rows are used, and the pending state is recorded truthfully.

## Passages amended

- TASKS.md, S2-T08, acceptance criterion 2: "every Public source in the release carries the publisher's terms in its
  own words with the date read and the basis of use, with no terms-based exclusion" becomes "every Public source in the
  release records the publisher's terms in its own words with the date read and the basis of use, or records each
  field it lacks as pending, which fails nothing; no terms-based exclusion".
- TASKS.md, S2-T19 acceptance criterion 1 and the slice S2 gate, and document 14 slice S2 task line S2-T19 and exit
  list: "a planted registry
  row with no basis of use (`licence_basis`) fails" becomes "a planted registry row with no basis of use (`licence_basis`)
  is recorded with basis `pending`, stays in use and is refused for commit".
- Document 14, slice S2 task line S2-T08: "check the publisher's terms in its own words with the date read and the basis
  of use for every source" becomes "record the publisher's terms in its own words with the date read and the basis of
  use for every source, a missing field recorded as pending".
- TASKS.md, S2-T16: "the build fails while that terms text is empty" becomes "an empty terms text is recorded as
  pending and fails nothing"; document 04, the busyness passage: "and the build fails while that text is empty" becomes
  "while that text is empty it is recorded as pending and fails nothing".
- TASKS.md, S2-T29 acceptance criterion 1: "a planted off-host request, missing basis or missing receipt fails" becomes
  "a planted off-host request or missing receipt fails, and a planted missing basis is recorded with basis `pending`,
  stays in use and is refused for commit".
- Document 04, PUB-97: "a licence different from the registry fails the build until a reviewer records the changed
  metadata under PUB-10" becomes "a licence different from the registry is recorded with the date read, pending a
  reviewer's record of the changed metadata under PUB-10, and fails nothing".
- Document 03, the plant list of the announced-project archive: "missing lineage or terms" becomes "missing lineage",
  with the sentence that a missing terms reading is recorded as pending and fails nothing.
- docs/README.md: this record's line in the decision index.

Every other passage that asks a source to record or carry its terms in the publisher's own words with the date read and
the basis of use (S2-T19, S2-T20, the slice S2 gate, the slice S2 exit list of document 14, PUB-12 of document 04)
keeps its words and reads with item 1: a field not yet known is recorded as pending and fails nothing.

## What does not change

Decision 0026 and decision 0034 are not rewritten; this record narrows no source and changes no gate other than the
passages above. The code of S2-T08 part B makes the build match this record in its own task, the refusals of S2-T16, S2-T29 and
PUB-97 among them. A substituted or tampered terms record with unchanged bytes still fails (an integrity check, not a
terms reading).

## Sources

- The owner's words of 2026-11-18 at 20:51 and 20:53, relayed by the owner's advisor (project records of the run,
  outside the pack).
- TASKS.md S2-T08, S2-T19 and the slice S2 gate, and document 14 slice S2, as they stand on the base branch.
