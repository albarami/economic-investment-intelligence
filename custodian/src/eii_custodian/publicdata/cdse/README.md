# Optional unread CDSE backup cache

S2-T41 and proposed decision 0066 define this custodian-only path. Ordinary
`./eii build-public` excludes the source, even with the pair present. Only the
lead-shell `./eii build-public --cdse-backup` form selects it. Missing/blank/partial
credentials omit it successfully. Current official provider evidence is pending,
so a full pair also omits it with `provider_contract_pending` and creates no cache.

`scripts/cdse_key.py` alone names the environment pair. The transport receives
injected values, uses a closed attempt sequence, rejects redirects and unlisted
hosts, holds tokens only in memory and redacts provider refusal text. It opens
no socket. Its empty reviewed-endpoint map admits no live host. `pending.v1`
Process and metadata envelopes are internal fixtures, never a claimed provider
request schema; no arbitrary URL, payload or evalscript is an input.

`contracts.py` uses the owner's tile parameters and explicit UTC windows. The
metric boundary is injected from the reviewed public frame; tests use an invented
boundary only. The cost model is an invented linear fixture formula with explicit
unit factors, minimum, rounding quantum and request costs. There is no assumed
provider allowance, account balance, rate limit or retry constant. Official
verification must supply the actual formula and pacing before bulk acquisition.

`cache.py` decodes and checks RGBA GeoTIFF bytes, binds dates/footprint/CRS and
response metadata to their hashes, records separate pending imagery/interface/
attribution readings, and reuses `sidecar_for`, `commit_pair` and the existing
immutable snapshots. Cache roots are `data/public_cache` only. Public-page
publisher evidence is required even when terms remain pending under decision 0059.
Snapshots are never exported to analytical tables, release/freeze files, product
assets or serving routes. Parent references resolve explicit tile/hash pairs;
this task builds no mosaic renderer, product adapter or display.

No provider page or live cache was read for this build. Official Authentication,
Process, Sentinel-2 L2A, acquisition-metadata, quota and legal page identities
are pending in OPEN_ITEMS.md. No new library or pin was introduced; raster/shape
handling follows the established grids/frame patterns. Normal independent maker
reviews and the lead's live proof remain separate from these offline tests.
