# 0011 — Store selection at start-up

| | |
|---|---|
| Status | Accepted, 2026-11-11 |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Record why the store is chosen once at start-up, why one presenter control may switch it, and why nothing switches it automatically. |
| Read first | [02_ARCHITECTURE.md](../02_ARCHITECTURE.md), [13_DEPLOYMENT_AND_OPERATIONS.md](../13_DEPLOYMENT_AND_OPERATIONS.md), [0003](0003-postgresql-postgis-in-version-1.md), [0004](0004-duckdb-build-engine-and-embedded-standby.md) |

## Context

- Version 1 has two stores that hold the same release: PostgreSQL and an embedded DuckDB file. On stage PostgreSQL may be unavailable.
- The architecture research proposed automatic failover. Two failed one-second probes, or any tool call over 300 ms, would move reads to the embedded file, spool ledger rows and replay them later, with automatic recovery after three good probes.
- On 2026-11-11 the Linux `docker` command on the build machine was a dangling link while Docker Desktop itself was running. Databases that were already running kept answering.

## Decision

1. The store is chosen once, at start-up, by the preflight check, and that selection is authoritative for the invocation: PostgreSQL when it answers and passes its checks; the embedded reader, with a warning that names the reason, when PostgreSQL does not answer. `./eii up` never starts a database: it serves from the store that preflight found, so preflight and start-up cannot disagree. Starting the database is the separate explicit command `./eii db-up`; `./eii db-down` stops it.
2. `./eii up --embedded` starts without contacting PostgreSQL.
3. One presenter control switches reads to the embedded reader, one way, at a request boundary. One answer never mixes stores.
4. A local SQLite ledger holds ledger rows while PostgreSQL is away, and the oversight seat shows "paused".
5. There is no automatic failover in the middle of a request and no switch triggered by latency.

## Evidence

- Feasibility judge (2026-11-11): the proposed 300 ms trip point sits just above PostgreSQL's own measured 229 ms at the 95th percentile on one query of the same benchmark, so the store could flip back and forth during a session. The judge called the failover the most stage-fragile code in the proposals and dropped it.
- Architecture research (build machine, 2026-11-11): the embedded file opened in 0.02 to 0.05 s, so keeping it open at every start costs nothing; a ledger insert took 0.31 ms.
- Same research: Docker's control path failed in three ways within 50 minutes (the command missing, calls of about 24 s through the socket, lost interoperability with the host) while PostgreSQL kept answering on its loopback port. Control paths failed; running databases did not.
- Both engines answered the site questions in 0.4 to 3 ms at the median, so the standby is not a slower mode.
- The start-up logic itself has not been run: the research did not start the Compose file end to end, and a native PostgreSQL service was not tested.

## Consequences

- A PostgreSQL failure during a session costs one failed request and one presenter action. This is rehearsed: the slice S11 gate asks for three rehearsals, one with PostgreSQL stopped and one offline.
- While the embedded reader serves, the live ledger, saving briefs, company separation and the reviewer mirror are paused. Release facts are unchanged.
- Local ledger rows are replayed only at a later start-up, idempotently.
- A PostgreSQL that answers but fails a security check stops the start. It is never a silent fall-back.
- The parity suite carries the weight: the switch is safe only because both stores give identical facts.

## What would change this decision

- A deployment with availability targets and no presenter. Availability then belongs to the database layer, for example a managed service, and not to failover written in the application.
- Measurements that show a trip point with a wide margin over normal latency, together with a real need for unattended operation.
- PostgreSQL leaving version 1 ([0003](0003-postgresql-postgis-in-version-1.md)): the selection logic disappears.

## Open questions and assumptions

- OI-10: where PostgreSQL runs on the build machine. Preflight uses whichever answers.
- ASSUMPTION (shared with document 13): the switch is one-way for the session; returning to PostgreSQL needs a restart after the session. A two-way control is the flapping risk this record removes.

## Sources

- EII architecture-options research (measurements and observed incidents) and feasibility-and-cost judgement, 2026-11-11 (project records held by the owner).
- Master design, component decisions (project record held by the owner, 2026-11-11).
