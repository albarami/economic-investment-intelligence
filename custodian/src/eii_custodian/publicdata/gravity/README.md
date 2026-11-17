# Gravity separate-series source

S2-T25 implements `eii_custodian.publicdata.gravity.parse.parse_archive@v1`.
The source page, licence, publisher version, Etalab lead, access state, country
keys and units are NOT READ. Decision 0040 supplies an unverified page lead.
That lead carries a query string and is not stored as a reviewed data URL. No
host has been admitted. `confirmed: false` and `bound_origin: pending` prevent
requests.

`gravity.yaml` is closed. Pending empty metadata and zero bounds are
placeholders, never source facts. Activation requires reviewed URLs, a page
hash, one country member, one bilateral member, source version, attribution
and an evidence reference. Every bound is inclusive. A missing bound fails
closed-schema validation.

ASSUMPTION from invented fixtures, pending the lead: distance allows 9 total
digits and 3 fractional digits; each GDP measure allows 16 total digits and 4
fractional digits. Measures are unsigned fixed-point ASCII. A declared missing
token becomes null. A written zero stays present. Flags are only the configured
tokens `0` and `1`. No HS revision is inferred. Qatar origin or destination
rows are kept after every row, including excluded rows, has been validated.
Missing partners are recorded and are not zeros.

Completion is published last in the caller's uncommitted `cepii_gravity` cache.
`contracts.read_selected` requires an explicit digest. Registration or a paid
tier fetches nothing.

Review repairs (S2-T25): the declared final period must be present even for a
narrower selection; other years remain in excluded coverage. Metadata and terms
acquisition reads at most the configured archive upper bound plus one byte,
then refuses overflow. Upstream exception context is suppressed at conversion.
The manifest records the actual final host; the reader checks that host against
this source's reviewed addresses and reconstructs the receipt with it.
The manifest's `archive_host` binds the final host independently of the receipt;
the registry continues to bind the initial address to its initial host.
