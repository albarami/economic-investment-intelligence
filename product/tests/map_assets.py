"""Invented offline map assets for tests.

Generates a minimal PMTiles version-3 archive whose vector tiles hold
invented geometry and invented bilingual names, plus glyph ``.pbf``
files for the closed font stack the basemap style requests. Every byte
is deterministic and invented: no real extract, tile, glyph or name.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

# Invented asset names (closed inventory of the test mount).
ARCHIVE_NAME = "basemap.pmtiles"
FONT_STACK = "Noto Sans Medium"

# Invented names in the style of the glyph-spike fixtures.
NAME_EN = "Waw Test Emirate"
NAME_AR = "إمارة الاختبار واو"

# Invented point near the glyph spike's synthetic scene.
CENTER_LON = 0.015
CENTER_LAT = 0.015
CENTER_ZOOM = 6
MAX_ZOOM = 8

# Closed set of glyph range files the mounted font stack holds. Each
# file covers one aligned 256-codepoint block named by its first codepoint.
GLYPH_RANGES = (
    (0, 255),
    (1536, 1791),
    (1792, 2047),
    (8192, 8447),
    (64256, 64511),
    (64512, 64767),
    (65024, 65279),
    (65280, 65535),
)

GLYPH_MIME = "application/x-protobuf"
ARCHIVE_MIME = "application/octet-stream"


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _zigzag(value: int) -> int:
    return (value << 1) ^ (value >> 31)


def _tag(field: int, wire: int) -> bytes:
    return _varint((field << 3) | wire)


def _uint(field: int, value: int) -> bytes:
    return _tag(field, 0) + _varint(value)


def _sint(field: int, value: int) -> bytes:
    return _tag(field, 0) + _varint(_zigzag(value))


def _string(field: int, text: str) -> bytes:
    data = text.encode("utf-8")
    return _tag(field, 2) + _varint(len(data)) + data


def _bytes(field: int, data: bytes) -> bytes:
    return _tag(field, 2) + _varint(len(data)) + data


def _mvt_value(value: object) -> bytes:
    if isinstance(value, str):
        return _string(1, value)
    if isinstance(value, bool):
        return _uint(7, int(value))
    if isinstance(value, int):
        return _uint(4, value) if value >= 0 else _sint(6, value)
    raise TypeError(f"unsupported tag value {value!r}")


def _mvt_feature(
    fid: int,
    tags: dict[str, object],
    geom_type: int,
    commands: list[tuple[int, list[tuple[int, int]]]],
    keys: list[str],
    values: list[object],
) -> bytes:
    packed_tags = bytearray()
    for key, value in tags.items():
        packed_tags += _varint(keys.index(key))
        packed_tags += _varint(values.index(value))
    geometry = bytearray()
    px = py = 0
    for command, points in commands:
        geometry += _varint((len(points) << 3) | command)
        for x, y in points:
            geometry += _varint(_zigzag(x - px))
            geometry += _varint(_zigzag(y - py))
            px, py = x, y
    return (
        _uint(1, fid)
        + _bytes(2, bytes(packed_tags))
        + _uint(3, geom_type)
        + _bytes(4, bytes(geometry))
    )


def _mvt_layer(
    name: str,
    features: list[tuple[int, dict[str, object], int, list]],
    extent: int = 4096,
) -> bytes:
    keys: list[str] = []
    values: list[object] = []
    for _, tags, _, _ in features:
        for key, value in tags.items():
            if key not in keys:
                keys.append(key)
            if value not in values:
                values.append(value)
    body = _uint(15, 2) + _string(1, name)
    for fid, tags, geom_type, commands in features:
        body += _bytes(2, _mvt_feature(fid, tags, geom_type, commands, keys, values))
    for key in keys:
        body += _string(3, key)
    for value in values:
        body += _bytes(4, _mvt_value(value))
    body += _uint(5, extent)
    return body


def _mvt_tile() -> bytes:
    # One invented land polygon covering the whole tile extent and one
    # invented country label point at its centre.
    earth = _mvt_layer(
        "earth",
        [
            (
                1,
                {"kind": "earth"},
                3,
                [
                    (1, [(0, 0)]),
                    (2, [(4096, 0), (4096, 4096), (0, 4096)]),
                    (7, [(0, 0)]),
                ],
            )
        ],
    )
    places = _mvt_layer(
        "places",
        [
            (
                2,
                {
                    "kind": "country",
                    "name": NAME_EN,
                    "name:en": NAME_EN,
                    "name:ar": NAME_AR,
                    "script": "Latin",
                    "population_rank": 3,
                    "min_zoom": 0,
                    "sort_key": 3,
                },
                1,
                [(1, [(2048, 2048)])],
            )
        ],
    )
    return _bytes(3, earth) + _bytes(3, places)


def zxy_to_tile_id(z: int, x: int, y: int) -> int:
    """Hilbert tile id, mirroring the pinned pmtiles package."""
    acc = ((1 << z) * (1 << z) - 1) // 3
    a = z - 1
    tx, ty = x, y
    s = 1 << a if a >= 0 else 0
    while s > 0:
        rx = tx & s
        ry = ty & s
        acc += ((3 * rx) ^ ry) * (1 << a)
        if ry == 0:
            tx, ty = (s - 1 - ty, s - 1 - tx) if rx else (ty, tx)
        a -= 1
        s >>= 1
    return acc


def _tile_xy(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 1 << z
    x = min(n - 1, max(0, int((lon + 180.0) / 360.0 * n)))
    lat_r = math.radians(lat)
    y = min(
        n - 1,
        max(
            0,
            int(
                (1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi)
                / 2.0
                * n
            ),
        ),
    )
    return x, y


def _pmtiles_entry_stream(entries: list[tuple[int, int, int, int]]) -> bytes:
    """Serialise directory entries (tile_id, offset, length, run_length)."""
    out = _varint(len(entries))
    last = 0
    for tile_id, _, _, _ in entries:
        out += _varint(tile_id - last)
        last = tile_id
    for _, _, _, run in entries:
        out += _varint(run)
    for _, _, length, _ in entries:
        out += _varint(length)
    for index, (_, offset, _, _) in enumerate(entries):
        out += _varint(
            0
            if index and offset == entries[index - 1][1] + entries[index - 1][2]
            else offset + 1
        )
    return out


def build_archive() -> bytes:
    """One invented PMTiles archive: header, root dir, metadata, tiles."""
    tiles: list[tuple[int, int, int, bytes]] = []
    for z in range(0, MAX_ZOOM + 1):
        x, y = _tile_xy(CENTER_LON, CENTER_LAT, z)
        tiles.append((z, x, y, _mvt_tile()))
    entries = sorted((zxy_to_tile_id(z, x, y), payload) for z, x, y, payload in tiles)

    tile_data = b""
    directory: list[tuple[int, int, int, int]] = []
    for tile_id, payload in entries:
        directory.append((tile_id, len(tile_data), len(payload), 1))
        tile_data += payload

    metadata = json.dumps(
        {
            "name": "invented-test-extract",
            "format": "pbf",
            "vector_layers": [
                {"id": "earth", "fields": {}},
                {"id": "places", "fields": {}},
            ],
        },
        sort_keys=True,
    ).encode("utf-8")

    header_len = 127
    root_offset = header_len
    root = _pmtiles_entry_stream(directory)
    metadata_offset = root_offset + len(root)
    data_offset = metadata_offset + len(metadata)

    header = bytearray(header_len)
    header[0:7] = b"PMTiles"
    header[7] = 3
    struct.pack_into("<Q", header, 8, root_offset)
    struct.pack_into("<Q", header, 16, len(root))
    struct.pack_into("<Q", header, 24, metadata_offset)
    struct.pack_into("<Q", header, 32, len(metadata))
    struct.pack_into("<Q", header, 40, data_offset + len(tile_data))
    struct.pack_into("<Q", header, 48, 0)
    struct.pack_into("<Q", header, 56, data_offset)
    struct.pack_into("<Q", header, 64, len(tile_data))
    struct.pack_into("<Q", header, 72, len(directory))
    struct.pack_into("<Q", header, 80, len(directory))
    struct.pack_into("<Q", header, 88, len(directory))
    header[96] = 1  # clustered
    header[97] = 1  # internal compression: none
    header[98] = 1  # tile compression: none
    header[99] = 1  # tile type: mvt
    header[100] = 0
    header[101] = MAX_ZOOM
    span = 0.04
    struct.pack_into("<i", header, 102, int((CENTER_LON - span) * 1e7))
    struct.pack_into("<i", header, 106, int((CENTER_LAT - span) * 1e7))
    struct.pack_into("<i", header, 110, int((CENTER_LON + span) * 1e7))
    struct.pack_into("<i", header, 114, int((CENTER_LAT + span) * 1e7))
    header[118] = CENTER_ZOOM
    struct.pack_into("<i", header, 119, int(CENTER_LON * 1e7))
    struct.pack_into("<i", header, 123, int(CENTER_LAT * 1e7))
    return bytes(header) + root + metadata + tile_data


def glyph_pbf(fontstack: str, start: int, end: int) -> bytes:
    """One invented glyph range: a tiny uniform bitmap per codepoint."""
    stack = _string(1, fontstack) + _string(2, f"{start}-{end}")
    for code in range(start, end + 1):
        bitmap = bytes((0xFF if (i // 12) % 2 == i % 2 else 0x20) for i in range(144))
        glyph = (
            _uint(1, code)
            + _bytes(2, bitmap)
            + _uint(3, 6)
            + _uint(4, 6)
            + _sint(5, 0)
            + _sint(6, 7)
            + _uint(7, 7)
        )
        stack += _bytes(3, glyph)
    return _bytes(1, stack)


def write_assets(tile_dir: Path, font_dir: Path) -> dict[str, object]:
    """Write the invented archive and glyph ranges; return the manifest."""
    tile_dir.mkdir(parents=True, exist_ok=True)
    font_dir.mkdir(parents=True, exist_ok=True)
    archive = build_archive()
    (tile_dir / ARCHIVE_NAME).write_bytes(archive)
    stack_dir = font_dir / FONT_STACK
    stack_dir.mkdir(parents=True, exist_ok=True)
    glyphs: dict[str, str] = {}
    for start, end in GLYPH_RANGES:
        name = f"{start}-{end}.pbf"
        payload = glyph_pbf(FONT_STACK, start, end)
        (stack_dir / name).write_bytes(payload)
        glyphs[f"{FONT_STACK}/{name}"] = hashlib.sha256(payload).hexdigest()
    return {
        "archive_name": ARCHIVE_NAME,
        "archive_mime": ARCHIVE_MIME,
        "archive_sha256": hashlib.sha256(archive).hexdigest(),
        "archive_size": len(archive),
        "glyph_mime": GLYPH_MIME,
        "glyph_sha256": glyphs,
        "names": {"en": NAME_EN, "ar": NAME_AR},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tile-dir", type=Path, required=True)
    parser.add_argument("--font-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = write_assets(args.tile_dir, args.font_dir)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
