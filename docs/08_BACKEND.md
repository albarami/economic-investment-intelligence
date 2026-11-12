# 08 — Backend

| | |
|---|---|
| Status | Draft v0.3, amended by decisions 0016, 0017 and 0018 on 2026-11-12 |
| Date | 2026-11-12 |
| Owner | albarami |
| Purpose | Specify the Python packages, the store interface, PostgreSQL, the loader, the closed tool list, the playbooks' calls, the API, seats, the ledger, routing, drawn areas, case sample files and the runtime rules of the serving plane precisely enough to generate tests from. |
| Read first | [02 Architecture](02_ARCHITECTURE.md), [03 Data contracts](03_DATA_CONTRACTS.md), [06 Privacy and disclosure control](06_PRIVACY_AND_DISCLOSURE_CONTROL.md), [07 Economic methods](07_ECONOMIC_METHODS.md), [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) |

## In brief

- Three Python packages in one `uv` workspace: `eii_core` (shared), `eii_custodian` (build plane), `eii_product` (serving plane). The product never imports custodian code and has no path to the vault.
- Every tool reads the release through one store interface. Tool SQL is a small portable subset, checked by a lint step, run with parameters only, on PostgreSQL and on an embedded DuckDB file. A parity case for every tool proves both engines return identical facts.
- PostgreSQL holds one schema per release, plus the `app` schema for seats, briefs, the ledger and the egress record. Three roles support query isolation after a seat is selected, not tenant authentication; the application role owns nothing and has no `SELECT` on application base tables.
- A manifest-driven loader is the only way data enters a serving store. It rejects any table the manifest does not name.
- A closed, versioned list of typed tools and the thirteen deterministic playbooks of document 09 cover the seven journeys, three services and four cases of [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md); with the template writer they give a full brief with no model. The API streams plan steps, stage directives, cards and narrative as server-sent events, evidence first; the brief itself is sent only after the accounting gate has passed on the complete brief.
- An area is drawn, set by a radius, or made by walk or drive time from any point, by hour. Public points and Simulated layers use its exact shape; figures from the four protected record types snap to whole release units before any is read. Drawn shapes and case sample files live only in the API process's memory, for one session and seat.
- New tools, layers and routes serve presence counts by hour and event day, crowd density, traffic by hour, the ranking and its reverse, similar areas, reachable access, monthly periods and "what changed", the labour-market view, openings and closures, firm lists, FDI projects and the agency's records. Each returns facts with provenance and lineage, and no route computes a number outside `eii_core.calc`, the release build or a listed fixed read function (BE-116).
- The product serves exactly one mounted release, named by `EII_RELEASE_DIR`. A protected build writes one release for its selected parameter set; a `public_only` build has no parameter set. No route, setting or switch selects a parameter set at run time.
- The store is chosen at start-up. A presenter switch moves to the embedded reader at a request boundary. There is no automatic failover in the middle of a request.

## 1. Scope

This document covers the serving plane (`product/`) and the shared library (`core/`). It names the custodian modules only to fix the import boundary; their behaviour is in [04](04_PUBLIC_DATA_PACK.md), [05](05_SYNTHETIC_WORLD_AND_SIMULATION.md) and [06](06_PRIVACY_AND_DISCLOSURE_CONTROL.md). The model loop, prompts, validator and evaluation harness are in [09](09_AI_ASSISTANT.md). Table columns and the manifest format are in [03](03_DATA_CONTRACTS.md); where a column name below differs from document 03, document 03 wins. Deployment, the compose file and the stage machine are in [13](13_DEPLOYMENT_AND_OPERATIONS.md). Terms are in the [glossary](GLOSSARY.md).

Version 1 covers the whole initiative ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md)) with the public additions of [decision 0017](decisions/0017-public-data-additions-and-public-splits.md). This document fixes the names of the new tools, the calls of every playbook bundle and the new stage directives; document 09 names the playbooks, the evidence they gather and the catalogue keys. The release tables added by the two decisions carry the names of document 03 section 7.2: among them `road_link`, `presence_count`, `flow_hourly` and `traffic_hourly` (which replace `presence_index`, `flow_od` and `speed_factor`), `month_change`, `firm_list`, `fdi_projects`, `pub_investqa_record` and the `pub_` tables of the 77 portal datasets. Where a table name here differs from document 03, document 03 wins.

Library versions follow the master design and are confirmed at the spike (slice S1) with written retreat pins. PostgreSQL 18, DuckDB 2.0 and FastAPI's server-sent-event support are newer than most coding-assistant training data: builders must read the current official documentation before writing code against them.

## 2. Package layout and the import boundary

All three packages use a `src` layout: `core/src/eii_core/`, `custodian/src/eii_custodian/`, `product/src/eii_product/` (ASSUMPTION: `src` layout is the `uv` workspace default and stops tests importing from the working tree by accident).

### 2.1 `eii_core` (shared library)

| Module | Responsibility |
|---|---|
| `provenance` | The four provenance classes, the three evidence statuses plus "not measured", and `least_real(classes)` (Public over Synthetic over Simulated; any Suppressed input makes the composite Suppressed). |
| `facts` | The pinned fact object as a strict Pydantic model; deterministic `fact_id`; the reliability band helper that applies the rule in document 06. |
| `manifest` | Manifest model, canonical hashing, `release_id` check, and the allow-list of release table names from the master design (section 5.4). |
| `grid` | H3 helpers: frame resolution for a point (9 in Greater Doha, 8 elsewhere), cell to parent, distance rings, and a polygon or circle to frame cells under the containment rule of BE-84. No database access. |
| `shapes` | The canonical form and SHA-256 of a drawn polygon; its validity checks (a simple polygon inside the frame, within the vertex and size limits fixed at the slice S2 gate); exact point-in-shape tests for Public points; the representative point of a shape for travel times (ASSUMPTION). No database access. |
| `ids` | All five synthetic identifier formats (`SYN-E-…`, `SYN-L-…`, `SYN-G-…`, `SYN-P-…`, `SYN-F-…`) and the complete `SYN-[ELGPF]-` pattern used to reject them in released data. The pattern exempts exactly one place, the `firm_key` column of `firm_list`, which accepts only a released firm key of the `SYN-E-` form or the literal `withheld`; a match in any other column of any table, a `SYN-E-` value included, is rejected ([03](03_DATA_CONTRACTS.md) DAT-83, DAT-140). |
| `text` | Normalisation for matching: Unicode NFKC, case folding, Arabic normalisation (unify alef variants, remove diacritics and tatweel, unify final yaa and taa marbuta forms). ASSUMPTION: these steps are pending native review (OI-09). |
| `situations` | The four situations (`weekday_lunch`, `weekday_evening`, `friday_evening`, `ramadan_iftar`) and the `summer` switch rule; the closed hour, day and month key lists of the release (document 03), the day keys including the three event days of decision 0016. |
| `calc` | The request-time part of the calculation layer (MTH-01, MTH-02): sums over release units, derived statistics, comparisons (difference, ratio, rank, direction facts) and the break-even calculator. Every displayed number is produced by deterministic tested code in `eii_core.calc`, the release build, or a fixed application-schema read function listed by the data contracts and covered by tests. Nothing else computes, rounds or compares a number, and no model ever does (BE-104). Under decision 0016 it also apportions released Public statistics and Simulated counts to a drawn shape, and computes crowd density, ranks, fits, similar-area ranks, reachable-access scores, monthly differences and trends, projections marked as projections, case-file figures, travel-time comparisons and the break-even calculator with an optional incentive package; each has a method card in document 07. |

### 2.2 `eii_custodian` (build plane)

`publicdata/` (fetchers and page parsers, document 04: the portal on both its hosts, the FDI dashboard and the agency's pages), `worldgen/` (synthetic world, document 05), `linkage/`, `privacy/` (document 06; it also releases the presence counts and the firm list), `mobility/` (simulator, document 05, and the traffic assignment that `./eii build-release` runs on the released flows, ARC-133), `release/` (writes Parquet, manifest, story-pin catchments and routing tiles). Only this package may open `data/vault/`; the traffic assignment reads only the released flows and the routing graph.

### 2.3 `eii_product` (serving plane)

| Module | Responsibility |
|---|---|
| `config` | Reads the pinned environment variables (section 11.2); no other configuration source for secrets. |
| `preflight` | Start-up checks and store selection (section 11.2); used by `./eii preflight` and `./eii up`. |
| `store/` | `protocol.py` (the interface), `postgres.py`, `embedded.py`, `sql/` (one file per named query), `lint.py`, `normalise.py`, `parity.py`, `loader.py`, `reviewer_views.py`. |
| `tools/` | `registry.py`, one module per tool of section 6.2, `areas.py` (area ids and snapping), `routing.py` (pyvalhalla with the hourly link speeds), `fact_builder.py`. |
| `assistant/` | `playbooks/` (the playbooks of document 09 and their evidence bundles) and `templates/` (template writer and status templates); the other sub-folders (parser, router, model loop, validator, memo, egress scan, providers) are specified in document 09. |
| `ledger/` | `postgres.py`, `local.py` (SQLite local ledger), `egress_store.py`, `oversight.py`, `seed.py` (seeded synthetic history). |
| `api/` | FastAPI application, routes, server-sent events, seat handling, presenter routes, the drawn-shape and case routes (section 8.3), `session_store.py` (BE-109), static files (built front end, PMTiles, glyphs). |

### 2.4 Requirements

| ID | Requirement |
|---|---|
| BE-01 | `eii_core` imports neither `eii_custodian` nor `eii_product`. |
| BE-02 | `eii_product` never imports `eii_custodian`, directly, through `importlib`, or through a dependency declared in its `pyproject.toml`. |
| BE-03 | `eii_custodian` never imports `eii_product`. |
| BE-04 | An import-boundary test parses every Python file of the three packages and fails on any forbidden import, including string arguments to `importlib.import_module`. It runs in `./eii test` and in CI from slice S0. |
| BE-05 | No module of `eii_product` contains the path segment `vault`, and at start-up the product refuses to run if `EII_RELEASE_DIR` resolves inside `data/vault/`. |
| BE-06 | The front end (`web/`) reaches the backend only over HTTP; no Python module serves data to it by any other route. |
| BE-102 | `eii_product` never imports or invokes the typed-decision gateway and does not read `EII_DECISION_PROVIDER` or `JEV_PRO_API_KEY`; those variables belong only to explicit offline build/evaluation scripts. The separate `gateway/` package (`eii_gateway`) is imported only by tooling under `evals/` and `scripts/`; nothing under `core/`, `custodian/` or `product/` imports it. |
| BE-109 | `api/session_store.py` holds drawn shapes and case sample files in process memory only, keyed by the verified `eii_seat` session and its seat. It has no disk, database, cache or log path. An entry is never visible to another session, another seat or the oversight seat, and every entry is dropped when its session ends, at `./eii down` and at every restart. No `app` table holds either (DAT-149). |

## 3. The store interface

### 3.1 The protocol

```python
Param = int | str | bool | datetime.date | list[int] | list[str]

class ReleaseStore(Protocol):
    engine: Literal["postgres", "embedded"]
    release_id: str                      # full content hash from the manifest

    def fetch(self, query: QueryName, params: Mapping[str, Param]) -> QueryResult: ...
    def ping(self, timeout_s: float) -> StoreHealth: ...
    def close(self) -> None: ...

@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[NormalValue, ...], ...]   # already normalised (section 3.4)
```

`QueryName` is an enumeration generated from the files in `store/sql/`. A query file starts with a header that the lint step and the adapters read:

```sql
-- name: unit_pay_sums
-- params: units list[text], period text, measure text, housing text
-- returns: unit_id text, period text, measure text, housing_class text, band_from text, band_to text, earner_count bigint, wage_bill numeric
-- order: unit_id, period, measure, housing_class, band_from, band_to
SELECT p.unit_id, p.period, p.measure, p.housing_class,
       p.band_from, p.band_to, p.earner_count, p.wage_bill
FROM resident_pay AS p
WHERE p.unit_id = ANY(:units) AND p.period = :period
  AND p.measure = :measure AND p.housing_class = :housing
ORDER BY p.unit_id ASC NULLS LAST, p.period ASC NULLS LAST,
         p.measure ASC NULLS LAST, p.housing_class ASC NULLS LAST,
         p.band_from ASC NULLS LAST, p.band_to ASC NULLS LAST
```

Tables are named without a schema. The PostgreSQL adapter sets the release schema per transaction with `SELECT set_config('search_path', :schema, true)` (PostgreSQL 18 documentation: `is_local` true limits the value to the current transaction). The DuckDB file holds one release in its default schema.

| ID | Requirement |
|---|---|
| BE-07 | Tools read release data only through `ReleaseStore.fetch` with a `QueryName`; no tool, playbook, model output or API input supplies SQL text. |
| BE-08 | Every query file declares `name`, `params`, `returns` and `order` in its header; the adapter rejects a call whose parameter names or types differ from the header, and a result whose column names differ. |
| BE-09 | The PostgreSQL adapter runs every release read in a transaction opened `READ ONLY`, with `search_path` set to the release schema only. |
| BE-10 | The embedded adapter opens the DuckDB file with `read_only=True` (DuckDB 2.0 Python documentation), then sets `enable_external_access` to false and `lock_configuration` to true (DuckDB 2.0 configuration documentation). |
| BE-11 | The embedded adapter loads no DuckDB extension; tool queries need none. |
| BE-12 | Both adapters run in worker threads so the event loop never blocks; the DuckDB adapter uses one cursor per thread as its Python documentation directs (ASSUMPTION: confirm the 2.0 threading guidance at slice S1). |

### 3.2 The portable SQL subset

Tool queries are plain `SELECT` statements over precomputed tables. All spatial work, H3 arithmetic and routing happen at build time or in Python (master design section 4; architecture research measured that DuckDB accepts the portable `cell = ANY(list)` form, 2026-11-11). Allowed constructs (the allow-list):

| Kind | Allowed |
|---|---|
| Statements | One `SELECT` per file; `WITH` (common table expressions); `WITH RECURSIVE` only in files whose name starts with `graph_`. |
| Clauses | `FROM`, `JOIN … ON` (`INNER`, `LEFT`), `WHERE`, `GROUP BY`, `HAVING`, `ORDER BY`, `LIMIT` with a parameter or literal, `UNION ALL`. |
| Predicates | `=`, `<>`, `<`, `<=`, `>`, `>=`, `AND`, `OR`, `NOT`, `IN (literal list)`, `= ANY(:param)`, `BETWEEN`, `IS NULL`, `IS NOT NULL`. |
| Expressions | Column references with a table alias, literals, `:name` parameters, `+`, `-`, `*`, `CASE WHEN … THEN … ELSE … END`, `COALESCE`, `NULLIF`, `CAST(x AS t)` where `t` is `BIGINT`, `INTEGER`, `TEXT` or `DATE`. |
| Aggregates | `SUM`, `COUNT`, `COUNT(DISTINCT …)`, `MIN`, `MAX` (public and control tables only; protected tables never release minima or maxima, document 06). |

Forbidden, with the reason:

| Forbidden | Reason |
|---|---|
| `/` and `%` | DuckDB's `/` is float division (`5 / 2` gives `2.5`, DuckDB 2.0 documentation) while PostgreSQL's integer division truncates towards zero (`5 / 2` gives `2`, PostgreSQL 18 documentation); `%` collides with driver placeholders. Ratios are computed in Python with `Decimal`. |
| `::` casts, `SELECT *`, `DISTINCT ON`, `LATERAL`, window functions, `FILTER`, `QUALIFY`, `PIVOT`, `ASOF` | Dialect-specific or unnecessary. |
| `ORDER BY` without explicit `NULLS FIRST` or `NULLS LAST` | DuckDB keeps `NULLS LAST` for `DESC` (DuckDB 2.0 documentation); PostgreSQL defaults to `NULLS FIRST` for `DESC` (PostgreSQL 18 documentation). |
| Any `ST_*`, `h3_*` or other extension function | No spatial predicates in tool queries (master design section 4). |
| `NOW`, `CURRENT_DATE`, `RANDOM` and other volatile functions | Identical questions must return identical answers. |
| Data definition or change (`CREATE`, `INSERT`, `UPDATE`, `DELETE`, `COPY`, `ATTACH`, `INSTALL`, `LOAD`, `PRAGMA`, `SET`), `;` | Tool queries only read. |

| ID | Requirement |
|---|---|
| BE-13 | `store/lint.py` parses every file in `store/sql/` (parser chosen at slice S0; a tokeniser over the allow-list is the fallback) and fails when a keyword is not in the allow-list, when a word followed by `(` is not an allowed function, or when any forbidden construct above appears. It runs in `./eii test` and in CI. |
| BE-14 | Every `ORDER BY` lists a key that makes the order total (ties impossible), each item with `ASC` or `DESC` and `NULLS FIRST` or `NULLS LAST`. |
| BE-15 | A `graph_` query carries a depth column bounded in its recursive member so that no traversal exceeds four steps (master design section 4). |
| BE-16 | In CI, both engines prepare every query file (`EXPLAIN` with sample parameters) against the fixture release; a query that fails to prepare on either engine fails the build. |

### 3.3 Parameter passing

Lists of cells and units are computed in Python and passed as one list parameter. A drawn shape or an exact outline never reaches SQL: a query receives only the frame cells or the release units the outline touches (`= ANY(:cells)`, `= ANY(:units)`), and for protected tables only the whole units it snaps to; the exact point-in-shape test and any apportioning run in Python (`eii_core.shapes`, `eii_core.calc`). Query files use the neutral placeholder `:name`. The PostgreSQL adapter rewrites it to `%(name)s` for psycopg, which adapts a Python `list` to a PostgreSQL array and recommends `= ANY(%s)` over `IN` (psycopg 3 documentation). The DuckDB adapter rewrites it to `$name` and passes a dictionary (DuckDB 2.0 Python documentation).

| ID | Requirement |
|---|---|
| BE-17 | Placeholders match `:[a-z_][a-z0-9_]*`; the rewrite is a whole-token replacement and is tested for both drivers, including an empty list. |
| BE-18 | Values are always bound as parameters. The only identifier ever composed into SQL is the release schema name, built by BE-33 and passed through `set_config`, never by string formatting. |
| BE-19 | H3 cells are stored and passed as signed 64-bit integers (`BIGINT`), as the architecture research recommends; the loader verifies every cell column is non-negative and fits that type. |

### 3.4 Normalisation and the rounding rule before comparison

Engines return different numeric types for the same SQL (for example PostgreSQL `SUM(bigint)` returns `numeric`). `store/normalise.py` converts every value before it leaves the adapter.

| ID | Requirement |
|---|---|
| BE-20 | Integral values of any engine type become Python `int`. |
| BE-21 | Non-integral numbers become `Decimal` quantised to six decimal places with `ROUND_HALF_EVEN`; a binary float is first converted with `Decimal(repr(value))`. |
| BE-22 | Text is converted to Unicode NFC; dates become `datetime.date`; `NULL` becomes `None`, and `None` equals `None` in comparisons. |
| BE-23 | Derived values (means, shares, ratios, break-even figures) are computed once by `eii_core.calc` (MTH-01) from normalised inputs with `Decimal`, then rounded for display by the fact builder using the rules of document 06; display rounding never happens inside SQL. |
| BE-24 | The rounding rule before comparison has two levels. Query results: integers must match exactly; non-integers are compared after BE-21. Facts: values are compared after rounding to the display precision declared for the fact's unit, which is what the parity suite of document 12 asserts. Released primitives are integers after treatment and therefore always match exactly. |
| BE-25 | Tool queries never `SUM` a binary floating-point column, because summation order may differ between engines; money and counts are integer columns (document 03). |

### 3.5 The parity harness

| ID | Requirement |
|---|---|
| BE-26 | Every registered tool declares at least one `ParityCase(tool, inputs)`; the registry test fails if a tool has none. This holds from the first tool in slice S3. |
| BE-27 | `store/parity.py` runs each case on both stores against the same release and compares the complete tool result field by field under the rounding rule (BE-24), excluding only `engine`, timings and `call_id`. Any difference fails. |
| BE-28 | Every query file is executed by at least one parity case; a coverage check fails on an unexecuted query. |
| BE-29 | From slice S5, a table-level parity check compares, for every manifest table, the row count and a SHA-256 digest of its rows read in primary-key order and serialised canonically after normalisation. |
| BE-30 | The parity run writes a report (cases run, facts compared, facts identical, release id). The Proof room line reads that report; it never recomputes at request time. |

## 4. PostgreSQL

PostgreSQL 18 with PostGIS; develop against PostGIS 3.6 and use no function that exists only in 3.7 (master design section 4). Measured on the build machine with a 7.5 million-row synthetic release (architecture research, 2026-11-11): 1.3 s first start, 0.2 s restart, about 32 MB idle, 5 s to load, 576 MB on disk; ledger insert 0.31 ms; notification delivery 1.45 ms median.

Each protected build writes exactly one `protected` release, the one selected by the shared rule
`export_parameter_set` (PRV-05); the unselected protected table set never leaves the custodian
plane. A `public_only` build writes a release with no Protected or Simulated table and no
protected-window field. Two release schemas online can therefore only be two different releases
during a change, never two parameter sets of one window, and the product serves only the release
named by `EII_RELEASE_DIR` (BE-103).

### 4.1 Schemas

| Schema | Owner | Contents |
|---|---|---|
| `r_<16 hex>` | `eii_owner` | One schema per loaded release: every manifest table plus the loader-materialised `release_manifest`. At most two release schemas online. |
| `app` | `eii_owner` | The seven pinned application tables, the two reference tables of DAT-148 among them, and fixed read functions. The one canonical DDL is [document 03, section 12](03_DATA_CONTRACTS.md#12-the-application-schema-postgresql-only-schema-app). |
| `review` | `eii_owner` | Read-only views for reviewers, generated from the manifest (section 4.4). ASSUMPTION: schema name `review`; the master design names the views but not the schema. |
| `public` | `eii_owner` | PostGIS objects only. |

### 4.2 Roles

| Role | Login | Privileges |
|---|---|---|
| `eii_owner` | yes, used only by `./eii load-release` | Owns every schema, table, view and fixed read function. Not a superuser. |
| `eii_app` | yes, used by the API process | `USAGE` and `SELECT` on release schemas; `USAGE` on `app`; `INSERT` on the writable application tables and `EXECUTE` on the fixed read functions in the canonical DDL. No `SELECT` on any `app` base table and no `UPDATE`, `DELETE`, `TRUNCATE` or `CREATE` anywhere. `NOSUPERUSER NOBYPASSRLS`; not a member of `eii_owner` or `eii_reviewer`, so `SET ROLE` to either is refused. |
| `eii_reviewer` | yes, for desktop GIS clients | `USAGE` on `review` and `SELECT` on its views only; `default_transaction_read_only` set on the role as a second line, because a session can change that default (architecture research). |

Roles are created once by a superuser during setup (document 13). The application never connects as a superuser.

| ID | Requirement |
|---|---|
| BE-31 | The application role owns no table, view, schema or function; a test queries the catalogue and fails on any object owned by `eii_app`. Table owners bypass row-level security unless it is forced (PostgreSQL 18 documentation; observed in the architecture research). |
| BE-32 | The only extensions present are `plpgsql` (installed by default) and `postgis`; preflight and a test fail on any other row in `pg_extension`. No `h3`, routing, graph, vector or audit extension in v1. |
| BE-33 | A release schema is named `r_` plus the first 16 hexadecimal characters of the `release_id`; the full id is stored in that schema's loader-materialised `release_manifest` table and the loader refuses a prefix that already belongs to a different full id. |
| BE-34 | `EII_DATABASE_URL` authenticates as `eii_app`; preflight checks `current_user`, `rolsuper` and `rolbypassrls` and fails otherwise. The loader connects to the same host and database as `eii_owner`, taking that role's password from libpq's standard password file written at setup, never from a committed file. ASSUMPTION: the master design pins no second connection variable; document 13 owns where setup stores the owner's password. |
| BE-35 | Every `app` table has row-level security enabled and forced (`ALTER TABLE … FORCE ROW LEVEL SECURITY`). |

### 4.3 Query isolation for the three seats

The canonical application DDL, including policies, privileges and fixed `SECURITY DEFINER` read
functions, is [document 03, section 12](03_DATA_CONTRACTS.md#12-the-application-schema-postgresql-only-schema-app).
It is not restated here. The functions have a locked empty `search_path`, explicit seat checks and
separate company and oversight return types. Oversight return types carry no organisation identity,
question text or brief text.

After the seat picker binds a signed `eii_seat` session cookie to the window, each transaction that
touches `app` verifies that cookie, obtains the organisation through the fixed seat-context function
and sets `eii.seat` and `eii.organisation` transaction-locally from that result. No seat-scoped route
accepts a seat in its address or request fields. Unset or empty settings match no seat. Version 1
demonstrates query isolation after a seat is selected;
it does not provide an identity system, tenant authentication or adversarial company separation.

| ID | Requirement |
|---|---|
| BE-36 | Database-level tests connected as `eii_app` prove that direct `SELECT` on every `app` base table fails. After inserting a brief as `company_a`, the company read functions return it to `company_a` but return zero rows to `company_b`, `oversight`, an unset seat and an empty seat. Policy tests are generated from the canonical application DDL. |
| BE-37 | Inserts are checked: a test proves a transaction set to one seat cannot insert a brief, ledger entry or egress record carrying another seat or organisation. |
| BE-38 | Tests prove that every oversight read function rejects a non-oversight seat, has a fixed return type distinct from the company functions, and returns no organisation identity, organisation label, question text or brief text (OI-08). |
| BE-39 | When a seat requests a brief that is not visible to it, the API answers 404 with the same body as for an id that does not exist, and writes a `brief_not_visible` ledger entry for the requesting seat. |

### 4.4 Reviewer views

The loader generates one view per manifest table in `review`, over the current release schema. Rows keyed by release unit join `release_unit` for its stored polygon. Rows on official geographies join `district`, `zone` or `municipality` geometry. Every view adds `provenance` and `release_id` columns. Loader and parity tests cover `release_unit.geometry`, `district` and `grid_cell.district_key`.

| ID | Requirement |
|---|---|
| BE-40 | Reviewer views are generated from the manifest only; a view for a table outside the manifest cannot be created. |
| BE-41 | A test connected as `eii_reviewer` proves `SELECT` on every `review` view succeeds and that `INSERT`, `CREATE TABLE`, `DELETE` and any read of `app` or a release schema are refused. |
| BE-42 | Geometry columns use SRID 4326 (ASSUMPTION: matches the H3 latitude and longitude convention and opens in standard GIS clients without reprojection). |
| BE-43 | Reviewer access bypasses the question ledger, so its credentials are for the operating ministry's IT reviewers only and never for a company seat (architecture research risk note). |

## 5. The loader (`./eii load-release`)

The loader is the only way data enters PostgreSQL or the embedded DuckDB file. It reads the release directory named by `EII_RELEASE_DIR` (Parquet files plus the manifest, document 03) and never reads anything else.

| Step | Action |
|---|---|
| 1 | Verify the manifest's canonical hash equals the `release_id`, and each listed table and artefact's SHA-256, row count where applicable and schema hash. |
| 2 | Require exact manifest agreement under `tables/` and `artefacts/`. At the root allow only `manifest.json`, `release.duckdb` and `load_receipt.json`. Reject absolute paths, `..`, symlinks, non-regular files and resolved paths outside the release root or expected subdirectory. Reject any table name outside the allow-list of `eii_core.manifest` or any column differing from the manifest schema. |
| 3 | Scan every text column of every table for `SYN-[ELGPF]-` and reject the complete forbidden column list in DAT-83. The scan exempts exactly one place, `firm_list.firm_key`, which DAT-83 requires to hold a released firm key of the `SYN-E-` form of DAT-12, or the literal `withheld` on the one row of a withheld list; any other value there (a key of the old `fk_` form, or a `SYN-L-`, `SYN-G-`, `SYN-P-` or `SYN-F-` value) is rejected, and so is a match in any other column, a `SYN-E-` value included. No v1 release table carries an establishment, legal-entity, person, group or salary-file identifier of the vault (OI-07): the released firm key is generated for the release and equals no vault identifier, which the release build proves before export because the loader cannot see the vault (DAT-140). The named synthetic firm list carries only each listed firm's fictional name, activity, size band and release unit beside that key ([02](02_ARCHITECTURE.md) ARC-131; document 03 pins its columns and key). |
| 4 | PostgreSQL: if schema `r_<16 hex>` exists and its stored manifest hash matches, report "already loaded", skip the PostgreSQL load and continue to DuckDB verification or rebuild and receipt verification. Otherwise remove only a stale `r_<16 hex>__loading` schema, load into it, create the manifest indexes, `ANALYZE`, verify counts and digests (BE-29), grant to `eii_app`, regenerate `review` views and rename the schema in one transaction. |
| 5 | DuckDB: build `release.duckdb` under a temporary name inside the release directory, verify counts and digests, then rename it atomically. Rebuild it when missing, corrupt or from the wrong engine pin even when PostgreSQL was already loaded; skip only when its recorded digest and engine pin match. |
| 6 | Apply the canonical `app` schema DDL from [document 03, section 12](03_DATA_CONTRACTS.md#12-the-application-schema-postgresql-only-schema-app) through the idempotent migrations in `infra/postgres/`; do not restate its columns in backend SQL. Load seeded ledger history (section 9.2) if absent. |
| 7 | Verify both final store names, release id, tables, counts and digests, then atomically write one `load_receipt.json` beside the manifest. It is not listed in `manifest.artefacts` and carries `state: complete`, the manifest's `release_id`, both engines, tables, counts, digests and durations. For a `protected` release it also carries matching `window_key`, `protected_sha256`, `rules_version_id` and `parameter_set`; for `public_only` it omits those protected-window fields. A temporary, incomplete or wrong-release receipt is never eligible to serve. |

The copy mechanism (DuckDB's PostgreSQL extension or psycopg `COPY`) is chosen at slice S1. The architecture research measured the first: 2.2 s copy plus 2.7 s indexing for 7.5 million rows, and noted that `postgres_execute` accepts one statement per call.

| ID | Requirement |
|---|---|
| BE-44 | The loader rejects any table not named in the manifest, prints the table name, changes neither store and exits with code 4 (document 13). |
| BE-45 | Running the loader twice on the same complete, verified release changes nothing and exits 0 the second time; a missing or corrupt DuckDB file is still rebuilt under step 5. |
| BE-46 | Both stores are staged and verified before one completion receipt is written. `load_receipt.json` is not a manifest artefact. For both release kinds, preflight and the API require `state: complete` and `release_id` equal to the mounted manifest's id. For a `protected` release they also require matching `window_key`, `protected_sha256`, `rules_version_id` and `parameter_set`; a `public_only` receipt omits those protected-window fields. An interrupted load or staging artefact is never eligible to serve. |
| BE-47 | The loader refuses to make a third release schema online and names the two present; removal is an operator step (document 13). |
| BE-48 | The loader never deletes or alters a file listed in the manifest. |
| BE-103 | The product serves exactly one mounted release, the one `EII_RELEASE_DIR` names. For a `protected` release, no route, setting or switch selects a parameter set at run time; `GET /api/release` reports the exported set as data and nothing else offers one. No second protected table set of one window exists in the product plane. The product shows the aggregate survival and attack results of both parameter sets, read from the `survival_report` control table (PRV-80) and the signed attack report (PRV-79); it holds no other value of the unselected set. A `public_only` release reports `release_kind: public_only`, has no parameter set or protected-window field, and contains no Protected or Simulated table. |

## 6. The tools

### 6.1 Common contract

Every tool is a pure function of its validated input and the release. Input models use Pydantic with `extra="forbid"`. Every result has this envelope:

```json
{
  "tool": "area_evidence",
  "call_id": "uuid",
  "release_id": "full hash",
  "engine": "postgres",
  "status": "OK",
  "blocks": [{"block": "resident_pay", "status": "OK", "fact_ids": ["…"]}],
  "facts": [{"fact_id": "…", "value": "…", "unit": "…", "provenance": "synthetic", "...": "pinned fields"}],
  "payload": {},
  "caveat_keys": ["coverage_partial"],
  "privacy_receipt": {}
}
```

Statuses are exactly `OK`, `SUPPRESSED`, `NO_DATA`, `OUT_OF_SCOPE`. A status is a governed answer; an error (section 12) means the tool could not run. The application, not the model, maps a status and caveat keys to the refusal or caveat template.

| ID | Requirement |
|---|---|
| BE-49 | Every numeral a tool returns is the `value` of a fact with all pinned fields; `payload` holds only identifiers, labels, enumerations and geometry for drawing. |
| BE-50 | `fact_id` matches `^f_[0-9a-f]{32}$` and is derived from the full SHA-256 over the canonical JSON of (`release_id`, `metric_key`, `geography`, `period`, `qualifiers`), using the first 32 hexadecimal characters. It is semantic identity, independent of tool name, arguments or fact slot, and matches DAT-93. |
| BE-51 | Composite facts take their provenance from `least_real` over their inputs and list every input class in `input_classes`. |
| BE-52 | A figure computed from the user's own inputs has `evidence_status` `inferred`, the caveat key `your_inputs`, and is never written to the release or to `ledger_entry`. |
| BE-53 | A withheld item is returned as a fact with provenance `suppressed`, no value, and the reason key from `suppression_reason`, so "Why can't I see this?" always has an answer. |
| BE-54 | Tools that read protected tables accept an `area_id` from `make_area`, whatever the area kind (a drawn shape included), never raw cells, polygons or coordinates, so no protected figure is read before snapping. The sole exception is the non-production scene endpoint defined by PRV-119 (BE-106). It is not an assistant tool, accepts only a manifest-listed `fixture_id`, and returns two pre-validated unit sets and area answers. |
| BE-55 | Public figures stay on their official geography: `public_context` uses `grid_cell.district_key` and reports the district, zone and municipality containing the pin cell; property-sale lookup reads `district` and `pub_property_sale`. It never area-weights or blends an official geography into a protected figure. Where a tool apportions a Public statistic to an area's exact outline, `eii_core.calc` applies the Public weight of document 07 (OPEN: area or a licensed public population grid, confirmed at slice S2); the fact has evidence status `inferred` and names its method and its official geography. An official split by sex or nationality is never apportioned (BE-110). |
| BE-104 | Every displayed number, comparisons included, is produced by deterministic tested code in `eii_core.calc`, by the release build, or by a fixed read function of the application schema that [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) lists and the tests cover. Difference, ratio, rank and direction facts are calculation facts (MTH-01, PRV-30). Nothing else computes, rounds or compares a number, and no model ever does; no other query file or handler holds display arithmetic. The fact API (`GET /api/facts/{fact_id}/lineage`) emits no fact whose `lineage_ref` does not resolve to a complete source chain — release table, method and version, source with publisher, licence, retrieval date and file hash — which the evidence drawer shows under the label "Source chain". |
| BE-108 | Every figure a tool, playbook or model path returns from protected or simulated tables is normally computed from exactly one additive family — one release table, one partition, one measure and one breakdown — named in the fact's lineage, and a count and adjacent non-ratio shares shown on one card come from the same family (PRV-30). The only exception is the closed list of ratio statistics: mean wage and the coverage, irregular and deployed-elsewhere shares. Each takes numerator and denominator columns from the same stored rows — one table, one partition, one unit set and one measure where applicable — even when those columns belong to two additive families, and its lineage names both. No tool result, evidence block, card, brief or export presents two routes to one population as two numeric estimates. The housing split lists `family_housing`, `labour_accommodation`, `institution` and `unknown` with an explicit `other` row only where pooling occurred, beside the separate not-measured count (PRV-39); no output says the listed classes reconcile to the card total. |
| BE-110 | Official figures split by sex or nationality ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)) are returned only as Public facts with their source and year, on the source's own geography and categories (for nationality, the published Qatari and non-Qatari categories). No tool joins such a split to a synthetic record, uses it to segment synthetic records, apportions it to a drawn area or combines it with a protected figure in a calculation; a lineage test fails on any fact whose inputs include both a split and a protected table. Synthetic and protected records carry no sex, gender or nationality, and none is derived for them. |
| BE-111 | Presence is returned as Simulated estimated counts of people, each with its range, by hour, segment (workers, residents, visitors) and day key, and crowd density as people per square kilometre ([02](02_ARCHITECTURE.md) ARC-129). Counts are read at release-unit grain and apportioned to the exact outline only by `eii_core.calc`. No count or density is returned for a named building, business or place: titles and templates say "estimated people around this location", and the build-time template scan rejects "footfall of". The 24-hour animation is offered for traffic and crowd density only, and every frame carries the Simulated mark. |
| BE-112 | Every rank, fit, similarity rank, reachable-access score and projection is computed by `eii_core.calc` under its method card and returned as facts: each criterion's value, each weight (tagged "your inputs" when the user changed it) and the rank (DAT-134), with the rank-stability facts of method card C11 beside every rank. The weighted score of C11 only orders the candidates and is never returned as a fact (PRV-41). Weights come only from the catalogue defaults or the user's typed values, never from the model. No result carries a verdict, a probability, a confidence claim, a revenue, demand or success forecast or advice to act; a projection carries its method and period and the caveat that it is a projection. |
| BE-113 | Only `synthetic_firms` returns synthetic firms, each marked Synthetic with its fictional name, activity, size band and release unit, from the rows the privacy engine released under the minimum, dominance and complement rules of document 06. The tool filters and orders those rows and never adds a row or a field. It never returns a firm's wages, wage bill, headcount, address or point, never places a firm at a real address, and never joins a firm to an FDI project, a public place or another firm (no network of firms or owners). A territory whose list the privacy engine withheld returns `SUPPRESSED` with the reason code the release records. |
| BE-114 | `investment_context` returns FDI projects only as published announcements. Only a published field whose value holds no digit is returned as a label (BE-49). Every digit-bearing field is returned as a Public fact with a complete source chain (BE-104), in a closed unit of the fact schema: capex and jobs in their numeric units; the `announced` date as `calendar_year`, `calendar_month` or `calendar_date`, at exactly the precision the page gives and never padded; and any other field whose published value holds a digit as `published_text`, its value the field as published (document 03 DAT-155). A digit-bearing field whose value fails its unit's checks is never returned as a label: the fact is dropped and its slot shows `NO_DATA` (document 03 DAT-90). The screen renders every such fact only through a Fact chip ([AGENTS.md](../AGENTS.md) rules 7 and 23). Each capex and jobs fact carries the caveat key with the source's note that they are estimates of publicly announced projects and that the dashboard does not capture every project. A project's subject is `fdi_project`, which accepts Public slots only; no Synthetic or Simulated fact is attached to a project, and a project is never joined to synthetic firm data. No input names a company, and a request to look up a firm, owner or person returns `OUT_OF_SCOPE`, as `resolve` does. The agency's records are returned as structured records for application templates, each with its page link and retrieval date. Every figure from either source shows its source and retrieval date. |
| BE-115 | Protected blocks read one month, or a range of months, of the release's one window ([02](02_ARCHITECTURE.md) ARC-130). Every change between months comes from the treated `month_change` rows: `eii_core.calc` computes change facts only from those rows, never by subtracting two monthly values, and a change that the release carries forward, or that spans a withheld month, is returned as `SUPPRESSED`, never as zero. The wage trend of an area, separated from changes in worker mix, is the fixed-composition index that the release holds in `month_change.stayer_wage_index` (document 07, method card C19, indicator 6) only for units at municipality level or coarser: the municipality units of the `money` and `quartile` pay partitions, one per municipality, and the national units ([06](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-16, PRV-55). An area is shown the index of each such unit that contains units of its block, so the index of its municipality and the national one, labelled with that unit's own released area; no stayer wage bill is released, and no index is averaged or combined across units. Wage trends by sector are the Public national branch of method card C19 (indicator 6), returned by `labour_facts`: each economic activity's change between adjacent published years of the activity table of `pub_wage_table`, the public portal's wage series by economic activity, with the national change split into within-sector and employment-mix components by method card C3's function. They come from that public series only, never from a protected split, and national by sector is the finest sector view in version 1, so no sector trend is computed for an area or a municipality. No route reads a second window. |
| BE-116 | Every tool of section 6.2 and every layer of section 8.1 reads the release only through named queries (BE-07), returns every number as a fact with provenance and a lineage that resolves (BE-104), and has at least one parity case (BE-26). No route, handler or query file computes, rounds, compares, ranks or selects a number outside `eii_core.calc`, the release build or a fixed read function that document 03 lists. |

### 6.2 Tool contracts

`resolve`

| Field | Contract |
|---|---|
| Inputs | `text` (1 to 200 characters), `lang` (`en` or `ar`), `kind` (`place`, `activity`, `both`). |
| Outputs | `payload.candidates`: at most five, each with kind, key, English and Arabic labels, source (`gazetteer` or `activity_spine`), match type (`exact`, `normalised`), and for activities the commerce code, ISIC Rev.4 class, public place category and a `not_mappable` flag. No facts. |
| Statuses | `OK` with at least one candidate; `NO_DATA` with none; `OUT_OF_SCOPE` for a location outside the frame or a request to look up a firm, owner or person (prohibited claim, master design section 13). |
| Reads | `gazetteer`, `district`, `zone`, `municipality`, `graph_node`, `graph_edge`. The gazetteer and spine are read once at start-up through named queries; matching runs in Python with `eii_core.text`. |
| Parity case | "Lusail" (place) and "Italian restaurant" (activity) in both languages. |

`make_area`

| Field | Contract |
|---|---|
| Inputs | Either `shape_id` (a polygon the user drew, registered by `POST /api/areas/shapes` for this session and seat, BE-117; the model passes only the identifier), or `pin` (latitude and longitude from the user's click, or a gazetteer key) with `mode` (`distance`, `walk`, `drive`) and `cutoff` (250, 500, 1,000 metres for distance; 5, 10, 15 minutes for walk or drive; drive 30 only for `staffing_and_pay`). For drive only: optional `situation` and `summer`, or an `hour_key` and a `day_key` from the release's closed lists ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md)). |
| Outputs | `payload.area_id` (section 11.1); `payload.outline` (GeoJSON of the exact shape, used for Public points and Simulated layers); `payload.units` by partition key, where the list of each protected partition holds only the whole-cell units of its snapped set, of `unit_kind` `cell` or `merged`: a remainder is never added to an area sum, and a unit of kind `municipality` or `national` is never snapped ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-18); `payload.snap_report` with the requested outline, cells inside, units used, cells added and cells dropped by snapping, and the key of the snap sentence. The snap-report counts are facts with provenance `synthetic`, because the unit partition is derived from protected tables (ASSUMPTION). |
| Statuses | `OK`; `OUT_OF_SCOPE` for a pin or a shape outside the frame. When no release unit survives snapping, the area is still made for its exact outline with an empty unit list, and every protected block read through it returns `NO_DATA` with reason `SNAPPED_TO_WHOLE_UNITS` (ASSUMPTION: in the first pack `make_area` itself returned `NO_DATA` here; Public and Simulated blocks now use the exact outline). |
| Errors | `INVALID_ARGUMENT` for a cutoff not in the list, drive 30 outside `staffing_and_pay`, `summer` with `ramadan_iftar`, an hour or day key outside the release's lists, both a `shape_id` and a `pin`, an unknown `shape_id`, or a `shape_id` of another session or seat. |
| Reads | `grid_cell`, `release_unit`, `unit_member`, `road_link` and `traffic_hourly` (drive with a situation or an hour). In public-only mode (BE-105): `grid_cell` only, with free-flow drive areas. |
| Public-only mode | When the mounted release holds Public tables only (slice S3), `make_area` uses the fixed base-cell frame: it reads no privacy-derived `release_unit` and no protected or simulated table, its area is the set of frame cells selected by the shape plus the pin's base cell, and the snap report is emitted as technical metadata, not as a Synthetic fact. |
| Parity case | The flagship pin with walk 5 and drive 10; a drive 10 area at two hours of one day key; a fixture polygon: identical unit lists and outlines on both engines. |

`area_evidence`

| Field | Contract |
|---|---|
| Inputs | `area_id`; `blocks` (any of `resident_pay`, `worker_pay`, `presence`, `traffic`, `register`, `coverage`, `public_context`); optional `month_key` for the protected blocks (one month of the release's closed month list; default the latest month, ASSUMPTION); for `presence` and `traffic`, a `day_key` (or `situation` and `summer`) and an optional `hour_key` (every hour of the day when absent). |
| Outputs | `resident_pay` and `worker_pay`: rounded earner count, median band, quartile band range, band distribution, and the housing split of covered earners that feeds the `live_pay` card of document 10 — `family_housing`, `labour_accommodation`, `institution` and `unknown`, an explicit `other` row only where pooling occurred (values as [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) defines them), beside the separate protected `not_measured_count`, which is a separate population from `resident_pay` on `rp_housing_count` (PRV-39); mean wage and wage bill flagged "more evidence"; `worker_pay` also carries the coarse home-area shares (capability S10). `presence` (from [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), replacing the index of the first pack): Simulated estimated counts of people around this location, each with its range, for workers, residents and visitors, hour by hour through the chosen day or for one hour, with crowd density (people per square kilometre) for the same hours; released counts are apportioned to the exact outline by `eii_core.calc` (BE-111); metro, tram, bus, hotel and restaurant-and-hotel price-index series stay separate Public context facts. `traffic`: Simulated slowdown by hour on the roads of the area, computed by `eii_core.calc` from the travel-time factors of `traffic_hourly` on the area's `road_link` rows as method card C25 defines it (the length-weighted mean of the speed ratios inside the outline, a link without a row at 1.000), and for a drive area the area reached at each hour (ARC-133). `register`: licensed outlets within reach and the share showing payroll activity by size band (capability S1). `coverage`: the C8 Public proxy, naming its geography, with its remainder labelled `outside this proxy`, never Not measured; the coverage bar uses the finest admitted geography, the census map layers included under decision 0017 item 10 (OI-04 closed for version 1), or returns `NO_DATA` (PUB-82). It never derives a not-measured share by subtracting the Public proxy. `public_context`: licences against the national rate, zone electricity growth, transit riders, sale price per square metre with its deal count, and census shares only at an admitted geography (PUB-82); from [decision 0017](decisions/0017-public-data-additions-and-public-splits.md), for the municipality containing the pin cell or the shape's representative point, residential unit sales with their deal counts, building permits and completion certificates, population by age and, as separate Public splits, population by age and sex, each on its source's own geography with source and period and never apportioned to the area (BE-110). Every pay and split figure is computed from exactly one additive family, named in the fact lineage, and a count and the shares shown beside it on one card come from the same family (PRV-30, BE-108); no block or card presents two routes to one population as two numeric estimates. Every result carries a privacy receipt (release, rules version, the exported parameter set where applicable, units, treatments, withheld items, snap report). |
| Statuses | Per block and overall: `OK`, `SUPPRESSED` (a derivation minimum in document 06 fails for the area total), `NO_DATA`. |
| Reads | `resident_pay`, `worker_pay`, `home_area_share`, `presence_count`, `traffic_hourly`, `outlet_register`, `release_unit`, `unit_member`, `suppression_reason`, `rules_version`, `pub_licence_active`, `pub_zone_utility`, `pub_transit_monthly`, `pub_hotel_monthly`, `pub_price_index`, `pub_property_sale`, `pub_property_resi`, `pub_building_permits`, `pub_population_age`, `pub_population_age_sex`, `pub_census_zone`, `pub_census_district`, `pub_population_municipality`, `pub_census_national`, `district`, `zone`, `municipality`. |
| Parity case | All blocks for the flagship walk-5 and drive-10 areas, each situation; `presence` and `traffic` for one day key at every hour and for each event day; one fixture polygon. |

The six income indicators of [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 9 come from these blocks, from `what_changed` and, for wage trends by sector, from `labour_facts`: average and median wage by residential area where groups are large enough, wage bands and their spread, and the covered wage bill with the earner count (`resident_pay`, `worker_pay`; for an area here, and per municipality and nationally through `labour_facts`: per municipality from its units of the `money` and `quartile` pay partitions, the mean, the wage bill and the one earner count from the `money` unit and the median band, band shares and quartile bands, with the denominator of those shares, from the `quartile` unit, that denominator never returned as a second earner count; nationally from the national units, the mean and the wage bill from the `money` partition, the bands from the `quartile` partition and the earner count from `rp_all_count` or `wp_all_count`; [06](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-16; [07](07_ECONOMIC_METHODS.md) MTH-55, MTH-76); residential income beside presence by time of day (`resident_pay` with `presence`); residence and workplace geography (the home-area shares of `worker_pay`); and wage trends separated from changes in worker mix: by area, the fixed-composition index of method card C19 (`what_changed`), only for the municipality and national units that contain the area's units and never by sector; by sector, the Public national branch of method card C19 on the activity table of `pub_wage_table`, the public portal's wage series by economic activity (`labour_facts`), never from a protected split and never for an area or a municipality: national by sector is the finest sector view in version 1. The national split of method card C3 on the occupation table stands in `sector_facts` (`pay_decomposition`). An area's mean wage is never returned without the median band, the band distribution and the earner count of the same area and month, each from the family that method card C19 assigns it (MTH-55), and the area figures describe covered earners and wages paid, never every household, wealth or spending power; a sector's mean, from the Public activity table, is returned only beside its paid workers.

`scan_places`

| Field | Contract |
|---|---|
| Inputs | `area_id`; `categories` (spine keys); `limit` (1 to 50); `include_neighbours` (bool). |
| Outputs | Public places whose precomputed cell is in the area and, for a drawn shape or an exact outline, whose point lies inside it (`eii_core.shapes`), each with name, category, source provider, licence and confidence (the `pub_place` columns of PUB-48), its verification status when `pub_place_verification` holds a row for it (PUB-53), and a network distance from the pin as a Public fact; it never takes an hourly link speed (MTH-57, PUB-92). For a named museum, exhibition or health centre, its published visitor counts as Public facts of a `place_public` subject with source and period ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)), never an estimate of people present. These are the real businesses and named public places of the journeys; no Synthetic or Simulated figure, fit or rank is attached to one. The caveat key `open_listings_incomplete` is always present. With `include_neighbours`, at most six "found near" categories from co-location edges (capability S9). |
| Statuses | `OK`; `NO_DATA` (no listed place, which is not evidence that none exist); `OUT_OF_SCOPE` for a category outside the spine. |
| Reads | `pub_place`, `pub_place_verification`, `pub_venue_visits`, `graph_node`, `graph_edge`, `grid_cell`. |
| Parity case | Restaurants around the flagship pin. |

`compare_areas`

| Field | Contract |
|---|---|
| Inputs | `area_id_a`, `area_id_b` (any two areas, drawn shapes included), `blocks`. |
| Outputs | The `area_evidence` result for each area, plus overlap: the shared units and the residents and workers in them, labelled "shared reach, not lost sales" (capability S6); the second-site comparison of journey D6 and service S2 shows overlap, never lost sales. Disjoint snapped areas return 0% shared reach when both weights are nonzero. `eii_core.calc` applies C7's derivation and privacy checks to the intersection and each denominator; a failing derivation minimum returns `SUPPRESSED`. |
| Statuses | As `area_evidence`; `NO_DATA` only when either weight is zero or a required source is unavailable; `SUPPRESSED` when a C7 privacy or derivation minimum fails. |
| Reads | As `area_evidence`. |
| Parity case | The flagship pin against a second Lusail pin. |

`pay_benchmark`

| Field | Contract |
|---|---|
| Inputs | `area_id`; `occupation_groups` (keys) or `activity` (spine key mapped to occupation groups); optional `month_key` (as `area_evidence`). |
| Outputs | Pay bands by occupation group for residents of the area (Synthetic), the published national average for the group, the statutory minimum and the C10 restaurant annual-wage and monthly-equivalent anchor from `pub_sector_accounts` (Public, documents 04 and 07). The occupation-group values may include `other` beside `0` to `9` and `unmapped` (values as [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) defines them). A median band or quartile range that the exported tier does not publish for a group returns `SUPPRESSED` with the reason code of document 06, and the answer template reads "not available at this area size" and offers the wider area (wording of [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md); PRV-21). |
| Statuses | `OK`, `SUPPRESSED`, `NO_DATA`, `OUT_OF_SCOPE` (unmapped activity). |
| Reads | `occupation_pay`, `release_unit`, `unit_member`, `pub_wage_table`, `pub_sector_accounts`. |
| Parity case | Food-service occupations within drive 30 of the flagship pin for `staffing_and_pay`, including the C10 restaurant annual-wage and monthly-equivalent anchor. |

`sector_facts`

| Field | Contract |
|---|---|
| Inputs | `activity`; `topic` (`unit_economics`, `licences`, `churn`, `zone_momentum`, `pay_decomposition`, and from [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) `employer_scale`, `market_context` and `visitor_markets`); `geography` (national, municipality or zone code); optional `scenario_inputs` for `unit_economics`: the six inputs of method card C4 in document 07 — monthly rent, seats, average bill, opening days (default 30), and the optional expected covers per day and monthly staff cost — plus the optional target surplus share `U` (default 0, break-even), and an optional `incentive_key` naming one `incentive` record of `pub_investqa_record` that the user chose, whose parameters are that record's `incentive_parameter` rows (DAT-143). |
| Outputs | Public facts on their official geography; with `scenario_inputs`, the covers per day required and the breakpoint as `inferred` facts tagged "your inputs", every one computed by `eii_core.calc` under method card C4 (MTH-25 to MTH-28). Breakpoints appear only when expected covers are entered. The target-surplus result is a separate line labelled "to earn the sector's 2022 surplus share" and is never called break-even (MTH-26). With an `incentive_key`, the package's parameters enter the calculator as Public facts naming their source page and retrieval date, as document 07 defines; the result keeps the "your inputs" tag and no Public figure changes. Churn facts flag bulk months (capability S8). `employer_scale`: establishments and employees by size class and activity, with compensation where published, each bulletin with its own last year, and the 2015 census by municipality marked as dated 2015. `market_context`: wholesale and retail purchases, sales and stocks, national, as context and never a forecast. `visitor_markets`: hotels and hotel apartments by municipality, hotel guests by nationality as a Public split (BE-110) and visitor arrivals. |
| Statuses | `OK`; `NO_DATA`; `OUT_OF_SCOPE` for an activity with no published cost structure. |
| Reads | `pub_sector_accounts`, `pub_licence_active`, `pub_licence_cancelled`, `pub_zone_utility`, `pub_wage_table`, `pub_price_index`, `pub_establishment_size`, `pub_census_2015_municipality`, `pub_trade_wr`, `pub_hotels_municipality`, `pub_visitor_markets`, `pub_investqa_record`, `fact_lineage`, `source_registry`. |
| Parity case | Restaurants (activity 561), 2022, national unit economics; the national pay-versus-mix decomposition. |

`supplier_lens`

| Field | Contract |
|---|---|
| Inputs | `activity`; optional `input_key`; `period`. |
| Outputs | Input basket, tariff lines at eight digits or finer, ordered origin data for the ranked bars with the calculated import unit value (QAR per kg) and its valuation basis as the source states it, concentration and trend, and licensed wholesale depth by municipality. From [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), which brings backlog item L3 into version 1: imports against local production (method card C13), with manufacturing industries and main products as separate Public facts with their own units and periods (a licence-type row is not a plant, and licensed investment is cumulative); and for journey D7, certificates of origin by importing country and arriving vessels as Public context. Never a capacity, demand or substitution figure. The Source chain is limited to fifteen nodes. |
| Statuses | `OK`; `NO_DATA`; `OUT_OF_SCOPE` for an activity without a reviewed basket. |
| Reads | `graph_node`, `graph_edge` (through `graph_` queries, at most four steps), `pub_customs_import`, `pub_licence_active`, `pub_manufacturing`, `pub_trade_logistics`. |
| Parity case | The pasta input of the restaurant basket. |

The journey tools added by [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) follow the same common contract (section 6.1). Each reads the release through named queries only and returns numbers only as facts (BE-116).

`travel_times`

| Field | Contract |
|---|---|
| Inputs | `area_id`; `destinations` (`place_key` values of `gazetteer` entries of kind `gateway`: the ports, the airport, the free zones and the land routes, document 03); optional `day_key` and `hour_key` (free flow when absent). |
| Outputs | One network travel time in minutes per destination, from the area's pin or, for a drawn shape, its representative point (`eii_core.shapes`): provenance `public` at free flow, `simulated` when an hour applies (ARC-92). The fact's subject is the area: the destination appears only as the Public label of the trip's end, and no figure is presented as the destination's own (BE-119). A straight-line distance is never labelled a network time (ARC-95). |
| Statuses | `OK`; `NO_DATA` when no route exists; `OUT_OF_SCOPE` for a destination outside the list. |
| Reads | `gazetteer`, the routing graph artefact, `road_link`, `traffic_hourly`. |
| Parity case | The flagship drive-10 area to every destination at free flow and at two hours of one day key. |

`area_ranking`

| Field | Contract |
|---|---|
| Inputs | `activity` (spine key); `candidates`: candidates of one kind, as method card C11 of document 07 defines them: areas the user builds (pins with walk, drive or radius areas, or drawn shapes); the published release units of one partition inside a region the user draws; or, in public-only mode, the official zones or municipalities; `weights` (one per criterion of the closed criterion list of method card C11, fixed at slice S2: the catalogue defaults or the user's typed values); `mode` (`full` or `public_only`). |
| Outputs | For each candidate, an `area_id` (section 11.1), the value of every criterion as a fact with its own class, each weight (tagged "your inputs" when the user changed it), the rank as a comparison fact (DAT-134), and the rank-stability facts of method card C11, all computed by `eii_core.calc` (BE-112). The weighted score only orders the candidates and is never returned (PRV-41). Protected criteria are read at whole release units; criterion values per candidate come from release rows, never from a whole-country sum at request time ([02](02_ARCHITECTURE.md) ARC-57). `public_only` reads no Protected or Simulated table. |
| Statuses | `OK`; `SUPPRESSED` for a criterion withheld for a candidate (document 07 fixes how the candidate is then ranked); `NO_DATA`; `OUT_OF_SCOPE` for an activity outside the spine. |
| Reads | The tables of the criteria of method card C11 among `resident_pay`, `worker_pay`, `outlet_register`, `presence_count`, `access_score`, `access_score_grid`, `pub_place`, `pub_licence_active`, `pub_property_resi`, `pub_building_permits` and `pub_population_age`; `release_unit`, `unit_member`. The Public statistics among them (`pub_licence_active`, `pub_property_resi`, `pub_building_permits`, `pub_population_age`) are read only for official-geography candidates in public-only mode, or as apportioned counts (method card C18) for areas the user builds, never for release-unit candidates (MTH-65); `access_score_grid` is read only for official-geography candidates and areas the user builds, never for release-unit candidates (DAT-154, MTH-56). |
| Parity case | Restaurants (activity 561), with the default weights: the release units of one partition inside a fixture region around the flagship pin, and, in public-only mode, the official zones of the flagship's municipality. |

`activity_fit`

| Field | Contract |
|---|---|
| Inputs | `area_id`; optional `activities` (spine keys; default the closed activity list of document 07); `weights` as for `area_ranking`. |
| Outputs | The reverse of `area_ranking`, for property owners matching tenants: activities ranked by fit for the area, each with every criterion of the closed list of method card C16 in document 07 as facts (places of the activity's category in the exact shape, typical neighbours near the pin, the location quotient, the catchment's wage-band share, estimated people at the selected hours); residential sales and the construction pipeline stand beside the fit as context, never in the score. The rank is a comparison fact, with the rank-stability facts (BE-112); the score only orders the activities and is never returned (PRV-41). A fit is never a forecast of a tenant's success. |
| Statuses | `OK`; `SUPPRESSED` for a withheld criterion; `NO_DATA`. |
| Reads | `resident_pay`, `presence_count`, `pub_place`, `pub_licence_active`, `pub_property_resi`, `pub_building_permits`, `graph_node`, `graph_edge`, `release_unit`, `unit_member`. |
| Parity case | The flagship walk-5 area against the default activity list. |

`similar_areas`

| Field | Contract |
|---|---|
| Inputs | `area_id`; optional `area_type` (one of the three area types of document 07). |
| Outputs | The area's type, with its stability facts, and the official zones ordered by similarity (method card C17), each with its rank-stability facts (BE-112); with `area_type`, only the zones of that type. The typing uses Public features only. |
| Statuses | `OK`; `NO_DATA`. |
| Reads | `zone_type` (the area types and stability figures that the release build writes, method card C17, DAT-152), `zone`, and the Public feature tables of C17's reviewed feature list (for example `pub_place` and `pub_zone_utility`). |
| Parity case | The flagship walk-5 area. |

`reachable_access`

| Field | Contract |
|---|---|
| Inputs | `area_id` or `activity`; `mode` (`walk`, `drive`) and `cutoff`, a closed value: one of the cut-offs that method card C12 stores for the chosen mode, fixed at slice S2 (DAT-151, DAT-154), never a free number and not the `make_area` list; optional `day_key` and `hour_key`. |
| Outputs | The reachable-access score of method card C12 (a travel-time catchment score) as a fact computed by `eii_core.calc` from the stored scores of the area's demand locations, weighted as C12 defines (BE-112). Its class is the least-real class of its demand layer, supply layer and times (MTH-67): Public for the population grid with Public points at free flow, and Simulated with estimated residents present or any hour's times. Each layer's score is its own fact; the two are never combined. No protected figure enters the score (PRV-41). |
| Statuses | `OK`; `SUPPRESSED` with `BELOW_PANEL_MINIMUM` when the score draws on a withheld presence group (PRV-58); `NO_DATA` when a layer is missing, when the area's demand weights sum to 0 (for the grid layer, no populated cell in the area) and for an hour or day key in public-only mode, where only free-flow scores exist, while an area that reaches no supply point has the score 0, as C12 defines; `OUT_OF_SCOPE` for an activity outside the spine. |
| Reads | `access_score` (DAT-151), `access_score_grid` (DAT-154), `presence_count` (the demand weights of C12), `pub_place`, `release_unit`, `unit_member`. Public-only mode reads `access_score_grid` and `pub_place` only; a protected release may read both score tables. The build-time times of `access_score` are in the manifest artefact `travel_time_matrix` (DAT-153); the tool reads the stored scores, not the times. |
| Parity case | The flagship drive-10 area at free flow and at one hour; the same area on the grid layer at free flow. |

`what_changed`

| Field | Contract |
|---|---|
| Inputs | `area_id`; `block` (`resident_pay`, `worker_pay`, `register`); `from_month_key` and `to_month_key` (two months of the release's closed list). The tool returns area figures only; wage trends by sector are national Public figures of `labour_facts` (method card C19). |
| Outputs | The released value of each month as Synthetic facts, and, for every pair of adjacent months in between, the published components of the treated `month_change` rows summed over the area's units (joiners, leavers and stayers, or openings and closures for `register`), computed by `eii_core.calc` under method card C20, never by subtracting two monthly values; for `resident_pay` and `worker_pay`, the wage trend of the same earners for each pair: the `stayer_wage_index` of each unit at municipality level or coarser that contains units of the area, labelled with that unit's own released area, with its change and direction (method card C19, indicator 6), never averaged or combined across units (BE-115). Every change carries the caveat that a change between synthetic months is a change in the synthetic world, not in Qatar. |
| Statuses | `OK`; `SUPPRESSED` when either month is withheld for the area, or with `CARRIED_FORWARD` when a `month_change` row of the pair is carried forward, an empty cohort's row included (DAT-137), and then no change is returned for that pair, never zero; `NO_DATA`. |
| Reads | The protected tables of the block at their monthly periods, `month_change`, `release_unit`, `unit_member`, `suppression_reason`. |
| Parity case | `resident_pay` and `worker_pay` for the flagship drive-10 area between the first and last month of the window. |

`labour_facts`

| Field | Contract |
|---|---|
| Inputs | `activity` or `occupation_groups`; `geography` (national or municipality code); `split` (`none`, `sex`, `nationality`); optional `projection` (true or false). |
| Outputs | The labour-market view of journey D5: occupations, and pay bands with middle ranges and earner counts, from the released national and municipal rows only (Synthetic), never by sector; for the chosen geography, the pay figures of method card C19 (indicators 1 to 3), each from the partition that C19 assigns it (per municipality, the mean, the wage bill and the one earner count from the `money` unit and the bands, band shares and their denominator from the `quartile` unit, that denominator never returned as a second earner count; nationally, the earner count from `rp_all_count` or `wp_all_count`; MTH-55, MTH-76), and the stayer index of its municipality unit, or of the national unit, of the `money` and `quartile` partitions of `resident_pay` and `worker_pay`, never by sector ([06](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-16, PRV-55), each a statistic of that geography taken as an `area` and labelled with that unit's own released area (Synthetic); each month's released values with every carried-forward month marked (PRV-123), and the national split of pay change from changes in worker mix (method card C3, on its Public table); at national geography, the wage trends by sector (method card C19, indicator 6, Public): for each economic activity of the activity table of `pub_wage_table`, its mean monthly pay beside its paid workers in each published year, and the difference, ratio and direction between adjacent years, with the national change split into within-sector and employment-mix components, shown only once OI-03 is closed, as for C3; published labour-force, employment, unemployment, compensation and student series (Public), and, when `split` asks for one, the official split by sex or nationality as Public facts on the source's own geography and categories (BE-110); with `projection`, simple projections computed by `eii_core.calc` over a published or released series, each marked as a projection with its method and period, never a revenue, demand or success forecast (BE-112). No Public split and no Synthetic figure share a calculation. No protected pay band by sector exists, and no figure by sector is returned for a municipality or an area. |
| Statuses | `OK`; `NO_DATA`; `OUT_OF_SCOPE` for an activity or occupation outside the spine. |
| Reads | `occupation_pay`, `resident_pay` and `worker_pay` (municipality and national units only), `month_change` (the carried-forward marks and the stayer index), `release_unit`, `pub_wage_table`, `pub_labour_sex_municipality`, `pub_active_sex_age`, `pub_active_nationality_occupation`, `pub_compensation_nationality`, `pub_students`. |
| Parity case | Food-service occupations, national, with each split value and with a projection; the national wage trends by sector with their split; the pay figures and stayer index of the flagship's municipality. |

`openings_closures`

| Field | Contract |
|---|---|
| Inputs | `area_id` or `municipality_code`; optional `activity`, which filters the Public series only (the synthetic births and closures carry no activity class); `from_month_key` and `to_month_key`, or published periods for the Public series. |
| Outputs | Public licence openings and closures over time on their official geography, openings only for the codes the issued series covers and always with its incompleteness note, closures with bulk months flagged (method card C2), and no net formation from the Public series; Synthetic firm births and closures by release unit and pair of adjacent months, all activity classes together, from the `openings` and `closures` of the `month_change` rows of `outlet_register`, read at whole units under the disclosure controls (method card C22). The two are never shown as one series. |
| Statuses | `OK`; `SUPPRESSED` for a withheld month or unit, or with `CARRIED_FORWARD` for a carried-forward pair, which an empty cohort also causes (DAT-137), never zero; `NO_DATA`. |
| Reads | `pub_licence_issued`, `pub_licence_cancelled`, `month_change` (the openings and closures of its `outlet_register` rows), `release_unit`, `unit_member`. |
| Parity case | Restaurants in the flagship's municipality over the window. |

`synthetic_firms`

| Field | Contract |
|---|---|
| Inputs | `area_id` (the territory; a candidate or official geography from `area_ranking` included); `activities` (spine keys); optional `size_bands` (closed list: the bands of the exported parameter set, read from the release (manifest `parameter_set`), as `firm_list` holds them: `s00_09`, `s10_49` and `s50_plus` under set A, `s00_49` and `s50_plus` under set B; a filter selects whole joined bands only, and a band that the exported set does not hold is not offered); `purpose` (`prospects`, `partners`, `suppliers`, `complementary`: the one closed list that method card C16 of document 07 also uses, each kept through the reviewed relation between activities); optional `weights` for ordering by fit. |
| Outputs | Named synthetic firms from the released firm list: fictional name, activity, size band and release unit only, each marked Synthetic; with `weights`, a fit rank and its rank-stability facts from `eii_core.calc` under method card C16 (BE-112, BE-113). No count of listed firms is returned. |
| Statuses | `OK`; `SUPPRESSED` for a territory whose list the privacy engine withheld; `NO_DATA`; `OUT_OF_SCOPE` for a request that names a firm to look it up. |
| Reads | `firm_list`, `release_unit`, `unit_member`, `graph_node` and `graph_edge` (activity spine), the routing graph artefact and `road_link` (the free-flow drive times of C16), and the `parameter_set` of `release_manifest` (the closed size-band list). |
| Parity case | Food-service suppliers in the flagship drive-10 area, with and without weights. |

`investment_context`

| Field | Contract |
|---|---|
| Inputs | `topic` (`fdi_projects`, `sectors`, `opportunities`, `incentives`, `setup_steps`, `laws`); optional `sector`, `source_country` and `municipality_code` filters for `fdi_projects`; optional `sector` for the agency's records. A `tenders` topic exists only once slice S2 confirms a public source of tenders. |
| Outputs | For `fdi_projects`: published announcements whose fields without a digit are labels and whose digit-bearing fields are Public facts with complete lineage, rendered only through Fact chips: capex and jobs in their numeric units, the `announced` date as `calendar_year`, `calendar_month` or `calendar_date` by the precision the page gives, and any other field whose published value holds a digit as `published_text` (BE-114; document 03 DAT-155); capex and jobs with the source's estimate note; counts by the requested breakdown as facts from `eii_core.calc`; a project is placed on the map only at the location the source states (BE-114). For the agency's topics: structured records with their page links and retrieval dates, every number in them a Public fact. |
| Statuses | `OK`; `NO_DATA`; `OUT_OF_SCOPE` for a request that names a company to look it up. |
| Reads | `fdi_projects`, `pub_investqa_record`, `source_registry`. |
| Parity case | Projects by sector, national; the incentive records. |

`own_records` (playbook-only)

| Field | Contract |
|---|---|
| Inputs | `case_key` (`c3` or `c4`); `blocks` (`concentrations`, `access` for case C3; `branch_sales` for case C4); an optional `area_id` to set the records beside. |
| Outputs | Facts computed by `eii_core.calc` under method card C29 from the case sample file that this session and seat loaded (BE-118): provenance `synthetic`, the caveat key `your_inputs` and evidence status `inferred`, with the subject `area` the records describe. `access` gives, for each depot of the file and, when the optional `area_id` gives one, the candidate depot at its pin, the delivered units and the share of the file within each free-flow drive cut-off; free-flow times only, so the facts stay Synthetic. |
| Statuses | `OK`; `NO_DATA` with the reason that no sample file is loaded when the session has none. |
| Reads | The session store (BE-109) for the file, and for `access` the routing graph artefact and `road_link` at free flow; no release table holds the file. |
| Parity case | Each committed sample file on both engines, with the same `area_id`. |

`own_records` is called only by the `depot_options` and `branch_check` playbooks and by the case routes of section 8.3. It is not offered to the model, and its facts are never sent in a model request ([02](02_ARCHITECTURE.md) ARC-128).

`stage`

| Field | Contract |
|---|---|
| Inputs | One directive from the closed list in the schema below. Document 10 defines the screen behaviour. |
| Outputs | `payload.directive`, sent unchanged as a `stage` event. No facts. |
| Statuses | `OK`. Errors: `INVALID_ARGUMENT` for anything outside the closed list. |
| Reads | No release table. |
| Parity case | Each directive with both stores selected gives byte-identical output. |

The `stage` schema (the closed list; every object forbids unknown fields). A directive carries identifiers, enumerations and coordinates, never a number to render.

```json
{"directive": "fly",       "target": {"area_id": "…"} | {"place_key": "…"} | {"zone_code": "…"} | {"lat": 0.0, "lon": 0.0},
                           "zoom": "country | city | district | street"}
{"directive": "layer",     "layer": "<key from the closed layer list, section 8.1>", "visible": true}
{"directive": "highlight", "fact_id": "…"} | {"place_keys": ["…"]} | {"unit_ids": ["…"]}
{"directive": "rings",     "area_ids": ["…"]}                       (one or two)
{"directive": "dial",      "situation": "weekday_lunch | weekday_evening | friday_evening | ramadan_iftar",
                           "summer": false}
{"directive": "hour",      "hour_key": "<a key of the release's closed hour list>"}
{"directive": "day",       "day_key": "<a key of the release's closed day list: a day type and season, or an event day>"}
{"directive": "month",     "month_key": "<a key of the release's closed month list>"}
{"directive": "split",     "area_ids": ["…", "…"]} | {"off": true}
{"directive": "set_scenario_inputs", "open": true, "focus": "rent | seats | average_bill"}
```

`set_scenario_inputs` opens the scenario panel; the values themselves come only from the user or the local parser (document 09), never from a directive. `hour`, `day` and `month` ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md)) select a stored hour, a day type or event day, and a month of the release; hero layers of the living map stay selected by `layer`. The 24-hour animation of traffic and crowd density is a control of the screen (document 10), not a directive. No directive opens a drawing, places a shape or loads a sample file: a shape comes only from the user's drawing, and a sample file only from the case route, when the user chooses one of the closed sample-file keys of the case or starts the case with one click (BE-118).

| ID | Requirement |
|---|---|
| BE-56 | The tool registry contains exactly the names of section 6.2: the nine tools of the first pack, the ten journey tools of [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) and the playbook-only `own_records`; a test fails on any other. The model is offered every name but `own_records` ([02](02_ARCHITECTURE.md) ARC-71). A further tool is a versioned change with its own contract and parity case. |
| BE-57 | Every release table of the master design (section 5.4), and every table that decisions 0016 and 0017 add to the catalogue of document 03 section 7.2, is read by at least one tool or endpoint, or is listed in the registry as control-only; a test checks this list against the manifest allow-list. |
| BE-58 | `flow_hourly`, which replaces the first pack's `flow_od`, is read only by the layers endpoint (`GET /api/layers/flows`, section 8.1) and appears only as aggregate flows. The traffic assignment reads the released flows at build time in the custodian plane ([02](02_ARCHITECTURE.md) ARC-133); no product code assigns traffic. |
| BE-59 | Only `synthetic_firms` returns fictional firms, each with only its fictional name, activity, size band and release unit (BE-113). A Synthetic or Simulated fact may appear only in a claim or component whose subject is `area`, or, for a Synthetic fact of one named synthetic firm, `synthetic_firm`; the validator decides this from the resolved place, subject and fact slots, never from wording. Claims with subject `place_public` or `fdi_project` accept Public slots only, and cards showing Synthetic or Simulated area facts are titled as statistics of the area (the shape the user drew, or the area within reach of the pin), never of a named building, business or place (master design sections 3.3, 8 and 16; [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 20). |
| BE-105 | In public-only mode (a mounted release whose tables are Public only, slice S3), `make_area` uses the fixed base-cell frame: it reads no privacy-derived `release_unit` and no protected or simulated table, its area is the set of frame cells selected by the shape plus the pin's base cell, and it emits the snap report as technical metadata, not as a Synthetic fact. When a protected release is mounted, BE-54 and the snap rule of document 06 apply unchanged. |

## 7. Playbooks and the template writer

A playbook is a fixed, deterministic list of tool calls. Its output is an evidence bundle: release id, playbook, inputs, ordered plan steps, stage directives, cards (each a list of fact ids) and all facts. Bundles are memoised by `(playbook, normalised inputs, release_id, rules_version)`; a bundle is language-independent because every fact carries both labels, so a language flip re-uses it. Every brief carries a `catalogue_version` hash, and that hash is also part of the brief memo key. A bundle that uses a case sample file is never memoised (BE-118).

The playbook list is the closed, versioned list of document 09 section 3: the three playbooks of the first pack and the ten added by [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), which together cover the seven journeys, three services and four cases. Document 09 names each playbook, its journeys, services and cases, and the evidence it gathers; this table fixes the calls of every bundle, and where the two differ this table wins and document 09 is corrected. "Near area" is the walk 5 area, or the shape the user drew, a radius or a walk time; "wider area" is the drive 10 area, or a drive time by hour.

| Playbook | Order of calls | What lands on screen first |
|---|---|---|
| `site_check` | `resolve` → `make_area` near area → `make_area` wider area → `stage` fly and rings → `area_evidence` (presence by hour for the selected day, worker_pay, register, public_context on the near area; resident_pay, coverage on the wider area, and traffic when the wider area is a drive area) → `scan_places` (near area, with neighbours) → `sector_facts` unit_economics | Fly, rings and snap report; then four hero cards in this order: who is present (estimated people around this location, by hour), real competitors with distances, pay of workers and of residents with the coverage bar, restaurant unit economics. |
| `staffing_and_pay` | `resolve` → `make_area` drive 30 → `stage` fly and rings → `area_evidence` (resident_pay, worker_pay, coverage) → `pay_benchmark` → `sector_facts` pay_decomposition | Snap report; pay of workers and of residents with the coverage bar; staffing pay card; national pay card. |
| `costs_and_suppliers` | `resolve` → `investment_context` incentives → `sector_facts` unit_economics (with scenario inputs and the incentive package the user chose, when given) → `stage` set_scenario_inputs → `supplier_lens` | Unit economics and break-even card; supplier path card. |
| `market_entry` | `resolve` (activity) → `sector_facts` employer_scale, licences and market_context → `area_ranking` (candidate areas) → `area_evidence` (resident_pay, public_context) on the first-ranked candidates → `scan_places` on the first-ranked candidate → `labour_facts` → `investment_context` fdi_projects, sectors, setup_steps and laws → `stage` fly and layer | The market entry pack: market profile, customers and competitors, local income context, candidate areas, workforce context, set-up steps and the cheapest next tests. |
| `rank_areas` | `resolve` (activity) → `area_ranking` (full, or public-only) → `stage` layer and highlight → `similar_areas` and `reachable_access` (by hour when an hour is selected) for the first-ranked candidate | The ranked candidates with every criterion, weight and value, and the rank-stability sentence beside every rank. |
| `site_fit` | `resolve` (place) → `make_area` near area → `stage` fly and rings → `activity_fit` → `area_evidence` (presence by hour, register, resident_pay, public_context) → `scan_places` | Activities ranked by fit with their criteria and rank stability; the area's business mix and pay profile. |
| `customer_finder` | `resolve` (activity) → `area_ranking` (the territory) → `synthetic_firms` prospects on the first-ranked candidates → `sector_facts` employer_scale, licences and visitor_markets → `area_evidence` public_context on the first-ranked candidate → `labour_facts` (students) → `stage` layer and highlight | The targeted territory and the prospect list of named synthetic firms by sector and size band. |
| `partner_finder` | `resolve` (activity) → `make_area` near area, or the territory the user chose → `synthetic_firms` partners or suppliers, with weights → `scan_places` → `supplier_lens` → `labour_facts` → `investment_context` fdi_projects (and tenders once a public source exists) → `stage` rings | Named synthetic firms ranked by fit, real businesses from public listings, the structured qualification route and aggregate workforce evidence. |
| `labour_market` | `resolve` (activity or occupation) → `labour_facts` (with the split and projection the user asked for) → with an area: `pay_benchmark` and `what_changed` worker_pay → `stage` | Pay bands with middle ranges and earner counts, trends, published series and splits with source and year, and projections marked as projections. |
| `where_to_grow` | `resolve` → `make_area` current site → `make_area` candidate site → `stage` split → `openings_closures` (both areas) → `what_changed` (both areas) → `area_evidence` public_context (both areas) → `compare_areas` → `investment_context` fdi_projects → `stage` month | Openings and closures over time, cluster change and the second-site comparison as shared reach and overlap, with the barriers to resolve. |
| `serve_region` | `resolve` → `make_area` near area → `travel_times` (every destination, at free flow and at the selected hour) → `supplier_lens` → `synthetic_firms` complementary → `scan_places` → `investment_context` fdi_projects → `stage` fly and layer | Travel times to the ports, the airport, the free zones and the land routes, complementary firms and the import context. |
| `depot_options` | `make_area` current depot and candidate depot, as drive areas at the selected hour → `own_records` (concentrations, and access with the candidate depot's `area_id`) → `stage` split → `compare_areas` → `synthetic_firms` partners → `scan_places` | The company's customer concentrations beside the two drive areas and their shared reach, and the partner candidates: a defined trial before the capital commitment. |
| `branch_check` | `own_records` (branch_sales) → `make_area` the branch's near area → `stage` fly and rings → `area_evidence` (presence by hour, resident_pay) → `what_changed` → `scan_places` | The branch's own sales beside estimated people by hour, residential pay bands and what changed in the area: a test of hours or offer. |

The four cases of decision 0016 are guided stories with a one-click start: case C1 runs `market_entry` and `partner_finder`, case C2 `customer_finder`, case C3 `depot_options` and case C4 `branch_check` (document 09 owns the stories). Without a loaded sample file, the `own_records` blocks of `depot_options` and `branch_check` return `NO_DATA` and the rest of the bundle runs.

ASSUMPTION (site check): workers, presence and outlets use walk 5 and residents use drive 10, because those are the two flagship defaults (master design section 6) and lunch trade is local. Staffing uses drive 30, the staffing-only cut-off pinned by the master design.

The template writer and the model path share the versioned catalogues under
`product/assistant/catalogue/`: `claims.yaml`, `components.yaml`, `fragments.yaml` and
`questions.yaml`. The template writer turns a bundle into the same structured brief as the model
path: `headline_key`; `decision_template_key`; `observed[]` and `inferred[]` items with `claim_key`
and fact-id `slots`, plus `strength` (`strong`, `indicative` or `illustrative`) for inferred items;
application-selected `still_to_test[]` and
`not_measured[]`; `next_questions[]` with `question_key` and `slots`; `layout[]` with `component`
and `props`; and `stage[]` directives. The model understands the question, plans tool calls, and
selects and orders claims, components and next questions. It writes no prose. The application owns
all templates, fills every number from fact ids and adds the privacy receipt (Arabic pending native
review, OI-09).

| ID | Requirement |
|---|---|
| BE-60 | A playbook runs with no model call and its bundle is byte-identical across runs and engines (apart from BE-27 exclusions). |
| BE-61 | At build time, a lint test scans every claim and fragment template and rejects numerals, number words, names of real places inside `area` claims, go or no-go wording, "footfall of" wording and wording of advice to act. No run-time scan of model prose exists because no model-written prose reaches the screen in version 1. |
| BE-62 | The template writer places a fact in Observed or Inferred by its `evidence_status`, never by its provenance; a Synthetic observed fact never reads as real. |
| BE-63 | The template writer's output passes the same structured-brief and catalogue validator as model output (document 09). One invalid item rejects the brief; after one repair attempt, the template writer composes the brief from the playbook's default selection. |
| BE-64 | When the model is absent, refuses, or fails validation, the answer completes with the template writer and the stream reports `writer: template`. |

## 8. The API

One FastAPI process on one port serves the API, the server-sent events, the built front end, tiles and fonts. Server-sent events use FastAPI's `EventSourceResponse` and `ServerSentEvent` (added in FastAPI 0.135.0; it sends a keep-alive comment every 15 s and supports resumption through `Last-Event-ID`, FastAPI documentation).

### 8.1 Endpoints

The seat picker runs once in each window and its fixed selection handler binds the choice to that
window with a signed session cookie named `eii_seat`. After selection, the API verifies the cookie
and reads the seat only from it, never from the address or a request field. The signed cookie is a
window binding, not authentication. `EventSource` therefore needs no custom seat header.

| Method and path | Request | Response |
|---|---|---|
| `GET /health` | none | the health object with exactly the fields document 13 defines (store, PostgreSQL state, release, parity, ledger, model mode, tiles, fonts, replays) |
| `GET /api/release` | none | manifest summary: release id, tables, rules version, the exported parameter set of this release, and the closed hour, day and month key lists, as data (BE-103); no route offers a choice of set |
| `GET /api/seats` | none | the three seat keys with labels, for the seat picker |
| `GET /api/seat/whoami` | none | `{seat, organisation_label_en, organisation_label_ar, fictional: true}`: the Viewing-as value from the signed cookie |
| `POST /api/ask` | `{question, lang}` plus optional `{pin, shape_id, mode, cutoff, situation, summer, hour_key, day_key, month_key, scenario_inputs, case_key}` | `202 {answer_id, events_url}` |
| `POST /api/playbooks/{playbook}` | structured playbook inputs, for any playbook of section 7 | `202 {answer_id, events_url}`; never calls the model |
| `GET /api/answers/{answer_id}/events` | `Last-Event-ID` header optional | event stream (section 8.2) |
| `POST /api/tools/{tool}` | tool input model of any tool of section 6.2 | tool result envelope; used by the dial, the hour, day and month controls, pins, drawn areas and area cards with no model |
| `POST /api/areas/shapes` | `{geometry}` exactly: one GeoJSON polygon from the user's drawing | `201 {shape_id}`, bound to the session and seat (BE-117); `422 INVALID_ARGUMENT` for an extra property or a polygon that is not simple, lies outside the frame or exceeds the vertex or size limit. Not model-callable |
| `GET /api/cases` | none | the four cases with their labels, the playbooks each runs and their one-click start inputs; for cases `c3` and `c4`, the closed key and label of each committed synthetic sample file (BE-118) |
| `POST /api/cases/{case_key}/sample-file` | `{sample_key}` exactly, with no other property: the closed key of one committed synthetic sample file of the case; `case_key` is `c3` or `c4`. No file body is accepted (BE-118) | `201 {case_key, sample_key, sample_sha256}`: the server loaded the committed file that the key names, after checking that its SHA-256 equals the committed value, and holds it in the session store for this session and seat (BE-118); `422 INVALID_ARGUMENT` for another case key, an unknown sample key, an extra property, or a body that carries a file, a path or a URL, with nothing kept; `500 INTERNAL` when the committed file's SHA-256 differs from its committed value or the file fails the case's column schema, with nothing loaded. Not model-callable |
| `GET /api/cases/{case_key}/sample-file/facts` | none | the facts that `own_records` computes from the loaded file (BE-118); `404 NOT_FOUND` when this session and seat loaded none |
| `DELETE /api/cases/{case_key}/sample-file` | none | `204`; drops the file, its facts and any brief that used them from the session store |
| `GET /api/facts/{fact_id}/lineage` | none | the fact's source chain — table, source, licence, retrieval date, release, rules — shown by the evidence drawer under the label "Source chain"; the API emits no fact whose `lineage_ref` does not resolve to a complete chain (BE-104) |
| `POST /api/briefs` | `{answer_id}` | `201 {brief_id}` |
| `GET /api/briefs` | none | own briefs through the company read function |
| `GET /api/briefs/{brief_id}` | none | brief, or 404 (BE-39) |
| `GET /api/oversight/ledger` | `since`, `limit` | fixed oversight function result, with no organisation identity or question text |
| `GET /api/oversight/ledger/events` | none | live ledger stream using the same oversight return type |
| `GET /api/oversight/demand` | `by` (`area`, `activity`, `decision`) | aggregates above the distinct-organisation minimum |
| `GET /api/layers/{layer}` | `situation`, `summer`; from decision 0016, `day_key`, `hour_key` or `hours=all` (the 24-hour animation, for `traffic` and `crowd_density` only), and `month_key` | layer values as facts for one key of the closed layer list: `zone_electricity_growth`, `licence_density`, `transit_riders`, `presence` (estimated people by hour, replacing `presence_index`), `crowd_density`, `traffic`, `flows`, `public_places`, `release_units`, `openings`, `closures`, `firm_density`, `fdi_projects`, `property_prices`, `construction_pipeline` (ASSUMPTION: the list the opening scene, the dial, the hour, day and month controls and the journeys need). Simulated layers carry the Simulated mark on every frame; a Public layer stays on its official geography. JSON, or Arrow when the client asks for it and the layer exceeds about 10,000 rows (document 10). |
| `GET /api/proof/parity`, `GET /api/proof/survival`, `GET /api/trust` | none | parity report; the survival report with one aggregate row per parameter set (PRV-80); the signed attack report replay, verified at start-up as PRV-107 requires; rules text generated from `rules_version` and the tool registry |
| `POST /api/proof/scene` | `{fixture_id: string}` exactly, with no other property; a fixture id is `scene:` followed by the lowercase SHA-256 already listed for its signed scene artefact in `manifest.artefacts` (PRV-119, BE-106) | `200`: the two pre-validated unit sets and area answers of that artefact's two prepared requests. `422 INVALID_ARGUMENT` for an extra property or a fixture id not of that form; `404 NOT_FOUND` for a well-formed id absent from `manifest.artefacts`. It is not one of the tools of section 6.2 and is not model-callable (PRV-100); it has no custodian-plane path |
| `GET /api/presenter/state` | `X-EII-Presenter-Token` header | store, PostgreSQL state, ledger state; only when `EII_PRESENTER=1` and the per-session token is valid |
| `POST /api/presenter/switch-to-embedded` | `X-EII-Presenter-Token` header | `202 {effective: "next_request"}`; only when `EII_PRESENTER=1` and the per-session token is valid |
| `GET /`, `/assets/*`, `/tiles/*.pmtiles`, `/fonts/*` | none | built front end, basemap with HTTP range requests, glyphs |

Example request and acknowledgement (the coordinates are placeholders):

```json
POST /api/ask
Cookie: eii_seat=<signed session value>
{"question": "Is this a good spot for an Italian restaurant?", "lang": "en",
 "pin": {"lat": 0.0, "lon": 0.0}, "mode": "walk", "cutoff": 5}

202 {"answer_id": "uuid", "events_url": "/api/answers/uuid/events"}
```

### 8.2 The event stream

The answer stream carries the event kinds that document 09 emits and document 10 consumes. The `answer_id` is the stream key that document 10 calls the brief id; the SSE `id` field is the per-answer sequence number. `data` is JSON.

| Event | Document 09 event kind | Data |
|---|---|---|
| `plan_step` | plan step | `{step_id, tool, label_en, label_ar, state: "pending" or "running" or "done" or "failed"}` |
| `stage` | stage directive | one object of the `stage` schema (section 6.2) |
| `evidence` | evidence card | `{card_id, kind, status, fact_ids, facts, caveat_keys, template_key}` |
| `receipt` | (application) | the privacy receipt with the accounting-gate result under "Checked before display" (BE-107), and a summary of egress records for this answer |
| `narrative` | structured brief item | One validated item of document 09's brief schema, using `claim_key` and fact-id `slots` for Observed and Inferred items, or the pinned key and slots for another section. It carries no model-written prose. |
| `withdrawn` | brief withdrawn | `{item_ids}`: model items withdrawn before a repaired or template brief replaces them |
| `status` | fallback | `{writer: "model" or "template" or "replay", status, template_key, note_key}` |
| `error` | (application) | `{code, message_key, error_id}`; closes the stream |
| `done` | brief complete | `{answer_id, brief}`; closes the stream |

The oversight ledger stream uses `ledger_entry` (one row in the fixed oversight return type), `paused` and `resumed`.

Every answer follows the five stages of the master design (section 17.4): First reading (the "We understood your question as…" chips), Watchfulness (scope and decline rules), Striving (the full deterministic evidence bundle), Accounting (the accounting gate of BE-107) and Answer (Observed, Inferred, Still to test, with the receipt). Document 09 owns the stage logic; this document fixes the wire: `evidence` events may be sent as soon as their facts are complete, each with its complete source chain, and the whole structured brief is buffered until the accounting gate has passed on it (BE-107).

| ID | Requirement |
|---|---|
| BE-65 | Every `evidence` event of the playbook bundle is sent before the first `narrative` event, and every fact id in a structured brief item's `slots` has been sent in an earlier `evidence` event. Components appear only after their typed catalogue schemas validate. The whole structured brief is buffered until the accounting gate has passed on the complete brief (BE-107); evidence events are not held back by it. |
| BE-66 | Reconnecting with `Last-Event-ID` replays every later event of the same answer exactly once and in order. |
| BE-67 | Every request body model forbids unknown fields; playbook, tool, layer, situation, cutoff, hour, day, month, case and sample-file key values are closed enumerations. The one-time seat-selection handler accepts only the three pinned seat keys and no later route accepts a seat field. |
| BE-68 | Company seats calling an oversight route receive 403 `SEAT_FORBIDDEN`; an unknown seat receives 404. |
| BE-69 | Every tool call on any route writes one ledger entry, whether it came from the model, a playbook or a direct call. |
| BE-106 | `POST /api/proof/scene` is the sole non-production area endpoint (PRV-119). Its request body is exactly `{fixture_id: string}` with no other property; a fixture id is `scene:` followed by the lowercase SHA-256 already listed for its signed scene artefact in `manifest.artefacts`. The endpoint resolves that id only to the artefact's two prepared requests and returns their two pre-validated unit sets and area answers. It accepts no pin, polygon, cut-off, arbitrary cell or unit id, SQL, question text or model argument; it is not one of the tools of section 6.2, is not model-callable (PRV-100, PRV-101) and has no custodian-plane path. An extra property or a fixture id not of that form is rejected with `INVALID_ARGUMENT`; a well-formed id absent from the manifest is rejected with `NOT_FOUND` (ASSUMPTION: the code split; PRV-119 requires only rejection). |
| BE-107 | The accounting gate is a code module of the product plane with exactly five checks — Sources, Assumptions, Nothing invented, Scope, Limits stated (master design section 17.3) — each reported as pass or fail. It runs after the catalogue validation of BE-63 and before any `narrative` or `done` event is sent: the whole structured brief is buffered, the five checks run once on the complete brief, and only then is the brief sent. `evidence` events may be sent earlier, each fact with its complete source chain. On any failed check the template writer's default answer is sent, the failure is logged with the BE-94 fields, and the receipt carries each check's result under "Checked before display". |

### 8.3 Drawn shapes and case sample files

A drawn shape enters from the browser. A case sample file never does: the browser posts only the closed key of a committed synthetic sample file, and the server loads that committed file itself ([10](10_FRONTEND.md) FE-120). Neither comes from the release or the model, and both stay in the session store of BE-109 for the session and seat that drew the shape or loaded the file ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md); [02](02_ARCHITECTURE.md) section 3.8, ARC-128).

| ID | Requirement |
|---|---|
| BE-117 | `POST /api/areas/shapes` is the only way a polygon enters the product. It accepts one GeoJSON polygon from the user's drawing, checks it with `eii_core.shapes` (simple, inside the frame, within the vertex and size limits fixed at the slice S2 gate), and stores its canonical form in the session store under a `shape_id` that is the SHA-256 of that form, bound to the session and seat. `make_area` accepts a `shape_id` only from the same session and seat. The route is not model-callable, and the model never writes a coordinate of a shape. Ledger rows and logs record the `shape_id` or the `area_id`, never the coordinates. |
| BE-118 | `POST /api/cases/{case_key}/sample-file` is the only way a case sample file enters a session, and it takes a closed key, never a file (ASSUMPTION: version 1 receives no file from the browser, so no real record can enter; [02](02_ARCHITECTURE.md) ARC-128, [10](10_FRONTEND.md) FE-120). It accepts only the case keys `c3` and `c4` and a request body that is exactly `{sample_key}`, the closed key of one of that case's committed synthetic sample files (document 03 DAT-150). It refuses with `INVALID_ARGUMENT` another case key, an unknown sample key, an extra property and any body that carries a file in any encoding, a path or a URL, and it keeps nothing of a refused request. The server reads the file that the key names from the committed sample files shipped with the application ([13](13_DEPLOYMENT_AND_OPERATIONS.md) OPS-67), never from a location the request gives, and loads it only when its SHA-256 equals the committed value; a file whose SHA-256 differs, or that fails the case's closed column schema (document 03 section 12.2), is not loaded, nothing of it is kept, and the route returns `INTERNAL`; the log records the failure but no content of the file (BE-95). A loaded file is held in the session store for the session and seat that loaded it. `own_records` computes its facts with `eii_core.calc`: provenance `synthetic`, the caveat key `your_inputs`, evidence status `inferred`, marked as a sample file that stands for the company's own records, with a lineage that names the method card and the committed file's SHA-256. The file, its facts and any brief that uses them are never written to the release, a store, `app.brief`, `ledger_entry` (which records only the call, the case key and the status), `egress_record`, a log or the memo; they are never sent to the model (ASSUMPTION: the egress record keeps exact payloads beyond the session), so the template writer places their cards; and another seat or the oversight seat receives 404 with the same body as for a case with no file. Saving such a brief returns `INVALID_ARGUMENT`. |

## 9. Seats and the ledger

### 9.1 Seats

The seats are a seat picker, not an identity system: there are no passwords and no accounts. The pinned keys are `oversight`, `company_a`, `company_b`; each maps to one fictional organisation in `app.seat`. Organisation labels are seed data that must pass the name-collision check of document 05. The seat is chosen once per window and bound by the signed `eii_seat` session cookie. This demonstrates query isolation after selection, not tenant authentication or adversarial company separation.

| ID | Requirement |
|---|---|
| BE-70 | After the one-time picker selection, the verified signed `eii_seat` cookie is the only seat source. The API derives the organisation through `read_seat_context` and sets `eii.seat` and `eii.organisation` with transaction-local `set_config` inside each transaction, never session-wide. No seat-scoped address or request field is accepted. |
| BE-71 | The Viewing-as value is read through the canonical seat-context function under the same seat setting as the data it labels; in embedded mode it reads a constant and adds "(local)". |
| BE-72 | Pooled connections are checked out per transaction; a test proves a seat setting never survives into the next transaction on the same connection. |

### 9.2 The ledger in PostgreSQL

`app.ledger_entry` uses exactly the canonical DDL in [document 03, section 12](03_DATA_CONTRACTS.md#12-the-application-schema-postgresql-only-schema-app); this document does not restate its columns. The application generates UUIDv7 identifiers in Python with `uuid.uuid7()` (added in Python 3.14). Tool arguments are stored without scenario-input values, without a drawn shape's coordinates (only its `shape_id` or `area_id`) and without any content of a case sample file (BE-117, BE-118). Question text is available only through the asking company seat's read function; the fixed oversight return type omits it (BE-38).

After the insert, the same transaction runs `SELECT pg_notify('eii_ledger', :entry_id)`. Notifications are delivered only when the transaction commits, and the payload must be shorter than 8,000 bytes by default (PostgreSQL 18 documentation), so only the id is sent and the listener calls the fixed oversight read function.

| ID | Requirement |
|---|---|
| BE-73 | Ledger and egress inserts use `INSERT … ON CONFLICT (entry_id) DO NOTHING` (respectively `egress_id`), a form both PostgreSQL and SQLite accept, so a replayed row is never duplicated. |
| BE-74 | `eii_app` cannot update or delete a ledger or egress row (append-only by privilege). |
| BE-75 | The fixed oversight demand path shows a group only when it holds at least the configured `distinct_organisation_minimum`, default 2. This is demonstration configuration for the two-company POC, not a disclosure threshold. The fixed database function performs the aggregate and returns no organisation identifier. |
| BE-76 | Seeded history rows have `origin = 'seeded'` and are marked Synthetic on screen; live rows are tagged "this session" (OI-08 default). |

### 9.3 The SQLite fallback

| ID | Requirement |
|---|---|
| BE-77 | When the store is embedded, or a PostgreSQL ledger or egress insert fails, the row is written to the local ledger `data/ledger_local.sqlite` with the same columns and the same identifier, and the oversight seat shows "paused". |
| BE-78 | Replay into PostgreSQL runs only at start-up (`./eii up` with PostgreSQL answering), in identifier order, marking each local row replayed only after commit and reporting the count; replaying twice is harmless (BE-73). The presenter switch is one-way, so there is no replay during a session. |
| BE-79 | In embedded mode, saving briefs is unavailable and the API says so with `BRIEF_STORE_PAUSED`; no brief is written to SQLite (ASSUMPTION: keeps the database-backed query-isolation demonstration inside PostgreSQL only). |

### 9.4 The egress record

`app.egress_record` uses exactly the canonical DDL in [document 03, section 12](03_DATA_CONTRACTS.md#12-the-application-schema-postgresql-only-schema-app), including UUIDv7 identifiers and direct row-level-security keys. Document 09 decides what may be sent and runs the egress scan; this document stores the result. The fixed oversight return type omits the payload itself as well as organisation identity, question text and brief text. A call that the egress scan blocks keeps no payload at all, only the hash of the proposed payload (BE-80; document 03 DAT-156).

| ID | Requirement |
|---|---|
| BE-80 | Every attempted provider call—sent, blocked by the egress scan, failed, refused or timed out—writes exactly one egress record before any response content is used. A blocked call records `scan_result=blocked` and, of its proposed payload, only the SHA-256 in `payload_sha256`: `payload_bytes` and `payload_json` are null, `fact_ids_sent` is empty, and `sent_at`, transport usage, stop reason and cost are null; no provider connection is opened (document 03 DAT-156; document 09 AI-82). A listed firm's fictional name or released key that the scan found is therefore in no column of the row. The local ledger applies the same rule to its rows. Failure to persist this record in PostgreSQL or the local ledger discards the response and selects the template writer. |
| BE-81 | For a call that passed the egress scan, the canonical DDL's exact-payload column stores the precise UTF-8 bytes as `bytea` and `payload_sha256` hashes those bytes; for a blocked call no bytes are kept and `payload_sha256` is the hash of the proposed bytes (BE-80). A separate parsed `jsonb` projection is optional, null for a blocked call, and is never treated as byte preservation. A test re-hashes the stored bytes of every passed row and checks the parsed projection against them when present. |

## 10. Routing

pyvalhalla runs in-process on the OpenStreetMap Qatar extract; the routing tiles are a release artefact listed in the manifest. The methods research reported a graph built in 5 s and a three-ring area in 0.12 s (cited by the feasibility judge, 2026-11-11). Valhalla's isochrone service takes minutes per contour and returns GeoJSON polygons (Valhalla documentation).

| ID | Requirement |
|---|---|
| BE-82 | `distance` areas use no routing. For protected figures the area is the cells of the frame whose centres lie within the cutoff great-circle distance of the pin cell's centre, snapped by BE-84. For Public points and Simulated layers the exact outline is the circle of the cutoff radius around the point. |
| BE-83 | Catchments for the story pins (every distance, walk and drive cut-off, including drive 30 for staffing only, each applicable situation, and each hour and day key the guided stories and cases use) are precomputed at release time and read from a manifest-listed artefact; a live pin or a drawn shape computes its area on request. Privacy, routing and parity tests include drive 30 for `staffing_and_pay`. |
| BE-84 | A catchment polygon becomes cells of the frame at the pin's resolution, and a drawn polygon becomes cells of the frame at their own frame resolution; both then become whole release units by the snap rule of document 06 before any protected figure is read. Public points and Simulated layers use the exact polygon. The cell-containment rule of the H3 library is confirmed at slice S1. |
| BE-85 | Time-of-day differences come only from the hourly link speeds of the traffic assignment (by road link, hour and day key; [02](02_ARCHITECTURE.md) ARC-133), and every such fact is Simulated. A `situation` uses the hours that `situation_windows` gives it, combined as document 07 defines. The mechanism (per-request costing options, the routing engine's own time-dependent speeds, or build-time catchments for live pins) is chosen at slice S1 and written down; no proprietary congestion data is used. |
| BE-119 | `travel_times` and `reachable_access` use the routing graph and hourly link speeds that `make_area` uses. A travel time to a destination (a port, the airport, a free zone or a land route) is a fact of the trip from the area, with subject `area`; the destination appears only as a Public label, and no Synthetic or Simulated figure is presented as the destination's own. |

## 11. Areas, configuration, start-up and the presenter switch

### 11.1 Area ids

`area_id` is a readable, self-describing string: release prefix, mode, cutoff, pin cell, situation and summer flag, and from decision 0016 the point (to the six decimal places of the gazetteer's coordinates), the hour and day keys, or the official geography or release unit of a candidate returned by `area_ranking`. Any process can recompute such an area from it, so no server state is needed. For a drawn polygon the `area_id` carries the `shape_id` (the SHA-256 of the canonical shape) instead, and only the session and seat that hold the shape can decode it (BE-117).

| ID | Requirement |
|---|---|
| BE-86 | Decoding an `area_id` and calling `make_area` again yields the same units and the same outline; an `area_id` from another release, or a drawn-shape `area_id` of another session or seat, returns `INVALID_ARGUMENT`. |

### 11.2 Configuration and preflight

Pinned variables: `ANTHROPIC_API_KEY` (optional; supplied for go-live and not used during the build; absent, or the live adapter not switched on by the owner, means template writer only), `EII_STORE` (`postgres` or `embedded`), `EII_DATABASE_URL`, `EII_RELEASE_DIR`, `EII_LANG_DEFAULT` (`en` or `ar`), `EII_PRESENTER` (`0` or `1`). Secrets come from the environment only; `.env` is never committed.

Preflight checks (the full list and output format are in document 13), in order: variable values;
release directory and manifest hashes; a complete matching `load_receipt.json`; `release.duckdb`
digest; routing tiles, PMTiles and glyphs present; for PostgreSQL, a connection within 5 s
(architecture research), BE-31, BE-32 and BE-34, the release schema hash, `app` tables with forced
row-level security and fixed read-function privileges, and PostGIS 3.6 (a wrong version is `FAIL`);
the vault rule (BE-05); the API key's presence (never its value). Whenever `EII_RELEASE_DIR` is
unset, foundation preflight prints `WARN not_configured` for the release, load-receipt,
embedded-reader and recorded-replay checks and those warnings do not make it fail; every other
check retains its normal severity. `./eii up` always requires a configured complete release. From
the slice S3 gate onward every gate runs preflight with `EII_RELEASE_DIR` set.

`./eii preflight` only probes and never starts or stops anything. `./eii db-up` and `./eii db-down`
are the only database start and stop commands; the database start waits up to 60 seconds inside
`db-up`. `./eii up` never starts a database and serves from the store preflight found. Network,
socket, process and Docker probes have five-second time-outs; hashing, replay validation and the
sandbox test use their separately recorded budgets.

| ID | Requirement |
|---|---|
| BE-87 | Store selection follows document 13 and is authoritative for that invocation: `postgres` when PostgreSQL answers and passes its checks, otherwise `embedded` with a `WARN` line naming the reason; `./eii up --embedded` selects `embedded` without contacting PostgreSQL. Whenever `EII_RELEASE_DIR` is unset, foundation preflight uses `WARN not_configured` for the release, receipt, embedded reader and replay checks only. `./eii up` always requires a configured complete release, never starts a database, passes the preflight selection to the API process as `EII_STORE`, and reports it in `/health`. A PostgreSQL that answers but fails BE-31, BE-32, BE-34 or the PostGIS version check is a `FAIL`, not a silent fall-back. |
| BE-88 | The API opens the embedded reader at every start. With the store `postgres`, it refuses to start (exit 4) unless the embedded reader and the PostgreSQL release schema carry the same `release_id` and digests and a complete receipt covers both. `./eii up` never reloads over an existing schema: a full-release-id or hash mismatch exits 4 and changes neither store. |
| BE-89 | Every presenter route requires `EII_PRESENTER=1`, a loopback request and the per-session `X-EII-Presenter-Token` header. A cryptographically random token is generated at each `./eii up`, supplied to the presenter console and never written to logs, ledger rows or health responses. Missing or incorrect tokens receive 403 on every window, including company windows. The switch is one-way for the session; it applies to answers and direct tool calls that start after it, while answers in flight finish on PostgreSQL, so one answer never mixes stores. |
| BE-90 | No code path changes the store in the middle of a request or answer, and no health probe switches stores automatically. |

## 12. Error handling and logging

Model unavailability is not an error: it is reported as a `status` event with `writer: template` (ASSUMPTION). Errors use these codes:

| Code | HTTP | Meaning |
|---|---|---|
| `INVALID_ARGUMENT` | 422 | input fails its model |
| `SEAT_FORBIDDEN` | 403 | company seat on an oversight route |
| `NOT_FOUND` | 404 | unknown seat, answer or brief (including briefs not visible), a scene fixture id absent from the manifest (BE-106), or a case sample file this session and seat did not load (BE-118) |
| `BRIEF_STORE_PAUSED` | 503 | brief saving unavailable in embedded mode |
| `STORE_UNAVAILABLE` | 503 | the selected store did not answer |
| `QUERY_TIMEOUT` | 504 | statement exceeded its timeout |
| `RELEASE_MISMATCH` | 503 | store release differs from the configured release |
| `RATE_LIMITED` | 429 | seat exceeded its request rate |
| `INTERNAL` | 500 | anything else |

| ID | Requirement |
|---|---|
| BE-91 | Error bodies are `{"error": {"code", "message_key", "error_id"}}`; no stack trace, SQL text or file path ever reaches a client. |
| BE-92 | Release reads run with a 2,000 ms statement timeout (ASSUMPTION: measured tool queries take 0.4 to 3 ms, so this only stops pathology). |
| BE-93 | Each seat is limited to 10 asks per minute (ASSUMPTION: generous for a demonstration, bounds model spend). |
| BE-94 | Logs are JSON lines on standard output with `ts`, `level`, `event`, `answer_id`, `seat_key`, `tool`, `engine`, `release_id`, `status`, `duration_ms`, `error_code`, `error_id`. |
| BE-95 | Logs never contain the API key, request headers, model payloads (only `egress_id`), question text, scenario-input values, a drawn shape's coordinates, or a case sample file or any value computed from it. |

## 13. Performance budgets

All values are targets, to be measured on the build machine and recorded; none is a promise.

| Measure | Target | Basis |
|---|---|---|
| Evidence bundle, flagship, 95th percentile, local | under 1.5 s | slice S6 gate |
| Evidence on screen / checked brief, no live model / checked brief, live model | 2 s / 6 s / 20 s | master design section 10; targets to be measured, not promised. The brief is never streamed item by item: the accounting gate runs once on the complete buffered brief (BE-107), and evidence events may appear earlier. "No live model" means the template writer or a recorded provider |
| One named query, 95th percentile | under 50 ms | ASSUMPTION; measured medians 0.4 to 3 ms (architecture research) |
| Live catchment for a new pin | under 500 ms | ASSUMPTION; 0.12 s reported for a three-ring area |
| `./eii up` to ready, release already loaded | under 15 s | ASSUMPTION |
| Ledger entry visible on the oversight seat | under 1 s | value-candidate statement in the architecture research |

Whole-country aggregates are precomputed at build time: PostgreSQL took 104 ms at the median on one such query against 4.3 ms for DuckDB (architecture research). Targets for drawn areas, hourly layers, the 24-hour animation, rankings and the case files are set when the slices that build them are planned (OPEN), then recorded under BE-96.

| ID | Requirement |
|---|---|
| BE-96 | A benchmark command records each target above with the release id, engine and machine description; a regression of more than 50% against the last recorded value fails the run (ASSUMPTION threshold). |

## 14. Security rules

| ID | Requirement |
|---|---|
| BE-97 | No model output, user text or API field is ever executed as SQL or used to choose a table. Release queries come only from the hashed files in `store/sql/`, whose digests are logged at start-up; `app` schema statements are fixed strings in `ledger/` and `api/` with bound parameters only. |
| BE-98 | Release reads use read-only connections: `READ ONLY` transactions as `eii_app` (which holds only `SELECT` on release schemas) and a `read_only=True` DuckDB connection. |
| BE-99 | The product has no path to the vault: BE-02, BE-05 and the loader's manifest check together; a test runs the API with `data/vault/` present and unreadable and proves start-up and every tool still work. |
| BE-100 | The API binds to `127.0.0.1` by default; cross-origin requests are not enabled. |
| BE-101 | Text from third parties (place names, activity descriptions, the fields of FDI projects, the titles of the agency's records) reaches the model only as JSON string values inside tool results (document 09), and the screen shows it only through application templates. |

## 15. Tests each module ships with

The strategy, fixtures and CI layout are in [12 Testing and quality](12_TESTING_AND_QUALITY.md). Each module ships with at least these tests, each tied to the requirements above.

| Module | Tests |
|---|---|
| `eii_core.provenance`, `facts`, `calc` | least-real rule table; deterministic `fact_id`; strict model rejects unknown fields; every method card's worked example reproduced, comparison facts included (BE-104, MTH-03) |
| `eii_core.text` | normalisation cases in both languages |
| `eii_core.shapes` | canonical form and hash of a polygon; refusal of a self-intersecting polygon, a polygon outside the frame and one over the vertex or size limit; point-in-shape cases on both sides of the Greater Doha resolution boundary (BE-117) |
| import boundary | BE-01 to BE-06 and BE-102, including the offline-gateway boundary |
| `store/lint.py` | each forbidden construct rejected; every allowed construct accepted (BE-13 to BE-16) |
| `store/` adapters | placeholder rewrite (BE-17), normalisation (BE-20 to BE-22), read-only enforcement (BE-09, BE-10) |
| `store/parity.py` | every tool and every query file covered, including district and stored unit geometry (BE-26 to BE-29) |
| `store/loader.py` | rejects an unlisted table, a bad hash, a synthetic identifier in any column but `firm_list.firm_key` (a `SYN-E-` value in another column included), and in that column any value but a `SYN-E-` key or `withheld` (an `fk_` key and each other identifier kind included); loads the distinct released `SYN-E-` firm key (DAT-83); rebuilds DuckDB after a PostgreSQL skip; requires the two-store completion receipt; idempotent; interrupted load ineligible (BE-44 to BE-48, BE-103) |
| `infra/postgres/` | tests generated from the canonical application DDL; owner and extension checks; direct base-read refusal; fixed-function seat matrix and locked `search_path`; reviewer refusals (BE-31 to BE-41) |
| `tools/` | one contract test per status of each tool; snapping before reading, a drawn shape included (BE-54); only `synthetic_firms` returns firms, and no Synthetic or Simulated fact outside an `area` subject or, Synthetic only, a `synthetic_firm` subject (BE-59); public-only `make_area` reads no protected or simulated table and emits the snap report as technical metadata (BE-105); the housing split lists `family_housing`, `labour_accommodation`, `institution`, `unknown` and `other` only where pooled; occupation groups may include `other`; an unpublished occupation band returns `SUPPRESSED` with "not available at this area size"; every non-ratio figure names one home family, each ratio statistic uses two columns of the same stored rows and names both families, a count and its adjacent non-ratio shares come from the same family, and no output presents two routes to one population side by side (BE-108) |
| journey tools | the travel-time subject is the area (BE-119); presence counts with ranges, apportioned only by `eii_core.calc`, and no count or density for a named place (BE-111); rank-stability facts beside every rank, no weighted score returned as a fact, weights from defaults or typed values only, public-only mode reads no Protected or Simulated table (BE-112); the firm list's four fields only, no join to an FDI project, a public place or another firm (BE-113); the FDI estimate caveat beside every capex and jobs figure, every digit-bearing FDI field returned as a Public fact in its unit of document 03 DAT-155 and none as a label, the `announced` date at the precision the page gives and never padded, no company lookup (BE-114); every change between months from `month_change`, none by subtracting monthly values, a carried-forward change returned as `SUPPRESSED`, and wage trends by sector only as national Public facts of the activity table, never for an area (BE-115); splits never joined, segmented, apportioned or combined with a protected figure (BE-110); every number from `eii_core.calc` with a resolving lineage and a parity case (BE-116) |
| `assistant/` playbooks and writer | determinism, build-time template scans, structured catalogue validation, template fallback (BE-60 to BE-64); `staffing_and_pay` calls `area_evidence` for its resident, worker and coverage blocks, and every playbook's calls agree with the table of section 7 and the playbook list of document 09; a bundle with sample-file facts is never memoised (BE-118) |
| `api/` | endpoint shapes, signed-cookie seat binding, presenter-token refusal, stream order and resumption (BE-65 to BE-69, BE-70, BE-89); no route or setting selects a parameter set (BE-103); the scene endpoint rejects an extra property, a malformed id and an unlisted id (BE-106); the brief is buffered until the accounting gate passes, a failed check sends the template writer's default answer, logs the failure and shows "Checked before display" (BE-107); the shape and case routes refuse every invalid input; the case route loads each closed sample-file key, refuses a file body in any encoding, a path, a URL, an extra property and an unknown key with nothing kept, and loads no committed file whose SHA-256 differs from its committed value; both routes return 404 to another seat and to oversight, keep nothing in the ledger, egress record, logs, memo or `app.brief`, and lose every entry at restart (BE-109, BE-117, BE-118) |
| `ledger/` | idempotent replay, append-only, paused state, demand minimum, exact payload bytes; a call blocked for a planted firm name and key writes one row holding only the proposed payload's hash, with the name and key in no column of it, in either ledger (BE-73 to BE-81) |
| `preflight`, presenter | store selection matrix, complete receipt, PostGIS version failure, no database start by `up`, no automatic switch (BE-87 to BE-90) |

## Open questions and assumptions

ASSUMPTIONS made in this document (each also marked where it appears):

1. `src` layout for the three packages.
2. Arabic normalisation steps for matching, pending native review.
3. Schema name `review` for reviewer views.
4. `EII_DATABASE_URL` carries the `eii_app` login; the loader connects as `eii_owner` with its password from libpq's standard password file, because no second connection variable is pinned.
5. Snap-report counts are Synthetic facts when a protected release is mounted; in public-only mode the snap report is technical metadata (BE-105).
6. Site-check area assignment (walk 5 for workers, presence, outlets; drive 10 for residents).
7. Distinct-organisation demonstration minimum of two for the demand view.
8. Brief saving unavailable in embedded mode.
9. SRID 4326 for reviewer geometry.
10. 2,000 ms statement timeout; 10 asks per minute per seat; performance targets marked ASSUMPTION; 50% regression threshold.
11. Model unavailability reported as a status, not an error.
12. The closed layer list of `GET /api/layers/{layer}`, extended for decision 0016, and the argument shapes of the `stage` directives (zoom levels, scenario-panel focus, the hour, day and month keys).
13. Question text stored in the ledger for the asking seat only.
14. The scene endpoint's refusal split: a malformed body or fixture id is `INVALID_ARGUMENT`, a well-formed id absent from the manifest is `NOT_FOUND` (BE-106); PRV-119 requires only rejection.
15. The names of the journey tools and the calls of every playbook bundle (sections 6.2 and 7) are fixed here, as document 09 asks; the playbook names are document 09's.
16. The tables added by decisions 0016 and 0017 carry the names of document 03 section 7.2. The agency's records are the release table `pub_investqa_record`, whose `incentive_parameter` rows hold the incentive parameters, read through the source `investqa_pages` (documents 03 and 04 agree).
17. The protected blocks default to the latest month of the window when no month is chosen.
18. When no release unit survives snapping, `make_area` still makes the area for its exact outline, and protected blocks return `NO_DATA` (section 6.2).
19. A drawn polygon enters only through `POST /api/areas/shapes` and reaches tools as a `shape_id`; the model never passes its coordinates (BE-117). Document 09 AI-23 also allows a vertex of the drawn shape as a numeric argument; this document passes none.
20. A case sample file is loaded only by the server, from a closed key that names a committed synthetic sample file of its case, and only when that file's SHA-256 equals its committed value; the case route accepts no file body, so no file comes from the browser and no real record can enter (BE-118; [10](10_FRONTEND.md) FE-120). Neither the file nor any value computed from it reaches the model, the memo, `app.brief`, the ledger beyond the call, or the egress record, because the egress record keeps exact payloads beyond the session (BE-118). The playbook-only tool `own_records` reads it; document 09 AI-116 keeps the file's rows from the model, and this document also keeps the values computed from them out of model requests.
21. Travel times start from the area's pin or, for a drawn shape, its representative point (`eii_core.shapes`).
22. The drawn-shape route and the case routes add no `app` table and no error code; they use `INVALID_ARGUMENT` and `NOT_FOUND`, and the case route uses `INTERNAL` for a committed sample file that fails its SHA-256 or column-schema check (BE-118).
23. Destinations of `travel_times` (the ports, the airport, the free zones and the land routes) are the `gazetteer` entries of kind `gateway` that document 03 defines.

OPEN items raised by decisions 0016 and 0017 that touch this document:

- OPEN: the apportioning weight for drawn shapes (area, or a licensed public population grid) is fixed in document 07 and confirmed at slice S2; the vertex and size limits of a drawn shape are fixed at the same gate (BE-117).
- OPEN: the closed criterion list of `area_ranking` is fixed at slice S2 (document 07, method card C11). Document 07 now fixes how a `situation`'s hours combine for a drive area (C25), the candidate kinds of `area_ranking` (C11), the criteria of `activity_fit` (C16), the area types of `similar_areas` (C17), the access scores and times of `reachable_access` (C12) and the projection method (C21).
- OPEN: the public source of tenders is confirmed at slice S2; until then `investment_context` has no `tenders` topic and no tender is shown.
- OPEN: the page structure of the FDI dashboard and of the agency's pages, and whether a project's location is a point or a city, are confirmed at slice S2 against a synthetic test page of the same shape.
- OPEN: performance targets for drawn areas, hourly layers, the 24-hour animation, rankings and the case files are set when the slices that build them are planned (section 13).

Open items from the master design that touch this document: OI-01 (API key supplied for go-live and not used during the build; template writer throughout the build), OI-04 (closed for version 1 by decision 0017 item 10: the census map layers fill `pub_census_zone` and `pub_census_district` in the local release; the coverage-bar geography fallback stays), OI-07 (firm lists: decision 0016 now allows the named synthetic firm list of BE-113; the complete synthetic-identifier scan keeps its full strength in every column but `firm_list.firm_key`, which accepts only the released `SYN-E-` key or `withheld` (loader step 3, DAT-83), and the run-time tripwire of PRV-103 exempts nothing), OI-08 (ledger row label and distinct-organisation minimum), OI-09 (Arabic review of templates and normalisation), OI-10 (where PostgreSQL runs on the build machine), OI-11 (privacy thresholds are proposals), OI-35 (which parameter set is exported; default A).

## Sources

Every timing and size in this document that is attributed to the design research of 2026-11-11 was measured once at design time, on third-party software with throwaway synthetic tables or public inputs, before any product code existed; none is a test result of this product, and each is measured again at the slice that builds the part concerned ([README.md](README.md), "Identifiers and change control", item 8).

- [Decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) and [decision 0017](decisions/0017-public-data-additions-and-public-splits.md), the owner's decisions of 2026-11-12 (amendments 3 and 4 to the first pack).
- Qatar Open Data Portal, Explore API v2.1, https://www.data.gov.qa/api/explore/v2.1/ (CC BY 4.0), and the FDI projects dashboard, https://fdiprojects.invest.qa/ , both read 2026-11-12 as recorded in decision 0017; every public source's registry entry is in [04 Public data pack](04_PUBLIC_DATA_PACK.md).
- EII design research, architecture options report, measurements on the build machine, 2026-11-11 (PostgreSQL start, memory, load and query timings; row-level security, notification and read-only role tests; DuckDB `ANY(list)` form; geometry transfer).
- EII design research, feasibility and cost judgement, 2026-11-11 (no automatic failover; PostGIS 3.6; routing timings from the methods report).
- PostgreSQL Global Development Group, PostgreSQL 18 documentation: Row Security Policies, https://www.postgresql.org/docs/18/ddl-rowsecurity.html; NOTIFY, https://www.postgresql.org/docs/18/sql-notify.html; System Administration Functions, https://www.postgresql.org/docs/18/functions-admin.html; Sorting Rows, https://www.postgresql.org/docs/18/queries-order.html; Mathematical Functions and Operators, https://www.postgresql.org/docs/18/functions-math.html; retrieved 2026-11-11.
- DuckDB Foundation, DuckDB 2.0 documentation: Python DB API, https://duckdb.org/docs/2.0/clients/python/dbapi.html; Configuration, https://duckdb.org/docs/2.0/configuration/overview.html; Numeric functions, https://duckdb.org/docs/2.0/sql/functions/numeric.html; ORDER BY, https://duckdb.org/docs/2.0/sql/query_syntax/orderby.html; retrieved 2026-11-11.
- Psycopg 3 documentation, Adapting basic Python types, https://www.psycopg.org/psycopg3/docs/basic/adapt.html, retrieved 2026-11-11.
- FastAPI documentation, Server-Sent Events, https://fastapi.tiangolo.com/tutorial/server-sent-events/, retrieved 2026-11-11.
- Python Software Foundation, `uuid` module documentation for Python 3.14, https://docs.python.org/3.14/library/uuid.html, retrieved 2026-11-11.
- Valhalla project, Isochrone API, https://valhalla.github.io/valhalla/api/isochrone/, as cited in the EII tech-stack research of 2026-11-11.
