"""Hand-written weather results that kill surviving numeric mutants."""

from __future__ import annotations

import os
import time
from typing import Any

import pytest

from eii_custodian.publicdata.grids.contracts import GridError
from eii_custodian.publicdata.grids.weather import validate_weather

ATTRIBUTION = (
    "Weather data by Open-Meteo.com — https://open-meteo.com/; "
    "https://creativecommons.org/licenses/by/4.0/; "
    "Generated using Copernicus Climate Change Service information 2022. "
    "Times converted to UTC."
)
FIRST = "2024-01-01T00:00"
LAST = "2024-01-01T01:00"


def _payload() -> dict[str, Any]:
    return {
        "latitude": 1.1,
        "longitude": 2.1,
        "timezone": "Asia/Qatar",
        "utc_offset_seconds": 10800,
        "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
        "hourly": {
            "time": [FIRST, LAST],
            "temperature_2m": [20, 21],
        },
    }


def _record() -> dict[str, Any]:
    return {
        "source_id": "weather_openmeteo",
        "requested_coordinates": [1.0, 2.0],
        "provider_coordinates": [1.1, 2.1],
        "hourly": {
            "time": ["2023-12-31T21:00:00Z", "2023-12-31T22:00:00Z"],
            "temperature_2m": [20, 21],
        },
        "hourly_units": {"time": "UTC", "temperature_2m": "°C"},
        "timezone": "Asia/Qatar",
        "utc_offset_seconds": 10800,
        "attribution": ATTRIBUTION,
        "licence_basis": "provider_terms",
        "release_tables": [],
    }


def test_validated_record_matches_the_hand_written_one() -> None:
    """The cache record is the converted hours and the named fields, whole."""
    previous = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    try:
        assert validate_weather(_payload(), (1.0, 2.0), FIRST, LAST) == _record()
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        time.tzset()


def _expect(data: dict[str, Any], message: str) -> None:
    with pytest.raises(GridError) as caught:
        validate_weather(data, (1.0, 2.0), FIRST, LAST)
    assert str(caught.value) == message


def test_provider_error_is_the_whole_sentence() -> None:
    """A provider error flag is refused before any other field is read."""
    _expect(
        {"error": True, "reason": "invented"},
        "weather_openmeteo: provider error",
    )


def test_timezone_mismatch_is_the_whole_sentence() -> None:
    """A zone other than Asia/Qatar is refused by name."""
    data = _payload()
    data["timezone"] = "GMT"
    _expect(data, "weather_openmeteo: timezone mismatch")


def test_units_mismatch_is_the_whole_sentence() -> None:
    """Units other than iso8601 and degrees Celsius are refused by name."""
    data = _payload()
    data["hourly_units"] = {"time": "iso8601", "temperature_2m": "F"}
    _expect(data, "weather_openmeteo: units mismatch")


def test_missing_hourly_object_is_a_named_refusal() -> None:
    """A response with no hourly object is a missing-hour refusal."""
    data = _payload()
    del data["hourly"]
    _expect(data, "weather_openmeteo: missing hour or array mismatch")


def test_missing_temperature_array_is_a_named_refusal() -> None:
    """Hours without a temperature array are a missing-hour refusal."""
    data = _payload()
    del data["hourly"]["temperature_2m"]
    _expect(data, "weather_openmeteo: missing hour or array mismatch")


def test_missing_hour_is_the_whole_sentence() -> None:
    """A gap in the hour list is refused by name."""
    data = _payload()
    data["hourly"]["time"][1] = "2024-01-01T02:00"
    _expect(data, "weather_openmeteo: missing hour or array mismatch")


def test_invalid_hourly_value_is_the_whole_sentence() -> None:
    """A non-numeric temperature is refused by name."""
    data = _payload()
    data["hourly"]["temperature_2m"][0] = None
    _expect(data, "weather_openmeteo: missing or invalid hourly value")


def test_missing_coordinates_is_the_whole_sentence() -> None:
    """A response without a latitude is refused by name."""
    data = _payload()
    del data["latitude"]
    _expect(data, "weather_openmeteo: missing coordinates")
