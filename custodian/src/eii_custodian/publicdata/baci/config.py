"""Closed BACI metadata. Pending source facts never activate a download."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, cast

import yaml

from eii_custodian.publicdata.fetch.allowlist import reviewed_url

METHOD = "eii_custodian.publicdata.baci.parse.parse_archive@v1"
TABLES = ("pub_baci_trade", "pub_baci_country", "pub_baci_product")
SCHEMAS = {
    "trade": {
        "year",
        "exporter_code",
        "importer_code",
        "hs_code",
        "value",
        "quantity",
        "hs_revision",
    },
    "country": {"country_code", "source_name", "iso3"},
    "product": {"hs_code", "source_description", "hs_revision"},
}


class BaciError(Exception):
    """Fixed check identifier only; never interpolate upstream content."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise BaciError(reason)


def digest_ok(value: str) -> bool:
    return re.fullmatch(r"[a-f0-9]{64}", value) is not None


def safe_url(url: str) -> bool:
    """BACI addresses carry no credentials, query, fragment or control text."""
    return reviewed_url(url)


def mapping(value: object, keys: set[str]) -> dict[str, object]:
    require(isinstance(value, dict) and set(value) == keys, "configuration_fields")
    return cast(dict[str, object], value)


def text(value: object, *, empty: bool = False) -> str:
    require(isinstance(value, str), "configuration_type")
    result = cast(str, value)
    require(empty or bool(result.strip()), "metadata_missing")
    return result


def integer(value: object) -> int:
    require(type(value) is int, "configuration_count")
    return cast(int, value)


def bounds(value: object) -> tuple[int, int]:
    require(isinstance(value, list) and len(value) == 2, "configuration_bounds")
    items = cast(list[object], value)
    low, high = integer(items[0]), integer(items[1])
    require(0 <= low <= high, "configuration_bounds")
    return low, high


def strings(value: object) -> tuple[str, ...]:
    require(isinstance(value, list), "configuration_type")
    return tuple(text(item) for item in cast(list[object], value))


@dataclass(frozen=True)
class Member:
    name: str
    kind: str
    year: int | None
    bytes: tuple[int, int]
    rows: tuple[int, int]
    sha256: str
    columns: dict[str, str]
    header: tuple[str, ...]

    @classmethod
    def load(cls, value: object) -> Member:
        row = mapping(value, {field.name for field in fields(cls)})
        name, kind = text(row["name"]), text(row["kind"])
        require(re.fullmatch(r"[A-Za-z0-9_-]+\.csv", name) is not None, "member_name")
        require(kind in SCHEMAS, "member_kind")
        year = None if row["year"] is None else integer(row["year"])
        require((kind == "trade") == (year is not None), "member_year")
        columns = row["columns"]
        require(isinstance(columns, dict), "member_schema")
        columns = {
            text(k): text(v) for k, v in cast(dict[object, object], columns).items()
        }
        require(
            set(columns.values()) == SCHEMAS[kind]
            and len(columns) == len(SCHEMAS[kind]),
            "member_schema",
        )
        header = strings(row["header"])
        require(
            set(header) == set(columns) and len(header) == len(columns), "member_schema"
        )
        checksum = text(row["sha256"], empty=True)
        require(not checksum or digest_ok(checksum), "member_checksum")
        return cls(
            name,
            kind,
            year,
            bounds(row["bytes"]),
            bounds(row["rows"]),
            checksum,
            columns,
            header,
        )


@dataclass(frozen=True)
class Config:
    config_version: str
    method_version: str
    source_version: str
    hs_revision: str
    access: str
    confirmed: bool
    reviewed_urls: tuple[str, ...]
    publisher: str
    page: str
    page_sha256: str
    attribution: str
    evidence: str
    qatar_key: str
    country_width: int
    product_width: int
    value_unit: str
    quantity_unit: str
    currency: str
    valuation_basis: str
    reconciliation: str
    missing_quantity: tuple[str, ...]
    period_first: int
    period_last: int
    archive_bytes: tuple[int, int]
    raw_rows: tuple[int, int]
    total_digits: int
    fractional_digits: int
    publisher_sha256: str
    members: tuple[Member, ...]

    @classmethod
    def from_mapping(cls, value: object) -> Config:
        row = mapping(value, {field.name for field in fields(cls)})
        require(type(row["confirmed"]) is bool, "configuration_type")
        kw: dict[str, object] = {}
        numbers = {
            "country_width",
            "product_width",
            "period_first",
            "period_last",
            "total_digits",
            "fractional_digits",
        }
        for field in fields(cls):
            name, item = field.name, row[field.name]
            if name in numbers:
                kw[name] = integer(item)
            elif name in {"archive_bytes", "raw_rows"}:
                kw[name] = bounds(item)
            elif name in {"reviewed_urls", "missing_quantity"}:
                kw[name] = strings(item)
            elif name == "members":
                require(isinstance(item, list), "configuration_type")
                kw[name] = tuple(
                    Member.load(member) for member in cast(list[object], item)
                )
            elif name == "confirmed":
                kw[name] = item
            else:
                kw[name] = text(
                    item, empty=not bool(row["confirmed"]) or name == "publisher_sha256"
                )
        # All fields have been checked above; construction does not coerce values.
        result = cls(**cast(dict[str, Any], kw))
        require(
            result.config_version == "baci-v1" and result.method_version == "v1",
            "method_version",
        )
        require(
            result.access
            in {
                "unconfirmed",
                "visitor",
                "registration",
                "sign_in",
                "robot_check",
                "paid_tier",
            },
            "access_state",
        )
        require(
            0 <= result.fractional_digits <= result.total_digits
            and result.total_digits > 0,
            "decimal_limits",
        )
        require(1 <= result.country_width and 1 <= result.product_width, "code_width")
        require(1 <= result.period_first <= result.period_last <= 9999, "period_bounds")
        if result.confirmed:
            require(result.access != "unconfirmed", "access_state")
            require(digest_ok(result.page_sha256), "page_hash")
            require(
                result.page in result.reviewed_urls
                and all(safe_url(url) for url in result.reviewed_urls),
                "blocked_host",
            )
            require(
                not result.publisher_sha256 or digest_ok(result.publisher_sha256),
                "archive_checksum",
            )
            require(
                len({m.name for m in result.members}) == len(result.members),
                "inventory",
            )
            require(
                sum(m.kind == "country" for m in result.members) == 1
                and sum(m.kind == "product" for m in result.members) == 1,
                "dictionaries",
            )
            years = [
                m.year
                for m in result.members
                if m.kind == "trade" and m.year is not None
            ]
            require(
                sorted(years)
                == list(range(result.period_first, result.period_last + 1)),
                "year_coverage",
            )
        return result


def load_config(path: Path | None = None) -> Config:
    target = path or Path(__file__).resolve().parents[4] / "publicdata/baci.yaml"
    try:
        return Config.from_mapping(yaml.safe_load(target.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError):
        raise BaciError("configuration_unreadable") from None
