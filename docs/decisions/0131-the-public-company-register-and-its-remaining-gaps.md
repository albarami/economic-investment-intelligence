# Decision 0131: The public company register and its remaining gaps

| | |
|---|---|
| Status | Accepted by the owner, 2026-11-26 |
| Date | 2026-11-26 |
| Owner | The owner |
| Amends | Decision 0023 items 12 and 13; tasks S2-T51, S6-T21, S6-T40 and S7-T10; open items OI-141 and OI-142; adds S2-T52 |
| Purpose | Record the public register's inclusion, assign its remaining collection gaps and date the two scheduled starts. |
| Read first | Decisions 0022, 0023 items 12, 13, 15 and 16, 0026 and 0074; document 06; CLAUDE.md rules 3 and 11; TASKS.md S2-T36 and S2-T49 |

## Context

The owner has directed that the public, real company register be included and
that the remaining collection gaps have tasks and statuses. The counts are kept
beside the files outside the repository. This record contains no register values.

## The owner's words

> its public data shouldnt be refused. now collect all and lets fix this gap. we already agreed the only data that is private is the ones we created synthetic of, so dont worry on privacy. build this system the way i wanted it in the first place and dont drop in value or quality.

## Decision

1. The company register, from the commerce ministry's public business map and
   the financial centre's public register, is public and real. A check that
   refuses it is a fault to fix under a fix reviewed by a different maker. No
   release check or review is waived. Finish M1 review, then register staging,
   then the full S2 audit. The first release built after staging carries the
   companies, and no later release leaves them out.
2. The privacy rules of document 06, including its cell rules and attack tests,
   protect the synthetic employment, wage, residence and movement records.
   They remain unchanged.
3. Collect the remaining gaps of the 13 November extraction: establishments
   the public map does not draw as points; the empty branches field needed by
   S6-T21 (OI-142); and openings and closures by date with monthly re-collection
   so two snapshots exist (S7-T10, decision 0023 item 12). None holds the S2
   gate. S2-T52 owns the first gap in the background lane; S6-T21 owns the
   branches follow-up; S7-T10 owns the dated openings and closures and monthly
   snapshot use. Under the owner's note of 13 November, the advisor collects
   from the public pages as a visitor's browser receives them, slowly and
   without sign-in, into the private register folder. If that seat cannot do
   it, the advisor tells the owner and the owner's designated alternate
   advisor seat collects it; the lead does not collect. The advisor seat
   keeps the monthly snapshots (OI-141); the next is due 2026-12-13.
4. The 13 November read conditions remain unchanged: the lead's shell, release
   build and running product may read the register files; the public repository,
   briefs, fixtures and worker tools may not. Tests use the invented stand-in.
   CLAUDE.md rules 3 and 11 and decisions 0022 and 0074 remain unchanged.
5. Listing rents (S6-T40) and dated imagery history (S2-T51) stay in the plan,
   with their run dates recorded. The lead schedules the imagery acquisition
   for 2026-11-27 in the lead's shell once its pending different-maker
   confirmation is in; it has not run. The listing-rents build is scheduled
   to start on 2026-11-28 on seats S2 and S3 cannot use; its status stays
   queued. Both dates are Qatar dates and scheduled starts, not completed runs.

## Consequences

S2-T36 and S2-T49 retain the existing register acquisition and staging work;
this record creates no parallel register implementation. S2-T52 is queued in
the background lane. S6-T21 and OI-142 retain the branches gap as pending;
S7-T10 retains dated openings and closures and monthly snapshot use as pending.
Each of these three collection gaps is outside the S2 gate. OI-141 is answered
by the advisor's retention responsibility and next due date. The order and
release inclusion of item 1 remain required; no gate, review or privacy check
is removed. No collection or build completion is claimed here.

## Sources

- The owner's decision of 2026-11-26, relayed by the advisor: the exact words
  above and its five numbered directions. The private original is retained
  locally outside the repository documents; it is the authority for this record.
- [Decision 0022](0022-real-register-companies-with-a-synthetic-world.md),
  [decision 0023](0023-ten-additions-and-the-data-rule.md) items 12, 13, 15 and 16,
  [decision 0026](0026-public-sources-used-in-full-locally.md) and
  [decision 0074](0074-company-level-fields-of-the-owners-company-workbook.md)
  supply the unchanged background conditions.
- The lead's dated task brief supplies the Qatar scheduled starts in item 5.
