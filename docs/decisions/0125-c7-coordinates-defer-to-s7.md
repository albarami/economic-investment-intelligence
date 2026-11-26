# Decision 0125: C7 coordinates defer to S7

| | |
|---|---|
| Status | Proposed by the builder, 2026-11-25; different-maker review and acceptance remain pending |
| Date | 2026-11-25 |
| Owner | The owner |
| Amends | Decision 0094 items 1, 2 and 4; task S2-T09 |
| Purpose | Defer the C7 example coordinates to the slice that can derive and source-check them, without inventing values or weakening the S7 gate. |
| Read first | Document 07 MTH-03 and C7; decisions 0094 and 0115; OPEN_ITEMS.md OI-283; TASKS.md S2-T09 and S7-T05 |

## Context

Decision 0094 item 1 leaves every C7 setting, including `c7.coordinates`, owed
at slice S2. Decision 0115 item 2 supplies the four landmarks' reviewed
district member keys, and item 3 defines each landmark point as the point on
surface of the union of its member polygons. The committed
`showcase_gazetteer.yaml` rows contain those members but no latitude or
longitude. `places/stage.py` derives the six-decimal points from the selected
boundary archive at run time. Neither the decision nor the committed review
rows contain coordinate values that can be copied into the C7 configuration.

## Decision

1. **One more S7 deferral.** `c7.coordinates` joins the five pins of decision
   0094 item 1 in `S7_DEFERRED_PINS`. At gate S2 it is accepted pending only
   when its source-check row's `unpinned_reason` begins `OI-283: `. Every
   other pending pin keeps the existing rule. The S7 branch is unchanged and
   refuses `c7.coordinates` by name while it remains pending.
2. **The later task and evidence.** Task S7-T05 derives the four coordinate
   pairs from the selected `bnd_hdx` district polygons under decision 0115
   item 3, checks them against that source and records their lineage and
   settings before writing the pin. No coordinate is invented or transcribed
   from an uncommitted cache. The existing closed pending representation
   remains empty values and empty lineage, never a stand-in.
3. **OI-283 and the generation configuration.** OI-283 holds a dedicated
   `c7.coordinates` row with this reason and task S7-T05. The generation
   configuration and source-check row use the same OI-283-prefixed reason.
   The existing `configuration_pending` rule excludes the enlarged deferral
   set; no new pending representation or bypass is added.

## Evidence

The guard tests use invented records only. They exercise S2 acceptance solely
with the `OI-283: ` prefix, S7 refusal by pin name, the committed OI-283 row,
and configuration readiness when only deferred pins remain. This record claims
no coordinate value, live build, independently reviewed source value or passed
gate.

## Consequences

- The S2 assembly no longer treats `c7.coordinates` as a non-deferred
  configuration blocker; all other live inputs, source reviews and governed
  card writes remain owed.
- The slice S7 gate fails until S7-T05 supplies the checked coordinates, just
  as it does for the five pins of decision 0094.

## What would change it

A later accepted decision supplying committed, source-checked coordinate values
before the S2 gate would allow the pin to be bound instead and would amend this
record and decision 0094 accordingly.
