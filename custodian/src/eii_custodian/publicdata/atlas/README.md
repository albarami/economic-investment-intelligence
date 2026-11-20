# Atlas finished-file source

S2-T25 implements `eii_custodian.publicdata.atlas.parse.parse_archives@v1`.
S2-P18 records dated publisher readings in
`custodian/publicdata/review/trade_publisher_readings.yaml`, linked by the registry.
The current download page and legacy index have different classification/history
statements; neither establishes a selected file vintage or native measure mapping.
The two dataset/index hosts are admitted under PUB-03. File-specific licence,
Qatar key, schema and exact member/count/byte bounds remain pending; a rounded
MB label is not an exact byte bound. `confirmed: false` and `bound_origin: pending`
keep downloads inactive for missing technical metadata. Pending terms alone
refuse nothing under decision 0059.

The configuration names two finished downloads, in order:
`country_product_year`, then `country_partner_product_year`. A rebuild member,
a rebuild grain, or `finished_only: false` is refused. The two downloads keep
separate country and product dictionaries. No concordance is inferred.

ASSUMPTION from invented fixtures, pending the lead: the finished measure
allows 12 total digits and 6 fractional digits and may be signed. A declared
missing token becomes null. A written zero stays present. Qatar selection keeps
a country-product row for the configured key and both directions of a
country-partner-product row, after every row has been validated. A narrower
year selection records the excluded coverage.

Completion is published last in the caller's uncommitted `atlas_complexity`
cache. Both archive hashes are bound in the manifest. Registration or a paid
tier fetches nothing.

Review repairs (S2-T25): the declared final period must be present even for a
narrower selection; other years remain in excluded coverage. Metadata and terms
acquisition reads at most the configured archive upper bound plus one byte,
then refuses overflow. Upstream exception context is suppressed at conversion.
The manifest records the actual final host; the reader checks that host against
this source's reviewed addresses and reconstructs the receipt with it.
Each finished download has unique member names and exactly one country, one
product and one own-grain member. The reader rechecks each configured publisher
checksum as well as both archives' stored hashes, sizes and final hosts.
