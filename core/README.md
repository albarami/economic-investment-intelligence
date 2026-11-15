# core/ — shared Python library `eii_core`

This folder will hold `eii_core`, the Python library shared by the custodian plane and the product plane: provenance, the fact model, the manifest, grid helpers and the calculation layer (`eii_core.calc`).

## Rules

- `eii_core` imports neither `eii_custodian` nor `eii_product` (ARC-06, BE-01).
- Every displayed number comes from deterministic, tested code. No model calculates.

Status: package skeleton (task S0-T02) and deterministic apportioning in `eii_core.calc.apportion` (task S2-T13). The package holds a version string and the apportioning calculation, with their tests under `tests/`. Source: core/src/eii_core/. Dependencies: none.

Read: [02_ARCHITECTURE.md](../docs/02_ARCHITECTURE.md), [08_BACKEND.md](../docs/08_BACKEND.md)
