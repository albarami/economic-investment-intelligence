"""R10: inspect the actual engine boundary, retaining the real engine."""

import inspect
import json
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path
from unittest.mock import patch

import h3
from eii_product.areas_spike import traffic as adapter
from eii_product.areas_spike.traffic import Traffic

FIXTURES = Path(__file__).parent / "fixtures/areas_spike/assignment"


def traffic_fixture():
    roads = json.loads((FIXTURES / "hourly_roads.json").read_text())
    params = json.loads((FIXTURES / "hourly_parameters.json").read_text())
    rows = json.loads((FIXTURES / "hourly_rows.json").read_text())["rows"]
    return Traffic(
        roads, {k: F(v["value"]) for k, v in params["speeds"].items()}, tuple(rows)
    )


def test_drive_and_walk_speed_documents_every_hour():
    traffic = traffic_fixture()
    frame = tuple(sorted(h3.grid_disk(h3.latlng_to_cell(0, 0, 9), 12)))
    for hour in range(24):
        with patch.object(adapter, "scaled_actor", wraps=adapter.scaled_actor) as spy:
            traffic.route("SYN-N-0-0", "SYN-N-0-2", hour)
            traffic.area("SYN-N-0-0", 3, hour, frame)
            traffic.area("SYN-N-0-0", 3, hour, frame, mode="walk")
        assert len(spy.call_args_list) == 3
        for call, selected in zip(spy.call_args_list, (hour, hour, None), strict=True):
            expected = json.dumps(
                traffic.road_fixture(
                    tuple(
                        traffic.link_speed(link["link_id"], selected)
                        for link in traffic.roads["links"]
                    ),
                    "SYN-N-0-0",
                ),
                sort_keys=True,
            )
            assert call.args == (expected, 1.0)


def test_route_uses_summer_rows():
    assert "summer" in inspect.signature(Traffic.route).parameters
    traffic = traffic_fixture()
    summer = tuple(
        {**row, "summer": True, "speed_ratio": "1.000"} for row in traffic.rows
    )
    traffic = replace(traffic, rows=(*traffic.rows, *summer))
    ordinary = traffic.route("SYN-N-0-0", "SYN-N-0-1", 8)
    seasonal = traffic.route("SYN-N-0-0", "SYN-N-0-1", 8, summer=True)
    assert seasonal["minutes"] == F(3339, 1750)  # 1113 metres / 35 kph in minutes.
    assert ordinary["minutes"] == F(3339, 500)  # 1113 metres / 10 kph in minutes.
