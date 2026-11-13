# product/ — serving plane `eii_product`

This folder will hold `eii_product`, the read-only serving plane: the store, the tools, the governed assistant, the ledger and the API.

## Rules

- `eii_product` never imports `eii_custodian` and never reaches `data/vault/` (ARC-06, BE-02, BE-05).
- `eii_product` never imports the typed-decision gateway and never reads its settings (BE-102).
- Only a verified release crosses from the custodian plane to this plane.

Status: package skeleton plus the tile spike API under `eii_product.api` and its HTTP range tests (task S1-T04). It also holds a fixture-only [area spike](src/eii_product/areas_spike/README.md) (task S1-T03): walk and drive areas from pyvalhalla in process, on a synthetic road extract built by the spike's own generator, with one set of routing tiles for each distinct hourly speed factor; the engine's polygon is kept exactly beside whole frame cells. A real road network, the release graph and performance with many tile sets are not proven. No release, store loader or product interface is claimed to work. Source: product/src/eii_product/. Dependencies: eii_core only (FastAPI and uvicorn are installed through the root `dev` group until task S3-T08, see open item OI-116; the libraries of the area spike through the root `engine` group).

Read: [02_ARCHITECTURE.md](../docs/02_ARCHITECTURE.md), [08_BACKEND.md](../docs/08_BACKEND.md)
