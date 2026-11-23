# Decision 0105: The register token scan admits short and year-shaped numbers in a closed list of typed columns

| | |
|---|---|
| Status | Accepted 2026-11-23 by the lead (ruling L-1647): every item is the owner's own choice (option (a) with three conditions, "a2 yes" and "a3", 2026-11-23) or the advisor's under the owner's delegation (item 8); built in S2-P71 Part 2 rounds 4 to 9, approved by another maker (`49e4c848`) and merged in train S2-24 |
| Date | 2026-11-23 |
| Scope | `custodian/src/eii_custodian/publicdata/registers/` (`contracts.py`, `validate.py`, `build.py`, `provenance.py`); the package README; [document 03](../03_DATA_CONTRACTS.md) **Register file projections (S2-T49)**; [TASKS.md](../../TASKS.md) S2-T49 |
| Amends | Document 03 **Register file projections (S2-T49)**: the sentence "No scan coverage is narrowed; coincidental token matches also refuse", for the fields listed below only; and its L-1288 paragraph, so that a typed number, still no identifier string, meets every key (item 4) |
| Purpose | Let the commerce register cross the release step when a short registration or licence number equals a token of an ordinary typed value, of a listed manifest field, of a fixed version text or of a period column, while every other identifier check stays as it is, and make every number column meet the published registrations (owner condition 1) |
| Read first | AGENTS.md rules 9, 12 and 46; DAT-11 and DAT-15 of document 03; [decision 0104](0104-register-row-key-letter-encoding.md) |

## Context and evidence

The release step refuses `registration_egress` when any token of a released
value equals a released registration, an input licence number or a withheld
duplicate registration. The round-2 review of S2-P71 (finding F2) showed that
short numbers make this refuse ordinary values: registration `12` against the
date `2026-11-12`, licence `25` against the latitude `2.25`.

The lead's counts-only probe of the real commerce file, from the lead's own
shell, counted 216 registrations of one or two digits, 18 of them equal to a day
or month token, 3 licences equal to a day token and 15 equal to a year. As built
before this record, the release step refuses the real file. The lead put the
choice to the owner (rule 12), recommending option (a): keep the full scan on all
free text, the key columns, the manifest and the report, and check only the
format of columns that already pass a closed typed grammar.

## The owner's words

The owner chose option (a), with three conditions. His exact words, relayed by
the advisor on 2026-11-23 (about 16:30): "yes a with 3 condotions". The
conditions below are the owner's own and binding, quoted exactly:

> 1. The format-only check applies only to short values (1 to 2 digits) and year-shaped values (19xx, 20xx); a value of 3 or more digits equal to a registration or licence number stays refused in every column, typed or not.
> 2. The typed-column list is closed: a column enters it only by decision record with its format written out; a value failing its format is refused, never skipped; an unlisted column is treated as free text.
> 3. Planted tests, all refusing: a licence or withheld number in any free-text column; a registration of 3 or more digits in a typed column; a typed column holding text that fails its format; a column missing from the list. Existing tests, attack sizes and tolerances stay unchanged.

The lead then asked whether the manifest's timestamps and period and the
report's counts should become typed fields under the same three conditions
(option a2). The owner's exact words, relayed by the advisor on 2026-11-23
(about 16:45): "a2 yes". Relayed with them: only one- or two-digit values and
years pass by format; any number of three or more digits equal to a registration
or licence stays refused everywhere; the list stays closed and is written in this
record; free text, key fields and the other manifest fields keep the full scan;
the planted tests of condition 3 extend to the manifest and report fields.

The lead then reported that the real file still refuses at three unlisted
fields, the manifest version `v2`, the receipt version `register_input_v1` and
the `period` columns of the snapshot and list tables, and asked whether they
should join the list with the strictest formats (option a3). The owner's exact
words, relayed by the advisor on 2026-11-23 (about 18:10): "a3". Relayed with
them: each version field must equal its one fixed text exactly, anything else
refused; each period column must be `YYYY-MM`, anything else refused; any number
of three or more digits equal to a registration or licence stays refused
everywhere; the receipt's free text stays fully scanned; planted tests as in
condition 3, extended to these three fields. The advisor's separate suggestion,
that further fixed-text or strict-date fields might join by decision record
without asking the owner, was not answered and is not approved: every further
field goes to the owner.

## Decision

1. **The closed typed-field list.** These fields, and no others, are typed
   fields. A release column is named `table.column`; a manifest field is named
   `manifest.` (a build report field `report.`) followed by the mapping keys
   that lead to it, list positions left out. The list has one home in code, `contracts.TYPED_FIELDS`, and a test binds
   it to this table.

   | Field | Format |
   |---|---|
   | `pub_register_company.registration_issue_date` | `date` |
   | `pub_register_company.registration_expiry_date` | `date` |
   | `pub_register_company.licence_issue_date` | `date` |
   | `pub_register_company.licence_expiry_date` | `date` |
   | `pub_register_company.notice_expiration_date` | `date` |
   | `pub_register_company.zone` | `integer` |
   | `pub_register_company.street_number` | `integer` |
   | `pub_register_company.block_en` | `integer` |
   | `pub_register_company.block_ar` | `integer` |
   | `pub_register_company.lon` | `longitude` |
   | `pub_register_company.lat` | `latitude` |
   | `pub_register_company.tax_classification_year` | `year` |
   | `pub_register_company.tax_registered` | `yes_no` |
   | `pub_register_company.capital_qar` | `integer` |
   | `register_company_list.employee_count` | `count` |
   | `pub_register_snapshot.period` | `month` |
   | `register_company_list.period` | `month` |
   | `manifest.version` | `manifest_version` |
   | `manifest.receipts.receipt.version` | `receipt_version` |
   | `manifest.receipts.receipt.retrieved_utc` | `timestamp` |
   | `manifest.receipts.receipt.terms_read_on` | `date_or_pending` |
   | `manifest.receipts.receipt.period` | `month` |
   | `manifest.snapshot_coverage.biz_register` | `month` |
   | `manifest.snapshot_coverage.fc_register` | `month` |
   | `manifest.field_absences.period` | `month` |
   | `manifest.field_absences.count` | `count` |
   | `manifest.tables.rows` | `count` |
   | `report.version` | `report_version` |

   The column formats, as `parse.validate_card` and `validate_release` check
   them on every released row before the scan:
   - `date`: exactly four digits, a hyphen, two digits, a hyphen and two digits,
     and a real calendar date; otherwise `malformed_date`.
   - `integer`: one or more ASCII digits and nothing else; otherwise
     `integer_format`.
   - `longitude` and `latitude`: a finite floating-point number within 180 or 90
     degrees of zero; a value of another type refuses `release_type`, one out of
     range `coordinate_format`.
   - `year`: exactly four ASCII digits; otherwise `integer_format`.
   - `yes_no`: exactly lowercase `yes` or `no`; otherwise
     `tax_registered_format`.
   - `integer` for `capital_qar`, a stored number: an integer from zero to
     2^63 - 1; a value of another type refuses `release_type`, one out of range
     `integer_format`.
   - `count` for `employee_count`: a non-negative integer, or null with the
     reason `CARRIED_FORWARD`; otherwise `release_count`.
   - `month` for the two `period` columns (the owner's a3): a string of exactly
     four ASCII digits, a hyphen and two ASCII digits that is a real month
     (`provenance.month`, the check the manifest's `month` also uses); any other
     value, of any type or shape, refuses `snapshot_month`. A snapshot month
     earlier than `2026-11` also refuses `snapshot_month`.

   The manifest and report formats, checked by `validate.scan_metadata` on every value of a
   listed field before its scan; any other value, including one of another type,
   a list or a mapping, refuses `typed_field_format`:
   - `timestamp`: a string that the receipt check reads as a UTC time
     (`fetch.snapshots.utc`: an ISO 8601 date and time with offset zero).
   - `date_or_pending`: exactly `pending`, or a `date` as above.
   - `month`: exactly four digits, a hyphen and two digits, a real month.
   - `count`: a non-negative integer, never a Boolean.
   - `manifest_version` and `receipt_version` (the owner's a3), and
     `report_version` (item 8): a string equal to its one fixed text, `v2`,
     `register_input_v1` and `v2`
     (`contracts.FIXED_TEXTS`, the texts the build writes); another version, the
     text with any character added, removed or changed, a string subclass, bytes
     or a number refuses.

   The two `snapshot_coverage` fields each hold a list of months, possibly
   empty, and every element is checked as a `month`; every other listed manifest
   field holds one value (`contracts.TYPED_SEQUENCES`). A field's shape is
   checked before anything below it is read: a list, tuple or mapping in place
   of one value (an empty one, or one holding a valid value, included), a value
   in place of the list of months, and a list inside that list each refuse
   `typed_field_format`. A listed release column holding a list, tuple, mapping
   or Boolean is a value of another type and refuses with that column's reason
   above before any scan.

   A column that a source does not publish must be null on that source's card
   (`release_source_field`); a published value is never skipped. A null is
   allowed only where the column's declaration in document 03 allows it.

2. **What a typed column admits.** In a listed column, a token equal to a
   released registration, an input licence number or a withheld duplicate
   registration is admitted only when that number is one or two digits, or four
   digits beginning `19` or `20`. A number of three or more digits that is not
   of that year shape refuses `registration_egress` as before. The prefix check
   and the rule-9 digit-run check (`identifier_digit_run`) are unchanged in a
   typed column. A typed number (`lon`, `lat`, `capital_qar`, `employee_count`)
   meets every such number (item 4) with the same short and year-shaped
   admission.

3. **Everything else keeps the full scan.** An unlisted field is free text and
   keeps the full scan: every free-text card column, the key columns, a column of
   a listed name in any other release table, the snapshot table, every unlisted
   manifest field (among them `method`, the receipt's publisher, dataset,
   licence, terms, basis note and file `bytes`, and the absence reasons), the
   whole build report except its `version` (item 8), and a manifest key
   holding a dot, below which nothing is typed. Of the snapshot table, only
   `period` is listed. No attack size, tolerance, the `BARE_DIGITS` pattern or any other
   scanner is changed.

4. **Number columns meet the published registrations (owner condition 1).**
   Since DAT-11 and L-1288 a stored number was scanned only against licence and
   withheld numbers. Now every number value of every release table (`lon`, `lat`,
   `capital_qar`, `registered_cell`, `employee_count`, and a number in any other
   table) meets every key by the scanner's existing token match: a registration
   `125` refuses against the capital `125` or the latitude `2.125`. A listed
   number column admits a short or year-shaped number (item 2); an unlisted one
   meets every key, short ones included. A number is still no identifier string:
   no prefix or digit-run check applies to it. This only adds refusals; it
   answers OPEN_ITEMS.md PO-S2-P71-08. `registered_cell` stays unlisted: a cell
   key is one token of 18 or 19 digits and a registration has at most six, so no
   registration can equal it; a licence equal to it refused before and still does.

5. **Listed manifest fields (the owner's a2).** The receipt times, the terms
   date, every period of the manifest and the counts that leave the build (the
   absence counts and the storage-added row counts, both in the manifest; the
   build report holds no count) are typed fields under item 2. A short or
   year-shaped number equal to one of their tokens is admitted; a number of three
   or more digits that is not of that year shape refuses `registration_egress`. A
   value failing its format refuses `typed_field_format` and is never skipped.
   This answers OPEN_ITEMS.md PO-S2-P71-07. If a real count of three or more
   digits equals a registration, the build refuses; that case goes to the owner
   and the rule is not loosened (the advisor's advice).

6. **What stays open.** A short key equal to a token of an unlisted field still
   refuses, as item 3 requires. After items 7 and 8, on the real file this can
   stop a build at a short number in the lead's receipt text or a receipt
   file's `bytes`. The receipt text is reworded, never listed (the owner's a3);
   the bytes stay a condition-1 refusal. OPEN_ITEMS.md PO-S2-P71-12.

7. **The version texts and the period columns (the owner's a3).** The
   manifest's `version`, the receipt's `version` and the `period` columns of
   `pub_register_snapshot` and `register_company_list` are typed fields under
   item 2. Each version field admits only its one fixed text, so it carries no
   other token; each period column admits only a real `YYYY-MM` month, checked
   on every row before the scan. A short key equal to `2`, `1` or a month token
   such as `11` is admitted there; a token of three or more digits that is not
   of the 19xx or 20xx shape, such as the year `2126`, still refuses
   `registration_egress`. This answers OPEN_ITEMS.md PO-S2-P71-09 for these
   three fields.

   The year clause of the owner's condition 1 reads, word for word: "The
   format-only check applies only to short values (1 to 2 digits) and
   year-shaped values (19xx, 20xx)". Under that clause, a year-shaped period
   year equal to a registration is admitted by format: the period `2026-11`
   against the registration `2026` passes, while `2126-11` against the
   registration `2126` refuses `registration_egress` (lead ruling L-1611).

8. **The build report's version (round 9).** The build report's `version`,
   written by `build.py`, is the typed field `report.version` of format
   `report_version`: a plain string equal to the fixed text `v2`
   (`contracts.VERSION`), checked exactly as the manifest's `version`; any other
   value, a string subclass or another type refuses `typed_field_format`, and
   the rest of the report keeps the full scan. Authority: the advisor's note of
   2026-11-23 18:32 (item 1), under the owner's delegation of fixed-text
   register fields of 2026-11-23 18:08 (L-1608).

## Tests

The owner's planted tests, each asserting its exact reason, in
`custodian/tests/test_registers_typed_scan.py` (extended to the manifest fields
and the number columns in round 5):

- **A licence or withheld number in any free-text column** refuses
  `registration_egress`, for every free-text column of a commerce card and of a
  financial-centre card.
- **A registration of three or more digits in a typed column** refuses
  `registration_egress`, as do a licence and a withheld number, across the
  integer, date and year columns, and a licence or withheld number in a
  coordinate.
- **A typed column holding text that fails its format** refuses with that
  format's reason, for every listed column.
- **A column missing from the list** is free text: with that column removed from
  the list, a short collision in it refuses `registration_egress`.
- **The manifest fields:** for each of the ten (eight since round 5, the two
  version fields since round 7), a value failing its format or of a wrong shape
  refuses `typed_field_format`; for each of the eight, whose formats admit more
  than one value, a token of three or more digits equal to a key refuses
  `registration_egress`; with the field removed from the
  list, a short collision refuses `registration_egress`; a short collision in an
  unlisted manifest field, the report or a key holding a dot refuses
  `registration_egress`.
- **The owner's a3 (round 7):** each version field holding a wrong version
  text, or its own text with one character added (a space before or after, a
  newline, a NUL, a zero-width space, a doubled last digit, a letter before or
  after), or in another case, digit form, type or a string subclass, refuses
  `typed_field_format`; a Hypothesis generator admits exactly the fixed text.
  Each period column holding a day, a one-digit month, no hyphen, a slash,
  month 13 or 00, a trailing space or newline, a letter, full-width or
  Arabic-Indic digits, bytes or an integer refuses `snapshot_month`; a generator
  admits exactly a real month. With each of the three removed from the list,
  its real-shaped short collision (`v2` with `2`, `register_input_v1` with `1`,
  `2026-11` with `11`) refuses `registration_egress`. A build with the key `1`
  or `11` passes with snapshots kept, and refuses `registration_egress` once
  that key is in a free-text card column; a build with the key `2` still
  refused at the report's `version` until round 9.
  The year `2126` in a period column refuses against the licence `2126`.
- **Period years (round 8):** in each period column, `2026-11` against the
  registration `2026` passes (condition 1's year clause) and `2126-11` against
  the registration `2126` refuses `registration_egress`; a generator over the
  years 1000 to 9999 admits a period year equal to the registration exactly
  when it is of the 19xx or 20xx shape.
- **The report's version (round 9):** `report.version` joins every version
  case above (`v3`, `v2 `, `v22` and the rest refuse `typed_field_format`) and
  the generator; with it removed from the list, a build with the key `2`
  refuses `registration_egress` and publishes nothing; with it listed, that
  build passes end to end with both versions `v2`, and a free-text `2` still
  refuses; the value `123` equal to a registration refuses
  `registration_egress` in each other field of the report.
- **Shapes (round 6):** every listed field in turn holds an empty list, an
  empty tuple, a valid value wrapped in a list or a tuple, a nested list or
  tuple, a mapping, `True` and the float `2.0`; each refuses with its exact
  reason (`typed_field_format` for a manifest field) unless it is the field's
  declared shape with valid elements: the months lists, and a coordinate's
  float.
- **The number columns:** a registration `125` against the capital `125`, the
  longitude `1.125`, the latitude `2.125`, the employee count `125` or a number
  `125` in another table refuses `registration_egress`, each against a passing
  case that differs in that one value.

Kept from round 3: registration `12` with the date `2026-11-12` builds, licence
`25` with the latitude `2.25` builds, and the staged bundle loads. A short key in
a receipt time, a terms date, a period or a row count builds since round 5.
Generators check that a typed column, a listed number and a listed manifest
count or time admit a number exactly when it is short or year-shaped, and that
free text and unlisted fields never do.

## What would change this decision

Adding or removing a field, changing a format, or changing what a typed field
admits needs a further decision record (the owner's condition 2).

## Sources

- The lead's question to the owner of 2026-11-23 on the register's identifier
  scan, and the owner's answer with the owner's three conditions, relayed by the advisor
  on 2026-11-23.
- The lead's question to the owner of 2026-11-23 on the manifest's times,
  period and counts, and the owner's answer "a2 yes", relayed by the advisor on
  2026-11-23.
- The lead's second question to the owner of 2026-11-23 on the version texts
  and the period columns, and the owner's answer "a3", relayed by the advisor on
  2026-11-23 (about 18:10).
- The advisor's note of 2026-11-23 18:32, item 1, approving the build report's
  `version` as the fixed text `v2`, under the owner's delegation of fixed-text
  register fields of 2026-11-23 18:08.
- The S2-P71 round-2 review verdict, finding F2.
- The lead's counts-only probe of the real commerce file of 2026-11-23, from the
  lead's own shell; counts only, no value described.
- [Document 03](../03_DATA_CONTRACTS.md), DAT-11, DAT-15 and **Register file
  projections (S2-T49)**.
- [PROGRESS.md](../../PROGRESS.md), **S2-P71 Part 2 round 4 — typed columns of
  the register token scan (decision 0105)** and **S2-P71 Part 2 round 5 — the
  owner's a2 and the number columns (decision 0105)**.

## Clarification note (2026-11-24, lead ruling L-1672)

In the Status line, "(item 8)" names item 8 of this record, the build report's version. The delegation it rests on is the owner's word of 2026-11-23, about 18:15, relayed by the advisor: fixed-text or strict-date fields may be added to the closed list on the advisor's answer, under the same three conditions. The advisor's note of 2026-11-23 18:32 applied it. This note changes no item of this record.
