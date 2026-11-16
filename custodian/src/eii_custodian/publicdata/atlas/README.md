# Atlas finished-file source

S2-T25 implements `eii_custodian.publicdata.atlas.parse.parse_archives@v1`.
The source pages, licence, native revision, available history, access tier and
units are NOT READ. Decision 0040 supplies unverified page leads. No host has
been admitted. `confirmed: false` and `bound_origin: pending` prevent requests.

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
