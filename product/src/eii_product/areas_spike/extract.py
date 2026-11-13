"""Encode the invented JSON roads as a minimal zlib OSM PBF, without packages.

Only HeaderBlock, StringTable, PrimitiveBlock, Node and Way are emitted.
The identifiers are local sequence positions, never real OSM identifiers.
"""

import struct
import zlib
from pathlib import Path

from .road import load_road


def varint(value: int) -> bytes:
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def integer(field: int, value: int) -> bytes:
    return varint(field << 3) + varint(value)


def signed(value: int) -> int:
    return value * 2 if value >= 0 else -value * 2 - 1


def message(field: int, value: bytes) -> bytes:
    return varint((field << 3) | 2) + varint(len(value)) + value


def block(kind: str, payload: bytes) -> bytes:
    blob = integer(2, len(payload)) + message(3, zlib.compress(payload))
    header = message(1, kind.encode()) + integer(3, len(blob))
    return struct.pack(">I", len(header)) + header + blob


def generate(path: Path, factor: float = 1.0) -> bytes:
    road = load_road(path)
    strings = ["", "highway", "residential", "maxspeed", "name"]
    nodes = {node["id"]: index for index, node in enumerate(road["nodes"], 1)}
    primitives = bytearray()
    for node in road["nodes"]:
        encoded = integer(1, signed(nodes[node["id"]]))
        encoded += integer(8, signed(round(node["lat"] * 10**7)))
        encoded += integer(9, signed(round(node["lon"] * 10**7)))
        primitives.extend(message(1, encoded))
    for index, edge in enumerate(road["edges"], 1):
        speed = format(edge["drive_kph"] * factor, "g")
        strings.extend((speed, f"SYN-WAY-{index}"))
        encoded = integer(1, index)
        encoded += message(2, b"".join(varint(key) for key in (1, 3, 4)))
        encoded += message(
            3,
            b"".join(
                varint(value) for value in (2, len(strings) - 2, len(strings) - 1)
            ),
        )
        start, end = nodes[edge["source"]], nodes[edge["target"]]
        encoded += message(8, varint(signed(start)) + varint(signed(end - start)))
        primitives.extend(message(3, encoded))
    string_table = b"".join(message(1, value.encode()) for value in strings)
    data = message(1, string_table) + message(2, bytes(primitives))
    header = message(4, b"OsmSchema-V0.6") + message(16, b"SYN-EII-fixture")
    return block("OSMHeader", header) + block("OSMData", data)
