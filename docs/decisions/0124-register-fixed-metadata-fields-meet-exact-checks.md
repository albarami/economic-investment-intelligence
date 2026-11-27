# Decision 0124: Register fixed metadata fields meet exact checks

| | |
|---|---|
| Status | Accepted by the owner, 2026-11-27 ("ACCEPT now: 0119, 0123 and 0124 ... 0124 stays conditional on the planted refusals and approval by a different maker, as its Status line says.", relayed by the advisor in note owner-relayed-20261127-060429); his choice M1 of 2026-11-26 stands, conditional on planted refusals and approval by a different maker before admission; on record: S2-REGM1.rv3 (Factory Droid) APPROVED `9363157053209d8e98fa82769a04d65f52d89968` with the planted refusals (PROGRESS.md **S2-REGM1 approval**) |
| Date | 2026-11-26 |
| Scope | Slice S2, task S2-T49; fixed register metadata and schema column-name keys only |
| Amends | Decision 0105 items 3, 5 and 6 for the fields listed below, including item 5's refusal of an exact recomputed count; decision 0119 item 6's statement that only named digests are exempt; proposed decision 0123 item 3's unchanged metadata scans |
| Read first | Decision 0105 item 5; decision 0119 item 6; decision 0123 item 3; document 03, **Register file projections (S2-T49)** |

## The owner's words and bounded rulings

The owner's answer of 2026-11-26, relayed in the lead's bounded M1 intake note:

> Approve M1. Condition: the tests must plant a real-looking company name inside a fixed label and an altered count, and both must be refused; a reviewer from a different maker approves it before it joins.

The lead's amendment L-2139 supplies the approved receipt wording and orders
existing scans before a new mismatch refusal. Amendment L-2141 explicitly
answers decision 0105 item 5's referral to the owner: an exact count recomputed
from the bundle is exempt, even when it equals a registration or licence.
Neither ruling waives a release check, the S2 gate, or different-maker review.
Decision 0105 itself is preserved; this record records its amendment.

## Closed fields and authority

`contracts.FIXED_METADATA` is the single closed path table. Paths omit list
indices. No unlisted field is made fixed by its spelling, value or type.

| Path | Check | Independent quantity or approved authority |
|---|---|---|
| `manifest.receipts.receipt.files.establishments.bytes` | `exact_count` | Length in bytes of that capture's establishments file |
| `manifest.receipts.receipt.files.companies.bytes` | `exact_count` | Length in bytes of that capture's companies file |
| `manifest.receipts.receipt.files.geocoded.bytes` | `exact_count` | Length in bytes of that capture's geocoded file |
| `manifest.receipts.receipt.files.events.bytes` | `exact_count` | Length in bytes of that capture's events file |
| `manifest.tables.rows` | `exact_count` | Length in rows of the named validated table supplied to storage |
| `manifest.receipts.receipt.publisher` | `fixed_text` | Source-specific `APPROVED_RECEIPT_WORDING`, lead's approved intake wording |
| `manifest.receipts.receipt.dataset` | `fixed_text` | Same source-specific wording table |
| `manifest.receipts.receipt.basis_note` | `fixed_text` | Same source-specific wording table |
| `manifest.receipts.receipt.terms_words` | `approved_exempt` | `TERMS_WORDS_EXEMPT_SET`, lead's closed intake set |
| `manifest.field_absences.field` | `fixed_text` | Field-name set from `contracts.ABSENCE_KINDS` |
| `manifest.field_absences.reason` | `fixed_text` | Reason set from `contracts.ABSENCE_KINDS` |
| `report.source_status` | `fixed_text` | Build's fixed text `validated` |
| `report.missing_snapshot_reason` | `fixed_text` | Build's fixed text `snapshot_not_kept` |
| `released.pub_register_company` mapping keys | `schema_keys` | Exactly `contracts.CARD_COLUMNS`; values are never exempted by this rule |
| `released.pub_register_snapshot` mapping keys | `schema_keys` | Exactly `contracts.SNAPSHOT_COLUMNS`; values are never exempted by this rule |

The receipt wording for `biz_register` and `fc_register` is copied exactly from
the lead's approved wording note, not from registry placeholders or the receipt
under check. Another source has no approved wording. `terms_words` is expressly
**not** a `fixed_text` field: an exact entry of the closed exemption set is
exempt; any other supplied terms get the existing full scans and no new
mismatch refusal. Pending and prohibitive terms remain records.

## Exact checks and scan order

1. `MetadataInputs` carries current and historical captures and the actual
   validated table rows. The validator recomputes byte lengths and row counts
   at check time, never from the declared counts. Receipt file lookup is bound
   to current/snapshot use, source, period and role; table lookup is by name.
   Counts must be plain integers, so a Boolean or float cannot match by Python
   equality. Text must be a plain string and equal an approved value exactly.
2. An exact match exempts that leaf from both existing token and card-content
   scans. A mismatch first meets the existing `scan_metadata` and
   `scan_content` behavior, including typed-format checks. An existing refusal
   such as `registration_egress`, `identifier_digit_run`, `typed_field_format`
   or `register_content_egress` wins. If both scans pass, it refuses
   `metadata_count_mismatch` or `metadata_fixed_text_mismatch`.
   An invalid list or tuple in a fixed scalar field cannot pass that scalar
   path to its items: every item gets the full scans, including approved
   words inside an invalid wrapper. Schema row lists retain their schema path.
3. A schema column-name key is exempt only in its own named schema mapping.
   An unknown key is scanned first, then refuses `metadata_key_not_schema`
   in that closed mapping. The lower-level release-row scanner retains full
   scanning for every unlisted key and value; full release validation retains
   its earlier closed-schema reasons. A key in any other mapping stays scanned.
4. `build` binds the independent inputs and card content to both scanners for
   the manifest, report and storage table descriptors. A standalone scanner
   without bundle inputs cannot exempt counts or enforce count equality; it
   retains the existing typed/count scan. Approved labels and schema keys can
   still match their code-owned constants without bundle inputs. Changed text
   without bound inputs remains fully scanned; that raw scanner is not a
   substitute for the build's bound validation.
5. Every unlisted field retains the existing scans. No token matching rule,
   content-match length, digest format, privacy parameter, table value scan,
   per-company licence binding, attack size or tolerance changes. The bundle
   loader retains its independent pin, receipt, hash, schema and table-count
   checks and its existing trust boundary: raw input files are not exported.

## Plants and permitted test migrations

The invented company label in `test_registers_fixed_metadata.py` is planted
independently in a publisher and in a schema key. The publisher plant absent
from cards refuses `metadata_fixed_text_mismatch`; when present in the cards it
refuses `register_content_egress`. The unknown key refuses
`metadata_key_not_schema`, or `register_content_egress` when it contains card
content. A licence and an eight-digit token in an unknown key retain their
old scan reasons. Each plant starts from a passing control.

A file length off by one and a table row count off by one each refuse
`metadata_count_mismatch`. An altered eight-digit count refuses
`identifier_digit_run`. A changed count equal to an intake licence or withheld
key refuses `registration_egress`. A genuinely eight-digit file length passes
only when recomputed exactly. Unlisted fields carrying card text or a licence
retain `register_content_egress` and `registration_egress`. Generators check row
and byte equality, suffix rejection and schema-key equality. Each new refusal
guard is independently removed and restored for red-test evidence in PROGRESS.md.

Under L-2141 F1 to F4 only these existing outcomes migrate:

- `test_register_storage_manifest_count_keeps_egress_scan` becomes
  `test_register_storage_manifest_exact_count_is_not_scanned`: the unchanged
  invented rows have exact count 125 and intake licence 125, so build passes.
  `test_register_storage_altered_count_equal_to_key_still_refuses` keeps the
  same current rows, adds an earlier capture supplying licence 126, and alters
  only the company descriptor from its exact count to 126; it refuses
  `registration_egress`.
- `test_register_duplicate_registration_cross_capture_leak_refuses`, its
  `storage_count` parameter only: the unchanged exact company count 125 passes
  despite withheld key 125. Altering only its empty snapshot-table count to
  125 refuses `registration_egress`. Every other parameter retains its reason.
- `test_register_short_key_in_table_counts_builds_and_unlisted_refuses` becomes
  `test_register_exact_table_count_survives_typed_list_removal`: removing the
  old typed declaration still leaves the exact count 4 checked by the new
  closed list. Removing its exact-count declaration too makes it unlisted and
  restores the original `registration_egress` refusal.

These migrations concern only listed, exactly recomputed counts. All other
existing expected reasons are retained. The shared invented `capture` helper
now supplies the approved publisher, dataset and basis note; it still builds
invented CSV data. No real register, public cache or secret input is used.

Four extra one-input cases wrap an approved report label or approved terms in
a list or tuple. Each retains `register_content_egress`; the approved scalar
control still passes. Deleting the scalar-path termination guard alone makes
all four fail, and its disposable source copy is restored by byte comparison.

## Admission and sources

Independent approval by a different maker is owed on the exact candidate
before it joins. Test results and plants are build evidence only, not a passed
real-register bundle, release or S2 gate.

Sources: the owner's relayed M1 note of 2026-11-26; the lead's bounded
`approved_receipt_wording.json` and field-only hit inventory; the S2-REGM1.b3
brief, amendments L-2139 A to E and L-2141 F1 to F5; decision 0105 items 3, 5
and 6; decision 0119 item 6; proposed decision 0123 item 3; document 03,
**Register file projections (S2-T49)**; PROGRESS.md, **S2-REGM1 b3 — exact fixed metadata checks**.
