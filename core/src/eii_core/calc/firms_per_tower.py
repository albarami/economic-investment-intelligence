"""Counts of financial-centre firms per published tower (DAT-168).

No I/O. Each row is one company. No numeric field is read or summed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

CLASS_KEYS = (
    "band_low",
    "band_mid_low",
    "band_mid",
    "band_mid_high",
    "band_high",
)
DISTRICT_COUNT_CLASS = "district_count"
CLOSED_CLASS_KEYS = frozenset((*CLASS_KEYS, DISTRICT_COUNT_CLASS))

_ALLOWED_KEYS = frozenset(
    {
        "registration_key",
        "tower_or_building",
        "position",
        "district_key",
        "district_free_zone",
    }
)
_NUMERIC_KEYS = frozenset(
    {
        "employee_count",
        "wage",
        "wage_bill",
        "wage_month",
        "jobs",
    }
)
_CLASS_COUNT = 5


class FirmsPerTowerError(ValueError):
    """A row cannot be counted on the terms of DAT-168."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class TowerCount:
    """One tower's company count and its reviewed-position status."""

    tower: str
    count: int
    class_key: str
    position: tuple[str, str] | None
    position_status: str
    companies: tuple[str, ...]


@dataclass(frozen=True)
class DistrictCount:
    """Companies whose card publishes no building, counted in their district."""

    district_key: str
    count: int
    class_key: str
    companies: tuple[str, ...]


@dataclass(frozen=True)
class UnplacedCompany:
    """A company placed at neither a published tower nor a district."""

    registration_key: str
    reason: str


@dataclass(frozen=True)
class ClassBreak:
    """One equal-count band. Equal boundaries are already merged."""

    class_key: str
    low: int
    high: int
    boundary_tower: str


@dataclass(frozen=True)
class FirmsPerTower:
    """Counts, placement report and class breaks. Nothing here is a sum."""

    towers: tuple[TowerCount, ...]
    districts: tuple[DistrictCount, ...]
    unplaced: tuple[UnplacedCompany, ...]
    coverage: Mapping[str, int]
    breaks: tuple[ClassBreak, ...]


def firms_per_tower(rows: Sequence[Mapping[str, object]]) -> FirmsPerTower:
    """Count companies per published tower, else per district.

    A company whose card names no building and whose registered cell is null
    is unplaced: ``zone_without_district`` only when that cell lies in a
    reviewed district-free zone, otherwise ``location_unresolved``.
    """
    prepared = [_prepare(row) for row in rows]
    towers = _towers(prepared)
    districts = _districts(prepared)
    unplaced = _unplaced(prepared)
    breaks = _breaks(towers)
    _apply_classes(towers, districts, breaks)
    coverage = _coverage(towers, unplaced)
    return FirmsPerTower(
        towers=tuple(towers),
        districts=tuple(districts),
        unplaced=tuple(unplaced),
        coverage=coverage,
        breaks=tuple(breaks),
    )


def _is_number(value: object) -> bool:
    return type(value) in (int, float, Decimal)


def _prepare(row: Mapping[str, object]) -> dict[str, object]:
    if type(row) is not dict:
        raise FirmsPerTowerError("row_shape")
    for key, value in row.items():
        if key in _NUMERIC_KEYS or _is_number(value):
            raise FirmsPerTowerError("numeric_field")
        if key == "count_at":
            if value != row.get("tower_or_building"):
                raise FirmsPerTowerError("tower_not_published")
            raise FirmsPerTowerError("row_shape")
        if key not in _ALLOWED_KEYS:
            raise FirmsPerTowerError("row_shape")
        if _nested_number(value):
            raise FirmsPerTowerError("numeric_field")
    key_text = row.get("registration_key")
    if (
        type(key_text) is not str
        or key_text.strip() == ""
        or key_text != key_text.strip()
    ):
        raise FirmsPerTowerError("row_shape")
    tower = _optional_text(row.get("tower_or_building", None))
    district = _optional_text(row.get("district_key", None))
    free = row.get("district_free_zone", False)
    if type(free) is not bool:
        raise FirmsPerTowerError("row_shape")
    position = _position(row.get("position", None))
    return {
        "registration_key": key_text,
        "tower_or_building": tower,
        "position": position,
        "district_key": district,
        "district_free_zone": free,
    }


def _nested_number(value: object) -> bool:
    if type(value) is tuple:
        return any(_is_number(item) or _nested_number(item) for item in value)
    return False


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str or value != value.strip():
        raise FirmsPerTowerError("row_shape")
    if value == "":
        return None
    return value


def _position(value: object) -> tuple[str, str] | None:
    if value is None:
        return None
    if type(value) is not tuple or len(value) != 2:
        raise FirmsPerTowerError("row_shape")
    lon, lat = value
    if type(lon) is not str or type(lat) is not str:
        raise FirmsPerTowerError("row_shape")
    if lon == "" or lat == "" or lon != lon.strip() or lat != lat.strip():
        raise FirmsPerTowerError("row_shape")
    return (lon, lat)


def _towers(rows: Sequence[Mapping[str, object]]) -> list[TowerCount]:
    order: list[str] = []
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for row in rows:
        tower = row["tower_or_building"]
        if type(tower) is not str:
            continue
        if tower not in grouped:
            order.append(tower)
            grouped[tower] = []
        grouped[tower].append(row)
    built: list[TowerCount] = []
    for tower in order:
        members = grouped[tower]
        status, position = _position_status(members)
        built.append(
            TowerCount(
                tower=tower,
                count=len(members),
                class_key="",
                position=position,
                position_status=status,
                companies=tuple(str(item["registration_key"]) for item in members),
            )
        )
    return built


def _position_status(
    members: Sequence[Mapping[str, object]],
) -> tuple[str, tuple[str, str] | None]:
    seen: list[tuple[str, str] | None] = []
    for item in members:
        position = item["position"]
        if position is None:
            seen.append(None)
        elif type(position) is tuple:
            seen.append(position)
        else:
            raise FirmsPerTowerError("row_shape")
    if all(item is None for item in seen):
        return "none", None
    first = seen[0]
    if first is not None and all(item == first for item in seen):
        return "agree", first
    return "disagree", None


def _districts(rows: Sequence[Mapping[str, object]]) -> list[DistrictCount]:
    order: list[str] = []
    grouped: dict[str, list[str]] = {}
    for row in rows:
        if type(row["tower_or_building"]) is str:
            continue
        district = row["district_key"]
        if type(district) is not str:
            continue
        if district not in grouped:
            order.append(district)
            grouped[district] = []
        grouped[district].append(str(row["registration_key"]))
    return [
        DistrictCount(
            district_key=district,
            count=len(grouped[district]),
            class_key="",
            companies=tuple(grouped[district]),
        )
        for district in order
    ]


def _unplaced(rows: Sequence[Mapping[str, object]]) -> list[UnplacedCompany]:
    found: list[UnplacedCompany] = []
    for row in rows:
        if type(row["tower_or_building"]) is str:
            continue
        if type(row["district_key"]) is str:
            continue
        reason = (
            "zone_without_district"
            if row["district_free_zone"] is True
            else "location_unresolved"
        )
        found.append(
            UnplacedCompany(
                registration_key=str(row["registration_key"]),
                reason=reason,
            )
        )
    return found


def _breaks(towers: Sequence[TowerCount]) -> list[ClassBreak]:
    ordered = sorted((item.tower, item.count) for item in towers)
    ordered.sort(key=lambda item: (item[1], item[0]))
    count = len(ordered)
    if count == 0:
        return []
    slices: list[list[tuple[str, int]]] = []
    for index in range(_CLASS_COUNT):
        start = index * count // _CLASS_COUNT
        end = (index + 1) * count // _CLASS_COUNT
        if start < end:
            slices.append(ordered[start:end])
    merged: list[list[tuple[str, int]]] = []
    for group in slices:
        if merged and merged[-1][-1][1] == group[0][1]:
            merged[-1].extend(group)
        else:
            merged.append(list(group))
    breaks: list[ClassBreak] = []
    for index, group in enumerate(merged):
        breaks.append(
            ClassBreak(
                class_key=CLASS_KEYS[index],
                low=group[0][1],
                high=group[-1][1],
                boundary_tower=group[-1][0],
            )
        )
    return breaks


def _class_of(count: int, breaks: Sequence[ClassBreak]) -> str:
    for band in breaks:
        if band.low <= count <= band.high:
            return band.class_key
    for band in breaks:
        if count <= band.high:
            return band.class_key
    return breaks[-1].class_key


def _apply_classes(
    towers: list[TowerCount],
    districts: list[DistrictCount],
    breaks: Sequence[ClassBreak],
) -> None:
    if not breaks:
        for index, district in enumerate(districts):
            districts[index] = DistrictCount(
                district_key=district.district_key,
                count=district.count,
                class_key=DISTRICT_COUNT_CLASS,
                companies=district.companies,
            )
        return
    for index, tower in enumerate(towers):
        towers[index] = TowerCount(
            tower=tower.tower,
            count=tower.count,
            class_key=_class_of(tower.count, breaks),
            position=tower.position,
            position_status=tower.position_status,
            companies=tower.companies,
        )
    for index, district in enumerate(districts):
        districts[index] = DistrictCount(
            district_key=district.district_key,
            count=district.count,
            class_key=_class_of(district.count, breaks),
            companies=district.companies,
        )


def _coverage(
    towers: Sequence[TowerCount],
    unplaced: Sequence[UnplacedCompany],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for tower in towers:
        if tower.position_status == "agree":
            continue
        counts["tower_without_position"] = counts.get("tower_without_position", 0) + 1
    for item in unplaced:
        counts[item.reason] = counts.get(item.reason, 0) + 1
    return counts
