"""Encode one invented road grid as a minimal OSM PBF. Identifiers are local."""

from __future__ import annotations

import struct
import zlib


def varint(value: int) -> bytes:
    """Encode an unsigned protobuf integer."""
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def integer(field: int, value: int) -> bytes:
    """Encode a protobuf varint field."""
    return varint(field << 3) + varint(value)


def signed(value: int) -> int:
    """Zigzag-encode a signed integer."""
    return value * 2 if value >= 0 else -value * 2 - 1


def message(field: int, value: bytes) -> bytes:
    """Encode a length-delimited protobuf field."""
    return varint((field << 3) | 2) + varint(len(value)) + value


def block(kind: str, payload: bytes) -> bytes:
    """Wrap one OSM PBF blob."""
    blob = integer(2, len(payload)) + message(3, zlib.compress(payload))
    header = message(1, kind.encode()) + integer(3, len(blob))
    return struct.pack(">I", len(header)) + header + blob


def grid_pbf(columns: int = 8, rows: int = 8) -> bytes:
    """A residential grid inside the frame box, named SYN, with no real way id."""
    origin_lon = 51.40
    origin_lat = 25.20
    step_lon = 0.0025
    step_lat = 0.00225
    strings = ["", "highway", "residential", "maxspeed", "40", "name"]
    nodes: list[tuple[int, int]] = []
    primitives = bytearray()
    index = 1
    for row in range(rows):
        for column in range(columns):
            lat = round((origin_lat + row * step_lat) * 10**7)
            lon = round((origin_lon + column * step_lon) * 10**7)
            encoded = integer(1, signed(index))
            encoded += integer(8, signed(lat))
            encoded += integer(9, signed(lon))
            primitives.extend(message(1, encoded))
            nodes.append((column, row))
            index += 1
    way = 1
    for row in range(rows):
        for column in range(columns):
            here = row * columns + column + 1
            neighbours = []
            if column + 1 < columns:
                neighbours.append(here + 1)
            if row + 1 < rows:
                neighbours.append(here + columns)
            for target in neighbours:
                strings.append(f"SYN-WAY-{way}")
                encoded = integer(1, way)
                keys = [1, 3, 5]
                values = [2, 4, len(strings) - 1]
                encoded += message(2, b"".join(varint(key) for key in keys))
                encoded += message(3, b"".join(varint(value) for value in values))
                encoded += message(
                    8, varint(signed(here)) + varint(signed(target - here))
                )
                primitives.extend(message(3, encoded))
                way += 1
    string_table = b"".join(message(1, value.encode()) for value in strings)
    data = message(1, string_table) + message(2, bytes(primitives))
    header = message(4, b"OsmSchema-V0.6") + message(16, b"SYN-EII-places-road")
    return block("OSMHeader", header) + block("OSMData", data)
