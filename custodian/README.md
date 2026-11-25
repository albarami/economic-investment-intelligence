# custodian/ — build plane `eii_custodian`

This folder will hold `eii_custodian`, the offline build plane: public data, the synthetic world, linkage, the privacy engine, the mobility simulator and the release builder.

## Rules

- This is the only plane in which record-level synthetic data may exist. Every person is invented; the companies are the real ones of the public register, and their labour and residence records are synthetic (AGENTS.md rule 3).
- `eii_custodian` never imports `eii_product` (ARC-06, BE-03).
- Generators and the release build run inside the sandbox (ARC-09, ARC-10).

The section 10 stage reads PUB-71's expected rounded results from
`local_expectations/PUB-71.json` inside the uncommitted public cache
(`data/public_cache/`). The lead writes that record on the build machine from
the published source; none of its values is committed.

The lead-only [restricted findings data tests](data_tests/README.md) document
the companion metadata, independent expectation preparation and wrong-value
proof for PUB-71 and the other locally retained findings (task S2-T35).

Status: package skeleton (task S0-T02). The package holds a version string and two small tests under `tests/`. Source: custodian/src/eii_custodian/. Dependencies: eii_core only.

Read: [02_ARCHITECTURE.md](../docs/02_ARCHITECTURE.md), [05_SYNTHETIC_WORLD_AND_SIMULATION.md](../docs/05_SYNTHETIC_WORLD_AND_SIMULATION.md), [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](../docs/06_PRIVACY_AND_DISCLOSURE_CONTROL.md)
