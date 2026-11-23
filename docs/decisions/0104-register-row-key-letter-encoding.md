# Decision 0104: The released register row identity spells its digits as letters

| | |
|---|---|
| Status | Proposed: lead ruling of 2026-11-23; owner acceptance asked |
| Date | 2026-11-23 |
| Scope | `custodian/src/eii_custodian/publicdata/registers/` (`contracts.py`, `parse.py`); the package README; [document 03](../03_DATA_CONTRACTS.md) **Register file projections (S2-T49)**; [TASKS.md](../../TASKS.md) S2-T49 |
| Amends | The S2-P71 lead brief's row-key ruling for the Public projection, as recorded in document 03 **Register file projections (S2-T49)**: the released `ROW-` identity form only |
| Purpose | Let a commerce row with no registration number cross the release step, while the rule-9 digit-run guard stays exactly as it is |
| Read first | AGENTS.md rules 8, 9, 12 and 46; DAT-02, DAT-12 and DAT-15 of document 03; [decision 0022](0022-real-register-companies-with-a-synthetic-world.md) item 1; [decision 0074](0074-company-level-fields-of-the-owners-company-workbook.md) item 5 |

## Context and evidence

Under the S2-P71 row-key ruling, a commerce row with no registration number is
keyed in the released `registration_number` slot by `ROW-` plus its published
twenty-character lowercase hexadecimal row key. The release step scans that slot,
like every released string, for a digit run of exactly eight or eleven digits
(DAT-15, AGENTS.md rule 9) and refuses `identifier_digit_run`.

The round-2 review (S2-P71, verdict finding F1) showed that a hexadecimal row key
can hold such a run. If the keys behave like hashes, one key holds one with a
chance of about 0.064. The lead's counts-only probe of the real commerce file, from
the lead's own shell, counted 1,463 rows with no number, and 106 of their row keys
hold a run of exactly eight or eleven digits. As built, the release step would
refuse the real file. Rule 12 forbids relaxing the guard to let them through.

## Decision

1. **Letter spelling.** The released identity of a row with no registration
   number is `ROW-` plus its published row key with each digit replaced by one
   fixed letter: `0` to `g`, `1` to `h`, and so on to `9` to `p`. The letters
   `a` to `f` are kept. The released form is exactly `ROW-[a-p]{20}`.
   - The published row key is still accepted only as `[a-f0-9]{20}`, so a raw
     `g` to `p` in the source refuses `row_key_format`. The spelling is therefore
     one-to-one, and the published key is recovered exactly by the reverse map.
     It is a lossless re-encoding, not a repair: no value is invented, merged,
     picked or dropped.
   - The released identity holds no digit, so the rule-9 scan, its
     `BARE_DIGITS` pattern and its use are unchanged and still refuse an eight-
     or eleven-digit run in every other released string.
   - Each pattern has one home in `registers/contracts.py`: `SOURCE_ROW_KEY` for
     the published key and `ROW_KEY` for the released identity.
   - A `ROW-` identity is valid only for the commerce source (`biz_register`).
     The same identity on a financial-centre row of either table refuses
     `registration_format` (S2-P71 verdict finding F4).
   - Registration numbers, the financial-centre five-digit numbers, the
     duplicate and collision refusals, and the absence counts are unchanged.
     The projection version stays `v2`.

## Tests

- **The verdict's row.** A row with no number whose key holds an exactly
  eight-digit run builds for both release kinds; so do an eleven-digit run and
  an all-digit key. Each appears once, spelled, in both tables.
- **The guard stays.** The same row with an eight- or eleven-digit run in a
  name refuses `identifier_digit_run`.
- **A generator over the real alphabet.** Lists of distinct `[a-f0-9]{20}` keys
  parse to identities that match `ROW-[a-p]{20}`, hold no digit, reverse to the
  source keys and pass the release check.
- **Refusals.** A released identity with a digit, a letter past `p` or the
  unspelled key refuses `registration_format`; a source key with `g` to `p`,
  an upper-case letter or the wrong length refuses `row_key_format`.
- **Deletions.** Deleting the spelling, the `ROW_KEY` alphabet, the source
  alphabet or the source binding, one at a time, turns its test red.

## What would change this decision

A published row key that is not lowercase hexadecimal, or a rule-9 change to
the digit-run guard. Either needs a further decision record.

## Sources

- The S2-P71 round-2 review verdict, finding F1, and the round-3 lead brief.
- The lead's counts-only probe of the real commerce file of 2026-11-23, from the
  lead's own shell; counts only, no value described.
- [Document 03](../03_DATA_CONTRACTS.md), DAT-02, DAT-12, DAT-15 and
  **Register file projections (S2-T49)**.
- [PROGRESS.md](../../PROGRESS.md), **S2-P71 round 3 — letter-spelled row
  identities**.
