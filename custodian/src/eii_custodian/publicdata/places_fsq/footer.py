"""Parquet footer reader for the copy's summary file.

The summary names each data file on the column chunk and stores coordinate
statistics there. The geographic bbox in the file's own metadata is read so
callers can show they did not use it. The reader never opens a data file.
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass, replace

from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError

MAX_METADATA_DEPTH = 64

_MAGIC = b"PAR1"
_STOP = 0
_TRUE = 1
_FALSE = 2
_BYTE = 3
_I16 = 4
_I32 = 5
_I64 = 6
_DOUBLE = 7
_BINARY = 8
_LIST = 9
_SET = 10
_MAP = 11
_STRUCT = 12
_SHORT_LIST = 14
_TYPE_DOUBLE = 5
_REP_REQUIRED = 0
_REP_OPTIONAL = 1
_PLAIN = 0
_UNCOMPRESSED = 0


@dataclass(frozen=True)
class ChunkStat:
    """One column of one row group, with the file the summary says it belongs to."""

    file_path: str
    path: tuple[str, ...]
    minimum: float | None
    maximum: float | None
    geo_bbox: tuple[float, float, float, float] | None
    deprecated_minimum: float | None = None
    deprecated_maximum: float | None = None


@dataclass(frozen=True)
class SummaryFooter:
    """Row groups of a summary file, and the dataset bbox that selection ignores."""

    row_groups: tuple[tuple[ChunkStat, ...], ...]
    dataset_geo_bbox: tuple[float, float, float, float] | None


def read_summary(body: bytes) -> SummaryFooter:
    """Read coordinate statistics and file names from a Parquet footer."""
    footer = _footer_bytes(body)
    try:
        return _FileReader(footer).file_metadata()
    except RecursionError as exc:
        raise PlacesFsqError("metadata_unreadable") from exc


def metadata_bytes(
    groups: tuple[dict[str, object], ...] | list[dict[str, object]],
    *,
    dataset_geo_bbox: tuple[float, float, float, float] | None,
    column_orders: tuple[int, ...] | None = (1, 1),
    deprecated_bounds: bool = False,
) -> bytes:
    """Build a summary footer. Each group is one row group of one data file."""
    writer = _Writer()
    writer.column_orders = column_orders
    writer.deprecated_bounds = deprecated_bounds
    writer.file_metadata(tuple(groups), dataset_geo_bbox)
    footer = bytes(writer.buffer)
    return _MAGIC + footer + struct.pack("<I", len(footer)) + _MAGIC


def _footer_bytes(body: bytes) -> bytes:
    if len(body) < 12 or body[:4] != _MAGIC or body[-4:] != _MAGIC:
        raise PlacesFsqError("metadata_unreadable")
    length = struct.unpack_from("<I", body, len(body) - 8)[0]
    start = len(body) - 8 - length
    if length < 1 or start < 4:
        raise PlacesFsqError("metadata_unreadable")
    return body[start : len(body) - 8]


def _bbox_from_geo(text: str) -> tuple[float, float, float, float] | None:
    try:
        loaded = json.loads(text)
    except (json.JSONDecodeError, RecursionError):
        return None
    if not isinstance(loaded, dict):
        return None
    columns = loaded.get("columns")
    if isinstance(columns, dict):
        for column in columns.values():
            if isinstance(column, dict) and "bbox" in column:
                return _four(column.get("bbox"))
    if "bbox" in loaded:
        return _four(loaded.get("bbox"))
    return None


def _four(value: object) -> tuple[float, float, float, float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    numbers: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        numbers.append(float(item))
    return (numbers[0], numbers[1], numbers[2], numbers[3])


def _geo_text(bbox: tuple[float, float, float, float]) -> str:
    return json.dumps(
        {"columns": {"geometry": {"bbox": list(bbox)}}},
        separators=(",", ":"),
    )


class _Writer:
    """Compact-protocol writer for the fields this summary uses."""

    def __init__(self) -> None:
        self.column_orders: tuple[int, ...] | None = (1, 1)
        self.deprecated_bounds = False
        self.buffer = bytearray()
        self._last: list[int] = []

    def file_metadata(
        self,
        groups: tuple[dict[str, object], ...],
        dataset_geo_bbox: tuple[float, float, float, float] | None,
    ) -> None:
        self._begin()
        self._i32(1, 1)
        self._field(2, _LIST)
        self._list_header(_STRUCT, 3)
        self._schema("schema", None, _REP_REQUIRED, 2)
        self._schema("longitude", _TYPE_DOUBLE, _REP_OPTIONAL, None)
        self._schema("latitude", _TYPE_DOUBLE, _REP_OPTIONAL, None)
        self._i64(3, len(groups))
        self._field(4, _LIST)
        self._list_header(_STRUCT, len(groups))
        for group in groups:
            self._row_group(group)
        if dataset_geo_bbox is not None:
            self._field(5, _LIST)
            self._list_header(_STRUCT, 1)
            self._key_value("geo", _geo_text(dataset_geo_bbox))
        self._binary(6, b"places_fsq summary")
        if self.column_orders is not None:
            self._field(7, _LIST)
            self._list_header(_STRUCT, len(self.column_orders))
            for member in self.column_orders:
                self._begin()
                self._field(member, _STRUCT)
                self._begin()
                self._end()
                self._end()
        self._end()

    def _schema(
        self, name: str, kind: int | None, repetition: int, children: int | None
    ) -> None:
        self._begin()
        if kind is not None:
            self._i32(1, kind)
        self._i32(3, repetition)
        self._binary(4, name.encode())
        if children is not None:
            self._i32(5, children)
        self._end()

    def _row_group(self, group: dict[str, object]) -> None:
        file_path = group["file_path"]
        longitude = group["longitude"]
        latitude = group["latitude"]
        geo = group.get("geo_bbox")
        if not isinstance(file_path, str):
            raise PlacesFsqError("metadata_unreadable")
        longitude_pair = _require_pair(longitude)
        latitude_pair = _require_pair(latitude)
        bbox = geo if isinstance(geo, tuple) else None
        self._begin()
        self._field(1, _LIST)
        self._list_header(_STRUCT, 2)
        self._chunk(file_path, ("longitude",), longitude_pair, bbox, omit_stats=False)
        self._chunk(
            file_path,
            ("latitude",),
            latitude_pair,
            None,
            omit_stats=group.get("omit_latitude_stats") is True,
        )
        self._i64(2, 2)
        self._i64(3, 1)
        self._end()

    def _chunk(
        self,
        file_path: str,
        path: tuple[str, ...],
        bounds: tuple[float, float],
        geo_bbox: tuple[float, float, float, float] | None,
        *,
        omit_stats: bool,
    ) -> None:
        self._begin()
        self._binary(1, file_path.encode())
        self._i64(2, 0)
        self._field(3, _STRUCT)
        self._column(path, bounds, geo_bbox, omit_stats=omit_stats)
        self._end()

    def _column(
        self,
        path: tuple[str, ...],
        bounds: tuple[float, float],
        geo_bbox: tuple[float, float, float, float] | None,
        *,
        omit_stats: bool,
    ) -> None:
        self._begin()
        self._i32(1, _TYPE_DOUBLE)
        self._field(2, _LIST)
        self._list_header(_I32, 1)
        self._zigzag(self.buffer, _PLAIN)
        self._field(3, _LIST)
        self._list_header(_BINARY, len(path))
        for part in path:
            self._raw_binary(part.encode())
        self._i32(4, _UNCOMPRESSED)
        self._i64(5, 1)
        self._i64(6, 0)
        self._i64(7, 0)
        if geo_bbox is not None:
            self._field(8, _LIST)
            self._list_header(_STRUCT, 1)
            self._key_value("geo", _geo_text(geo_bbox))
        self._i64(9, 0)
        if not omit_stats:
            self._field(12, _STRUCT)
            self._statistics(bounds)
        self._end()

    def _statistics(self, bounds: tuple[float, float]) -> None:
        low = struct.pack("<d", bounds[0])
        high = struct.pack("<d", bounds[1])
        self._begin()
        if self.deprecated_bounds:
            self._binary(1, high)
            self._binary(2, low)
        self._binary(5, high)
        self._binary(6, low)
        self._end()

    def _key_value(self, key: str, value: str) -> None:
        self._begin()
        self._binary(1, key.encode())
        self._binary(2, value.encode())
        self._end()

    def _begin(self) -> None:
        self._last.append(0)

    def _end(self) -> None:
        self.buffer.append(_STOP)
        self._last.pop()

    def _field(self, field_id: int, kind: int) -> None:
        delta = field_id - self._last[-1]
        if 0 < delta <= 15:
            self.buffer.append((delta << 4) | kind)
        else:
            self.buffer.append(kind)
            self._zigzag(self.buffer, field_id)
        self._last[-1] = field_id

    def _i32(self, field_id: int, value: int) -> None:
        self._field(field_id, _I32)
        self._zigzag(self.buffer, value)

    def _i64(self, field_id: int, value: int) -> None:
        self._field(field_id, _I64)
        self._zigzag(self.buffer, value)

    def _binary(self, field_id: int, value: bytes) -> None:
        self._field(field_id, _BINARY)
        self._raw_binary(value)

    def _raw_binary(self, value: bytes) -> None:
        _uvarint(self.buffer, len(value))
        self.buffer.extend(value)

    def _list_header(self, element: int, size: int) -> None:
        if size <= _SHORT_LIST:
            self.buffer.append((size << 4) | element)
            return
        self.buffer.append(0xF0 | element)
        _uvarint(self.buffer, size)

    @staticmethod
    def _zigzag(buffer: bytearray, value: int) -> None:
        _uvarint(buffer, (value << 1) ^ (value >> 63))


def _pair(value: object) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and all(
            isinstance(item, (int, float)) and not isinstance(item, bool)
            for item in value
        )
    )


def _require_pair(value: object) -> tuple[float, float]:
    if not _pair(value):
        raise PlacesFsqError("metadata_unreadable")
    assert isinstance(value, tuple)
    return (float(value[0]), float(value[1]))


def _uvarint(buffer: bytearray, value: int) -> None:
    number = value & ((1 << 64) - 1) if value < 0 else value
    while True:
        byte = number & 0x7F
        number >>= 7
        if number:
            buffer.append(byte | 0x80)
        else:
            buffer.append(byte)
            return


class _FileReader:
    """Compact-protocol reader. Unknown fields are skipped."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._at = 0
        self._last: list[int] = []
        self._container_depth = 0

    def file_metadata(self) -> SummaryFooter:
        self._begin()
        groups: list[tuple[ChunkStat | None, ...]] = []
        orders: tuple[bool, ...] | None = None
        dataset: tuple[float, float, float, float] | None = None
        while True:
            kind, field_id = self._header()
            if kind is None:
                break
            if field_id == 4 and kind == _LIST:
                groups = self._row_groups()
            elif field_id == 5 and kind == _LIST:
                dataset = self._dataset_geo()
            elif field_id == 7 and kind == _LIST:
                orders = self._column_orders()
            else:
                self._skip(kind)
        resolved = []
        for group in groups:
            columns = []
            for index, chunk in enumerate(group):
                if chunk is None:
                    continue
                if orders is None or len(orders) != len(group) or not orders[index]:
                    chunk = replace(
                        chunk,
                        minimum=chunk.deprecated_minimum,
                        maximum=chunk.deprecated_maximum,
                    )
                columns.append(chunk)
            resolved.append(tuple(columns))
        return SummaryFooter(tuple(resolved), dataset)

    def _column_orders(self) -> tuple[bool, ...]:
        self._enter_container()
        try:
            size, element = self._list_header()
            orders = []
            for _ in range(size):
                members = []
                if element == _STRUCT:
                    self._begin()
                    while True:
                        kind, field_id = self._header()
                        if kind is None:
                            break
                        members.append((field_id, kind))
                        self._skip(kind)
                else:
                    self._skip_element(element)
                orders.append(members == [(1, _STRUCT)])
            return tuple(orders)
        finally:
            self._container_depth -= 1

    def _row_groups(self) -> list[tuple[ChunkStat | None, ...]]:
        self._enter_container()
        try:
            size, element = self._list_header()
            found: list[tuple[ChunkStat | None, ...]] = []
            for _ in range(size):
                if element != _STRUCT:
                    self._skip_element(element)
                    continue
                found.append(self._row_group())
            return found
        finally:
            self._container_depth -= 1

    def _row_group(self) -> tuple[ChunkStat | None, ...]:
        self._begin()
        chunks: tuple[ChunkStat | None, ...] = ()
        while True:
            kind, field_id = self._header()
            if kind is None:
                break
            if field_id == 1 and kind == _LIST:
                chunks = self._chunks()
            else:
                self._skip(kind)
        return chunks

    def _chunks(self) -> tuple[ChunkStat | None, ...]:
        self._enter_container()
        try:
            size, element = self._list_header()
            found: list[ChunkStat | None] = []
            for _ in range(size):
                if element != _STRUCT:
                    self._skip_element(element)
                    found.append(None)
                    continue
                found.append(self._chunk())
            return tuple(found)
        finally:
            self._container_depth -= 1

    def _chunk(self) -> ChunkStat | None:
        self._begin()
        file_path = ""
        meta: (
            tuple[
                tuple[str, ...],
                float | None,
                float | None,
                tuple[float, float, float, float] | None,
                float | None,
                float | None,
            ]
            | None
        ) = None
        while True:
            kind, field_id = self._header()
            if kind is None:
                break
            if field_id == 1 and kind == _BINARY:
                file_path = self._bytes().decode("utf-8", "replace")
            elif field_id == 3 and kind == _STRUCT:
                meta = self._column()
            else:
                self._skip(kind)
        if meta is None:
            return None
        path, low, high, geo, plain_low, plain_high = meta
        return ChunkStat(file_path, path, low, high, geo, plain_low, plain_high)

    def _column(
        self,
    ) -> tuple[
        tuple[str, ...],
        float | None,
        float | None,
        tuple[float, float, float, float] | None,
        float | None,
        float | None,
    ]:
        self._begin()
        path: tuple[str, ...] = ()
        kind_code: int | None = None
        geo: tuple[float, float, float, float] | None = None
        low: float | None = None
        high: float | None = None
        plain_low: float | None = None
        plain_high: float | None = None
        while True:
            kind, field_id = self._header()
            if kind is None:
                break
            if field_id == 1 and kind == _I32:
                kind_code = _unzigzag(self._varint())
            elif field_id == 3 and kind == _LIST:
                path = self._path()
            elif field_id == 8 and kind == _LIST:
                geo = self._geo_pairs()
            elif field_id == 12 and kind == _STRUCT:
                low, high, plain_low, plain_high = self._statistics(kind_code)
            else:
                self._skip(kind)
        return path, low, high, geo, plain_low, plain_high

    def _path(self) -> tuple[str, ...]:
        self._enter_container()
        try:
            size, element = self._list_header()
            parts: list[str] = []
            for _ in range(size):
                if element == _BINARY:
                    parts.append(self._bytes().decode("utf-8", "replace"))
                else:
                    self._skip_element(element)
            return tuple(parts)
        finally:
            self._container_depth -= 1

    def _geo_pairs(self) -> tuple[float, float, float, float] | None:
        self._enter_container()
        try:
            size, element = self._list_header()
            found: tuple[float, float, float, float] | None = None
            for _ in range(size):
                if element != _STRUCT:
                    self._skip_element(element)
                    continue
                key, value = self._pair()
                if key == "geo" and value is not None:
                    parsed = _bbox_from_geo(value)
                    if parsed is not None:
                        found = parsed
            return found
        finally:
            self._container_depth -= 1

    def _dataset_geo(self) -> tuple[float, float, float, float] | None:
        return self._geo_pairs()

    def _pair(self) -> tuple[str, str | None]:
        self._begin()
        key = ""
        value: str | None = None
        while True:
            kind, field_id = self._header()
            if kind is None:
                break
            if field_id == 1 and kind == _BINARY:
                key = self._bytes().decode("utf-8", "replace")
            elif field_id == 2 and kind == _BINARY:
                value = self._bytes().decode("utf-8", "replace")
            else:
                self._skip(kind)
        return key, value

    def _statistics(
        self, kind_code: int | None
    ) -> tuple[float | None, float | None, float | None, float | None]:
        self._begin()
        plain_min: bytes | None = None
        plain_max: bytes | None = None
        value_min: bytes | None = None
        value_max: bytes | None = None
        while True:
            kind, field_id = self._header()
            if kind is None:
                break
            if kind == _BINARY and field_id == 1:
                plain_max = self._bytes()
            elif kind == _BINARY and field_id == 2:
                plain_min = self._bytes()
            elif kind == _BINARY and field_id == 5:
                value_max = self._bytes()
            elif kind == _BINARY and field_id == 6:
                value_min = self._bytes()
            else:
                self._skip(kind)
        low = value_min if value_min is not None else plain_min
        high = value_max if value_max is not None else plain_max
        return (
            _float(low, kind_code),
            _float(high, kind_code),
            _float(plain_min, kind_code),
            _float(plain_max, kind_code),
        )

    def _begin(self) -> None:
        if len(self._last) + self._container_depth >= MAX_METADATA_DEPTH:
            raise PlacesFsqError("metadata_unreadable")
        self._last.append(0)

    def _header(self) -> tuple[int | None, int]:
        byte = self._take(1)[0]
        if byte == _STOP:
            self._last.pop()
            return None, 0
        kind = byte & 0x0F
        delta = byte >> 4
        if delta:
            field_id = self._last[-1] + delta
        else:
            field_id = _unzigzag(self._varint())
        self._last[-1] = field_id
        return kind, field_id

    def _list_header(self) -> tuple[int, int]:
        byte = self._take(1)[0]
        size = byte >> 4
        element = byte & 0x0F
        if size == 15:
            size = self._varint()
        self._check_size(size)
        return size, element

    def _check_size(self, size: int) -> None:
        if size > len(self._payload) - self._at:
            raise PlacesFsqError("metadata_unreadable")

    def _skip_element(self, kind: int) -> None:
        if kind in (_TRUE, _FALSE):
            self._take(1)
        else:
            self._skip(kind)

    def _bytes(self) -> bytes:
        size = self._varint()
        return self._take(size)

    def _varint(self) -> int:
        shift = 0
        number = 0
        while True:
            byte = self._take(1)[0]
            number |= (byte & 0x7F) << shift
            if byte < 0x80:
                return number
            shift += 7
            if shift > 70:
                raise PlacesFsqError("metadata_unreadable")

    def _take(self, size: int) -> bytes:
        end = self._at + size
        if size < 0 or end > len(self._payload):
            raise PlacesFsqError("metadata_unreadable")
        chunk = self._payload[self._at : end]
        self._at = end
        return chunk

    def _enter_container(self) -> None:
        if len(self._last) + self._container_depth >= MAX_METADATA_DEPTH:
            raise PlacesFsqError("metadata_unreadable")
        self._container_depth += 1

    def _skip(self, kind: int) -> None:
        if kind in (_LIST, _SET, _MAP):
            self._enter_container()
            try:
                self._skip_value(kind)
            finally:
                self._container_depth -= 1
        else:
            self._skip_value(kind)

    def _skip_value(self, kind: int) -> None:
        if kind in (_TRUE, _FALSE):
            return
        if kind == _BYTE:
            self._take(1)
            return
        if kind in (_I16, _I32, _I64):
            self._varint()
            return
        if kind == _DOUBLE:
            self._take(8)
            return
        if kind == _BINARY:
            self._bytes()
            return
        if kind in (_LIST, _SET):
            size, element = self._list_header()
            for _ in range(size):
                self._skip_element(element)
            return
        if kind == _MAP:
            size = self._varint()
            self._check_size(size)
            if size == 0:
                return
            types = self._take(1)[0]
            key = types >> 4
            value = types & 0x0F
            for _ in range(size):
                self._skip_element(key)
                self._skip_element(value)
            return
        if kind == _STRUCT:
            self._begin()
            while True:
                inner, _field = self._header()
                if inner is None:
                    return
                self._skip(inner)
            return
        raise PlacesFsqError("metadata_unreadable")


def _float(payload: bytes | None, kind_code: int | None) -> float | None:
    if payload is None or kind_code != _TYPE_DOUBLE or len(payload) != 8:
        return None
    value = float(struct.unpack("<d", payload)[0])
    return None if math.isnan(value) else value


def _unzigzag(number: int) -> int:
    return (number >> 1) ^ -(number & 1)
