"""Closed fixture adapter; all rows validated before country/indicator selection."""

import csv
import io
import json
from dataclasses import dataclass, fields, replace
from typing import Any, cast

from eii_custodian.publicdata.fetch.bounded import within
from eii_custodian.publicdata.fetch.decimals import (
    DecimalRefusal,
    exact_decimal,
    read_measure,
)

from .config import Policy, require
from .contracts import STATUSES, Benchmark, validate_row


@dataclass(frozen=True)
class Parsed:
    rows: tuple[Benchmark, ...]
    coverage: dict[str, Any]


def _decode(body: bytes, policy: Policy) -> list[dict[str, Any]]:
    text = body.decode("utf-8")
    if policy.format == "json":
        raw = json.loads(text)
    else:
        reader = csv.DictReader(
            io.StringIO(text), delimiter="," if policy.format == "csv" else "\t"
        )
        if policy.native_columns:
            require(
                tuple(reader.fieldnames or ()) == policy.native_columns, "native_schema"
            )
        raw = list(reader)
    require(isinstance(raw, list), "row_schema")
    return cast(list[dict[str, Any]], raw)


def _native(item: dict[str, Any], policy: Policy, index: int) -> dict[str, Any]:
    require(set(item) == set(policy.native_columns), "native_schema")
    require(all(isinstance(v, str) for v in item.values()), "native_types")
    mapped = {
        **policy.constants,
        **{key: item[column] for key, column in policy.column_map.items()},
    }
    status = {(i, p): s for i, p, s in policy.status_map}.get(
        (mapped["indicator_code"], mapped["period"])
    )
    require(status in STATUSES, "status_mapping")
    value, value_status = read_measure(
        mapped.pop("value"),
        total_digits=policy.total_digits,
        fractional_digits=policy.fractional_digits,
        signed=policy.signed,
        missing=policy.missing,
    )
    mapped.update(
        publisher_status=status,
        value_status=value_status,
        receipt_sha256="a" * 64,
        source_row_key=f"native-row-{index}",
    )
    for name in STATUSES:
        mapped[name + "_value"] = value if name == status else None
    return mapped


def parse(body: bytes, policy: Policy, receipt_hash: str) -> tuple[Benchmark, ...]:
    return parse_with_coverage(body, policy, receipt_hash).rows


def parse_with_coverage(body: bytes, policy: Policy, receipt_hash: str) -> Parsed:
    import hashlib
    import zipfile

    require(policy.confirmed, "benchmark_metadata_unconfirmed")
    require(within(len(body), policy.bytes), "data_bytes")
    try:
        inventory = []
        raw = []
        if policy.members:
            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                require(
                    sorted(archive.namelist()) == sorted(m[0] for m in policy.members),
                    "member_inventory",
                )
                for name, low_bytes, high_bytes, low_rows, high_rows in policy.members:
                    info = archive.getinfo(name)
                    require(
                        within(info.file_size, (low_bytes, high_bytes)), "member_bytes"
                    )
                    with archive.open(info) as member:
                        content = member.read(high_bytes + 1)
                    require(
                        within(len(content), (low_bytes, high_bytes)), "member_bytes"
                    )
                    items = _decode(content, policy)
                    require(within(len(items), (low_rows, high_rows)), "member_rows")
                    inventory.append(
                        {
                            "name": name,
                            "sha256": hashlib.sha256(content).hexdigest(),
                            "bytes": len(content),
                            "rows": len(items),
                        }
                    )
                    raw.extend(items)
        else:
            raw = _decode(body, policy)
        require(within(len(raw), policy.raw_rows), "raw_bounds")
        selected = []
        seen: set[tuple[str, ...]] = set()
        for index, item in enumerate(raw):
            if policy.native_columns:
                item = _native(item, policy, index)
            require(
                isinstance(item, dict)
                and set(item) == {f.name for f in fields(Benchmark)},
                "row_schema",
            )
            if policy.format != "json":
                item = {
                    key: None
                    if value == ""
                    and (key.endswith("_value") or key in {"currency", "price_basis"})
                    else value
                    for key, value in item.items()
                }
            row = Benchmark(**item)
            validate_row(row)
            require(
                row.source_id == policy.source_id
                and row.source_version == policy.source_version,
                "source_version",
            )
            require(
                row.unit in policy.units
                and row.publisher_status in policy.statuses
                and row.dimension_key in policy.dimensions
                and row.period in policy.periods,
                "row_mapping",
            )
            for status in STATUSES:
                value = getattr(row, status + "_value")
                if value is not None:
                    exact_decimal(
                        value,
                        total_digits=policy.total_digits,
                        fractional_digits=policy.fractional_digits,
                        signed=policy.signed,
                    )
            key = tuple(
                str(getattr(row, name))
                for name in (
                    "source_id",
                    "source_version",
                    "country_code",
                    "indicator_code",
                    "dimension_key",
                    "frequency",
                    "period",
                    "publisher_status",
                    "unit",
                    "currency",
                    "scale",
                    "price_basis",
                )
            )
            require(key not in seen, "duplicate_key")
            seen.add(key)
            if (
                row.country_code == policy.country
                and row.indicator_code in policy.indicators
            ):
                selected.append(replace(row, receipt_sha256=receipt_hash))
        require(within(len(selected), policy.selected_rows), "selected_bounds")
        actual_last: dict[tuple[str, str, str, str], str] = {}
        for row in selected:
            series = (
                row.country_code,
                row.indicator_code,
                row.dimension_key,
                row.publisher_status,
            )
            actual_last[series] = max(actual_last.get(series, ""), row.period)
        if policy.last_periods:
            expected_last = {v[:4]: v[4] for v in policy.last_periods}
            require(actual_last == expected_last, "last_period")
        return Parsed(
            tuple(selected),
            {
                "raw": len(raw),
                "selected": len(selected),
                "excluded": len(raw) - len(selected),
                "missing": sum(r.value_status == "source_missing" for r in selected),
                "last_periods": [
                    [*key, value] for key, value in sorted(actual_last.items())
                ],
                "members": inventory,
            },
        )
    except (
        UnicodeError,
        TypeError,
        KeyError,
        csv.Error,
        DecimalRefusal,
        zipfile.BadZipFile,
    ):
        raise ValueError("benchmark row_schema") from None
