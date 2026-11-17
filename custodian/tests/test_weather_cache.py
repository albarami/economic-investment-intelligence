"""Invented hourly weather; offset conversion crosses UTC midnight."""

import json
from copy import deepcopy

import pytest
from custodian.tests.fixtures.grids.invented import entry, store

from eii_custodian.publicdata.fetch.allowlist import (
    ALLOWED_HOSTS,
    NAMED_WEATHER_HOST,
    approve,
)
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.grids.build import build_grids
from eii_custodian.publicdata.grids.contracts import GridError
from eii_custodian.publicdata.grids.weather import validate_weather


def payload():
    return {
        "latitude": 1.1,
        "longitude": 2.1,
        "timezone": "Asia/Qatar",
        "utc_offset_seconds": 10800,
        "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
        "hourly": {
            "time": ["2024-01-01T00:00", "2024-01-01T01:00"],
            "temperature_2m": [20, 21],
        },
    }


def test_weather_midnight():
    result = validate_weather(payload(), (1, 2), "2024-01-01T00:00", "2024-01-01T01:00")
    assert result["hourly"]["time"] == ["2023-12-31T21:00:00Z", "2023-12-31T22:00:00Z"]
    assert result["requested_coordinates"] == [1, 2]
    assert result["provider_coordinates"] == [1.1, 2.1]
    assert result["release_tables"] == []


@pytest.mark.parametrize(
    "change", ["error", "missing", "null", "units", "timezone", "offset", "length"]
)
def test_weather_refusals(change):
    data = deepcopy(payload())
    if change == "error":
        data = {"error": True, "reason": "invented error"}
    if change == "missing":
        data["hourly"]["time"][1] = "2024-01-01T02:00"
    if change == "null":
        data["hourly"]["temperature_2m"][1] = None
    if change == "units":
        data["hourly_units"]["temperature_2m"] = "F"
    if change == "timezone":
        data["timezone"] = "GMT"
    if change == "offset":
        data["utc_offset_seconds"] = 0
    if change == "length":
        data["hourly"]["temperature_2m"].pop()
    with pytest.raises(GridError, match="weather_openmeteo"):
        validate_weather(data, (1, 2), "2024-01-01T00:00", "2024-01-01T01:00")


@pytest.mark.parametrize(
    "field,value", [("latitude", None), ("longitude", float("nan")), ("latitude", True)]
)
def test_weather_bad_coordinates(field, value):
    data = payload()
    data[field] = value
    with pytest.raises(GridError, match="coordinates"):
        validate_weather(data, (1, 2), "2024-01-01T00:00", "2024-01-01T01:00")


@pytest.mark.parametrize("value", [True, "20", float("nan")])
def test_weather_bad_values(value):
    data = payload()
    data["hourly"]["temperature_2m"][0] = value
    with pytest.raises(GridError, match="hourly value"):
        validate_weather(data, (1, 2), "2024-01-01T00:00", "2024-01-01T01:00")


def test_weather_empty_period():
    with pytest.raises(GridError, match="missing hour"):
        validate_weather(payload(), (1, 2), "2024-01-02T00:00", "2024-01-01T01:00")


def _weather_row():
    return entry(
        "weather_openmeteo",
        "weather_openmeteo/2024-2025/point",
        extension="json",
        licence_basis="provider_terms",
        url="https://archive-api.open-meteo.com/v1/archive?latitude=1&longitude=2",
        fetch_host="archive-api.open-meteo.com",
        nightly_live_fetch=True,
        period_first="2024-01-01T00:00",
        period_last="2024-01-01T01:00",
        point=(1.0, 2.0),
        variables=("temperature_2m",),
        cache_role="generator_input",
    )


def test_weather_hashed_cache_file(tmp_path):
    row = _weather_row()
    body = json.dumps(payload()).encode("utf-8")
    digest = store(tmp_path, row, body)
    result = build_grids(tmp_path, (row,), {})
    cached = json.loads(
        (tmp_path / "grids" / "weather_openmeteo.json").read_text("utf-8")
    )
    assert cached["source_key"] == row.key
    assert cached["source_sha256"] == digest
    assert cached["release_tables"] == []
    assert cached["variables"] == ["temperature_2m"]
    assert cached["attribution"].startswith("Weather data by Open-Meteo.com")
    assert cached["hourly"]["time"] == [
        "2023-12-31T21:00:00Z",
        "2023-12-31T22:00:00Z",
    ]
    assert result.tables["pub_night_lights"] == []
    assert result.tables["pub_pop_agesex_grid"] == []
    assert result.tables["fact_lineage"] == []
    assert [item["source_key"] for item in result.tables["source_registry"]] == [
        row.key
    ]
    assert result.sources[row.key]["method"] == "weather.v1"
    manifest = json.loads((tmp_path / "grids" / "manifest.json").read_text("utf-8"))
    assert manifest["files"][0]["sha256"] == digest
    assert manifest["files"][0]["variables"] == ["temperature_2m"]


def test_weather_cache_refuses_a_tampered_file(tmp_path):
    row = _weather_row()
    body = json.dumps(payload()).encode("utf-8")
    digest = store(tmp_path, row, body)
    (tmp_path / row.key / f"{digest}.json").write_bytes(b"{}")
    with pytest.raises(GridError, match="content hash mismatch"):
        build_grids(tmp_path, (row,), {})


def test_weather_cache_refuses_a_broken_response(tmp_path):
    row = _weather_row()
    broken = payload()
    broken["hourly"]["temperature_2m"].pop()
    store(tmp_path, row, json.dumps(broken).encode("utf-8"))
    with pytest.raises(GridError, match="weather_openmeteo"):
        build_grids(tmp_path, (row,), {})


def test_weather_cache_refuses_a_diverged_receipt(tmp_path):
    row = _weather_row()
    body = json.dumps(payload()).encode("utf-8")
    digest = store(tmp_path, row, body)
    path = tmp_path / row.key / f"{digest}.meta.json"
    loaded = json.loads(path.read_text("utf-8"))
    loaded["file"]["cache_role"] = "release_table"
    path.write_text(json.dumps(loaded), encoding="utf-8")
    with pytest.raises(GridError, match="receipt file mismatch"):
        build_grids(tmp_path, (row,), {})


def test_weather_registry_entry():
    entries = load_registry()
    rows = [
        item
        for item in entries
        if item.source_id == "weather_openmeteo" and "/" in item.key
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row.licence_basis == "provider_terms"
    assert row.release_tables == ()
    assert row.nightly_live_fetch is True
    assert row.point == (25.2854, 51.531)
    assert row.variables == ("temperature_2m",)
    assert row.cache_role == "generator_input"
    assert row.terms_url == ""
    assert row.period_first == "2024-01-01T00:00"
    assert row.period_last == "2025-12-31T23:00"
    assert row.licence_url == "https://open-meteo.com/en/licence"
    assert row.landing_url == "https://open-meteo.com/en/docs/historical-weather-api"
    assert approve(row.url).ok


def test_weather_host_is_allow_listed():
    assert NAMED_WEATHER_HOST in ALLOWED_HOSTS
    assert approve("https://archive-api.open-meteo.com/v1/archive").ok
    assert approve("https://open-meteo.com/en/terms").ok is False
    assert approve("https://api.open-meteo.com/v1/forecast").ok is False
