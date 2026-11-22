# Decision 0090: Reviewed wholly-outside boundary parts and the required building part set

| | |
|---|---|
| Status | Accepted by the owner, 2026-11-22 |
| Date | 2026-11-22 |
| Owner | The owner |
| Decided by | The owner, 2026-11-22, accepting it as proposed by task S2-P47 under the advisor's ruling of option B(b) |
| Amends | [Decision 0077](0077-overture-footprints-as-the-national-building-table.md) item 2, the sentence "National boundary bounds must fit the PUB-17 frame box"; document 04 PUB-17 |
| Purpose | Admit the reviewed islets wholly outside the frame box without moving the box, and state the required building part set as a rule over the STAC items. |
| Read first | Decision 0077; document 04 PUB-17; the S2-P47 records in PROGRESS.md and OPEN_ITEMS.md |

## Context

Decision 0077 item 2 requires the national boundary bounds to fit the PUB-17
frame box (50.7 to 51.7 E, 24.4 to 26.2 N). The dated `bnd_hdx` municipality
union does not: three of its parts are islets north of the box. The lead's
probes 5, 6 and 7 of task S2-P47, run in the lead's own shell on the real
public cache, gave counts only:

- The boundary union has 95 parts: 92 inside the box, 3 wholly outside it and
  0 straddling its edge (probe 6).
- Of the 512 STAC items of the pinned collection, only items 00384 and 00385
  meet the bounds of the 92 inside parts. Each of their asset addresses equals
  the registered part `url` byte for byte (probe 6).
- The three islets meet only items 00384 and 00385, and no building row of any
  of the three earlier pinned parts lies on an islet (probes 5 and 6).

Probe 7 counted the rows of the three earlier pinned parts:

| Part | Rows | Inside the frame box | Inside the mainland bounds |
|---|---|---|---|
| 00288 | 4,853,827 | 204 | 0 |
| 00384 | 4,905,384 | 400,005 | 399,690 |
| 00385 | 4,883,090 | 123,072 | 123,072 |

Item 00288 lies south of the boundary.

## Decision

1. **Reviewed outside parts (option B(b)); the box is unchanged.** The parts
   are the polygons of the boundary union that the frame step already passes to
   the building producer; the call does not change. A part is inside when the
   frame box covers it, and wholly outside when it shares no point with the box.
   Every other part straddles the edge and refuses
   `national_boundary_outside_frame_box`, even when listed; a part touching the
   edge from outside straddles. This is the intended fail-closed reading of
   granularity: a municipality outside the box that touches one inside it forms
   one straddling part and refuses. Polygons meeting at a single point are
   classified one by one; an outside polygon meeting an inside one at a point
   shares that point with the box and so straddles. Wholly-outside parts are
   admitted only when the committed review file
   `custodian/publicdata/review/national_boundary_outside.json` lists exactly
   their hashes (SHA-256 of each part's normalised two-dimensional WKB) and is
   bound to the pinned `bnd_hdx` snapshot hash. An unlisted outside part or an
   absent file refuses `national_boundary_outside_frame_box`; a listed hash of
   no outside part, or a file bound to another `bnd_hdx` hash, refuses
   `national_boundary_review_stale`; a malformed file, or a hash listed twice,
   refuses `national_boundary_review`. An empty or invalid boundary, or one with
   no inside part, refuses `national_boundary_outside_frame_box`. The guard and
   the lead's step that writes the real file use one shared split-and-hash
   helper.
2. **The required part set is a rule.** The required building parts are the
   assets of the STAC items whose bbox meets `in_box_bounds`, the bounds of the
   inside parts. The guard's per-item test uses `in_box_bounds`, not the bounds
   of the whole union; an item meeting only an islet, or lying wholly outside
   `in_box_bounds`, is not required. The pinned part set must equal the required
   set, or the build refuses `bldg_ovt_part_set_incomplete`. On the pinned
   collection the measured result is {00384, 00385}, so part 00288 leaves the
   fixed part list. Its part row stays registered with the skip reason
   `not_required_part_decision_0090`, so no build fetches it, and it leaves the
   large-intake key list; its STAC item row stays.
3. **Evidence.** The per-part table and the counts of the Context section are
   from the lead's probes 5, 6 and 7 of task S2-P47, as recorded there.
4. **Rows of part 00288.** The 204 frame-box rows of part 00288 lie outside the
   boundary, so they never entered any output; the producer counted them as
   `inside_box_outside_boundary`.
5. **Value lost.** No building row inside the boundary is lost. About 4.85
   million rows of part 00288 are no longer read in each build.
6. **Manifest.** `boundary_bounds` keeps the bounds of the whole union. The new
   `boundary_scope` block holds `in_box_bounds`, the outside-part count, their
   sorted hashes, the review file's SHA-256 and the rule sentence of item 2.

## Amended anchors

- Decision 0077 item 2: a pointer to this record.
- Document 04 PUB-17: the guard sentence and the original concrete extract.

## Evidence and remaining confirmation

The builder's tests use invented boundaries and fixtures only. The real review
file is written by the lead from the real cache with the shared helper and
committed after review; until then a real build with outside parts refuses
`national_boundary_outside_frame_box`. This record claims no live national
coverage.

## Acceptance

On 2026-11-22 the owner, asked what waited on him, answered of this record
as written: "I accept". The acceptance is recorded after the merge of the
pull request that carried the record, as the next records change; no rule,
check, test or bound changes with it.
