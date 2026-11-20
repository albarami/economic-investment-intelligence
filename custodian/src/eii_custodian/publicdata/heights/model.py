"""The S2-T20 input contract: building table, rules file, closed lists (B3, B4).

The building table is `data/assets/buildings/buildings.geojson`, a GeoJSON
FeatureCollection whose features carry exactly the properties `building_id`,
`recorded_height_m`, `floor_count` and `footprint_source_id`. Any property
beyond those four is refused, whatever its name (FE-50).
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from eii_core.calc.building_heights import HEIGHT_SOURCES, height_value

BUILDINGS_RELATIVE = "assets/buildings/buildings.geojson"
LANDMARK_HEIGHTS_RELATIVE = "publicdata/review/landmark_heights.yaml"
HEIGHTS_RELATIVE = "assets/heights"
HEIGHTS_FILE = "heights.json"
MANIFEST_FILE = "manifest.heights.json"
REQUIRED_PROPERTIES = frozenset(
    {
        "building_id",
        "recorded_height_m",
        "floor_count",
        "footprint_source_id",
    }
)
OUTPUT_COLUMNS = frozenset(
    {
        "building_id",
        "height_m",
        "height_source",
        "footprint_source_id",
        "reason",
    }
)
STRUCTURE_MARKER = "to be confirmed"
SOURCE_IDS = ("bldg_3dglobfp", "bldg_wsf3d", "bldg_gba")
RULES_PATH = Path(__file__).resolve().parents[4] / "publicdata" / "height_rules.yaml"
_RULES_KEYS = frozenset(
    {
        "storey_height_m",
        "order",
        "match_3dglobfp",
        "match_wsf3d",
        "credit_3dglobfp",
        "sources",
    }
)
_STOREY_KEYS = frozenset({"value", "label", "basis"})
_STRUCTURE_KEYS = frozenset(
    {
        "format",
        "field",
        "band",
        "unit",
        "nodata",
        "scale",
        "crs",
        "dtype",
        "class_field",
    }
)


class HeightError(ValueError):
    """A named refusal. The name is the check that failed."""

    def __init__(self, name: str, detail: str = "") -> None:
        self.name = name
        self.detail = detail
        super().__init__(name)


@dataclass(frozen=True)
class Building:
    """One row of the input contract, already checked."""

    building_id: str
    geometry: BaseGeometry
    recorded: Decimal | None
    floor_count: Decimal | None
    footprint_source_id: str


@dataclass(frozen=True)
class SourceStructure:
    """The declared structure of one height source (PUB-07).

    `scale` is declared only on the band form: a stored cell value times the
    scale is metres. `dtype` is the band's own stored type, as the source
    publishes it. The field form carries neither.
    """

    format: str
    field: str
    band: str
    unit: str
    nodata: str
    scale: str
    crs: str
    dtype: str
    class_field: str


@dataclass(frozen=True)
class Rules:
    """The committed height rules: the one storey constant and the wording."""

    storey_height: Decimal
    storey_value: str
    label: str
    basis: str
    order: str
    match_3dglobfp: str
    match_wsf3d: str
    credit_3dglobfp: str
    structures: dict[str, SourceStructure]


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HeightError(f"rules_{name}")
    return value


def unique_json(body: bytes | str, name: str) -> object:
    """Parse JSON with Decimal numbers; refuse a repeated object key (V6)."""

    def hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        out: dict[str, object] = {}
        for key, value in pairs:
            if key in out:
                raise HeightError(name, key)
            out[key] = value
        return out

    try:
        return json.loads(body, parse_float=Decimal, object_pairs_hook=hook)
    except HeightError:
        raise
    except ValueError:
        raise HeightError(name) from None


def _structure(raw: object, source_id: str) -> SourceStructure:
    if not isinstance(raw, dict):
        raise HeightError("rules_source")
    if set(raw) - _STRUCTURE_KEYS:
        raise HeightError("rules_unknown_key")
    for name in ("format", "unit", "nodata", "crs"):
        if name not in raw:
            raise HeightError("rules_missing_key")
    has_field = "field" in raw
    has_band = "band" in raw
    has_scale = "scale" in raw
    has_dtype = "dtype" in raw
    if has_field == has_band or (has_scale and has_field) or (has_dtype and has_field):
        raise HeightError("rules_field_or_band")
    if has_band and not has_scale:
        raise HeightError("rules_missing_key")
    if has_band and not has_dtype:
        raise HeightError("rules_missing_key")
    nodata = raw["nodata"]
    if not isinstance(nodata, str):
        raise HeightError("rules_nodata")
    class_field = raw.get("class_field", "")
    if class_field != "" and not has_field:
        raise HeightError("rules_field_or_band", "class_field")
    if class_field != "" and not isinstance(class_field, str):
        raise HeightError("rules_class_field")
    return SourceStructure(
        format=_require_text(raw["format"], "format"),
        field=_require_text(raw.get("field", ""), "field") if has_field else "",
        band=_require_text(raw.get("band", ""), "band") if has_band else "",
        unit=_require_text(raw["unit"], "unit"),
        nodata=nodata,
        scale=_require_text(raw.get("scale", ""), "scale") if has_band else "",
        crs=_require_text(raw["crs"], "crs"),
        dtype=_require_text(raw.get("dtype", ""), "dtype") if has_band else "",
        class_field=class_field if isinstance(class_field, str) else "",
    )


def load_rules(path: Path) -> Rules:
    """Read the committed height rules; every key is checked."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        raise HeightError("rules_root") from None
    if not isinstance(document, dict):
        raise HeightError("rules_root")
    if set(document) - _RULES_KEYS:
        raise HeightError("rules_unknown_key")
    if _RULES_KEYS - set(document):
        raise HeightError("rules_missing_key")
    storey = document["storey_height_m"]
    if not isinstance(storey, dict):
        raise HeightError("rules_storey")
    if set(storey) - _STOREY_KEYS:
        raise HeightError("rules_unknown_key")
    if _STOREY_KEYS - set(storey):
        raise HeightError("rules_missing_key")
    if storey["label"] != "ASSUMPTION":
        raise HeightError("rules_label")
    value_text = _require_text(storey["value"], "storey_value")
    try:
        storey_height = Decimal(value_text)
    except ArithmeticError:
        raise HeightError("rules_storey_value") from None
    if height_value(storey_height) is None:
        raise HeightError("rules_storey_value")
    sources = document["sources"]
    if not isinstance(sources, dict) or set(sources) != set(SOURCE_IDS):
        raise HeightError("rules_sources")
    return Rules(
        storey_height=storey_height,
        storey_value=value_text,
        label=storey["label"],
        basis=_require_text(storey["basis"], "basis"),
        order=_require_text(document["order"], "order"),
        match_3dglobfp=_require_text(document["match_3dglobfp"], "match_3dglobfp"),
        match_wsf3d=_require_text(document["match_wsf3d"], "match_wsf3d"),
        credit_3dglobfp=_require_text(document["credit_3dglobfp"], "credit_3dglobfp"),
        structures={
            source_id: _structure(sources[source_id], source_id)
            for source_id in SOURCE_IDS
        },
    )


def structure_unconfirmed(structure: SourceStructure) -> bool:
    """A declared value still holding the marker keeps its source out (PUB-07)."""
    return STRUCTURE_MARKER in {
        structure.format,
        structure.field,
        structure.band,
        structure.unit,
        structure.nodata,
        structure.scale,
        structure.crs,
        structure.dtype,
        structure.class_field,
    }


def _number(value: object, name: str) -> Decimal | None:
    """A number or null; anything else or an unusable value is refused."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise HeightError(f"bad_{name}")
    parsed = Decimal(value) if isinstance(value, int) else value
    if height_value(parsed) is None:
        raise HeightError(f"bad_{name}")
    return parsed


def _footprint(geometry: object) -> BaseGeometry:
    """A non-empty, valid polygon or multipolygon footprint."""
    if not isinstance(geometry, dict):
        raise HeightError("bad_footprint")
    if geometry.get("type") not in ("Polygon", "MultiPolygon"):
        raise HeightError("bad_footprint")
    try:
        parsed = shape(geometry)
    except (ValueError, TypeError, KeyError, AttributeError):
        raise HeightError("bad_footprint") from None
    if parsed.is_empty or not parsed.is_valid:
        raise HeightError("bad_footprint")
    return parsed


def load_buildings(path: Path) -> list[Building]:
    """Read the one documented building table; every refusal writes no row."""
    try:
        payload = unique_json(path.read_bytes(), "building_table")
    except OSError:
        raise HeightError("building_table") from None
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise HeightError("building_table")
    features = payload.get("features")
    if not isinstance(features, list):
        raise HeightError("building_table")
    seen: set[str] = set()
    out: list[Building] = []
    for feature in features:
        if not isinstance(feature, dict):
            raise HeightError("building_table")
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise HeightError("missing_property")
        if set(properties) - REQUIRED_PROPERTIES:
            raise HeightError("extra_property")
        if REQUIRED_PROPERTIES - set(properties):
            raise HeightError("missing_property")
        building_id = properties["building_id"]
        if not isinstance(building_id, str) or not building_id.strip():
            raise HeightError("building_id")
        if building_id in seen:
            raise HeightError("repeated_id")
        seen.add(building_id)
        footprint_source_id = properties["footprint_source_id"]
        if not isinstance(footprint_source_id, str) or not footprint_source_id.strip():
            raise HeightError("footprint_source_id")
        floor_count = _number(properties["floor_count"], "floor_count")
        if floor_count is not None and floor_count != floor_count.to_integral_value():
            raise HeightError("bad_floor_count")
        out.append(
            Building(
                building_id=building_id,
                geometry=_footprint(feature.get("geometry")),
                recorded=_number(properties["recorded_height_m"], "recorded_height_m"),
                floor_count=floor_count,
                footprint_source_id=footprint_source_id,
            )
        )
    return sorted(out, key=lambda building: building.building_id)


def storey_literals(path: Path, constant: Decimal) -> tuple[int, ...]:
    """Line numbers of numeric literals equal to the storey constant (B4)."""
    found: list[int] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
            and Decimal(str(node.value)) == constant
        ):
            found.append(node.lineno)
    return tuple(sorted(found))


def float_calls(path: Path) -> tuple[int, ...]:
    """Line numbers of `float(` calls; no figure passes through a float."""
    found: list[int] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "float"
        ):
            found.append(node.lineno)
    return tuple(sorted(found))


__all__ = [
    "BUILDINGS_RELATIVE",
    "HEIGHTS_FILE",
    "HEIGHTS_RELATIVE",
    "HEIGHT_SOURCES",
    "MANIFEST_FILE",
    "OUTPUT_COLUMNS",
    "REQUIRED_PROPERTIES",
    "RULES_PATH",
    "SOURCE_IDS",
    "STRUCTURE_MARKER",
    "Building",
    "HeightError",
    "Rules",
    "SourceStructure",
    "float_calls",
    "load_buildings",
    "load_rules",
    "storey_literals",
    "structure_unconfirmed",
    "unique_json",
]
