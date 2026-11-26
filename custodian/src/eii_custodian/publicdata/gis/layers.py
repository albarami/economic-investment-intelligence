"""Parsers and release rows for the GIS centre layers.

`frame.geometry.release_rows` writes only the frame's own boundary tables and
refuses every other source. These rows encode section 1.2 WKB from coordinates
the request asked for in EPSG:4326. A geometry whose answer is not wkid 4326
fails closed; this module does not project.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from eii_custodian.publicdata.additions.common import Coverage
from eii_custodian.publicdata.fetch.kinds import prepare
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.report import pin_share_line
from eii_custodian.publicdata.fetch.transport import Transport
from eii_custodian.publicdata.frame.gazetteer import reviewed_points
from eii_custodian.publicdata.frame.grid import ownership_index, point_cell

CONTEXT_ROLE = (
    "street centre lines with class and names; no flow, volume, "
    "speed or direction field"
)
_MONEY = Decimal("0.01")
_COORD = Decimal("0.000001")
_MILLIS = 1000
_PRICE = re.compile(r"^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?$")
_PRICE_RANGE = re.compile(r"^\d+-\d+$")
_PRICE_FIELDS = (
    "ResidentialPrices",
    "ResidentialCityCenter",
    "ResidentialPriceFlats",
    "ResidentialPriceVillas",
    "CommercialPrices",
)
_USE_FIELDS = (
    "LU_ENG",
    "LU_ARB",
    "P_COM_SHOP",
    "P_COM_OFF",
    "P_RES_VIL",
    "P_RES_APA",
    "P_RES_HOT",
)
_HEIGHT_FIELDS = ("HEIGHT", "HEIGHTS")
_SETBACK_FIELDS = (
    "SET_NOW_FR",
    "SET_NOW_RE",
    "SET_NOW_S1",
    "SET_NOW_S2",
    "SET_W_FR",
    "SET_W_RE",
    "SET_W_S1",
    "SET_W_S2",
)
_SERVICE_YEAR = re.compile(r"(?<!\d)\d{4}(?!\d)")
_RAIL_KIND = {2: "planned_station", 0: "line", 1: "protection_zone"}
_RAIL_GEOM = {2: "point", 0: "line", 1: "polygon"}
_BANNED = frozenset(
    {
        "pin",
        "objectid",
        "objectid_1",
        "parcel_number",
        "water_no",
        "electricity_no",
        "qtel_id",
        "globalid",
        "qars",
        "emp_num",
        "surveyed_by",
        "job",
        "gfcode",
        "remarks",
        "comments",
        "available",
        "availability",
        "approved",
        "approval",
        "permit",
        "rent",
        "operational",
        "operates",
        "operational_date",
        "pdarea",
    }
)


class LayerError(ValueError):
    """A GIS layer cannot be turned into release rows."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class ParsedLayer:
    """One fetched layer, still carrying in-build fields such as PIN."""

    layer_id: int
    layer_name: str
    geometry: str
    features: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class LayerRead:
    """Features from one source, or the check that loaded nothing."""

    layers: tuple[ParsedLayer, ...]
    failure: str | None


@dataclass(frozen=True)
class PinShare:
    """How many address points lie inside the parcel of the same PIN."""

    inside: int
    total: int
    line: str


@dataclass(frozen=True)
class HealthRows:
    """Health rows and the coverage note the build report carries."""

    rows: tuple[dict[str, object], ...]
    coverage: tuple[Coverage, ...]


@dataclass(frozen=True)
class _LandmarkBody:
    """The stored landmark content its lm- key is taken from."""

    name_en: str
    name_ar: str
    lon: Decimal
    lat: Decimal


def read_layer(entry: Entry, transport: Transport) -> LayerRead:
    """Page one declared source. A refusal returns no layers."""
    prepared = prepare(entry, transport, _no_sleep)
    if prepared.failure is not None:
        return LayerRead((), prepared.failure.check)
    return LayerRead(_parse_body(prepared.body), None)


def require_release_columns(rows: Sequence[Mapping[str, Any]]) -> None:
    """Refuse a release column that is an identifier, a rent or an approval."""
    for row in rows:
        for name in row:
            if name.casefold() in _BANNED:
                raise LayerError(f"release column {name}")


def pattern_class(value: object) -> str:
    """Show a string's shape: digits as 9, letters as a, other marks kept."""
    if not isinstance(value, str):
        return "not-a-string"
    chars: list[str] = []
    for char in value:
        if char.isdigit():
            chars.append("9")
        elif char.isalpha():
            chars.append("a")
        else:
            chars.append(char)
    return "".join(chars)


def parse_guide_price(field: str, value: object) -> Decimal:
    """Turn a plain numeric string into a decimal. Anything else fails closed."""
    if not isinstance(value, str) or _PRICE.fullmatch(value) is None:
        raise LayerError(f"{field}: {pattern_class(value)}")
    amount = Decimal(value.replace(",", ""))
    return amount.quantize(_MONEY, rounding=ROUND_HALF_EVEN)


def assign_feature_keys(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Assign fea- keys from the release columns. Ties gain _2, _3, and so on."""
    seen: dict[str, int] = {}
    keyed: list[dict[str, object]] = []
    for row in rows:
        body = {key: item for key, item in row.items() if key != "feature_key"}
        digest = hashlib.sha256(_canonical(body)).hexdigest()
        grouped = "-".join(digest[index : index + 4] for index in range(0, 16, 4))
        base = f"fea-{grouped}"
        seen[base] = seen.get(base, 0) + 1
        suffix = "" if seen[base] == 1 else f"_{seen[base]}"
        keyed.append({**body, "feature_key": base + suffix})
    return keyed


def land_price_rows(
    features: list[dict[str, object]],
    service_name: str,
    *,
    as_of: str,
) -> list[dict[str, object]]:
    """One guide-price row per published price field. The field name is the use.

    The period is the one year of the service's own name; a service name
    without exactly one year is refused (J22).
    """
    period = _service_year(service_name)
    rows: list[dict[str, object]] = []
    for feature in features:
        attributes = _attributes(feature)
        district = _district_key(attributes)
        for field in _PRICE_FIELDS:
            served = attributes.get(field)
            if field in attributes and (
                served is None
                or (isinstance(served, str) and _PRICE_RANGE.fullmatch(served))
            ):
                # R1: a use with no published price, or a published range
                # (not a single guide price), gives no row; counts after go-live.
                continue
            row = {
                "district_key": district,
                "period": period,
                "use_category": field,
                "guide_price": parse_guide_price(field, attributes.get(field)),
                "price_basis": "per_ft2",
            }
            row["as_of"] = as_of
            rows.append(row)
    require_release_columns(rows)
    return rows


def address_rows(
    features: list[dict[str, object]], grid: list[dict[str, object]]
) -> list[dict[str, object]]:
    """Address points. PIN stays out of the release."""
    owned = ownership_index(_frame_grid(grid))
    rows: list[dict[str, object]] = []
    for feature in features:
        attributes = _attributes(feature)
        lon, lat = _lon_lat(feature)
        if point_cell(float(lon), float(lat), owned) is None:
            # R1: a point outside the frame grid is left out, never refused
            # (328 of 163,860 live points); the count is written after go-live.
            continue
        rows.append(
            {
                "zone_number": _digits(attributes.get("ZONE_NO")),
                "street_number": _digits(attributes.get("STREET_NO")),
                "building_number": _digits(attributes.get("BUILDING_NO")),
                "building_subtype": _optional_digits(
                    attributes.get("BUILDING_NO_SUBTYPE")
                ),
                "survey_date": _survey_date(attributes.get("SURVEYED_DATE")),
                "lon": lon,
                "lat": lat,
                "cell": _cell(lon, lat, owned),
            }
        )
    keyed = assign_feature_keys(rows)
    require_release_columns(keyed)
    return keyed


def parcel_rows(features: list[dict[str, object]]) -> list[dict[str, object]]:
    """Parcels. Area is SHAPE.AREA. PIN stays out of the release."""
    rows: list[dict[str, object]] = []
    for feature in features:
        attributes = _attributes(feature)
        rows.append(
            {
                "area_m2": _money(attributes.get("SHAPE.AREA")),
                "start_date": _calendar_date(attributes.get("STARTDATE")),
                "end_date": _calendar_date(attributes.get("ENDDATE")),
                "geometry": geometry_wkb(_geometry(feature), "polygon"),
            }
        )
    keyed = assign_feature_keys(rows)
    require_release_columns(keyed)
    return keyed


def zoning_rows(layers: list[dict[str, object]]) -> list[dict[str, object]]:
    """Zoning as published. A null use is not filled from another feature."""
    rows: list[dict[str, object]] = []
    for layer in layers:
        name = layer.get("layer_name")
        if not isinstance(name, str):
            raise LayerError("layer name")
        detailed = name == "Khor_Wakra_Zoning"
        for feature in _feature_list(layer.get("features")):
            attributes = _attributes(feature)
            if detailed:
                permitted: object = _published(attributes, _USE_FIELDS)
                height: object = _published(attributes, _HEIGHT_FIELDS)
                setbacks: object = _published(attributes, _SETBACK_FIELDS)
                code = attributes.get("ZONING_COD")
            else:
                permitted = None
                height = None
                setbacks = None
                code = attributes.get("ZONING")
            if not isinstance(code, str):
                raise LayerError("zoning_code")
            rows.append(
                {
                    "zoning_code": code,
                    "permitted_uses": permitted,
                    "height_rule": height,
                    "setback_rule": setbacks,
                    "source_layer": name,
                    "geometry": geometry_wkb(_geometry(feature), "polygon"),
                }
            )
    keyed = assign_feature_keys(rows)
    require_release_columns(keyed)
    return keyed


def rail_rows(layers: list[dict[str, object]]) -> list[dict[str, object]]:
    """Rail plan rows. No column says a line or a station operates."""
    rows: list[dict[str, object]] = []
    for layer in layers:
        layer_id = layer.get("layer_id")
        if isinstance(layer_id, bool) or not isinstance(layer_id, int):
            raise LayerError("rail layer")
        if layer_id not in _RAIL_KIND:
            raise LayerError("rail layer")
        kind = _RAIL_GEOM[layer_id]
        for feature in _feature_list(layer.get("features")):
            attributes = _attributes(feature)
            rows.append(
                {
                    "feature_kind": _RAIL_KIND[layer_id],
                    "name_en": _optional_text(_rail_name_en(layer_id, attributes)),
                    "name_ar": _optional_text(_rail_name_ar(layer_id, attributes)),
                    "geometry": geometry_wkb(_geometry(feature), kind),
                }
            )
    keyed = assign_feature_keys(rows)
    require_release_columns(keyed)
    return keyed


def health_rows(layers: list[dict[str, object]]) -> HealthRows:
    """Health centres and catchments. The layers publish no period (J22).

    ``period`` is null and a ``period_not_published`` coverage note counts
    the rows for the build report.
    """
    rows: list[dict[str, object]] = []
    for layer in layers:
        name = layer.get("layer_name")
        geometry = layer.get("geometry")
        if not isinstance(name, str) or geometry not in {"point", "polygon"}:
            raise LayerError("health layer")
        kind = "catchment" if geometry == "polygon" else "centre"
        for feature in _feature_list(layer.get("features")):
            attributes = _attributes(feature)
            rows.append(
                {
                    "feature_kind": kind,
                    "name_en": _optional_text(
                        attributes.get("HC_NAME", attributes.get("ENAME"))
                    ),
                    "name_ar": _optional_text(
                        attributes.get("A_HC_NAME", attributes.get("ANAME"))
                    ),
                    "period": None,
                    "geometry": geometry_wkb(_geometry(feature), geometry),
                }
            )
    keyed = assign_feature_keys(rows)
    require_release_columns(keyed)
    coverage = (Coverage("period_not_published", len(keyed)),) if keyed else ()
    return HealthRows(tuple(keyed), coverage)


def poi_rows(
    features: list[dict[str, object]], grid: list[dict[str, object]]
) -> list[dict[str, object]]:
    """Commercial points. The layer publishes no category."""
    owned = ownership_index(_frame_grid(grid))
    rows: list[dict[str, object]] = []
    for feature in features:
        attributes = _attributes(feature)
        lon, lat = _lon_lat(feature)
        rows.append(
            {
                "name": _required_text(attributes.get("ENAME")),
                "name_ar": _optional_text(attributes.get("ANAME")),
                "category": None,
                "lon": lon,
                "lat": lat,
                "cell": _cell(lon, lat, owned),
            }
        )
    keyed = assign_feature_keys(rows)
    require_release_columns(keyed)
    return keyed


def landmark_rows(
    features: list[dict[str, object]], grid: list[dict[str, object]]
) -> list[dict[str, Any]]:
    """Landmark names enter the gazetteer only through reviewed_points.

    The ``lm-`` key is content-based (J24): the canonical JSON of the stored
    name and point, never the input order.
    """
    prepared: list[_LandmarkBody] = []
    for feature in features:
        attributes = _attributes(feature)
        lon, lat = _lon_lat(feature)
        prepared.append(
            _LandmarkBody(
                name_en=_required_text(attributes.get("ENAME")),
                name_ar=_required_text(attributes.get("ANAME")),
                lon=lon,
                lat=lat,
            )
        )
    keyed = _landmark_keys(prepared)
    specifications: list[dict[str, Any]] = []
    points: dict[tuple[str, str], dict[str, Any]] = {}
    for key, body in keyed:
        specifications.append(
            {
                "place_key": key,
                "kind": "landmark",
                "arabic_review": "pending native review",
                "source_id": "gis_landmarks",
                "record_key": key,
                "name_en": body.name_en,
                "name_ar": body.name_ar,
                "aliases": None,
            }
        )
        points[("gis_landmarks", key)] = {
            "lon": float(body.lon),
            "lat": float(body.lat),
        }
    rows = reviewed_points(specifications, points, _frame_grid(grid))
    require_release_columns(rows)
    return rows


def _landmark_keys(
    bodies: list[_LandmarkBody],
) -> list[tuple[str, _LandmarkBody]]:
    """Assign lm- keys by content in canonical order; ties gain _2, and so on."""
    seen: dict[str, int] = {}
    keyed: list[tuple[str, _LandmarkBody]] = []
    for body in sorted(bodies, key=_landmark_canonical):
        digest = hashlib.sha256(_landmark_canonical(body)).hexdigest()
        grouped = "-".join(digest[index : index + 4] for index in range(0, 16, 4))
        base = f"lm-{grouped}"
        seen[base] = seen.get(base, 0) + 1
        suffix = "" if seen[base] == 1 else f"_{seen[base]}"
        keyed.append((base + suffix, body))
    return keyed


def _landmark_canonical(body: _LandmarkBody) -> bytes:
    """The canonical content a landmark's lm- key is taken from."""
    return _canonical(
        {
            "name_en": body.name_en,
            "name_ar": body.name_ar,
            "lon": body.lon,
            "lat": body.lat,
        }
    )


def address_parcel_share(
    addresses: list[dict[str, object]], parcels: list[dict[str, object]]
) -> PinShare:
    """Share of address points inside the parcel polygon of the same PIN."""
    by_pin: dict[object, list[BaseGeometry]] = {}
    for parcel in parcels:
        pin = _attributes(parcel).get("PIN")
        by_pin.setdefault(pin, []).append(geometry_shape(_geometry(parcel), "polygon"))
    inside = 0
    for address in addresses:
        pin = _attributes(address).get("PIN")
        point = geometry_shape(_geometry(address), "point")
        if any(polygon.covers(point) for polygon in by_pin.get(pin, [])):
            inside += 1
    total = len(addresses)
    return PinShare(inside, total, pin_share_line(inside, total))


def context_tables() -> dict[str, list[dict[str, object]]]:
    """Street centre lines have no release table."""
    return {}


def geometry_wkb(geometry: dict[str, object], kind: str) -> bytes:
    """Encode one EPSG:4326 geometry as WKB."""
    return geometry_shape(geometry, kind).wkb


def geometry_shape(geometry: dict[str, object], kind: str) -> BaseGeometry:
    """Build a shapely geometry. The answer must already be wkid 4326."""
    if not _wkid_4326(geometry):
        raise LayerError("spatial_reference")
    if kind == "point":
        return shape(
            {
                "type": "Point",
                "coordinates": [
                    _number(geometry.get("x")),
                    _number(geometry.get("y")),
                ],
            }
        )
    if kind == "line":
        paths = _paths(geometry.get("paths"))
        if len(paths) == 1:
            return shape({"type": "LineString", "coordinates": paths[0]})
        return shape({"type": "MultiLineString", "coordinates": paths})
    if kind == "polygon":
        rings = _paths(geometry.get("rings"))
        return shape({"type": "Polygon", "coordinates": rings})
    raise LayerError("geometry")


def _no_sleep(_seconds: float) -> None:
    return None


def _parse_body(body: bytes) -> tuple[ParsedLayer, ...]:
    try:
        loaded = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise LayerError("layer body") from error
    if not isinstance(loaded, dict):
        raise LayerError("layer body")
    layers = loaded.get("layers")
    if not isinstance(layers, list):
        raise LayerError("layer body")
    parsed: list[ParsedLayer] = []
    for layer in layers:
        if not isinstance(layer, dict):
            raise LayerError("layer body")
        layer_id = layer.get("layer_id")
        name = layer.get("layer_name")
        geometry = layer.get("geometry")
        if (
            isinstance(layer_id, bool)
            or not isinstance(layer_id, int)
            or not isinstance(name, str)
            or not isinstance(geometry, str)
        ):
            raise LayerError("layer body")
        parsed.append(
            ParsedLayer(
                layer_id, name, geometry, tuple(_feature_list(layer.get("features")))
            )
        )
    return tuple(parsed)


def _published(attributes: dict[str, object], names: tuple[str, ...]) -> str:
    payload = {name: attributes.get(name) for name in names}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _service_year(service_name: str) -> str:
    """The year of the service's own name; it must hold exactly one year."""
    years = _SERVICE_YEAR.findall(service_name)
    if len(years) != 1:
        raise LayerError("service name year")
    return str(years[0])


def _district_key(attributes: dict[str, object]) -> str:
    left = attributes.get("DIST_NO")
    right = attributes.get("District_No")
    if left != right or isinstance(left, bool) or not isinstance(left, int):
        raise LayerError("district numbers differ")
    return str(left)


def _rail_name_en(layer_id: int, attributes: dict[str, object]) -> object:
    if layer_id == 2:
        return attributes.get("STATION_NAME_ENGLISH")
    if layer_id == 0:
        return attributes.get("TRACK_NAME")
    return None


def _rail_name_ar(layer_id: int, attributes: dict[str, object]) -> object:
    if layer_id == 2:
        return attributes.get("STATION_NAME_ARABIC")
    return None


def _attributes(feature: dict[str, object]) -> dict[str, object]:
    found = _text_map(feature.get("attributes"))
    if found is None:
        raise LayerError("attributes")
    return found


def _geometry(feature: dict[str, object]) -> dict[str, object]:
    found = _text_map(feature.get("geometry"))
    if found is None:
        raise LayerError("geometry")
    return found


def _feature_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise LayerError("features")
    rows: list[dict[str, object]] = []
    for item in value:
        found = _text_map(item)
        if found is None:
            raise LayerError("features")
        rows.append(found)
    return rows


def _text_map(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            return None
        result[key] = item
    return result


def _calendar_date(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LayerError("date")
    return datetime.fromtimestamp(value // _MILLIS, UTC).date().isoformat()


def _survey_date(value: object) -> str | None:
    # A served survey date before 1970 is an impossible entry (one live row
    # carries year 201); it is left blank instead of refusing the whole layer.
    if isinstance(value, int) and not isinstance(value, bool) and value < 0:
        return None
    return _calendar_date(value)


def _digits(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LayerError("number")
    return str(value)


def _optional_digits(value: object) -> str | None:
    if value is None:
        return None
    return _digits(value)


def _required_text(value: object) -> str:
    if not isinstance(value, str) or value == "":
        raise LayerError("text")
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _required_text(value)


def _money(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LayerError("area")
    return Decimal(str(value)).quantize(_MONEY, rounding=ROUND_HALF_EVEN)


def _lon_lat(feature: dict[str, object]) -> tuple[Decimal, Decimal]:
    geometry = _geometry(feature)
    if not _wkid_4326(geometry):
        raise LayerError("spatial_reference")
    return _coordinate(geometry.get("x")), _coordinate(geometry.get("y"))


def _coordinate(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LayerError("coordinate")
    return Decimal(str(value)).quantize(_COORD, rounding=ROUND_HALF_EVEN)


def _cell(lon: Decimal, lat: Decimal, owned: frozenset[int]) -> int:
    # The ownership index is built once per layer, not once per point (R1: 164k
    # address points against 72k cells was about 35 minutes of rebuilding).
    found = point_cell(float(lon), float(lat), owned)
    if found is None:
        raise LayerError("cell")
    return found


def _frame_grid(grid: list[dict[str, object]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in grid:
        cell = row.get("cell")
        if isinstance(cell, bool) or not isinstance(cell, int):
            raise LayerError("cell")
        rows.append({"cell": cell})
    return rows


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LayerError("coordinate")
    return float(value)


def _paths(value: object) -> list[list[tuple[float, float]]]:
    if not isinstance(value, list) or not value:
        raise LayerError("geometry")
    return [_ring(item) for item in value]


def _ring(value: object) -> list[tuple[float, float]]:
    if not isinstance(value, list) or len(value) < 2:
        raise LayerError("geometry")
    points: list[tuple[float, float]] = []
    for pair in value:
        if not isinstance(pair, list) or len(pair) < 2:
            raise LayerError("geometry")
        points.append((_number(pair[0]), _number(pair[1])))
    return points


def _wkid_4326(geometry: dict[str, object]) -> bool:
    reference = geometry.get("spatialReference")
    if not isinstance(reference, dict):
        return False
    wkid = reference.get("wkid")
    return isinstance(wkid, int) and not isinstance(wkid, bool) and wkid == 4326


def _canonical(value: object) -> bytes:
    return json.dumps(
        _canon(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _canon(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {str(key): _canon(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canon(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise LayerError("feature key value")
