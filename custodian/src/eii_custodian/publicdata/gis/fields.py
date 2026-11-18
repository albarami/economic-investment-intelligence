"""Reviewed kept fields for the GIS centre layers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_ESRI_KINDS = {
    "esriFieldTypeString": "string",
    "esriFieldTypeSmallInteger": "integer",
    "esriFieldTypeInteger": "integer",
    "esriFieldTypeDouble": "number",
    "esriFieldTypeDate": "date",
    "esriFieldTypeGeometry": "geometry",
}

# Never requested and never stored. RULEID is kept only where the review lists it.
NEVER_TAKEN = frozenset(
    {
        "EMP_NUM",
        "SURVEYED_BY",
        "JOB",
        "GFCODE",
        "REMARKS",
        "COMMENTS",
        "WATER_NO",
        "ELECTRICITY_NO",
        "QTEL_ID",
        "QARS",
        "DATE_LUPD",
        "GLOBALID",
        "EMAIL",
        "PHONE",
        "FAX_NO",
        "POBOX_NO",
        "PHOTO_URL",
        "POI_ID_PHO",
    }
)

_FILE = Path("custodian") / "publicdata" / "review" / "gis_layer_fields.yaml"
_CACHE: dict[str, SourceDecl] | None = None


class FieldsError(ValueError):
    """The reviewed field file is not usable."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class FieldDecl:
    """One kept field and the service's field type."""

    name: str
    esri_type: str

    @property
    def json_kind(self) -> str:
        """Return the JSON kind the query answer must use."""
        return _ESRI_KINDS[self.esri_type]

    @property
    def geometry(self) -> bool:
        """Return whether this field is the feature geometry."""
        return self.esri_type == "esriFieldTypeGeometry"


@dataclass(frozen=True)
class LayerDecl:
    """One feature layer inside a source."""

    service_path: str
    layer_id: int
    layer_name: str
    geometry: str
    page_limit: int
    fields: tuple[FieldDecl, ...]

    @property
    def attribute_fields(self) -> tuple[FieldDecl, ...]:
        """Return kept fields that arrive as attributes, not as geometry."""
        return tuple(field for field in self.fields if not field.geometry)

    @property
    def geometry_field(self) -> str:
        """Return the geometry field's published name."""
        names = [field.name for field in self.fields if field.geometry]
        if len(names) != 1:
            raise FieldsError("geometry field")
        return names[0]


@dataclass(frozen=True)
class SourceDecl:
    """Every layer this source fetches."""

    source_id: str
    layers: tuple[LayerDecl, ...]


def declarations() -> dict[str, SourceDecl]:
    """Return the reviewed declarations, keyed by source id."""
    global _CACHE
    if _CACHE is None:
        _CACHE = _read(fields_path())
    return _CACHE


def declaration_for(source_id: str) -> SourceDecl | None:
    """Return one source's declaration, or None when it has none."""
    return declarations().get(source_id)


def fields_path() -> Path:
    """Find the review file by walking parents, in the checkout or a copy."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / _FILE
        if candidate.is_file():
            return candidate
    raise FieldsError("gis_layer_fields.yaml missing")


def _read(path: Path) -> dict[str, SourceDecl]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise FieldsError("gis fields root")
    sources = loaded.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise FieldsError("gis fields sources")
    found: dict[str, SourceDecl] = {}
    for source_id, body in sources.items():
        if not isinstance(source_id, str) or not isinstance(body, dict):
            raise FieldsError("gis fields source")
        found[source_id] = SourceDecl(source_id, _layers(body.get("layers")))
    return found


def _layers(value: object) -> tuple[LayerDecl, ...]:
    if not isinstance(value, list) or not value:
        raise FieldsError("gis fields layers")
    return tuple(_layer(item) for item in value)


def _layer(value: object) -> LayerDecl:
    if not isinstance(value, dict):
        raise FieldsError("gis fields layer")
    geometry = value.get("geometry")
    if geometry not in {"point", "line", "polygon"}:
        raise FieldsError("gis fields geometry")
    layer_id = value.get("layer_id")
    page_limit = value.get("page_limit")
    name = value.get("layer_name")
    path = value.get("service_path")
    if (
        isinstance(layer_id, bool)
        or not isinstance(layer_id, int)
        or layer_id < 0
        or isinstance(page_limit, bool)
        or not isinstance(page_limit, int)
        or page_limit < 1
        or not isinstance(name, str)
        or not isinstance(path, str)
        or not path.startswith("/")
    ):
        raise FieldsError("gis fields layer values")
    fields = _fields(value.get("fields"))
    layer = LayerDecl(path, layer_id, name, geometry, page_limit, fields)
    if any(field.name in NEVER_TAKEN for field in fields):
        raise FieldsError("gis fields never taken")
    if sum(1 for field in fields if field.geometry) != 1:
        raise FieldsError("geometry field")
    return layer


def _fields(value: object) -> tuple[FieldDecl, ...]:
    if not isinstance(value, list) or not value:
        raise FieldsError("gis fields list")
    found: list[FieldDecl] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise FieldsError("gis fields field")
        name = item.get("name")
        esri_type = item.get("esri_type")
        if not isinstance(name, str) or not name or name in seen:
            raise FieldsError("gis fields name")
        if not isinstance(esri_type, str) or esri_type not in _ESRI_KINDS:
            raise FieldsError("gis fields type")
        seen.add(name)
        found.append(FieldDecl(name, esri_type))
    return tuple(found)
