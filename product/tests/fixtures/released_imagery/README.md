# Invented released-imagery fixture

All image pixels, tile coordinates, input hashes and acquisition observations here
are invented for offline tests. These are not fetched imagery or real coverage.
The generic credit fields exercise the existing closed release schema; they do
not attribute the invented pixels to a publisher. These test assets carry the
repository's licence in `LICENSE`.

`tile.jpg` is the fixed uniform JPEG made by `encoded_jpeg()` in
`custodian/tests/test_gis_snapshot.py`. `release/` holds the complete selected
assembly of `fixture_archive()` with that tile and its fixed test timestamp:
one content-addressed manifest and every assembled object, including receipts.
The TAR object is stored as `.tar.b64` so its padded numeric header fields do
not violate the repository's identifier guard. Test setup decodes the base64
to the original `.tar` bytes; no archive or receipt is rebuilt by the product.

The product tests copy only `release/` to their temporary directory and compare
served bytes with `tile.jpg`. They need no build-plane package or acquisition
directory. The custodian test
`test_assembled_release_equals_product_imagery_fixture` verifies the same invented
archive with `verify_selection()`, assembles it, and requires the manifest identity,
complete relative file set and every file byte to equal this decoded fixture. A changed
or omitted receipt, archive, manifest or JPEG fails that contract.

This fixture implements the test boundary of decision 0079 item 4 and AGENTS.md
rule 11. It establishes no live acquisition, coverage or release-command status.
