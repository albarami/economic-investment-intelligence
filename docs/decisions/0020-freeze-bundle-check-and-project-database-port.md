# 0020 — Freeze-bundle preflight and the database port of this project's Compose service

| | |
|---|---|
| Status | Accepted, 2026-11-12 (amendment 7 to the first pack) |
| Date | 2026-11-12 |
| Owner | albarami |
| Purpose | Record the freeze-bundle preflight rule and the loopback port of this project's database service. |
| Read first | [13_DEPLOYMENT_AND_OPERATIONS.md](../13_DEPLOYMENT_AND_OPERATIONS.md), [16_DEMO_RUNBOOK.md](../16_DEMO_RUNBOOK.md), [0003](0003-postgresql-postgis-in-version-1.md), [0011](0011-store-selection-at-start-up.md) |

## Context

- OPS-06 keeps normal severity for checks other than the four foundation rows. The tiles, glyphs and interface fonts row checks a freeze bundle, which does not exist before the first freeze.
- The operations document used loopback port 55432. The owner assigned this project's Compose database service to loopback port 55440 and reported that Compose works on the build machine.

## Decision

1. The tiles, glyphs and interface fonts row is a freeze-bundle check in every mode. With no `freeze.json` under `data/freeze/`, it prints a defined warning and does not make preflight non-zero. Once a freeze bundle exists, it has full severity. The bubblewrap sandbox row is never downgraded on the build machine.
2. This project's database service is service `db` of Compose project `eii-poc`, published only on `127.0.0.1:55440`. Preflight and the database commands take the host and port from `EII_DATABASE_URL`; no host port is fixed in probe code. Only this project's database commands start or stop this project. Tests do not start or stop containers, and no command of this task touches another project's container, volume, network or port.

## Evidence

- `scripts/preflight_rows.py` implements both states of the freeze-bundle row; `scripts/tests/test_preflight_rows.py` and `scripts/tests/test_preflight_run.py` cover them and the foundation exit.
- `infra/compose.yaml` names the project and service, publishes through the required port interpolation and holds no host port number. `scripts/preflight_database.py` derives that interpolation from `EII_DATABASE_URL`.
- `scripts/tests/live_preflight_server.py` probes the service the lead starts. The S0-T08 task log in `PROGRESS.md` records the four live tests against this project's service.

## Consequences

- Documents 08, 12, 13, 14 and 16 read "normal severity" through the corrected preflight table and use the documented default address.
- The native option remains documented, but its setup script is not built in version 1.
- With no freeze bundle, preflight warns for `tiles-glyphs-fonts`; with a bundle, it fails until the later asset-hash check is built.

## What would change this decision

- An asset pipeline that places the governed tiles, glyphs and fonts outside the freeze bundle before the first freeze.
- A later owner decision assigning this project's service another loopback port or deployment path, while keeping the address configurable through `EII_DATABASE_URL`.

## Open questions and assumptions

- OI-110 to OI-112 hold the remaining S0-T08 assumptions.

## Sources

- Owner decisions on foundation preflight and the database port, 2026-11-11, and the owner note on this project's Compose service, 2026-11-12 (project records held by the owner).
- [13_DEPLOYMENT_AND_OPERATIONS.md](../13_DEPLOYMENT_AND_OPERATIONS.md) sections "Prerequisites and how each is checked", "PostgreSQL on the build machine", and "Store selection, the presenter switch and the local ledger".
