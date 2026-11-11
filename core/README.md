# core/ — shared Python library `eii_core`

This folder will hold `eii_core`, the Python library shared by the custodian plane and the product plane: provenance, the fact model, the manifest, grid helpers and the calculation layer (`eii_core.calc`).

## Rules

- `eii_core` imports neither `eii_custodian` nor `eii_product` (ARC-06, BE-01).
- Every displayed number comes from deterministic, tested code. No model calculates.

Status: scaffolding only (task S0-T01). This folder holds no code yet.

Read: [02_ARCHITECTURE.md](../docs/02_ARCHITECTURE.md), [08_BACKEND.md](../docs/08_BACKEND.md)
