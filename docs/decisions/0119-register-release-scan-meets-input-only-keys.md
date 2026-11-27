# Decision 0119: The register release scan meets published columns against input-only keys

| | |
|---|---|
| Status | Accepted by the owner, 2026-11-27 ("ACCEPT now: 0119, 0123 and 0124. They carry my own choices (option b, C1 and M1).", relayed by the advisor in note owner-relayed-20261127-060429) |
| Date | 2026-11-25 |
| Scope | `custodian/src/eii_custodian/publicdata/registers/validate.py` (`validate_release`; for item 6 also `scan_artefact`, `scan_metadata` and `scan_content`), `contracts.py` (`DIGEST_FIELDS`, item 6) and `build.py` (item 6); its invented tests; the package README; [document 03](../03_DATA_CONTRACTS.md) **Register file projections (S2-T49)** |
| Amends | [Decision 0105](0105-register-scan-typed-columns.md) items 3 and 4, for the release tables only |
| Purpose | Let the register release publish a column value that coincides with a registration number being released, while every intake licence and every withheld duplicate registration still refuses in every published column |
| Read first | AGENTS.md rules 9, 12 and 46; DAT-11 and DAT-15 of document 03; [decision 0102](0102-register-projection-run-in-rule-44.md); [decision 0104](0104-register-row-key-letter-encoding.md); decision 0105 |

## Context and evidence

The release scan of decision 0105 item 4 meets every published value of every
release table against three sets of numbers: the registrations being released,
the intake licences and the withheld duplicate registrations. On the real
register, run from the lead's own shell under decision 0102, the release scan
refused because a published column value coincides with a registration number
being released. The lead reported this as a count only; no value is given here
or needed.

A released registration is itself published in its own key column, so the same
number in another published column of the same release discloses nothing that
the key column does not already publish. The input-only keys are different: an
intake licence is never released, and a withheld duplicate registration is
nulled at intake and replaced by a `ROW-` identity (decision 0104); either
number in a published column would be its only way out.

## The owner's words

The lead put the choice to the owner (rule 12). The owner chose option B on
2026-11-25. His exact words: "option b". Option B, as the lead's brief states
it: published columns other than the registration-key columns are checked only
against the input-only keys (intake licences and withheld duplicate
registrations), not against the registration numbers being released. A withheld
number in any column still refuses.

## Decision

1. **Published columns meet the input-only keys only.** In `validate_release`,
   every published non-key value of every release table (free text or typed,
   a string or a number, nested in a list or mapping or held as bytes) and every
   column name meets the union of the intake licences and the withheld
   duplicate registrations, and nothing else. A token equal to a registration
   being released, the `ROW-` identities included, is published. This amends
   decision 0105 item 3 ("an unlisted field is free text and keeps the full
   scan") and item 4 ("every number value of every release table meets every
   key") for the release tables: the full scan and "every key" there now mean
   the input-only keys.
2. **A typed column narrows the same set.** A listed typed column (decision 0105
   item 1) meets the input-only keys less the short and year-shaped numbers
   (decision 0105 item 2), as before; a released registration no longer enters
   it.
3. **The key slot is unchanged.** Each `registration_number` of the three key
   tables still meets the withheld duplicate registrations only, so a withheld
   number in a key slot refuses `registration_egress`. Licences do not join the
   key slot check: an intake licence equal to a published registration still
   passes, as before; adding them would be a refusal the owner did not ask for.
4. **The released-key set is still built and returned.** `validate_release`
   still collects the released registrations and returns them for their other
   uses: the list table's membership in the current cards
   (`list_company_missing`), one owner per key across sources
   (`ambiguous_cross_source_key`), the duplicate key check
   (`release_duplicate_key`) and the metadata egress set of `build.py`.
5. **Consequences for other items of decision 0105.** Where items 2 and 7 name
   a released registration as a number that a release column meets, they read
   under item 1 of this record: the period `2126-11` against the released
   registration `2126` now publishes, and still refuses against the licence or
   withheld number `2126`. Owner condition 1 of decision 0105 ("a value of 3 or
   more digits equal to a registration or licence number stays refused in every
   column, typed or not") and the second plant of its condition 3 ("a
   registration of 3 or more digits in a typed column") hold for a withheld
   registration and for a licence; for a registration being released, the
   owner's later choice of option B governs the release tables. The manifest
   and the build report are unchanged (below), except for item 6.
6. **Only a named digest field is exempt.** A string is exempt from the token
   scan and the content scan only as the value of a field of the closed list
   `contracts.DIGEST_FIELDS` (the release columns of document 03 section 7.3
   that hold a SHA-256, and the manifest's frame, receipt, receipt-file and
   table digests), which must be exactly 64 lowercase hexadecimal characters or
   refuses `digest_field_format`; every other string is scanned even when it
   looks like a digest, in release text, decoded bytes, list items, nested
   values, mapping keys and column names, in the release tables and in the
   manifest and the build report.

## What stays unchanged

- `scan_metadata` and its `egress` set in `build.py`: the manifest, the build
  report and the storage-added table descriptors still meet the released
  registrations, the licences and the withheld registrations, with decision
  0105's typed manifest fields.
- `scan_content`: card names and published addresses still refuse
  `register_content_egress` in metadata.
- The banned identifier columns and a `registration_number` column outside the
  three key tables (`release_identifier_column`), the prefix check
  (`identifier_prefix`) and the rule-9 digit-run check (`identifier_digit_run`,
  `BARE_DIGITS`).
- `bundle.py`: the loader calls `validate_release` with no input-only key, as
  before; it holds none, because the input-only keys are never exported.
- No attack size, tolerance, typed field or format is changed; the scanners
  change only as item 6 states (the former shape-only digest exemption of
  `scan_artefact` and `scan_content` is removed).

## Tests

In `custodian/tests/test_registers_input_only_scan.py`, each with an invented
value of four digits that no listed column admits by format, and each
refusal against a passing control that differs only in the input-only set:

- A licence, and in turn a withheld duplicate registration, in each published
  non-key card column of both sources (37 commerce and 8 financial-centre
  columns, typed and free text) refuses `registration_egress`; a test binds the
  column lists to the contracts.
- The same number as the registration being released, in each of those
  columns, publishes.
- In another release table (`pub_place`), the number as text, an integer, a
  float, in a list, a mapping, a mapping key, bytes, nested bytes and a column
  name refuses against a licence or a withheld number, and publishes as a
  released registration; likewise the list's `employee_count` and the period of
  the snapshot and list tables.
- The key slot: a withheld number there refuses; a licence equal to the
  released registration publishes; the same number released and a licence in
  one column refuses.
- End to end: a build with released keys in free text and in a typed column
  publishes; a withheld duplicate in a free-text or typed column refuses with
  nothing published.
- A Hypothesis generator over numbers of one to six digits, five plant kinds and
  the three roles checks an independent oracle: only an input-only key refuses,
  and a listed column admits a short or year-shaped one.

For item 6, in `custodian/tests/test_registers_digest_fields.py`: a licence of
64 decimal digits in `name_en`, and a withheld or licence number padded to the
digest shape with hexadecimal letters, in card free text, a nested value, a list
item, a mapping key, a column name, bytes, nested bytes and an unlisted `sha256`
column, refuse `registration_egress` (a digest-shaped digit run refuses
`identifier_digit_run`); the same strings in ordinary manifest fields refuse
`registration_egress`, and as copied card text `register_content_egress`; every
named digest field, release and manifest, publishes a valid digest holding an
input-only key and refuses each malformed value (`digest_field_format`); a
build whose card name is a piece of the frame digest publishes, and refuses
when the receipt's `basis_note` repeats it. A Hypothesis generator draws
digest-shaped strings around a number in every such place, and the property
above gains two digest-shaped plants. The base's digest case of
`test_registers.py` now uses two named digest columns; its former
`fact_lineage` case, a table with no digest column, is scanned and refuses.

The existing plants that expected a released-key refusal are re-pointed to an
input-only value, each with its released-key case now publishing, in
`test_registers_typed_scan.py`, `test_registers.py`,
`test_registers_restoration.py` and `test_registers_intake.py`. The loader plant
of `test_register_tables.py` cannot hold an input-only key, because a bundle
holds none; it now plants a prefixed identifier (`identifier_prefix`), and the
former released-key value loads.

## What would change this decision

Adding a field to `DIGEST_FIELDS` needs a document-03 column or manifest field
that holds a SHA-256. Scanning a published column against the released registrations again, adding
the licences to the key slot check, or narrowing the input-only keys needs a
further decision record and the owner's answer (rule 12).

## Sources

- The owner's answer "option b" of 2026-11-25, relayed in the lead's brief for
  S2-REGB; the option's wording as that brief states it.
- The lead's counts-only report of the real-register release refusal under
  decision 0102, from the lead's own shell; no value described.
- [Decision 0105](0105-register-scan-typed-columns.md), items 2, 3, 4 and 7 and
  the owner's three conditions; [decision 0104](0104-register-row-key-letter-encoding.md)
  item 1; [decision 0102](0102-register-projection-run-in-rule-44.md).
- [Document 03](../03_DATA_CONTRACTS.md), DAT-11, DAT-15 and **Register file
  projections (S2-T49)**.
