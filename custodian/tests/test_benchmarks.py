"""Invented benchmark records; no publisher response or identifier."""

from dataclasses import replace

import pytest


def row(source="ilostat_qat", status="historical"):
    from eii_custodian.publicdata.benchmarks.contracts import Benchmark

    values = {
        name + "_value": None
        for name in (
            "historical",
            "publisher_estimate",
            "publisher_forecast",
            "unclassified",
        )
    }
    values[status + "_value"] = "12.50"
    return Benchmark(
        source_id=source,
        source_version="invented-vintage",
        country_code="invented-country",
        indicator_code="invented-indicator",
        dimension_key="invented-category",
        frequency="annual",
        period="2020",
        unit="invented-unit",
        currency=None,
        scale="invented-scale",
        price_basis=None,
        publisher_status=status,
        value_status="present",
        source_flags="invented-flag",
        receipt_sha256="a" * 64,
        source_row_key="invented-row",
        **values,
    )


@pytest.mark.parametrize("operation", ["join", "sum"])
@pytest.mark.parametrize("boundary", ["contract", "build"])
def test_f1_announcements_refused(operation, boundary):
    from eii_custodian.publicdata.benchmarks.contracts import validate_use
    from eii_custodian.publicdata.benchmarks.fetch import build_rows

    item = row("unctad_fdi")
    with pytest.raises(ValueError, match="forbidden_use"):
        if boundary == "contract":
            validate_use(item, operation, "fdi_projects")
        else:
            build_rows((item,), operation=operation, target="fdi_projects")


@pytest.mark.parametrize("source", ["ilostat_qat", "wb_wdi", "imf_weo", "unctad_fdi"])
@pytest.mark.parametrize(
    "operation,target",
    [
        ("join", "company"),
        ("segment", "company"),
        ("sum", "protected"),
        ("join", "worker"),
        ("join", "residence"),
        ("apportion", "drawn_area"),
    ],
)
def test_f2_public_splits_refused(source, operation, target):
    from eii_custodian.publicdata.benchmarks.fetch import build_rows

    with pytest.raises(ValueError, match="forbidden_use"):
        build_rows((row(source),), operation=operation, target=target)


@pytest.mark.parametrize("status", ["publisher_forecast", "unclassified"])
def test_f3_stored_nonhistorical_excluded(status):
    from eii_custodian.publicdata.benchmarks.contracts import historical_rows

    assert historical_rows((row(status=status),)) == ()


def test_f3_multiple_values_refused():
    from eii_custodian.publicdata.benchmarks.contracts import validate_row

    with pytest.raises(ValueError, match="status_values"):
        validate_row(replace(row(), publisher_forecast_value="5"))


def test_historical_and_missing_are_not_reclassified():
    from eii_custodian.publicdata.benchmarks.contracts import (
        historical_rows,
        validate_row,
    )

    item = row()
    assert historical_rows((item,)) == (item,)
    missing = replace(item, historical_value=None, value_status="source_missing")
    validate_row(missing)
    assert historical_rows((missing,)) == (missing,)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("source_id", "fdi_projects", "source_id"),
        ("unit", "", "row_schema"),
        ("scale", 1, "row_schema"),
        ("receipt_sha256", "a" * 63, "receipt_hash"),
        ("receipt_sha256", "z" * 64, "receipt_hash"),
        ("publisher_status", "invented", "status_values"),
        ("value_status", "invented", "status_values"),
    ],
    ids=[
        "source",
        "empty",
        "type",
        "digest_length",
        "digest_hex",
        "publisher_status",
        "value_status",
    ],
)
def test_row_plants(field, value, reason):
    from eii_custodian.publicdata.benchmarks.contracts import validate_row

    validate_row(row())
    with pytest.raises(ValueError, match=rf"^benchmark {reason}$"):
        validate_row(replace(row(), **{field: value}))
