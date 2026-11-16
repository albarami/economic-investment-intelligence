"""Invented benchmark contract boundary and integrity survivors."""

import hashlib
import json
from dataclasses import replace

import pytest

from eii_custodian.publicdata.benchmarks import contracts as ctr
from eii_custodian.publicdata.fetch.decimals import DecimalRefusal

from .test_benchmarks import row
from .test_benchmarks_fetch import benchmark_release


def refusal(caught, expected):
    assert str(caught.value) == expected


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("currency", "", "benchmark row_schema"),
        ("price_basis", "", "benchmark row_schema"),
        ("receipt_sha256", "X" * 64, "benchmark receipt_hash"),
        ("historical_value", None, "benchmark status_values"),
        ("publisher_forecast_value", "2", "benchmark status_values"),
    ],
)
def test_row_exact_refusal(field, value, expected):
    with pytest.raises(ValueError) as caught:
        ctr.validate_row(replace(row(), **{field: value}))
    refusal(caught, expected)


def test_empty_flags_and_signed_value():
    ctr.validate_row(replace(row(), source_flags="", historical_value="-2.75"))


def test_unknown_missing_status_refused():
    with pytest.raises(ValueError) as caught:
        ctr.validate_row(replace(row(), value_status="invented", historical_value=None))
    refusal(caught, "benchmark status_values")


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1" * 1001, "decimal_total_digits"),
        ("0." + "1" * 1001, "decimal_fractional_digits"),
    ],
)
def test_decimal_limits(value, expected):
    with pytest.raises(DecimalRefusal) as caught:
        ctr.validate_row(replace(row(), historical_value=value))
    refusal(caught, expected)


@pytest.mark.parametrize(
    "operation,target", [("join", "source_geography"), ("context", "drawn_area")]
)
def test_each_use_boundary(operation, target):
    with pytest.raises(ValueError) as caught:
        ctr.validate_use(row(), operation, target)
    refusal(caught, "ilostat_qat forbidden_use")


@pytest.mark.parametrize(
    "plant,expected",
    [
        ("complete", "manifest_contract"),
        ("raw_bytes", "output_hash"),
        ("output_bytes", "output_hash"),
        ("licence", "source_chain"),
        ("output", "reparsed_output"),
        ("count", "reparsed_output"),
    ],
)
def test_selected_release_messages(tmp_path, plant, expected):
    source, selected, manifest = benchmark_release(tmp_path)
    directory = tmp_path / source
    if plant == "complete":
        manifest["complete"] = False
    elif plant == "licence":
        manifest["receipt"]["licence_id"] = "invented-other"
    elif plant == "count":
        manifest["selected"] = 2
    elif plant == "output":
        body = b"[]"
        digest = hashlib.sha256(body).hexdigest()
        (directory / f"{digest}.json").write_bytes(body)
        manifest["output_sha256"] = digest
    else:
        path = directory / (
            f"{manifest['receipt']['sha256']}.bin"
            if plant == "raw_bytes"
            else f"{manifest['output_sha256']}.json"
        )
        path.write_bytes(b"invented-corrupt")
    body = json.dumps(manifest).encode()
    selected = hashlib.sha256(body).hexdigest()
    (directory / f"{selected}.manifest.json").write_bytes(body)
    with pytest.raises(ValueError) as caught:
        ctr.read_selected(tmp_path, source, selected)
    refusal(caught, expected)


def test_selected_utf8_under_ascii_locale(tmp_path, monkeypatch):
    import locale

    from . import test_benchmarks_fetch as builders

    original = builders.row
    monkeypatch.setattr(
        builders,
        "row",
        lambda *args: replace(original(*args), source_flags="invented-é"),
    )
    source, _, manifest = benchmark_release(tmp_path)
    directory = tmp_path / source
    output = directory / f"{manifest['output_sha256']}.json"
    raw = json.dumps(json.loads(output.read_bytes()), ensure_ascii=False).encode()
    digest = hashlib.sha256(raw).hexdigest()
    (directory / f"{digest}.json").write_bytes(raw)
    manifest["output_sha256"] = digest
    manifest["invented_note"] = "invented-é"
    raw = json.dumps(manifest, ensure_ascii=False).encode()
    selected = hashlib.sha256(raw).hexdigest()
    (directory / f"{selected}.manifest.json").write_bytes(raw)
    previous = locale.setlocale(locale.LC_CTYPE)
    try:
        locale.setlocale(locale.LC_CTYPE, "C")
        assert (
            ctr.read_selected(tmp_path, source, selected).rows[0].source_flags
            == "invented-é"
        )
    finally:
        locale.setlocale(locale.LC_CTYPE, previous)


def test_source_chain_refusal_precedes_invalid_date(tmp_path):
    source, _, manifest = benchmark_release(tmp_path)
    manifest["receipt"]["publisher"] = "invented-other"
    manifest["receipt"]["retrieved_utc"] = "invented-invalid-date"
    body = json.dumps(manifest).encode()
    selected = hashlib.sha256(body).hexdigest()
    (tmp_path / source / f"{selected}.manifest.json").write_bytes(body)
    with pytest.raises(ValueError) as caught:
        ctr.read_selected(tmp_path, source, selected)
    refusal(caught, "source_chain")
