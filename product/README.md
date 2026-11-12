# product/ — serving plane `eii_product`

This folder will hold `eii_product`, the read-only serving plane: the store, the tools, the governed assistant, the ledger and the API.

## Rules

- `eii_product` never imports `eii_custodian` and never reaches `data/vault/` (ARC-06, BE-02, BE-05).
- `eii_product` never imports the typed-decision gateway and never reads its settings (BE-102).
- Only a verified release crosses from the custodian plane to this plane.

Status: scaffolding only (task S0-T01). This folder holds no code yet.

Read: [02_ARCHITECTURE.md](../docs/02_ARCHITECTURE.md), [08_BACKEND.md](../docs/08_BACKEND.md)
