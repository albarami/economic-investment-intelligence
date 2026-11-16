"""Closed Atlas metadata. Finished downloads only; pending facts do not activate."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, cast

import yaml

from eii_custodian.publicdata.fetch.allowlist import reviewed_url
from eii_custodian.publicdata.fetch.decimals import is_zero_token

METHOD = "eii_custodian.publicdata.atlas.parse.parse_archives@v1"
SOURCE_ID = "atlas_complexity"
FINISHED = ("country_product_year", "country_partner_product_year")
TABLES = (
    "pub_atlas_country_product_year",
    "pub_atlas_cpy_country",
    "pub_atlas_cpy_product",
    "pub_atlas_country_partner_product_year",
    "pub_atlas_cppy_country",
    "pub_atlas_cppy_product",
)
GRAIN_TABLES = {
    "country_product_year": TABLES[0],
    "country_partner_product_year": TABLES[3],
}
COUNTRY_TABLES = {
    "country_product_year": TABLES[1],
    "country_partner_product_year": TABLES[4],
}
PRODUCT_TABLES = {
    "country_product_year": TABLES[2],
    "country_partner_product_year": TABLES[5],
}
SCHEMAS = {
    "country": {"country_code", "source_name"},
    "product": {"product_code", "source_description", "hs_revision"},
    "country_product_year": {
        "year",
        "country_code",
        "product_code",
        "hs_revision",
        "finished_measure",
    },
    "country_partner_product_year": {
        "year",
        "reporter_code",
        "partner_code",
        "product_code",
        "hs_revision",
        "finished_measure",
    },
}
_ACCESS = frozenset(
    {
        "unconfirmed",
        "visitor",
        "registration",
        "sign_in",
        "robot_check",
        "paid_tier",
    }
)


class AtlasError(Exception):
    """Fixed check identifier only; never interpolate upstream content."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise AtlasError(reason)


def digest_ok(value: str) -> bool:
    return re.fullmatch(r"[a-f0-9]{64}", value) is not None


def safe_url(url: str) -> bool:
    """Reviewed data URLs reject credentials, queries, fragments and control text."""
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
class Measure:
    name: str
    total_digits: int
    fractional_digits: int
    signed: bool
    missing: tuple[str, ...]
    unit: str

    @classmethod
    def load(cls, value: object) -> Measure:
        row = mapping(value, {field.name for field in fields(cls)})
        require(type(row["signed"]) is bool, "configuration_type")
        total, fractional = (
            integer(row["total_digits"]),
            integer(row["fractional_digits"]),
        )
        require(0 <= fractional <= total and total > 0, "decimal_limits")
        missing = strings(row["missing"])
        require(len(set(missing)) == len(missing), "missing_tokens")
        require(all(not is_zero_token(token) for token in missing), "missing_is_zero")
        return cls(
            text(row["name"]),
            total,
            fractional,
            cast(bool, row["signed"]),
            missing,
            text(row["unit"]),
        )


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
        require(kind != "rebuild", "rebuild_refused")
        require(kind in SCHEMAS, "member_kind")
        require(row["year"] is None, "member_year")
        columns = row["columns"]
        require(isinstance(columns, dict), "member_schema")
        mapped = {
            text(key): text(item)
            for key, item in cast(dict[object, object], columns).items()
        }
        require(
            set(mapped.values()) == SCHEMAS[kind] and len(mapped) == len(SCHEMAS[kind]),
            "member_schema",
        )
        header = strings(row["header"])
        require(
            set(header) == set(mapped) and len(header) == len(mapped), "member_schema"
        )
        checksum = text(row["sha256"], empty=True)
        require(not checksum or digest_ok(checksum), "member_checksum")
        return cls(
            name,
            kind,
            None,
            bounds(row["bytes"]),
            bounds(row["rows"]),
            checksum,
            mapped,
            header,
        )


@dataclass(frozen=True)
class Download:
    grain: str
    url: str
    archive_bytes: tuple[int, int]
    raw_rows: tuple[int, int]
    member_count: tuple[int, int]
    publisher_sha256: str
    members: tuple[Member, ...]

    @classmethod
    def load(cls, value: object, *, confirmed: bool) -> Download:
        row = mapping(value, {field.name for field in fields(cls)})
        grain = text(row["grain"])
        require(grain in FINISHED, "rebuild_refused")
        members_value = row["members"]
        require(isinstance(members_value, list), "configuration_type")
        members = tuple(Member.load(item) for item in cast(list[object], members_value))
        result = cls(
            grain,
            text(row["url"], empty=not confirmed),
            bounds(row["archive_bytes"]),
            bounds(row["raw_rows"]),
            bounds(row["member_count"]),
            text(row["publisher_sha256"], empty=True),
            members,
        )
        if confirmed:
            require(
                result.member_count[0] <= len(members) <= result.member_count[1],
                "member_count",
            )
            require(
                sum(member.kind == "country" for member in members) == 1, "dictionaries"
            )
            require(
                sum(member.kind == "product" for member in members) == 1, "dictionaries"
            )
            require(
                sum(member.kind == grain for member in members) == 1, "finished_grain"
            )
            require(
                all(member.kind != "rebuild" for member in members), "rebuild_refused"
            )
        return result


@dataclass(frozen=True)
class Config:
    config_version: str
    method_version: str
    source_version: str
    access: str
    confirmed: bool
    bound_origin: str
    finished_only: bool
    reviewed_urls: tuple[str, ...]
    publisher: str
    page: str
    page_sha256: str
    attribution: str
    evidence: str
    licence_words: str
    hs_revision: str
    publisher_mapping: str
    qatar_key: str
    country_width: int
    product_width: int
    period_first: int
    period_last: int
    year_selection: str
    raw_rows: tuple[int, int]
    measures: tuple[Measure, ...]
    downloads: tuple[Download, ...]

    @classmethod
    def from_mapping(cls, value: object) -> Config:
        row = mapping(value, {field.name for field in fields(cls)})
        require(type(row["confirmed"]) is bool, "configuration_type")
        require(type(row["finished_only"]) is bool, "configuration_type")
        confirmed = cast(bool, row["confirmed"])
        require(row["finished_only"] is True, "rebuild_refused")
        downloads_value = row["downloads"]
        require(isinstance(downloads_value, list), "configuration_type")
        downloads = tuple(
            Download.load(item, confirmed=confirmed)
            for item in cast(list[object], downloads_value)
        )
        measures_value = row["measures"]
        require(isinstance(measures_value, list), "configuration_type")
        measures = tuple(
            Measure.load(item) for item in cast(list[object], measures_value)
        )
        kw: dict[str, object] = {
            "confirmed": confirmed,
            "finished_only": True,
            "downloads": downloads,
            "measures": measures,
            "country_width": integer(row["country_width"]),
            "product_width": integer(row["product_width"]),
            "period_first": integer(row["period_first"]),
            "period_last": integer(row["period_last"]),
            "raw_rows": bounds(row["raw_rows"]),
            "reviewed_urls": strings(row["reviewed_urls"]),
        }
        for name in (
            "config_version",
            "method_version",
            "source_version",
            "access",
            "bound_origin",
            "publisher",
            "page",
            "page_sha256",
            "attribution",
            "evidence",
            "licence_words",
            "hs_revision",
            "publisher_mapping",
            "qatar_key",
            "year_selection",
        ):
            kw[name] = text(row[name], empty=not confirmed)
        result = cls(**cast(dict[str, Any], kw))
        require(
            result.config_version == "atlas-v1" and result.method_version == "v1",
            "method_version",
        )
        require(result.access in _ACCESS, "access_state")
        require(result.publisher_mapping == "pending", "publisher_mapping")
        require(
            result.bound_origin in {"pending", "assumption", "source_evidence"},
            "bounds_origin",
        )
        require(1 <= result.country_width and 1 <= result.product_width, "code_width")
        require(1 <= result.period_first <= result.period_last <= 9999, "period_bounds")
        require(
            result.year_selection in {"pending", "native", "narrower"}, "year_selection"
        )
        require(
            tuple(item.grain for item in result.downloads) == FINISHED, "download_order"
        )
        if result.confirmed:
            require(result.bound_origin != "pending", "bounds_unconfirmed")
            require(result.year_selection != "pending", "year_selection")
            require(result.access != "unconfirmed", "access_state")
            require(bool(result.hs_revision.strip()), "revision")
            require(digest_ok(result.page_sha256), "page_hash")
            require(
                result.page in result.reviewed_urls
                and all(safe_url(url) for url in result.reviewed_urls),
                "blocked_host",
            )
            require(
                all(
                    item.url in result.reviewed_urls and safe_url(item.url)
                    for item in result.downloads
                ),
                "blocked_host",
            )
            require(
                len({item.url for item in result.downloads}) == len(result.downloads),
                "download_url",
            )
            names = [measure.name for measure in result.measures]
            require(names == ["finished_measure"], "measure_fields")
            require(
                all(
                    not item.publisher_sha256 or digest_ok(item.publisher_sha256)
                    for item in result.downloads
                ),
                "archive_checksum",
            )
        return result


def load_config(path: Path | None = None) -> Config:
    target = path or Path(__file__).resolve().parents[4] / "publicdata/atlas.yaml"
    try:
        return Config.from_mapping(yaml.safe_load(target.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError):
        raise AtlasError("configuration_unreadable") from None
