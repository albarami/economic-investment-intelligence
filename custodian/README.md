# custodian/ — build plane `eii_custodian`

This folder will hold `eii_custodian`, the offline build plane: public data, the synthetic world, linkage, the privacy engine, the mobility simulator and the release builder.

## Rules

- This is the only plane in which record-level synthetic data may exist. Every company and person is invented.
- `eii_custodian` never imports `eii_product` (ARC-06, BE-03).
- Generators and the release build run inside the sandbox (ARC-09, ARC-10).

Status: scaffolding only (task S0-T01). This folder holds no code yet.

Read: [02_ARCHITECTURE.md](../docs/02_ARCHITECTURE.md), [05_SYNTHETIC_WORLD_AND_SIMULATION.md](../docs/05_SYNTHETIC_WORLD_AND_SIMULATION.md), [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](../docs/06_PRIVACY_AND_DISCLOSURE_CONTROL.md)
