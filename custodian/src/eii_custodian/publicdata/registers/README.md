# Register file projections (S2-T49)

This is an offline, lead-operated adapter for decision 0022 item 1, document 03
sections **7.2 Table catalogue** and **7.3 Columns**, DAT-83 and DAT-164, and
document 12 TST-196. Automated tests use invented UTF-8 CSV bytes only. No module
here fetches a register, searches for a private file or copies raw input into a
cache. No release command placeholder is implemented by this task.

`build.build(output, release_kind, frame, current, snapshots)` publishes the same
validated `pub_register_company` and `pub_register_snapshot` projections for
`public_only` and `protected`. The receiving release builder consumes both tables
and the manifest together, checks their hashes and uses the manifest's exact
source key and period to resolve lineage. It must also run its own full-release
schema and privacy checks; this module does not implement those checks. The
future release-builder call site remains with its owner.

`contracts.SCHEMAS` is the schema-only lead contract: column list, declared
lexeme type and value format for each of the four CSV roles. The commerce
source also requires the two `HEADER_ONLY` column names at intake; they are
absent from registry and release schemas and their values are dropped before
lexeme validation (ruling L-1304). CSV scalar lexemes
are validated as strings. The release projects capital to a non-negative BIGINT
in QAR and coordinates to finite DOUBLE values; other declared card fields keep
source strings, preserving leading zeros and publisher spelling. Dates must be
calendar dates in ISO format. Only an events `notice_expiration_date` matching
`[0-9]{2}-[A-Z][a-z]{2}-[0-9]{3}` becomes null without parsing or guessing;
`field_absences` counts it under `published_non_iso_notice_shape` with source,
period and current/snapshot use. Every other non-ISO shape refuses.
Empty optional fields become null; required fields
do not get default values. Categories whose values have not been declared by
document 03 remain open text, tested with invented, previously unseen values.
The tax flag accepts exactly lowercase `yes` / `no`; `Yes`, `No`, `YES`, empty
and `y` refuse. Source spelling is preserved, never normalised into that set.

The commerce projection preserves its declared card fields except internal
the standalone `row_key`, the extra `nationality_group` fields, derived
`points_at_location` and `licence_number`. Licence numbers are validated only
at intake and never appear in a release table, manifest or report.
The extra nationality-group columns are header-checked and dropped; internal
row keys and location counts are validated but never released. The
financial-centre projection
maps `qfc_number` to `registration_number`, preserves its published names,
registered address and licence status, and preserves at most one published
notice and its complete date. Under [decision 0117](../../../../../docs/decisions/0117-financial-centre-event-selection.md)
(proposed), fully identical repeated events rows collapse (item 1); otherwise the
row with the later parsed notice date wins, and a dated row wins over an undated
row, deterministically in either input order (item 2). If the winning date group,
or the undated group of a company with no dated row, holds differing rows, that
company's event and notice date are null instead of refusing the register (item 3).
`field_absences` counts one `event` / `published_event_conflict` absence per
company. A conflict on an older date does not block the later row or add a count.
The geocoded companion contributes coordinates
and the frame-resolved cell only. Internal order and row keys, inferred building
names, matched-place labels and match quality never become card facts. A tower
field needs confirmation that it is published on the card before it can be
added. Source-inapplicable columns are null and cannot be filled by the other
source's schema. No worker, residence, owner or person column is accepted.

DAT-11 scans every string column, including non-key address strings.
Under proposed decision 0123 (option C1, awaiting the owner's choice), every
published non-key value and column name meets that row's own company's licence
numbers plus every withheld duplicate registration. A row without an entry in
the licence map meets only the withheld duplicates. The closed typed-column
rule applies to that same per-row set. A coincidental match with another
company's licence is published; a released registration is still published.
The ephemeral map is built beside the intake licence set, keyed by the released
registration or existing `ROW-` identity, and unioned across current and historical
captures before their full cards are scanned. Neither map nor licence value is
exported. Key slots, the returned released-key set, metadata key sets and the bundle
loader's no-input-only-key call remain unchanged; so does decision 0119 item 6.
Typed capital, coordinates,
counts and cell keys are not identifier strings. Artefact token rules are retained,
with the fixed metadata exemptions below. Under decision 0119 item 6, a
digest-shaped string is exempt from the token and
content scans as the value of a named digest field (`contracts.DIGEST_FIELDS`:
the document-03 release columns that hold a SHA-256 and the manifest's frame,
receipt, receipt-file and table digests), which must be 64 lowercase
hexadecimal characters or refuses `digest_field_format`; every other string is
scanned even when it looks like a digest.
The 2026-11 floor applies only to kept snapshots. Each snapshot is compared with
its own source's current capture; current retrieval months may differ and may
predate the keeper floor.

The ephemeral per-company licence map protects non-key released fields,
including numeric values. The complete intake licence set still protects
manifests/reports, with decision 0124's exact-field exemptions below. Neither is exported. The dedicated key exemption is
unchanged: an intake licence equal to a published registration passes because
no licence field is released and the key slot meets withheld numbers only. An own-company
licence or withheld token in a non-key field still refuses; a released
registration token there is published (decision 0119). Under decision 0105 (proposed), the closed typed-field list
`contracts.TYPED_FIELDS` (the five ISO dates, `zone`, `street_number`,
`block_en`, `block_ar`, `lon`, `lat`, `capital_qar`, the tax year and the yes/no
tax flag of `pub_register_company`, the list's `employee_count`, and the
manifest's receipt times, terms date, periods, absence counts and storage-added
row counts, under the owner's a3 the manifest's and the receipt's `version`, and
under the advisor's note of 2026-11-23 the build report's `version`, each
equal to its one fixed text (`contracts.FIXED_TEXTS`), and the `period` columns of
the snapshot and list tables, each a real `YYYY-MM` month (else
`snapshot_month`), each format and declared shape checked before the scan: the two
snapshot coverage fields are lists of months, every other field one value, and
a container in place of one value refuses) admits a token equal to a key it
meets (an own-company licence or withheld number in a release column; in a manifest or
report field also a published registration) only when that number has one or two
digits or the shape 19xx or 20xx. Longer numbers, every unlisted field, the other
manifest fields and the rest of the report, except the fixed metadata listed
below, keep
the full scan against the keys they meet; other coincidental token
matches with those keys still refuse. Every number of every release table meets
its own-company licences and all withheld numbers by the token match (decision
0105 item 4 as amended by decisions 0119 and proposed 0123), with no string check.

Commerce registrations accept exactly one to six ASCII digits with an optional
slash followed by one to three ASCII digits (at most ten characters).
A row without a registration uses `ROW-` plus its published lowercase hexadecimal
twenty-character `row_key` with each digit spelled as a letter (`0-9` to `g-p`,
decision 0104 item 1), never its licence number. The released identity is
exactly `ROW-[a-p]{20}` and holds no digit, so the unchanged eight- and
eleven-digit scan never meets one in it; the spelling is one-to-one because the
published key accepts only `[a-f0-9]{20}`. A `ROW-` identity on a
financial-centre row refuses `registration_format`. The raw row-key column
remains absent. This S2-P71 lead ruling restores the Public projection only;
decision 0074 item 5's world-feed treatment and enrichment stay with S4-T02.
A commerce registration lexeme of one to ten ASCII letters becomes null at
intake, counted by rows under `published_non_registration_value`; other malformed
shapes still refuse `registration_format`. Every occurrence of a number published
on multiple commerce rows becomes null at intake and uses its own `ROW-` identity,
counted by rows under `published_duplicate_registration`. Rows are never merged,
picked or de-duplicated. Both counts use the existing `field_absences` capture
metadata (`registration_number`, source, period and current/snapshot use); the
bundle reader permits both reasons for one capture, but rejects repeated entries
of the same field/reason. The existing released `registration_number` key slot
holds the `ROW-` identity, never the withheld source value; no new column is added.

Withheld duplicate numbers stay only in the ephemeral audit set. The egress scan
refuses them in every released field, including typed numbers and dedicated key
slots, across current and historical captures and non-exempt manifests/reports and
storage-added counts; an exactly recomputed count is exempt under decision 0124. No duplicate-number list is exported; assembly retains its existing
lead-pin trust boundary.
Financial-centre numbers keep their five-digit declaration. Duplicate
companies and geocoded keys and collisions of `ROW-` identities still refuse as
`duplicate_registration_key`; winning-group event conflicts are counted absences
under decision 0117 item 3, not refusals. Duplicate published row keys still refuse as
`duplicate_row_key` when their identities differ. Cross-register ambiguity still
refuses as `ambiguous_cross_source_key`, with no source prefix added.

Missing financial-centre keys, duplicate financial-centre companies or geocoded keys,
duplicate row identities, cross-source key ambiguity, unknown columns, unconfirmed
branch structure and other malformed notice dates refuse with named reasons.
There is no merge, date repair, inferred cancellation
date or opening/closure column. A historical company need not be in today's
card table. Its cell belongs to its own snapshot. Empty kept snapshots and
missing snapshots are distinct; `Built.snapshot_reason` returns
`snapshot_not_kept` when either requested month is missing for that source.

Projection version `v2` removes the licence column and adds `field_absences` and
`activity_check` metadata. The activity result is always `not_proved` with reason
`register_publishes_no_code` for today's code-free schema; a planted stand-in
signed-class mismatch (a `mapped` review whose class differs from the code's
first four digits) refuses as `activity_code_mismatch`; any other review the
existing spine checker rejects (no sign-off, a malformed review date, a wrong
reason or name, a status that is not a decision) refuses as
`activity_review_invalid`. A legacy code never maps by prefix. No activity, nationality,
status or date is invented. The bundle reader checks the closed absence metadata
against its capture receipts and retains both metadata fields in assembly evidence.
Old v1 bundles must be rebuilt and pinned again; no compatibility fallback exists.

## Fixed metadata checks (decision 0124, proposed)

The single closed table `contracts.FIXED_METADATA` lists receipt file byte
counts, table row counts, approved publisher/dataset/basis-note text, the
absence field/reason sets, report status/snapshot reason, and the card/snapshot
schema mapping keys. The source-specific receipt wording is the lead's approved
intake wording, never registry placeholders. `terms_words` is exempt only when
it equals the closed approved set; other supplied terms retain the full scans
and do not receive a new mismatch refusal.

`build` supplies actual captures and table rows through `MetadataInputs` to the
existing scanners. Byte counts are recomputed from file bytes; row counts from
the actual table rows. Exact matches alone bypass token and content scans.
Altered fields meet both old scans first; if they pass, they refuse
`metadata_count_mismatch`, `metadata_fixed_text_mismatch`, or, for a closed
schema key, `metadata_key_not_schema`. Old scan reasons remain authoritative.
An invalid list or tuple in a fixed scalar field cannot inherit that scalar
exemption for its items; schema row lists keep their schema binding.
Unknown keys in the lower-level release-row scanner still receive its full
scan. Schema-key exemptions never apply to their values or another mapping.
Without independent bundle inputs the raw scanner never exempts a count; it
retains its old typed scan. The bound build calls enforce the exact checks.

This amends decision 0105 item 5 only for exactly recomputed counts. All other
fields keep their scans, including unlisted metadata and every released card
value. Digest and typed-format rules, per-company licence checks, bundle pins
and receipt-to-table trust are retained. The decision record lists the three
permitted existing test migrations and their matching altered/unlisted
negatives. Different-maker approval is required before admission.

## Sibling intake protocol

The lead supplies `EII_REGISTER_FILE` and `EII_FC_REGISTER_FILE` only in the lead's
shell. `intake.from_environment` takes an explicit mapping; parsers and builders
never inspect ambient environment values. No extra environment setting is used.
The sibling index protocol below is a builder interface, not an assertion about
files already retained by the lead. Its preparation and actual retained months
require the lead's verification.

Each primary CSV has a sibling with its full filename plus `.register.json`.
The lead pins each index's byte hash separately. Intake requires the two pins
through its `index_hashes` argument; the CLI takes `--biz-index-sha256` and
`--fc-index-sha256`. Changing an index or its selected receipt cannot silently
repin a retained month. A changed selection requires the lead's new reviewed
pin; the builder never computes its own trust anchor from the index it reads.
The closed index has exactly `version` (`register_siblings_v1`), `current` and
`snapshots` (an explicit list; no latest selection). Each selected capture has
exactly `receipt` and `files`. `files` maps each declared role to one sibling
basename. The current commerce role is `establishments`; the current
financial-centre roles are `companies`, `geocoded` and `events`. Its companies
role names the environment-selected file; its two companion basenames are
`qfc_companies_geocoded.csv` and `qfc_events.csv`.

A historical basename is `<period>.<role>.csv`, with the period in year-month
form. The index explicitly pins the receipt for that month, including a valid
empty CSV when the month is empty. A missing month is omitted. No directory
crawl, historical/current substitution, nested path or symbolic link is allowed.
Reads are bounded and check file identity, size and modification metadata before
and after reading. Intake writes nothing.

`receipt_for` declares the exact receipt shape: `version` (`register_input_v1`),
`kind` (`register_file`), `key`, `source_id`, `period`, `publisher`, `dataset`,
`retrieved_utc`, `licence_id`, `licence_basis`, `terms_words`, `terms_read_on`,
`basis_note` and `files`. The last maps each role to exactly `sha256` and `bytes`.
Every byte hash and length is rechecked. Retrieval time must be UTC in the
capture's month. Terms use the registry's pending words/date when unread; pending
or prohibitive terms never refuse a capture. Attribution must be supplied by the
lead, not inferred from filenames or filled with registry placeholders.

Receipts bind key `biz_register` to released source `biz_register` and key
`fc_register/file` to released source `fc_register`. The existing page key
`fc_register` has a different kind and is refused as a file receipt. Its page
schema and activation hold are unchanged. Ordinary fetch dispatch never opens
these file inputs or invokes a transport for them. Source-wide nightly selection
is conservative across all declarations, independent of order.

The CLI accepts a lead-prepared JSON array containing the exact integer
`grid_cell.cell` ownership set from the verified S2 frame, its byte hash, an output
directory and a release kind. It validates the hash and cell ownership before
intake. The manifest also hashes the canonical sorted ownership set. Frame
production and its source receipts remain with S2-T02. All errors are fixed
reason codes; the CLI prints only a fixed success or refusal. No source row,
registration, filename or path enters its output. Table metadata contains input
hashes, key-scoped attribution, method/version and per-source kept months.

## Verification boundary

Tests cover both release kinds, all three allowed registration-key tables, every
other table in document 03's closed table catalogue, schema/type/format and
identifier plants, historical location, pinned siblings, tampering, safe errors,
network denial and atomic publication failure. `validate_release` enforces the
register schemas and scans other tables; their full schemas stay with their own
builders. No independent review, actual register read, real geocoding check,
retention proof, full application release or store load is claimed here.

## Assembly handoff

The release assembly never reads a register file, its siblings or either
environment setting. The lead alone runs this package's build under the sibling
intake protocol, then stages the published `current/` output — `manifest.json`
and `tables/` — as `register_bundle/` inside the allowed assembly cache and
writes `register_bundle_pin.json` beside it holding the manifest's byte hash.
The `register_tables` phase re-verifies the pin, the manifest's closed key set
and bindings, every receipt's digest, metadata, files and period rules, the
declared table byte hashes and row counts, the frame's ownership hash against
the run's own `grid_cell` set, and the released rows through `validate_release`,
refusing by name at the first mismatch. After table-byte and row validation,
`load_bundle` refuses an empty `pub_register_company` as
`register_bundle_company_empty`, then a current receipt source without a company
row as `register_bundle_source_empty` (decision 0131 item 1; L-2395 item 3).
Empty snapshot tables and kept snapshot months without rows remain valid. A bundle path that is not a real
directory — a symlinked `register_bundle/` or `tables/` — is refused as
missing, so every byte read stays inside the allowed cache. Only the bundle's
released rows, file digests and receipt lineage are bound: current receipts
credit both registry keys, historical receipts stay per-period in the phase
record, and a missing kept month stays `snapshot_not_kept`.

Trust root: the receipt list is bound to the released tables only through the
lead's manifest pin. Raw register files are never retained in the cache, so the
reader cannot re-derive a receipt from file bytes; a stale receipt list
repacked under a fresh pin passes all checks. Reviewing and pinning the
manifest is therefore the sole control over the receipt-to-table binding.

Under proposed decision 0132, card content with at least four alphanumeric characters keeps substring matching, one to three uses consecutive whole Unicode word tokens including underscores, and punctuation-only text requires exact equality; longer-text collisions still fail closed for review.
