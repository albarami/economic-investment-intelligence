"""L-83: closed trip parts, pinned millisecond boundaries, and real junctions."""

from copy import deepcopy
from fractions import Fraction as F
from unittest.mock import patch

import pytest
from product.tests.test_traffic_speed_document import traffic_fixture

from eii_product.areas_spike.traffic import Traffic


def test_route_has_only_itemised_product_fields():
    traffic = traffic_fixture()
    route = traffic.route("SYN-N-0-1", "SYN-N-0-2", 8)
    assert set(route) == {
        "link_ids",
        "link_minutes",
        "junction_seconds",
        "minutes",
        "line",
        "provenance",
        "evidence_status",
        "caveat",
    }
    assert route["link_ids"] == ("SYN-L-003",)
    assert route["link_minutes"] == (F(3339, 1150),)
    assert route["junction_seconds"] == 0
    assert route["minutes"] == sum(route["link_minutes"], F(0))
    assert route["line"] == ((0.0, 0.01), (0.0, 0.02))


# Method card: a route agrees within n x 0.001 seconds for n links; larger
# junction residuals are rounded half-up to milliseconds and negatives refused.
@pytest.mark.parametrize(
    "residual,expected",
    [("-0.002", "0"), ("0.002", "0"), ("0.0025", "0.003"), ("2.105", "2.105")],
)
def test_route_junction_resolution_boundaries(residual, expected):
    traffic = traffic_fixture()
    assert hasattr(Traffic, "route_for_measurement")
    raw = deepcopy(traffic.route_for_measurement("SYN-N-0-0", "SYN-N-0-2", 0))
    raw["trip"]["summary"]["time"] = F(9063, 50) + F(residual)
    with patch.object(Traffic, "route_for_measurement", return_value=raw):
        route = traffic.route("SYN-N-0-0", "SYN-N-0-2", 0)
    assert route["junction_seconds"] == F(expected)
    assert route["minutes"] == F(3021, 1000) + F(expected) / 60


def test_real_negative_disagreement_is_refused():
    traffic = traffic_fixture()
    assert hasattr(Traffic, "route_for_measurement")
    raw = deepcopy(traffic.route_for_measurement("SYN-N-0-1", "SYN-N-0-2", 8))
    raw["trip"]["summary"]["time"] = F(20034, 115) - F("0.0011")
    with patch.object(Traffic, "route_for_measurement", return_value=raw):
        with pytest.raises(ValueError, match="engine time below exact link sum"):
            traffic.route("SYN-N-0-1", "SYN-N-0-2", 8)


# Method card: a route agrees with its itemised total within
# n x 0.001 seconds for n links (here two links).
@pytest.mark.parametrize("residual", ["-0.002", "0.0015", "0.002"])
def test_resolution_scales_with_link_count(residual):
    traffic = traffic_fixture()
    raw = deepcopy(traffic.route_for_measurement("SYN-N-0-0", "SYN-N-0-2", 0))
    raw["trip"]["summary"]["time"] = F(9063, 50) + F(residual)
    with patch.object(Traffic, "route_for_measurement", return_value=raw):
        route = traffic.route("SYN-N-0-0", "SYN-N-0-2", 0)
    assert route["link_minutes"] == (F(3339, 1750), F(1113, 1000))
    assert route["junction_seconds"] == 0
    assert route["minutes"] == F(3021, 1000)


def test_route_provenance_and_status():
    traffic = traffic_fixture()
    for hour, provenance in ((None, "Public"), (0, "Simulated")):
        route = traffic.route("SYN-N-0-0", "SYN-N-0-2", hour)
        assert route["provenance"] == provenance
        assert route["evidence_status"] == "observed"
        assert route["caveat"] == (None if hour is None else "traffic_simulated")


@pytest.mark.parametrize("residual", ["0.0011", "2.105"])
def test_single_link_cannot_have_a_junction_cost(residual):
    traffic = traffic_fixture()
    raw = deepcopy(traffic.route_for_measurement("SYN-N-0-1", "SYN-N-0-2", 8))
    raw["trip"]["summary"]["time"] = F(20034, 115) + F(residual)
    with patch.object(Traffic, "route_for_measurement", return_value=raw):
        with pytest.raises(
            ValueError,
            match=r"^engine time above exact link time on a route without junctions$",
        ):
            traffic.route("SYN-N-0-1", "SYN-N-0-2", 8)


@pytest.mark.parametrize("residual", ["-0.001", "0.001"])
def test_single_link_printed_resolution_is_zero(residual):
    traffic = traffic_fixture()
    raw = deepcopy(traffic.route_for_measurement("SYN-N-0-1", "SYN-N-0-2", 8))
    raw["trip"]["summary"]["time"] = F(20034, 115) + F(residual)
    with patch.object(Traffic, "route_for_measurement", return_value=raw):
        route = traffic.route("SYN-N-0-1", "SYN-N-0-2", 8)
    assert route["junction_seconds"] == 0


def test_route_line_is_latitude_longitude():
    assert traffic_fixture().route("SYN-N-0-1", "SYN-N-0-2", 8)["line"] == (
        (0.0, 0.01),
        (0.0, 0.02),
    )
