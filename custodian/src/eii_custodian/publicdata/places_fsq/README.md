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
- Row 31: [PQ-E "Plain"](https://parquet.apache.org/docs/file-format/data-pages/encodings/), read 2026-11-14: "DOUBLE: 8 bytes IEEE little endian". The quote was checked word for word on 2026-11-15 against the page, under its heading "Plain: (PLAIN = 0)", and against the page's source, [PQ-E source "Plain: (PLAIN = 0)"](https://raw.githubusercontent.com/apache/parquet-format/master/Encodings.md): the wording is the same in both.
- Row 32: [PQ-T `struct Statistics`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-14: "All fields are optional.".
- Row 33: [PQ-T `Statistics.max_value`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-14: "Lower and upper bound values for the column, determined by its ColumnOrder.".
- Row 34: [PQ-T `union ColumnOrder` (TYPE_ORDER reader rules)](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-14: "If the min is a NaN, it should be ignored." / "If the max is a NaN, it should be ignored.".

The following statements were read from the official pages on 2026-11-15, for
finding N1 of the confirmation. The numbers N1-01 to N1-46 identify that reading,
not pack requirements. Each quote holds the page's own words; line breaks, the
stars of a comment block and the link and emphasis marks of the page's source are
dropped. PQ-R is the format's own README, PQ-G its geospatial definitions, and
GPQ the GeoParquet specification, read in its latest release, v2.0.0, and in
v1.1.0; a GPQ quote is the same in both releases unless the entry says otherwise.
The reader reads `columns` and `bbox` of the `geo` value and no other member:
`version`, `primary_column`, `encoding` and `covering` are not read.

The reader's own allowances, which are not statements of the official pages: the
bounding box is taken from the first column of `columns` that holds one, not from
the primary column; a `bbox` at the top level of the `geo` value is tolerated as an
extra field; a `geo` key in the key-value metadata of a column chunk is read as
well as the file's; a bounding box that does not hold four numbers is not listed;
and an enumeration field is expected as a 32-bit integer. The first four touch
only the list of geographic boxes that the reader records as ignored, never which
files are selected; where the last does not hold, the statistics read as missing
and the file set is refused by name.

- N1-01: [PQ-R "File format"](https://raw.githubusercontent.com/apache/parquet-format/master/README.md), read 2026-11-15: "4-byte magic number "PAR1"".
- N1-02: [PQ-R "File format"](https://raw.githubusercontent.com/apache/parquet-format/master/README.md), read 2026-11-15: "4-byte length in bytes of file metadata (little endian)".
- N1-03: [PQ-R "Metadata"](https://raw.githubusercontent.com/apache/parquet-format/master/README.md), read 2026-11-15: "All thrift structures are serialized using the TCompactProtocol.".
- N1-04: [PQ-R "Separating metadata and column data"](https://raw.githubusercontent.com/apache/parquet-format/master/README.md), read 2026-11-15: "This allows splitting columns into multiple files, as well as having a single metadata file reference multiple parquet files.".
- N1-05: [TC "Struct"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "A `struct` is a sequence of zero or more fields, followed by a stop field.".
- N1-06: [TC "Struct"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "Therefore it is also possible to handle unknown fields while decoding by ignoring them. The field type is used to determine how to decode field values.".
- N1-07: [TC "Struct"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "A `union` is encoded the same as a struct with the additional restriction that at most 1 field may be encoded.".
- N1-08: [TC "Struct encoding"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "`dddd` is the field id delta, an unsigned 4-bit integer." / "`tttt` is field-type, an unsigned 4-bit integer (see below).".
- N1-09: [TC "Struct encoding"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "`field id` the field id (i16), ZigZag'ed varint encoded.".
- N1-10: [TC "Struct encoding"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "The field id delta can be computed by `current-field-id - previous-field-id`, or just `current-field-id` if this is the first of the struct." / "The short form should be used when the field id delta is in the range 1 - 15 (inclusive).".
- N1-11: [TC "Struct encoding"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: under the label "Compact protocol stop-field:" the page draws the stop field as one byte whose bits are all zero (the drawing is not copied here, because it is a run of eight digits).
- N1-12: [TC "Struct encoding"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "`BOOLEAN_TRUE`, encoded as `1`" / "`BOOLEAN_FALSE`, encoded as `2`" / "`I8`, encoded as `3`" / "`I16`, encoded as `4`" / "`I32`, encoded as `5`" / "`I64`, encoded as `6`" / "`DOUBLE`, encoded as `7`" / "`BINARY`, used for binary and string fields, encoded as `8`" / "`LIST`, encoded as `9`" / "`SET`, encoded as `10`" / "`MAP`, encoded as `11`" / "`STRUCT`, used for both structs and union fields, encoded as `12`".
- N1-13: [TC "Struct encoding"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "the encoding of a boolean field value has no length (0 bytes).".
- N1-14: [TC "Integer encoding"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "Values of type `i8` and `byte` are encoded as one byte." / "Values of type `i16`, `i32` and `i64` are first transformed to using ZigZag and that result is then varint encoded before being written.".
- N1-15: [TC "ZigZag encoding"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "def ToZigzag(n: Long): Long = (n << 1) ^ (n >> 63)" / "def FromZigzag(n: Long): Long = (n >>> 1) ^ - (n & 1)".
- N1-16: [TC "Varint encoding"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "A ULEB128 value is encoded 7 bits at a time, starting from the LSB. Each 7 bits are encoded as 8 bits with the top bit set if it is not the last byte.".
- N1-17: [TC "Enum encoding"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "`enum`s are encoded as their integer value as defined by the Thrift IDL.".
- N1-18: [TC "Binary encoding"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "`byte length` is the length of the byte array (non-negative), encoded as a varint (not ZigZag'ed).".
- N1-19: [TC "String encoding"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "`string`s are written as binary and must be encoded as UTF-8.".
- N1-20: [TC "Double encoding"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "Values of type `double` are written in IEEE 754 format (the standard representation on almost all systems) in little-endian byte order (8 bytes).".
- N1-21: [TC "List and Set"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "`list`s and `set`s are encoded the same: a header indicating the size and the element-type of the elements, followed by the encoded elements.".
- N1-22: [TC "List and Set"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "`ssss` is the size, 4-bit unsigned values `0` - `14`" / "`tttt` is the element-type, a 4-bit unsigned value" / "`size` is the size, an unsigned 32-bit varint, `15` or higher (not ZigZag encoded)."; the long form is drawn with a first byte "1111tttt".
- N1-23: [TC "Map"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "`size` is the 32-bit unsigned size, varint encoded (not ZigZag'ed)." / "`kkkk` is the key element-type, a 4-bit unsigned value" / "`vvvv` is the value element-type, a 4-bit unsigned value".
- N1-24: [TC "Map"](https://raw.githubusercontent.com/apache/thrift/master/doc/specs/thrift-compact-protocol.md), read 2026-11-15: "The maximum map size is configurable. By default there is no limit (meaning the limit is the maximum 32-bit value: 2147483647).".
- N1-25: [PQ-T `struct FileMetaData`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-15: "4: required list<RowGroup> row_groups" / "5: optional list<KeyValue> key_value_metadata" / "7: optional list<ColumnOrder> column_orders;".
- N1-26: [PQ-T `FileMetaData.column_orders`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-15: "Sort orders are listed in the order matching the columns in the schema. The indexes are not necessarily the same though, because only leaf nodes of the schema are represented in the list of sort orders.".
- N1-27: [PQ-T `struct RowGroup`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-15: "1: required list<ColumnChunk> columns".
- N1-28: [PQ-T `struct ColumnChunk`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-15: "1: optional string file_path" / "3: optional ColumnMetaData meta_data".
- N1-29: [PQ-T `struct ColumnMetaData`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-15: "1: required Type type" / "3: required list<string> path_in_schema" / "8: optional list<KeyValue> key_value_metadata" / "12: optional Statistics statistics;".
- N1-30: [PQ-T `enum Type`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-15: "DOUBLE = 5;".
- N1-31: [PQ-T `struct Statistics`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-15: "1: optional binary max;" / "2: optional binary min;".
- N1-32: [PQ-T `struct Statistics`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-15: "Values are encoded using PLAIN encoding, except that variable-length byte arrays do not include a length prefix.".
- N1-33: [PQ-T `struct KeyValue`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-15: "1: required string key" / "2: optional string value".
- N1-34: [PQ-T `union ColumnOrder`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-15: "struct TypeDefinedOrder {}" / "1: TypeDefinedOrder TYPE_ORDER;"; the members this reader does not support are "2: IEEE754TotalOrder IEEE_754_TOTAL_ORDER;" and "3: Int96TimestampOrder INT96_TIMESTAMP_ORDER;".
- N1-35: [PQ-T `struct FileMetaData`, `struct SchemaElement`, `struct RowGroup`, `struct ColumnMetaData`, `enum FieldRepetitionType`, `enum Encoding`, `enum CompressionCodec`](https://raw.githubusercontent.com/apache/parquet-format/master/src/main/thrift/parquet.thrift), read 2026-11-15, for the fields that only the fixture writer `metadata_bytes` writes: "1: required i32 version" / "2: required list<SchemaElement> schema;" / "3: required i64 num_rows" / "6: optional string created_by" / "1: optional Type type;" / "3: optional FieldRepetitionType repetition_type;" / "4: required string name;" / "5: optional i32 num_children;" / "2: required i64 total_byte_size" / "2: required list<Encoding> encodings" / "4: required CompressionCodec codec" / "5: required i64 num_values" / "9: required i64 data_page_offset" / "REQUIRED = 0;" / "OPTIONAL = 1;" / "PLAIN = 0;" / "UNCOMPRESSED = 0;".
- N1-36: [GPQ v2.0.0 "Version and schema"](https://geoparquet.org/releases/v2.0.0/), read 2026-11-15: "This is version 2.0.0 of the GeoParquet specification."; [GPQ v1.1.0 "Version and schema"](https://geoparquet.org/releases/v1.1.0/), read 2026-11-15: "This is version 1.1.0 of the GeoParquet specification.".
- N1-37: [GPQ v2.0.0 "Metadata"](https://geoparquet.org/releases/v2.0.0/) and [GPQ v1.1.0 "Metadata"](https://geoparquet.org/releases/v1.1.0/), read 2026-11-15: "A GeoParquet file MUST include a `geo` key in the Parquet metadata" (the page names `FileMetaData::key_value_metadata`) / "The value of this key MUST be a JSON-encoded UTF-8 string representing the file and column metadata that validates against the GeoParquet metadata schema.".
- N1-38: [GPQ v2.0.0 "File metadata"](https://geoparquet.org/releases/v2.0.0/) and [GPQ v1.1.0 "File metadata"](https://geoparquet.org/releases/v1.1.0/), read 2026-11-15, on `columns`: "REQUIRED. Metadata about geometry columns. Each key is the name of a geometry column in the table.".
- N1-39: [GPQ v2.0.0 "File metadata"](https://geoparquet.org/releases/v2.0.0/) and [GPQ v1.1.0 "File metadata"](https://geoparquet.org/releases/v1.1.0/), read 2026-11-15, on `primary_column`, which this reader does not read: "REQUIRED. The name of the "primary" geometry column. In cases where a GeoParquet file contains multiple geometry columns, the primary geometry may be used by default in geospatial operations.".
- N1-40: [GPQ v2.0.0 "Column metadata"](https://geoparquet.org/releases/v2.0.0/) and [GPQ v1.1.0 "Column metadata"](https://geoparquet.org/releases/v1.1.0/), read 2026-11-15: "Each geometry column in the dataset MUST be included in the `columns` field above with the following content, keyed by the column name:"; on `bbox`: "Bounding Box of the geometries in the file, formatted according to RFC 7946, section 5."; on `covering`, which this reader does not read: "Object containing bounding box column names to help accelerate spatial data retrieval".
- N1-41: [GPQ v2.0.0 "bbox"](https://geoparquet.org/releases/v2.0.0/) and [GPQ v1.1.0 "bbox"](https://geoparquet.org/releases/v1.1.0/), read 2026-11-15: "The bbox, if specified, MUST be encoded with an array representing the range of values for each dimension in the geometry coordinates. For geometries in a geographic coordinate reference system, longitude and latitude values are listed for the most southwesterly coordinate followed by values for the most northeasterly coordinate.".
- N1-42: [GPQ v2.0.0 "bbox"](https://geoparquet.org/releases/v2.0.0/), read 2026-11-15: "XY (two dimensions): `[<xmin>, <ymin>, <xmax>, <ymax>]`"; [GPQ v1.1.0 "bbox"](https://geoparquet.org/releases/v1.1.0/), read 2026-11-15: "For example, given geometries that have coordinates with two dimensions, the bbox would have the form `[<xmin>, <ymin>, <xmax>, <ymax>]`.".
- N1-43: [GPQ v1.1.0 "Column metadata"](https://geoparquet.org/releases/v1.1.0/), read 2026-11-15, on `encoding`, which this reader does not read: "REQUIRED. Name of the geometry encoding format. Currently `"WKB"`, `"point"`, `"linestring"`, `"polygon"`, `"multipoint"`, `"multilinestring"`, and `"multipolygon"` are supported."; [GPQ v2.0.0 "Column metadata"](https://geoparquet.org/releases/v2.0.0/), read 2026-11-15: "REQUIRED. Name of the geometry encoding format. Only `"WKB"` is supported.".
- N1-44: [GPQ v1.1.0 "WKB"](https://geoparquet.org/releases/v1.1.0/), read 2026-11-15: "WKB geometry columns MUST be stored using the `BYTE_ARRAY` parquet type."; [GPQ v2.0.0 "encoding"](https://geoparquet.org/releases/v2.0.0/), read 2026-11-15: "WKB geometry columns MUST be stored using the `BYTE_ARRAY` parquet type, with either a `GEOMETRY` or `GEOGRAPHY` logical type, as specified by the Parquet format.".
- N1-45: [GPQ v2.0.0 "Coordinate axis order"](https://geoparquet.org/releases/v2.0.0/) and [GPQ v1.1.0 "Coordinate axis order"](https://geoparquet.org/releases/v1.1.0/), read 2026-11-15: "The axis order of the coordinates in WKB stored in a GeoParquet follows the de facto standard for axis order in WKB and is therefore always (x, y) where x is easting or longitude and y is northing or latitude.".
- N1-46: [PQ-G "Background"](https://raw.githubusercontent.com/apache/parquet-format/master/Geospatial.md), read 2026-11-15: "Well-Known Binary (WKB) serializations (ISO variant supporting XY, XYZ, XYM, XYZM) are defined by OpenGIS Implementation Specification for Geographic information - Simple feature access - Part 1: Common architecture"; that document was not read, so the byte layout of a WKB point that `_wkb_point` expects carries no quote.

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

Not read by that check, and read on 2026-11-15: geoparquet.org, in its releases v2.0.0 and v1.1.0; the file-format and metadata pages of parquet.apache.org; the README File format, Metadata, Nulls and Separating metadata and column data sections; the format's geospatial definitions. The GeoParquet primary_column and covering sentences and the Parquet site quote of row 31 were checked word for word on that date. Still not read: the parquet.apache.org nulls, page-index and statistics pages. The DuckDB metadata columns/geo sentence is still not checked word for word.
Still not checked: spatial autoload in the Python client, the byte layout of a WKB point and the EWKB rules (the document that the official pages name for WKB was not read), the GeoParquet version that the copy's files declare, or stored-file naming. The check ran no tests or project commands and fetched no data file.

Tests use invented footers and hand-made files only. No network fetch is needed.
The spatial-loaded parser run remains a lead check: the custodian mutation suite
runs in a copy of git-listed files without the ignored engine-extension folder.
This pass uses the permitted connection-setting test without a skip or a path
back to the original workspace.
