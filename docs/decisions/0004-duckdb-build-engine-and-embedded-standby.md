# 0004 — DuckDB as build engine and embedded standby

| | |
|---|---|
| Status | Accepted, 2026-11-11 |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Record why DuckDB builds every release and also stands by inside the API process as a read-only reader of the same release. |
| Read first | [02_ARCHITECTURE.md](../02_ARCHITECTURE.md), [0003](0003-postgresql-postgis-in-version-1.md) |

## Context

- The custodian plane must build a synthetic world and a release of millions of rows in seconds, reproducibly, on one machine.
- The product needs a second engine: as the standby when PostgreSQL is away, and as the independent recomputation behind capability S7 of the brief ("two engines, one answer").
- DuckDB 2.0.0 was released on 2026-10-21, three weeks before this decision.

## Decision

1. DuckDB 2.0.x with the `spatial` and `h3` extensions is the build engine for the public pack, the synthetic world and the release.
2. The same engine, embedded in the API process, is the read-only reader of the same release (`release.duckdb`). It is the standby store.
3. Retreat pin: 1.5.x. The choice between 2.0.x and 1.5.x is confirmed at slice S1.
4. Parquet stays the source of truth. The DuckDB file is disposable and is rebuilt by the loader.
5. Extensions are used at build and load time only. The embedded reader loads none; H3 arithmetic at request time runs in Python.

## Evidence

Architecture research, build machine, 2026-11-11, on the same 7.5 million-row random synthetic test release as [0003](0003-postgresql-postgis-in-version-1.md):

- Build of the release: 0.85 s. DuckDB file 90.5 MB; Parquet 34.7 MB. Open: 0.02 to 0.05 s. The Python process held 587 MB after a 16-thread run.
- One whole-country aggregate (780,000 rows grouped to 4,119 parents): 4.3 ms, against 104 ms in PostgreSQL with default settings. This is why DuckDB builds and pre-aggregates and PostgreSQL serves.
- Site queries: medians of 0.7 to 3.0 ms; 563 bundles per second with sixteen clients.
- DuckDB accepted the portable form `cell = ANY(list)`, so one SQL text can serve both engines.
- Through DuckDB's PostgreSQL extension, 4.68 million rows were copied into PostgreSQL in 1.64 s, and a DuckDB `GEOMETRY` column arrived as a PostGIS geometry column with no conversion.
- Two changes broke code written from memory during the tests: Python relations no longer have `fetchone()`, and `postgres_execute` accepts one statement per call.

DuckDB project pages, retrieved by the research on 2026-11-11:

- 2.0.0 is a long-term-support release, supported until at least October 2027. The announcement suggests waiting for the first patch release for mission-critical work; none existed on 2026-11-11.
- Files written by 2.0 cannot be read by earlier versions.
- Concurrency: one read-write process, or several read-only processes.
- An extension needs the network for its first install and is cached locally afterwards.

## Consequences

- The engine version can change without migrating data: delete `release.duckdb` and reload from Parquet.
- Builders must read the DuckDB 2.0 documentation before writing code; slice S0 delivers reference notes.
- Extension files must be installed while the network is available and must be reachable inside the build sandbox.
- The standby is only as good as the parity suite, so every tool ships with a parity case.
- DuckDB does not run in the browser: aggregation and suppression happen before release.

## What would change this decision

- A regression in 2.0.x found at slice S1: retreat to 1.5.x.
- Parity that cannot be held inside the portable subset: the standby role is revisited, not the build role.
- PostgreSQL leaving version 1 ([0003](0003-postgresql-postgis-in-version-1.md)): DuckDB then serves alone, which this design already supports.

## Open questions and assumptions

- ASSUMPTION (stated in the architecture document): extension files live in a project-local directory inside the sandbox mounts; the path is fixed at slice S1.
- No open item of the master design is specific to this record.

## Sources

- EII architecture-options research (measurements) and technology-stack research, 2026-11-11 (project records held by the owner).
- DuckDB, announcement of version 2.0.0, https://duckdb.org/2026/10/21/announcing-duckdb-200 ; documentation pages on concurrency, https://duckdb.org/docs/2.0/connect/concurrency.html , on installing extensions, https://duckdb.org/docs/2.0/extensions/installing_extensions.html , and on the PostgreSQL extension, https://duckdb.org/docs/2.0/core_extensions/postgres/overview.html ; retrieved by the research on 2026-11-11.
