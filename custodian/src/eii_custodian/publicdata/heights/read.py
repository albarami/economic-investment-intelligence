"""B6: read the cached height files under their declared structure (PUB-07).

The receipt and hash checks copy the frame's `read_cached`, minus its JSON
parse, because the bodies here are raster and vector files. A row that is
skipped or has no cached file is not a failure: its source is absent with the
row's own technical reason. A declared value still holding the marker
`to be confirmed` keeps its source absent with `structure_unconfirmed`; an
unreadable declared format is absent the same way, while a declared unit or
reference system that is wrong is refused.
"""

from __future__ import annotations

import hashlib
import io
import math
import zipfile
from dataclasses import dataclass
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import numpy as np
import numpy.typing as npt
from affine import Affine
from shapely.geometry.base import BaseGeometry

from eii_custodian.publicdata.fetch.receipts import cache_directory
from eii_custodian.publicdata.fetch.registry import Entry

from .model import (
    SOURCE_IDS,
    HeightError,
    Rules,
    SourceStructure,
    structure_unconfirmed,
    unique_json,
)

EPSG_WGS84 = 4326
GLOBFP_FORMAT = "shapefile_zip"
WSF_FORMAT = "GTiff"
UNIT_METRES = "m"
GLOBFP_EXTENSIONS = ("cpg", "dbf", "prj", "shp", "shx")
GLOBFP_SHAPE_TYPE = 5
_DBF_HEADER_BYTES = 32
_DBF_FIELD_BYTES = 32
_DBF_TERMINATOR = 0x0D
_DBF_EOF = 0x1A
_DBF_VERSION = b"\x03"
_DBF_LIVE = b" "
# One bound on the unpacked members: the larger published tile unpacks to
# about 235 MB, so 1 GiB refuses a hostile size before any member is read.
_ZIP_MEMBER_TOTAL_MAX = 1 << 30
# One bound on a read window's cells: Qatar's extent is about 3.2 million
# cells of the published grid, so 64 million refuses a spanning window
# before any cell is read.
_WINDOW_CELL_MAX = 64_000_000
# The window grows one cell on each side so a building on a cell border
# still reads its own cell.
_WINDOW_GROW_CELLS = 1
# The body is hashed in pieces: the published cell file is about 2.1 GB and
# is never held in memory whole. 8 MiB pieces keep the read bounded.
_HASH_PIECE_BYTES = 8 << 20
_NUMERIC_DTYPES = frozenset(
    {"float16", "float32", "float64", "uint8", "uint16", "uint32", "int16", "int32"}
)


@dataclass(frozen=True)
class WsfGrid:
    """The window of one WSF 3D file kept for matching, with its own transform.

    `scale` is the declared text of the rules document, checked against the
    dataset's own scale; `wsf_value` turns a stored value into metres with it.
    """

    transform: Affine
    data: npt.NDArray[Any]
    nodata: Decimal
    width: int
    height: int
    scale: Decimal


@dataclass(frozen=True)
class SourceResult:
    """The files one source gave, or its absent reason and recorded terms.

    `rows` names every registry row of the source with its own state and
    reason; the source's state is `read` only when every row is, `absent`
    when no row gave a file, and `partial` between the two.
    """

    source_id: str
    state: str
    reason: str
    globfp: tuple[tuple[str, tuple[tuple[BaseGeometry, Decimal], ...]], ...]
    wsf: tuple[tuple[str, WsfGrid], ...]
    files: tuple[dict[str, object], ...]
    rows: tuple[dict[str, str], ...]
    terms_words: str
    terms_read_on: str
    retrieved_utc: str


def sha256_path(path: Path) -> str:
    """The hex digest of a file, read one piece at a time.

    The cell file is gigabytes and never enters memory whole; the piecewise
    digest is the same value `sha256_hex` gives the full bytes.
    """
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for piece in iter(lambda: source.read(_HASH_PIECE_BYTES), b""):
            digest.update(piece)
    return digest.hexdigest()


def _local_file(cache: Path, path: Path) -> Path:
    """Reject schemes, GDAL virtual paths and cache escapes before decoding."""
    name = str(path)
    if urlsplit(name).scheme or name.startswith("/vsi"):
        raise HeightError("cache_path")
    candidate = path.resolve()
    if not candidate.is_relative_to(cache.resolve()):
        raise HeightError("cache_path")
    if not candidate.is_file():
        raise HeightError("cache_path")
    return candidate


def _verified_body(cache: Path, entry: Entry) -> tuple[Path, dict[str, object]] | None:
    """The receipt and hash checks of `read_cached`, minus the JSON parse.

    Returns None when the row has no cached file (`not_fetched`); every other
    defect is a refusal. The body is hashed in pieces, never held in memory.
    """
    directory = cache_directory(cache, entry.key)
    receipts = sorted(directory.glob("*.meta.json"))
    if not receipts:
        return None
    if len(receipts) != 1:
        raise HeightError("cache_receipt")
    try:
        receipt = unique_json(receipts[0].read_text(encoding="utf-8"), "cache_receipt")
    except OSError:
        raise HeightError("cache_receipt") from None
    if not isinstance(receipt, dict):
        raise HeightError("cache_receipt")
    for field, expected in (
        ("source_id", entry.source_id),
        ("key", entry.key),
        ("licence_id", entry.licence_id),
        ("licence_basis", entry.licence_basis),
    ):
        if receipt.get(field) != expected:
            raise HeightError("cache_receipt_mismatch")
    for field in ("publisher", "title_en", "fetch_url", "retrieved_utc", "sha256"):
        if not receipt.get(field):
            raise HeightError("cache_receipt_missing")
    if receipt.get("switched_off") is not False:
        raise HeightError("switched_off")
    digest = str(receipt["sha256"])
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise HeightError("malformed_hash")
    body_path = directory / f"{digest}.{entry.extension}"
    if not body_path.is_file() or sha256_path(body_path) != digest:
        raise HeightError("content_hash_mismatch")
    return body_path, receipt


def _file_record(
    entry: Entry, receipt: dict[str, object], digest: str
) -> dict[str, object]:
    return {
        "key": entry.key,
        "licence_basis": entry.licence_basis,
        "licence_id": entry.licence_id,
        "retrieved_utc": receipt["retrieved_utc"],
        "role": "read",
        "sha256": digest,
        "terms_read_on": entry.terms_read_on,
        "terms_words": entry.terms_words,
        "url": receipt["fetch_url"],
    }


def _declared_check(structure: SourceStructure) -> None:
    """The declared unit and reference system are the only ones we read (R9g)."""
    if structure.unit != UNIT_METRES:
        raise HeightError("declared_unit")
    if structure.crs != f"EPSG:{EPSG_WGS84}":
        raise HeightError("declared_reference_system")


def _positive_height(value: Decimal) -> Decimal:
    """The parsed height text must be a positive, finite Decimal."""
    if not value.is_finite() or value <= 0:
        raise HeightError("height_value")
    return value


def _height_decimal(text: str) -> Decimal:
    """Only digits with at most one decimal point, in surrounding spaces.

    Everything else is refused as `height_value` by name: an exponent, an
    underscore, a sign, a second point, a lone point and a blank cell. The
    published tables hold plain digits, and `Decimal` would accept more
    than the published form ever writes.
    """
    body = text.strip(" ")
    if (
        not body
        or body.count(".") > 1
        or any(character not in "0123456789." for character in body)
        or not any(character in "0123456789" for character in body)
    ):
        raise HeightError("height_value")
    return Decimal(body)


def _zip_members(body: bytes) -> dict[str, bytes]:
    """The five members of one zipped shapefile, extension -> bytes.

    The published form is flat: exactly the five sidecars of one stem, never
    a folder, a further member, an encrypted member or a second stem. Member
    sizes are declared before extraction and their total is bounded.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            infos = archive.infolist()
            total = 0
            stems: set[str] = set()
            members: dict[str, str] = {}
            for info in infos:
                name = info.filename
                stem, dot, extension = name.rpartition(".")
                if (
                    info.is_dir()
                    or not dot
                    or "/" in name
                    or "\\" in name
                    or not stem
                    or extension not in GLOBFP_EXTENSIONS
                    or info.flag_bits & 0x1
                    or info.compress_type
                    not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                ):
                    raise HeightError("structure_mismatch")
                total += info.file_size
                if total > _ZIP_MEMBER_TOTAL_MAX:
                    raise HeightError("structure_mismatch")
                stems.add(stem)
                members[extension] = name
            if (
                len(infos) != len(GLOBFP_EXTENSIONS)
                or len(stems) != 1
                or sorted(members) != list(GLOBFP_EXTENSIONS)
            ):
                raise HeightError("structure_mismatch")
            bodies: dict[str, bytes] = {}
            for extension, name in members.items():
                try:
                    bodies[extension] = archive.read(name)
                except (
                    RuntimeError,
                    zipfile.BadZipFile,
                    NotImplementedError,
                    EOFError,
                    OSError,
                ):
                    raise HeightError("structure_mismatch") from None
    except zipfile.BadZipFile:
        raise HeightError("structure_mismatch") from None
    return bodies


def _dbf_heights(dbf: bytes, field_name: str) -> tuple[Decimal, ...]:
    """The declared numeric field's text of each live record, as Decimals.

    The table is read directly: a fixed-width text field holds a height of
    up to eighteen significant digits, which a library's numeric conversion
    would round. A missing, duplicated or non-numeric field, a record the
    table marks deleted, or a file shorter than its own header arithmetic is
    structure_mismatch; the length is checked before the header's terminator
    byte is read, so a table cut inside its header is refused the same way;
    a text that is no usable height is height_value.
    """
    minimum = _DBF_HEADER_BYTES + _DBF_FIELD_BYTES + 2
    if len(dbf) < minimum or dbf[0:1] != _DBF_VERSION:
        raise HeightError("structure_mismatch")
    count = int.from_bytes(dbf[4:8], "little")
    header_len = int.from_bytes(dbf[8:10], "little")
    record_len = int.from_bytes(dbf[10:12], "little")
    descriptors = header_len - _DBF_HEADER_BYTES - 1
    records_end = header_len + count * record_len
    if (
        header_len < minimum - 1
        or descriptors % _DBF_FIELD_BYTES
        or record_len < 2
        or len(dbf) < header_len
        or dbf[header_len - 1] != _DBF_TERMINATOR
        or len(dbf) < records_end
        or len(dbf) > records_end + 1
        or (len(dbf) == records_end + 1 and dbf[records_end] != _DBF_EOF)
    ):
        raise HeightError("structure_mismatch")
    fields: list[tuple[str, str, int, int]] = []
    offset = 1
    for index in range(descriptors // _DBF_FIELD_BYTES):
        start = _DBF_HEADER_BYTES + index * _DBF_FIELD_BYTES
        descriptor = dbf[start : start + _DBF_FIELD_BYTES]
        try:
            name = descriptor[:11].split(b"\x00", 1)[0].decode("ascii")
            field_type = descriptor[11:12].decode("ascii")
        except UnicodeDecodeError:
            raise HeightError("structure_mismatch") from None
        fields.append((name, field_type, offset, descriptor[16]))
        offset += descriptor[16]
    if offset != record_len:
        raise HeightError("structure_mismatch")
    found = [field for field in fields if field[0] == field_name]
    if len(found) != 1 or found[0][1] != "N":
        raise HeightError("structure_mismatch")
    _name, _type, field_offset, field_size = found[0]
    heights: list[Decimal] = []
    for row in range(count):
        start = header_len + row * record_len
        record = dbf[start : start + record_len]
        if record[0:1] != _DBF_LIVE:
            raise HeightError("structure_mismatch")
        try:
            text = record[field_offset : field_offset + field_size].decode("ascii")
        except UnicodeDecodeError:
            raise HeightError("height_value") from None
        try:
            heights.append(_positive_height(_height_decimal(text)))
        except ArithmeticError:
            raise HeightError("height_value") from None
    return tuple(heights)


def _parse_globfp(
    body: bytes, structure: SourceStructure
) -> tuple[tuple[BaseGeometry, Decimal], ...]:
    """The published form: one flat zip of five members sharing one stem.

    The `.prj` text is the older WGS 84 WKT without an authority code, so the
    reference system is decided by `to_epsg`, never by CRS equality. The
    `.dbf` records are read as raw fixed-width text so a height arrives digit
    for digit: the pinned shapefile package converts a numeric field to a
    float and would lose digits, so only its shapes are used, in file order,
    one shape per live `.dbf` record. `FID` and `FID_1` are not identities
    and are never read.
    """
    bodies = _zip_members(body)
    if bodies["cpg"].strip() != b"ISO-8859-1":
        raise HeightError("structure_mismatch")
    rasterio = import_module("rasterio")
    shapefile = import_module("shapefile")
    geometry = import_module("shapely.geometry")
    try:
        prj_text = bodies["prj"].decode("utf-8")
        epsg = rasterio.CRS.from_wkt(prj_text).to_epsg()
    except (UnicodeDecodeError, rasterio.errors.CRSError):
        raise HeightError("reference_system") from None
    if epsg != EPSG_WGS84:
        raise HeightError("reference_system")
    heights = _dbf_heights(bodies["dbf"], structure.field)
    try:
        reader = shapefile.Reader(
            shp=io.BytesIO(bodies["shp"]), shx=io.BytesIO(bodies["shx"])
        )
        records = reader.shapes()
    except Exception:
        raise HeightError("structure_mismatch") from None
    if len(records) != len(heights):
        raise HeightError("structure_mismatch")
    rows: list[tuple[BaseGeometry, Decimal]] = []
    for record, height in zip(records, heights, strict=True):
        if record.shapeType != GLOBFP_SHAPE_TYPE:
            raise HeightError("structure_mismatch")
        try:
            footprint = geometry.shape(record.__geo_interface__)
        except Exception:
            raise HeightError("structure_mismatch") from None
        if (
            footprint.is_empty
            or not footprint.is_valid
            or footprint.geom_type not in ("Polygon", "MultiPolygon")
        ):
            raise HeightError("structure_mismatch")
        rows.append((footprint, height))
    return tuple(rows)


def _raster_window(
    bounds: tuple[float, float, float, float] | None,
    transform: Affine,
    width: int,
    height: int,
) -> Any:
    """The pixel window over the building table's bounds, grown and clipped.

    `from_bounds` gives fractional offsets. The start of the bounds is
    floored and their end ceiled in cell units, the window then grows one
    cell on each side and is clipped to the raster, as document 07 (MTH-123)
    and the package README say. An empty window reads nothing.
    """
    windows = import_module("rasterio.windows")
    if bounds is None:
        col_start, row_start, col_stop, row_stop = 0, 0, width, height
    else:
        west, south, east, north = bounds
        raw = windows.from_bounds(west, south, east, north, transform)
        col_start = math.floor(raw.col_off) - _WINDOW_GROW_CELLS
        row_start = math.floor(raw.row_off) - _WINDOW_GROW_CELLS
        col_stop = math.ceil(raw.col_off + raw.width) + _WINDOW_GROW_CELLS
        row_stop = math.ceil(raw.row_off + raw.height) + _WINDOW_GROW_CELLS
    col_start = max(0, col_start)
    row_start = max(0, row_start)
    col_stop = min(width, col_stop)
    row_stop = min(height, row_stop)
    if col_stop <= col_start or row_stop <= row_start:
        return windows.Window(0, 0, 0, 0)
    return windows.Window(
        col_start, row_start, col_stop - col_start, row_stop - row_start
    )


def _parse_wsf(
    cache: Path,
    body_path: Path,
    structure: SourceStructure,
    bounds: tuple[float, float, float, float] | None,
) -> WsfGrid:
    """The declared band's window over the building table, never the whole file.

    The published raster stores tenths of a metre: the dataset's own scale,
    offset, no-data value, `unit` tag and raster type must equal the declared
    structure, and the declared scale is handed on for the value rule. Only
    the cells inside the window are read; a window past the cell bound is
    refused before any read.
    """
    checked = _local_file(cache, body_path)
    rasterio = import_module("rasterio")
    try:
        band = int(structure.band)
    except ValueError:
        raise HeightError("structure_mismatch") from None
    try:
        declared_nodata = Decimal(structure.nodata)
        declared_scale = Decimal(structure.scale)
    except ArithmeticError:
        raise HeightError("structure_mismatch") from None
    try:
        with rasterio.open(checked) as source:
            if source.count != band:
                raise HeightError("structure_mismatch")
            if source.crs is None or source.crs.to_epsg() != EPSG_WGS84:
                raise HeightError("reference_system")
            if any(dtype not in _NUMERIC_DTYPES for dtype in source.dtypes):
                raise HeightError("structure_mismatch")
            if source.nodata is None or Decimal(str(source.nodata)) != declared_nodata:
                raise HeightError("structure_mismatch")
            if (
                len(source.scales) != band
                or Decimal(str(source.scales[band - 1])) != declared_scale
            ):
                raise HeightError("structure_mismatch")
            if len(source.offsets) != band or Decimal(
                str(source.offsets[band - 1])
            ) != Decimal(0):
                raise HeightError("structure_mismatch")
            tags = source.tags()
            if tags.get("unit") != structure.unit:
                raise HeightError("structure_mismatch")
            if tags.get("AREA_OR_POINT") != "Area":
                raise HeightError("structure_mismatch")
            window = _raster_window(
                bounds, source.transform, source.width, source.height
            )
            if int(window.width) * int(window.height) > _WINDOW_CELL_MAX:
                raise HeightError("raster_window")
            if window.width and window.height:
                data = source.read(band, window=window)
            else:
                data = np.zeros((0, 0), dtype=source.dtypes[band - 1])
            return WsfGrid(
                transform=source.window_transform(window),
                data=data,
                nodata=Decimal(str(source.nodata)),
                width=int(data.shape[1]),
                height=int(data.shape[0]),
                scale=declared_scale,
            )
    except rasterio.errors.RasterioIOError:
        raise HeightError("structure_mismatch") from None


def read_sources(
    cache: Path,
    entries: tuple[Entry, ...] | list[Entry],
    rules: Rules,
    bounds: tuple[float, float, float, float] | None,
) -> dict[str, SourceResult]:
    """Read every active row of the two height sources; absent rows are kept.

    `bounds` is the building table's bounding box (west, south, east, north);
    it is a required argument, so a caller cannot read a raster source
    without handing the table's bounds in, and a raster row reads only the
    window over it (an empty table's bounds are None).
    """
    results: dict[str, SourceResult] = {}
    for source_id in SOURCE_IDS:
        structure = rules.structures[source_id]
        rows = sorted(
            (
                entry
                for entry in entries
                if entry.source_id == source_id
                and (entry.key == source_id or entry.key.startswith(source_id + "/"))
            ),
            key=lambda entry: entry.key,
        )
        terms = rows[0] if rows else None
        if (
            structure_unconfirmed(structure)
            or (source_id == "bldg_3dglobfp" and structure.format != GLOBFP_FORMAT)
            or (source_id == "bldg_wsf3d" and structure.format != WSF_FORMAT)
        ):
            results[source_id] = SourceResult(
                source_id=source_id,
                state="absent",
                reason="structure_unconfirmed",
                globfp=(),
                wsf=(),
                files=(),
                rows=tuple(
                    {
                        "key": row.key,
                        "reason": row.skip_reason or "structure_unconfirmed",
                        "state": "not_fetched",
                    }
                    for row in rows
                ),
                terms_words=terms.terms_words if terms else "",
                terms_read_on=terms.terms_read_on if terms else "",
                retrieved_utc="",
            )
            continue
        _declared_check(structure)
        globfp: list[tuple[str, tuple[tuple[BaseGeometry, Decimal], ...]]] = []
        wsf: list[tuple[str, WsfGrid]] = []
        files: list[dict[str, object]] = []
        records: list[dict[str, str]] = []
        retrieved_utc = ""
        for row in rows:
            state = "not_fetched"
            reason = row.skip_reason or "not_fetched"
            if not row.skip_reason:
                found = _verified_body(cache, row)
                if found is not None:
                    body_path, receipt = found
                    digest = str(receipt["sha256"])
                    if not retrieved_utc:
                        retrieved_utc = str(receipt["retrieved_utc"])
                    files.append(_file_record(row, receipt, digest))
                    file_name = row.key
                    if source_id == "bldg_3dglobfp":
                        globfp.append(
                            (
                                file_name,
                                _parse_globfp(body_path.read_bytes(), structure),
                            )
                        )
                    else:
                        wsf.append(
                            (
                                file_name,
                                _parse_wsf(cache, body_path, structure, bounds),
                            )
                        )
                    state, reason = "read", ""
            records.append({"key": row.key, "reason": reason, "state": state})
        missing = [record["reason"] for record in records if record["state"] != "read"]
        if globfp or wsf:
            state = "read" if not missing else "partial"
            reason = "" if not missing else missing[0]
        else:
            state = "absent"
            reason = missing[0] if missing else "not_fetched"
        results[source_id] = SourceResult(
            source_id=source_id,
            state=state,
            reason=reason,
            globfp=tuple(globfp),
            wsf=tuple(wsf),
            files=tuple(files),
            rows=tuple(records),
            terms_words=rows[0].terms_words if rows else "",
            terms_read_on=rows[0].terms_read_on if rows else "",
            retrieved_utc=retrieved_utc,
        )
    return results


__all__ = [
    "SourceResult",
    "WsfGrid",
    "read_sources",
    "sha256_path",
]
