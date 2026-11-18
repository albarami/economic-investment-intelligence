"""Tiny invented binary layouts, generated only in test temporary folders."""

import json

import h5py
import numpy as np
import rasterio
from rasterio.transform import from_origin

from eii_custodian.publicdata.fetch.receipts import (
    cache_directory,
    commit_pair,
    sha256_hex,
    sidecar_for,
)
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.grids.night_lights import FIELD, GROUP

FILE_ATTRIBUTES = "/HDFEOS/ADDITIONAL/FILE_ATTRIBUTES"


def reseal_receipt(cache, row, digest, meta) -> None:
    """Rehash an invented receipt so a test reaches its semantic guards."""
    index = cache / row.key / "index" / f"{digest}.json"
    value = json.loads(index.read_text(encoding="utf-8"))
    value["receipt_sha256"] = sha256_hex(meta.read_bytes())
    index.write_text(json.dumps(value), encoding="utf-8")


def write_night_root(source) -> None:
    """Write the four product attributes on the file root as byte strings.

    The real monthly file stores ``ShortName``, ``VersionID``, ``StartTime`` and
    ``LocalGranuleID`` on ``/``. ``/HDFEOS/ADDITIONAL/FILE_ATTRIBUTES`` exists and
    is empty.
    """
    source.attrs["ShortName"] = np.bytes_(b"VNP46A3")
    source.attrs["VersionID"] = np.bytes_(b"002")
    source.attrs["StartTime"] = np.bytes_(b"2024-01-01 00:00:00")
    source.attrs["LocalGranuleID"] = np.bytes_(b"VNP46A3.A2024001.h23v06.002.SYN.h5")
    source.create_group(FILE_ATTRIBUTES)


def write_scale_offset(
    dataset,
    fill: float = -999.9,
    scale: float = 1.0,
    offset: float = 0.0,
    offset_name: str = "offset",
) -> None:
    """Store fill, scale and offset as numeric arrays of one element."""
    dataset.attrs["_FillValue"] = np.array([np.float32(fill)])
    dataset.attrs["scale_factor"] = np.array([scale], dtype="float64")
    dataset.attrs[offset_name] = np.array([offset], dtype="float64")


def night_file(path, offset_name="offset"):
    with h5py.File(path, "w") as source:
        write_night_root(source)
        fields = source.create_group(GROUP)
        fields.create_dataset("lat", data=np.array([0.5], dtype="float64"))
        fields.create_dataset(
            "lon", data=np.array([0.1, 0.2, 0.3, 1.5, 2.5, 3.5], dtype="float64")
        )
        data = fields.create_dataset(
            FIELD, data=np.array([[2, 4, 6, -999.9, 8, 0]], dtype="float32")
        )
        write_scale_offset(data, scale=1.0, offset=2.0, offset_name=offset_name)
        fields.create_dataset(
            FIELD + "_Quality", data=np.array([[0, 1, 2, 255, 0, 0]], dtype="uint8")
        )
    return path


def checksummed_night_file(path, chunks, damaged_chunk):
    """Write a 4 by 3 invented grid and flip one checksummed radiance chunk.

    Values run 0..11 in row-major order, with scale 0.1, offset 0 and fill
    -999.9. Quality is 0. Latitude centres are 0.5, 1.5, 2.5 and 3.5.
    Longitude centres are 0.1, 0.2 and 0.3. Radiance and quality are stored
    in the given chunks with the fletcher32 filter. ``damaged_chunk`` is the
    radiance chunk coordinate whose first stored byte is flipped.

    A planted file the product does not ship: the product stores radiance with
    gzip and no checksum filter, and its latitude descends. This file keeps an
    ascending latitude so a window can stop before a damaged chunk.
    """
    with h5py.File(path, "w") as source:
        write_night_root(source)
        fields = source.create_group(GROUP)
        fields.create_dataset(
            "lat", data=np.array([0.5, 1.5, 2.5, 3.5], dtype="float64")
        )
        fields.create_dataset("lon", data=np.array([0.1, 0.2, 0.3], dtype="float64"))
        data = fields.create_dataset(
            FIELD,
            data=np.arange(12, dtype="float32").reshape(4, 3),
            chunks=chunks,
            fletcher32=True,
        )
        write_scale_offset(data, scale=0.1, offset=0.0)
        fields.create_dataset(
            FIELD + "_Quality",
            data=np.zeros((4, 3), dtype="uint8"),
            chunks=chunks,
            fletcher32=True,
        )
    with h5py.File(path, "r") as source:
        stored = source[GROUP + FIELD].id.get_chunk_info_by_coord(damaged_chunk)
        offset = stored.byte_offset
    raw = bytearray(path.read_bytes())
    raw[offset] ^= 0xFF
    path.write_bytes(raw)
    return path


def weather_point(key="weather_openmeteo/2024-2025/point"):
    """Return one invented hourly weather row."""
    return entry(
        "weather_openmeteo",
        key,
        extension="json",
        licence_basis="provider_terms",
        url="https://archive-api.open-meteo.com/v1/archive?latitude=1&longitude=2",
        fetch_host="archive-api.open-meteo.com",
        period_first="2024-01-01T00:00",
        period_last="2024-01-01T01:00",
        point=(1.0, 2.0),
        variables=("temperature_2m",),
        cache_role="generator_input",
    )


def population_file(path):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=2,
        height=1,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(0, 1, 1 / 1200, 1 / 1200),
        nodata=-99999,
        compress="LZW",
        tiled=True,
        blockxsize=512,
        blockysize=512,
        BIGTIFF="YES",
    ) as target:
        target.write(np.array([[10.4, -99999]], dtype="float32"), 1)
    return path


def entry(source_id, key, **overrides):
    """Return an invented registry row of one of the three S2-T14 sources."""
    fields = {
        "key": key,
        "source_id": source_id,
        "slug": "",
        "kind": "https_file",
        "title_en": "Invented S2-T14 row",
        "publisher": "SYN-publisher",
        "licence_id": "CC-BY-4.0",
        "licence_basis": "dataset",
        "decision_record": "",
        "fetch_host": "data.worldpop.org",
        "url": "https://data.worldpop.org/SYN/qat_f_25_2025_SYN.tif",
        "terms_url": "",
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
        "extension": "tif",
        "landing_url": "",
        "terms_words": "invented terms words",
        "terms_read_on": "2026-01-01",
    }
    fields.update(overrides)
    return Entry(**fields)


def store(cache, row, body, publisher="SYN-publisher"):
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
    pins_path = cache / "snapshot_pins.json"
    pins = (
        json.loads(pins_path.read_text(encoding="utf-8")) if pins_path.exists() else {}
    )
    pins[row.key] = digest
    pins_path.write_text(json.dumps(pins), encoding="utf-8")
    return digest
