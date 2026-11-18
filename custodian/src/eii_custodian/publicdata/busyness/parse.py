"""G12 to G15 provider projection. Unselected fields never leave this boundary."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

FORECAST_URL = "https://besttime.app/api/v1/forecasts"
QUERY_URL = FORECAST_URL + "/week/raw"
WINDOW = {
    "time_window_start": 6,
    "time_window_end": 5,
    "day_window_start_int": 0,
    "day_window_start_txt": "Monday",
    "week_window": "Monday 6AM until Monday 5AM next week",
}


class ShapeError(ValueError):
    """Diagnostics contain only the source and a fixed key-free endpoint."""


@dataclass(frozen=True, repr=False)
class Forecast:
    venue_id: str
    name: str
    days: tuple[tuple[int, ...], ...]
    reason: str


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _clean(item)
            for key, item in value.items()
            if key != "request_url" and "api_key" not in key.casefold()
        }
    if isinstance(value, list):
        return [_clean(item) for item in value]
    return value


def _document(body: bytes) -> dict[str, Any]:
    value = json.loads(body)
    value = _clean(value)
    if not isinstance(value, dict):
        raise ValueError
    return value


def _indices(value: Any, size: int) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) != size:
        raise ValueError
    if any(type(item) is not int or not 0 <= item <= 100 for item in value):
        raise ValueError
    return tuple(value)


def parse_forecast(body: bytes) -> Forecast:
    """Project only identity for in-memory matching and the seven hourly arrays."""
    try:
        value = _document(body)
        info = value["venue_info"]
        if not isinstance(info, dict):
            raise ValueError
        if value["status"] == "Error":
            return Forecast(
                "", "", (), "no_forecast" if "venue_id" in info else "not_found"
            )
        if value["status"] != "OK":
            raise ValueError
        if not isinstance(info["venue_id"], str) or not isinstance(
            info["venue_name"], str
        ):
            raise ValueError
        analysis = value["analysis"]
        if not isinstance(analysis, list) or len(analysis) != 7:
            raise ValueError
        days: dict[int, tuple[int, ...]] = {}
        for day in analysis:
            index = day["day_info"]["day_int"]
            if type(index) is not int or index not in range(7) or index in days:
                raise ValueError
            hours = day["hour_analysis"]
            if not isinstance(hours, list) or len(hours) != 24:
                raise ValueError
            for i, hour in enumerate(hours):
                if type(hour["hour"]) is not int or hour["hour"] != (6 + i) % 24:
                    raise ValueError
            days[index] = _indices(day["day_raw"], 24)
        return Forecast(
            info["venue_id"], info["venue_name"], tuple(days[i] for i in range(7)), ""
        )
    except (ValueError, KeyError, TypeError, UnicodeError):
        pass
    raise ShapeError(f"busy_besttime {FORECAST_URL} changed_shape") from None


def parse_query(body: bytes, forecast: Forecast) -> str | None:
    """Require the stored week to be exactly the requested provider week."""
    try:
        value = _document(body)
        if value["venue_id"] != forecast.venue_id:
            raise ValueError
        if _indices(value["analysis"]["week_raw"], 168) != tuple(
            item for day in forecast.days for item in day
        ):
            raise ValueError
        window = value["window"]
        for key, expected in WINDOW.items():
            if type(window[key]) is not type(expected) or window[key] != expected:
                raise ValueError
        updated = value.get("forecast_updated_on")
        if updated is None:
            return None
        if (
            not isinstance(updated, str)
            or re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}[+-][0-9]{2}:[0-9]{2}",
                updated,
            )
            is None
        ):
            raise ValueError
        return datetime.fromisoformat(updated).date().isoformat()
    except (ValueError, KeyError, TypeError, UnicodeError):
        pass
    raise ShapeError(f"busy_besttime {QUERY_URL} changed_shape") from None
