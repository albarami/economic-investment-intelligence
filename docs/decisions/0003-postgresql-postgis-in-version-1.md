# 0003 — PostgreSQL 18 with PostGIS in version 1

| | |
|---|---|
| Status | Accepted, 2026-11-11 |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Record why PostgreSQL enters version 1 as the serving store, what it must visibly deliver, and the limits it runs under. |
| Read first | [02_ARCHITECTURE.md](../02_ARCHITECTURE.md), [0004](0004-duckdb-build-engine-and-embedded-standby.md), [0011](0011-store-selection-at-start-up.md) |

## Context

- Owner decision 11: PostgreSQL and a graph are added from the start where they add visible value, and the result must not be computation-heavy or costly.
- The first design panel (2026-11-11) deferred PostgreSQL to deployment: in a one-presenter demonstration it would add a server for no visible gain.
- Nine later reports fed the decision. One of them, the architecture research, measured four options: A, embedded DuckDB and files; B, PostgreSQL serving with DuckDB building; C, option B plus vector, H3 and graph extensions; D, option B plus a graph server.

## Decision

1. PostgreSQL 18 with PostGIS is in version 1 as the serving store: option B, with option A kept as the standby.
2. It must buy three visible things: the oversight seat with a live ledger; separation of the two company seats by row-level security; a read-only mirror of the release that reviewers open in a standard GIS tool.
3. Limits: one database; one schema per release; at most two releases loaded; no extension beyond PostGIS; no spatial predicate in tool queries; an application role that does not own tables; development against PostGIS 3.6.
4. On the build machine the stage path prefers a native PostgreSQL service. Docker Compose stays the path for CI and deployment (open item OI-10).

## Evidence

Measured on the build machine with a 7.5 million-row random synthetic test release (architecture research, 2026-11-11). The test image carried PostgreSQL 18.6 with PostGIS 3.7.0; development targets PostGIS 3.6. Data directories were RAM-backed, so disk effects are absent.

| Measure | PostgreSQL 18.6 | For comparison |
|---|---|---|
| First start, including database creation | 1.3 s | restart 0.2 s |
| Memory at idle | about 32 MB | |
| Load of the release | about 5 s (2.2 s copy, 2.7 s indexing) | |
| Size on disk | 576 MB | 34.7 MB as Parquet; 90.5 MB as a DuckDB file |
| Four site queries, medians over 300 random pins | 0.4 to 1.0 ms | DuckDB 0.7 to 3.0 ms |
| Sixteen clients, three site questions each | 888 bundles per second | DuckDB 563 |
| One whole-country aggregate | 104 ms median; 229 ms at the 95th percentile | DuckDB 4.3 ms |
| One ledger row; one notification | 0.31 ms; 1.45 ms median | |

- The 95th percentile is the feasibility judge's reading of the same benchmark files (2026-11-11).
- Row-level security, same research: with one policy on a three-row table, company A saw 2 rows, company B saw 1 and the table owner saw all 3. Hence the rule that the application role owns nothing.
- A role with `SELECT` only was refused `INSERT`, `CREATE TABLE` and `DELETE`. A read-only session default can be changed by the session, so privileges are the lock.
- PostGIS 3.7.0 was released on 2026-10-30. The in-country managed PostgreSQL services listed PostGIS 3.6 for PostgreSQL 18, and Ubuntu's archive offered 3.6.2 (provider pages and package index, checked 2026-11-11). Neither service listed an H3 extension.
- The research's conclusion: neither engine is a compute cost at this scale. The choice is about what people can see and how the product is deployed.
- Effort is estimated, not measured: 6 to 9 working days (architecture research) against 11 to 15 for a reduced package (feasibility judge).

## Consequences

- One more process on stage. The embedded standby and selection at start-up take it off the critical path.
- Whole-country aggregates are computed at build time; tool queries read small sets of units.
- Tool SQL stays inside a portable subset so that both engines agree, checked by a parity case with every tool.
- If time slips, company separation is cut first and the oversight seat last, falling back to the local ledger view. If both go, PostgreSQL remains only as the reviewer mirror and the parity proof.
- Which database platform the operating bodies themselves run is unconfirmed (architecture research: unverified). No document may claim fit.

## What would change this decision

- Fewer than two of the three visible things surviving the cut order. The minister-impact judge's condition is that PostgreSQL then leaves version 1 and the embedded store serves alone. The owner decides.
- A deployment target that cannot run PostgreSQL 18 with PostGIS 3.6.
- Measurements on disk-backed storage that contradict the table above.

## Open questions and assumptions

- OI-10: native service inside Ubuntu, or Docker Desktop with WSL integration. Preflight uses whichever answers; CI always uses a service container.
- This record makes no ASSUMPTION.

## Sources

- EII architecture-options research (measurements), feasibility-and-cost judgement, minister-impact judgement and engineering-and-delivery-risk judgement, 2026-11-11 (project records held by the owner).
- PostgreSQL Global Development Group, versioning policy, https://www.postgresql.org/support/versioning/ and release notes for version 18, https://www.postgresql.org/docs/18/release-18.html ; PostGIS project, news, https://postgis.net/news/ ; retrieved by the research on 2026-11-11.
- Microsoft Learn, extension versions for Azure Database for PostgreSQL, https://learn.microsoft.com/en-us/azure/postgresql/extensions/concepts-extensions-versions ; Google Cloud, extensions for Cloud SQL for PostgreSQL, https://docs.cloud.google.com/sql/docs/postgres/extensions ; retrieved by the research on 2026-11-11.
