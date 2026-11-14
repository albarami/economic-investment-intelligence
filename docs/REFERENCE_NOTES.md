# Reference notes: engines and the Claude API

| | |
|---|---|
| Status | Draft written by task S0-T13 on 2026-11-12; every row is as true as the page or run it names, on the date it names |
| Date | 2026-11-12 |
| Owner | Project owner (see OPEN_ITEMS.md) |
| Purpose | Record the official pages read and the idioms that changed from earlier versions for DuckDB 2.0, PostgreSQL 18 and the current Claude API, the libraries and services that the pack calls newer than most model training data. |
| Read first | [02_ARCHITECTURE.md](02_ARCHITECTURE.md) section 7, [the notes for the map libraries](../web/REFERENCE_NOTES.md) |

## How to read these notes

Every statement in a table has one kind. READ: an official page, read on the date given, whose quoted words support the statement and nothing more. OBSERVED: a command run on the date given with the package and version named; the command and its output are in the Runs table of the section. PACK: the pack says it, the pack anchor is given, and it could be neither read nor observed here, so the statement says "not verified". A page can change after its date: quoted words are searched for again when the notes are checked.

The PostgreSQL pin, image-digest and volume-path confirmation fields await a recorded measurement stating each fact. S0-T08 records a run against PostgreSQL 18.6 and PostGIS 3.6.4, and S1-T05 records the live Compose service, but the confirmation-value grammar currently accepts only a slice S1 task-log heading; the ledger does not state the image digest or volume path. The three are in use since task S0-T08, and the rows `postgresql`, `postgis` and `postgis-image` of `pins.toml` hold their rulings; the fields close with the record of the slice S1 gate, which takes the lead's reading of the running service (the PostgreSQL and PostGIS versions, the image digest and the volume path).

The last section of each file lists the statements of the pack about these libraries and where each stands: a row of these notes, or "not covered" with the reason. The notes name a series, not a pin. Exact pins and retreat pins are the rows of `pins.toml`, which a check compares with the manifests; the table at the end of each section lists what slice S1 still has to confirm, with unmeasured fields marked "not yet confirmed". The task appended to each non-native field's Pack source owns confirmation when the product first uses that behaviour; a retreat-dependent field is checked only if that retreat is selected. The DuckDB field "files written by 2.0 when the retreat series is chosen" is confirmed only if the duckdb retreat is taken, by the task that takes it. The existing validator permits no separate assigned-task value, so the task is recorded in that field's source instead of inventing a measured confirmation. A value beginning "confirmed: " records only the measurement named in its PROGRESS.md task-log heading; it does not confirm untested retreats or broader capabilities. No PostgreSQL server was started and no request was sent to the Claude API for these notes (no key, no account), so every PostgreSQL and Claude API row is READ or PACK. The notes make no claim that a library works in this project: the original READ and OBSERVED rows describe the S0-T13 date; the S1 confirmation fields now cite later project measurements. `scripts/check_reference_notes.py` checks the form of these notes (sections, kinds, sources, allowed addresses, dates, the confirmation tables and the coverage table), that each anchor exists in the cited file and not what the anchored text says, and nothing about whether a quotation is still on its page.

## DuckDB 2.0

Used here as the build engine for the public pack, the synthetic world and the release (docs/decisions/0004-duckdb-build-engine-and-embedded-standby.md section "Decision" item 1) and as the embedded reader (docs/02_ARCHITECTURE.md section "Technology stack" row "Build engine and embedded reader"). Series 2.0, retreat series 1.5; the pins.toml row is `duckdb`.

### Pages read

| Id | Address | Page title | Date read |
|---|---|---|---|
| P1 | https://duckdb.org/2026/10/21/announcing-duckdb-200 | Announcing DuckDB 2.0.0 LTS "Cinnamon Teal" - DuckDB | 2026-11-12 |
| P2 | https://duckdb.org/docs/2.0/operations_manual/migration | Migrating to DuckDB 2.0 - DuckDB | 2026-11-12 |
| P3 | https://duckdb.org/docs/2.0/connect/concurrency | Concurrency - DuckDB | 2026-11-12 |
| P4 | https://duckdb.org/docs/2.0/extensions/installing_extensions | Installing Extensions - DuckDB | 2026-11-12 |
| P5 | https://duckdb.org/docs/2.0/core_extensions/postgres/overview | PostgreSQL Extension - DuckDB | 2026-11-12 |
| P6 | https://duckdb.org/docs/2.0/core_extensions/postgres/functions | PostgreSQL Extension Functions - DuckDB | 2026-11-12 |
| P7 | https://duckdb.org/docs/2.0/clients/python/dbapi | Python DB API - DuckDB | 2026-11-12 |
| P8 | https://duckdb.org/docs/2.0/clients/python/relational_api | Relational API - DuckDB | 2026-11-12 |
| P9 | https://duckdb.org/docs/2.0/configuration/overview | Configuration - DuckDB | 2026-11-12 |
| P10 | https://duckdb.org/docs/2.0/sql/functions/numeric | Numeric Functions - DuckDB | 2026-11-12 |
| P11 | https://duckdb.org/docs/2.0/sql/query_syntax/orderby | ORDER BY Clause - DuckDB | 2026-11-12 |
| P12 | https://duckdb.org/docs/2.0/core_extensions/spatial/overview | Spatial Extension - DuckDB | 2026-11-12 |

### Runs

Setup, in an empty folder: `uv venv --python 3.14 venv`, then `uv pip install --python venv/bin/python "duckdb==2.0.0"`. Run R7 first; R8 and R9 use the file it creates. A run's output is the last line printed (the standard error stream included); for a run that ends in an error, the output cell holds the start of that line.

| Id | Package and version | Date | Command | Output |
|---|---|---|---|---|
| R1 | duckdb 2.0.0 | 2026-11-12 | `venv/bin/python -I -c "import duckdb; r=duckdb.sql('select 1'); print(hasattr(r,'fetchone'), hasattr(r,'fetchmany'), r.limit(1).fetchall())"` | False False [(1,)] |
| R2 | duckdb 2.0.0 | 2026-11-12 | `venv/bin/python -I -c "import duckdb; duckdb.sql('select 1').fetchone()"` | AttributeError: Relations no longer have fetchone() |
| R3 | duckdb 2.0.0 | 2026-11-12 | `venv/bin/python -I -c "import duckdb; print(duckdb.sql('select 5/2, 5//2').fetchall())"` | [(2.5, 2)] |
| R4 | duckdb 2.0.0 | 2026-11-12 | `venv/bin/python -I -c "import duckdb; print(duckdb.sql('select x from (values (1),(NULL),(3)) t(x) order by x desc').fetchall())"` | [(3,), (1,), (None,)] |
| R5 | duckdb 2.0.0 | 2026-11-12 | `venv/bin/python -I -c "import duckdb; print(duckdb.execute('select 3 = ANY([1,2,3]), \$a + 1', {'a': 4}).fetchall())"` | [(True, 5)] |
| R6 | duckdb 2.0.0 | 2026-11-12 | `venv/bin/python -I -c "import duckdb; print(duckdb.sql('select list_transform([1,2,3], lambda x: x+1)').fetchall())"` | [([2, 3, 4],)] |
| R7 | duckdb 2.0.0 | 2026-11-12 | `venv/bin/python -I -c "import duckdb; d=duckdb.connect('t.duckdb'); d.execute('create or replace table t as select 1 i'); d.close(); c=duckdb.connect('t.duckdb', read_only=True); c.execute('insert into t values (2)')"` | _duckdb.InvalidInputException: Invalid Input Error: Cannot execute statement of type "INSERT" |
| R8 | duckdb 2.0.0 | 2026-11-12 | `venv/bin/python -I -c "import duckdb; c=duckdb.connect('t.duckdb', read_only=True); duckdb.connect('t.duckdb', read_only=False)"` | _duckdb.ConnectionException: Connection Error: Can't open a connection to same database file |
| R9 | duckdb 2.0.0 | 2026-11-12 | `venv/bin/python -I -c "import duckdb; c=duckdb.connect('t.duckdb', read_only=True); c.execute('set enable_external_access=false'); c.execute('set lock_configuration=true'); c.execute('set enable_external_access=true')"` | _duckdb.InvalidInputException: Invalid Input Error: Cannot change configuration option |

### Idioms that changed

| Id | Earlier form | Current form | Kind | Source | Quote |
|---|---|---|---|---|---|
| I1 | `rel.fetchone()` and `rel.fetchmany(n)` on a relation | `rel.limit(1).fetchall()`, `rel.limit(n).fetchall()` or `iter_rows()` | READ | P8 | "To read the first rows into Python, as fetchone() and fetchmany() did on a relation before DuckDB 2.0, use rel.limit(1).fetchall() and rel.limit(n).fetchall()." |
| I2 | the single-arrow lambda `x -> x + 1` | the Python-style lambda `lambda x : x + 1` | READ | P2 | "The old single arrow syntax (x -> x + 1) is now disabled by default in favor of the Python-style syntax (lambda x : x + 1)." |
| I3 | the function `postgres_attach` | the `ATTACH` statement | READ | P5 | "The old postgres_attach function was removed in DuckDB 2.0. Use the ATTACH statement instead." |
| I4 | the setting `extension_directory` (singular) | the setting `extension_directories` (plural, a list) | READ | P4 | "The extension_directory setting (singular) is deprecated in DuckDB 2.0 and emits a warning when set." |

### Statements

| Id | Statement | Kind | Source | Quote |
|---|---|---|---|---|
| S1 | DuckDB 2.0 is a long-term support release with support until at least October 2027. | READ | P1 | "DuckDB 2.0 is a long-term support (LTS) release with support until at least October 2027." |
| S2 | Support for DuckDB 1.5 was extended until March 2027. | READ | P1 | "we extended the support period of DuckDB 1.5 until March 2027" |
| S3 | The announcement advises waiting for the first patch release when a workload is mission-critical, and says that release is coming in November. | READ | P1 | "you may want to wait for the first patch release, coming in November" |
| S4 | Versions before 2.0.0 cannot read database files that use the 2.0.0 storage format. | READ | P2 | "DuckDB versions before 2.0.0 cannot read database files that use the DuckDB 2.0.0 storage format." |
| S5 | In read-only mode several processes can read one database file and none can write. | READ | P3 | "multiple processes can read from the database, but no processes can write" |
| S6 | An installed extension is copied to a local directory and cached, to avoid later network traffic. | READ | P4 | "it is copied to a local directory to be cached and avoid future network traffic" |
| S7 | The relation object of duckdb 2.0.0 has no fetchone or fetchmany, and limit(1).fetchall() returns the first row. | OBSERVED | R1 | - |
| S8 | Calling fetchone on a relation of duckdb 2.0.0 raises an AttributeError that names limit(1).fetchall() as the replacement. | OBSERVED | R2 | - |
| S9 | Within one Python process, all connections to a database file must use the same configuration, read_only included. | READ | P7 | "all connections to a database file must use the same configuration, read_only included" |
| S10 | In duckdb 2.0.0, an insert through a read-only connection is refused. | OBSERVED | R7 | - |
| S11 | In duckdb 2.0.0, opening a second connection to the same file with a different read_only setting is refused while the first is open. | OBSERVED | R8 | - |
| S12 | The setting lock_configuration decides whether configuration options can be altered. | READ | P9 | "Whether configurations can be altered." |
| S13 | In duckdb 2.0.0, after lock_configuration is set to true, setting enable_external_access again is refused. | OBSERVED | R9 | - |
| S14 | Each thread should be given its own cursor. | READ | P7 | "give each thread its own cursor" |
| S15 | The operator / divides integers as floating point and // divides as integers. | READ | P10 | "When both operands are integers, / performs floating points division (5 / 2 = 2.5) while // performs integer division (5 // 2 = 2)." |
| S16 | In duckdb 2.0.0, select 5/2, 5//2 returns 2.5 and 2. | OBSERVED | R3 | - |
| S17 | DuckDB sorts NULL values last even for descending order; PostgreSQL sorts them first. | READ | P11 | "DuckDB keeps NULLS LAST even for DESC ordering, whereas PostgreSQL places NULLs first on DESC" |
| S18 | In duckdb 2.0.0, a descending sort over 1, NULL and 3 returns 3, 1 and NULL. | OBSERVED | R4 | - |
| S19 | Text is sorted by binary comparison of its UTF-8 values unless a collation is set. | READ | P11 | "Text is sorted using the binary comparison collation by default" |
| S20 | In duckdb 2.0.0, the form `= ANY(list)` and a named parameter written with a dollar sign and given as a dictionary are accepted. | OBSERVED | R5 | - |
| S21 | In duckdb 2.0.0, the Python-style lambda is accepted. | OBSERVED | R6 | - |
| S22 | Any error inside an explicit transaction aborts the transaction in DuckDB 2.0.0. | READ | P2 | "any error inside an explicit transaction aborts the transaction" |
| S23 | The function postgres_execute sends its query to PostgreSQL with no transformation or analysis by DuckDB. | READ | P6 | "no transformation or analysis of this query is performed by DuckDB" |
| S24 | The pack says postgres_execute takes one statement per call (docs/02_ARCHITECTURE.md section "Technology stack" row "Build engine and embedded reader"); the function page names one query argument and does not state a limit on statements, and no PostgreSQL server was available: not verified. | PACK | docs/02_ARCHITECTURE.md section "Technology stack" row "Build engine and embedded reader" | - |
| S25 | The pack says DuckDB 2.x needs SET geometry_always_xy=true for the Overture extract (docs/04_PUBLIC_DATA_PACK.md PUB-17); the spatial extension overview page (P12) does not mention the setting: not verified. | PACK | docs/04_PUBLIC_DATA_PACK.md PUB-17 | - |
| S26 | The pack records that a DuckDB GEOMETRY column arrives as a PostGIS geometry column through the PostgreSQL extension with no conversion (docs/decisions/0004-duckdb-build-engine-and-embedded-standby.md section "Evidence"); that was measured by the architecture research and not repeated here: not verified. | PACK | docs/decisions/0004-duckdb-build-engine-and-embedded-standby.md section "Evidence" | - |
| S27 | The pack lists byte-order sorting of text as an assumption to be confirmed with the parity query of slice S1 (docs/02_ARCHITECTURE.md section "The portable SQL subset (minimum rules)"); the page read (S19) names the default for DuckDB only, and no parity query has been run: not verified. | PACK | docs/02_ARCHITECTURE.md section "The portable SQL subset (minimum rules)" | - |

### Slice S1 confirmation

| Field | Value | Rows in pins.toml | Pack source |
|---|---|---|---|
| exact pin, or the retreat series chosen instead | confirmed: DuckDB 2.0.0 returned the parity result; 1.5.x retreat not tried; PROGRESS.md heading "S1-T05 — First two-store parity query: task log" | duckdb | docs/decisions/0004-duckdb-build-engine-and-embedded-standby.md section "Decision" item 3 |
| path of the project-local extension directory | confirmed: data/engine_extensions/ verified and loaded offline inside the sandbox; PROGRESS.md heading "S1-T06 — Sandbox enforcement spike: task log" | - | docs/02_ARCHITECTURE.md section "Open questions and assumptions" item 2 |
| need for geometry_always_xy | not yet confirmed | - | docs/03_DATA_CONTRACTS.md section "Logical types"; docs/04_PUBLIC_DATA_PACK.md PUB-17; TASKS.md S2-T01 |
| text ordering by byte value, by the parity query | confirmed: DuckDB 2.0.0 and PostgreSQL 18.6 returned identical byte-sorted text including accents, Arabic, ties and NULL last; PROGRESS.md heading "S1-T05 — First two-store parity query: task log" | - | docs/02_ARCHITECTURE.md section "The portable SQL subset (minimum rules)" |
| threading guidance of the 2.0 Python interface | not yet confirmed | - | docs/08_BACKEND.md BE-12; TASKS.md S3-T01 |
| copy mechanism from DuckDB to PostgreSQL | not yet confirmed | - | docs/08_BACKEND.md section "The loader (`./eii load-release`)"; TASKS.md S3-T02 |
| files written by 2.0 when the retreat series is chosen | not yet confirmed | duckdb | docs/decisions/0004-duckdb-build-engine-and-embedded-standby.md section "Evidence" |

## PostgreSQL 18

Used here as the serving store, with PostGIS and no other extension (docs/02_ARCHITECTURE.md section "Technology stack" row "Serving store"). Series 18; the pins.toml rows are `postgresql`, `postgis` and `postgis-image`.

### Pages read

| Id | Address | Page title | Date read |
|---|---|---|---|
| P1 | https://www.postgresql.org/support/versioning/ | PostgreSQL: Versioning Policy | 2026-11-12 |
| P2 | https://www.postgresql.org/docs/18/release-18.html | PostgreSQL: Documentation: 18: E.6. Release 18 | 2026-11-12 |
| P3 | https://www.postgresql.org/docs/18/ddl-rowsecurity.html | PostgreSQL: Documentation: 18: 5.9. Row Security Policies | 2026-11-12 |
| P4 | https://www.postgresql.org/docs/18/sql-notify.html | PostgreSQL: Documentation: 18: NOTIFY | 2026-11-12 |
| P5 | https://www.postgresql.org/docs/18/functions-math.html | PostgreSQL: Documentation: 18: 9.3. Mathematical Functions and Operators | 2026-11-12 |
| P6 | https://www.postgresql.org/docs/18/functions-admin.html | PostgreSQL: Documentation: 18: 9.28. System Administration Functions | 2026-11-12 |
| P7 | https://www.postgresql.org/docs/18/queries-order.html | PostgreSQL: Documentation: 18: 7.5. Sorting Rows (ORDER BY) | 2026-11-12 |
| P8 | https://www.postgresql.org/docs/18/app-pgrestore.html | PostgreSQL: Documentation: 18: pg_restore | 2026-11-12 |
| P9 | https://hub.docker.com/_/postgres | postgres - Official Image - Docker Hub | 2026-11-12 |

### Idioms that changed

| Id | Earlier form | Current form | Kind | Source | Quote |
|---|---|---|---|---|---|
| I1 | a data volume mounted at `/var/lib/postgresql/data` (version 17 and below) | a volume mounted at `/var/lib/postgresql` (version 18 and above, official image) | READ | P9 | "The defined VOLUME was changed in 18 and above to /var/lib/postgresql." |
| I2 | `initdb` creates a cluster without data checksums | `initdb` enables data checksums by default | READ | P2 | "Change initdb default to enable data checksums" |

### Statements

| Id | Statement | Kind | Source | Quote |
|---|---|---|---|---|
| S1 | The versioning page lists version 18 with its first release on 2025-09-25. | READ | P1 | "September 25, 2025" |
| S2 | Version 18 adds the OAuth authentication method. | READ | P2 | "Add support for the OAuth authentication method" |
| S3 | Table owners normally bypass row security, and an owner can choose to be subject to it with FORCE ROW LEVEL SECURITY. | READ | P3 | "Table owners normally bypass row security as well, though a table owner can choose to be subject to row security with ALTER TABLE ... FORCE ROW LEVEL SECURITY" |
| S4 | Superusers and roles with the BYPASSRLS attribute always bypass row security. | READ | P3 | "Superusers and roles with the BYPASSRLS attribute always bypass the row security system" |
| S5 | Setting row_security to off does not bypass row security; it throws an error if a query's results would be filtered by a policy. | READ | P3 | "what it does is throw an error if any query's results would get filtered by a policy" |
| S6 | With is_local true, set_config applies its new value only during the current transaction. | READ | P6 | "If is_local is true, the new value will only apply during the current transaction." |
| S7 | Division of integral types truncates the result towards zero. | READ | P5 | "division truncates the result towards zero" |
| S8 | NULLS FIRST is the default for DESC order. | READ | P7 | "NULLS FIRST is the default for DESC order" |
| S9 | A NOTIFY executed in a transaction is not delivered unless the transaction is committed. | READ | P4 | "the notify events are not delivered until and unless the transaction is committed" |
| S10 | In the default configuration a notification payload must be shorter than 8000 bytes. | READ | P4 | "In the default configuration it must be shorter than 8000 bytes." |
| S11 | Multiple jobs of pg_restore cannot be used together with the option --single-transaction. | READ | P8 | "multiple jobs cannot be used together with the option --single-transaction" |
| S12 | The pack applies the volume layout of the official postgres image to the postgis/postgis image (docs/13_DEPLOYMENT_AND_OPERATIONS.md section "Compose service definition (in words)" item 4); the page read is the page of the official image, not of the PostGIS image: not verified. | PACK | docs/13_DEPLOYMENT_AND_OPERATIONS.md section "Compose service definition (in words)" item 4 | - |
| S13 | The pack says the PostGIS image defines no health check and that the first-boot server listens on the socket only (docs/12_TESTING_AND_QUALITY.md TST-152; docs/13_DEPLOYMENT_AND_OPERATIONS.md section "Compose service definition (in words)" item 5); neither was looked for here: not verified. | PACK | docs/12_TESTING_AND_QUALITY.md TST-152 | - |
| S14 | The pack says the database may carry only PostGIS and the built-in procedural language, and that text columns use the C collation (docs/08_BACKEND.md BE-32; docs/13_DEPLOYMENT_AND_OPERATIONS.md OPS-12; docs/02_ARCHITECTURE.md section "The portable SQL subset (minimum rules)"); neither was looked for here: not verified. | PACK | docs/08_BACKEND.md BE-32; docs/13_DEPLOYMENT_AND_OPERATIONS.md OPS-12; docs/02_ARCHITECTURE.md section "The portable SQL subset (minimum rules)" | - |

### Slice S1 confirmation

| Field | Value | Rows in pins.toml | Pack source |
|---|---|---|---|
| exact pin of PostgreSQL 18 and the PostGIS 3.6 line | not yet confirmed | postgresql, postgis | docs/02_ARCHITECTURE.md section "Technology stack" row "Serving store" |
| image digest of the PostGIS image | not yet confirmed | postgis-image | docs/13_DEPLOYMENT_AND_OPERATIONS.md section "Compose service definition (in words)" item 1 |
| data directory and volume path of that image | not yet confirmed | postgis-image | docs/13_DEPLOYMENT_AND_OPERATIONS.md section "Compose service definition (in words)" item 4 |
| first parity query on both stores | confirmed: DuckDB 2.0.0 and PostgreSQL 18.6 returned the same parity query result; PROGRESS.md heading "S1-T05 — First two-store parity query: task log" | - | TASKS.md S1-T05 |

## Claude API

Used here behind one provider adapter for the router and the writer, with the template writer as the retreat (docs/09_AI_ASSISTANT.md section "In brief"; docs/09_AI_ASSISTANT.md section "Model settings" row "Model"). The model string and the Python SDK are the pins.toml rows `claude-model` and `anthropic`. The pack says its statements about the API were checked against a reference bundled with a coding tool and not against an official page (docs/09_AI_ASSISTANT.md section "Model settings"); every row below is a page read on the date given, or a pack statement marked "not verified". Page titles are the `title` of the front matter of each page's Markdown form (the page address plus `.md`).

### Pages read

| Id | Address | Page title | Date read |
|---|---|---|---|
| P1 | https://platform.claude.com/docs/en/models/opus-5-5/migration-guide | Claude Opus 5.5 migration guide | 2026-11-12 |
| P2 | https://platform.claude.com/docs/en/api/errors | Claude API errors | 2026-11-12 |
| P3 | https://platform.claude.com/docs/en/build-with-claude/structured-outputs | Structured outputs | 2026-11-12 |
| P4 | https://platform.claude.com/docs/en/agents-and-tools/tool-use/fine-grained-tool-streaming | Fine-grained tool streaming | 2026-11-12 |
| P5 | https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons | Stop reasons and fallback | 2026-11-12 |
| P6 | https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback | Refusals and fallback | 2026-11-12 |
| P7 | https://platform.claude.com/docs/en/build-with-claude/prompt-caching | Prompt caching | 2026-11-12 |
| P8 | https://platform.claude.com/docs/en/build-with-claude/thinking-steering-and-cost | Steering thinking | 2026-11-12 |
| P9 | https://platform.claude.com/docs/en/build-with-claude/preserved-thinking | Preserved thinking | 2026-11-12 |
| P10 | https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages | Mid-conversation system messages and tool changes | 2026-11-12 |
| P11 | https://platform.claude.com/docs/en/manage-claude/data-residency | Data residency | 2026-11-12 |
| P12 | https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/python | Python SDK | 2026-11-12 |
| P13 | https://platform.claude.com/docs/en/api/migration-2026-10-21 | Migrating to API version 2026-10-21 | 2026-11-12 |
| P14 | https://platform.claude.com/docs/en/build-with-claude/fast-mode | Fast mode | 2026-11-12 |
| P15 | https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls | Handle tool calls | 2026-11-12 |
| P16 | https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use | Parallel tool use | 2026-11-12 |

### Idioms that changed

| Id | Earlier form | Current form | Kind | Source | Quote |
|---|---|---|---|---|---|
| I1 | a manual thinking budget, `thinking: {type: "enabled", budget_tokens: N}`, or thinking disabled | no thinking field, or an adaptive thinking setting; the other two are rejected on this model | READ | P1 | "both return a 400 error" |
| I2 | the sampling parameters `temperature`, `top_p` and `top_k` | omit them | READ | P1 | "Omit temperature, top_p, and top_k." |
| I3 | forcing a tool call with a tool choice of type `any` or `tool` | a tool choice of type `auto`, with strict tool use or structured outputs | READ | P1 | "Replace tool_choice types any and tool with auto plus strict tool use or structured outputs" |
| I4 | a prefilled final assistant turn | structured outputs or system prompt instructions | READ | P1 | "Don't end messages with a prefilled assistant turn: it is rejected." |
| I5 | the SDK and the CLI send the API key in the `X-Api-Key` header | the SDK and the CLI send the key as `Authorization: Bearer`; the API accepts a key in either header | READ | P13 | "The SDK and the CLI send your API key as Authorization: Bearer <key> instead of in the X-Api-Key header ... The Claude API accepts a key in either header" |

### Statements

| Id | Statement | Kind | Source | Quote |
|---|---|---|---|---|
| S1 | The model identifier is a fixed string with no date suffix. | READ | P1 | "Use claude-opus-5-5, a fixed model ID with no date suffix." |
| S2 | The default effort is medium. | READ | P1 | "and the default is medium" |
| S3 | Thinking counts toward max_tokens, so max_tokens must leave room for both the reasoning and the answer. | READ | P8 | "Because thinking counts toward max_tokens, set it high enough to leave room for both the reasoning and the answer." |
| S4 | Thinking blocks arrive with an empty thinking field alongside their signature by default. | READ | P1 | "so thinking blocks arrive with an empty thinking field alongside their signature" |
| S5 | A structured-output schema cannot use numerical constraints such as minimum, maximum or multipleOf. | READ | P3 | "Numerical constraints (such as minimum, maximum, multipleOf)" |
| S6 | A schema that exceeds the complexity limits gets a 400 error with a message about compilation. | READ | P3 | "Schema is too complex for compilation" |
| S7 | A structured output can contain an enum value in a different case from the one in the schema, with no error. | READ | P3 | "even though that exact value isn't in the enum" |
| S8 | When the stop reason is max_tokens, a structured output can be incomplete and not match the schema. | READ | P3 | "The output might be incomplete and not match your schema" |
| S9 | Enabling citations together with output_config.format returns a 400 error. | READ | P3 | "The API returns a 400 error if citations are enabled with output_config.format" |
| S10 | With eager input streaming the API does not buffer or validate a tool's input before streaming it, so the input can arrive partial or invalid. | READ | P4 | "you might receive partial or invalid JSON" |
| S11 | A refusal arrives as a normal HTTP 200 response, not an error. | READ | P5 | "Safety classifiers return this stop reason as a normal HTTP 200 response, not an error." |
| S12 | The stop reason model_context_window_exceeded exists; the response is truncated. | READ | P5 | "Treat the response as truncated" |
| S13 | A refusal can arrive before any output or in the middle of a stream; partial output is incomplete and is discarded. | READ | P6 | "treat any partial output as incomplete and discard it" |
| S14 | Automatic caching uses a five-minute lifetime by default. | READ | P7 | "By default, automatic caching uses a 5-minute TTL." |
| S15 | Changing the effort setting always invalidates message blocks in the cache. | READ | P7 | "value always invalidates message blocks, with the same model-specific effect on tool and system caches as thinking parameters" |
| S16 | The minimum cacheable prompt length is 512 tokens for a group of models that includes Claude Opus 5.5. | READ | P7 | "the minimum cacheable prompt length is: 512 tokens for ... Claude Opus 5.5" |
| S17 | The history must be append-only: the system prompt and tools stay the same and only the end of messages changes. | READ | P9 | "Make your integration append-only" |
| S18 | A mid-conversation system message must immediately follow a user turn. | READ | P10 | "must immediately follow a user turn" |
| S19 | The value global of inference_geo lets inference run in any available geography. | READ | P11 | "Inference may run in any available geography" |
| S20 | United States only inference is priced at 1.1 times the standard rate. | READ | P11 | "is priced at 1.1x the standard rate" |
| S21 | By default the SDK retries certain errors twice: connection errors and the statuses 408, 409, 429 and 500 or above. | READ | P12 | "By default, the SDK retries certain errors twice ... It retries connection errors ... 408 Request Timeout, 409 Conflict, 429 Rate Limit, and >=500 Internal errors" |
| S22 | A client from the separate httpx package, given to the SDK, raises a TypeError. | READ | P12 | "Passing a client from the separate httpx package raises a TypeError" |
| S23 | The pack says a zero-output pre-warm is rejected together with streaming or structured output (docs/09_AI_ASSISTANT.md AI-57); no page read says so: not verified. | PACK | docs/09_AI_ASSISTANT.md AI-57 | - |
| S24 | The pack calls eager input streaming the reference's recommended setting (docs/09_AI_ASSISTANT.md section "Model settings" row "Tool definitions"); no page read calls it recommended: not verified. | PACK | docs/09_AI_ASSISTANT.md section "Model settings" row "Tool definitions" | - |
| S25 | The pack says earlier turns must be byte-identical (docs/09_AI_ASSISTANT.md AI-48); the page read says the prefix is compared with what was sent: not verified as worded. | PACK | docs/09_AI_ASSISTANT.md AI-48 | - |
| S26 | The pack says the reference recommends server-side refusal fallbacks by default (docs/09_AI_ASSISTANT.md AI-60); the page read does not use that wording: not verified. | PACK | docs/09_AI_ASSISTANT.md AI-60 | - |
| S27 | The pack asks whether other inference geographies exist and whether either runs in Qatar (docs/09_AI_ASSISTANT.md section "Model settings" row "Inference geography"); the page read names no Qatar region and does not rule one out for global: not verified. | PACK | docs/09_AI_ASSISTANT.md section "Model settings" row "Inference geography" | - |
| S28 | Claude Opus 5.5 does not support forced tool use, and sending a forcing tool choice returns a 400 invalid_request_error. | READ | P2 | "Claude Opus 5.5 ... don't support forced tool use ... returns a 400 invalid_request_error" |
| S29 | The page on the speed setting prices it at a multiplier on standard rates and lists Claude Opus 5.5 at 8 USD for input and 40 USD for output per million tokens. | READ | P14 | "Fast mode is priced at a multiplier on standard rates ... Input ... Output ... Claude Opus 5.5 ... $8 USD / MTok ... $40 USD / MTok" |
| S30 | The pack calls the price of the speed setting twice the standard price (docs/09_AI_ASSISTANT.md section "Model settings" row "Fast mode"); the page read gives a multiplier and not that ratio in words: not verified as worded. | PACK | docs/09_AI_ASSISTANT.md section "Model settings" row "Fast mode" | - |
| S31 | A one-hour cache lifetime can be requested instead of the five-minute default. | READ | P7 | "By default, automatic caching uses a 5-minute TTL. You can specify a 1-hour TTL at 2x the base input token price" |
| S32 | A compiled structured-output schema is cached for 24 hours from last use. | READ | P3 | "Compiled grammars are cached for 24 hours from last use" |
| S33 | A tool result carries an optional is_error field, set to true when the tool execution failed. | READ | P15 | "Set to true if the tool execution resulted in an error" |
| S34 | The results of parallel tool calls go back together in a single user message. | READ | P16 | "all tool results together in a single user message" |

### Slice S1 confirmation

| Field | Value | Rows in pins.toml | Pack source |
|---|---|---|---|
| SDK pin and written retreat pin | not yet confirmed | anthropic | docs/09_AI_ASSISTANT.md section "Model settings"; TASKS.md S8-T02 |
| model string | not yet confirmed | claude-model | docs/09_AI_ASSISTANT.md section "Model settings" row "Model"; TASKS.md S8-T02 |
| thinking counts toward max_tokens | not yet confirmed | - | docs/09_AI_ASSISTANT.md section "Model settings" row "`max_tokens`"; TASKS.md S8-T02 |
| inference geographies | not yet confirmed | - | docs/09_AI_ASSISTANT.md section "Model settings" row "Inference geography"; TASKS.md S8-T02 |
| minimum cacheable prefix | not yet confirmed | - | docs/09_AI_ASSISTANT.md AI-58; TASKS.md S8-T02 |

## Pack statements and where each stands

| Pack claim | Pack source | Where |
|---|---|---|
| DuckDB 2.0.0 is a long-term support release supported until at least October 2027 | docs/decisions/0004-duckdb-build-engine-and-embedded-standby.md section "Evidence" | DuckDB 2.0 S1 |
| The announcement suggests waiting for a first patch release for mission-critical work | docs/decisions/0004-duckdb-build-engine-and-embedded-standby.md section "Evidence" | DuckDB 2.0 S3 |
| Files written by 2.0 cannot be read by earlier versions | docs/decisions/0004-duckdb-build-engine-and-embedded-standby.md section "Evidence" | DuckDB 2.0 S4 |
| One read-write process, or several read-only processes | docs/decisions/0004-duckdb-build-engine-and-embedded-standby.md section "Evidence" | DuckDB 2.0 S5 |
| An extension needs the network for its first install and is cached locally afterwards | docs/decisions/0004-duckdb-build-engine-and-embedded-standby.md section "Evidence" | DuckDB 2.0 S6 |
| Python relations no longer have fetchone() | docs/decisions/0004-duckdb-build-engine-and-embedded-standby.md section "Evidence" | DuckDB 2.0 S7; DuckDB 2.0 S8 |
| postgres_execute takes one statement per call | docs/decisions/0004-duckdb-build-engine-and-embedded-standby.md section "Evidence" | DuckDB 2.0 S24 |
| DuckDB 2.x needs SET geometry_always_xy=true for the Overture extract | docs/04_PUBLIC_DATA_PACK.md PUB-17 | DuckDB 2.0 S25 |
| The operator / is float division in DuckDB | docs/08_BACKEND.md section "The portable SQL subset" row "`/` and `%`" | DuckDB 2.0 S15; DuckDB 2.0 S16 |
| DuckDB keeps NULLS LAST for DESC | docs/08_BACKEND.md section "The portable SQL subset" row "`ORDER BY` without explicit `NULLS FIRST` or `NULLS LAST`" | DuckDB 2.0 S17; DuckDB 2.0 S18 |
| The embedded adapter opens read-only, then sets enable_external_access to false and lock_configuration to true | docs/08_BACKEND.md BE-10 | DuckDB 2.0 S10; DuckDB 2.0 S12; DuckDB 2.0 S13 |
| DuckDB accepts cell = ANY(list), and a dictionary of named parameters | docs/08_BACKEND.md section "The portable SQL subset"; docs/decisions/0004-duckdb-build-engine-and-embedded-standby.md section "Evidence" | DuckDB 2.0 S20 |
| A DuckDB GEOMETRY column arrives as a PostGIS geometry column with no conversion | docs/decisions/0004-duckdb-build-engine-and-embedded-standby.md section "Evidence" | DuckDB 2.0 S26 |
| DuckDB orders text by byte value by default (assumption) | docs/02_ARCHITECTURE.md section "The portable SQL subset (minimum rules)" | DuckDB 2.0 S19; DuckDB 2.0 S27 |
| The adapter uses one cursor per thread (assumption) | docs/08_BACKEND.md BE-12 | DuckDB 2.0 S14 |
| PostgreSQL set_config with is_local true limits the value to the current transaction | docs/08_BACKEND.md section "The protocol" | PostgreSQL 18 S6 |
| PostgreSQL integer division truncates towards zero | docs/08_BACKEND.md section "The portable SQL subset" row "`/` and `%`" | PostgreSQL 18 S7 |
| PostgreSQL defaults to NULLS FIRST for DESC | docs/08_BACKEND.md section "The portable SQL subset" row "`ORDER BY` without explicit `NULLS FIRST` or `NULLS LAST`" | PostgreSQL 18 S8 |
| Notifications are delivered only when the transaction commits and the payload is under 8,000 bytes | docs/08_BACKEND.md section "The ledger in PostgreSQL" | PostgreSQL 18 S9; PostgreSQL 18 S10 |
| Table owners bypass row-level security unless it is forced | docs/08_BACKEND.md BE-31 | PostgreSQL 18 S3 |
| With row_security set to off a query that would be filtered raises an error | docs/12_TESTING_AND_QUALITY.md TST-64 | PostgreSQL 18 S5 |
| The version 18 images declare /var/lib/postgresql as the volume | docs/13_DEPLOYMENT_AND_OPERATIONS.md section "Compose service definition (in words)" item 4 | PostgreSQL 18 I1; PostgreSQL 18 S12 |
| The PostGIS image has no health check and the first-boot server listens on the socket only | docs/12_TESTING_AND_QUALITY.md TST-152; docs/13_DEPLOYMENT_AND_OPERATIONS.md section "Compose service definition (in words)" item 5 | PostgreSQL 18 S13 |
| Parallel restore does not work with --single-transaction | docs/13_DEPLOYMENT_AND_OPERATIONS.md section "Logs, backups and restore" row "Release schema damaged or missing" | PostgreSQL 18 S11 |
| PostgreSQL 18 adds OAuth authentication and data checksums by default | docs/13_DEPLOYMENT_AND_OPERATIONS.md section "Deployment path (later)" | PostgreSQL 18 S2; PostgreSQL 18 I2 |
| The database carries only PostGIS and plpgsql, and text columns use the C collation | docs/08_BACKEND.md BE-32; docs/13_DEPLOYMENT_AND_OPERATIONS.md OPS-12; docs/02_ARCHITECTURE.md section "The portable SQL subset (minimum rules)" | PostgreSQL 18 S14 |
| Thinking is omitted or adaptive, and disabled or a token budget returns a 400 error | docs/09_AI_ASSISTANT.md section "Model settings" row "Thinking" | Claude API I1 |
| The thinking display default is omitted | docs/09_AI_ASSISTANT.md section "Model settings" row "Thinking display" | Claude API S4 |
| The default effort is medium | docs/09_AI_ASSISTANT.md section "Model settings" row "Effort" | Claude API S2 |
| temperature, top_p and top_k are rejected with a 400 error | docs/09_AI_ASSISTANT.md section "Model settings" row "Sampling" | Claude API I2 |
| Only the auto tool choice is allowed and forcing a tool returns a 400 error | docs/09_AI_ASSISTANT.md section "Model settings" row "Tool choice" | Claude API I3; Claude API S28 |
| Eager input streaming stops server validation, and the API buffers by default | docs/09_AI_ASSISTANT.md section "Model settings" row "Tool definitions" | Claude API S10; Claude API S24 |
| Tool definitions carry strict: true | docs/09_AI_ASSISTANT.md section "Model settings" row "Tool definitions" | not covered: the strict tool use page is not quoted in these notes |
| Structured-output schemas do not support numeric range constraints | docs/09_AI_ASSISTANT.md AI-25 | Claude API S5 |
| Structured output is schema-valid except on refusal or max_tokens and cannot be combined with citations or prefill | docs/09_AI_ASSISTANT.md section "Model settings" row "Structured output" | Claude API S8; Claude API S9; Claude API I4 |
| Thinking counts toward the max_tokens limit | docs/09_AI_ASSISTANT.md section "Model settings" row "`max_tokens`" | Claude API S3 |
| Five stop reasons exist and a refusal arrives as HTTP 200 | docs/09_AI_ASSISTANT.md section "Model settings" row "Stop reasons" | Claude API S11; Claude API S12 |
| Fast mode costs 8 and 40 USD per million tokens, twice the standard price | docs/09_AI_ASSISTANT.md section "Model settings" row "Fast mode" | Claude API S29; Claude API S30 |
| The inference geography is global by default and us costs 1.1 times the price | docs/09_AI_ASSISTANT.md section "Model settings" row "Inference geography" | Claude API S19; Claude API S20; Claude API S27 |
| A system message after the user turn is supported | docs/09_AI_ASSISTANT.md section "Model settings" row "Response language" | Claude API S18 |
| The SDK retries 408, 409, 429, 5xx and connection errors twice by default | docs/09_AI_ASSISTANT.md section "Model settings" row "Retries" | Claude API S21 |
| Preserved thinking checks that earlier turns are byte-identical | docs/09_AI_ASSISTANT.md AI-48 | Claude API S17; Claude API S25 |
| One explicit one-hour breakpoint and a five-minute automatic default | docs/09_AI_ASSISTANT.md AI-55 | Claude API S14; Claude API S31 |
| A zero-output pre-warm is rejected together with streaming or structured output | docs/09_AI_ASSISTANT.md AI-57 | Claude API S23 |
| The structured-output schema compilation is cached for 24 hours | docs/09_AI_ASSISTANT.md AI-57 | Claude API S32 |
| The minimum cacheable prefix is 512 tokens | docs/09_AI_ASSISTANT.md AI-58 | Claude API S16 |
| Changing the effort setting invalidates the cache | docs/09_AI_ASSISTANT.md section "Model settings" row "Repair" | Claude API S15 |
| Server-side refusal fallbacks are recommended by default | docs/09_AI_ASSISTANT.md AI-60 | Claude API S26 |
| A failed tool is returned as a result with is_error: true | docs/09_AI_ASSISTANT.md AI-61 | Claude API S33 |
| All parallel tool results are returned in one user message | docs/09_AI_ASSISTANT.md AI-61 | Claude API S34 |
