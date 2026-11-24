# Decision 0087: make_area by a returned area identifier

| | |
|---|---|
| Status | Proposed, 2026-11-21: the builder's record for S3-T26 box A5, for the lead's review and the owner's confirmation |
| Date | 2026-11-21 |
| Owner | The owner |
| Decided by | Pending: the lead's review of S3-T26 box A5 and the owner's confirmation |
| Amends | Document 08 section 6.2, the `make_area` Inputs row; document 03 section 9.2, the paragraph before the area record table. Implemented by TASKS.md S3-T26 box A5. |
| Purpose | Let the story draw the wider context area that its `rings` directive names, from the existing BE-86 decode, without vertices in a directive and without a new route, table or read function |
| Read first | Document 08 section 6.2 `make_area` and section 7 `site_check`; BE-86; document 10 section 3.6 Stage directives; AGENTS.md rules 8, 16, 18 and 46 |

## Context

The `site_check` story names its one or two areas in the `rings` directive by
identifier only (document 08 section 7: "Fly targets the headline's `area_id`;
rings names the one or two returned areas. The exact outlines remain in the
corresponding `make_area` step payloads"). A directive never carries vertices
(document 10 section 3.6). The browser therefore holds only the outline of the
area the user chose, and cannot draw a distinct wider context area. BE-86
already fixes that decoding an `area_id` and calling `make_area` again yields
the same units and the same outline, through `decode_area`. The `make_area`
input surface is closed and model-callable (BE-56), so a third alternative is a
material amendment under rule 46.

## Decision

1. **A third input alternative.** `make_area` accepts exactly `{area_id}`
   beside `shape_id` and `pin`: one string in the grammar of section 11.1 and no
   other field. It is validated by the closed schema before any read and then
   dispatched to the existing `decode_area` of BE-86. The answer is the
   unchanged `make_area` envelope; its payload is byte-identical to the payload
   of the original request's answer. "Byte-identical" means the payload only:
   the envelope carries a new call identifier for each call.
2. **Refusals are BE-86's.** A malformed identifier, an extra field, a value
   that is not a string, another release's identifier, a shape identifier of
   another session or seat, and an identifier whose recomputed area differs
   return `INVALID_ARGUMENT` and write no ledger row. A grammar or schema
   refusal reads nothing; another release is refused before any read. A
   well-formed identifier whose point lies off the land answers as the pin
   request it spells does under BE-86's decode (`OUT_OF_SCOPE`, or `NO_DATA`
   where the point has no base cell), with no payload.
3. **Same route and ledger.** The call uses the existing
   `POST /api/tools/make_area` route and its one identifier-only ledger row;
   the area identifier is stored as `area_redacted`, never a coordinate (DAT-149).
4. **Drawing payload only.** The returned outline is geometry, never a fact
   (BE-49); no release table, fixed read function or catalogue entry is added.
5. **The browser's use.** The story requests the outline only for the area
   whose documented role is the wider area and only when it differs from the
   chosen area (document 08 section 7: near, then wider; a drive selection is
   the wider area; a shape has none). The typed client sends exactly
   `{area_id}` and accepts only an `OK` answer whose `payload.area_id` equals
   the request; any other answer draws nothing.

## Consequences

The S3-T24 live two-store query inventory names this input when that proof
closes. No model, provider or `/api/ask` call is added. The Arabic legend of the
ring stays pending native review (OI-09).
