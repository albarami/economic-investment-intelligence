# Company web pages (S2-T48)

Authority: decision 0076, the owner's decision recorded in decision 0074 item 8,
and the lead's S2-T48 design-review rulings. This is tooling only. It creates no
product or release table. Offline fixtures establish guards, never live acceptance
criteria 1, 2, 4 or 7. No real provider, company, page, register value or fetched
selector is committed. Provider selection/verification and live evidence remain
with the lead, after S2-T36's live capture. No library pin changes or new external
API is used; parsing uses the existing HTML tree and Python standard library.

Only the lead operates `./eii build-public --company-web`. Ordinary build-public
excludes the family, including at the shared `run_build` seam. There is no second
HTTPS opener, shell interpolation, model extraction, browser automation, keyed
provider, retry, capture bypass or selection of the latest archive.

## Inputs and stages

The closed environment selector `EII_COMPANY_WEB_STAGE` is `inventory`, `search`,
`fetch` or `review`. `EII_COMPANY_WEB_RUN_ID` is a lowercase letter followed by at
most thirty-nine lowercase letters or hyphens. All stage artifacts live under
`data/public_cache/company_web/runs/<run-id>/`. `selection.json` is a convenience
receipt only; later stages require explicitly selected hashes from the lead.

`input_companies` reads the public-register CSV through `EII_REGISTER_FILE` in the
lead's shell, never the owner's workbook. Its declared columns are
`company_name`, `registration_number`, `licence_number` and optional public
`address`, `website`, `activity`; other columns, duplicate headers, malformed rows
and missing/ambiguous keys refuse. This is a narrow adapter shape, not a claim
that the lead's unread real file has that shape. Registration and visibly prefixed
licence keys are hashed in separate namespaces. No number is guessed or enriched
from an ambiguous match. The financial-centre input calls `fc_register.names.contribution`
to verify its pinned complete capture, then uses one company name per row of the
same selected page, preferring its published primary name to its alternate name.
Its tooling identity is a hash of the source and name, never a registration or
establishment number. An absent number remains absent.

Input names receive only nonempty-string, control-character and query-metacharacter
checks. Ordinary trading words do not bar a register name from search. A refused
input stays in the company denominator as `input_refused`, sends no request and
has no pages or fields; other companies continue. The inventory records this
derived flag. Extracted values, reviewer bundles and retained names still receive
the full person, contact and identifier guard.

`inventory` archives those company inputs for the lead to select a batch. It
opens no source connection and needs no host manifest. Its cached company keys
are used to construct the batch manifest. `search` and later stages select only
the manifest's batch: one to ten companies, at most three result pages each.

The other stages require `EII_COMPANY_WEB_MANIFEST`, pointing inside
`data/public_cache/company_web/input/`, and `EII_COMPANY_WEB_MANIFEST_SHA256`, the
SHA-256 of its exact bytes after the lead reviews it. Those exact bytes are
retained in the immutable `company_web/manifests/` archive; the manifest hash
in later artifacts is this byte hash. A separate canonical-content hash detects
in-memory changes. JSON properties are unique.
The manifest's closed shape is:

- `version`: the integer one.
- `reviewed_by`: nonempty `maker`, `tool`, `model`, `run_id`, identifying the
  lead's deterministic extraction run. This identity is frozen into each page
  receipt and candidate. These are tool/model identifiers, never personal names.
- `reviewed_utc`: a UTC timestamp.
- `provider`: one `host`, `path`, closed simple `result_selector`, `attribute`
  equal to `href`, and `visitor_readable` and `keyless` both true. The lead must
  verify one visitor-readable provider's request/response structure and terms
  before live use; configuration alone is not evidence of that verification.
  Requests are HTTPS GET with exactly `q = company name + " Qatar"`, built by
  `canonical_https` and checked by `approve_closed`. Results retain direct HTTPS
  addresses only; the declared provider must return that shape. Wrapped redirect
  links and undeclared query selectors refuse rather than being guessed.
- `companies`: each selected tooling key maps to an exact list of approved page
  URLs (empty during initial search if not yet known). The fetch manifest is
  reviewed again after search and may only choose addresses bound to that
  company in the selected search record.
- `access`: exactly the provider and selected page hosts, each with `terms_url`,
  `robots_url` and `delay_seconds` at least two. Terms and robots URLs are empty
  only after the lead establishes "none found"; otherwise they are same-host
  exact HTTPS addresses and the robots path is `/robots.txt`. Dated records and
  fetched bytes stay in the cache. Unread reuse terms are recorded and remain
  usable; access obstacles stop the host. Robots rules are enforced and a slower
  crawl delay is honoured. Tests inject time and refuse a sleeper that does not
  actually advance it. Real use supplies the real monotonic clock and sleeper.
  Robots rules apply before the search request as well as before company pages;
  a disallowed search stops that host and counts `search_obstacle` per company.
- `selectors`: an empty object or a per-host mapping with exactly `block` and
  `fields`, using the existing closed simple-selector syntax. Fields are only
  name/address/website/activity, with name required. This entire declaration is
  covered by the manifest's reviewed hash; nothing is inferred from an arbitrary
  page. Selectors never combine with a structured block on the same page.

`fetch` also requires `EII_COMPANY_WEB_SEARCH_SHA256`, the chosen search snapshot
hash. The same company and request bindings are rechecked before any page opens.
The manifest has a scoped exact-URL frame; its contexts only narrow a parent
frame and always reset on exit. Redirects, final addresses and injected responses
are checked too. Static `allowlist.approve` is unchanged and streams cannot use
the company scope. Credentials, headers and postbacks are refused in that scope.
IP-literal, localhost (including its subdomains) and single-label hosts are refused
before manifest admission. The final host label must be alphabetic or punycode;
legacy shortened, octal and hexadecimal numeric IPv4 spellings are refused too.
Selector lookup uses the parsed, lowercase host,
including when a URL spells an explicit default HTTPS port. Manifest containers
are type-checked before their properties are read; malformed inputs use the fixed
refusal diagnostic.

Every complete fetched company page, including a no-block or mixed-content page,
is stored in full through the shared immutable snapshot archive, with its original
and final addresses, retrieval UTC, complete-byte SHA-256, publisher, local-use
licence/basis, decision record, method and extraction identity. A fetched obstacle
body is archived before that host stops. An unsuccessful connection has no body
and is recorded as unavailable. A partial publication has no valid snapshot
index; readers require the explicitly selected identity and recheck bytes and
receipts. Search response bodies/snippets are never archived.

## Extraction, review and evidence

`parse.extract` reads declared schema.org Organization/LocalBusiness JSON-LD or
microdata, or the manifest's reviewed selector. Duplicate JSON properties,
personal contexts, multiple blocks and foreign vocabularies are refused or
unmatched. It uses `award_checks.normalise_name` unchanged. Legal-suffix variants
are ambiguous, never aliases. Address components are PostalAddress source text;
activity is source `isicV4`, `naics` or description text, never mapped to a spine.
Absent fields remain absent. Web fields are separate candidates, with conflicts
against register-published fields marked; no register field is overwritten.

The archived reviewer bundle holds the matched company name, the selected source
block before field assembly, page/fragment hashes, source address, parser and
proposed fields. For JSON-LD this is the canonical serialization of the parsed
Organization/LocalBusiness object, retaining separate PostalAddress parts and
activity source properties. For microdata or a reviewed selector it is the
serialized selected source subtree, including context outside the field nodes.
Personal contexts and forbidden source values refuse the fragment. It excludes
register keys, rows, files and values of conflicting register fields. Each proposal
includes an opaque `candidate_digest` and `value_sha256`, so another-maker decisions
bind exactly without receiving a register key. A re-dump of assembled candidate
fields is refused as a fragment, including when its hashes are recomputed. The
fragment never replaces the archived full body; its hash is distinct from the
full-page hash.

A declared block with a telephone, fax or e-mail property is refused in full at
extraction, even when that property would not become a candidate. A reviewed
per-host selector can narrow the source block; live coverage remains for the lead
to measure. If a reviewer bundle is refused, fetch records `field_refused` with
no candidate digests or bundle identity. Review repeats extraction and bundle
validation inside the same refusal boundary, preserving the counted refusal
without aborting the batch.

The reviewer returns records keyed by `candidate_digest`. Each record has exactly
`candidate_digest`, `field`, `value_sha256`, `page_sha256`, `fragment_sha256`,
`parser`, `extractor_sha256`, `reviewer` (maker/tool/model/run_id) and `decision`
(`accepted`, `rejected`, `pending`). `review.record` constructs this same schema.
Only the lead operates the separate-maker session and records its actual identity
in PROGRESS.md; labels alone cannot authenticate a maker. The code rejects empty
identities, same-maker labels after case/space folding, reused session IDs and
any changed binding. It adds no cryptographic signature or receipt format.

`review` requires the same fetch manifest, `EII_COMPANY_WEB_SEARCH_SHA256` and
`EII_COMPANY_WEB_FETCH_SHA256`. Optional `EII_COMPANY_WEB_REVIEWS` and
`EII_COMPANY_WEB_REVIEWS_SHA256` select the reviewed decision file inside the
input directory. Omission keeps every field pending. It rereads each named full
snapshot and reruns deterministic extraction; supplied candidate values never
stand in for those bytes. Orphan reviews and omitted/duplicate outcomes refuse.
Only accepted fields enter the retained output. Retained names produce a
`name_inventory.Contribution` for the existing SYN-20/DAT-14 collision checks.

E1 is the search record (company/request bindings and outcomes); E2 is the reviewed
manifest and full-page receipts; E3 is the fetch record's proposed/missing/refused
field audit; E4 is the review record and exact identities; E5 is the matching
outcome per page. The review snapshot carries E7 counts for every company/search,
page, archive, obstacle/unavailable outcome and field state, plus conflicts and
missing slots. A block refusal counts refused slots, not invented field values.
Its explicit search/fetch identities link the complete chain. E6 is the lead's
unchanged repository scanner exits. Commit only safe metadata and counts; all
real details and reviewer bundles stay cached. Refresh cadence is unconfirmed.
