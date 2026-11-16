# Decision 0048: The shadow clock serves every area

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-16 |
| Owner | The owner |
| Decided by | The owner's words relayed by the advisor on 2026-11-16 at 12:48, applied by the lead's ruling L-710 |
| Amends | Decision 0023 item 2; BRF-97 and the excluded-features row of document 01; ARC-140 and the data-layers row of the stack table of document 02; FE-143 of document 10; DES-57, DES-207, DES-146 and the map row of the design checklist of document 11; the clock entry of the glossary; S3-T16 of TASKS.md; the slice S3 paragraph of document 14; the living-map line of README.md; the accepted-record sentence and the Decision records table of docs/README.md |
| Purpose | Let the clock's sunlight and shadows serve every place where a building height exists, under a measured building cap, instead of one focus district. |
| Read first | Decision 0023 item 2; decision 0035; BRF-97; FE-143; DES-57 and DES-207; S2-T20 and S3-T16 |

## Context

Decision 0023 item 2 kept the clock's shadows to one focus district. The reason was performance and stage risk only: deck.gl marks the shadow of its sun light as experimental, and its cost grows with the number of buildings drawn. Height coverage was not the reason. The height chain of S2-T20 gives every building a height: the recorded height, else the floor count times a stated storey height, else the open 3D building heights, else the 90 m cell mean.

The owner has said that the sunlight and shadow clock must serve every place where someone would use it, not one district. The commercial use comes first: a terrace, a shop front, or a walk in the shade through a summer day.

This record changes documents and the acceptance criteria of a queued task. It claims no implementation, no measured frame rate and no passed gate.

## Decision

1. **Shadows in view, wherever a height exists.** S3-T16 draws shadows for the buildings in view at the zoom where buildings are shown (DES-57), in every area where a height exists. No shadow is drawn for a building without a height. A planted building without a height that casts a shadow fails.
2. **A measured building cap.** The build fixes a building cap from the slice S1 frame-rate configuration, repeated with shadows on. The measurement and the cap are recorded in the task's evidence; this record sets no number. Over the cap, the buildings nearest the view centre keep their shadows, and the view says in words that shadows are limited at this zoom. A planted view over the cap that draws more shadows than the cap fails, and so does one that omits the words.
3. **One setting.** The clock has one setting: its day basis, which defaults to today. The focus-district setting is withdrawn. The shadow criteria of S3-T16 no longer wait for an owner's choice of district.
4. **Estimated heights in words.** Heights are Public estimates (BRF-97). The shadow layer says "estimated heights" in words, and each building's height source and that source's measured error open behind "More evidence". Decision 0035 governs generated figures; heights are Public, so no origin texture is added. The words meet the owner's intent that estimated heights be visible as estimates.
5. **Order of use.** The commercial use is first. Industrial areas and the cities follow from the same viewport rule, with no extra setting.
6. **What does not change.** deck.gl's lighting effect with its sun light stays the method, read first from the current official documentation (AGENTS rule 42), with its experimental status recorded. The scrubber still moves only the sun, the light and the sky, and changes no figure. Buildings are still never extruded by a data value. The light and the sky still follow the clock everywhere.

## Consequences

- S3-T16's shadow criterion is replaced by the criteria of items 1 to 4, each with its planted violation. The frame-rate criterion is repeated with shadows on.
- DES-146 still forbids any shadow or sun-position effect other than the clock's. Only the clock's area limit changes.
- The height work of S3-T16 still waits for S2-T20. This record adds no dependency.

## Amended passages

- **Decision 0023 item 2:** the words "kept to one focus district" are superseded by this record's items 1 and 2. Decision 0023's text is not edited.
- **Document 01, BRF-97:** "sunlight with shadows on one focus district" now reads "sunlight with shadows on the buildings in view wherever a height exists, under a measured building cap (decision 0048)".
- **Document 01, excluded-features row of live shadows:** "sunlight with building shadows on one focus district (BRF-97)" now reads "sunlight with building shadows in view wherever a height exists, under a measured building cap (BRF-97, decision 0048)".
- **Document 02, stack table, data-layers row:** "kept to one focus district" now reads "drawn for the buildings in view wherever a height exists, under a building cap measured with shadows on (decision 0048)".
- **Document 02, ARC-140:** "the shadows of one focus district" now reads "the shadows of the buildings in view wherever a height exists, under a measured building cap (decision 0048)".
- **Document 11, DES-57:** "the shadows of the clock inside its one focus district" now reads "the shadows of the clock on the buildings in view wherever a height exists, under its measured building cap", citing this record.
- **Document 10, FE-143:** the shadow clause, a new sentence on the clock's one setting and the frame-rate sentence follow items 1 to 4.
- **Document 11, DES-207, DES-146 and the map row of the design checklist:** the focus-district limit is replaced by items 1, 2 and 4.
- **Glossary, Clock:** the focus-district clause follows items 1 and 2.
- **TASKS.md, S3-T16:** the Goal, the shadow criterion and the frame-rate criterion follow items 1 to 4; the Requirements add BRF-97 and DES-146.
- **Document 14, slice S3 paragraph, and README.md, living-map line:** "in one focus district" now names the buildings in view.
- **docs/README.md:** 0048 joins the accepted-record sentence and the Decision records table.
