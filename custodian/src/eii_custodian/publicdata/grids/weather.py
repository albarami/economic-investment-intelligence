"""Validate hourly reanalysis for a generator cache, never a release table."""

from datetime import UTC, datetime, timedelta, timezone
from math import isfinite
from typing import Any

from .contracts import GridError

ATTRIBUTION = "Weather data by Open-Meteo.com — https://open-meteo.com/; https://creativecommons.org/licenses/by/4.0/; Generated using Copernicus Climate Change Service information 2022. Times converted to UTC."


def validate_weather(
    data: dict[str, Any],
    requested: tuple[float, float],
    first: str,
    last: str,
) -> dict[str, Any]:
    """Require each requested local hour and convert using the supplied offset."""
    if data.get("error") is True:
        raise GridError("weather_openmeteo: provider error")
    if data.get("timezone") != "Asia/Qatar" or data.get("utc_offset_seconds") != 10800:
        raise GridError("weather_openmeteo: timezone mismatch")
    if data.get("hourly_units") != {"time": "iso8601", "temperature_2m": "°C"}:
        raise GridError("weather_openmeteo: units mismatch")
    hourly = data.get("hourly", {})
    times, values = hourly.get("time", []), hourly.get("temperature_2m", [])
    start, end = datetime.fromisoformat(first), datetime.fromisoformat(last)
    expected = []
    cursor = start
    while cursor <= end:
        expected.append(cursor.isoformat(timespec="minutes"))
        cursor += timedelta(hours=1)
    if not expected or times != expected or len(values) != len(times):
        raise GridError("weather_openmeteo: missing hour or array mismatch")
    if any(
        isinstance(v, bool) or not isinstance(v, int | float) or not isfinite(v)
        for v in values
    ):
        raise GridError("weather_openmeteo: missing or invalid hourly value")
    offset = timezone(timedelta(seconds=data["utc_offset_seconds"]))
    utc_times = [
        datetime.fromisoformat(t)
        .replace(tzinfo=offset)
        .astimezone(UTC)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
        for t in times
    ]
    coordinates = [data.get("latitude"), data.get("longitude")]
    if any(
        isinstance(v, bool) or not isinstance(v, int | float) or not isfinite(v)
        for v in coordinates
    ):
        raise GridError("weather_openmeteo: missing coordinates")
    return {
        "source_id": "weather_openmeteo",
        "requested_coordinates": list(requested),
        "provider_coordinates": coordinates,
        "hourly": {"time": utc_times, "temperature_2m": values},
        "hourly_units": {"time": "UTC", "temperature_2m": "°C"},
        "timezone": data["timezone"],
        "utc_offset_seconds": data["utc_offset_seconds"],
        "attribution": ATTRIBUTION,
        "licence_basis": "provider_terms",
        "release_tables": [],
    }
