"""VNP46A3 v2 whole-pixel aggregation, MTH-109 and brief rulings L4-L5."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from .contracts import GridError, local_file

GROUP = "/HDFEOS/GRIDS/VIIRS_Grid_DNB_2d/Data Fields/"
FIELD = "AllAngle_Composite_Snow_Free"


class FrameGeometry(Protocol):
    """Geometry operations used by windowing and exact ownership."""

    @property
    def bounds(self) -> tuple[float, float, float, float]: ...

    def covers(self, point: BaseGeometry) -> bool: ...

    def contains(self, point: BaseGeometry) -> bool: ...


@dataclass(frozen=True)
class Pixel:
    key: str
    lon: float
    lat: float
    value: Decimal | None
    quality: int


@dataclass(frozen=True)
class NightResult:
    rows: list[dict[str, Any]]
    missing: dict[int, str]
    excluded: dict[str, int]


def _text(value: Any) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _root_text(attrs: Any, name: str) -> str:
    if name not in attrs:
        raise GridError("ntl_blackmarble: product attribute missing")
    return _text(attrs[name])


def _one_number(value: Any) -> Any:
    """Return the one numeric element of a scalar or a one-element attribute."""
    array = np.asarray(value)
    if array.dtype.kind not in ("f", "i", "u") or array.size != 1:
        raise GridError("ntl_blackmarble: attribute shape")
    return array.flat[0]


def _field_number(attrs: Any, name: str) -> Any:
    if name not in attrs:
        raise GridError("ntl_blackmarble: attribute missing")
    return _one_number(attrs[name])


def _dataset(group: Any, name: str, message: str) -> Any:
    if name not in group:
        raise GridError(message)
    return group[name]


def read_night_lights(
    cache: Path,
    path: str | Path,
    period: str,
    bounds: tuple[float, float, float, float] | None = (
        -float("inf"),
        -float("inf"),
        float("inf"),
        float("inf"),
    ),
) -> list[Pixel]:
    """Decode local arrays; filter fill before scale and preserve source centres."""
    checked = local_file(cache, path)
    h5py = import_module("h5py")
    with h5py.File(checked, "r") as source:
        short_name = _root_text(source.attrs, "ShortName")
        version = _root_text(source.attrs, "VersionID")
        if short_name != "VNP46A3" or version != "002":
            raise GridError("ntl_blackmarble: unsupported product")
        start = _root_text(source.attrs, "StartTime")
        if start[:7] != period:
            raise GridError("ntl_blackmarble: period mismatch")
        stamp = datetime.strptime(period + "-01", "%Y-%m-%d")
        prefix = f"VNP46A3.A{stamp:%Y%j}.h23v06.002."
        granule = _root_text(source.attrs, "LocalGranuleID")
        if not granule.startswith(prefix):
            raise GridError("ntl_blackmarble: granule period or tile mismatch")
        if GROUP not in source:
            raise GridError("ntl_blackmarble: data group missing")
        fields = source[GROUP]
        radiance = _dataset(fields, FIELD, "ntl_blackmarble: field missing")
        quality = _dataset(
            fields, FIELD + "_Quality", "ntl_blackmarble: quality missing"
        )
        latitude = _dataset(fields, "lat", "ntl_blackmarble: lat missing")
        longitude = _dataset(fields, "lon", "ntl_blackmarble: lon missing")
        lat, lon = latitude[:], longitude[:]
        if radiance.shape != (len(lat), len(lon)) or quality.shape != radiance.shape:
            raise GridError("ntl_blackmarble: array shape mismatch")
        if getattr(radiance.dtype, "name", "") != "float32":
            raise GridError("ntl_blackmarble: radiance type")
        if getattr(quality.dtype, "name", "") != "uint8":
            raise GridError("ntl_blackmarble: quality type")
        if (
            getattr(latitude.dtype, "name", "") != "float64"
            or getattr(longitude.dtype, "name", "") != "float64"
        ):
            raise GridError("ntl_blackmarble: coordinate type")
        fill = _field_number(radiance.attrs, "_FillValue")
        scale = Decimal(str(_field_number(radiance.attrs, "scale_factor")))
        offset_name = "offset" if "offset" in radiance.attrs else "add_offset"
        offset = Decimal(str(_field_number(radiance.attrs, offset_name)))
        if bounds is None:
            return []
        west, south, east, north = bounds
        rows = np.flatnonzero((lat >= south) & (lat <= north))
        cols = np.flatnonzero((lon >= west) & (lon <= east))
        if not len(rows) or not len(cols):
            return []
        # Slice only the selected window; retain vector masks for noncontiguous
        # coordinates without assuming ascending latitude or longitude.
        row_start, col_start = int(rows[0]), int(cols[0])
        window = (
            slice(row_start, int(rows[-1]) + 1),
            slice(col_start, int(cols[-1]) + 1),
        )
        values, flags = radiance[window], quality[window]
        pixels = []
        for row in rows:
            for col in cols:
                latitude, longitude = lat[row], lon[col]
                raw = values[row - row_start, col - col_start]
                flag = int(flags[row - row_start, col - col_start])
                value = None if raw == fill else Decimal(str(raw)) * scale + offset
                pixels.append(
                    Pixel(
                        f"{row}:{col}", float(longitude), float(latitude), value, flag
                    )
                )
        return pixels


def aggregate(
    pixels: list[Pixel], cells: Mapping[int, FrameGeometry], period: str
) -> NightResult:
    """Mean kept centres once; shared edges belong to the lowest cell key."""
    buckets: dict[int, list[Decimal]] = {key: [] for key in cells}
    counts = {"poor": 0, "history": 0, "quality_fill": 0, "radiance_fill": 0}
    keys = list(cells)
    tree = import_module("shapely.strtree").STRtree([cells[key] for key in keys])
    seen: set[str] = set()
    for pixel in pixels:
        if pixel.key in seen:
            raise GridError("ntl_blackmarble: duplicate pixel")
        seen.add(pixel.key)
        if pixel.quality not in (0, 1, 2, 255):
            raise GridError("ntl_blackmarble: unknown quality code")
        if pixel.quality == 0 and pixel.value is not None:
            if not pixel.value.is_finite() or pixel.value < 0:
                raise GridError("ntl_blackmarble: invalid radiance")
        point = Point(pixel.lon, pixel.lat)
        owners = sorted(
            keys[index]
            for index in tree.query(point)
            if cells[keys[index]].covers(point)
        )
        if not owners:
            continue
        if pixel.quality != 0:
            counts[{1: "poor", 2: "history", 255: "quality_fill"}[pixel.quality]] += 1
        if pixel.value is None:
            counts["radiance_fill"] += 1
        if pixel.quality != 0 or pixel.value is None:
            continue
        if sum(cells[key].contains(point) for key in owners) > 1:
            raise GridError("ntl_blackmarble: overlapping ownership")
        if owners:
            buckets[owners[0]].append(pixel.value)
    rows, missing = [], {}
    for key, values in sorted(buckets.items()):
        if not values:
            missing[key] = "NO_DATA"
        else:
            rows.append(
                {
                    "cell": key,
                    "period": period,
                    "radiance": (sum(values, Decimal(0)) / len(values)).quantize(
                        Decimal("0.0001"), rounding=ROUND_HALF_UP
                    ),
                    "source_id": "ntl_blackmarble",
                }
            )
    return NightResult(rows, missing, counts)


def area_mean(rows: list[dict[str, Any]]) -> Decimal | None:
    """MTH-109 regression helper over selected frame-cell rows, without weighting."""
    if not rows:
        return None
    if len({row["cell"] for row in rows}) != len(rows):
        raise GridError("ntl_blackmarble: duplicate cell")
    for row in rows:
        if type(row["radiance"]) is not Decimal:
            raise GridError("ntl_blackmarble: radiance not decimal")
    return sum((row["radiance"] for row in rows), Decimal(0)) / len(rows)
