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
calendar dates in ISO format. Empty optional fields become null; required fields
do not get default values. Categories whose values have not been declared by
document 03 remain open text, tested with invented, previously unseen values.
The only supplied categorical values, the tax flag, are validated as declared.

The commerce projection preserves its declared card fields except internal
`row_key`, the extra `nationality_group` fields and derived `points_at_location`.
The extra nationality-group columns are header-checked and dropped; internal
row keys and location counts are validated but never released. The
financial-centre projection
maps `qfc_number` to `registration_number`, preserves its published names,
registered address and licence status, and preserves at most one published
notice and its complete date. The geocoded companion contributes coordinates
and the frame-resolved cell only. Internal order and row keys, inferred building
names, matched-place labels and match quality never become card facts. A tower
field needs confirmation that it is published on the card before it can be
added. Source-inapplicable columns are null and cannot be filled by the other
source's schema. No worker, residence, owner or person column is accepted.

DAT-11 scans every string column, including non-key licence and address strings.
A string equal to another registration key refuses. Typed capital, coordinates,
counts and cell keys are not identifier strings; artefact scanning is unchanged.
The 2026-11 floor applies only to kept snapshots. Each snapshot is compared with
its own source's current capture; current retrieval months may differ and may
predate the keeper floor.

Blank registration keys, duplicate keys, cross-source key ambiguity, unknown
columns, unconfirmed branch structure and malformed notice dates refuse with
named reasons. There is no key prefix, merge, date repair, inferred cancellation
date or opening/closure column. A historical company need not be in today's
card table. Its cell belongs to its own snapshot. Empty kept snapshots and
missing snapshots are distinct; `Built.snapshot_reason` returns
`snapshot_not_kept` when either requested month is missing for that source.

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
