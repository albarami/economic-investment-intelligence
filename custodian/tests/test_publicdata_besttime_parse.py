"""Invented provider answers; G12 to G15 define the protocol, not live data."""

import json
from copy import deepcopy

import pytest

from eii_custodian.publicdata.busyness.parse import (
    ShapeError,
    parse_forecast,
    parse_query,
)


def forecast():
    return {
        "status": "OK",
        "venue_info": {"venue_id": "SYN-venue-a", "venue_name": "Invented cafe"},
        "analysis": [
            {
                "day_info": {"day_int": day},
                "day_raw": [(day + hour) % 101 for hour in range(24)],
                "hour_analysis": [{"hour": (6 + hour) % 24} for hour in range(24)],
            }
            for day in range(7)
        ],
    }


def query():
    return {
        "venue_id": "SYN-venue-a",
        "analysis": {
            "week_raw": [
                value for day in forecast()["analysis"] for value in day["day_raw"]
            ]
        },
        "window": {
            "time_window_start": 6,
            "time_window_end": 5,
            "day_window_start_int": 0,
            "day_window_start_txt": "Monday",
            "week_window": "Monday 6AM until Monday 5AM next week",
        },
        "forecast_updated_on": "2026-10-01T01:02:03.123456+03:00",
    }


def encode(value):
    return json.dumps(value).encode()


def test_besttime_provider_day_and_query_date():
    parsed = parse_forecast(encode(forecast()))
    assert parsed.venue_id == "SYN-venue-a"
    assert parsed.name == "Invented cafe"
    assert parsed.reason == ""
    assert parsed.days[0] == tuple(range(24))
    assert parse_query(encode(query()), parsed) == "2026-10-01"
    for absent in (None, "missing"):
        value = query()
        if absent is None:
            value["forecast_updated_on"] = None
        else:
            del value["forecast_updated_on"]
        assert parse_query(encode(value), parsed) is None


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "status",
        "info",
        "id",
        "name",
        "days",
        "short",
        "duplicate",
        "daytype",
        "dayrange",
        "hours",
        "hourorder",
        "hourtype",
        "high",
        "low",
        "float",
        "bool",
        "root",
    ],
)
def test_besttime_forecast_shape(kind):
    value = deepcopy(forecast())
    if kind == "missing":
        del value["analysis"]
    elif kind == "status":
        value["status"] = "unknown"
    elif kind == "info":
        value["venue_info"] = []
    elif kind == "id":
        value["venue_info"]["venue_id"] = 1
    elif kind == "name":
        value["venue_info"]["venue_name"] = None
    elif kind == "days":
        value["analysis"].append(value["analysis"][0])
    elif kind == "short":
        value["analysis"][0]["day_raw"].pop()
    elif kind == "duplicate":
        value["analysis"][1]["day_info"]["day_int"] = 0
    elif kind == "daytype":
        value["analysis"][0]["day_info"]["day_int"] = False
    elif kind == "dayrange":
        value["analysis"][0]["day_info"]["day_int"] = -1
    elif kind == "hours":
        value["analysis"][0]["hour_analysis"].pop()
    elif kind == "hourorder":
        value["analysis"][0]["hour_analysis"][0]["hour"] = 5
    elif kind == "hourtype":
        value["analysis"][0]["hour_analysis"][18]["hour"] = False
    elif kind in {"high", "low", "float", "bool"}:
        value["analysis"][0]["day_raw"][0] = {
            "high": 101,
            "low": -1,
            "float": 1.5,
            "bool": True,
        }[kind]
    elif kind == "root":
        value = []
    with pytest.raises(
        ShapeError, match=r"busy_besttime https://besttime\.app/api/v1/forecasts"
    ):
        parse_forecast(encode(value))


@pytest.mark.parametrize(
    "kind",
    [
        "id",
        "week",
        "different",
        "bool",
        "window",
        "windowtype",
        "date",
        "offset",
        "root",
    ],
)
def test_besttime_query_shape(kind):
    value = query()
    if kind == "id":
        value["venue_id"] = "SYN-other"
    elif kind == "week":
        value["analysis"]["week_raw"].pop()
    elif kind == "different":
        value["analysis"]["week_raw"][0] = 100
    elif kind == "bool":
        value["analysis"]["week_raw"][0] = False
    elif kind == "window":
        value["window"]["time_window_start"] = 5
    elif kind == "windowtype":
        value["window"]["day_window_start_int"] = False
    elif kind == "date":
        value["forecast_updated_on"] = "2026-02-30T01:02:03.123456+03:00"
    elif kind == "offset":
        value["forecast_updated_on"] = "2026-10-01"
    elif kind == "root":
        value = []
    with pytest.raises(ShapeError, match="forecasts/week/raw"):
        parse_query(encode(value), parse_forecast(encode(forecast())))


def test_besttime_no_figure_reasons_and_ignored_fields():
    for info, reason in [
        ({}, "not_found"),
        ({"venue_id": "SYN-venue-a"}, "no_forecast"),
    ]:
        parsed = parse_forecast(
            encode(
                {
                    "status": "Error",
                    "venue_info": info,
                    "request_url": "discarded",
                    "arbitrary_api_key": "discarded",
                }
            )
        )
        assert parsed.reason == reason
        assert parsed.days == ()
    value = forecast()
    value["extra"] = "never taken"
    assert parse_forecast(encode(value)) == parse_forecast(encode(forecast()))


def test_besttime_error_requires_object_and_nested_list_secrets_removed():
    from eii_custodian.publicdata.busyness.parse import _clean

    with pytest.raises(ShapeError):
        parse_forecast(encode({"status": "Error", "venue_info": []}))
    assert _clean(
        {
            "items": [
                {"request_url": "discard", "an_api_key": "discard", "keep": "invented"}
            ]
        }
    ) == {"items": [{"keep": "invented"}]}


def test_besttime_index_endpoints_and_shuffled_provider_days():
    value = forecast()
    value["analysis"][0]["day_raw"][0:2] = [0, 100]
    value["analysis"].reverse()
    parsed = parse_forecast(encode(value))
    assert parsed.days[0][0:2] == (0, 100)


@pytest.mark.parametrize(
    "value",
    [
        "2026-10-01T01:02:03+03:00",
        "2026-10-01T01:02:03.123456",
        1,
        "2026-10-01T01:02:03.123456+99:00",
    ],
)
def test_besttime_exact_updated_shape(value):
    answer = query()
    answer["forecast_updated_on"] = value
    with pytest.raises(ShapeError):
        parse_query(encode(answer), parse_forecast(encode(forecast())))
