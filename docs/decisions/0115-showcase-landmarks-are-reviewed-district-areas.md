# Decision 0115: Gazetteer landmark rows by district members

| | |
|---|---|
| Status | Accepted by the owner, 2026-11-27 ("Accept 0114 and 0115", relayed by the advisor in note owner-relayed-20261127-0822, ruling L-2288), on the different-maker review that stands on main `bc9bb749`: R60-REC.rv2 (Moonshot Kimi through Factory Droid, review mode, a maker other than the builder) APPROVED this record's text (blob `0943ed6e`) with no rejecting finding; its two wording notes were applied as records only |
| Date | 2026-11-24 |
| Owner | The owner |
| Scope | `custodian/publicdata/review/showcase_gazetteer.yaml` rows `landmark:0` to `landmark:3`; `custodian/publicdata/review/flagship_candidates.yaml` row `building:3`; the review loader `custodian/src/eii_custodian/publicdata/places/review.py`; the places stage `custodian/src/eii_custodian/publicdata/places/stage.py`; the hand-over `places/integrate.py` and `frame/live.py`; the review tool `scripts/review_place_keys.py`; [document 03](../03_DATA_CONTRACTS.md) |
| Amends | Nothing until accepted |
| Purpose | Let the four reviewed landmark rows of the showcase gazetteer resolve as boundary-district areas of the licensed boundary archive, so that the live build no longer refuses `gazetteer_missing_source_point` on them |
| Read first | AGENTS.md rules 5, 7, 8, 19, 36 and 46; [decision 0030](0030-frame-grid-by-index-ownership-and-two-nullable-keys.md); [decision 0093](0093-landmark-hand-list-in-one-reviewed-cache-record.md); document 03 |

## Context

The showcase gazetteer review file names four landmarks — Lusail, West Bay,
Msheireb and The Pearl — whose `record_ref` stayed null pending S2-T06. A
key with either half null reports `gazetteer: source point pending` and no
Overture place record or building footprint carries their extents: these are
areas, not points, and no point source the build holds names them.

The licensed boundary archive `bnd_hdx` publishes Qatar's districts as named
polygons, and the source's own district names cover three of the landmarks:
Lusail spans Lusail 69, Lusail 70, Lusail West and Wadi Lusail; Msheireb spans
Mushaireb 3, Mushaireb 4 and Mushaireb 13; The Pearl is exactly the one
district the source names The Pearl. Three of those matches are already
reviewed rows of `district_crosswalk.csv`. The source publishes no district
named West Bay: that row's extent is the lead's reviewed assumption on the
source's zone grouping — the three districts of the Al Dafna zones, Al Dafna
60, Al Dafna 61 and Al Gassar 61 — stated in item 6.

## Decision

1. A `showcase_gazetteer.yaml` row of kind `landmark` may carry the review
   route `source_id: bnd_hdx.district`. Such a row holds a null `record_ref`
   and two further fields: `members`, a non-empty list of distinct district
   keys of the `bnd_hdx` archive, and `member_reason`, a non-empty sentence
   recording why those members are the landmark's extent. The row's internal
   `record_key` is derived, never stored: the sorted members joined by `|`.
2. The four committed rows are filled on this route: `landmark:0` Lusail with
   `QAT001069812`, `QAT001070813`, `QAT003096699` and `QAT001070121`;
   `landmark:1` West Bay with `QAT006060805`, `QAT006061806` and
   `QAT006061810`;
   `landmark:2` Msheireb with `QAT006003776`, `QAT006004777` and
   `QAT006013778`; `landmark:3` The Pearl with `QAT006066765`. Every member
   key is checked against the source's district list; the crosswalk's own
   reviewed matches are reused where they exist.
3. The gazetteer point of such a row is the point on surface of the union of
   its member polygons, the same derivation `administrative_rows` applies to
   each district; it is never moved to a grid cell and it resolves its base
   cell like every other gazetteer point. The stage computes the point only
   where the frame hands over the archive districts, and it checks the stored
   six-decimal point, not the computed one: a stored point the member union
   or the frame boundary does not cover refuses the run.
4. Every refusal on the route is closed: the loader raises
   `landmark_source_refused` (a `landmark` row on a source outside
   `places_ovt` and `bnd_hdx.district`, or non-null member fields on any other row),
   `landmark_record_ref` (a non-null `record_ref` on a district row),
   `landmark_members_empty` (no list, an empty list or a non-string or empty
   member), `landmark_member_duplicate` (a repeated member, and at the stage
   a repeated archive district key) and `landmark_reason_missing` (no reason
   or a blank one); the stage raises `landmark_member_unknown` (a member no
   archive district names), `landmark_member_outside` (a member polygon
   the frame boundary does not cover) and `landmark_point_outside` (the
   stored six-decimal point the member union or the frame boundary does not
   cover). Each refusal is registered in the
   refusal policy and planted in `REVIEW_DATA_GUARD_CASES`.
5. `review_place_keys.py` never proposes for a district row — its derived key
   is never null — and `--check` re-derives the key from the file's own
   members instead of the place-matching path, so it accepts the rows and
   never overwrites them.
6. ASSUMPTION: the source publishes no district named West Bay, and no source
   name settles the landmark's extent. The lead's reviewed ruling takes the
   three districts of the Al Dafna zones — Al Dafna 60 (`QAT006060805`),
   Al Dafna 61 (`QAT006061806`) and Al Gassar 61 (`QAT006061810`): zone 60's
   only district is Al Dafna 60, and zone 61 is the source's Al Dafna -
   Al Qassar zone. Al Gassar 66 (`QAT006066811`) is not taken: the source
   groups it in zone 66, the zone of The Pearl (`landmark:3`), not the
   Al Dafna zones. A reviewer finding a different extent changes `members`
   and `member_reason` only.
7. A `flagship_candidates.yaml` building row the name route leaves ambiguous
   may carry a reviewed choice: `source_id: bldg_ovt`, a non-null
   `record_ref` and a non-empty `choice_reason` recording why that footprint
   is the building. `review_place_keys.py --check` accepts such a row as
   `check=yes basis=reviewed_choice` only when its stored `kind` is
   `building` and its stored `source_id` is `bldg_ovt`, the helper cannot
   re-derive the key, the chosen `record_ref` is text naming a footprint in
   the row's own exact-or-folded name-candidate set, and that footprint is
   inside the boundary set; both the fill run and `--check` refuse
   `reviewed_choice_kind` (a `choice_reason` on a row of
   `showcase_gazetteer.yaml`, or on a row whose stored `kind` is not
   `building` or whose stored `source_id` is not `bldg_ovt`, null included),
   `reviewed_choice_reason_missing`, `reviewed_choice_unneeded` (the helper
   re-derives the key uniquely), `reviewed_choice_not_candidate` (a
   `record_ref` that is not text or is outside the candidate set) and
   `reviewed_choice_outside`. The fill run never writes or overwrites such
   a row. `building:3` is filled on this route.

## Evidence and consequences

- The derived `record_key` keeps every existing seam unchanged: pending
  detection, point lookup by `(source_id, record_key)`, gazetteer row shape
  and lineage bookkeeping all read the same fields as before.
- District point rows join `place_points.json` beside the Overture rows, so
  the live frame resolves them through `_place_points` with no second file.
- Every new refusal is exercised by one dedicated negative test that changes
  one input of a valid case; hostile values on the new leaves refuse, and a
  property test holds member order order-free.
- The route adds no source, no fetched file and no invented attribute: the
  members are the boundary archive's own named districts, and the review
  file records the reason for each set.
