# product/ — serving plane `eii_product`

This folder will hold `eii_product`, the read-only serving plane: the store, the tools, the governed assistant, the ledger and the API.

## Rules

- `eii_product` never imports `eii_custodian` and never reaches `data/vault/` (ARC-06, BE-02, BE-05).
- `eii_product` never imports the typed-decision gateway and never reads its settings (BE-102).
- Only a verified release crosses from the custodian plane to this plane.

The store is `eii_product.store`. A tool calls `ReleaseStore.fetch` with a `QueryName` looked up from that store's inventory and bound parameters. `load_inventory` stays importable from `eii_product.store.registry` for tests and for start-up, not for a tool. `ToolResult` and `Fact` are placeholders until the task that defines the tool result. The packaged folder `src/eii_product/store/sql/` ships the `make_area` queries. The drivers `duckdb` and `psycopg` stay in the root group `engine` (open item OI-116). The product package declares `duckdb` and `psycopg` at the same pins as the root group `engine`. A store adapter still imports its driver only when that store opens. The public loader is `eii_product.store.loader`, with `eii_product.store.release_check` and `eii_product.store.receipt`. It reads Parquet through DuckDB, writes PostgreSQL with psycopg `COPY`, and writes `load_receipt.json` only after both stores verify. That receipt is not a manifest artefact. A later tool adds its `.sql` file, the adjacent `.toml` contract and a parity case; task S3-T03 registers tools.

Status: package skeleton plus the tile spike API under `eii_product.api` and its HTTP range tests (task S1-T04). It also holds a fixture-only [area spike](src/eii_product/areas_spike/README.md) (task S1-T03): walk and drive areas from pyvalhalla in process, on a synthetic road extract built by the spike's own generator, with one set of routing tiles for each distinct hourly speed factor; the engine's polygon is kept exactly beside whole frame cells. A real road network, the release graph and performance with many tile sets are not proven. The public-only release loader works: `eii_product.store.loader` checks a `public_only` release, loads it into PostgreSQL and the embedded reader, and writes `load_receipt.json` only after both stores verify. The store registry, the two read-only adapters and the portability lint are in place. A geometry column is returned as upper-case little-endian ISO WKB in hexadecimal, with no spatial-reference identifier; the query file selects the column bare and the adapter wraps it outside the file. The PostgreSQL adapter names the extension's function by the extension's own schema, read at open. Two-engine parity on a real PostgreSQL service is not proved here. Source: product/src/eii_product/. Dependencies: `eii_core`, `pyvalhalla`, `pyyaml`, `pydantic`, `duckdb`, `psycopg` and `sqlglot`, as `product/pyproject.toml` declares (`pyvalhalla==3.9.1`, `pyyaml==6.0.3`, `pydantic==2.14.3`, `duckdb==2.0.0`, `psycopg[binary]==3.3.8` and `sqlglot==30.31.0`; `duckdb` and `psycopg` are the same pins as the root `engine` group, and `sqlglot` the same pin as the root `dev` group, because loading the packaged query inventory parses each query). The S3-T08 work declares FastAPI and uvicorn in the product manifest at the existing root `dev` pins. The clean-environment tests import both server packages and plant missing FastAPI and uvicorn installations (open item OI-116). Task S3-T07 adds the closed claim, component, fragment and question catalogues and refuses an unknown key, an unknown property, a swapped fact slot and a numeral in a template.

Read: [02_ARCHITECTURE.md](../docs/02_ARCHITECTURE.md), [08_BACKEND.md](../docs/08_BACKEND.md)

The `tools/sector_facts.py` module accepts the eight topics of document 08
section 6.2 through strict inputs. Licences, churn, pay decomposition and zone momentum
call `eii_core.calc`; employer scale, market context and visitor markets are
fixed Public reads. All emitted facts pass the shared model and complete-chain
builder, including lineage validation at final assembly. Churn returns one rate
block per complete year supplied by the calculation layer, using named national
sums. The year is its fact period; the active snapshot enters `base_period`.
Unit economics returns compensation, surplus, goods, services, food, beverages
and building-rent shares. Component labels follow the pinned C4 replay and the
release indicator encoding; each group total is a named read. Scenarios wait for
S7-T01. No employer-scale
shares or employees-per-establishment figure, price-index topic, class-level
quotient or national resident sum is implemented. Arabic labels remain pending
native review. Parity cases are in `tools/registry.py`; only the embedded leg is
exercised by this task. The package also ships the tool's named Public queries
and declares Pydantic for its strict input model.

The S3-T08 `site_check` definition executes the available Public tools, writes
local tool-ledger rows, and serves a template SSE answer when `create_app` is
given a loaded store and ledger. Evidence carries its source chain; narrative
and completion wait for catalogue validation and the accounting gate, including
revalidation of the default selection after failure. Reconnection replays the
in-process answer without rerunning tools. The local seat stand-in remains an
empty seat key and null organisation until S9. A failed POST rolls back its
ledger writes and creates no answer. The playbook routes return the BE-91 error
envelope with the same error identifier in their BE-94 log line; other routers
keep their existing error handling.

Narrative events contain the validated brief values (each list item separately),
in brief section order. Completion carries `{answer_id, brief}` with the closed,
validated brief. The receipt's `Checked before display` object holds the five
check results plus `assumptions`, `caveat_keys` and `coverage_keys`, as L-712 G1
requires; these gate lists are not brief properties.

Rings and split directives share the area parser's grammar. Other directive and
brief identifiers keep the general identifier grammar. The offline integration
uses the custodian-built Public fixture and real loader; PostgreSQL driver rows
are replayed offline, so that test is not live engine parity. The lead-run
`scripts/tests/live_public_playbook.py` companion checks repeated bundles and
briefs across both live stores and supplies a divergence plant. It has not been
run for this worker handoff. No model, memoisation, shapes route or health route
is added. The tile spike's status route remains. The shipped foundation catalogue
has no claims; richer claim checks use invented test-local catalogues. Arabic
step labels remain pending native review.
