# Decision 0116: Showcase venue selection by reviewed district union

| | |
|---|---|
| Status | Accepted by the owner, 2026-11-27 ("ACCEPT 0116, 0117, 0118, 0120, 0121 and 0122", relayed by the advisor in note owner-relayed-20261127-060429), on the lead's confirmation (ruling L-2272) that its review still stands on main `bc9bb749`: the record's text is byte-equal to its text at `247c6dc` (S2-DREC.fx1), which S2-DREC.cf2 (Cursor, grok-4.7-high, a maker other than the builders) CONFIRMED; S2-DREC.rv1 (Devin) found the same text at `d975159d` ready for acceptance |
| Date | 2026-11-25 |
| Scope | PUB-101 build-time venue selection; PUB-52; document 04, Open questions and assumptions, notes 4 and 17; review-U7 Inputs item 2 and the U7 HOWTO |
| Amends | Proposed amendment of PUB-52's area-definition sentence and document 04, Open questions and assumptions, notes 4 and 17; review-U7 Inputs item 2's `in_build_time_list` explanation and the U7 HOWTO. Nothing is accepted by this record's publication. |
| Purpose | Distinguish reviewed district-member showcase venue-selection extents from showcase walks used for place verification |
| Read first | [Decision 0115](0115-showcase-landmarks-are-reviewed-district-areas.md) items 1 to 6; [document 04](../04_PUBLIC_DATA_PACK.md) PUB-52 and PUB-101, Open questions and assumptions notes 4 and 17; [documentation index](../README.md), Identifiers and change control item 5 |

## Context

Decision 0115 proposes the district-member route for landmark gazetteer rows
and their point derivation. It does not amend PUB-52's walk definition. This
record proposes the separate PUB-101 venue-selection rule from the supplied
S2-U7D2 design review, Item 3, while retaining the verification scope. Decision
0115 remains Proposed; this record does not accept it or authorize the changed
membership definition before review and acceptance.

## Decision

1. For PUB-101 build-time venue selection only, a `showcase_gazetteer.yaml`
   landmark row whose `source_id` is `bnd_hdx.district` uses the union of its
   reviewed `members` polygons from the hash-bound licensed `bnd_hdx` archive
   as its showcase venue-selection extent, with `member_reason` retained,
   including the reviewed West Bay assumption of decision 0115 item 6. A named
   kept place belongs to that extent exactly when the union covers the point
   stored for that place in the hash-bound `places_s2_t06/pub_place.jsonl`;
   boundary points count and points in polygon holes do not. Every member must
   be known and covered by the frame boundary, and duplicate members or archive
   district keys refuse under decision 0115 item 4.
2. Other showcase venue-selection extents remain the ten-minute walk polygons
   defined in `showcase_areas.yaml`; the PUB-89 branch remains a nonempty exact
   place link to the same kept table.
3. Amend PUB-52's area-definition sentence to read: “For place verification,
   each showcase area is defined in `showcase_areas.yaml` by a pin at a named
   public landmark and the ten-minute walk area from it; for PUB-101 build-time
   venue selection only, a district-member landmark instead uses the reviewed
   member-district union in `showcase_gazetteer.yaml`, and other showcase
   definitions keep their walk extent.” Retain PUB-52's verification sentence
   and its walk-margin assumption for verification.
4. Replace document 04, Open questions and assumptions, note 4 with: “PUB-52:
   for place verification a showcase area is the ten-minute walk area from a
   named landmark pin; for PUB-101 venue selection a district-member landmark
   uses its reviewed member-district union, and other showcase definitions use
   their walk extent.” Read note 17's showcase-area branch on that same
   venue-selection basis.
5. Replace review-U7 Inputs item 2's `in_build_time_list` explanation with:
   “boolean: a named kept venue whose stored point is covered by a reviewed
   district-member showcase union or another showcase's reviewed ten-minute
   walk polygon, or a PUB-89 venue with a nonempty exact link to that kept
   place.” Use that same definition in the U7 HOWTO.
6. A district union is never described as a walk. This selection rule changes
   no place attribute, place deduplication, shown-place decision,
   required-verification population, flagship walk, completeness result,
   provider request limit, allowance rule or privacy rule; empty showcase walk
   definitions remain valid but do not establish completed showcase
   verification.

## Evidence and limits

The supplied S2-U7D2 design review, Item 3, is the source of the numbered
wording above, split into separately testable items without changing its
sentences. Its Items 1, 2 and 4 distinguish the existing district-point route
from the proposed venue-membership rule and record remaining implementation
and evidence gaps. This documents-only proposal claims no implementation,
runtime proof, completed verification, U7 acceptance or live-run acceptance.

## Consequences

PUB-52 and document 04's notes distinguish venue selection from verification,
with the proposed amendment cited explicitly. No refusal code, check or source
is added or changed. The U7 review and HOWTO wording is specified by item 5;
this record alone is not evidence that those separate materials were updated.

## What would change it

A change to the membership definition or the unchanged scopes in item 6 needs
its own reviewed amendment under the documentation index's Identifiers and
change control item 5. This record was accepted by the owner on 2026-11-27 (see Status).
