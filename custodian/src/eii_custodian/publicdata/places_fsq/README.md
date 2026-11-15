# Further places source

This package implements the pinned-copy reader of S2-T15 (PUB-102 and DAT-157).
Selection uses coordinate statistics against the frame, never the geographic bbox.
The parser preserves source fields; display eligibility, duplicates and category
mapping follow the reviewed policy. Fetch checks every selected file against the
summary before storing any receipt or manifest.

## Format facts this reader relies on

The following statements are transcribed from the lead’s format check, section 1,
read 2026-11-14. Row numbers identify that check, not pack requirements.
The reader supports only type-defined column order; IEEE total order is unknown.
Container sizes are bounded by remaining bytes, and nesting is limited to
64 structs and containers including FileMetaData. These are reader limits,
not requirements claimed for the format.

- Row 12: [TC "Boolean encoding"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-14: "Field values are encoded directly in the field header.".
- Row 13: [TC "Boolean encoding"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-14: "Element values of type `bool` are sent as an `i8`; true as `1` and false as `2`.".
- Row 14: [TC "List and Set"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-14: "The short form should be used when the length is in the range 0 - 14 (inclusive).".
- Row 15: [TC "List and Set"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-14: Same codes today; the page warns there is "no guarantee that this will remain true after new types are added".
- Row 16: [TC "Map"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-14: "Compact protocol map header (1 byte, empty map)".
- Row 18: [TC "List and Set"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-14: "By default there is no limit (meaning the limit is the maximum signed 32-bit integer value: 2147483647).".
- Row 21: [PQ-T `struct RowGroup`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-14: "This list must have the same order as the SchemaElement list in FileMetaData.".
- Row 22: [PQ-T `struct ColumnChunk`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-14: "If not set, assumed to be same file as metadata. This path is relative to the current file.".
- Row 23: [PQ-T `ColumnChunk.file_path`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-14: "These files do not appear to have ever been formally specified in the specification.".
- Row 27: [PQ-T `struct Statistics`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-14: "5: optional binary max_value;" / "6: optional binary min_value;".
- Row 28: [PQ-T `Statistics.max`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-14: "DEPRECATED: min and max value of the column. Use min_value and max_value.".
- Row 29: [PQ-T `FileMetaData.column_orders`, `union ColumnOrder`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-14: "The obsolete min and max fields in the Statistics object are always sorted by signed comparison regardless of column_orders." plus "DOUBLE - signed comparison of the represented value (*)".
- Row 30: [PQ-T `FileMetaData.column_orders`, `union ColumnOrder`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-14: "Without column_orders, the meaning of the min_value and max_value fields in the Statistics object and the ColumnIndex object is undefined." / "If the reader does not support the value of this union, min and max stats" (should be ignored).
- Row 31: [PQ-E "Plain"](https://parquet.apache.org/docs/file-format/data-pages/encodings/), read 2026-11-14: "DOUBLE: 8 bytes IEEE little endian". Quote was not checked word for word.
- Row 32: [PQ-T `struct Statistics`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-14: "All fields are optional.".
- Row 33: [PQ-T `Statistics.max_value`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-14: "Lower and upper bound values for the column, determined by its ColumnOrder.".
- Row 34: [PQ-T `union ColumnOrder` (TYPE_ORDER reader rules)](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-14: "If the min is a NaN, it should be ignored." / "If the max is a NaN, it should be ignored.".

Engine setting: `_connect` turns `enable_geoparquet_conversion` off before any
read. The pinned DuckDB settings table was checked in this pass: its default is
`true`, and the connection returned by `_connect` reports `false`.
[Configuration overview](https://duckdb.org/docs/2.0/configuration/overview),
read 2026-11-14 in the lead’s format check: "Attempt to decode/encode geometry
data in/as GeoParquet files if the spatial extension is present."

## Limits

Files not selected are not checked against the summary, so stale excluded files
can remain undiscovered; the format states "These files do not appear to have ever been formally specified in the specification."
([ColumnChunk.file_path](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-14, format-check row 23).

Not read by that check: geoparquet.org; parquet.apache.org nulls, page-index and statistics pages; the README Nulls section. GeoParquet primary_column/covering, the Parquet site quotes and DuckDB metadata columns/geo sentence were not checked word for word.
Not checked: spatial autoload in the Python client, ISO/EWKB geometry rules, or stored-file naming. The check ran no tests or project commands and fetched no data file.

Tests use invented footers and hand-made files only. No network fetch is needed.
The spatial-loaded parser run remains a lead check: the custodian mutation suite
runs in a copy of git-listed files without the ignored engine-extension folder.
This pass uses the permitted connection-setting test without a skip or a path
back to the original workspace.
