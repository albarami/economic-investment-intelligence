# infra/ — database, Compose and stage configuration

This folder will hold the Compose file, the PostgreSQL SQL (roles, row-level security, schemas), the stage scripts and the append-only export register.

## Rules

- No credential is committed here or anywhere else in the repository.
- `infra/export_register.jsonl` is created by a later task and is append-only (ARC-126).

Status: scaffolding only (task S0-T01). This folder holds no code yet.

Read: [13_DEPLOYMENT_AND_OPERATIONS.md](../docs/13_DEPLOYMENT_AND_OPERATIONS.md), [02_ARCHITECTURE.md](../docs/02_ARCHITECTURE.md)
