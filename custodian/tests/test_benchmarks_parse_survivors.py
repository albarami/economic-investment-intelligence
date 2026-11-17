"""Invented parser records and exact coverage/refusal contracts."""

import csv
import hashlib
import io
import json
from dataclasses import asdict, replace

import pytest

from eii_custodian.publicdata.benchmarks.parse import parse, parse_with_coverage

from .test_benchmark_native import archive, native, payload
from .test_benchmarks import row
from .test_benchmarks_fetch import policy


def refusal(caught, expected):
    assert str(caught.value) == expected


@pytest.mark.parametrize(
    "plant,expected",
    [
        ("header", "native_schema"),
        ("status", "status_mapping"),
        ("inventory", "member_inventory"),
        ("member_bytes", "member_bytes"),
        ("member_rows", "member_rows"),
        ("duplicate", "duplicate_key"),
        ("last", "last_period"),
    ],
)
def test_exact_parser_refusals(plant, expected):
    p, body = native(), payload()
    if plant == "header":
        body = b"\n"
    elif plant == "status":
        p = replace(p, status_map=())
    elif plant == "duplicate":
        body += body.splitlines(keepends=True)[1]
    elif plant == "last":
        p = replace(
            p,
            last_periods=(
                (
                    "invented-country",
                    "invented-indicator",
                    "invented-category",
                    "historical",
                    "2021",
                ),
            ),
        )
    else:
        p = replace(p, members=(("invented.csv", 1, 2000, 1, 3),))
        if plant == "member_bytes":
            p = replace(p, members=(("invented.csv", 1, 2, 1, 3),))
        elif plant == "member_rows":
            p = replace(p, members=(("invented.csv", 1, 2000, 2, 3),))
        body = archive(
            body, "invented-other.csv" if plant == "inventory" else "invented.csv"
        )
    with pytest.raises(ValueError) as caught:
        parse(body, p, "b" * 64)
    refusal(caught, expected)


def test_archive_complete_coverage():
    body = payload(value="invented-missing", extra=True)
    p = replace(native(), members=(("invented.csv", 1, 2000, 1, 3),))
    result = parse_with_coverage(archive(body), p, "b" * 64)
    assert result.coverage == {
        "raw": 2,
        "selected": 1,
        "excluded": 1,
        "missing": 1,
        "last_periods": [
            [
                "invented-country",
                "invented-indicator",
                "invented-category",
                "historical",
                "2020",
            ]
        ],
        "members": [
            {
                "name": "invented.csv",
                "sha256": hashlib.sha256(body).hexdigest(),
                "bytes": len(body),
                "rows": 2,
            }
        ],
    }
    assert result.rows[0].source_row_key == "native-row-0"
    assert result.rows[0].receipt_sha256 == "b" * 64


@pytest.mark.parametrize("fmt", ["json", "csv"])
def test_negative_values(fmt):
    p = native(fmt=fmt)
    result = parse(payload(fmt, "-2.75"), p, "b" * 64)
    assert result[0].historical_value == "-2.75"
    assert result[0].receipt_sha256 == "b" * 64


@pytest.mark.parametrize("fmt", ["csv", "tsv"])
def test_flat_nullable_columns(fmt):
    item = asdict(replace(row(), source_flags=""))
    stream = io.StringIO()
    writer = csv.DictWriter(
        stream, fieldnames=list(item), delimiter="," if fmt == "csv" else "\t"
    )
    writer.writeheader()
    writer.writerow(item)
    result = parse(stream.getvalue().encode(), replace(policy(), format=fmt), "b" * 64)
    assert result == (replace(row(), source_flags="", receipt_sha256="b" * 64),)


def test_json_blank_is_not_null():
    item = asdict(row())
    item["currency"] = ""
    with pytest.raises(ValueError) as caught:
        parse(json.dumps([item]).encode(), policy(), "b" * 64)
    refusal(caught, "benchmark row_schema")


def test_flat_negative_and_reverse_periods():
    p = replace(policy(), periods=("2020", "2021"))
    rows = [replace(row(), period="2021", historical_value="-2.75"), row()]
    result = parse_with_coverage(
        json.dumps([asdict(v) for v in rows]).encode(), p, "b" * 64
    )
    assert result.rows == tuple(replace(v, receipt_sha256="b" * 64) for v in rows)
    assert result.coverage == {
        "raw": 2,
        "selected": 2,
        "excluded": 0,
        "missing": 0,
        "last_periods": [
            [
                "invented-country",
                "invented-indicator",
                "invented-category",
                "historical",
                "2021",
            ]
        ],
        "members": [],
    }
