"""Closed technical mappings. Empty pending records do not authorize a fetch."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from .contracts import STATUSES, TABLES

METHOD = "benchmark_native.v1"


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def digest_ok(value: str) -> bool:
    return len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def safe_url(url: str) -> bool:
    parts = urlsplit(url)
    return bool(
        parts.scheme == "https"
        and parts.hostname
        and not parts.username
        and not parts.password
        and not parts.query
        and not parts.fragment
        and parts.port in {None, 443}
    )


@dataclass(frozen=True)
class Policy:
    source_id: str
    confirmed: bool = False
    publisher: str = ""
    page: str = ""
    page_sha256: str = ""
    source_version: str = ""
    licence_words: str = ""
    attribution: str = ""
    access: str = "pending"
    url: str = ""
    reviewed_urls: tuple[str, ...] = ()
    format: str = "json"
    country: str = ""
    indicators: tuple[str, ...] = ()
    dimensions: tuple[str, ...] = ()
    units: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()
    raw_rows: tuple[int, int] = (0, 0)
    selected_rows: tuple[int, int] = (0, 0)
    bytes: tuple[int, int] = (0, 0)
    bound_origin: str = ""
    periods: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    total_digits: int = 0
    fractional_digits: int = 0
    signed: bool = False

    native_columns: tuple[str, ...] = ()
    column_map: dict[str, str] = field(default_factory=dict)
    constants: dict[str, str | None] = field(default_factory=dict)
    status_map: tuple[tuple[str, str, str], ...] = ()
    last_periods: tuple[tuple[str, str, str, str, str], ...] = ()
    members: tuple[tuple[str, int, int, int, int], ...] = ()

    @classmethod
    def from_mapping(cls, data: Any) -> Policy:
        require(isinstance(data, dict), "policy_schema")
        require(set(data) <= {f.name for f in fields(cls)}, "policy_schema")
        require(data.get("source_id") in TABLES, "source_id")
        converted = dict(data)
        for name in (
            "native_columns",
            "reviewed_urls",
            "indicators",
            "dimensions",
            "units",
            "statuses",
            "periods",
            "missing",
            "raw_rows",
            "selected_rows",
            "bytes",
        ):
            if name in converted:
                require(isinstance(converted[name], (list, tuple)), "policy_schema")
                converted[name] = tuple(converted[name])
        for name in ("status_map", "last_periods", "members"):
            if name in converted:
                require(isinstance(converted[name], (list, tuple)), "policy_schema")
                converted[name] = tuple(tuple(v) for v in converted[name])
        result = cls(**converted)
        require(
            type(result.confirmed) is bool and type(result.signed) is bool,
            "policy_schema",
        )
        if not result.confirmed:
            require(not result.url and not result.reviewed_urls, "pending_urls")
            return result
        for name in (
            "publisher",
            "page",
            "source_version",
            "licence_words",
            "attribution",
            "bound_origin",
            "country",
        ):
            value = getattr(result, name)
            require(isinstance(value, str) and bool(value.strip()), "metadata_required")
        require(digest_ok(result.page_sha256), "page_hash")
        require(
            result.access
            in {"visitor", "registration", "sign_in", "robot_check", "paid_tier"},
            "access",
        )
        require(result.format in {"json", "csv", "tsv"}, "format")
        for span in (result.raw_rows, result.selected_rows, result.bytes):
            require(
                len(span) == 2
                and all(type(n) is int for n in span)
                and 0 <= span[0] <= span[1]
                and span[1] > 0,
                "bounds",
            )
        require(
            type(result.total_digits) is int and 0 < result.total_digits <= 1000,
            "precision",
        )
        require(
            type(result.fractional_digits) is int
            and 0 <= result.fractional_digits <= result.total_digits,
            "precision",
        )
        for values in (
            result.indicators,
            result.dimensions,
            result.units,
            result.statuses,
            result.periods,
        ):
            require(
                bool(values)
                and all(isinstance(v, str) and v for v in values)
                and len(set(values)) == len(values),
                "selection",
            )
        require(set(result.statuses) <= set(STATUSES), "status_mapping")
        require(all(isinstance(v, str) for v in result.missing), "missing_tokens")
        require(
            all(safe_url(u) for u in result.reviewed_urls)
            and result.page in result.reviewed_urls
            and result.url in result.reviewed_urls,
            "blocked_host",
        )
        from eii_custodian.publicdata.fetch.decimals import looks_numeric

        from .contracts import Benchmark

        require(not any(looks_numeric(v) for v in result.missing), "missing_tokens")
        if result.native_columns:
            derived = {
                "receipt_sha256",
                "source_row_key",
                "publisher_status",
                "value_status",
            }
            targets = {
                f.name for f in fields(Benchmark) if not f.name.endswith("_value")
            } - derived
            require(
                len(set(result.native_columns)) == len(result.native_columns),
                "native_schema",
            )
            require(
                set(result.column_map.values()) == set(result.native_columns),
                "native_schema",
            )
            require(
                set(result.column_map) | set(result.constants) == targets | {"value"},
                "native_schema",
            )
            require(not set(result.column_map) & set(result.constants), "native_schema")
            require("value" in result.column_map, "native_schema")
            require(
                bool(result.status_map) and bool(result.last_periods), "series_policy"
            )
            require(
                all(len(v) == 3 and v[2] in result.statuses for v in result.status_map),
                "series_policy",
            )
            require(
                len({v[:2] for v in result.status_map}) == len(result.status_map),
                "series_policy",
            )
            require(
                all(
                    len(v) == 5 and v[3] in result.statuses and v[4] in result.periods
                    for v in result.last_periods
                ),
                "series_policy",
            )
            require(
                len({v[:4] for v in result.last_periods}) == len(result.last_periods),
                "series_policy",
            )
        for member in result.members:
            require(len(member) == 5, "member_policy")
            name, low_bytes, high_bytes, low_rows, high_rows = member
            require(
                isinstance(name, str)
                and bool(name)
                and "/" not in name
                and "\\" not in name,
                "member_policy",
            )
            require(
                all(type(v) is int for v in member[1:])
                and 0 <= low_bytes <= high_bytes
                and 0 <= low_rows <= high_rows,
                "member_policy",
            )
        require(
            len({v[0] for v in result.members}) == len(result.members), "member_policy"
        )
        return result


def load_policies(path: Path | None = None) -> dict[str, Policy]:
    target = path or Path(__file__).resolve().parents[4] / "publicdata/benchmarks.yaml"
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
        require(isinstance(data, dict) and set(data) == set(TABLES), "policy_schema")
        result = {key: Policy.from_mapping(value) for key, value in data.items()}
        require(
            all(key == value.source_id for key, value in result.items()), "source_id"
        )
        return result
    except (OSError, TypeError, yaml.YAMLError):
        raise ValueError("benchmark configuration_unreadable") from None
