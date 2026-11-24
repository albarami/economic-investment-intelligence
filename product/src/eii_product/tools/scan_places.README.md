# Public places tool

The entry point is `scan_places(store, inputs, context)`. The closed request
holds an area identifier, spine categories, limit and neighbour flag. The
context supplies the token-owning inventory, make-area context, release period,
routing graph identity, reviewed release mapping, route port and complete
expected source chains. No source row is manufactured.

The area is revalidated by `decode_area`. Category-only queries cover its whole
outline; `eii_core.shapes` decides containment. Source lists stay separate.

## Assumptions requiring review

- ASSUMPTION: representative_point is a drawn shape's origin.
- ASSUMPTION: walking except drive is the costing selection.
- ASSUMPTION: origin to place is the route direction.
- ASSUMPTION: release period is the distance fact's period.
- ASSUMPTION: latest verification governs visibility; duplicate remains visible.
- ASSUMPTION: the source release identifies the name/confidence period; the
  check date uses canonical SQL date text without changing precision.

L1 reuses `facts`, `calc.facts` and `source_chain`; no parallel provenance module
or wire schema is introduced. DAT-155 and L8 govern digit-bearing names: emit
verbatim published text or omit the name with its closed flag. Exact rational
origin components provide stable identity independent of area identifiers.

The adapter opens make-area's tile configuration and calls the in-process matrix
API. Fixture answers prove the adapter seam, not real routes or two-engine parity.

Round four D1 withholds neighbours for both flag values. A requested block carries
the closed reason `neighbours_geography_unreleased`; no quotient is emitted or
neighbour query executed. The query pair remains for its contract tests only.
C6 geography in the release (release owner) remains unresolved. Missing release mapping
leaves the secondary block NO_DATA. Unreachable wording, PUB-56 hidden counts
and C6 presence/counts remain with their owning tasks. Full planted-violation and
independent review gates remain required; no acceptance box is ticked.
