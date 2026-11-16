"""Closed Gravity metadata. Pending source facts never activate a download."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, cast

import yaml

from eii_custodian.publicdata.fetch.allowlist import reviewed_url
from eii_custodian.publicdata.fetch.decimals import is_zero_token

METHOD = "eii_custodian.publicdata.gravity.parse.parse_archive@v1"
SOURCE_ID = "cepii_gravity"
TABLES = ("pub_gravity_bilateral", "pub_gravity_country")
MEASURE_FIELDS = frozenset({"distance", "gdp_origin", "gdp_destination"})
FLAG_FIELDS = frozenset(
    {"contig", "common_language", "colonial_link", "trade_agreement"}
)
SCHEMAS = {
    "country": {"country_code", "source_name"},
    "bilateral": {
        "year",
        "origin_code",
        "destination_code",
        "distance",
        "contig",
        "common_language",
        "colonial_link",
        "trade_agreement",
        "gdp_origin",
        "gdp_destination",
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


class GravityError(Exception):
    """Fixed check identifier only; never interpolate upstream content."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise GravityError(reason)


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


def _no_zero_tokens(tokens: tuple[str, ...]) -> None:
    require(all(not is_zero_token(token) for token in tokens), "missing_is_zero")


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
        _no_zero_tokens(missing)
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
class Config:
    config_version: str
    method_version: str
    source_version: str
    access: str
    confirmed: bool
    bound_origin: str
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
    period_first: int
    period_last: int
    year_selection: str
    archive_bytes: tuple[int, int]
    raw_rows: tuple[int, int]
    member_count: tuple[int, int]
    publisher_sha256: str
    flag_tokens: tuple[str, ...]
    flag_missing: tuple[str, ...]
    measures: tuple[Measure, ...]
    members: tuple[Member, ...]

    @classmethod
    def from_mapping(cls, value: object) -> Config:
        row = mapping(value, {field.name for field in fields(cls)})
        require(type(row["confirmed"]) is bool, "configuration_type")
        confirmed = cast(bool, row["confirmed"])
        kw: dict[str, object] = {}
        numbers = {"country_width", "period_first", "period_last"}
        for field in fields(cls):
            name, item = field.name, row[field.name]
            if name in numbers:
                kw[name] = integer(item)
            elif name in {"archive_bytes", "raw_rows", "member_count"}:
                kw[name] = bounds(item)
            elif name in {"reviewed_urls", "flag_tokens", "flag_missing"}:
                kw[name] = strings(item)
            elif name == "measures":
                require(isinstance(item, list), "configuration_type")
                kw[name] = tuple(Measure.load(one) for one in cast(list[object], item))
            elif name == "members":
                require(isinstance(item, list), "configuration_type")
                kw[name] = tuple(Member.load(one) for one in cast(list[object], item))
            elif name == "confirmed":
                kw[name] = confirmed
            else:
                kw[name] = text(item, empty=not confirmed or name == "publisher_sha256")
        result = cls(**cast(dict[str, Any], kw))
        require(
            result.config_version == "gravity-v1" and result.method_version == "v1",
            "method_version",
        )
        require(result.access in _ACCESS, "access_state")
        require(result.publisher_mapping == "pending", "publisher_mapping")
        require(
            result.bound_origin in {"pending", "assumption", "source_evidence"},
            "bounds_origin",
        )
        require(set(result.flag_tokens) == {"0", "1"}, "flag_tokens")
        require(set(result.flag_missing).isdisjoint({"0", "1"}), "missing_is_zero")
        _no_zero_tokens(result.flag_missing)
        require(1 <= result.country_width, "code_width")
        require(1 <= result.period_first <= result.period_last <= 9999, "period_bounds")
        require(
            result.year_selection in {"pending", "native", "narrower"}, "year_selection"
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
                not result.publisher_sha256 or digest_ok(result.publisher_sha256),
                "archive_checksum",
            )
            names = [measure.name for measure in result.measures]
            require(
                set(names) == set(MEASURE_FIELDS) and len(names) == len(MEASURE_FIELDS),
                "measure_fields",
            )
            require(
                len({member.name for member in result.members}) == len(result.members),
                "inventory",
            )
            require(
                sum(member.kind == "country" for member in result.members) == 1
                and sum(member.kind == "bilateral" for member in result.members) == 1,
                "members",
            )
            require(
                result.member_count[0] <= len(result.members) <= result.member_count[1],
                "member_count",
            )
        return result


def load_config(path: Path | None = None) -> Config:
    target = path or Path(__file__).resolve().parents[4] / "publicdata/gravity.yaml"
    try:
        return Config.from_mapping(yaml.safe_load(target.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError):
        raise GravityError("configuration_unreadable") from None
