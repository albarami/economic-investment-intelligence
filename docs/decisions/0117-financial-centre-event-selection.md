# Decision 0117: Financial-centre event rows select one latest notice or withhold a conflict

| | |
|---|---|
| Status | Accepted by the owner, 2026-11-27 ("ACCEPT 0116, 0117, 0118, 0120, 0121 and 0122", relayed by the advisor in note owner-relayed-20261127-060429), on the lead's confirmation (ruling L-2272) that its review still stands on main `bc9bb749`: the record's text is byte-equal to its text at `247c6dc` (S2-DREC.fx1), which S2-DREC.cf2 (Cursor, grok-4.7-high, a maker other than the builders) CONFIRMED |
| Date | 2026-11-25 |
| Scope | `custodian/src/eii_custodian/publicdata/registers/parse.py`; its invented parser tests; the package README; [document 03](../03_DATA_CONTRACTS.md) **Register file projections (S2-T49)** |
| Amends | [Document 03](../03_DATA_CONTRACTS.md) **Register file projections (S2-T49)**, the sentences on the financial-centre events selection (proposed) |
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

## Consequences

A company with several events rows now has one card, not a refusal. The card keeps
exactly one event and one notice expiration date, or both null when the winning
group conflicts. A company whose events are withheld is counted once in the
capture-bound `field_absences` entry `event` / `published_event_conflict`, so the
withholding is visible in the manifest. Duplicate refusal for the companies and
geocoded roles stays as it was. The record changes no schema and no column.

## Tests

Invented five-digit company keys and synthetic event text cover identical pairs,
both orders of distinct dates, dated versus undated rows in both orders, latest-date
and undated conflicts with null card fields and a count of one company, an older-date
conflict losing with count zero, and release coverage through the bundle reader.
Companies and geocoded duplicates keep their exact refusal reason. A Hypothesis
oracle covers empty, singleton, repeated, ordered and permuted event lists, winning
and losing ties; a separate planted case covers `date.min` against an undated row.
Existing privacy scans stay unchanged.

## What would change it

Releasing more than one event or notice date on a card, adding a column to the
events schema, or selecting by any rule other than the later parsed notice date
needs a further decision record and an amendment of document 03 **Register file
projections (S2-T49)**. Admitting repeated differing rows in the companies or
geocoded roles needs its own record, since those roles keep `duplicate_registration_key`.

## Sources

- S2-REGEV task brief of 2026-11-25 and its counts-only description of the lead's
  real-file refusal.
- [Document 03](../03_DATA_CONTRACTS.md), **Register file projections (S2-T49)**.
- `registers/contracts.py`, events schema, and `registers/parse.py`, card projection.
