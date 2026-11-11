# 0005 — Economic graph as tables; Neo4j deferred

| | |
|---|---|
| Status | Accepted, 2026-11-11 |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Record why the economic graph ships in version 1 as node and edge tables, why a graph server waits, and what would bring one in. |
| Read first | [02_ARCHITECTURE.md](../02_ARCHITECTURE.md), [0003](0003-postgresql-postgis-in-version-1.md) |

## Context

- Owner decision 11 asks for a graph from the start where it adds visible value.
- Version 1 has real graph-shaped content: the activity spine (commerce activity code, international activity class, public place category), crosswalks, input baskets to tariff lines to origins, co-location pairs, and lineage.
- Nine reports weighed how to hold and query it. Eight advised against a graph server in version 1. The graph-value research advised for one, as a read-only exploration engine, for credibility and extensibility and not for speed.

## Decision

1. The graph is content, not an engine: two release tables, `graph_node` and `graph_edge`.
2. Limits: at most four steps per query and fifteen nodes per drawn path. An edge joins two Public ends, or it is lineage. No firm-level edges.
3. Traversal is recursive SQL inside the portable subset. Paths are drawn with SVG, not a second WebGL canvas.
4. A Neo4j server is deferred to backlog item L5: an optional loader, with the same typed graph-query cases and result contract, implemented by engine-specific templates and checked for result parity. Apache AGE and native graph queries in PostgreSQL are dropped.
5. The owner may overrule this record (open item OI-12). The edge tables are the contract, so adopting a graph server later changes no content.
6. Trigger to adopt: a real, lawful relationship feed with paths deeper than four steps.

## Evidence

Measured by the architecture research on the build machine, 2026-11-11: one seeded stress graph of about 195,000 nodes and 270,000 edges on every engine, with identical result checksums. Medians:

| Question | PostgreSQL 18, recursive SQL | Neo4j Community 2026.10.2 | DuckDB 2.0 |
|---|---|---|---|
| Follow links up to four steps from a known node | 0.38 ms | 1.11 ms | 2.6 ms |
| Everything reachable below a node | 0.41 ms | 1.11 ms | 3.5 ms |
| Shortest link between two nodes within eight steps | 32 ms | 1.3 ms | 7 ms |

- In short: bounded traversals took 0.4 ms in PostgreSQL against 1.1 ms. Neo4j won only pairwise path finding, 1.3 ms against 32 ms, which no version 1 question needs.
- Cost of the server, same research: 7.3 s to start (8.1 s with the bundled plugins), about 0.6 to 0.9 GB of memory, a 516 MB empty store, a second query language and a copy job. Loading 195,000 nodes and 250,000 relationships took 5.7 s, so a later switch is cheap.
- Neo4j documentation and the running server, checked 2026-11-11: Community Edition refused `CREATE ROLE` and `CREATE DATABASE`, so it has no fine-grained access control and every signed-in user has full access; it reported usage data by default. The licence file in the image is GNU GPL version 3.
- Scale: the graph research built its public prototype graph of 5,123 nodes in 0.07 s, and measured 1,000 two-hop expansions on a graph of 200,000 nodes and 1,000,000 edges in 0.03 s in plain Python. The engine does not change any speed a user can see.
- No real relationship feed exists. On synthetic links, network algorithms would return what the generator planted.
- Apache AGE on the same graph: 0.75 ms when the pattern started from the known node and 7.5 s when written the other way round; no shortest-path function; preloading it broke `TRUNCATE` in databases without the extension. Native graph queries were absent from the PostgreSQL 19 release candidate.
- The stress graph held firm-level links for measurement only. Version 1 holds none.

## Consequences

- The graph the audience sees (the "understood as" chips, the supplier path, the neighbours chips, the why-path) ships in version 1 with no extra server.
- Path questions between two arbitrary nodes are slow in SQL and are not offered.
- Networks of firms or owners are not drawn, even synthetic ones.
- Item L5 stays cheap because nothing in the two tables is specific to an engine.

## What would change this decision

- The trigger: a real, lawful relationship feed with paths deeper than four steps, for example ownership or group chains. The judges add that a governed service to expose such paths must be approved first.
- The owner overruling under OI-12. If a server is ever run, the feasibility judge's conditions apply: read-only by server setting, usage reporting off, memory capped, and never on the stage path.
- A deployment target that mandates graph queries inside PostgreSQL would reopen the graph-extension question, not this one.

## Open questions and assumptions

- OI-12: a graph server is deferred to L5 by evidence; the owner may overrule.
- This record makes no ASSUMPTION.

## Sources

- EII architecture-options research (measurements), graph-value research, feasibility-and-cost judgement and minister-impact judgement, 2026-11-11 (project records held by the owner).
- Neo4j, release notes for 2026.10, https://neo4j.com/release-notes/database/neo4j-2026-10/ ; usage data page, https://neo4j.com/docs/usage-data/ ; licensing page, https://neo4j.com/licensing/ ; retrieved by the research on 2026-11-11.
- Apache AGE, releases, https://github.com/apache/age/releases ; retrieved by the research on 2026-11-11.
