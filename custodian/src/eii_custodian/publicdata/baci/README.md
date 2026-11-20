# BACI separate-series source

S2-T24 implements `eii_custodian.publicdata.baci.parse.parse_archive@v1`.
The lead's supplied page reading of 2026-11-20 confirms the selected HS 2017
edition, release 202601, published period 2017-2024 and "Licence: Etalab 2.0".
Document 04 **S2-T21 part B terms readings** records the page URL and supplied
SHA-256. The supplied licence-link reading identifies the publisher's exact
Etalab PDF link; no PDF text is claimed read here. The supplied byte-range
archive reading records trade header `t,i,j,k,v,q`, both dictionary headers,
`Readme.txt`, the eleven-member inventory and exact compressed/expanded byte
bounds in `baci.yaml`. Its inventory evidence hash is not an archive checksum.
The Readme supplies thousand USD, metric tons and six-digit HS products.
Row counts remain null, to be recorded at the first fetch.

PUB-03 admits `www.cepii.fr` through this reviewed registry change. Every BACI
request and redirect still needs an exact `reviewed_urls` entry. Only the literal
publisher-page query `id=37` has a closed exception; generic query refusal stays.
`confirmed: false` and `baci_metadata_unconfirmed` still prevent requests:
target/country representation, missing-quantity tokens, decimal limits, access
configuration and bounded first-fetch row accounting need lead evidence/work.
Trade input 4 stays pending. These readings are not a complete fetch.

`baci.yaml` is closed: required fields and unknown-field refusal stay. A member
may additionally declare reviewed compressed-byte bounds; existing expanded
bounds always apply. Null counts are accepted only as pending metadata; confirmed
configuration and parsing require bounds for every data member and all raw rows.
A text member must be exactly `Readme.txt`, have no columns/header or row count,
and is fully hashed and byte-checked. Exact native CSV header variants are
supported alongside the existing complete logical schema. Native trade and product
rows obtain HS revision from the reviewed configuration. The country ISO2 column
is validated but not added to the closed release schema. Published code strings
remain unchanged; no country code or padding convention is guessed.

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
