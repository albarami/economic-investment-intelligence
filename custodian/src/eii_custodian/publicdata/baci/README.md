# BACI separate-series source

S2-T24 implements `eii_custodian.publicdata.baci.parse.parse_archive@v1`.
The lead's supplied page reading of 2026-11-20 confirms the selected HS 2017
edition, release 202601, published period 2017-2024 and "Licence: Etalab 2.0".
Document 04 **S2-T21 part B terms readings** records the page URL and supplied
SHA-256; the registry records the ZIP URL and dataset licence. Native columns,
row counts, member inventory, country keys, units, access-state configuration
and reporter reconciliation remain pending. No host has been admitted for BACI.
`confirmed: false` and `baci_metadata_unconfirmed` still prevent requests; the
fetcher requires declared columns and complete archive configuration. The page
reading supplies no archive hash and is not a completed fetch.

The lead must supply the four live steps of the task brief before activation.
`baci.yaml` is closed: every field is required and unknown fields fail. Pending
empty metadata and zero bounds are placeholders, never source facts. Activation
requires the complete yearly member inventory, one country and product dictionary,
reviewed URLs, page hash, source version, attribution and evidence reference.
Each member declares its exact ordered header, header-to-logical-field mapping,
kind, year, inclusive expanded byte and row bounds and optional publisher hash.
A source without a published valuation records `unknown`. Access obstacles stop
before archive requests. Reuse terms alone do not exclude a visitor-readable source.

ASSUMPTION: value and quantity each allow 18 total digits and 6 fractional digits,
chosen from invented fixtures; the lead must verify this against the dictionary.
Only unsigned fixed-point ASCII digits with an optional decimal point followed
by digits are accepted. All written digits count, including leading and trailing
zeros. Exponents, signs, whitespace and nonfinite values fail. Decimal is parsed
from text, without float or rounding; the original accepted string is retained.
Only configured missing-quantity tokens become null, with `source_missing` status.
A source zero remains a decimal string with `present` status.

The archive is streamed into temporary staging; all members are read and hashed
without extracting member paths. Every row, including excluded rows, is validated.
Rows with exporter OR importer equal to the configured target key are retained
once. Raw, selected and excluded counts and year/partner/product coverage are
recorded. Missing cells are not zeros. There is no currency conversion, quantity
fill, classification concordance, portal replacement or cross-source averaging.

Completion is published last as `<sha256>.manifest.json`, alongside hash-named
archive and JSONL output files in the caller's uncommitted `cepii_baci` cache.
Local SHA-256 values are integrity measurements, not publisher authentication.
Old content is never deleted on an interrupted new publication. Unreferenced
content may remain after a failed publication; it is not a complete release.
`contracts.read_selected(cache, selected)` requires an explicitly reviewed digest,
verifies hashes and reparses the whole archive before returning typed rows.
No latest discovery or fallback is supported. S2-T08 receives the selected
manifest, source_registry and fact_lineage; S2-T25 receives versioned dictionaries;
S2-T26 receives the separate trade series, units, coverage and reconciliation note.
No consumer or store loader is implemented here.

Deferred: resumable downloads, scheduled freshness monitoring and independent
archive mirrors. Official library documentation was not read live in this pass.
