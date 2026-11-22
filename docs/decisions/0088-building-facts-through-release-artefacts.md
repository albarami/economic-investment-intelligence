# Decision 0088 — Building facts through release artefacts

| | |
|---|---|
| Status | Proposed by task S3-P1b D0; review owed |
| Date | 2026-11-22 |
| Scope | S3-T16, Plan 4 sections 2 and 3; ruling L-1439 |

## Context

Heights are asset-pipeline outputs, not release tables. Plan 4 section 2 closes
the shared Fact chain before any building reader or renderer consumes it.

## Proposed decision

1. Both release kinds, including `public_only`, may list the six building files
   as manifest artefacts with SHA-256: `heights.json`, `manifest.heights.json`,
   `manifest.buildings.json`, `buildings_contributors.json`,
   `artefacts/buildings/buildings_3d.geojson` and `manifest.pack.json`.
   P0a owns contributor membership and method-version production; P0b owns
   packing, assembly and installed-release byte verification.
2. The closed lineage link is `table` or `artefact`. The latter resolves
   fact → release artefact → method and version → source, licence, retrieval
   date and hash. This proposes a narrow amendment to AGENTS.md/CLAUDE.md
   rule 19 and document 07 MTH-08 for manifest artefacts; their table rule
   remains binding for table facts. The pending amendment is recorded in both
   agent files together; no proposed decision is represented as accepted.
3. C47 (MTH-125) is the building-height method. This proposal fixes its
   `method_version` to `v1`; P0a writes it in `manifest.heights.json`. The
   selected producer method and version are carried unchanged; a blank
   version refuses. This is a proposed version contract, not a claim that the
   current producer writes it. B3a owns the height metric key.
4. A building Fact uses `kind: public`, `public_code: building:` followed by
   its canonical building ID unchanged. It is Public, has input classes
   `[public]`, unit `metres` and status Observed for recorded heights or
   Inferred for fallbacks. B3a validates the canonical ID and installed-release
   binding, with `building_geography_mismatch` and `building_release_changed`.
   The existing Observed-only `cell:`/`feature:` rules remain unchanged.
5. Drawing is separate from the exact decimal Fact channel. P0b's drawing
   domain is canonical hundredth-metre text from 0.01 through 9999.99;
   half-up rounding of the binary64 and binary32 forms must recover the input.
   Producer-valid heights above the bound retain their Fact, draw flat and
   cast no shadow. P0b owes the whole-domain Decimal oracle.
6. Retain DES-57's exact legend sentence, “Building heights are estimates.”
   The WSF credit is document 04's attribution-table sentence:
   “Building heights: WSF 3D, German Aerospace Center (DLR), CC BY 4.0,
   retrieved {date}. Heights are estimates.” Its Copyright DLR notice,
   landing-page link and fallback modification notice remain mandatory.
   `terms_words` is never substituted for credit. Publisher text stays
   verbatim in both languages; numerals use reference chips.
7. The two future fixed readers are
   `eii_product.api.building_heights.read_aggregates` (verified height manifest)
   and `eii_product.api.building_heights.read_building` (canonical map-returned
   ID, installed release, verified exact heights). B3a implements them through
   Fact validation; no D0 reader implementation or rendered-height claim.

## Evidence and consequences

Plan 4 sections 1–4 and 6; CF2-RETURN finding CF2-N1; document 03 section 9;
document 04 attribution table; document 07 C47/MTH-125; DES-57.
D0 uses one explicit legacy table-wire adapter and a coordinated release-summary
inventory migration. Every existing refusal assertion and reason remains.
The drawer's artefact row is B3a's work; D0 shows no manufactured table.
The `gba_calibration` block remains comparison evidence behind “More evidence”,
explicitly outside the height order (OI-310); D0 changes no producer order.
The document 03 schema omits the validator's existing cell/feature namespaces;
D0 adds only building and records the prior difference in OPEN_ITEMS.md.

## What would change this decision

Another reviewed decision is required for another link kind, geography,
drawing domain, producer method, or legend wording. Review and acceptance are
owed; no S3-T16 acceptance box closes through this proposal.
