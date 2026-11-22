# Decision 0094: S2-T09 closes at S2 with the C6 and C7 pins at later slices

| | |
|---|---|
| Status | Accepted by the owner, 2026-11-22 20:14 |
| Date | 2026-11-22 |
| Owner | The owner |
| Decided by | The owner, 2026-11-22 20:14, answering yes to the lead's question with the advisor's three conditions |
| Amends | Document 12 TST-198 (one sentence added, no other word changed); task S2-T09 |
| Purpose | Let task S2-T09 close at the slice S2 gate while the five C6 neighbour and C7 shared-reach result pins wait for the slice that builds their calculation code, without weakening the slice S7 gate. |
| Read first | Document 07 MTH-03; document 12 TST-198; OPEN_ITEMS.md OI-283; TASKS.md S2-T09, S6-T10 and S7-T05 |

## Context

TST-198 requires a slice S2 task to write every regression value that MTH-03
lists as unpinned, and the slice S7 gate to fail while any remains unpinned.
`completion_evidence` in
`custodian/src/eii_custodian/publicdata/method_card_validation.py` applied
the same 29-pin rule at both gates. Five of those pins are results of
calculations whose code is built after slice S2:

- `c6.expected_clq`, `c6.expected_p`, `c6.expected_q`: the expected
  co-location quotients and their p and q values of card C6, computed by
  task S6-T10;
- `c7.shared_b_given_a`, `c7.shared_a_given_b`: the expected shares of card
  C7, computed by task S7-T05.

The other 24 pins (C5, C14, the reliability period, the sixteen
configuration pins, and the source inputs `c6.release_sha256` and
`c7.district_weights`) stay owed at slice S2.

## Decision

1. **TST-198 amendment.** TST-198 gains exactly this text, with a link to
   this record, and no other word of TST-198 changes: "C5, C14, reliability
   period and configuration pins at S2; C6 neighbours and C7 shared reach at
   S7". "C6 neighbours" means the three pins `c6.expected_clq`,
   `c6.expected_p` and `c6.expected_q`; "C7 shared reach" means the two pins
   `c7.shared_b_given_a` and `c7.shared_a_given_b`. No other pin moves; the
   C6 settings and release hash and the C7 settings and district weights
   stay at slice S2.
2. **The S2 path.** At gate S2, `completion_evidence` accepts a pending pin
   only when the pin is one of the five of item 1 (`S7_DEFERRED_PINS`) and
   its record row's `unpinned_reason` begins `OI-283: `, naming its row in
   open item OI-283. Every other pending pin, and a pending pin of the five
   whose reason does not begin so, is refused as `S2:unpinned:<pins>`,
   naming each refused pin.
3. **The S7 path is unchanged.** The S7 branch of `completion_evidence` and
   its rule over every pin stay unchanged: at gate S7 every pending pin of
   the 29, the five of item 1 included, is refused as `S7:unpinned:<pins>`,
   and an open item never clears it. The guard
   `custodian/tests/test_method_card_pins.py::test_plant_unpinned_at_gate_even_with_open_item`
   stays and still passes for every pin at both gates.
4. **OI-283 rows.** OI-283 holds one row per pin of item 1, with its reason
   and the task that computes it: S6-T10 for the three C6 pins and S7-T05
   for the two C7 pins. A test reads the committed ledger and refuses a
   missing row or a row without its task.

## Evidence

The builder's tests use invented records only (`method_card_pin_fixtures`):
one-change negatives for each refusal branch, a property test over pending
subsets against an oracle written from items 2 and 3, and the planted
removals of task S2-P62. This record claims no pinned value and no passed
gate.

## Consequences

- S2-T09 can close at the slice S2 gate with the five pins of item 1 pending
  under OI-283, once every other pin is checked and written.
- The slice S7 gate fails until S6-T10 and S7-T05 pin the five values; their
  pinning follows MTH-03 unchanged (reviewer check, recorded settings, no
  invented value).

## What would change it

A later decision that moves another pin, or that builds the C6 or C7
calculation code before slice S2 closes, would amend items 1 and 2.

## Acceptance

The lead put the question to the advisor, who put it to the owner with three
conditions: (a) this record, amending TST-198 as in item 1; (b) the S7 guard
that refuses each pending pin by name, with a planted test; (c) one OI-283
row per pending pin with its reason and later task. The owner's exact words,
relayed by the advisor at 20:14 on 2026-11-22, were: "Yea to both". The
first of the two items answered was decision 0093; the second was this
question, with the conditions above.
