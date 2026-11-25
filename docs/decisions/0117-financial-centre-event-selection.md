# Decision 0117: Financial-centre event rows select one latest notice per company

| | |
|---|---|
| Status | Proposed |
| Date | 2026-11-25 |
| Scope | `custodian/src/eii_custodian/publicdata/registers/parse.py`; its invented parser tests; the package README; [document 03](../03_DATA_CONTRACTS.md) **Register file projections (S2-T49)** |
| Purpose | Let the financial-centre events sibling hold more than one row per company without weakening duplicate refusal in the companies or geocoded roles |
| Read first | AGENTS.md rules 6, 7, 8, 19 and 24; document 03 **Register file projections (S2-T49)** |

## Context and evidence

The lead's real-file run refused `duplicate_registration_key` because one company
number occurred on two differing events rows. The lead reported counts only.
The events schema remains exactly `qfc_number`, `event` and the optional ISO
`notice_expiration_date`; a released card still carries exactly one event and one
notice expiration date. No real row value is reproduced here.

## Decision

1. **Identical rows collapse.** For the events role only, fully identical repeated
   rows for one company collapse to one. The companies and geocoded roles remain
   one row per company and retain their existing duplicate refusal.
2. **The latest distinct notice is selected.** Otherwise the company's card takes
   the row with the later `notice_expiration_date`, compared as parsed calendar
   dates rather than strings of another shape. A row without a date never wins
   over a dated row. Selection is deterministic and independent of input row order.
3. **Ambiguous ties still refuse.** Two different events rows for one company with
   the same parsed date, or both without a date, refuse
   `duplicate_registration_key`. Identical rows remain subject to item 1.

## Tests

Invented five-digit company keys and synthetic event text cover identical pairs,
both orders of distinct dates, dated versus undated rows in both orders, same-date
and both-undated refusals with the exact reason, and unchanged companies and
geocoded duplicate refusals. A Hypothesis oracle covers empty, singleton, repeated,
ordered and permuted event lists and ties; a separate planted case covers
`date.min` against an undated row. Existing tests and privacy scans stay unchanged.

## Sources

- S2-REGEV task brief of 2026-11-25 and its counts-only description of the lead's
  real-file refusal.
- [Document 03](../03_DATA_CONTRACTS.md), **Register file projections (S2-T49)**.
- `registers/contracts.py`, events schema, and `registers/parse.py`, card projection.
