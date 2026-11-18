"""S2-T17: invented metadata fixtures, never fetched records."""

import copy
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from eii_custodian.publicdata.fetch.forecast_series import (
    forecast_refusal_reason,
    forecastable,
    load_forecast_series,
)
from eii_custodian.publicdata.fetch.registry import (
    Entry,
    RegistryError,
    load_registry,
    registry_path,
)


def test_series_without_a_table_is_not_forecastable() -> None:
    rows = [
        {
            "key": "producer_prices",
            "state": "open",
            "source_keys": [],
            "table": "",
            "period": "",
            "frequency": "",
            "past_count": None,
            "subject": "",
            "reason": "no_source_table",
        }
    ]
    series = load_forecast_series(rows, ())
    assert forecastable("producer_prices", series, ()) is False
    assert forecast_refusal_reason("producer_prices", series, ()) == "no_source_table"


def source(key: str = "lic_issued", table: str = "pub_licence_issued") -> Entry:
    return Entry(
        key=key,
        source_id=key,
        slug="invented-fixture",
        kind="portal_dataset",
        title_en="Invented fixture",
        publisher="Invented publisher",
        licence_id="CC0",
        licence_basis="dataset",
        decision_record="",
        fetch_host="example.test",
        url="https://example.test/invented",
        terms_url="",
        terms_words="invented terms words for a test",
        terms_read_on="2026-11-14",
        nightly_live_fetch=False,
        public_splits=(),
        commit_allowed=False,
        release_tables=(table,),
        caveat_keys=(),
        columns=(),
        row_count_min=None,
        row_count_max=None,
        period_first="",
        period_last="",
        period_field="",
        reconciliation="none",
        skip_reason="",
        extension="json",
        landing_url="https://example.test/invented",
    )


def held() -> dict[str, object]:
    return dict(
        key="licence_issues",
        state="held",
        source_keys=["lic_issued"],
        table="pub_licence_issued",
        period="2001-01/2001-09",
        frequency="month",
        past_count=9,
        subject="",
        reason="",
    )


def test_held_metadata_and_skip_reason() -> None:
    rows = load_forecast_series([held()], (source(),))
    assert rows[0].past_count == 9
    assert rows[0].period == "2001-01/2001-09"
    assert rows[0].frequency == "month"
    assert forecastable("licence_issues", rows, (source(),)) is True
    blocked = replace(source(), skip_reason="invented_unconfirmed_schema")
    assert not forecastable("licence_issues", rows, (blocked,))
    assert (
        forecast_refusal_reason("licence_issues", rows, (blocked,))
        == blocked.skip_reason
    )
    assert (
        forecast_refusal_reason("licence_issues", rows, ()) == "source_not_registered"
    )
    with pytest.raises(RegistryError, match="unknown series"):
        forecastable("invented_unknown", rows, (source(),))


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"key": "licence_net"}, "unknown series"),
        ({"table": "invented_absent"}, "table"),
        ({"source_keys": ["invented_absent"]}, "source"),
        ({"source_keys": []}, "source"),
        ({"past_count": None}, "past_count"),
        ({"past_count": True}, "past_count"),
        ({"past_count": 0}, "past_count"),
        ({"period": ""}, "period"),
        ({"frequency": ""}, "frequency"),
        ({"frequency": "quarter"}, "frequency"),
        ({"state": "open", "reason": "invented_reason"}, "past_count"),
        ({"state": "open", "past_count": None}, "reason"),
        ({"state": "invented_state"}, "state"),
        ({"table": ["pub_property_sale", "pub_property_quarter"]}, "table"),
        ({"source_keys": ["restaurant_production_value"]}, "source"),
        (
            {"key": "property_prices", "subject": "area", "frequency": "year"},
            "district",
        ),
        ({"extra": "invented"}, "unknown field"),
        ({"reason": "invented_reason"}, "held reason"),
        ({"period": 9}, "period"),
        ({"source_keys": "lic_issued"}, "source_keys"),
        ({"source_keys": [9]}, "source_keys"),
    ],
)
def test_planted_forecast_record(change: dict[str, object], reason: str) -> None:
    row = held() | change
    with pytest.raises(RegistryError, match=reason):
        load_forecast_series([row], (source(),))


def test_duplicate_and_malformed_forecast_records() -> None:
    for rows, reason in [
        (None, "list"),
        ([None], "map"),
        ([held(), held()], "duplicate"),
    ]:
        with pytest.raises(RegistryError, match=reason):
            load_forecast_series(rows, (source(),))


def test_source_table_must_belong_to_named_source() -> None:
    with pytest.raises(RegistryError, match="table"):
        load_forecast_series([held()], (source(table="invented_other_table"),))


def committed():
    document = yaml.safe_load(registry_path().read_text())
    return load_forecast_series(document["forecast_series"], load_registry())


def test_closed_list_and_two_licence_names() -> None:
    assert {row.key for row in committed()} == {
        "licence_issues",
        "licence_cancellations",
        "property_prices",
        "hotel_demand_and_room_rates",
        "consumer_prices",
        "producer_prices",
        "imports_by_product",
        "announced_investment",
        "construction_pipeline",
        "expected_households_and_workers",
        "property_prices_quarterly",
    }


def test_committed_metadata_or_open_reason() -> None:
    for row in committed():
        if row.state == "held":
            assert row.table and row.period and row.frequency and row.past_count
        else:
            assert row.reason and row.past_count is None
            assert not forecastable(row.key, committed(), load_registry())


def test_district_subject_and_quarterly_separation() -> None:
    rows = {row.key: row for row in committed()}
    annual = rows["property_prices"]
    quarterly = rows["property_prices_quarterly"]
    assert annual.subject == quarterly.subject == "district"
    assert annual.table == "pub_property_sale"
    assert annual.frequency == "year"
    assert quarterly.table == "pub_property_quarter"
    assert quarterly.state == "open"
    assert quarterly.frequency == "quarter"
    assert quarterly.past_count is None
    assert "use_map" in quarterly.reason
    assert "crosswalk" in quarterly.reason


def test_a_held_quarterly_price_entry_validates() -> None:
    """The former open-only guard now accepts the held C41 entry (DR11)."""
    entries = (
        source("prop_sales", "pub_property_quarter"),
        source(
            "prop_resi_units/weekly-residential-units-sales-bulletin",
            "pub_property_quarter",
        ),
    )
    row = dict(
        key="property_prices_quarterly",
        state="held",
        subject="district",
        source_keys=[
            "prop_sales",
            "prop_resi_units/weekly-residential-units-sales-bulletin",
        ],
        table="pub_property_quarter",
        period="2020-Q3/2025-Q4",
        frequency="quarter",
        past_count=22,
        reason="",
    )
    series = load_forecast_series([row], entries)
    assert series[0].state == "held"
    assert forecastable("property_prices_quarterly", series, entries) is True


def test_confirmation_matches_record_and_names_open_questions() -> None:
    confirmation = (
        registry_path().parent / "review/s2_t17_forecast_series.md"
    ).read_text()
    for row in committed():
        assert f"`{row.key}`" in confirmation
        assert f"`{row.state}`" in confirmation
        if row.state == "open":
            assert f"OI-98: `{row.key}` — `{row.reason}`" in confirmation
        else:
            assert (
                f"`{row.period}`; `{row.frequency}`; past_count `{row.past_count}`"
                in confirmation
            )


def test_registry_checks_forecast_block_and_rejects_unknown_root(
    tmp_path: Path,
) -> None:
    document = yaml.safe_load(registry_path().read_text())
    for mutate, reason in [("root", "unknown field"), ("count", "past_count")]:
        planted = copy.deepcopy(document)
        if mutate == "root":
            planted["invented_extra_root"] = []
        else:
            planted["forecast_series"][0]["past_count"] = None
        path = tmp_path / "invented.yaml"
        path.write_text(yaml.safe_dump(planted))
        with pytest.raises(RegistryError, match=reason):
            load_registry(path)


def test_held_source_removed_from_registry_is_refused() -> None:
    with pytest.raises(RegistryError, match="source is not registered"):
        load_forecast_series([held()], ())


def test_forecast_request_rechecks_table() -> None:
    rows = load_forecast_series([held()], (source(),))
    assert (
        forecast_refusal_reason(
            "licence_issues", rows, (source(table="invented_other"),)
        )
        == "table_not_registered"
    )


def test_net_disguised_as_issues_is_refused() -> None:
    row = held() | {"source_keys": ["lic_issued", "lic_cancelled"]}
    with pytest.raises(RegistryError, match="source keys"):
        load_forecast_series([row], (source(),))


def test_annual_quarterly_join_disguised_as_annual_is_refused() -> None:
    row = held() | dict(
        key="property_prices",
        subject="district",
        frequency="year",
        source_keys=["prop_sales"],
        table="pub_property_sale+pub_property_quarter",
    )
    with pytest.raises(RegistryError, match="table"):
        load_forecast_series([row], (source("prop_sales", "pub_property_sale"),))


def test_empty_forecast_subset_and_legacy_registry(tmp_path: Path) -> None:
    assert load_forecast_series([], ()) == ()
    document = yaml.safe_load(registry_path().read_text())
    del document["forecast_series"]
    path = tmp_path / "invented_legacy.yaml"
    path.write_text(yaml.safe_dump(document))
    assert load_registry(path) == load_registry()


def test_open_quarterly_price_still_requires_district() -> None:
    row = dict(
        key="property_prices_quarterly",
        state="open",
        subject="area",
        source_keys=[
            "prop_sales",
            "prop_resi_units/weekly-residential-units-sales-bulletin",
        ],
        table="pub_property_quarter",
        reason="invented_pending_confirmation",
    )
    with pytest.raises(RegistryError, match="district"):
        load_forecast_series([row], ())


@pytest.mark.parametrize(
    "key,keys,table",
    [
        ("consumer_prices", ["cpi_group"], "pub_price_index"),
        ("imports_by_product", ["cus_imp_2019", "cus_imp_2025"], "pub_customs_import"),
    ],
)
def test_invented_monthly_metadata_for_currently_open_sources(key, keys, table) -> None:
    row = held() | dict(key=key, source_keys=keys, table=table)
    entries = tuple(source(name, table) for name in keys)
    result = load_forecast_series([row], entries)
    assert result[0].frequency == "month"
    assert forecastable(key, result, entries)


@pytest.mark.parametrize(
    "field",
    [
        "key",
        "state",
        "table",
        "period",
        "frequency",
        "subject",
        "reason",
        "note",
        "evidence",
    ],
)
def test_forecast_text_fields_are_typed(field: str) -> None:
    with pytest.raises(RegistryError, match=field + " is not text"):
        load_forecast_series([held() | {field: 9}], (source(),))
