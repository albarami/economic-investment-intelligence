"""Release manifest model. No plane and no driver."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

HASH_IGNORED = frozenset({"release_id", "build_id", "built_at"})
FORBIDDEN_PUBLIC_ONLY = frozenset(
    {
        "window_key",
        "protected_sha256",
        "parameter_set",
        "world_seed",
        "scenario_sha256",
        "contracts",
        "window_period",
        "spare_seeds",
    }
)
MANIFEST_CLASSES = frozenset(
    {"frame", "protected", "simulated", "public", "graph", "lineage", "control"}
)
COMMON_SCALARS = (
    "release_kind",
    "release_id",
    "release_contract_version",
    "build_id",
    "built_at",
    "code_version",
    "rules_version_id",
    "engine_versions",
)
ENGINE_VERSION_KEYS = ("duckdb", "postgis_target", "python")
_ENGINE_VERSION_KEY_SET = frozenset(ENGINE_VERSION_KEYS)
_LOGICAL = frozenset(
    {"string", "int", "bool", "date", "month", "timestamp", "cell", "geometry"}
)
_DECIMAL = re.compile(r"decimal\([0-9]+,[0-9]+\)\Z")
_LABELS = {
    "Protected": "protected",
    "Simulated": "simulated",
    "Graph": "graph",
    "Lineage": "lineage",
    "Control": "control",
}
_REASONS = frozenset(
    {
        "float_refused",
        "unknown_class",
        "unknown_class_label",
        "unknown_logical_type",
        "value_not_canonical",
    }
)


class ManifestRefusal(ValueError):
    """A fixed reason from the manifest model."""

    def __init__(self, reason: str) -> None:
        """Refuse a reason outside the model's closed list."""
        if reason not in _REASONS:
            message = "refusal reason invalid"
            raise ValueError(message)
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class ColumnSpec:
    """One logical column. Geometry carries its type and SRID."""

    name: str
    logical_type: str
    nullable: bool
    geometry_type: str | None = None
    srid: int | None = None


@dataclass(frozen=True)
class CatalogueTable:
    """One row of the section 7.2 catalogue."""

    name: str
    label: str
    grain: str
    key: tuple[str, ...]
    writer: str
    manifest_class: str


def class_of_label(label: str) -> str:
    """Map a document class label onto the closed manifest class."""
    if label.startswith("Public"):
        return "public"
    if label.startswith("Frame"):
        return "frame"
    mapped = _LABELS.get(label)
    if mapped is None:
        raise ManifestRefusal("unknown_class_label")
    return mapped


def require_manifest_class(value: str) -> str:
    """Refuse a class that is not one of the seven manifest classes."""
    if value not in MANIFEST_CLASSES:
        raise ManifestRefusal("unknown_class")
    return value


def require_logical_type(value: str) -> None:
    """Refuse a logical type outside section 1.2."""
    if value in _LOGICAL or _DECIMAL.fullmatch(value):
        return
    raise ManifestRefusal("unknown_logical_type")


def engine_versions_reason(value: object) -> str | None:
    """Refusal reason, or none when the three engines are non-empty strings."""
    if type(value) is not dict:
        return "manifest_type_invalid"
    lowered = {key.lower() for key in _ENGINE_VERSION_KEY_SET}
    for key in value:
        if type(key) is not str:
            return "manifest_type_invalid"
        if key.lower() in lowered and key not in _ENGINE_VERSION_KEY_SET:
            return "manifest_key_case"
        if key not in _ENGINE_VERSION_KEY_SET:
            return "unknown_manifest_key"
    for key in ENGINE_VERSION_KEYS:
        if key not in value:
            return "manifest_type_invalid"
        item = value[key]
        if type(item) is not str or item == "":
            return "manifest_type_invalid"
    return None


def canonical_json(value: object) -> str:
    """Encode canonical JSON. A floating-point value is refused."""
    return _encode(value)


def release_hash(document: Mapping[str, object]) -> str:
    """SHA-256 of the manifest without release_id, build_id and built_at."""
    body = {key: item for key, item in document.items() if key not in HASH_IGNORED}
    return _sha256(canonical_json(body))


def schema_document(columns: Sequence[ColumnSpec]) -> list[dict[str, object]]:
    """Ordered logical schema. Geometry adds geometry type and SRID."""
    rows: list[dict[str, object]] = []
    for column in columns:
        require_logical_type(column.logical_type)
        row: dict[str, object] = {
            "logical_type": column.logical_type,
            "name": column.name,
            "nullable": column.nullable,
        }
        if column.logical_type == "geometry":
            row["geometry_type"] = column.geometry_type or ""
            row["srid"] = -1 if column.srid is None else column.srid
        rows.append(row)
    return rows


def schema_hash(columns: Sequence[ColumnSpec]) -> str:
    """SHA-256 of the canonical logical schema."""
    return _sha256(canonical_json(schema_document(columns)))


def by_name(name: str) -> CatalogueTable | None:
    """Return the catalogue row or none."""
    return _BY_NAME.get(name)


def written_by_privacy(table: CatalogueTable) -> bool:
    """The privacy engine writes this table."""
    return table.writer == "privacy"


def _encode(value: object) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if type(value) is float:
        raise ManifestRefusal("float_refused")
    if type(value) is str:
        return json.dumps(value, ensure_ascii=False)
    if type(value) is list or type(value) is tuple:
        return "[" + ",".join(_encode(item) for item in value) + "]"
    if type(value) is dict:
        parts: list[str] = []
        for key in sorted(value, key=lambda item: str(item)):
            if type(key) is not str:
                raise ManifestRefusal("value_not_canonical")
            parts.append(_encode(key) + ":" + _encode(value[key]))
        return "{" + ",".join(parts) + "}"
    raise ManifestRefusal("value_not_canonical")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build() -> tuple[CatalogueTable, ...]:
    built: list[CatalogueTable] = []
    for name, label, grain, key, writer in _RAW:
        built.append(
            CatalogueTable(
                name=name,
                label=label,
                grain=grain,
                key=key,
                writer=writer,
                manifest_class=class_of_label(label),
            )
        )
    return tuple(built)


_RAW: tuple[tuple[str, str, str, tuple[str, ...], str], ...] = (
    ("grid_cell", "Frame", "base cell", ("cell",), "publicdata"),
    ("release_unit", "Frame", "unit", ("unit_id",), "privacy"),
    ("unit_member", "Frame", "unit x cell", ("unit_id", "cell"), "privacy"),
    ("zone", "Frame (Public geometry)", "zone", ("zone_code",), "publicdata"),
    (
        "district",
        "Frame (Public geometry)",
        "district",
        ("district_key",),
        "publicdata",
    ),
    (
        "municipality",
        "Frame (Public geometry)",
        "municipality",
        ("municipality_code",),
        "publicdata",
    ),
    ("gazetteer", "Frame (Public)", "named place", ("place_key",), "publicdata"),
    ("road_link", "Frame (Public geometry)", "road link", ("link_id",), "publicdata"),
    (
        "resident_pay",
        "Protected",
        "unit x period x measure x housing class x band range",
        ("unit_id", "period", "measure", "housing_class", "band_from", "band_to"),
        "privacy",
    ),
    (
        "worker_pay",
        "Protected",
        "unit x period x measure x band range",
        ("unit_id", "period", "measure", "band_from"),
        "privacy",
    ),
    (
        "home_area_share",
        "Protected",
        "work unit x home unit x period",
        ("work_unit_id", "home_unit_id", "period"),
        "privacy",
    ),
    (
        "outlet_register",
        "Protected",
        "unit x period x activity class x size band",
        ("unit_id", "period", "activity_node_id", "size_band"),
        "privacy",
    ),
    (
        "occupation_pay",
        "Protected",
        "unit x period x measure x basis x group x band range",
        ("unit_id", "period", "measure", "basis", "occupation_group", "band_from"),
        "privacy",
    ),
    (
        "register_company_list",
        "Protected",
        "register company x last month",
        ("registration_number", "period"),
        "privacy",
    ),
    (
        "month_change",
        "Protected",
        "unit x adjacent months x table x measure",
        ("unit_id", "period", "table_name", "measure"),
        "privacy",
    ),
    (
        "presence_count",
        "Simulated",
        "unit x day type x hour x summer x segment",
        ("unit_id", "day_type", "hour", "summer", "segment"),
        "privacy",
    ),
    (
        "flow_hourly",
        "Simulated",
        "origin unit x destination unit x day type x hour x summer",
        ("origin_unit_id", "destination_unit_id", "day_type", "hour", "summer"),
        "privacy",
    ),
    (
        "presence_split",
        "Simulated",
        "unit x day type x hour x summer x split kind x split value",
        ("unit_id", "day_type", "hour", "summer", "split_kind", "split_value"),
        "privacy",
    ),
    (
        "flow_split",
        "Simulated",
        "origin unit x destination unit x day type x hour x summer x split kind x split value",
        (
            "origin_unit_id",
            "destination_unit_id",
            "day_type",
            "hour",
            "summer",
            "split_kind",
            "split_value",
        ),
        "privacy",
    ),
    (
        "traffic_hourly",
        "Simulated",
        "road link x day type x hour x summer",
        ("link_id", "day_type", "hour", "summer"),
        "mobility",
    ),
    (
        "access_score",
        "Simulated",
        "unit x supply layer x mode x cut-off x day type x hour x summer x traffic",
        (
            "unit_id",
            "activity_key",
            "mode",
            "cutoff",
            "day_type",
            "hour",
            "summer",
            "traffic",
        ),
        "mobility",
    ),
    (
        "pub_licence_active",
        "Public",
        "municipality x activity code x snapshot",
        ("municipality_code", "activity_code", "period"),
        "publicdata",
    ),
    (
        "pub_licence_cancelled",
        "Public",
        "municipality x activity code x month",
        ("municipality_code", "activity_code", "period"),
        "publicdata",
    ),
    (
        "pub_licence_issued",
        "Public",
        "municipality x activity code x period",
        ("municipality_code", "activity_code", "period"),
        "publicdata",
    ),
    (
        "pub_zone_utility",
        "Public",
        "zone x year x utility",
        ("zone_code", "period", "utility"),
        "publicdata",
    ),
    ("pub_transit_monthly", "Public", "month x mode", ("period", "mode"), "publicdata"),
    (
        "pub_sector_accounts",
        "Public",
        "activity x year x indicator",
        ("activity_code", "period", "indicator"),
        "publicdata",
    ),
    (
        "pub_wage_table",
        "Public (split)",
        "table x period x breakdown",
        ("table_code", "period", "breakdown_key", "indicator"),
        "publicdata",
    ),
    (
        "pub_customs_import",
        "Public",
        "tariff line x origin x month",
        ("tariff_code", "origin_iso3", "period"),
        "publicdata",
    ),
    (
        "pub_property_sale",
        "Public",
        "district x year x property type",
        ("district_key", "period", "property_type"),
        "publicdata",
    ),
    (
        "pub_census_zone",
        "Public",
        "zone x census year x indicator",
        ("zone_code", "period", "indicator"),
        "publicdata",
    ),
    (
        "pub_population_municipality",
        "Public",
        "municipality x period x indicator",
        ("municipality_code", "period", "indicator"),
        "publicdata",
    ),
    (
        "pub_census_national",
        "Public",
        "period x indicator",
        ("period", "indicator"),
        "publicdata",
    ),
    (
        "pub_census_district",
        "Public",
        "district x period x indicator",
        ("district_key", "period", "indicator"),
        "publicdata",
    ),
    ("pub_place", "Public", "place", ("place_id",), "publicdata"),
    (
        "pub_place_verification",
        "Public",
        "place x check date",
        ("place_id", "check_date"),
        "publicdata",
    ),
    (
        "pub_register_company",
        "Public",
        "register company",
        ("registration_number",),
        "publicdata",
    ),
    (
        "pub_register_snapshot",
        "Public",
        "register company x snapshot month",
        ("registration_number", "period"),
        "publicdata",
    ),
    (
        "pub_hotel_monthly",
        "Public",
        "month x star class x indicator",
        ("period", "star_class", "indicator"),
        "publicdata",
    ),
    (
        "pub_price_index",
        "Public",
        "month x group",
        ("period", "group_code"),
        "publicdata",
    ),
    (
        "pub_property_resi",
        "Public",
        "district x month x unit type",
        ("district_key", "period", "unit_type"),
        "publicdata",
    ),
    (
        "pub_property_quarter",
        "Public",
        "district x quarter x use x unit type",
        ("district_key", "period", "use_key", "unit_type"),
        "publicdata",
    ),
    (
        "pub_land_price",
        "Public",
        "district x use category x year",
        ("district_key", "use_category", "period"),
        "publicdata",
    ),
    (
        "pub_bank_credit",
        "Public",
        "economic activity x period",
        ("activity_key", "period"),
        "publicdata",
    ),
    (
        "pub_rail_plan",
        "Public",
        "rail feature: a line, a planned station or a protection zone",
        ("feature_key",),
        "publicdata",
    ),
    (
        "pub_health_centre",
        "Public",
        "health centre or its catchment",
        ("feature_key",),
        "publicdata",
    ),
    ("pub_zoning", "Public", "zoning polygon", ("feature_key",), "publicdata"),
    (
        "pub_address_point",
        "Public",
        "official address point",
        ("feature_key",),
        "publicdata",
    ),
    ("pub_parcel", "Public", "approved land parcel", ("feature_key",), "publicdata"),
    ("pub_poi_comm", "Public", "commercial point", ("feature_key",), "publicdata"),
    ("pub_tender", "Public", "tender", ("tender_key",), "publicdata"),
    (
        "pub_district_cooling",
        "Public",
        "municipality x sector x period x indicator",
        ("municipality_code", "sector_key", "period", "indicator"),
        "publicdata",
    ),
    (
        "pub_completions_ext",
        "Public",
        "registry slug x row x declared field",
        ("source_key", "slug", "row_index", "field_name"),
        "publicdata",
    ),
    (
        "pub_coverage_ext",
        "Public",
        "registry slug x row x declared field",
        ("source_key", "slug", "row_index", "field_name"),
        "publicdata",
    ),
    (
        "pub_fdi_stats",
        "Public",
        "registry slug x row x declared field",
        ("source_key", "slug", "row_index", "field_name"),
        "publicdata",
    ),
    (
        "pub_hotel_ext",
        "Public",
        "registry slug x row x declared field",
        ("source_key", "slug", "row_index", "field_name"),
        "publicdata",
    ),
    (
        "pub_jobseekers",
        "Public",
        "registry slug x row x declared field",
        ("source_key", "slug", "row_index", "field_name"),
        "publicdata",
    ),
    (
        "pub_price_ext",
        "Public",
        "registry slug x row x declared field",
        ("source_key", "slug", "row_index", "field_name"),
        "publicdata",
    ),
    (
        "pub_survey_ext",
        "Public",
        "registry slug x row x declared field",
        ("source_key", "slug", "row_index", "field_name"),
        "publicdata",
    ),
    (
        "pub_talent_ext",
        "Public",
        "registry slug x row x declared field",
        ("source_key", "slug", "row_index", "field_name"),
        "publicdata",
    ),
    (
        "pub_trade_ext",
        "Public",
        "registry slug x row x declared field",
        ("source_key", "slug", "row_index", "field_name"),
        "publicdata",
    ),
    (
        "pub_utilities_ext",
        "Public",
        "registry slug x row x declared field",
        ("source_key", "slug", "row_index", "field_name"),
        "publicdata",
    ),
    (
        "pub_venue_visits",
        "Public",
        "venue x period x indicator",
        ("venue_key", "period", "indicator"),
        "publicdata",
    ),
    (
        "pub_building_permits",
        "Public",
        "municipality x period x document x permit type x building type",
        (
            "municipality_code",
            "period",
            "document_type",
            "permit_type",
            "building_type",
        ),
        "publicdata",
    ),
    (
        "pub_establishment_size",
        "Public",
        "bulletin x activity x size class x year x indicator",
        ("table_code", "activity_key", "size_class", "period", "indicator"),
        "publicdata",
    ),
    (
        "pub_manufacturing",
        "Public",
        "table x year x breakdown x indicator",
        ("table_code", "period", "breakdown_key", "indicator"),
        "publicdata",
    ),
    (
        "pub_trade_wr",
        "Public",
        "trade type x year x indicator",
        ("trade_type", "period", "indicator"),
        "publicdata",
    ),
    (
        "pub_population_age",
        "Public",
        "municipality x year x age group x indicator",
        ("municipality_code", "period", "age_group", "indicator"),
        "publicdata",
    ),
    (
        "pub_hotels_municipality",
        "Public",
        "municipality x year x facility type",
        ("municipality_code", "period", "facility_type"),
        "publicdata",
    ),
    (
        "pub_trade_logistics",
        "Public",
        "table x year x breakdown x indicator",
        ("table_code", "period", "breakdown_key", "indicator"),
        "publicdata",
    ),
    (
        "pub_census_2015_municipality",
        "Public",
        "municipality x indicator",
        ("municipality_code", "period", "indicator"),
        "publicdata",
    ),
    (
        "pub_labour_sex_municipality",
        "Public (split)",
        "municipality x year x sex x indicator",
        ("municipality_code", "period", "sex", "indicator"),
        "publicdata",
    ),
    (
        "pub_population_age_sex",
        "Public (split)",
        "municipality x year x age group x sex x indicator",
        ("municipality_code", "period", "age_group", "sex", "indicator"),
        "publicdata",
    ),
    (
        "pub_active_sex_age",
        "Public (split)",
        "year x sex x age group x activity x indicator",
        ("period", "sex", "age_group", "activity_key", "indicator"),
        "publicdata",
    ),
    (
        "pub_active_nationality_occupation",
        "Public (split)",
        "year x nationality group x sex x occupation x activity x indicator",
        (
            "period",
            "nationality_group",
            "sex",
            "occupation_key",
            "activity_key",
            "indicator",
        ),
        "publicdata",
    ),
    (
        "pub_compensation_nationality",
        "Public (split)",
        "bulletin x year x activity x nationality group x indicator",
        ("table_code", "period", "activity_key", "nationality_group", "indicator"),
        "publicdata",
    ),
    (
        "pub_students",
        "Public (split)",
        "municipality x school year x level x type x sex x nationality group x indicator",
        (
            "municipality_code",
            "period",
            "education_level",
            "education_type",
            "sex",
            "nationality_group",
            "indicator",
        ),
        "publicdata",
    ),
    (
        "pub_visitor_markets",
        "Public (split)",
        "table x period x nationality group x breakdown x indicator",
        ("table_code", "period", "nationality_group", "breakdown_key", "indicator"),
        "publicdata",
    ),
    ("fdi_projects", "Public", "announced project", ("project_key",), "publicdata"),
    (
        "pub_investqa_record",
        "Public",
        "agency page record",
        ("record_type", "record_key"),
        "publicdata",
    ),
    (
        "pub_investqa_page",
        "Public",
        "agency page x language",
        ("page_key", "page_language"),
        "publicdata",
    ),
    ("zone_type", "Public", "zone", ("zone_code",), "publicdata"),
    (
        "access_score_grid",
        "Public",
        "population-grid cell x supply layer x mode x cut-off x traffic",
        ("grid_key", "activity_key", "mode", "cutoff", "traffic"),
        "publicdata",
    ),
    (
        "pub_venue_busyness",
        "Public",
        "named venue x day of week x hour",
        ("place_id", "day_of_week", "hour"),
        "publicdata",
    ),
    (
        "pub_night_lights",
        "Public",
        "frame cell x month",
        ("cell", "period"),
        "publicdata",
    ),
    ("pub_place_fsq", "Public", "place", ("fsq_place_id",), "publicdata"),
    (
        "pub_comtrade_trade",
        "Public",
        "reporter or mirror trade cell",
        (
            "series_role",
            "reporter_code",
            "partner_code",
            "partner2_code",
            "frequency",
            "period",
            "flow_code",
            "classification",
            "classification_revision",
            "product_code",
            "aggregation_level",
            "customs_code",
            "transport_mode_code",
            "valuation_basis",
            "measure",
        ),
        "publicdata",
    ),
    (
        "pub_pop_agesex_grid",
        "Public (split)",
        "grid cell x age band x sex x year",
        ("grid_key", "age_band", "sex", "period"),
        "publicdata",
    ),
    ("graph_node", "Graph", "node", ("node_id",), "publicdata, release"),
    ("graph_edge", "Graph", "edge", ("edge_id",), "publicdata, release"),
    (
        "fact_lineage",
        "Lineage",
        "lineage id x source",
        ("lineage_id", "source_id"),
        "release",
    ),
    ("source_registry", "Lineage", "source", ("source_id",), "publicdata, release"),
    (
        "rules_version",
        "Control",
        "rule x parameter set",
        ("rules_version_id", "parameter_set", "rule_code"),
        "privacy",
    ),
    ("suppression_reason", "Control", "reason code", ("code",), "privacy"),
    (
        "survival_report",
        "Control",
        "parameter set x partition",
        ("parameter_set", "partition_id"),
        "privacy",
    ),
)

CATALOGUE: tuple[CatalogueTable, ...] = _build()
_BY_NAME = {row.name: row for row in CATALOGUE}
