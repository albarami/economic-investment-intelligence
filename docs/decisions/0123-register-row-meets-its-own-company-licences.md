# Decision 0123: A register row meets its own company's licences

| | |
|---|---|
| Status | Accepted by the owner, 2026-11-27 ("ACCEPT now: 0119, 0123 and 0124", relayed by the advisor in note owner-relayed-20261127-060429); his choice of option C1 of 2026-11-25 stands (see **The owner's words**) |
| Date | 2026-11-25 |
| Scope | S2-T49 register intake audit, release-table scan, build wiring, invented tests and projection documentation |
| Amends | [Decision 0119](0119-register-release-scan-meets-input-only-keys.md) item 1, and the owner's condition 1 of [decision 0105](0105-register-scan-typed-columns.md) through decision 0119, for release tables only |
| Purpose | Aim the licence-token scan at the company whose licence could leak beside its published fields |
| Read first | Decision 0119 items 1 to 6; decision 0105, **The owner's words**; document 03, **Register file projections (S2-T49)** |

## Context and reasoning

The lead's counts-only note for S2-REGC1 reports that the option-B release still
refuses when ordinary published address and numeric values coincide with intake
licence numbers. Option C1 applies option B's reasoning to licences: the scan
protects a company's licence from leaking beside that company, while a chance
equality with another company's unpublished licence does not disclose that
company's licence relationship. The lead put options C1, C2 and C3 to the
owner, with C1 recommended, and the owner chose C1.

## The owner's words

The lead put the choice to the owner (rule 12) through the advisor on
2026-11-25, with option C1 recommended. His exact words: "I prove your
reconfsyins Reconnections Your Recommend pick". The advisor read them as "I
approve your recommendations ... your recommended pick", that is option C1, and
relayed that reading for the lead to check. The lead's note had recommended
C1, so the reading is that pick. Any further register refusal goes to the owner
as a new choice with counts only; it is never worked around.

## Proposed decision

1. **Each row meets its own licences and every withheld duplicate.** Every
   published non-key value and column name meets that row's own company's
   licence numbers plus every withheld duplicate registration. A row without
   an entry in the licence map meets only the withheld duplicates. Released
   registrations do not join this set. The closed typed-column rule of decision
   0105 applies to this same per-row set; all other fields keep its full scan.
2. **The map stays ephemeral.** `InputAudit.licences_by_registration` is built
   beside `InputAudit.licences` in `parse._rows` for the establishments role,
   after duplicate registrations are withheld. Its key is the released
   registration or the existing `ROW-` identity for a numberless row; its value
   is that company's set of intake licences. `build` unions the map across
   current and historical captures before scanning their full cards, then
   validates the projected tables with that same map. Neither the map nor any
   licence value enters a table, manifest, report or bundle.
3. **The other boundaries stay unchanged.** The key slot meets withheld
   duplicates only. `validate_release` still returns the released-key set and
   checks its membership, ownership and uniqueness. The `build.py` metadata
   scans keep the released registrations, every intake licence and every
   withheld duplicate. `bundle.py` keeps calling `validate_release(tables,
   frame)` with no input-only key. Decision 0119 item 6's named-digest rule,
   the typed-field list and formats, the identifier-column ban, prefix and
   digit-run checks, attack sizes and tolerances are unchanged.

## Verification scope

Invented tests cover each published card column, other-company street, building,
capital and address matches, withheld duplicates, numberless identities, and
cross-capture licence unions. Recursive values, list items, mapping keys, column
names and decoded bytes are tested directly at the shared row-scanner boundary;
actual card containers and extra columns still refuse earlier under the closed
schema. A property draws licence maps and rows against an independent token and
typed-admission oracle. No real register input or count is measured by this
build, and no passed release or slice gate is claimed.

## What would change this decision

A later owner choice of C2, C3 or another scope replaces this decision. Use or
merge still requires another maker's review and the record's acceptance. Changing the row-to-licence binding, withholding scope, typed admission,
metadata key set or digest exception requires a further decision record.

## Sources

- The lead's S2-REGC1 task brief, **Status of this build**, **Base** and **Build**.
- The lead's supplied register-collisions note, **What the counts show** and
  **Options**; counts only, no register value reproduced.
- Decision 0119 items 1 to 6 and **What stays unchanged**; decision 0105,
  **The owner's words**, items 1 and 2.
- [Document 03](../03_DATA_CONTRACTS.md), **Register file projections (S2-T49)**.
