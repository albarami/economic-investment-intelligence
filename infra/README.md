# infra/ — database, Compose and stage configuration

This folder holds the Compose file for the database service. It will hold the PostgreSQL SQL (roles, row-level security, schemas), the stage scripts and the append-only export register.

## Rules

- No credential is committed here or anywhere else in the repository.
- `infra/export_register.jsonl` is created by a later task and is append-only (ARC-126).

Status: the Compose file is present. The PostgreSQL SQL, the stage scripts and the export register are not all present yet.

Read: [13_DEPLOYMENT_AND_OPERATIONS.md](../docs/13_DEPLOYMENT_AND_OPERATIONS.md), [02_ARCHITECTURE.md](../docs/02_ARCHITECTURE.md)
