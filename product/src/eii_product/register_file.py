"""Read the financial-centre register through its setting only.

The file stays outside the repository. This module opens the path the
setting names, read-only, and prints nothing about the path or the rows.
The file's bytes must hash to the sha256 the loaded release lists (L-1509).
Every read of the file, here and in the release build, goes through
``read_register_bytes``: a regular file, opened without following a symlink.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from eii_core.reasons import reason
from eii_product.config import read_fc_register_file

COLUMN_REGISTRATION_KEY = "registration_key"
COLUMN_ROW_ID = "row_id"
COLUMN_TOWER = "tower_or_building"
COLUMN_POSITION_LON = "position_lon"
COLUMN_POSITION_LAT = "position_lat"
COLUMN_DISTRICT = "district_key"
COLUMN_DISTRICT_FREE_ZONE = "district_free_zone"
COLUMN_CARD = "card"

ROW_COLUMNS = (
    COLUMN_REGISTRATION_KEY,
    COLUMN_ROW_ID,
    COLUMN_TOWER,
    COLUMN_POSITION_LON,
    COLUMN_POSITION_LAT,
    COLUMN_DISTRICT,
    COLUMN_DISTRICT_FREE_ZONE,
    COLUMN_CARD,
)
CARD_FIELDS = ("trade_name", "activity")
_COORDINATE = re.compile(r"-?[0-9]{1,3}\.[0-9]{1,3}")
_ROW_ID = re.compile(r"row-[a-z]+(?:-[a-z]+)*")
_PLACE = re.compile(r"place:.+")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_HASH = re.compile(r"[0-9a-f]{64}")
_OPEN_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


class RegisterRefusal(Exception):
    """The read is refused. The message is a fixed reason, never a path."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class RegisterRow:
    """One invented or register row after the column constant is applied."""

    registration_key: str
    row_id: str
    tower_or_building: str | None
    position: tuple[str, str] | None
    district_key: str | None
    district_free_zone: bool
    card: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class GazetteerPlace:
    """A tower name joined to a ``place:`` code. Coordinates are not used."""

    tower_or_building: str
    place_code: str


@dataclass(frozen=True)
class DistrictGeometry:
    """A supplied district ring. The product does not invent one."""

    district_key: str
    name: str
    ring: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class RegisterBundle:
    """Rows plus the stand-in geography and the chain the route must resolve."""

    rows: tuple[RegisterRow, ...]
    gazetteer: Mapping[str, GazetteerPlace]
    districts: Mapping[str, DistrictGeometry]
    source: Mapping[str, object]
    lineage: Mapping[str, object]
    release_id: str
    year: str


def read_fc_register_rows(
    setting: str | None,
    *,
    listed_sha256: str | None,
    asked_path: str | None = None,
) -> RegisterBundle | None:
    """Read only the freshly configured path; refuse caller substitutions.

    ``listed_sha256`` is the hash the loaded release lists for the file: none
    refuses with ``hash_unlisted`` before the file is opened, and other bytes
    refuse with ``hash_mismatch`` before any row is parsed.
    """
    configured = read_fc_register_file()
    if setting is not None and (type(setting) is not str or setting == ""):
        raise RegisterRefusal("register_setting_invalid")
    if setting != configured:
        raise RegisterRefusal("path_refused")
    if asked_path is not None and asked_path != configured:
        raise RegisterRefusal("path_refused")
    if configured is None:
        return None
    if listed_sha256 is None:
        raise RegisterRefusal("hash_unlisted")
    return _read_path(configured, listed_sha256)


def _signature(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def read_register_bytes(path: str) -> bytes:
    """Return the bytes of the regular file at ``path``, read from one descriptor.

    A symlink as the last component, a FIFO, a device, a directory, a missing
    file, or a file changed or replaced at ``path`` during the read refuses
    with ``read_refused``; the reason carries no path. The descriptor is owned
    from the moment ``os.open`` returns and is closed on every exit.
    """
    try:
        descriptor = os.open(path, _OPEN_FLAGS)
    except (OSError, ValueError):
        raise RegisterRefusal("read_refused") from None
    try:
        return _regular_file_bytes(descriptor, path)
    finally:
        os.close(descriptor)


def _regular_file_bytes(descriptor: int, path: str) -> bytes:
    """Read ``descriptor`` when it is a regular file that is still ``path``.

    The caller owns ``descriptor`` and closes it. The wrapper does not.
    """
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RegisterRefusal("read_refused")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            body = handle.read()
        after = os.fstat(descriptor)
        current = os.stat(path, follow_symlinks=False)
    except OSError:
        raise RegisterRefusal("read_refused") from None
    if _signature(before) != _signature(after) or _signature(after) != (
        _signature(current)
    ):
        raise RegisterRefusal("read_refused")
    return body


def _read_path(path: str, listed_sha256: str) -> RegisterBundle:
    body = read_register_bytes(path)
    if hashlib.sha256(body).hexdigest() != listed_sha256:
        raise RegisterRefusal("hash_mismatch")
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RegisterRefusal(reason(error, "register_json_invalid")) from None
    if type(parsed) is not dict:
        raise RegisterRefusal("register_document_invalid")
    rows = _rows(parsed.get("rows"))
    return RegisterBundle(
        rows=rows,
        gazetteer=_gazetteer(parsed.get("gazetteer")),
        districts=_districts(parsed.get("districts")),
        source=_source(parsed.get("source")),
        lineage=_lineage(parsed.get("lineage")),
        release_id=_hash_text(parsed.get("release_id")),
        year=_year(parsed.get("year")),
    )


def _rows(value: object) -> tuple[RegisterRow, ...]:
    if type(value) is not list or not value:
        raise RegisterRefusal("register_rows_invalid")
    seen: set[str] = set()
    built: list[RegisterRow] = []
    for item in value:
        row = _row(item)
        if row.registration_key in seen or row.row_id in seen:
            raise RegisterRefusal("register_row_duplicate")
        seen.add(row.registration_key)
        seen.add(row.row_id)
        built.append(row)
    return tuple(built)


def _row(value: object) -> RegisterRow:
    if type(value) is not dict:
        raise RegisterRefusal("register_row_invalid")
    if any(key not in ROW_COLUMNS for key in value):
        raise RegisterRefusal("register_column_unknown")
    registration = _token(value.get(COLUMN_REGISTRATION_KEY))
    row_id = value.get(COLUMN_ROW_ID)
    if type(row_id) is not str or _ROW_ID.fullmatch(row_id) is None:
        raise RegisterRefusal("register_row_id_invalid")
    tower = _optional(value.get(COLUMN_TOWER))
    lon = _optional(value.get(COLUMN_POSITION_LON))
    lat = _optional(value.get(COLUMN_POSITION_LAT))
    if (lon is None) != (lat is None):
        raise RegisterRefusal("register_position_incomplete")
    position = None
    if lon is not None and lat is not None:
        if _COORDINATE.fullmatch(lon) is None or _COORDINATE.fullmatch(lat) is None:
            raise RegisterRefusal("register_position_invalid")
        position = (lon, lat)
    district = _optional(value.get(COLUMN_DISTRICT))
    free = value.get(COLUMN_DISTRICT_FREE_ZONE)
    if type(free) is not bool:
        raise RegisterRefusal("register_district_flag_invalid")
    return RegisterRow(
        registration_key=registration,
        row_id=row_id,
        tower_or_building=tower,
        position=position,
        district_key=district,
        district_free_zone=free,
        card=_card(value.get(COLUMN_CARD)),
    )


def _card(value: object) -> tuple[tuple[str, str], ...]:
    if type(value) is not dict or set(value) != set(CARD_FIELDS):
        raise RegisterRefusal("register_card_invalid")
    pairs: list[tuple[str, str]] = []
    for key in CARD_FIELDS:
        text = value[key]
        if type(text) is not str or text.strip() == "" or text != text.strip():
            raise RegisterRefusal("register_card_text_invalid")
        pairs.append((key, text))
    return tuple(pairs)


def _gazetteer(value: object) -> Mapping[str, GazetteerPlace]:
    if type(value) is not list:
        raise RegisterRefusal("register_gazetteer_invalid")
    found: dict[str, GazetteerPlace] = {}
    place_codes: set[str] = set()
    for item in value:
        if type(item) is not dict:
            raise RegisterRefusal("register_gazetteer_row_invalid")
        tower = _token(item.get("tower_or_building"))
        code = item.get("place_code")
        if type(code) is not str or _PLACE.fullmatch(code) is None:
            raise RegisterRefusal("register_place_code_invalid")
        # DAT-93 identifies the count by geography, not by the tower's name.
        # Distinct tower groups must never emit different counts for one code.
        if tower in found or code in place_codes:
            raise RegisterRefusal("register_place_duplicate")
        place_codes.add(code)
        found[tower] = GazetteerPlace(tower_or_building=tower, place_code=code)
    return found


def _districts(value: object) -> Mapping[str, DistrictGeometry]:
    if type(value) is not list:
        raise RegisterRefusal("register_districts_invalid")
    found: dict[str, DistrictGeometry] = {}
    for item in value:
        if type(item) is not dict:
            raise RegisterRefusal("register_district_invalid")
        key = _token(item.get("district_key"))
        name = _token(item.get("name"))
        ring = _ring(item.get("ring"))
        if key in found:
            raise RegisterRefusal("register_district_duplicate")
        found[key] = DistrictGeometry(district_key=key, name=name, ring=ring)
    return found


def _ring(value: object) -> tuple[tuple[str, str], ...]:
    if type(value) is not list or len(value) < 4:
        raise RegisterRefusal("register_ring_invalid")
    points: list[tuple[str, str]] = []
    for item in value:
        if type(item) is not list or len(item) != 2:
            raise RegisterRefusal("register_ring_point_invalid")
        lon, lat = item
        if (
            type(lon) is not str
            or type(lat) is not str
            or _COORDINATE.fullmatch(lon) is None
            or _COORDINATE.fullmatch(lat) is None
        ):
            raise RegisterRefusal("register_ring_coordinate_invalid")
        points.append((lon, lat))
    return tuple(points)


def _source(value: object) -> Mapping[str, object]:
    if type(value) is not dict:
        raise RegisterRefusal("register_source_invalid")
    retrieved = value.get("retrieved_on")
    if type(retrieved) is not str or _DATE.fullmatch(retrieved) is None:
        raise RegisterRefusal("register_retrieved_invalid")
    year_text, month_text, day_text = retrieved.split("-")
    try:
        parsed = date(int(year_text), int(month_text), int(day_text))
    except ValueError as error:
        raise RegisterRefusal(
            reason(error, "register_retrieved_date_invalid")
        ) from None
    return {
        "source_id": _token(value.get("source_id")),
        "publisher": _token(value.get("publisher")),
        "title": _token(value.get("title")),
        "licence": _token(value.get("licence")),
        "url": _token(value.get("url")),
        "retrieved_on": parsed,
        "sha256": _hash_text(value.get("sha256")),
    }


def _lineage(value: object) -> Mapping[str, object]:
    if type(value) is not dict:
        raise RegisterRefusal("register_lineage_invalid")
    return {
        "lineage_id": _token(value.get("lineage_id")),
        "table_name": _token(value.get("table_name")),
        "source_id": _token(value.get("source_id")),
        "input_class": _token(value.get("input_class")),
        "transform": _token(value.get("transform")),
    }


def _token(value: object) -> str:
    if type(value) is not str or value.strip() == "" or value != value.strip():
        raise RegisterRefusal("register_token_invalid")
    return value


def _optional(value: object) -> str | None:
    if value is None:
        return None
    return _token(value)


def _hash_text(value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise RegisterRefusal("register_hash_invalid")
    return value


def _year(value: object) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9]{4}", value) is None:
        raise RegisterRefusal("register_year_invalid")
    return value
