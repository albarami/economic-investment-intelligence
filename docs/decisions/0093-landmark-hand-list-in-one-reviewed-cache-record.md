# Decision 0093: Landmark hand list in one reviewed cache record

| | |
|---|---|
| Status | Proposed; owner acceptance required before code merge (S2-P53 ruling R9) |
| Date | 2026-11-22 |
| Scope | Document 04 PUB-106; decision 0064 item 25; S2-T20 |

## Context

Decision 0026 item 5 keeps records, names and values without an open licence
out of the public repository. Decision 0059 item 3 keeps sources in local use
regardless of their terms. S2-P53 rulings R0 and R9 require one placement for
all publishers, following the local district-alias record of S2-T22.

## Proposed decision

1. Place the landmark hand list in the single uncommitted, independently
   reviewed `review/landmark_heights.yaml` record under the public cache.
   This replaces the committed-list placement in PUB-106 and clarifies the
   hand list restored by decision 0064 item 25. The committed review file is
   an empty format sample and carries no source record, name or value.
2. Every publisher uses that same record and loader. No source or height is
   removed by this placement change. Decision 0026 item 5 and decision 0059
   item 3 continue to apply without a new licence admission step.
3. No value, calculation, rule, gate or check is changed by this decision.
   Citation snapshots and their receipts remain uncommitted. Independent
   review and the source chain remain required. S2-T20 and gate condition
   C-20 remain open until their existing evidence requirements are met.

## Evidence and consequences

The task brief and lead rulings R0 and R9 are the authority for this proposed
placement. Offline implementation evidence is recorded under S2-P53 in
PROGRESS.md. It establishes no live selection, tie, coverage or source reading.
The build may proceed before acceptance; merge waits for owner acceptance.
