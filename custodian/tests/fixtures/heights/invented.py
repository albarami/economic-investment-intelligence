"""Hand-made stand-ins for the height inputs (FE-95).

Invented GeoJSON tables, invented zipped shapefiles and a tiny invented
raster, written only into a test's temporary folder; nothing real is fetched,
and no binary file is committed. Every identifier uses the SYN- form; the
fetch fixtures use the reserved invented host `syn-heights.invalid`, which
only a test admits to the allow-list, and the refusal plants use the
invented unlisted host `invented-unlisted.example`. The shapefile fixtures
are written by the pinned shapefile package's own writer; the bytes a writer
cannot produce (an 18-digit height text, a deletion mark, a wrong record
count, an encryption flag, a duplicated zip member, a corrupted member
stream, a lying shape record) are patched in the tests with the helpers here.
"""

from __future__ import annotations

import io
import json
import warnings
import zipfile

import numpy as np
import rasterio
import shapefile
import yaml
from rasterio.transform import from_origin

from eii_custodian.publicdata.fetch.receipts import (
    cache_directory,
    commit_pair,
    sha256_hex,
    sidecar_for,
)
from eii_custodian.publicdata.fetch.registry import Entry

ALLOWED_HOST = "syn-heights.invalid"
BLOCKED_HOST = "invented-unlisted.example"
NODATA = -32767
WGS84_PRJ = (
    b'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
    b'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    b'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)
GLOBFP_FIELDS = (
    ("FID", "N", 18, 0),
    ("Height", "N", 24, 15),
    ("FID_1", "N", 24, 15),
)


def square(x: float, y: float, size: float) -> list:
    """Return one ring of an axis-aligned square footprint."""
    return [
        [x, y],
        [x + size, y],
        [x + size, y + size],
        [x, y + size],
        [x, y],
    ]


def cw(ring: list) -> list:
    """Return the ring as a clockwise outer ring, the published tiles' form."""
    return [ring[0], *reversed(ring[1:-1]), ring[0]]


def building_feature(
    building_id: str,
    ring: list,
    recorded: object = None,
    floors: object = None,
    source: str = "SYN-FOOT",
    extra: dict | None = None,
    geometry: dict | None = None,
) -> dict:
    """One feature of the invented building table."""
    properties = {
        "building_id": building_id,
        "recorded_height_m": recorded,
        "floor_count": floors,
        "footprint_source_id": source,
    }
    if extra:
        properties.update(extra)
    return {
        "type": "Feature",
        "geometry": geometry or {"type": "Polygon", "coordinates": [ring]},
        "properties": properties,
    }


def buildings_bytes(features: list) -> bytes:
    """The invented building table as GeoJSON bytes."""
    return json.dumps({"type": "FeatureCollection", "features": features}).encode(
        "utf-8"
    )


def shapefile_members(
    shapes: list,
    records: list,
    fields: list | None = None,
    *,
    shape_type: int = shapefile.POLYGON,
    prj: bytes = WGS84_PRJ,
) -> dict:
    """The five members of one invented shapefile, as raw bytes.

    `shapes` is one entry per record: a list of rings (each ring a list of
    points) for a polygon file, a point pair for a point file, or None for a
    null shape. `records` is one list of field texts per record.
    """
    fields = fields if fields is not None else [list(f) for f in GLOBFP_FIELDS]
    shp_io, shx_io, dbf_io = io.BytesIO(), io.BytesIO(), io.BytesIO()
    writer = shapefile.Writer(shp=shp_io, shx=shx_io, dbf=dbf_io, shapeType=shape_type)
    for field in fields:
        writer.field(*field)
    for geometry, record in zip(shapes, records, strict=True):
        if geometry is None:
            writer.null()
        elif shape_type == shapefile.POLYGON:
            writer.poly(geometry)
        elif shape_type == shapefile.POINT:
            writer.point(*geometry)
        else:
            raise AssertionError("fixture shape type")
        writer.record(*record)
    writer.close()
    return {
        "cpg": b"ISO-8859-1",
        "dbf": dbf_io.getvalue(),
        "prj": prj,
        "shp": shp_io.getvalue(),
        "shx": shx_io.getvalue(),
    }


def zip_members(members: dict, compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    """Pack name -> bytes into one in-memory zip body.

    `compression` lets a planted case pack the members with a method the
    reader does not accept (the compression-method check's own plant).
    """
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression) as archive:
        for name, body in members.items():
            archive.writestr(_member(name), body, compress_type=compression)
    return out.getvalue()


def _member(name: str) -> zipfile.ZipInfo:
    """One member header with a fixed time, so a body never carries the clock.

    A member written by name takes the wall-clock time of its writing, and
    the manifest records each input's hash: two builds of one fixture that
    fell on either side of a two-second step of the zip time field gave
    different bytes. The fixed time is the zip format's first date; the
    permission bits are the ones a member written by name receives.
    """
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.external_attr = 0o600 << 16
    return info


def shapefile_zip(
    shapes: list,
    records: list,
    fields: list | None = None,
    *,
    stem: str = "syn.tile.01",
    shape_type: int = shapefile.POLYGON,
    prj: bytes = WGS84_PRJ,
    overrides: dict | None = None,
    extra: dict | None = None,
    drop: tuple = (),
) -> bytes:
    """One invented zipped shapefile: flat, five members of one stem.

    `stem` may hold dots, as the real tiles' names do. `overrides` replaces a
    member by extension, `drop` removes members, `extra` adds members under
    their own names (the planted refusals use all three).
    """
    bodies = shapefile_members(shapes, records, fields, shape_type=shape_type, prj=prj)
    bodies.update(overrides or {})
    for ext in drop:
        bodies.pop(ext, None)
    members = {f"{stem}.{ext}": body for ext, body in bodies.items()}
    members.update(extra or {})
    return zip_members(members)


def globfp_zip(
    features: list,
    field: str = "Height",
    stem: str = "syn.tile.01",
    **kwargs,
) -> bytes:
    """Invented 3D-GloBFP tile: (geometry, height text) pairs in a zip.

    A geometry is one ring (a list of points) or a list of rings for a
    footprint with a hole or several parts. Three numeric fields carry the
    height field in the middle; the first and last columns stand for FID and
    FID_1, whose texts mean nothing to the reader.
    """
    fields = [
        [field if name == "Height" else name, ftype, size, decimals]
        for name, ftype, size, decimals in GLOBFP_FIELDS
    ]
    shapes = []
    for geometry, _height in features:
        if isinstance(geometry[0][0], (int, float)):
            shapes.append([cw(geometry)])
        else:
            shapes.append([cw(ring) for ring in geometry])
    records = [
        [str(index + 1), height, ""]
        for index, (_geometry, height) in enumerate(features)
    ]
    return shapefile_zip(shapes, records, fields, stem=stem, **kwargs)


def dbf_fields(dbf: bytes) -> list:
    """(name, type, record offset, size) of each field of the table bytes."""
    header_len = int.from_bytes(dbf[8:10], "little")
    count = (header_len - 33) // 32
    fields = []
    offset = 1
    for index in range(count):
        desc = dbf[32 + index * 32 : 32 + (index + 1) * 32]
        name = desc[:11].split(b"\x00", 1)[0].decode("ascii")
        fields.append((name, desc[11:12].decode("ascii"), offset, desc[16]))
        offset += desc[16]
    return fields


def dbf_field_offset(dbf: bytes, name: str) -> tuple:
    """(record offset, size) of the named field."""
    for field_name, _ftype, offset, size in dbf_fields(dbf):
        if field_name == name:
            return offset, size
    raise AssertionError(name)


def dbf_patch(dbf: bytes, row: int, offset: int, text: bytes) -> bytes:
    """Write raw bytes at one record offset of the table (a planted form)."""
    raw = bytearray(dbf)
    header_len = int.from_bytes(raw[8:10], "little")
    record_len = int.from_bytes(raw[10:12], "little")
    start = header_len + row * record_len + offset
    raw[start : start + len(text)] = text
    return bytes(raw)


def zip_flag_patch(body: bytes, flag: int) -> bytes:
    """Set the general-purpose flag bits of every central-directory entry.

    The planted encryption violation sets bit 0, which the standard library
    cannot write itself.
    """
    raw = bytearray(body)
    marker = b"PK\x01\x02"
    at = 0
    while True:
        at = body.find(marker, at)
        if at < 0:
            break
        raw[at + 8] |= flag
        at += 1
    return bytes(raw)


def zip_members_duplicated(members: dict, name: str, drop: str = "") -> bytes:
    """Pack members with one member name written twice (the duplicate plants).

    A dict cannot hold two entries of one name, so the planted
    duplicate-extension and member-set refusals pack their zip here:
    `name` is written twice and, when `drop` names an extension, one member
    of that extension is left out. The standard library warns about the
    repeated name; that warning is the plant's own form, not a defect.
    """
    out = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            for member, member_body in members.items():
                if member.endswith(f".{drop}"):
                    continue
                archive.writestr(
                    _member(member), member_body, compress_type=zipfile.ZIP_DEFLATED
                )
                if member == name:
                    archive.writestr(
                        _member(member), member_body, compress_type=zipfile.ZIP_DEFLATED
                    )
    return out.getvalue()


def zip_stream_corrupt(body: bytes, name: str) -> bytes:
    """Flip one byte inside one member's compressed stream.

    The central directory keeps its declared sizes, so every check before the
    member's own read passes and only the read itself fails (the extraction
    failure check's own plant).
    """
    raw = bytearray(body)
    marker = b"PK\x03\x04"
    at = body.find(marker)
    while at >= 0:
        name_len = int.from_bytes(raw[at + 26 : at + 28], "little")
        extra_len = int.from_bytes(raw[at + 28 : at + 30], "little")
        compressed = int.from_bytes(raw[at + 18 : at + 22], "little")
        if bytes(raw[at + 30 : at + 30 + name_len]) == name.encode("ascii"):
            if compressed < 2:
                raise AssertionError("member stream too small to corrupt")
            raw[at + 30 + name_len + extra_len + 1] ^= 0x55
            return bytes(raw)
        at = body.find(marker, at + 4)
    raise AssertionError(name)


def shp_record_numpoints(shp: bytes, count: int) -> bytes:
    """Rewrite the first shape record's point count (planted parse failures).

    The record content begins at byte 108 of the `.shp` body: shape type,
    bounding box, part count, then the point count, all little-endian in the
    published form. A count the writer never writes makes the shape parser
    or the geometry conversion refuse.
    """
    raw = bytearray(shp)
    at = 108 + 4 + 32 + 4
    raw[at : at + 4] = count.to_bytes(4, "little")
    return bytes(raw)


def wsf_bytes(
    path,
    values: list,
    width: int,
    height: int,
    *,
    west: float = 0.0,
    north: float = 1.0,
    cell: float = 1.0,
    nodata: float = NODATA,
    epsg: int = 4326,
    dtype: str = "int16",
    scale: float = 0.1,
    offset: float = 0.0,
    unit_tag: str | None = "m",
    area_or_point: str = "Area",
) -> bytes:
    """A tiny invented WGS 84 raster in the published form's metadata.

    Stored integers times the declared scale are metres; the dataset tags
    `unit` and `AREA_OR_POINT` hold the unit and the raster type, as the real
    file does (`area_or_point` lets a planted case tag the raster "Point",
    the raster-type check's own plant). Returns the file's bytes for the
    cache pair.
    """
    data = np.array(values, dtype=dtype).reshape(height, width)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=1,
        dtype=dtype,
        crs=f"EPSG:{epsg}",
        transform=from_origin(west, north, cell, cell),
        nodata=nodata,
    ) as target:
        target.write(data, 1)
        target.scales = (scale,)
        target.offsets = (offset,)
        target.update_tags(AREA_OR_POINT=area_or_point)
        if unit_tag is not None:
            target.update_tags(unit=unit_tag)
    return path.read_bytes()


def rules_document(
    *,
    storey: str = "4",
    label: str = "ASSUMPTION",
    globfp_format: str = "shapefile_zip",
    globfp_field: str = "Height",
    globfp_unit: str = "m",
    globfp_crs: str = "EPSG:4326",
    wsf_format: str = "GTiff",
    wsf_band: str = "1",
    wsf_unit: str = "m",
    wsf_nodata: str = str(NODATA),
    wsf_scale: str = "0.1",
    wsf_crs: str = "EPSG:4326",
    wsf_dtype: str = "int16",
) -> dict:
    """A hand-made declared structure with invented names (B6)."""
    return {
        "storey_height_m": {
            "value": storey,
            "label": label,
            "basis": "invented fixture basis text",
        },
        "order": "invented order wording",
        "match_3dglobfp": "invented 3D-GloBFP matching rule",
        "match_wsf3d": "invented WSF 3D matching rule",
        "credit_3dglobfp": "Invented credit line, retrieved {date}.",
        "sources": {
            "bldg_3dglobfp": {
                "format": globfp_format,
                "field": globfp_field,
                "unit": globfp_unit,
                "nodata": "",
                "crs": globfp_crs,
            },
            "bldg_wsf3d": {
                "format": wsf_format,
                "band": wsf_band,
                "unit": wsf_unit,
                "nodata": wsf_nodata,
                "scale": wsf_scale,
                "crs": wsf_crs,
                "dtype": wsf_dtype,
            },
        },
    }


def rules_file(path, **overrides):
    """Write a hand-made rules document and return its path."""
    return write_rules(path, rules_document(**overrides))


def write_rules(path, document: dict):
    """Write a mutated rules document and return its path."""
    path.write_text(yaml.safe_dump(document, sort_keys=True), encoding="utf-8")
    return path


def entry(source_id: str, key: str | None = None, **overrides) -> Entry:
    """One invented height-source registry row on an allow-listed host."""
    fields = {
        "key": key or source_id,
        "source_id": source_id,
        "slug": "",
        "kind": "https_file",
        "title_en": "Invented S2-T20 height row",
        "publisher": "SYN-publisher",
        "licence_id": "CC-BY-4.0",
        "licence_basis": "dataset",
        "decision_record": "",
        "fetch_host": ALLOWED_HOST,
        "url": f"https://{ALLOWED_HOST}/SYN/{source_id}.bin",
        "terms_url": "",
        "terms_words": "invented terms words for a test",
        "terms_read_on": "2026-11-14",
        "nightly_live_fetch": False,
        "public_splits": (),
        "commit_allowed": False,
        "release_tables": (),
        "caveat_keys": (),
        "columns": (),
        "row_count_min": None,
        "row_count_max": None,
        "period_first": "",
        "period_last": "",
        "period_field": "",
        "reconciliation": "none",
        "skip_reason": "",
        "extension": "bin",
        "landing_url": "",
    }
    fields.update(overrides)
    return Entry(**fields)


def store(cache, row: Entry, body: bytes, publisher: str = "SYN-publisher"):
    """Write one hash-addressed cache pair for a row and return its digest."""
    digest = sha256_hex(body)
    sidecar = sidecar_for(
        row,
        digest=digest,
        nbytes=len(body),
        fetch_url=row.url,
        fetch_host=row.fetch_host,
        retrieved_utc="2026-11-14T00:00:00Z",
        publisher=publisher,
        source_modified="",
        row_count=None,
        terms_sha256="",
    )
    commit_pair(cache_directory(cache, row.key), digest, row.extension, body, sidecar)
    return digest


def card_fixture(tmp_path):
    """The card's seven invented buildings and their two invented sources.

    Building i sits at x in [i + 0.1, i + 0.6], y in [0.1, 0.6]; its
    representative point lands near (i + 0.35, 0.35), inside WSF cell i.
    """
    specs = {
        "SYN-B-0001": (30, 8),
        "SYN-B-0002": (12, 3),
        "SYN-B-0003": (21, None),
        "SYN-B-0004": (None, 5),
        "SYN-B-0005": (None, None),
        "SYN-B-0006": (None, None),
        "SYN-B-0007": (None, None),
    }
    features = [
        building_feature(building_id, square(i + 0.1, 0.1, 0.5), recorded, floors)
        for i, (building_id, (recorded, floors)) in enumerate(sorted(specs.items()))
    ]
    globfp = globfp_zip(
        [
            (square(0.05, 0.05, 0.6), "24"),
            (square(1.05, 0.05, 0.6), "15"),
            (square(2.05, 0.05, 0.6), "15"),
            (square(3.05, 0.05, 0.6), "11"),
            (square(6.05, 0.05, 0.6), "7"),
        ]
    )
    wsf = wsf_bytes(
        tmp_path / "syn-wsf.tif",
        [[180, NODATA, 130, NODATA, 60, NODATA, 50, NODATA]],
        8,
        1,
    )
    return buildings_bytes(features), globfp, wsf
