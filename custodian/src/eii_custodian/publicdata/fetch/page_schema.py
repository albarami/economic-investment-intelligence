"""Versioned closed declarations and recursive JSON types for reviewed page shapes."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .page_html import ShapeError

SCHOOL_FIELDS = tuple(
    "objectid,name,aname,category,category_a,eng_type,type,adoptedcurriculum,operationalstatus,mncp_code,mncp_name,mncp_name_en,district_code,district_name,district_name_en,lat,long_,students_n,staff_num".split(
        ","
    )
)
SHAPES = {
    "embedded_json": {
        "element",
        "attribute",
        "id",
        "type",
        "copies",
        "record_path",
        "more_path",
        "page_bound",
        "record_schema",
        "fields",
    },
    "xlsx_sheet": {"discovery", "sheets"},
    "html_blocks": {
        "heading",
        "scope",
        "layouts",
        "unit",
        "currency",
        "pages",
        "discovery",
    },
    "html_table": {
        "profile",
        "selector",
        "headers",
        "sections",
        "total_selector",
        "total_prefix",
        "last_selector",
        "path_template",
    },
    "arcgis_query": {
        "layer",
        "fields",
        "record_path",
        "attribute_path",
        "geometry",
        "spatial_reference",
        "order_by",
        "page_size",
        "where",
        "record_schema",
    },
    "fc_company_cards": {
        "pane",
        "card",
        "fields",
        "pager_targets",
        "form_fields",
        "progress_fields",
        "projection",
        "producer",
    },
    "refusal": {"reason", "observed_utc", "decision"},
}
COMMON = {
    "version",
    "kind",
    "url",
    "reviewed_urls",
    "columns",
    "as_of",
    "publisher_date",
    "period_fields",
    "bounds_basis",
    "bounds_reason",
    "pins",
    "evidence",
    "hold",
    "shape",
    "max_bytes",
}


def keys(value: object, expected: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ShapeError("schema_missing")
    return value


def path(value: Any, tokens: object) -> Any:
    if not isinstance(tokens, list) or any(
        not isinstance(t, str) or not t for t in tokens
    ):
        raise ShapeError("schema_missing")
    for token in tokens:
        if not isinstance(value, dict) or token not in value:
            raise ShapeError("schema_missing")
        value = value[token]
    return value


def validate_schema(value: object) -> None:
    if not isinstance(value, dict):
        raise ShapeError("schema_missing")
    kind = value.get("kind")
    expected = {"kind", "nullable", "optional"}
    if kind == "object":
        expected.add("fields")
    elif kind == "array":
        expected.add("items")
    elif kind not in {"string", "integer", "number", "boolean"}:
        raise ShapeError("schema_missing")
    keys(value, expected)
    if type(value["nullable"]) is not bool or type(value["optional"]) is not bool:
        raise ShapeError("schema_missing")
    if kind == "object":
        if not isinstance(value["fields"], dict) or any(
            not isinstance(k, str) or not k for k in value["fields"]
        ):
            raise ShapeError("schema_missing")
        for child in value["fields"].values():
            validate_schema(child)
    if kind == "array":
        validate_schema(value["items"])


def typed(value: Any, spec: Mapping[str, Any]) -> None:
    kind = spec["kind"]
    if value is None and spec["nullable"]:
        return
    if kind == "object" and isinstance(value, dict):
        fields = spec["fields"]
        if set(value) - set(fields) or any(
            k not in value and not s["optional"] for k, s in fields.items()
        ):
            raise ShapeError("schema_missing")
        for k, item in value.items():
            typed(item, fields[k])
        return
    if kind == "array" and isinstance(value, list):
        for child in value:
            typed(child, spec["items"])
        return
    if kind == "string" and isinstance(value, str):
        return
    if kind == "boolean" and type(value) is bool:
        return
    if kind == "integer" and type(value) is int:
        return
    if kind == "number" and type(value) in {int, float, Decimal}:
        if Decimal(str(value)).is_finite():
            return
    raise ShapeError("schema_missing")


def scalar(value: object, kind: str) -> object:
    if value is None or value == "":
        return None
    try:
        if kind == "string" and isinstance(value, str):
            return value
        if (
            kind == "integer"
            and type(value) is not bool
            and re.fullmatch(r"-?[0-9]+", str(value))
        ):
            return int(str(value))
        if kind == "number" and type(value) is not bool:
            number = Decimal(str(value))
            if number.is_finite():
                return str(number)
    except (ValueError, InvalidOperation):
        pass
    raise ShapeError("schema_missing")


def json_body(body: bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ShapeError("schema_missing")
            result[key] = value
        return result

    def bad(_: str) -> Any:
        raise ShapeError("schema_missing")

    try:
        return json.loads(
            body, parse_float=Decimal, object_pairs_hook=unique, parse_constant=bad
        )
    except (ValueError, UnicodeError):
        raise ShapeError("schema_missing") from None


def validate(review: Mapping[str, Any]) -> None:
    if review.get("as_of") != "retrieval_date":
        raise ShapeError("snapshot_date_missing")
    keys(dict(review), COMMON | ({"profile"} if "profile" in review else set()))
    if (
        type(review["version"]) is not int
        or review["version"] != 2
        or not isinstance(review["kind"], str)
        or review["kind"] not in SHAPES
    ):
        raise ShapeError("schema_missing")
    shape = keys(review["shape"], SHAPES[review["kind"]])
    if not isinstance(review["evidence"], str) or not review["evidence"]:
        raise ShapeError("schema_missing")
    if review["max_bytes"] is not None and (
        type(review["max_bytes"]) is not int or review["max_bytes"] < 1
    ):
        raise ShapeError("schema_missing")
    columns = review["columns"]
    if (
        not isinstance(columns, list)
        or any(
            not isinstance(c, list)
            or len(c) != 2
            or not isinstance(c[0], str)
            or c[1] not in {"string", "integer", "number"}
            for c in columns
        )
        or len({c[0] for c in columns}) != len(columns)
    ):
        raise ShapeError("schema_missing")
    if not isinstance(review["period_fields"], list) or not set(
        review["period_fields"]
    ) <= {c[0] for c in columns}:
        raise ShapeError("schema_missing")
    if review["publisher_date"] is not None:
        try:
            value = review["publisher_date"]
            if (
                not isinstance(value, str)
                or date.fromisoformat(value).isoformat() != value
            ):
                raise ValueError
        except ValueError:
            raise ShapeError("snapshot_date_missing") from None
    if review["kind"] == "fc_company_cards":
        from ..fc_register.constants import COLUMNS, SHAPE, URL

        if (
            shape != SHAPE
            or columns != [list(c) for c in COLUMNS]
            or review["url"] != URL
        ):
            raise ShapeError("schema_missing")
    if review["kind"] == "arcgis_query":
        if (
            not isinstance(shape["layer"], str)
            or shape["layer"] + "?f=json" != review["url"]
        ):
            raise ShapeError("blocked_host")
        if shape["record_path"] != ["features"] or shape["attribute_path"] != [
            "attributes"
        ]:
            raise ShapeError("schema_missing")
        if (
            shape["fields"] != list(SCHOOL_FIELDS)
            or shape["order_by"] != "objectid"
            or shape["where"] != "1=1"
        ):
            raise ShapeError("school_field_refused")
        if set(shape["record_schema"].get("fields", {})) != set(SCHOOL_FIELDS):
            raise ShapeError("school_field_refused")
        if (
            type(shape["page_size"]) is not int
            or shape["page_size"] < 1
            or shape["geometry"] != "esriGeometryPoint"
        ):
            raise ShapeError("schema_missing")
    if "record_schema" in shape:
        # Missing nested evidence is a declared hold, not an invented schema.
        if review["hold"] is None:
            validate_schema(shape["record_schema"])
    if review["kind"] == "embedded_json":
        if (
            shape["page_bound"] != 1
            or shape["copies"] not in {1, 2}
            or (shape["attribute"] is None) != (shape["element"] == "script")
        ):
            raise ShapeError("schema_missing")
        if set(shape["fields"]) != {c[0] for c in columns}:
            raise ShapeError("schema_missing")
    for discovery in [shape["discovery"]] if "discovery" in shape else []:
        if discovery is not None:
            keys(
                discovery,
                {
                    "url",
                    "record_path",
                    "link_path",
                    "length_path",
                    "modified_path",
                    "count_header",
                    "pages_header",
                },
            )
    if review["kind"] == "html_blocks":
        if shape["layouts"] != ["single", "double"] or not isinstance(
            shape["pages"], list
        ):
            raise ShapeError("schema_missing")
        for page in shape["pages"]:
            keys(page, {"url", "state", "layout"})
            if page["state"] not in {"tariff", "no tariff on page"} or page[
                "layout"
            ] not in {"single", "double", None}:
                raise ShapeError("schema_missing")
    if review["kind"] == "html_table":
        if shape["profile"] not in {"classified", "awards"}:
            raise ShapeError("schema_missing")
        for section in shape["sections"]:
            keys(section, {"heading", "headers", "date_in_heading"})
            if type(section["date_in_heading"]) is not bool:
                raise ShapeError("schema_missing")
        if (
            shape["profile"] == "classified"
            and shape["path_template"].format(page=1) != review["url"]
        ):
            raise ShapeError("blocked_host")
    if review["kind"] == "xlsx_sheet":
        for sheet in shape["sheets"]:
            keys(
                sheet,
                {
                    "name",
                    "part",
                    "relationship",
                    "sheet_id",
                    "header_cells",
                    "merged_cells",
                    "annual_rows",
                    "quarter_rows",
                    "blank_row",
                    "period_cell",
                    "year_column",
                    "quarter_column",
                    "quarter_label_column",
                    "carry_year",
                    "footer_row",
                    "footer_last_column",
                    "columns",
                },
            )
            if sheet["carry_year"] != "first_quarter":
                raise ShapeError("schema_missing")
    if review["hold"] is not None and review["hold"] not in {
        "schema_evidence_pending",
        "acquisition_bound_unconfirmed",
        "awards_profile_pending",
    }:
        raise ShapeError("schema_missing")


def period(
    rows: list[dict[str, object]], fields: list[str]
) -> tuple[str | None, str | None]:
    values = []
    for row in rows:
        for field in fields:
            value = row.get(field)
            if not isinstance(value, str) or not value:
                raise ShapeError("snapshot_date_missing")
            try:
                if re.fullmatch(r"[0-9]{4}(?:-Q[1-4])?", value):
                    if not 1 <= int(value[:4]) <= 9999:
                        raise ValueError
                else:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                raise ShapeError("snapshot_date_missing") from None
            values.append(value)
    return (min(values), max(values)) if values else (None, None)
