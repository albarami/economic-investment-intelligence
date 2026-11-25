# Decision 0117: Financial-centre event rows select one latest notice or withhold a conflict

| | |
|---|---|
| Status | Proposed |
| Date | 2026-11-25 |
| Scope | `custodian/src/eii_custodian/publicdata/registers/parse.py`; its invented parser tests; the package README; [document 03](../03_DATA_CONTRACTS.md) **Register file projections (S2-T49)** |
| Purpose | Let the financial-centre events sibling hold more than one row per company without weakening duplicate refusal in the companies or geocoded roles |
| Read first | AGENTS.md rules 6, 7, 8, 19 and 24; document 03 **Register file projections (S2-T49)** |

## Context and evidence

The lead's real-file run refused `duplicate_registration_key` because one company
number occurred on two differing events rows. A later counts-only run found the
remaining case: two differing rows, both without a notice date and with no dated
row for that company. The lead reported counts only.
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
3. **A conflict in the winning group withholds that company's events.** After
   item 2 chooses the latest date, or the undated group when the company has no
   dated row, two or more differing rows in that group select no event. The card's
   `event` and `notice_expiration_date` are null, and `event_conflict_absences`
   increases once for that company. The capture-bound `field_absences` entry is
   `event` / `published_event_conflict`, with unit companies. A conflict on an
   older date that loses to a later dated row neither withholds nor counts.
   Identical rows remain subject to item 1.

## Tests

Invented five-digit company keys and synthetic event text cover identical pairs,
both orders of distinct dates, dated versus undated rows in both orders, latest-date
and undated conflicts with null card fields and a count of one company, an older-date
conflict losing with count zero, and release coverage through the bundle reader.
Companies and geocoded duplicates keep their exact refusal reason. A Hypothesis
oracle covers empty, singleton, repeated, ordered and permuted event lists, winning
and losing ties; a separate planted case covers `date.min` against an undated row.
Existing privacy scans stay unchanged.

## Sources

- S2-REGEV task brief of 2026-11-25 and its counts-only description of the lead's
  real-file refusal.
- [Document 03](../03_DATA_CONTRACTS.md), **Register file projections (S2-T49)**.
- `registers/contracts.py`, events schema, and `registers/parse.py`, card projection.
